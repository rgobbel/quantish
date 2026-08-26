"""Turn the network builder's graph into a runnable model.

The builder widget edits a plain dict:

    graph = {
      'gates':     {name: {'x': …, 'y': …, 'angle': spec,
                           'stage': name?, 'dgroup': name?,
                           'kind': 'phase'?, 'phase': degrees?}},
      'particles': {name: {'x': …, 'y': …, 'sign': 1 | -1, 'weight': 1.0}},
      'links':     [[src, dst], …],
    }

An angle (or a φ plate's phase) is a spec in the model files' own
syntax — radians, expressions included: 0, 'pi/6', 'rad(30)', 0.5 —
kept verbatim through load, edit, and save; validate_graph reports
specs qify cannot parse. A link source is a particle name ('p1') or a
gate output
('g1.upper'), and a destination is always a gate input ('g2.control').
A gate with kind 'phase' is a phase plate — an angle-0 gate with a
phase, used through its control wire only. A gate with kind 'delay'
is a delay gate: a portless pass-through, addressed in links by its
bare name ('g1.upper: d1', 'd1: g2.control'), emitted as the model's
delay_gates list. 'stage' names a user-assigned execution stage and
'dgroup' a diagram group; both are optional. This module validates the graph, derives run_stages by
topological layering over stage groups (ungrouped gates merge per
layer), and emits the same config shape the YAML model files load into.
"""
import re
from fractions import Fraction

import sympy as sym

from quantish.qnumber import qify, reserved_name
from quantish.util import SEP, WIRES


def variables_env(variables) -> tuple[dict, list[str]]:
    """Resolve a model's variables mapping into qified values, in
    definition order (later entries may use earlier ones), exactly as
    the engine does. Returns (env, problems) — problems instead of an
    exception, so every bad definition is reported at once."""
    env, problems = {}, []
    for name, expr in (variables or {}).items():
        if reserved_name(str(name)):
            problems.append(f'variable {name} shadows a builtin math '
                            'name')
            continue
        try:
            env[str(name)] = qify(expr, env)
        except Exception as exc:  # noqa: BLE001 — report and continue
            reason = str(exc).splitlines()[0]
            problems.append(f'variable {name}: cannot use {expr!r} — '
                            f'{reason}')
    return env, problems


def angle_degrees(spec, env=None) -> float:
    """The degrees value of an angle spec: the model files' radians
    syntax ('pi/6', 'rad(30)', 0.5, a variable name resolved through
    env), or the builder dialog's degree-marked entries ('30°',
    '22.5º'), kept verbatim so editing presents exactly what was
    typed. Raises ValueError for anything unparseable."""
    if isinstance(spec, str):
        s = spec.strip()
        if s and s[-1] in '°º˚':
            try:
                return float(s[:-1].strip())
            except ValueError:
                raise ValueError(f'{s!r} is not a number of degrees') \
                    from None
    val = qify(0 if spec in (None, '') else spec, env)
    return float(val.degrees)


def _angle_expr(deg) -> str:
    """The model-file spelling of an angle given in degrees: sympy's
    own rendering ('0', 'pi/6', '3*pi/8', '-pi/4') when the angle is an
    exact fraction of pi, rad(<degrees>) only otherwise. The canvas
    stores degrees as floats, so they are rationalized first — going
    straight through Real(deg).radians would drag a sympy Float along
    ('0.1666...*pi')."""
    frac = Fraction(deg / 180).limit_denominator(360)
    if abs(float(frac) - deg / 180) < 1e-12:
        return str(sym.Rational(frac.numerator, frac.denominator)
                   * sym.pi)
    return f'rad({deg:.12g})'


def _natural(name: str):
    """Sort key treating a trailing number numerically: d2 before d10."""
    m = re.match(r'(.*?)(\d+)$', name)
    return (m.group(1), int(m.group(2))) if m else (name, -1)


def _gate_of(endpoint: str):
    return endpoint.split(SEP)[0] if SEP in endpoint else None


def _endpoint(e: str, gates) -> tuple:
    """(gate, wire) of a link endpoint: ('g1', 'upper') for 'g1.upper',
    ('d1', None) for a bare delay-gate name, (None, None) for anything
    else (a particle, or an unknown name)."""
    if SEP in e:
        g, w = e.split(SEP, 1)
        return g, w
    if e in gates:
        return e, None
    return None, None


