"""The decoherence lab's slots: a model in a slot — its spec, sliders,
on/off boxes, screen panel, diagram, stage views, and readout — built
once per model choice and updated in place as the sliders move. The
notebook keeps the widgets bound as cell globals and the two plain
dicts every slot shares: `hit_store` ({'seq', 'hits': {slot: [...]}},
the sampled hits, the rebuild baseline) and `current` (slot -> the
settings the curves were last computed for, what fire and reset read
instead of the sliders).
"""
from __future__ import annotations

import math

import marimo as mo

from quantish.apps.curves import grouped_curves, push_curves
from quantish.builder_widget import (
    DiagramWidget,
    HtmlWidget,
    NetworkGraphWidget,
    ScreenPanelWidget,
)
from quantish.coherence import path_coherence, signed_visibility
from quantish.diagram_layout import diagram_geometry
from quantish.display import html_table
from quantish.network_graph import NetworkGraph
from quantish.screen import ScreenSpec, screen_curves, stage_screens

__all__ = [
    'geometry', 'make_controls', 'make_screen_editor', 'make_slot',
    'notes_html', 'pretty', 'readout_text', 'refresh_panel',
    'screen_override', 'set_panel_curves', 'stages_html', 'strips_html',
    'update_slot',
]


def pretty(spec, var):
    # theta_pre_1 -> θ pre,1; theta_erase -> θ erase; a slider made
    # for a gate whose angle was a literal is named for the gate
    # (non-breaking spaces: the label sits beside its gate's checkbox
    # in a row and must not wrap)
    if var in spec.synthetic:
        what = spec.synthetic[var]
        return f'{what}\u00a0φ\u00a0(°)' if var.startswith('phi_') else f'{what}\u00a0(°)'
    v = var.replace('theta_', 'θ\u00a0').replace('_', ',')
    return f'{v}\u00a0(°)'


def notes_html(spec):
    # the notes are Markdown (paragraphs, lists, `code`, $LaTeX$),
    # rendered as prose so the stylesheet's black reading text applies
    cap = f'*{spec.caption}*\n\n' if spec.caption else ''
    return mo.md(cap + (spec.notes or '*no notes*'))


def geometry(spec, variables, labels, disabled=(), absent=()):
    overrides = {spec.plate: 'φ(x)'} if spec.has_screen else {}
    geom = diagram_geometry(spec.simulation(variables), has_run=False,
                            angle_overrides={**overrides, **labels},
                            disabled=tuple(disabled), absent=tuple(absent))
    # a full-width frame: the chain circuits are wide
    geom.update({'frame_w': 1250, 'frame_h': 420, 'fit': True})
    return geom


def make_screen_editor(model_id):
    """The slot's screen definition, editable: which phase plate to
    sweep across the pixels (or none), which particle arriving at
    which gate makes a hit, and the sort. Seeded from the model's
    own sweep section; built once per model choice."""
    if not model_id:
        return None
    spec = ScreenSpec.load(model_id)
    d = spec.screen_definition()
    particles = list(spec.config.get('particles') or {})
    gates = spec.gate_names
    grp = d['group_by'] or {}
    return mo.ui.dictionary({
        'plate': mo.ui.dropdown(options=['(no screen)', *spec.plates],
                                value=d['plate'] or '(no screen)', label='sweep the plate'),
        'particle': mo.ui.dropdown(options=particles,
                                   value=d['observe'].get('particle', particles[0]),
                                   label='hits: particle'),
        'at': mo.ui.dropdown(options=gates, value=d['observe'].get('at', gates[-1]),
                             label='arriving at'),
        'sort': mo.ui.dropdown(options=['(unsorted)', *particles],
                               value=grp.get('particle', '(unsorted)'), label='sort by'),
        'coordinate': mo.ui.dropdown(options=['sign', 'position', 'both'],
                                     value=grp.get('coordinate', 'sign'),
                                     label='coordinate'),
    })


def screen_override(editor):
    v = editor.value
    return {'plate': None if v['plate'] == '(no screen)' else v['plate'],
            'observe': {'particle': v['particle'], 'at': v['at']},
            'group_by': (None if v['sort'] == '(unsorted)'
                         else {'particle': v['sort'], 'coordinate': v['coordinate']})}


