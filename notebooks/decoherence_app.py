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
    DL_EDITOR_UI = editor_ui(_wasm_editor) if WASM_MODE else editor_ui()
    return (
        DL_EDITOR_UI,
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
    dl_uploads = mo.ui.file(filetypes=['.yaml', '.yml'], multiple=True, kind='button',
                         label='⬆ add model files')
    # re-read the library's files (after editing a model on disk)
    dl_rescan = mo.ui.run_button(label='↻ reload models')
    # what each slot holds, remembered across catalog rebuilds (a reload
    # or an upload) so neither resets the selections: {slot: model id}.
    # A plain dict, not mo.state: the pickers themselves carry the live
    # value, so nothing needs to rerun when it changes
    dl_chosen = {'A': 'decoherence/double_slit_decoherence_chain',
              'B': 'decoherence/double_slit_eraser_chain'}
    return dl_chosen, dl_rescan, dl_uploads


@app.cell(hide_code=True)
def _():
    # a model sent from the network builder — None on its own; the
    # suite passes the builder's slot in (a cell of its own: the suite
    # overrides this one definition)
    dl_model_in = None
    return (dl_model_in,)


@app.cell(hide_code=True)
def _(
    dl_model_in,
    dl_chosen,
    library,
    mo,
    model_label,
    register,
    reload,
    remember_in,
    dl_rescan,
    ScreenSpec,
    dl_uploads,
    yaml,
):
    # The catalog, one collection at a time as everywhere else: the
    # library's collections plus 'uploads' for files added here; each
    # collection maps a model's picker label (file name — title) to its
    # id. The collection pickers open on the remembered models' collections.
    if dl_rescan.value:
        reload()
    # a model sent from the network builder (the suite passes it in) is
    # already in the `uploads` collection: slot A opens on it
    if dl_model_in is not None:
        dl_chosen['A'] = dl_model_in.model_id
    _bad = []
    for _f in dl_uploads.value or []:
        try:
            register(f'upload:{_f.name.rsplit(".", 1)[0]}', yaml.safe_load(_f.contents))
        except Exception as exc:  # noqa: BLE001 — a bad file is reported, not fatal
            _bad.append(f'{_f.name}: {exc}')
    DL_CATALOG = {}
    for _mid in library():
        try:
            _spec = ScreenSpec.load(_mid)
        except Exception:  # noqa: BLE001, S112 — an unloadable file stays out of the catalog
            continue
        _coll, _stem = (('uploads', _mid[len('upload:'):]) if _mid.startswith('upload:')
                        else tuple(_mid.split('/', 1)))
        DL_CATALOG.setdefault(_coll, {})[model_label(_stem, _spec.title)] = _mid
    _colls = list(DL_CATALOG)
    _home = 'decoherence' if 'decoherence' in DL_CATALOG else _colls[0]

    def _collection_of(model_id):
        if not model_id:
            return _home
        coll = 'uploads' if model_id.startswith('upload:') else model_id.split('/', 1)[0]
        return coll if coll in DL_CATALOG else _home

    def dl_remember(slot):
        # a picker's on_change: keep the slot's choice ('' = '(none)')
        return remember_in(dl_chosen, slot, lambda model_id: model_id or '')

    dl_coll_a = mo.ui.dropdown(options=_colls, value=_collection_of(dl_chosen['A']),
                            label='slot A: collection')
    dl_coll_b = mo.ui.dropdown(options=_colls, value=_collection_of(dl_chosen['B']),
                            label='slot B: collection')
    dl_upload_note = mo.md('  \n'.join(f'⚠ {b}' for b in _bad)) if _bad else mo.md('')
    return DL_CATALOG, dl_coll_a, dl_coll_b, dl_remember, dl_upload_note


@app.cell(hide_code=True)
def _(DL_CATALOG, dl_chosen, dl_coll_a, mo, dl_remember):
    # slot A's model picker, rebuilt when its collection changes; it
    # opens on the remembered model when that is in the collection
    _models = DL_CATALOG.get(dl_coll_a.value) or {}
    _by_id = {mid: title for title, mid in _models.items()}
    _opens_on = _by_id.get(dl_chosen['A'], next(iter(_models), None))
    dl_pick_a = mo.ui.dropdown(options=_models, value=_opens_on,
                            label='model', on_change=dl_remember('A'))
    # what the picker opens on is the slot's model too (a collection
    # change opens on that collection's first model without a change event)
    dl_remember('A')(_models.get(_opens_on))
    return (dl_pick_a,)


@app.cell(hide_code=True)
def _(DL_CATALOG, dl_chosen, dl_coll_b, mo, dl_remember):
    # slot B's model picker, with '(none)' to leave the slot empty
    _models = DL_CATALOG.get(dl_coll_b.value) or {}
    _by_id = {mid: title for title, mid in _models.items()}
    _opens_on = ('(none)' if dl_chosen['B'] == ''
                 else _by_id.get(dl_chosen['B'], next(iter(_models), '(none)')))
    dl_pick_b = mo.ui.dropdown(options={**_models, '(none)': ''}, value=_opens_on,
                            label='model', on_change=dl_remember('B'))
    dl_remember('B')(_models.get(_opens_on))
    return (dl_pick_b,)


@app.cell(hide_code=True)
def _(mo):
    # the shared controls, created here so that no model change resets them
    dl_fringes = mo.ui.slider(steps=[1, 3, 5, 7, 9], value=3, label='fringes',
                           show_value=True)
    dl_n_points = mo.ui.slider(41, 161, step=20, value=81,
                            label='screen resolution', show_value=True)
    dl_shots = mo.ui.slider(steps=[100, 200, 500, 1000, 2000, 5000, 10000],
                         value=1000, label='particles per volley',
                         show_value=True)
    dl_fire_btn = mo.ui.run_button(label='🔫 fire particles')
    dl_reset_btn = mo.ui.run_button(label='reset screens')
    dl_exact_sw = mo.ui.switch(value=False,
                            label='one engine run per pixel on every change')
    return dl_exact_sw, dl_fire_btn, dl_fringes, dl_n_points, dl_reset_btn, dl_shots


@app.cell(hide_code=True)
def _(
    dl_coll_a,
    dl_coll_b,
    dl_exact_sw,
    dl_fire_btn,
    dl_fringes,
    mo,
    dl_n_points,
    dl_pick_a,
    dl_pick_b,
    dl_rescan,
    dl_reset_btn,
    dl_shots,
    dl_upload_note,
    dl_uploads,
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
        mo.hstack([mo.hstack([dl_coll_a, dl_pick_a], justify='start', gap=1),
                   mo.hstack([dl_coll_b, dl_pick_b], justify='start', gap=1),
                   dl_uploads], justify='start', wrap=True, gap=3),
        dl_upload_note,
        mo.hstack([dl_fringes, dl_n_points, dl_shots, dl_fire_btn, dl_reset_btn, dl_rescan, dl_exact_sw],
                  wrap=True, justify='start'),
    ])