def validate_graph(graph, variables=None) -> list[str]:
    """Human-readable problems that keep the graph from running.
    Angle and phase specs resolve through the model's variables."""
    env, problems = variables_env(variables)
    gates = graph.get('gates', {})
    particles = graph.get('particles', {})
    links = [tuple(l) for l in graph.get('links', [])]

    if not gates:
        problems.append('add at least one gate')
    if not particles:
        problems.append('add at least one particle')

    delays = {n for n, g in gates.items() if g.get('kind') == 'delay'}
    sources = [src for src, _ in links]
    dests = [dst for _, dst in links]
    for src in {s for s in sources if sources.count(s) > 1}:
        problems.append(f'{src} feeds more than one input')
    for dst in {d for d in dests if dests.count(d) > 1}:
        problems.append(f'{dst} is fed by more than one wire')
    for src, dst in links:
        sg, sw = _endpoint(src, gates)
        if sg is None:
            if src not in particles:
                problems.append(f'link from unknown source {src}')
        elif sg in delays and sw is not None:
            problems.append(f'{src}: a delay gate has no ports — '
                            'link it by name')
        dg, dw = _endpoint(dst, gates)
        if dg is None or dg not in gates:
            problems.append(f'link into unknown gate input {dst}')
        elif dg in delays:
            if dw is not None:
                problems.append(f'{dst}: a delay gate has no ports — '
                                'link it by name')
        elif dw is None:
            problems.append(f'{dst}: link a gate through one of its '
                            'input ports')
        elif dw not in WIRES:
            problems.append(f'unknown input wire {dst}')

    linked = {p for p in particles if p in sources}
    for p in sorted(set(particles) - linked):
        problems.append(f'particle {p} is not connected to anything')

    fed = {_endpoint(dst, gates)[0] for _, dst in links}
    for g in sorted(set(gates) - fed):
        problems.append(f'gate {g} has no inputs')

    plates = {n for n, g in gates.items() if g.get('kind') == 'phase'}
    for end in sorted({e for l in links for e in l}):
        eg, ew = _endpoint(end, gates)
        if eg in plates and ew != 'control':
            problems.append(f'{end}: a phase plate only uses its '
                            'control wire')

    for name, g in sorted(gates.items()):
        if g.get('kind') == 'delay':
            continue
        field = 'phase' if g.get('kind') == 'phase' else 'angle'
        try:
            _deg = angle_degrees(g.get(field, 0), env)
            if abs(_deg) > 360:
                problems.append(
                    f'{name}: {field} {g.get(field)!r} is '
                    f'{_deg:.0f}° — more than a full turn, usually a '
                    'degrees-vs-radians mix-up')
        except sym.SympifyError:  # sympy's own message is noise
            problems.append(f'{name}: {field} {g.get(field)!r} is not '
                            'a valid expression')
        except Exception as exc:  # noqa: BLE001 — qify's message informs
            reason = str(exc).splitlines()[0]
            problems.append(f'{name}: cannot use {field} '
                            f'{g.get(field)!r} — {reason}')
    return problems


def gate_layers(graph) -> dict[str, int]:
    """Longest-path dependency layer of every gate (1 = no gate feeds
    it). A wiring loop raises ValueError — the engine cannot run one."""
    gates = graph.get('gates', {})
    feeds = {g: set() for g in gates}
    for src, dst in graph.get('links', []):
        sg = _endpoint(src, gates)[0]
        dg = _endpoint(dst, gates)[0]
        if sg in feeds and dg in feeds:
            feeds[sg].add(dg)
    layer = {}

    def _layer(g, path):
        if g in path:
            raise ValueError(f'wiring loop through {g}')
        if g not in layer:
            preds = [p for p in feeds if g in feeds[p]]
            layer[g] = 1 + max((_layer(p, path | {g}) for p in preds),
                               default=0)
        return layer[g]

    for g in gates:
        _layer(g, set())
    return layer


