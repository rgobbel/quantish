"""The decoherence lab: any quantish model, on a screen when it has one.

A model with a `sweep` section declares its own screen — the phase
plate whose phase sweeps across the pixels, the particle and detector
to observe, and (optionally) a particle whose final sign sorts the hits.
This app reads that: load a model into a slot, and its variables become
sliders (ranged by the gates' `angle_range` hints), its caption and
notes are the explanation, and the circuit diagram, the exact intensity
curve and the fired-particle screen follow from the engine. Two slots,
A and B, put any two models side by side; any library model or an
uploaded model file can go in either, screened or not.

Engine side: quantish/screen.py.
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full", css_file="css/double_slit_app.css")


@app.cell(hide_code=True)
async def initialization():
    import math
    import random
    import sys
    from pathlib import Path

    import marimo as mo

    if sys.platform == 'emscripten':
        # dynamic import: a literal `import micropip` makes server-side
        # marimo install a mock micropip meta-path finder whose globals
        # die with the notebook session, breaking all later imports
        import importlib
        micropip = importlib.import_module('micropip')
        _base = str(mo.notebook_location())
        await micropip.install([
            f'{_base}/public/wheels/addict-2.4.0-py3-none-any.whl',
            f'{_base}/public/wheels/quantish-0.1.0-py3-none-any.whl',
        ], deps=False)
        await micropip.install(['sympy', 'scipy', 'networkx',
                                'pyyaml', 'anywidget'])
        import json as _json

        from pyodide.http import pyfetch
        _base = str(mo.notebook_location())
        _resp = await pyfetch(f'{_base}/public/models.json')
        for _rel, _text in _json.loads(await _resp.string()).items():
            _p = Path('/wasm-data/models') / _rel
            _p.parent.mkdir(parents=True, exist_ok=True)
            _p.write_text(_text)
        # Under WASM, mo.app_meta().mode reports 'edit' for BOTH export
        # modes; the page's own mount config records which one this is.
        _page = await (await pyfetch(f'{_base}/index.html')).string()
        _wasm_editor = '"mode": "edit"' in _page

    _repo = Path(__file__).resolve().parent.parent
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    import logging

    import yaml

    from quantish.qnumber import CalcMode

    CalcMode.default('Float')
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('quantish').setLevel(logging.WARNING)

    from quantish.builder_widget import (
        DiagramWidget,
        HtmlWidget,
        NetworkGraphWidget,
        ScreenPanelWidget,
    )
    from quantish.coherence import path_coherence, signed_visibility
    from quantish.diagram_layout import diagram_geometry
    from quantish.display import html_table
    from quantish.double_slit import sample_hits
    from quantish.network_graph import NetworkGraph
    from quantish.screen import (
        ScreenSpec,
        library,
        model_label,
        register,
        reload,
        screen_curves,
        stage_screens,
    )

    WASM_MODE = sys.platform == 'emscripten'
    EDITOR_UI = (_wasm_editor if WASM_MODE
                 else mo.app_meta().mode == 'edit')
    return (
        DiagramWidget,
        EDITOR_UI,
        HtmlWidget,
        NetworkGraph,
        NetworkGraphWidget,
        ScreenPanelWidget,
        ScreenSpec,
        diagram_geometry,
        html_table,
        library,
        math,
        mo,
        model_label,
        path_coherence,
        random,
        register,
        reload,
        sample_hits,
        screen_curves,
        signed_visibility,
        stage_screens,
        sys,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Decoherence lab

    A workbench for putting two quantish circuits side by side. Load a
    model into each slot — any model in the library, or a model file of
    your own — and its angles become sliders, its own notes explain it,
    and its circuit diagram follows the sliders. A model that declares a
    screen (a `sweep` on a phase plate: which phase sweeps across the
    pixels, which particle at which detector makes a hit, and, where a
    recorder is read out, which particle's sign sorts the hits) also
    gets a fired-particle screen with its exact intensity curve — and any model can be given one, or a different one, from the slot's controls: choose the phase plate to sweep, the particle and gate that make a hit, and the sort — and the *virtual screens*: one film strip per stage showing what the screen would be if the two paths were merged right there — whole and per sorted subset — so a which-way record is seen being written, and erased, as the fringes die and return. A table gives the same progression as fringe visibilities, and every slot carries the weight-evolution graphic of its particles across the stages.

    The library holds, by collection:

    - the **decoherence** collection: the double-slit family with a
      screen — which-way recorders complete and partial, the quantum
      eraser, and chains of recorders with and without an eraser;
    - the book's figures (**gr2026**, **gr2006**) and the **extras**,
      most of which have no screen but load all the same, with their
      diagrams and angle sliders;
    - any model file of your own, added with the button below.

    Every gate has a slider, and beside each slider a checkbox: uncheck it and the gate is switched off — a plain wire that every particle passes straight through. Every particle has a checkbox too: unchecked, it never enters — a null input, its wires empty — so a circuit can be taken apart piece by piece without rewiring it. A switched-off slider grays out, and the diagram grays and crosses out whatever is off.

    Every landing point on a screen is drawn from exact weights computed
    by the quantish engine.
    """)


