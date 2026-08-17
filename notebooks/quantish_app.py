"""Quantish Physics — marimo front-end.

Pick a model, adjust gate angles with sliders, and everything downstream
reacts: exact final worlds (LaTeX weights), marginal summaries, circuit
diagrams (TikZ + Mermaid), the weight-evolution graph, Monte Carlo
sampling, the Bell/CHSH experiment, and the four-way weight-split
explorer.

Run with:  marimo edit notebooks/quantish_app.py   (or `marimo run` to serve)
"""

import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import cmath
    import logging
    import math
    import sys
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import pandas as pd
    import yaml
    from addict import Addict

    # Inline chart data in the Vega-Lite spec instead of marimo's
    # shared-memory virtual files: our frames are tiny, and virtual files
    # produce noisy 404/KeyError tracebacks when a slider re-creates a
    # chart while the browser still holds the old data URL.
    alt.data_transformers.enable('default')

    # make the repo importable no matter where marimo was launched from
    def _():
        repo = Path(__file__).resolve().parents[1]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))

    _()

    import multiworld.qnumber as qn
    from multiworld.qnumber import CalcMode

    CalcMode.default('Float')
    qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('multiworld').setLevel(logging.WARNING)

    from multiworld.epr import run_epr_experiment, supports_epr
    from multiworld.gate import FredkinGate
    from multiworld.montecarlo import run_monte_carlo
    from multiworld.simulation import Simulation
    from multiworld.mermaid_diagram import diagram, short_config
    from multiworld.network_graph import NetworkGraph

    REPO_DIR = Path(__file__).resolve().parents[1]
    MODELS_DIR = REPO_DIR / 'models'
    return (
        Addict,
        CalcMode,
        FredkinGate,
        MODELS_DIR,
        Simulation,
        alt,
        cmath,
        diagram,
        math,
        mo,
        NetworkGraph,
        pd,
        qn,
        run_epr_experiment,
        run_monte_carlo,
        short_config,
        supports_epr,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Quantish Physics
    A simulation of the quantish universe from Chapter 4 of
    *Good and Real* (Drescher, 2006): Fredkin gates, complex-weighted
    worlds, and EPR experiments.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    model_rescan = mo.ui.run_button(label='↻ rescan models')
    # remembers the selection across rescans (see the dropdown's on_change)
    last_model_get, last_model_set = mo.state('fig417')
    return last_model_get, last_model_set, model_rescan


@app.cell(hide_code=True)
def _(MODELS_DIR, last_model_get, last_model_set, mo, model_rescan):
    model_rescan  # dependency: pressing the button re-globs the directory

    def _():
        options = {p.stem: p for p in sorted(MODELS_DIR.glob('*.yaml'))
                   if p.stem != 'defaults'}
        default = last_model_get() if last_model_get() in options \
            else next(iter(options))
        return mo.ui.dropdown(
            options=options,
            value=default,
            label='model',
            on_change=lambda p: last_model_set(p.stem) if p is not None else None,
        )

    model_pick = _()
    mo.hstack([model_pick, model_rescan], justify='start', gap=1)
    return (model_pick,)


@app.cell(hide_code=True)
def _(Addict, MODELS_DIR, Simulation, mo, model_pick, yaml):
    def load_config(path):
        with open(MODELS_DIR / 'defaults.yaml') as f:
            cfg = yaml.safe_load(f)
        with open(path) as f:
            cfg.update(yaml.safe_load(f))
        cfg['loglevel'] = 'warning'
        return Addict(cfg)

    base_config = load_config(model_pick.value)

    mode_pick = mo.ui.radio(['Float', 'Symbolic'], value='Float',
                            label='math mode', inline=True)
    units_pick = mo.ui.radio(['degrees', 'radians'], value='degrees',
                             label='typed numbers are', inline=True)

    # ONE state for all gate angles: {gate: {'deg': float, 'expr': str|None}}.
    # marimo's state reactivity keys on the getter being referenced as a
    # global variable — a dict of per-gate states breaks the subscription
    # (the earlier bug), so everything lives under a single getter/setter.
    # 'expr' preserves the symbolic form (model YAML or typed) alongside
    # its numeric degree equivalent.
    def _():
        def centered(deg):
            d = deg % 360.0
            return d - 360.0 if d > 180.0 else d

        base_sim = Simulation(load_config(model_pick.value))
        names = list(base_sim.fredkin_gates.keys())
        angles = mo.state({
            g: {'deg': round(centered(float(gate.atheta.degrees)) * 2) / 2,
                'expr': str(base_config.gates[g].angle)}
            for g, gate in base_sim.fredkin_gates.items()})
        return names, angles

    gate_names, (angles_get, angles_set) = _()
    return (
        angles_get,
        angles_set,
        base_config,
        gate_names,
        load_config,
        mode_pick,
        units_pick,
    )


@app.cell(hide_code=True)
def _(angles_get, angles_set, gate_names, mo):
    # Sliders live in their OWN cell (and the text entries in theirs):
    # marimo never re-runs the cell that invoked a state setter, so tied
    # elements must be defined in separate cells — a text edit re-runs
    # this cell (rebuilding the sliders), a slider move re-runs the text
    # cell. Registration through mo.ui.dictionary globals keeps on_change
    # events flowing.
    def _():
        def slider_cb(g):
            def cb(v):
                angles_set({**angles_get(), g: {'deg': float(v), 'expr': None}})
            return cb

        return mo.ui.dictionary({
            g: mo.ui.slider(
                -180, 180, step=0.5,
                value=max(0.0, min(180.0, round(angles_get()[g]['deg'] * 2) / 2)),
                label=f'**{g}**', show_value=True, full_width=True,
                on_change=slider_cb(g))
            for g in gate_names})

    angle_slider_elems = _()
    return (angle_slider_elems,)


@app.cell(hide_code=True)
def _(angles_get, angles_set, gate_names, math, mo, mode_pick, qn, units_pick):
    def _():
        def text_cb(g):
            def cb(raw):
                txt = (raw or '').strip().rstrip('º°').strip()
                if not txt:
                    return
                try:
                    num = float(txt)
                    deg = num if units_pick.value == 'degrees' else math.degrees(num)
                    angles_set({**angles_get(), g: {'deg': deg, 'expr': None}})
                    return
                except ValueError:
                    pass
                try:
                    rad = float(qn.qify(txt))  # symbolic expression, radians
                    angles_set({**angles_get(),
                                g: {'deg': math.degrees(rad), 'expr': txt}})
                except Exception:  # noqa: BLE001 — unparseable: keep previous value
                    pass
            return cb

        def shown(cur):
            # The entry mirrors the current math mode: symbolic form when in
            # Symbolic mode (and one exists), numeric degrees otherwise.
            if mode_pick.value == 'Symbolic' and cur['expr']:
                return cur['expr']
            return f"{cur['deg']:.1f}º"

        return mo.ui.dictionary({
            g: mo.ui.text(value=shown(angles_get()[g]), on_change=text_cb(g))
            for g in gate_names})

    angle_text_elems = _()
    return (angle_text_elems,)


@app.cell(hide_code=True)
def _(
    angle_slider_elems,
    angle_text_elems,
    base_config,
    gate_names,
    mo,
    mode_pick,
    units_pick,
):
    def _():
        rows = [mo.hstack([angle_slider_elems[g], angle_text_elems[g]],
                          widths=[5, 1], align='center')
                for g in gate_names]
        return mo.vstack([
            mo.md(f"**{base_config.title}** — gate angles. Slider and entry track "
                  "each other; sliders are degrees (0-centered). Typed numbers "
                  "use the units selector; anything else is a symbolic radian "
                  "expression (`pi/8`, `rad(30)`, `acos(4/5)`)."),
            mo.hstack([mode_pick, units_pick], wrap=True, justify='start', gap=2),
            mo.vstack(rows),
        ])

    _()
    return


@app.cell(hide_code=True)
def _(mo):
    run_btn = mo.ui.run_button(label='▶ Run simulation')
    run_btn
    return (run_btn,)


@app.cell(hide_code=True)
def _(mo, sim):
    mo.accordion({'## Loaded Configuration Details': mo.accordion(sim.__dict__, multiple=True, lazy=True)})
    return


@app.cell(hide_code=True)
def _(
    CalcMode,
    Simulation,
    angles_get,
    gate_names,
    load_config,
    math,
    mo,
    mode_pick,
    model_pick,
    qn,
    run_btn,
):
    # Gated on the button: changing sliders/text/model/mode marks results
    # stale (this message) but leaves the previous results visible below.
    mo.stop(not run_btn.value,
            mo.md('_settings changed — press **▶ Run simulation** to (re)compute; '
                  'results below are from the previous run_'))

    def _():
        def angle_for(g):
            cur = angles_get()[g]
            if cur['expr']:
                return qn.qify(cur['expr'])  # symbolic expression, in radians
            return math.radians(cur['deg'])

        try:
            CalcMode.default(mode_pick.value)
            qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
            config = load_config(model_pick.value)
            for g in gate_names:
                config.gates[g].angle = angle_for(g)
            run = Simulation(config)
            run.run()
            return run
        except Exception as exc:  # noqa: BLE001 — old-format models raise all sorts
            mo.stop(True, mo.md(
                f"**{model_pick.value.stem} failed to load or run** — probably "
                f"an old-format model.\n\n```\n{exc}\n```"))

    sim = _()

    def _():
        angles = ', '.join(f'{g}={float(gate.atheta.degrees):.1f}º'
                           for g, gate in sim.fredkin_gates.items())
        return mo.md(
            f"Ran **{sim.title}** ({mode_pick.value} mode) — {angles}; "
            f"{len(sim.run_stages)} steps, "
            f"{len(sim.result_space.index)} final world(s), "
            f"total probability "
            f"{sum(float(p.probability) for p in sim.result_space.index.values()):.6f}")

    _()
    return (sim,)


@app.cell(hide_code=True)
def _(FredkinGate, qn):
    def cpair(g: FredkinGate, w:qn.Complex, twist=False):
        """
        From AIM-1026a: the four split components of weight w.
        Values are precomputed for speed. twist=True gives the minus-sign
        column (cos/sin of theta - pi/2, i.e. sin/cos of theta).
        """
        if not twist:
            c2a = w * g.cos2_theta
            c2b = w * g.cos_sin_theta
            c3a = w * g.sin2_theta
            c3b = w * g.mcos_sin_theta
        else:
            c2a = w * g.cos2_twist
            c2b = w * g.cos_sin_twist
            c3a = w * g.sin2_twist
            c3b = w * g.mcos_sin_twist
        return c2a, c2b, c3a, c3b

    return (cpair,)


@app.cell(hide_code=True)
def _(cmath, mo, qn):
    def latex_weight(w, prec=4) -> str:
        # In Symbolic mode, render the exact sympy expression as LaTeX.
        try:
            if qn.CalcMode.default() == 'Symbolic' and qn.isq(w):
                import sympy
                return sympy.latex(qn.simplify(w).v)
        except Exception:  # noqa: BLE001 — fall back to the numeric form
            pass
        wc = complex(w)
        real, imag = wc.real, wc.imag
        parts = []
        if abs(real) > 1e-12:
            sign = '-' if real < 0 else '+'
            parts.append(f'{sign}{abs(round(real, 2))}')
        if abs(imag) > 1e-12:
            sign = '-' if imag < 0 else '+'
            parts.append(f' {sign}{abs(imag):.{prec}g}i')
        return ''.join(parts) if parts else f'{0.00:+.2f}'

    def math_weight(w, prec=4) -> str:
        # latex_weight wrapped as inline math. Whitespace is normalized
        # because markdown doesn't recognize '$ x$' (leading space) as
        # math — symbolic LaTeX often leads with '- \frac{...}'.
        return f'${" ".join(latex_weight(w, prec).split())}$'

    def phase_deg(w) -> float:
        return cmath.phase(complex(w)) * 180.0 / cmath.pi

    def md_table(headers, rows) -> str:
        # NB: markdown needs a blank line before a table, and literal '|'
        # inside cells (world keys use it as a separator) must be escaped
        # or they read as column breaks.
        def cell(c):
            return str(c).replace('|', r'\|')
        lines = ['',
                 '| ' + ' | '.join(headers) + ' |',
                 '|' + '|'.join(['---'] * len(headers)) + '|']
        lines += ['| ' + ' | '.join(cell(c) for c in row) + ' |' for row in rows]
        return '\n'.join(lines)

    _ = mo.md('')  # helpers only
    return latex_weight, math_weight, md_table, phase_deg


@app.cell(hide_code=True)
def _(math_weight, md_table, mo, phase_deg, short_config, sim):
    # Worlds sorted canonically: gate (in evaluation order), then port
    # (upper before lower), then sign (+ before −); the configuration
    # label's coordinates are reordered to match.
    def _():
        rows = [(
            f'`{short_config(p, key=sim.coord_sort_key).replace("|", " ")}`',
            math_weight(p.weight, prec=3),
            f'${float(p.probability):.4f}$',
            f'${phase_deg(p.weight):+.1f}º$',
        ) for p in sorted(sim.result_space.index.values(),
                          key=sim.world_sort_key)]
        return mo.accordion({'## Final worlds\n': mo.md(md_table(
            ['configuration', 'weight $w$', r'$\lvert w\rvert^2$', 'phase'],
            rows))})

    _()
    return


@app.cell(hide_code=True)
def _(md_table, mo, sim):
    # Marginal in the statistics sense: each row sums |w|² over every
    # final world containing that coordinate — the chance of finding that
    # particle, with that sign, at that port, regardless of where the
    # other particles ended up. Rows follow gate evaluation order (upper
    # before lower, + before −), so a port's +/− pair sits together and
    # sums to the port's total output probability.
    def _():
        acc = {}
        for p in sim.result_space.index.values():
            prob = float(p.probability)
            for coord in p.coords.values():
                entry = acc.setdefault(f'{coord.pkey}@{coord.position.origin}',
                                       [coord, 0.0])
                entry[1] += prob
        rows = [(f'`{key}`', f'{entry[1]:.4f}')
                for key, entry in sorted(acc.items(),
                                         key=lambda kv: sim.coord_sort_key(kv[1][0]))]
        return mo.accordion({
            '## Marginal probabilities (one coordinate at a time)':
                mo.md(r'Each row sums $\lvert w\rvert^2$ over every final world '
                      'in which that particle, with that sign, sits at that '
                      'port — its probability there *regardless of where the '
                      'other particles ended up* (the marginal over the rest '
                      'of the configuration). The +/− rows at one port '
                      "together give the port's total output probability.\n" +
                      md_table(['coordinate', 'probability'], rows))
        })

    _()
    return


@app.cell(hide_code=True)
def _(md_table, mo, sim):
    # Per-step gate traffic: what arrived at each port (previous step's
    # coordinate endpoints) and what left it (that step's origins), with
    # per-sign probabilities and the aggregate Σ (|Σ|² and phase).
    def _():
        rows = [(row['step'], row['gate'], row['port'],
                 row['input'].replace('\n', '<br>'),
                 row['output'].replace('\n', '<br>'))
                for row in sim.gate_io()]
        return mo.accordion({
            '## Gate inputs and outputs by step':
                mo.md(md_table(['step', 'gate', 'port', 'input', 'output'], rows))
        })

    _()
    return


@app.cell(hide_code=True)
def _(mo, sim):
    # Depends on sim, so it refreshes on every Run (runs are now explicit,
    # so the pdflatex cost is paid once per Run, not per slider move).
    def _():
        from multiworld.tikz_diagram import render_diagram, spec_from_simulation
        try:
            overrides = {g: f'{float(gate.atheta.degrees):.1f}°'
                         for g, gate in sim.fredkin_gates.items()}
            img = render_diagram(spec_from_simulation(sim), dpi=150,
                                 angle_overrides=overrides)
            if img is None:
                return mo.md('_TikZ render unavailable (needs pdflatex + imagemagick)_')
            return mo.image(img, caption='circuit (TikZ)')
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'_TikZ diagram failed: {exc}_')

    mo.vstack([mo.md('## Circuit diagram (TikZ)'), _()])
    return