def derive_stages(graph) -> dict[str, list[str]]:
    """run_stages honoring user stage groups. A named stage may contain
    internal wiring — the engine splits such a stage into sub-stages by
    itself — so only orderings no topology can satisfy are errors: a
    wiring loop, or stages that feed each other. Ungrouped gates merge
    per dependency layer under stageN names. Stages order by dependency,
    then by the graph's stage_order list, then by name; gates inside a
    stage are listed in dependency order (the order the engine fires
    them)."""
    gates = graph.get('gates', {})
    glayer = gate_layers(graph)

    # a unit is a named stage group or a single ungrouped gate
    unit_of = {name: (('stage', gd['stage']) if gd.get('stage')
                      else ('gate', name))
               for name, gd in gates.items()}
    units = {}
    for name in sorted(gates):
        units.setdefault(unit_of[name], []).append(name)

    # inter-unit wires only: wiring inside a stage is the engine's job
    feeds = {u: set() for u in units}
    for src, dst in graph.get('links', []):
        sg = _endpoint(src, gates)[0]
        dg = _endpoint(dst, gates)[0]
        if sg in unit_of and dg in unit_of:
            a, b = unit_of[sg], unit_of[dg]
            if a != b:
                feeds[a].add(b)

    layer = {}

    def _layer(u, path):
        if u in path:
            names = ', '.join(sorted(x[1] for x in path))
            raise ValueError(f'no stage order can run this wiring: '
                             f'{names} feed each other')
        if u not in layer:
            preds = [p for p in feeds if u in feeds[p]]
            layer[u] = 1 + max((_layer(p, path | {u}) for p in preds),
                               default=0)
        return layer[u]

    for u in units:
        _layer(u, set())

    rank = {name: i for i, name in
            enumerate(graph.get('stage_order') or [])}
    stages = {}
    taken = {u[1] for u in units if u[0] == 'stage'}
    auto = 0
    for lyr in sorted(set(layer.values())):
        here = [u for u in units if layer[u] == lyr]
        named = sorted((u for u in here if u[0] == 'stage'),
                       key=lambda u: (rank.get(u[1], len(rank)), u[1]))
        for u in named:
            stages[u[1]] = sorted(units[u],
                                  key=lambda g: (glayer[g],
                                                 _natural(g)))
        anon = sorted((g for u in here if u[0] == 'gate'
                       for g in units[u]), key=_natural)
        if anon:
            auto += 1
            while f'stage{auto}' in taken:
                auto += 1
            stages[f'stage{auto}'] = anon
    return stages


def graph_to_config(graph, title: str, caption: str | None = None,
                    variables: dict | None = None,
                    symbolic: bool | None = None) -> dict:
    """The model-config dict the Simulation loads (no defaults mixed
    in). caption, variables, and symbolic ride along when given; angle
    and weight specs referencing the variables stay verbatim."""
    gates = graph.get('gates', {})
    delays = sorted((n for n, g in gates.items()
                     if g.get('kind') == 'delay'), key=_natural)
    config = {'title': title}
    if caption:
        config['caption'] = str(caption)
    if symbolic:
        config['symbolic'] = True
    config['run_stages'] = derive_stages(graph)
    config['particles'] = {
        name: {'weight': p.get('weight', 1), 'sign': p.get('sign', 1)}
        for name, p in sorted(graph.get('particles', {}).items())}
    def _spec(v):
        # the builder's degree-marked entries become the YAML's
        # radians syntax; everything else passes through verbatim
        if isinstance(v, str):
            s = v.strip()
            if s and s[-1] in '°º˚':
                return f'rad({float(s[:-1].strip()):g})'
        return v if isinstance(v, (int, float)) else str(v)

    config['gates'] = {
        name: ({'angle': 0, 'phase': _spec(g.get('phase', 0))}
               if g.get('kind') == 'phase'
               else {'angle': _spec(g.get('angle', 0))})
        for name, g in sorted(gates.items()) if name not in delays}
    if delays:
        config['delay_gates'] = delays
    if variables:
        config['variables'] = {str(k): v for k, v in variables.items()}
    config['links'] = {src: dst for src, dst in graph.get('links', [])}

    # diagram groups, only when the user assigned any (without them,
    # the engine already treats the run stages as the diagram groups).
    # Uncovered gates fall back to their run stage's group — the same
    # hierarchy — and groups run left to right in execution order
    dgroups = {}
    for name, g in sorted(gates.items()):
        if g.get('dgroup'):
            dgroups.setdefault(g['dgroup'], []).append(name)
    if dgroups:
        covered = {g for gs in dgroups.values() for g in gs}
        for sname, sgates in config['run_stages'].items():
            rest = [g for g in sgates if g not in covered]
            if rest:
                grp = dgroups.setdefault(sname, [])
                grp.extend(g for g in rest if g not in grp)
        order = {g: i for i, gs in
                 enumerate(config['run_stages'].values()) for g in gs}
        # the explicit order applies only when it covers every group —
        # a stale or partial list would misplace the fallback groups
        _order_list = graph.get('dgroup_order') or []
        rank = ({name: i for i, name in enumerate(_order_list)}
                if all(n in _order_list for n in dgroups) else {})
        config['diagram_groups'] = {
            n: gs for n, gs in sorted(
                dgroups.items(),
                key=lambda kv: (rank.get(kv[0], len(rank)),
                                min(order.get(g, 0) for g in kv[1]),
                                kv[0]))}
    return config