@app.cell(hide_code=True)
def _():
    # what every slot shares (the slots themselves are quantish.apps.lab):
    # the sampled hits, the rebuild baseline — each volley streams only
    # its new hits to the client — and the settings the curves were
    # last computed for, which fire and reset read instead of the
    # sliders, so a slider move never runs them
    dl_hit_store = {'seq': 0, 'hits': {}}
    dl_current = {}     # slot -> settings for fire/reset (never from sliders)
    return dl_current, dl_hit_store


@app.cell(hide_code=True)
def _(make_screen_editor, dl_pick_a):
    # slot A's screen definition, rebuilt with the model choice
    dl_screen_a = make_screen_editor(dl_pick_a.value)
    return (dl_screen_a,)


@app.cell(hide_code=True)
def _(make_screen_editor, dl_pick_b):
    dl_screen_b = make_screen_editor(dl_pick_b.value)
    return (dl_screen_b,)


@app.cell(hide_code=True)
def _(dl_hit_store, make_slot, dl_pick_a, dl_screen_a):
    dl_slot_a = make_slot('A', dl_pick_a.value, dl_screen_a, dl_hit_store)
    dl_toggles_a = dl_slot_a['toggles'] if dl_slot_a else None
    dl_ptoggles_a = dl_slot_a['ptoggles'] if dl_slot_a else None
    return dl_ptoggles_a, dl_slot_a, dl_toggles_a


@app.cell(hide_code=True)
def _(dl_hit_store, make_slot, dl_pick_b, dl_screen_b):
    dl_slot_b = make_slot('B', dl_pick_b.value, dl_screen_b, dl_hit_store)
    dl_toggles_b = dl_slot_b['toggles'] if dl_slot_b else None
    dl_ptoggles_b = dl_slot_b['ptoggles'] if dl_slot_b else None
    return dl_ptoggles_b, dl_slot_b, dl_toggles_b


@app.cell(hide_code=True)
def _(dl_hit_store, mo, refresh_panel, dl_slot_a, dl_slot_b):
    # the screens, side by side
    for _state in (dl_slot_a, dl_slot_b):
        if _state:
            refresh_panel(_state, dl_hit_store)
    mo.hstack([_state['screen'] for _state in (dl_slot_a, dl_slot_b) if _state],
              justify='start', align='start', gap=3, wrap=True)