@app.cell(hide_code=True)
async def build_stamp(mo, sys):
    # the build stamp of a deployed site: tools/build_wasm_app.sh
    # writes public/version.json beside the page; a development copy
    # says so instead.
    _stamp = 'development copy'
    if sys.platform == 'emscripten':
        try:
            import json as _json

            from pyodide.http import pyfetch as _pyfetch
            _v = _json.loads(await (await _pyfetch(
                f'{mo.notebook_location()}/public/version.json')).string())
            _stamp = f"build {_v['build']} · {_v['built_at']}"
        except Exception:  # noqa: BLE001 — an unstamped site shows nothing
            _stamp = ''
    mo.md(f'<span style="font-size: 0.8em; color: #444">{_stamp}</span>') \
        if _stamp else None


@app.cell(hide_code=True)
def _(mo):
    # model files added at runtime join the catalog under 'upload:<name>'
    uploads = mo.ui.file(filetypes=['.yaml', '.yml'], multiple=True, kind='button',
                         label='⬆ add model files')
    # re-read the library's files (after editing a model on disk)
    rescan = mo.ui.run_button(label='↻ reload models')
    # what each slot holds, remembered across catalog rebuilds (a reload
    # or an upload) so neither resets the selections: {slot: model id}.
    # A plain dict, not mo.state: the pickers themselves carry the live
    # value, so nothing needs to rerun when it changes
    chosen = {'A': 'decoherence/double_slit_decoherence_chain',
              'B': 'decoherence/double_slit_eraser_chain'}
    return chosen, rescan, uploads


@app.cell(hide_code=True)
def _(
    ScreenSpec,
    chosen,
    library,
    mo,
    model_label,
    register,
    reload,
    rescan,
    uploads,
    yaml,
):
    # The catalog, one collection at a time as everywhere else: the
    # library's collections plus 'uploads' for files added here; each
    # collection maps a model's picker label (file name — title) to its
    # id. The collection pickers open on the remembered models' collections.
    if rescan.value:
        reload()
    _bad = []
    for _f in uploads.value or []:
        try:
            register(f'upload:{_f.name.rsplit(".", 1)[0]}', yaml.safe_load(_f.contents))
        except Exception as exc:  # noqa: BLE001 — a bad file is reported, not fatal
            _bad.append(f'{_f.name}: {exc}')
    CATALOG = {}
    for _mid in library():
        try:
            _spec = ScreenSpec.load(_mid)
        except Exception:  # noqa: BLE001, S112 — an unloadable file stays out of the catalog
            continue
        _coll, _stem = (('uploads', _mid[len('upload:'):]) if _mid.startswith('upload:')
                        else tuple(_mid.split('/', 1)))
        CATALOG.setdefault(_coll, {})[model_label(_stem, _spec.title)] = _mid
    _colls = list(CATALOG)
    _home = 'decoherence' if 'decoherence' in CATALOG else _colls[0]

    def _collection_of(model_id):
        if not model_id:
            return _home
        coll = 'uploads' if model_id.startswith('upload:') else model_id.split('/', 1)[0]
        return coll if coll in CATALOG else _home

    def remember(slot):
        # a picker's on_change: keep the slot's choice ('' = '(none)')
        def _(model_id):
            chosen[slot] = model_id or ''
        return _

    coll_a = mo.ui.dropdown(options=_colls, value=_collection_of(chosen['A']),
                            label='slot A: collection')
    coll_b = mo.ui.dropdown(options=_colls, value=_collection_of(chosen['B']),
                            label='slot B: collection')
    upload_note = mo.md('  \n'.join(f'⚠ {b}' for b in _bad)) if _bad else mo.md('')
    return CATALOG, coll_a, coll_b, remember, upload_note