def coherence_warnings(graph) -> list[str]:
    """Softer than validate_graph: things that run fine but make the
    diagrams or the emitted model read badly. Currently: diagram groups
    whose run-stage ranges overlap (diagram columns follow the run
    stages, so such groups' boxes tangle — the book's groups always
    cover disjoint stage spans)."""
    try:
        stages = derive_stages(graph)
    except ValueError:
        return []
    pos = {g: i for i, gs in enumerate(stages.values()) for g in gs}
    spans = {}
    for name, gd in graph.get('gates', {}).items():
        if gd.get('dgroup'):
            lo, hi = spans.get(gd['dgroup'], (pos[name], pos[name]))
            spans[gd['dgroup']] = (min(lo, pos[name]),
                                   max(hi, pos[name]))
    warnings = []
    names = sorted(spans)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (alo, ahi), (blo, bhi) = spans[a], spans[b]
            # identical spans stack vertically in the diagrams and are
            # fine; only a partial overlap tangles the boxes
            if (alo <= bhi and blo <= ahi
                    and (alo, ahi) != (blo, bhi)):
                warnings.append(
                    f'diagram groups {a} and {b} overlap in the '
                    'execution order — their boxes will tangle in '
                    'the diagrams')
    return warnings


def config_to_graph(config) -> tuple[dict, list[str]]:
    """The inverse of graph_to_config: a builder graph from a loaded
    model config, canvas positions laid out one column per run stage.
    Returns (graph, notes); the notes say what the builder cannot carry
    (captions, variables, wire labels, symbolic angle forms — angles
    load as their resolved numeric degrees)."""
    from addict import Dict as Addict

    from quantish.simulation import Simulation

    base = {'string_precision': 2, 'max_symbolic_len': 40,
            'loglevel': 'warning'}
    base.update(config)
    base['config_path'] = 'builder-load'
    sim = Simulation(Addict(base))   # resolves variables, checks wiring

    notes = []
    if config.get('wire_labels'):
        notes.append('wire labels are not carried into the builder')
    env, _ = variables_env(config.get('variables'))

    stage_of = {g: s for s, gs in config['run_stages'].items() for g in gs}
    # diagram groups, minus the singleton padding graph_to_config adds
    dgroup_of = {g: d
                 for d, gs in (config.get('diagram_groups') or {}).items()
                 for g in gs if not (d == g and list(gs) == [g])}

    graph = {'gates': {}, 'particles': {}, 'links': []}
    col_of = {s: i for i, s in enumerate(config['run_stages'])}
    row_count = {}
    for name, gate in sim.fredkin_gates.items():
        deg = round(float(gate.theta.degrees), 10)
        pdeg = round(float(gate.phase.degrees), 10)
        col = col_of.get(stage_of.get(name), 0)
        row = row_count[col] = row_count.get(col, 0)
        row_count[col] += 1
        gd = {'x': 170 + col * 200, 'y': 40 + row * 150}

        def _keep(field, spec, resolved_deg):
            # the original spec survives verbatim — variable references
            # included, now that the variables travel with the model;
            # only a spec even the variables can't explain falls back
            try:
                angle_degrees(spec, env)
            except Exception:  # noqa: BLE001 — any unparseable spec
                expr = _angle_expr(resolved_deg)
                notes.append(f'{name}: {field} {spec} loaded as its '
                             f'value {expr}')
                return expr
            return spec if isinstance(spec, (int, float)) else str(spec)

        if pdeg and not deg:
            gd['kind'] = 'phase'
            gd['phase'] = _keep(
                'phase', config['gates'][name].get('phase', 0), pdeg)
        else:
            gd['angle'] = _keep(
                'angle', config['gates'][name].get('angle', 0), deg)
            if pdeg:
                notes.append(f'{name}: phase {pdeg:g}° dropped (the '
                             'builder only puts phases on φ plates)')
        if name in stage_of:
            gd['stage'] = stage_of[name]
        if name in dgroup_of:
            gd['dgroup'] = dgroup_of[name]
        graph['gates'][name] = gd

    for name in config.get('delay_gates', []):
        col = col_of.get(stage_of.get(name), 0)
        row = row_count[col] = row_count.get(col, 0)
        row_count[col] += 1
        gd = {'x': 170 + col * 200, 'y': 40 + row * 150,
              'kind': 'delay'}
        if name in stage_of:
            gd['stage'] = stage_of[name]
        if name in dgroup_of:
            gd['dgroup'] = dgroup_of[name]
        graph['gates'][name] = gd

    for i, (name, p) in enumerate(config['particles'].items()):
        # weight specs stay verbatim — the variables travel with the
        # model, so 'q45' or '0.5+0.87j' both survive the round trip
        spec = p.get('weight', 1)
        w = spec if isinstance(spec, (int, float)) else str(spec)
        graph['particles'][name] = {'x': 24, 'y': 60 + i * 70,
                                    'sign': int(p.get('sign', 1)),
                                    'weight': w}
    graph['links'] = [[src, dst] for src, dst in config['links'].items()]
    graph['stage_order'] = list(config['run_stages'])
    graph['dgroup_order'] = [d for d in (config.get('diagram_groups')
                                         or {})]
    return graph, notes