def make_slot(slot, model_id, editor, hit_store):
    """Everything a slot holds, built once per model choice: the spec,
    the gate and particle on/off boxes, the remembered angles, the
    widgets (built once, updated in place), and the slot's two views —
    the screen for the side-by-side row and, from make_controls, the
    details accordion. `hit_store` is the lab's, the slot's hits kept
    under its name. None for no model."""
    if not model_id:
        hit_store['hits'].pop(slot, None)
        return None
    spec = ScreenSpec.load(model_id, sweep=screen_override(editor) if editor else None)
    defaults = spec.default_degrees()
    ranges = spec.angle_ranges()
    # a checkbox per Fredkin gate, created once with the slot:
    # unchecked, the gate is switched off (inert) for every run of
    # the slot. The sliders are built by make_controls, per toggle
    # state, so a switched-off gate's slider can be disabled
    # the gates and the phase plates (a plate switched off applies no phase)
    _declared = set(spec.config.get('gates') or {}) | set(spec.config.get('phase_plates') or {})
    gate_names = [g for g in spec.simulation({}).run_order if g in _declared]   # circuit order
    toggles = mo.ui.dictionary({g: mo.ui.checkbox(value=True, label='on')
                                for g in gate_names})
    # and one per particle: unchecked, the particle is absent (a
    # null input) for every run of the slot
    particle_names = list(spec.config.get('particles') or {})
    ptoggles = mo.ui.dictionary({p: mo.ui.checkbox(value=True, label=p)
                                 for p in particle_names})
    angles = {var: min(max(round(defaults[var]), int(ranges[var][0])), int(ranges[var][1]))
              for var in spec.variables}
    readout = HtmlWidget(html='')
    panel = ScreenPanelWidget() if spec.has_screen else None
    diagram = DiagramWidget(geometry=geometry(spec, {}, {}))
    stages = HtmlWidget(html='') if spec.has_screen else None
    strips = HtmlWidget(html='') if spec.has_screen else None
    graph = NetworkGraphWidget(model={})
    hit_store['hits'][slot] = []
    # two views: the screen (readout above the panel) for the
    # side-by-side row, and the details (notes, angles, diagram)
    # for the slot's own accordion below
    _sim0 = spec.simulation({})
    screen = mo.vstack([
        mo.md(f'**Slot {slot}** — {spec.title}'
              + ('<br><span style="color: #b00020">⚠ no `run_stages` declared: the '
                 'gates run in wiring order</span>' if _sim0.run_stages_derived else '')),
        mo.ui.anywidget(readout),
        (mo.ui.anywidget(panel) if panel is not None
         else mo.md('_This model declares no screen (no `sweep` on a '
                    'phase plate); see its diagram below._')),
    ], gap=0.5)
    return {'slot': slot, 'spec': spec, 'toggles': toggles, 'angles': angles,
            'ptoggles': ptoggles, 'particle_names': particle_names, 'editor': editor,
            'ranges': ranges, 'gate_names': gate_names,
            'readout': readout, 'panel': panel, 'diagram': diagram,
            'stages': stages, 'strips': strips, 'graph': graph,
            'screen': screen, 'grain': None,
            'angle_gates': spec.angle_gates()}