@app.cell(hide_code=True)
def _(diagram, mo, sim):
    def _():
        # The generated source carries no theme, and mo.mermaid's own
        # theme choice is unreadable on nested subgraphs — so pin the
        # palette of the old CLI-rendered SVGs (mermaid's classic
        # 'default' look): light-yellow group/gate clusters, light-gray
        # port nodes. Injected into the frontmatter alongside the title.
        theme = ('config:\n'
                 '  theme: base\n'
                 '  themeVariables:\n'
                 "    clusterBkg: '#ffffde'\n"
                 "    clusterBorder: '#aaaa33'\n"
                 "    primaryColor: '#ececec'\n"
                 "    primaryBorderColor: '#999999'\n"
                 "    primaryTextColor: '#333333'\n"
                 "    lineColor: '#333333'\n"
                 "    titleColor: '#333333'\n"
                 "    edgeLabelBackground: 'rgba(232,232,232,0.8)'\n"
                 'title:')
        try:
            src = str(diagram(sim, output_file=None, has_run=True)).replace(
                'title:', theme, 1)
            return mo.mermaid(src)
        except Exception as exc:  # noqa: BLE001
            return mo.md(f'_Mermaid diagram failed: {exc}_')

    mo.vstack([mo.md('## Gate network with port values (Mermaid)'), _()])
    return