@app.cell(hide_code=True)
def _(CATALOG, chosen, coll_a, mo, remember):
    # slot A's model picker, rebuilt when its collection changes; it
    # opens on the remembered model when that is in the collection
    _models = CATALOG.get(coll_a.value) or {}
    _by_id = {mid: title for title, mid in _models.items()}
    _opens_on = _by_id.get(chosen['A'], next(iter(_models), None))
    pick_a = mo.ui.dropdown(options=_models, value=_opens_on,
                            label='model', on_change=remember('A'))
    # what the picker opens on is the slot's model too (a collection
    # change opens on that collection's first model without a change event)
    remember('A')(_models.get(_opens_on))
    return (pick_a,)


@app.cell(hide_code=True)
def _(CATALOG, chosen, coll_b, mo, remember):
    # slot B's model picker, with '(none)' to leave the slot empty
    _models = CATALOG.get(coll_b.value) or {}
    _by_id = {mid: title for title, mid in _models.items()}
    _opens_on = ('(none)' if chosen['B'] == ''
                 else _by_id.get(chosen['B'], next(iter(_models), '(none)')))
    pick_b = mo.ui.dropdown(options={**_models, '(none)': ''}, value=_opens_on,
                            label='model', on_change=remember('B'))
    remember('B')(_models.get(_opens_on))
    return (pick_b,)


@app.cell(hide_code=True)
def _(mo):
    # the shared controls, created here so that no model change resets them
    fringes = mo.ui.slider(steps=[1, 3, 5, 7, 9], value=3, label='fringes',
                           show_value=True)
    n_points = mo.ui.slider(41, 161, step=20, value=81,
                            label='screen resolution', show_value=True)
    shots = mo.ui.slider(steps=[100, 200, 500, 1000, 2000, 5000, 10000],
                         value=1000, label='particles per volley',
                         show_value=True)
    fire_btn = mo.ui.run_button(label='🔫 fire particles')
    reset_btn = mo.ui.run_button(label='reset screens')
    exact_sw = mo.ui.switch(value=False,
                            label='one engine run per pixel on every change')
    return exact_sw, fire_btn, fringes, n_points, reset_btn, shots


@app.cell(hide_code=True)
def _(
    coll_a,
    coll_b,
    exact_sw,
    fire_btn,
    fringes,
    mo,
    n_points,
    pick_a,
    pick_b,
    rescan,
    reset_btn,
    shots,
    upload_note,
    uploads,
):
    mo.vstack([
        mo.md('## Simulation controls'),
        mo.md('Load a model into each slot — a collection, then a model — and '
              'set its angles inside the slot. Slider moves redraw the exact '
              'curves; firing reruns the engine at every pixel and draws the '
              'particles that reach the screen. The screen resolution slider '
              'sets how many points the curve is computed at and how fine the '
              'film\'s pixels are: moving it repaints the film, but nothing is '
              'simulated or redrawn at random — every hit keeps the landing '
              'point it got when it was fired, and the same hits are simply '
              're-binned into the new pixels (coarser pixels collect more hits '
              'each and glow brighter). The hit counts in the titles do not '
              'change.'),
        mo.hstack([mo.hstack([coll_a, pick_a], justify='start', gap=1),
                   mo.hstack([coll_b, pick_b], justify='start', gap=1),
                   uploads], justify='start', wrap=True, gap=3),
        upload_note,
        mo.hstack([fringes, n_points, shots, fire_btn, reset_btn, rescan, exact_sw],
                  wrap=True, justify='start'),
    ])