def make_controls(state):
    """The slot's sliders — one per settable variable, at the slot's
    remembered angles, disabled when every gate the variable sets is
    switched off — laid out with each gate's on/off checkbox beside
    its slider, and the slot's details accordion around them. Rebuilt
    on every toggle (the checkboxes and the other widgets persist)."""
    spec, toggles = state['spec'], state['toggles']
    on = {g: toggles.elements[g].value for g in state['gate_names']}
    gates_of = {}
    for g, var in state['angle_gates'].items():
        gates_of.setdefault(var, []).append(g)
    ranges = state['ranges']
    sliders = mo.ui.dictionary({
        var: mo.ui.slider(int(ranges[var][0]), int(ranges[var][1]), step=1,
                          value=state['angles'][var], label=pretty(spec, var),
                          show_value=True,
                          disabled=bool(gates_of.get(var)) and not any(
                              on[g] for g in gates_of[var] if g in on))
        for var in spec.variables})

    def row(var):
        # the slider, its gates' on/off boxes, and any note line
        boxes = [toggles.elements[g] for g in gates_of.get(var, []) if g in on]
        note = spec.variable_notes.get(var)
        line = mo.hstack([sliders.elements[var], *boxes], justify='start',
                         align='center', gap=0.5)
        if not note:
            return line
        return mo.vstack([line, mo.md(f'<span style="font-size: 0.85em; '
                                      f'color: #000">{note}</span>')], gap=0)
    # gates with no slider of their own — the swept phase plate,
    # whose phase is the screen's — still get their on/off box
    loose_boxes = [g for g in state['gate_names']
                   if g in on and not any(g in gs for gs in gates_of.values())]
    others = (mo.hstack(
        [mo.md('<span style="color: #000">also:</span>')]
        + [mo.hstack([mo.md(f'<span style="color: #000">{g}</span>'), toggles.elements[g]],
                     justify='start', align='center', gap=0.4) for g in loose_boxes],
        justify='start', align='center', wrap=True, gap=1.5) if loose_boxes else None)
    particles = mo.hstack(
        [mo.md('<span style="color: #000">particles:</span>')]
        + [state['ptoggles'].elements[p] for p in state['particle_names']],
        justify='start', align='center', wrap=True, gap=1.5)
    screen_row = (mo.vstack([
        mo.hstack([mo.md('<span style="color: #000">screen:</span>'),
                   *state['editor'].elements.values()],
                  justify='start', align='center', wrap=True, gap=1),
        mo.md('<span style="font-size: 0.85em; color: #000">the screen is a sweep: '
              'the chosen plate\'s phase runs across the pixels, a hit is the chosen '
              'particle arriving at the chosen gate, and the hits can be sorted by '
              'another particle\'s final sign or position — changing it rebuilds '
              'the slot</span>'),
    ], gap=0.2) if state['editor'] is not None else None)
    controls = mo.vstack([
        *([screen_row] if screen_row is not None else []),
        (mo.hstack([row(v) for v in spec.variables], justify='start',
                   align='start', wrap=True, gap=2) if spec.variables
         else mo.md('_this model has no variables_')),
        *([others] if others is not None else []),
        particles,
        mo.md('<span style="font-size: 0.85em; color: #000">uncheck a gate to switch '
              'it off — a plain wire, every particle passes straight through — and '
              'a particle to leave it out, a null input; a switched-off slider grays '
              'out, and the diagram grays and crosses out whatever is off</span>'),
    ], gap=0.4)
    sections = {f'About: {spec.title}': notes_html(spec),
                'Controls': controls,
                'Circuit diagram': mo.ui.anywidget(state['diagram'])}
    if state['stages'] is not None:
        sections['Virtual screens by stage'] = mo.ui.anywidget(state['strips'])
        sections['Fringe visibility by stage'] = mo.ui.anywidget(state['stages'])
    sections['Weight evolution (gate output ports × stages)'] = mo.ui.anywidget(state['graph'])
    details = mo.accordion({
        f'## Slot {state["slot"]}\n\n<span style="font-size:0.85em">{spec.title}</span>':
        mo.accordion(sections, multiple=True)})
    return sliders, details


def refresh_panel(state, hit_store):
    """Rebuild a slot's screen from its stored hits: the side-by-side
    row re-renders when either slot's model changes, which remounts
    both panels, and a remounted panel only knows the hits in its
    `data` (later volleys arrived as chunks)."""
    panel = state['panel']
    if panel is None or not panel.data:
        return
    panel.data = {**panel.data,
                  'hits': [list(p) for p in hit_store['hits'].get(state['slot'], [])]}


def set_panel_curves(state, xs, curves, hit_store):
    """Push the curves to the slot's screen: the total plus, when
    the model sorts its hits, one part per group; at a new grain the
    panel rebuilds from its baseline. The screen sits under a
    full-width diagram, so it can be wider than the double-slit
    app's; the title drops the family prefix."""
    spec = state['spec']
    total, parts = grouped_curves(curves, spec.group_by[0] if spec.group_by else '')
    state['grain'] = push_curves(
        state['panel'], xs, total, parts, grain=state['grain'],
        title=spec.title.removeprefix('Double slit, '), width=560,
        hits=hit_store['hits'].get(state['slot'], []))