@app.cell(hide_code=True)
def _(mo, NetworkGraph, sim):
    def _():
        from matplotlib import pyplot as plt
        fig = NetworkGraph(sim.all_points, sim).figure()
        # deregister from pyplot so slider-driven reruns don't accumulate
        # open figures (the Figure object itself stays renderable)
        plt.close(fig)
        return fig

    mo.vstack([mo.md('## Weight evolution (worlds × steps)'), _()])
    return


@app.cell(hide_code=True)
def _(math_weight, md_table, mo, short_config, sim):
    # Tabular twin of the weight-evolution graph: per stage, one row per
    # parent→child branch — the input world and its weight, the literal
    # per-particle factors the gate applied (cos²θ, ±i·sinθcosθ, sin²θ),
    # the branch amplitude, and the output world's total weight. Where
    # branch w ≠ world w, interfering branches merged into that world.
    def _():
        def label(p):
            return f'`{short_config(p, key=sim.coord_sort_key).replace("|", " ")}`'

        def factor_cell(w, parent, contrib):
            # A merged world stores only its FIRST branch's per-particle
            # factors; for other branches show just the branch's overall
            # multiplier Π (recovered as branch w / input w).
            facts = {name: f for name, f in w.factors.items() if f is not None}
            try:
                expected = complex(parent.weight)
                for f in facts.values():
                    expected *= complex(f)
                stored_ok = abs(expected - complex(contrib)) < 1e-9
            except (TypeError, ValueError):
                stored_ok = True  # symbolic with free symbols: trust the stored factors
            if stored_ok:
                return '<br>'.join(f'{name}: {math_weight(f)}'
                                   for name, f in facts.items()) or '—'
            try:
                return f'Π: {math_weight(complex(contrib) / complex(parent.weight))}'
            except (TypeError, ValueError, ZeroDivisionError):
                return 'Π: ?'

        by_step = {}
        for pt in sim.all_points.index.values():
            by_step.setdefault(pt.step, []).append(pt)
        sections = {}
        for step in sorted(by_step):
            worlds = sorted(by_step[step], key=sim.world_sort_key)
            if step == 0:
                sections['Step 0 — initial world'] = mo.md(md_table(
                    ['world', 'weight $w$'],
                    [(label(w), math_weight(w.weight)) for w in worlds]))
                continue
            rows = []
            for w in worlds:
                out_label = label(w) + (' _(cancelled)_' if w.cancelled else '')
                for parent, contrib in sorted(w.contributions.items(),
                                              key=lambda kv: sim.world_sort_key(kv[0])):
                    rows.append((label(parent), math_weight(parent.weight),
                                 factor_cell(w, parent, contrib),
                                 math_weight(contrib), out_label,
                                 math_weight(w.weight)))
            gates = ', '.join(sim.run_stages[step - 1])
            sections[f'Step {step} — {gates}'] = mo.md(md_table(
                ['input world', '$w_{in}$', 'factors', 'branch $w$',
                 'output world', '$w_{out}$'], rows))
        return mo.accordion({'## Weight evolution table':
                             mo.accordion(sections, multiple=True, lazy=True)})

    _()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Monte Carlo sampling
    Optional sampled trials on top of the exact run above: each trial
    draws one final world from the evolved superposition with
    probability $\lvert w\rvert^2$. This is the faithful simulation of a
    real experiment — interference stays intact until observation, and
    frequencies converge on the exact values as trials grow.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mc_trials = mo.ui.slider(
        steps=[100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000,
               100000, 200000, 500000, 1000000],
        value=20000, label='trials', show_value=True)
    mc_trials_text = mo.ui.text(value='', placeholder='custom trial count')
    mc_seed = mo.ui.number(value=42, label='seed')
    mc_button = mo.ui.run_button(label='Run Monte Carlo')
    mo.hstack([mc_trials, mc_trials_text, mc_seed, mc_button],
              wrap=True)
    return mc_button, mc_seed, mc_trials, mc_trials_text


