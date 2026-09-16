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

    import yaml

    from quantish.apps.common import (
        WASM_MODE,
        build_stamp,
        editor_ui,
        init_engine,
        remember_in,
        stamp_html,
    )
    from quantish.apps.curves import grouped_curves
    from quantish.apps.lab import (
        make_controls,
        make_screen_editor,
        make_slot,
        refresh_panel,
        set_panel_curves,
        update_slot,
    )
    from quantish.double_slit import sample_hits
    from quantish.screen import (
        ScreenSpec,
        library,
        model_label,
        register,
        reload,
        screen_curves,
    )

    init_engine()
    EDITOR_UI = editor_ui(_wasm_editor) if WASM_MODE else editor_ui()
    return (
        EDITOR_UI,
        build_stamp,
        ScreenSpec,
        grouped_curves,
        library,
        make_controls,
        make_screen_editor,
        make_slot,
        mo,
        model_label,
        refresh_panel,
        set_panel_curves,
        update_slot,
        random,
        register,
        reload,
        remember_in,
        sample_hits,
        screen_curves,
        stamp_html,
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
async def _(build_stamp, stamp_html):
    # which build is this? (the site build writes public/version.json
    # beside the page; a development copy says so instead)
    stamp_html(await build_stamp())


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
    chosen,
    library,
    mo,
    model_label,
    register,
    reload,
    remember_in,
    rescan,
    ScreenSpec,
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
        return remember_in(chosen, slot, lambda model_id: model_id or '')

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
def _():
    # what every slot shares (the slots themselves are quantish.apps.lab):
    # the sampled hits, the rebuild baseline — each volley streams only
    # its new hits to the client — and the settings the curves were
    # last computed for, which fire and reset read instead of the
    # sliders, so a slider move never runs them
    hit_store = {'seq': 0, 'hits': {}}
    current = {}     # slot -> settings for fire/reset (never from sliders)
    return current, hit_store


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
def _(hit_store, make_slot, pick_a, screen_a):
    slot_a = make_slot('A', pick_a.value, screen_a, hit_store)
    toggles_a = slot_a['toggles'] if slot_a else None
    ptoggles_a = slot_a['ptoggles'] if slot_a else None
    return ptoggles_a, slot_a, toggles_a


@app.cell(hide_code=True)
def _(hit_store, make_slot, pick_b, screen_b):
    slot_b = make_slot('B', pick_b.value, screen_b, hit_store)
    toggles_b = slot_b['toggles'] if slot_b else None
    ptoggles_b = slot_b['ptoggles'] if slot_b else None
    return ptoggles_b, slot_b, toggles_b


@app.cell(hide_code=True)
def _(hit_store, mo, refresh_panel, slot_a, slot_b):
    # the screens, side by side
    for _state in (slot_a, slot_b):
        if _state:
            refresh_panel(_state, hit_store)
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
def _(current, fringes, hit_store, n_points, sliders_a, slot_a, update_slot, via):
    # slot A's engine cell: it names sliders_a, so it reruns on A's
    # slider moves and on nothing else of B's
    current['n'], current['fringes'] = n_points.value, fringes.value
    if slot_a:
        current['A'] = update_slot(slot_a, sliders_a, n_points.value,
                                   fringes.value, via, hit_store)


@app.cell(hide_code=True)
def _(current, fringes, hit_store, n_points, sliders_b, slot_b, update_slot, via):
    if slot_b:
        current['B'] = update_slot(slot_b, sliders_b, n_points.value,
                                   fringes.value, via, hit_store)


@app.cell(hide_code=True)
def _(
    current,
    fire_btn,
    grouped_curves,
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
            set_panel_curves(state, xs, curves, hit_store)
            out[slot] = (state, xs, curves)
        return out

    mo.stop(not fire_btn.value)
    with mo.status.spinner(title='running the exact simulations…'):
        _runs = engine_curves()
    _rng = random.Random()
    hit_store['seq'] += 1
    for _slot, (_state, _xs, _curves) in _runs.items():
        _total, _parts = grouped_curves(_curves)
        _parts = tuple(ys for _, ys in _parts) if _parts else None
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