def update_slot(state, sliders, n, fringes, via, hit_store):
    """A slot's engine step: sliders -> the diagram's angle labels,
    and for a screened model the curves and the visibility readout.
    Returns the variables (radians) for `current`."""
    spec = state['spec']
    state['angles'] = {var: sl.value for var, sl in sliders.elements.items()}
    variables = {var: math.radians(v) for var, v in state['angles'].items()}
    # the unchecked gates are switched off, the unchecked particles
    # left out, for every run of the slot
    inert = tuple(g for g in state['gate_names'] if not state['toggles'].elements[g].value)
    absent = tuple(p for p in state['particle_names']
                   if not state['ptoggles'].elements[p].value)
    state['inert'], state['absent'] = inert, absent
    labels = {g: f'{sliders.elements[v].value:.0f}°'
              for g, v in state['angle_gates'].items()}
    state['diagram'].geometry = geometry(spec, variables, labels, inert, absent)
    if set(absent) >= set(state['particle_names']):
        # nothing enters: say so and leave every view empty
        gone = '<span style="color: #000"><b>every particle is off</b>: nothing enters</span>'
        state['readout'].html = gone
        for key in ('stages', 'strips'):
            if state[key] is not None:
                state[key].html = gone
        state['graph'].model = {}
        if state['panel'] is not None:
            xs = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
            set_panel_curves(state, xs, {'all': [0.0] * n}, hit_store)
        return variables
    # one run at the model's own phase for the stage views (the
    # screen's cached runs hold whatever phase ran last)
    sim = spec.simulation(variables, inert, absent)
    sim.run()
    no_screen = spec.has_screen and spec.observe[0] in absent
    if state['panel'] is not None:
        xs, curves = screen_curves(spec, variables, n, fringes, via,
                                   inert=inert, absent=absent)
        set_panel_curves(state, xs, curves, hit_store)
        state['readout'].html = readout_text(spec, curves, inert, absent)
    if state['stages'] is not None:
        if no_screen:
            gone = (f'<span style="color: #000"><b>{spec.observe[0]} is off</b>: nothing '
                    f'reaches the screen</span>')
            state['stages'].html = gone
            state['strips'].html = gone
        else:
            state['stages'].html = stages_html(spec, sim)
            xs, screens = stage_screens(spec, variables, n, fringes, via, sim=sim,
                                        inert=inert, absent=absent)
            state['strips'].html = strips_html(spec, xs, screens)
    state['graph'].model = NetworkGraph(sim.all_points, sim).build_model()
    return variables


STRIP_RGB = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]   # the film's group colors
STRIP_W, STRIP_H, LABEL_W = 560, 26, 120


def strips_html(spec, xs, screens):
    """The virtual screens as film strips, one per stage: the exact
    intensity as brightness (the sorted subsets in the film's
    additive colors), so the fringes are seen dying as a record is
    written and returning, per subset, as it is erased."""
    groups = list(screens[0]['curves']) if screens else []
    particle = spec.group_by[0] if spec.group_by else ''
    peak = max((sum(s['curves'][g][i] for g in groups)
                for s in screens for i in range(len(xs))), default=1.0) or 1.0
    n, px = len(xs), STRIP_W / max(1, len(xs))
    rows = []
    for k, s in enumerate(screens):
        y = k * (STRIP_H + 4)
        cells = []
        for i in range(n):
            r = g = b = 0.0
            for gi, grp in enumerate(groups):
                level = min(1.0, s['curves'][grp][i] / peak)
                cr, cg, cb = (255, 255, 255) if grp == 'all' else STRIP_RGB[gi % 3]
                r, g, b = r + cr * level, g + cg * level, b + cb * level
            fill = f'rgb({min(255, round(r))},{min(255, round(g))},{min(255, round(b))})'
            cells.append(f'<rect x="{LABEL_W + i * px:.2f}" y="{y}" '
                         f'width="{px + 0.3:.2f}" height="{STRIP_H}" fill="{fill}"/>')
        what = ', '.join(s['gates'])
        acts = f' — {", ".join(s["switched"])} split' if s['switched'] else ''
        rows.append(f'<g><title>{s["name"]}: {what}{acts}</title>'
                    f'<text x="{LABEL_W - 8}" y="{y + STRIP_H / 2 + 4}" text-anchor="end" '
                    f'font-size="12" fill="#000">{s["name"]}</text>'
                    f'<rect x="{LABEL_W}" y="{y}" width="{STRIP_W}" height="{STRIP_H}" '
                    f'fill="#000"/>{"".join(cells)}</g>')
    height = len(screens) * (STRIP_H + 4)
    legend = ('brightness is the exact intensity'
              + (''.join(f', <span style="color: rgb{STRIP_RGB[gi % 3]}">■</span> {grp}{particle}'
                         for gi, grp in enumerate(groups)) if particle else '')
              + '; each strip is the screen as it would be if the two paths were '
                'merged right after that stage, the environment frozen there — '
                'stages where nothing acts are left out — and the last strip is '
                'the actual screen, the model as declared.')
    return (f'<div style="color: #000"><svg width="{LABEL_W + STRIP_W}" height="{height}" '
            f'viewBox="0 0 {LABEL_W + STRIP_W} {height}" style="max-width: 100%" '
            f'shape-rendering="crispEdges">'
            + ''.join(rows) + f'</svg><p style="font-size: 0.9em">{legend}</p></div>')