def config_to_yaml(config) -> str:
    """The config in the model files' style: block YAML, sections in the
    conventional order, flow mappings for the one-line entries."""
    def _scalar(v):
        s = str(v)
        return f"'{s.replace(chr(39), chr(39) * 2)}'" \
            if isinstance(v, str) else s

    lines = [f"title: {config['title']}"]
    if config.get('caption'):
        cap = str(config['caption'])
        if ': ' in cap or cap[:1] in '\'"#&*[]{}':
            cap = f"'{cap.replace(chr(39), chr(39) * 2)}'"
        lines += ['', f'caption: {cap}']
    if config.get('symbolic'):
        lines += ['', 'symbolic: true']
    lines += ['', 'run_stages:']
    for stage, gates in config['run_stages'].items():
        lines.append(f"  {stage}: [{', '.join(gates)}]")
    if 'diagram_groups' in config:
        lines += ['', 'diagram_groups:']
        for group, gates in config['diagram_groups'].items():
            lines.append(f"  {group}: [{', '.join(gates)}]")
    lines += ['', 'particles:']
    for name, p in config['particles'].items():
        w = p['weight']
        wtxt = (f'{w:.12g}' if isinstance(w, (int, float))
                else f"'{w}'")
        lines.append(f"  {name}: {{weight: {wtxt}, sign: {p['sign']}}}")
    lines += ['', 'gates:']
    for name, g in config['gates'].items():
        opts = f"angle: {g['angle']}"
        if 'phase' in g:
            opts += f", phase: {g['phase']}"
        lines.append(f"  {name}: {{{opts}}}")
    if config.get('delay_gates'):
        lines += ['', f"delay_gates: "
                      f"[{', '.join(config['delay_gates'])}]"]
    if config.get('variables'):
        lines += ['', 'variables:']
        for vname, vval in config['variables'].items():
            lines.append(f'  {vname}: {_scalar(vval)}')
    lines += ['', 'links:']
    for src, dst in config['links'].items():
        lines.append(f'  {src}: {dst}')
    return '\n'.join(lines) + '\n'