@app.cell(hide_code=True)
def _(
    mc_button,
    mc_seed,
    mc_trials,
    mc_trials_text,
    md_table,
    mo,
    run_monte_carlo,
    sim,
):
    mo.stop(not mc_button.value, mo.md('_press **Run Monte Carlo** to sample_'))

    def _():
        try:  # the text entry, when it parses, overrides the slider
            n_trials = max(1, int(mc_trials_text.value.strip()))
        except ValueError:
            n_trials = int(mc_trials.value)
        results = run_monte_carlo(sim, n_trials, mode='terminal',
                                  seed=int(mc_seed.value))
        tally = results['terminal']
        pred = results['predicted']
        rows = []
        tvd = 0.0
        for key in sorted(set(tally) | set(pred), key=lambda k: -pred.get(k, 0)):
            freq = tally.get(key, 0) / n_trials
            tvd += abs(freq - pred.get(key, 0.0))
            rows.append((f'`{key.split(":")[0][:60].replace("|", " ")}`',
                         tally.get(key, 0),
                         f'{freq:.4f}', f'{pred.get(key, 0.0):.4f}'))
        return mo.md(f'{n_trials} draws from the final superposition; '
                     f'total variation distance {tvd / 2:.4f}\n\n' +
                     md_table(['world', 'count', 'freq', 'exact'], rows))

    _()
    return