@app.cell(hide_code=True)
def _(
    DiagramWidget,
    HtmlWidget,
    NetworkGraph,
    NetworkGraphWidget,
    ScreenPanelWidget,
    ScreenSpec,
    diagram_geometry,
    html_table,
    math,
    mo,
    path_coherence,
    signed_visibility,
    stage_screens,
):
    # Everything a slot holds, built once per model choice: the spec, a
    # slider per settable angle (in degrees, ranged by the gates'
    # angle_range hints), the widgets, and the hit store. Slider moves
    # reach only the engine cells (through the dictionary of sliders);
    # the slot's display is a static container that re-renders only when
    # the model changes. The sliders, the diagram, the visibility-by-
    # stage table, and the weight-evolution graphic sit in closed
    # accordions so two screens fit on one page; the widgets inside are
    # built once and updated in place.
    hit_store = {'seq': 0, 'hits': {}}
    current = {}     # slot -> settings for fire/reset (never from sliders)

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

    def make_slot(slot, model_id, editor=None):
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

    def refresh_panel(state):
        """Rebuild a slot's screen from its stored hits: the side-by-side
        row re-renders when either slot's model changes, which remounts
        both panels, and a remounted panel only knows the hits in its
        `data` (later volleys arrived as chunks)."""
        panel = state['panel']
        if panel is None or not panel.data:
            return
        panel.data = {**panel.data,
                      'hits': [list(p) for p in hit_store['hits'].get(state['slot'], [])]}

    def set_panel_curves(state, xs, curves):
        """Push the curves to the slot's screen: the total plus, when
        the model sorts its hits, one part per group."""
        panel, spec = state['panel'], state['spec']
        total = [sum(curves[g][i] for g in curves) for i in range(len(xs))]
        data = {'x': list(xs), 'y': total}
        if list(curves) != ['all']:
            particle = spec.group_by[0]
            data['parts'] = [{'name': f'{g}{particle}' if len(g) == 1 else g,
                              'y': list(ys)} for g, ys in curves.items()]
        if state['grain'] == len(xs):
            panel.curves = data
            return
        state['grain'] = len(xs)
        panel.curves = data
        # the screen sits under a full-width diagram, so it can be wider
        # than the double-slit app's; the title drops the family prefix
        title = spec.title.removeprefix('Double slit, ')
        panel.data = {'title': title, 'curve': data, 'width': 560,
                      'hits': [list(p) for p in hit_store['hits'].get(state['slot'], [])]}

    def update_slot(state, sliders, n, fringes, via, screen_curves):
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
                set_panel_curves(state, xs, {'all': [0.0] * n})
            return variables
        # one run at the model's own phase for the stage views (the
        # screen's cached runs hold whatever phase ran last)
        sim = spec.simulation(variables, inert, absent)
        sim.run()
        no_screen = spec.has_screen and spec.observe[0] in absent
        if state['panel'] is not None:
            xs, curves = screen_curves(spec, variables, n, fringes, via,
                                       inert=inert, absent=absent)
            set_panel_curves(state, xs, curves)
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
    return (current, hit_store, make_controls, make_screen_editor, make_slot, refresh_panel,
            set_panel_curves, update_slot)


@app.cell(hide_code=True)
def _(make_screen_editor, pick_a):
    # slot A's screen definition, rebuilt with the model choice
    screen_a = make_screen_editor(pick_a.value)
    return (screen_a,)


@app.cell(hide_code=True)
def _(make_screen_editor, pick_b):
    screen_b = make_screen_editor(pick_b.value)
    return (screen_b,)


@app.cell(hide_code=True)
def _(make_slot, pick_a, screen_a):
    slot_a = make_slot('A', pick_a.value, screen_a)
    toggles_a = slot_a['toggles'] if slot_a else None
    ptoggles_a = slot_a['ptoggles'] if slot_a else None
    return ptoggles_a, slot_a, toggles_a


@app.cell(hide_code=True)
def _(make_slot, pick_b, screen_b):
    slot_b = make_slot('B', pick_b.value, screen_b)
    toggles_b = slot_b['toggles'] if slot_b else None
    ptoggles_b = slot_b['ptoggles'] if slot_b else None
    return ptoggles_b, slot_b, toggles_b


@app.cell(hide_code=True)
def _(mo, refresh_panel, slot_a, slot_b):
    # the screens, side by side
    for _state in (slot_a, slot_b):
        if _state:
            refresh_panel(_state)
    mo.hstack([_state['screen'] for _state in (slot_a, slot_b) if _state],
              justify='start', align='start', gap=3, wrap=True)