def stages_html(spec, sim):
    """The fringe visibility the screen would show if the paths were
    merged right after each stage — whole screen and per sort
    subset — with the cells that change from the row above in bold:
    that is where a record is written, or erased."""
    rows = path_coherence(sim, spec.observe[0], spec.group_by, upto_gate=spec.plate)
    particle = spec.group_by[0] if spec.group_by else ''
    groups = list(rows[-1].groups) if rows else []
    head = [('stage', None), ('acts on', None), ('whole screen', None)]
    head += [(f'{g}{particle}' if len(g) == 1 else g, None) for g in groups]

    def cell(z):
        v = signed_visibility(z)
        if v is not None:
            return f'{0.0 if abs(v) < 5e-5 else v:.4f}'     # no '-0.0000'
        if z is None:
            return '—'
        return f'{abs(z):.4f} ∠{math.degrees(math.atan2(z.imag, z.real)):+.0f}°'

    body, previous = [], None
    for r in rows:
        values = [cell(r.whole)] + [cell(r.groups.get(g)) for g in groups]
        if previous is not None:
            values = [f'<b>{v}</b>' if v != p and '—' not in (v, p) else v
                      for v, p in zip(values, previous)]
        stage = (f'{r.name}<br><span style="font-size: 0.8em">'
                 f'{", ".join(r.gates)}</span>' if r.gates else r.name)
        body.append([stage, ', '.join(r.switched) or '—'] + values)
        previous = [cell(r.whole)] + [cell(r.groups.get(g)) for g in groups]
    note = ('the fringe visibility the screen would show if the two paths were '
            'merged right after this stage, whole and per sorted subset; '
            'negative: fringes shifted by half a period; bold: changed from '
            'the row above, where a record is written or erased. The last row '
            'is the readout’s visibility.')
    return ('<style>.stage-table td, .stage-table th {padding: 0.15em 0.8em}</style>'
            '<div class="stage-table" style="color: #000">' + html_table(head, body)
            + f'<p style="font-size: 0.9em">{note}</p></div>')


def readout_text(spec, curves, inert=(), absent=()):
    def vis(ys):
        lo, hi = min(ys), max(ys)
        return '—' if hi + lo < 1e-12 else f'{(hi - lo) / (hi + lo):.4f}'
    parts = []
    for g, ys in curves.items():
        label = 'visibility' if g == 'all' else f'visibility, {g}{spec.group_by[0]}'
        parts.append(f'{label}: <b>{vis(ys)}</b>')
    if list(curves) != ['all']:
        n = len(next(iter(curves.values())))
        parts.append('whole screen: <b>'
                     + vis([sum(curves[g][i] for g in curves) for i in range(n)]) + '</b>')
    text = ' · '.join(parts) + ' — of the drawn curve, (max − min)/(max + min)'
    off = ([f'gates off: {", ".join(inert)}'] if inert else []) \
        + ([f'particles off: {", ".join(absent)}'] if absent else [])
    if off:
        text = f'<b>{" · ".join(off)}</b> · ' + text
    return f'<span style="color: #000">{text}</span>'