@app.cell(hide_code=True)
def _(mo):
    # Defined independently of sim/mode so a math-mode change or a Run can
    # never reset the user's chosen trial count.
    epr_trials = mo.ui.slider(0, 50000, step=1000, value=0,
                              label='trials per cell (0 = exact only)',
                              show_value=True)
    epr_button = mo.ui.run_button(label='Run EPR experiment')
    return epr_button, epr_trials


@app.cell(hide_code=True)
def _(base_config, mo):
    # Sweep-angle entries, reseeded from the model's qa/qb/qc variables
    # (or the canonical 0, pi/8, pi/4) when the model changes. Same input
    # forms as the gate-angle entries: a bare number in the selected
    # units, anything else a symbolic radian expression.
    def _():
        from multiworld.epr import DEFAULT_VALUES
        model_vars = {str(k).lower(): str(v)
                      for k, v in base_config.variables.items()}
        return mo.ui.dictionary({
            k: mo.ui.text(value=model_vars.get(k, v), label=f'**{k}** =')
            for k, v in DEFAULT_VALUES.items()})

    epr_angle_elems = _()
    return (epr_angle_elems,)


@app.cell(hide_code=True)
def _(epr_angle_elems, epr_button, epr_trials, mo, sim, supports_epr):
    mo.stop(not supports_epr(sim))
    mo.vstack([
        mo.md(r"""
    ## EPR-Bell experiment
    **What the sweep does:** it re-runs the whole circuit **nine times**,
    once per pair $(\theta_1, \theta_2)$ from the sweep angles
    $\{q_a, q_b, q_c\}$ chosen below — "measuring $p_1$ at $\theta_1$
    and $p_2$ at $\theta_2$" by overriding the measurement gates
    ($g_7 = \theta_1$, $g_8 = (Q_5{+}Q_6) - \theta_2$ on two-stage
    circuits; $g_5/g_6$ on one-stage). Each cell tabulates the conditional
    discrepancy of the two outcomes; the grid then tests **Bell**
    ($d(a,c) \le d(a,b)+d(b,c)$) and **CHSH** ($|S| \le 2$) against the
    intrinsic law $d = \sin^2(\theta_1 - \theta_2)$.
    """),
        mo.accordion({'How the fig 4.17 circuit works': mo.md(r"""
    Condensed from Gary Drescher's explanation of the revised circuit.

    **The splitting rule.** A gate measuring at angle $Q$ splits each
    incoming weight into a *measurement-parallel* component — the
    particle passes straight across, weight × $e^{iQ}\cos Q$ — and a
    *measurement-perpendicular* component — the particle crosses over,
    weight × $e^{i(Q+\pi/2)}\sin Q$. Perpendicular is literal: the
    crossed component is rotated $\pi/2$ from the straight one, so
    adding $\pi/2$ to a gate's angle swaps the roles of its two
    switch-wire outputs.

    **Why $Q_2 = Q_1 + \pi/2$.** With the $\pi/2$ term, the states
    where $p_1$ and $p_2$ emerge with *matching* positions acquire
    identical weights: one gate contributes $e^{iQ}\cos Q$ and the
    other $e^{i(Q-\pi/2)}\sin Q$ — in either order, so both-upper and
    both-lower each multiply the initial weight by
    $e^{i(2Q-\pi/2)}\sin Q\cos Q$. The mismatched states instead get
    $e^{i2Q}\cos^2 Q$ and $-e^{i2Q}\sin^2 Q$, which are never equal.
    (Try setting $Q_2 = Q_1$: the circuit still works, but the coupling
    inverts — *opposite* positions couple, and $p_3$ exits $g_4$'s
    lower wire instead of its upper.)

    **Two gates acting as one.** $g_5$ and $g_6$ fire simultaneously,
    so each successor picks up factors from both. On the both-upper and
    both-lower configurations their joint effect is a *real* multiple
    of $e^{i(Q_5+Q_6)}$ — the pair acts like a single measurement at
    angle $Q_5{+}Q_6$, and $g_7/g_8$ likewise at $Q_7{+}Q_8$ (the same
    roles $g_1$ and $g_2$ play in fig 4.7).

    **Split, then reassemble.** When $Q_5{+}Q_6 = Q_7{+}Q_8$, the
    second stage reuses the first's summed angle and undoes its
    splitting, re-establishing the both-upper/both-lower correlation.
    The reassembly is interference: both-upper and both-lower share
    successor configurations where their weights add — which is why the
    matching states had to carry equal weights in the first place (the
    $\pi/2$ term again).

    **The measurement.** After $g_7/g_8$ the two measured positions
    disagree at rate $\sin^2\bigl((Q_5{+}Q_6)-(Q_7{+}Q_8)\bigr)$ —
    perfect correlation when the sums match. The sweep sets
    $g_7 = \theta_1$ and $g_8 = (Q_5{+}Q_6)-\theta_2$, reducing the law
    to $\sin^2(\theta_1-\theta_2)$.

    **The point.** Before $g_5/g_6$ the universe is already a
    superposition of both-upper and both-lower: the positions are
    correlated though neither particle has a definite one. Scrambling
    the correlation at $g_5/g_6$ and re-establishing it at $g_7/g_8$
    demonstrates *from within the universe* that the correlation has no
    hidden-variable explanation: by Bell's theorem, no pre-assigned
    definite outcomes per angle can jointly reproduce the grid's
    discrepancy rates (barring influence between the two measurements
    themselves — which this circuit's topology, like sufficiently
    distant real-world measurements, rules out).
    """)}),
        mo.md(r"""
    **Choosing the sweep angles.** Only differences matter — the law is
    $\sin^2(\theta_1-\theta_2)$, with period $\pi$ — so the one hard
    constraint is that the three angles be **distinct (mod π)**: equal
    angles make cells compare an angle with itself and the inequalities
    degenerate. Any distinct triple is a valid experiment; whether it
    *violates* the classical bounds depends on spacing. With equal
    spacing $\delta$, Bell is violated exactly when $0 < \delta < 45°$
    (largest excess at $\delta = 30°$), and the canonical set
    $(0°, 22.5°, 45°)$ drives CHSH to $1{+}\sqrt2 \approx 2.414$.
    A bare number below uses the units selector at the top; anything
    else is read as a symbolic radian expression (`pi/8`, `rad(30)`).

    With trials = 0 (the default) each cell uses only the exact final
    worlds — fast. Setting trials adds per-cell Monte Carlo sampling on
    top. **Symbolic mode multiplies the cost**: nine exact symbolic runs
    with non-special angles may take several seconds even at 0 trials.
    """),
        mo.hstack([epr_angle_elems['qa'], epr_angle_elems['qb'],
                   epr_angle_elems['qc']],
                  justify='start', gap=2),
        mo.hstack([epr_trials, epr_button], justify='start'),
    ])
    return