@app.cell(hide_code=True)
def _(make_controls, mo, ptoggles_a, slot_a, toggles_a):
    # slot A's sliders and details: rebuilt when a gate or particle is
    # toggled (the toggles' values), so a switched-off gate's slider is
    # disabled
    sliders_a, _details_a = (make_controls(slot_a)
                             if slot_a and toggles_a is not None and ptoggles_a is not None
                             else (None, mo.md('')))
    _details_a  # noqa: B018 — the cell's output
    return (sliders_a,)


@app.cell(hide_code=True)
def _(make_controls, mo, ptoggles_b, slot_b, toggles_b):
    sliders_b, _details_b = (make_controls(slot_b)
                             if slot_b and toggles_b is not None and ptoggles_b is not None
                             else (None, mo.md('')))
    _details_b  # noqa: B018 — the cell's output
    return (sliders_b,)


@app.cell(hide_code=True)
def _(exact_sw):
    via = 'pixels' if exact_sw.value else 'fit'
    return (via,)


@app.cell(hide_code=True)
def _(current, fringes, n_points, screen_curves, sliders_a, slot_a, update_slot, via):
    # slot A's engine cell: it names sliders_a, so it reruns on A's
    # slider moves and on nothing else of B's
    current['n'], current['fringes'] = n_points.value, fringes.value
    if slot_a:
        current['A'] = update_slot(slot_a, sliders_a, n_points.value,
                                   fringes.value, via, screen_curves)


@app.cell(hide_code=True)
def _(current, fringes, n_points, screen_curves, sliders_b, slot_b, update_slot, via):
    if slot_b:
        current['B'] = update_slot(slot_b, sliders_b, n_points.value,
                                   fringes.value, via, screen_curves)


@app.cell(hide_code=True)
def _(
    current,
    fire_btn,
    hit_store,
    mo,
    random,
    sample_hits,
    screen_curves,
    set_panel_curves,
    shots,
    slot_a,
    slot_b,
):
    # Fire and reset read the settings from `current`, so slider moves
    # do not run them; both recompute the curves with one engine run per
    # pixel, the sampled hits' source of truth. Slots without a screen
    # take no part.
    def engine_curves():
        out = {}
        for slot, state in (('A', slot_a), ('B', slot_b)):
            if not state or state['panel'] is None or slot not in current:
                continue
            xs, curves = screen_curves(state['spec'], current[slot], current['n'],
                                       current['fringes'], 'pixels',
                                       inert=state.get('inert', ()),
                                       absent=state.get('absent', ()))
            set_panel_curves(state, xs, curves)
            out[slot] = (state, xs, curves)
        return out

    mo.stop(not fire_btn.value)
    with mo.status.spinner(title='running the exact simulations…'):
        _runs = engine_curves()
    _rng = random.Random()
    hit_store['seq'] += 1
    for _slot, (_state, _xs, _curves) in _runs.items():
        _total = [sum(_curves[g][i] for g in _curves) for i in range(len(_xs))]
        _parts = None if list(_curves) == ['all'] else tuple(_curves.values())
        _new = sample_hits(_xs, _total, shots.value, _rng, parts=_parts)
        hit_store['hits'].setdefault(_slot, []).extend(_new)
        _state['panel'].hits_chunk = {
            'seq': hit_store['seq'],
            'pts': [list(_p) for _p in _new],
            'total': len(hit_store['hits'][_slot])}
    return (engine_curves,)


@app.cell(hide_code=True)
def _(engine_curves, hit_store, mo, reset_btn):
    mo.stop(not reset_btn.value)
    with mo.status.spinner(title='running the exact simulations…'):
        _runs = engine_curves()
    hit_store['seq'] += 1
    for _slot, (_state, _, _) in _runs.items():
        hit_store['hits'][_slot] = []
        _state['panel'].hits_chunk = {'seq': hit_store['seq'], 'reset': True}


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    mo.Html('<div style="text-align: center; font-size: 1.6em; '
            'margin: 2em 0 1em">&#8258;</div>') if not EDITOR_UI else None


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    mo.md(r"""## Support code""") if EDITOR_UI else None


if __name__ == "__main__":
    app.run()