@app.cell(hide_code=True)
def _(make_controls, mo, dl_ptoggles_a, dl_slot_a, dl_toggles_a):
    # slot A's sliders and details: rebuilt when a gate or particle is
    # toggled (the toggles' values), so a switched-off gate's slider is
    # disabled
    dl_sliders_a, _details_a = (make_controls(dl_slot_a)
                             if dl_slot_a and dl_toggles_a is not None and dl_ptoggles_a is not None
                             else (None, mo.md('')))
    _details_a  # noqa: B018 — the cell's output
    return (dl_sliders_a,)


@app.cell(hide_code=True)
def _(make_controls, mo, dl_ptoggles_b, dl_slot_b, dl_toggles_b):
    dl_sliders_b, _details_b = (make_controls(dl_slot_b)
                             if dl_slot_b and dl_toggles_b is not None and dl_ptoggles_b is not None
                             else (None, mo.md('')))
    _details_b  # noqa: B018 — the cell's output
    return (dl_sliders_b,)


@app.cell(hide_code=True)
def _(dl_exact_sw):
    dl_via = 'pixels' if dl_exact_sw.value else 'fit'
    return (dl_via,)


@app.cell(hide_code=True)
def _(dl_current, dl_fringes, dl_hit_store, dl_n_points, dl_sliders_a, dl_slot_a, update_slot, dl_via):
    # slot A's engine cell: it names sliders_a, so it reruns on A's
    # slider moves and on nothing else of B's
    dl_current['n'], dl_current['fringes'] = dl_n_points.value, dl_fringes.value
    if dl_slot_a:
        dl_current['A'] = update_slot(dl_slot_a, dl_sliders_a, dl_n_points.value,
                                   dl_fringes.value, dl_via, dl_hit_store)


@app.cell(hide_code=True)
def _(dl_current, dl_fringes, dl_hit_store, dl_n_points, dl_sliders_b, dl_slot_b, update_slot, dl_via):
    if dl_slot_b:
        dl_current['B'] = update_slot(dl_slot_b, dl_sliders_b, dl_n_points.value,
                                   dl_fringes.value, dl_via, dl_hit_store)


@app.cell(hide_code=True)
def _(
    dl_current,
    dl_fire_btn,
    grouped_curves,
    dl_hit_store,
    mo,
    random,
    sample_hits,
    screen_curves,
    set_panel_curves,
    dl_shots,
    dl_slot_a,
    dl_slot_b,
):
    # Fire and reset read the settings from `current`, so slider moves
    # do not run them; both recompute the curves with one engine run per
    # pixel, the sampled hits' source of truth. Slots without a screen
    # take no part.
    def dl_engine_curves():
        out = {}
        for slot, state in (('A', dl_slot_a), ('B', dl_slot_b)):
            if not state or state['panel'] is None or slot not in dl_current:
                continue
            xs, curves = screen_curves(state['spec'], dl_current[slot], dl_current['n'],
                                       dl_current['fringes'], 'pixels',
                                       inert=state.get('inert', ()),
                                       absent=state.get('absent', ()))
            set_panel_curves(state, xs, curves, dl_hit_store)
            out[slot] = (state, xs, curves)
        return out

    mo.stop(not dl_fire_btn.value)
    with mo.status.spinner(title='running the exact simulations…'):
        _runs = dl_engine_curves()
    _rng = random.Random()
    dl_hit_store['seq'] += 1
    for _slot, (_state, _xs, _curves) in _runs.items():
        _total, _parts = grouped_curves(_curves)
        _parts = tuple(ys for _, ys in _parts) if _parts else None
        _new = sample_hits(_xs, _total, dl_shots.value, _rng, parts=_parts)
        dl_hit_store['hits'].setdefault(_slot, []).extend(_new)
        _state['panel'].hits_chunk = {
            'seq': dl_hit_store['seq'],
            'pts': [list(_p) for _p in _new],
            'total': len(dl_hit_store['hits'][_slot])}
    return (dl_engine_curves,)


@app.cell(hide_code=True)
def _(dl_engine_curves, dl_hit_store, mo, dl_reset_btn):
    mo.stop(not dl_reset_btn.value)
    with mo.status.spinner(title='running the exact simulations…'):
        _runs = dl_engine_curves()
    dl_hit_store['seq'] += 1
    for _slot, (_state, _, _) in _runs.items():
        dl_hit_store['hits'][_slot] = []
        _state['panel'].hits_chunk = {'seq': dl_hit_store['seq'], 'reset': True}


@app.cell(hide_code=True)
def _(DL_EDITOR_UI, mo):
    mo.Html('<div style="text-align: center; font-size: 1.6em; '
            'margin: 2em 0 1em">&#8258;</div>') if not DL_EDITOR_UI else None


@app.cell(hide_code=True)
def _(DL_EDITOR_UI, mo):
    mo.md(r"""## Support code""") if DL_EDITOR_UI else None


if __name__ == "__main__":
    app.run()