@app.cell(hide_code=True)
def _(
    epr_angle_elems,
    epr_button,
    epr_trials,
    math,
    md_table,
    mo,
    qn,
    run_epr_experiment,
    sim,
    supports_epr,
    units_pick,
):
    mo.stop(not supports_epr(sim))
    mo.stop(not epr_button.value, mo.md('_press **Run EPR experiment** to sweep_'))

    def _():
        def parse_angle(raw):
            # same convention as the gate-angle entries: a bare number is in
            # the selected units, anything else a symbolic radian expression
            txt = (raw or '').strip().rstrip('º°').strip()
            try:
                num = float(txt)
                return qn.qify(num if units_pick.value == 'radians'
                               else math.radians(num))
            except ValueError:
                return qn.qify(txt)

        try:
            values = {k: parse_angle(v)
                      for k, v in epr_angle_elems.value.items()}
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            mo.stop(True, mo.md(f'**unparseable sweep angle** — {exc}'))
        mo.stop(len({round(float(v) % math.pi, 9) for v in values.values()}) < 3,
                mo.md('**sweep angles must be distinct (mod π)** — equal angles '
                      'make cells compare an angle with itself and the '
                      'inequalities degenerate'))
        res = run_epr_experiment(sim, n_trials=int(epr_trials.value), seed=1,
                                 values=values)
        labels = list(res['values'].keys())

        def grid_table(getter, fmt='{:.4f}'):
            rows = [[f'**{l1}**'] + [fmt.format(getter(res['grid'][(l1, l2)]))
                                     for l2 in labels]
                    for l1 in labels]
            return md_table([r'$\theta_1 \backslash \theta_2$'] + labels, rows)

        parts = [
            'sweep angles: ' + ', '.join(
                f'{k} = {math.degrees(float(v)):.1f}º'
                for k, v in values.items()),
            '**observed discrepancy** (sampled)' if epr_trials.value else '**exact discrepancy**',
            grid_table(lambda c: c.get('sampled', c['exact'])),
            r'**analytical** $\sin^2(\theta_1-\theta_2)$',
            grid_table(lambda c: c['analytical']),
            '**classical hidden-variable prediction**',
            grid_table(lambda c: c['classical']),
        ]
        bell, bell_at = res['bell_exact']
        chsh, chsh_at = res['chsh_exact']
        parts.append(
            f'Bell excess (exact): **{bell:+.4f}** at {bell_at} — '
            f'{"**VIOLATED**" if bell > 1e-9 else "satisfied"}  \n'
            f'CHSH $|S|$ (exact): **{chsh:.4f}** at {chsh_at} — '
            f'{"**VIOLATED**" if chsh > 2 + 1e-9 else "satisfied"}')
        return mo.md('\n\n'.join(parts))

    _()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Weight-split explorer
    The four-way split of one Fredkin gate measurement at angle $\theta$:
    $c_{2a} = w\cos^2\theta$, $c_{2b} = i\,w\sin\theta\cos\theta$
    (straight), $c_{3a} = w\sin^2\theta$,
    $c_{3b} = -i\,w\sin\theta\cos\theta$ (cross); $c_2 = c_{2a}+c_{2b}$,
    $c_3 = c_{3a}+c_{3b}$. A minus-sign particle swaps the roles.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    ws_theta = mo.ui.slider(-90, 90, step=5, value=30, label='θ (º)',
                            show_value=True)
    ws_sign = mo.ui.switch(value=True, label='sign + (off = −)')
    ws_wmag = mo.ui.slider(0.0, 1.0, step=0.05, value=1.0, label='|w|',
                           show_value=True)
    ws_wphase = mo.ui.slider(-180, 180, step=5, value=0, label='arg(w) (º)',
                             show_value=True)
    ws_components = mo.ui.multiselect(
        options=['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b'],
        value=['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b'],
        label='components')
    # one value drives both chart dimensions, so the 1:1 aspect (which
    # keeps the unit circle circular) can't be broken by stretching
    ws_size = mo.ui.slider(300, 1000, step=25, value=500,
                           label='chart size (px)', show_value=True)
    mo.hstack([ws_theta, ws_sign, ws_wmag, ws_wphase, ws_components, ws_size],
              wrap=True)
    return ws_components, ws_sign, ws_size, ws_theta, ws_wmag, ws_wphase


@app.cell(hide_code=True)
def _(
    FredkinGate,
    alt,
    cmath,
    cpair,
    latex_weight,
    math,
    mo,
    pd,
    phase_deg,
    qn,
    ws_components,
    ws_sign,
    ws_size,
    ws_theta,
    ws_wmag,
    ws_wphase,
):
    def _():
        gate = FredkinGate('ws', qn.qify(math.radians(ws_theta.value)))
        w = ws_wmag.value * cmath.exp(1j * math.radians(ws_wphase.value))
        c2a, c2b, c3a, c3b = (complex(x) for x in
            cpair(gate, qn.Complex(w), twist=not ws_sign.value))
        data = {'c2': c2a + c2b, 'c3': c3a + c3b,
                'c2a': c2a, 'c2b': c2b, 'c3a': c3a, 'c3b': c3b}
        order = ['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b']
        sel = [c for c in order if c in ws_components.value]
        frame = pd.DataFrame({
            'parallel': [data[c].real for c in sel],
            'perpendicular': [data[c].imag for c in sel],
            'component': sel,
        })
        base = alt.Chart(frame)
        vectors = base.mark_rule(strokeWidth=2.5).encode(
            x2=alt.datum(0.0),
            x=alt.X('parallel:Q', axis=alt.Axis(title='Parallel (Re)'),
                    scale=alt.Scale(domain=[-1.1, 1.1])),
            y2=alt.datum(0.0),
            y=alt.Y('perpendicular:Q', axis=alt.Axis(title='Perpendicular (Im)'),
                    scale=alt.Scale(domain=[-1.1, 1.1])),
            color=alt.Color('component:N', sort=order,
                            scale=alt.Scale(domain=order)),
        )
        labels = base.mark_text(align='left', baseline='middle', dx=7).encode(
            x='parallel:Q', y='perpendicular:Q', text='component:N',
            color=alt.Color('component:N', sort=order,
                            scale=alt.Scale(domain=order)),
        )
        sign_str = '+' if ws_sign.value else '−'
        chart = (vectors + labels).properties(
            title=f'θ = {ws_theta.value}º, sign = {sign_str}',
            width=int(ws_size.value), height=int(ws_size.value))
        lines = []
        for name in sel:
            val = data[name]
            lines.append(
                rf"{name} &= {latex_weight(val, prec=2)}"
                rf" &\quad \texttt{{Pr}} &= {abs(val)**2:.2f} & \phi &= {phase_deg(val):.1f}\degree\\")
        joined = '\n'.join(lines)
        latex = rf"""
    $$
    \begin{{aligned}}
    {joined}
    \end{{aligned}}
    $$
    """
        # plain display (not mo.ui.altair_chart): no selection plumbing,
        # and with inline data no virtual-file churn on slider moves
        return mo.hstack([chart, mo.md(latex)], align='center', justify='start')

    _()
    return


if __name__ == "__main__":
    app.run()
