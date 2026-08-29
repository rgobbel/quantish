"""Quantish network builder — construct a model on a canvas, run it,
save it as YAML.

Run with:  marimo run notebooks/network_builder_app.py
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full", css_file="css/quantish_app.css")


@app.cell(hide_code=True)
async def initialization():
    import sys
    from pathlib import Path

    import marimo as mo

    # Under Pyodide (the WASM export) the quantish package and its
    # dependencies are installed from the bundled wheels; see the
    # quantish app's initialization for the full story.
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
        # the model library, frozen into the page at build time
        import json as _json

        from pyodide.http import pyfetch
        _resp = await pyfetch(f'{_base}/public/models.json')
        for _rel, _text in _json.loads(await _resp.string()).items():
            _p = Path('/wasm-data/models') / _rel
            _p.parent.mkdir(parents=True, exist_ok=True)
            _p.write_text(_text)

    WASM_MODE = sys.platform == 'emscripten'

    from addict import Dict as Addict

    _repo = Path(__file__).resolve().parents[1]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    import quantish.qnumber as qn
    from quantish.qnumber import CalcMode

    CalcMode.default('Float')

    import copy
    import yaml

    from quantish.diagram_layout import diagram_geometry
    from quantish.builder import (angle_degrees, coherence_warnings,
                                  config_to_graph, config_to_yaml,
                                  graph_to_config, validate_graph,
                                  variables_env)
    from quantish.builder_widget import BuilderWidget, DiagramWidget
    from quantish.display import coord_sort_key, cs_point_sort_key
    from quantish.util import angle_label
    from quantish.simulation import Simulation

    # the model library, for loading an existing model into the
    # builder: the repo's models/ directory, or the frozen copy
    # fetched above under WASM
    _models_top = (Path('/wasm-data/models') if WASM_MODE
                   else _repo / 'models')
    models_top = _models_top if _models_top.is_dir() else None
    model_paths = {str(p.relative_to(_models_top)): p
                   for p in sorted(_models_top.rglob('*.yaml'))
                   if p.name not in ('defaults.yaml', 'schema.yaml')
                   and not p.name.startswith('.')} \
        if models_top else {}
    return (
        Addict,
        BuilderWidget,
        CalcMode,
        DiagramWidget,
        Simulation,
        WASM_MODE,
        angle_degrees,
        angle_label,
        coherence_warnings,
        config_to_graph,
        config_to_yaml,
        coord_sort_key,
        cs_point_sort_key,
        diagram_geometry,
        graph_to_config,
        mo,
        model_paths,
        models_top,
        validate_graph,
        variables_env,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    _intro = mo.md(r"""
    # Quantish Network Builder

    With this tool you can build a complete quantish model, either from scratch or by modifying an existing model.
    """)
    def _sub(md):
        # a sub-section's body sits one list level under its '- '
        # heading (.qb-doc-body in css/quantish_app.css); the class
        # rides inside the content, which is what marimo's accordion
        # actually renders
        return mo.Html('<div class="qb-doc-body">' + mo.md(md).text
                       + '</div>')

    _doc = mo.vstack([mo.md(r"""
    Use the icon palette beside the canvas to add components to a network. Hovering over each icon will reveal a descriptive tooltip.
    Components can be added to a network by dragging from a palette icon, or clicking on
    one of them. Basic circuit elements are above the divider, grouping elements are below.
    In most contexts, text can use [Markdown](https://docs.marimo.io/api/markdown/) formatting, including interpolated
    [LaTeX](https://www.latex-project.org/).
    """), mo.accordion({'- Types of components': _sub(r"""
    - **gates** are quantish Fredkin gates, as described in *Good and Real*.
    - **particles** are the entities that travel through a quantish network.
      Each starts with a sign (+ or −) and a complex-valued weight, and enters the network through one gate input.
    - **phase plates** (φ) are gates that rotate every traversing weight in the complex plane without
      affecting amplitude, simulating an alteration to [optical path length](https://en.wikipedia.org/wiki/Optical_path_length). One example of a real-world phase plate device is an
      [electro-optic modulator](https://en.wikipedia.org/wiki/Electro-optic_modulator). 
    - **delay gates** are simple passthroughs, useful for manipulating diagram layout, but having no effect on execution.
    """), '- Grouping': _sub(r"""
    - A **run stage** is a set of gates that fire together, one step
      of a run. By default execution proceeds serially in an order determined by network topology. Run stages can be
      used for cases in which the automatically-determined order is ambiguous.
    - A **diagram group** is purely visual, a labeled bracket in the
      network diagram. Diagram groups don't affect how a circuit runs.
    """), '- Actions': _sub(r"""
    - To modify an existing model, pick one from the list of predefined models or upload a model's YAML declaration and press
      **⬆ load into builder**. The selected model replaces the contents of canvas
    - **✕ clear** starts over with an empty canvas, with confirmation. **Note**: _Undo_ will restore the superseded canvas.

    """), '- Creating and editing a network': _sub(r"""
    - Drag from an **output port** on the right side of any gate or particle to a free
      **input port** on the left side of another element to wire them together.
    - Double-click in the middle of a Fredkin gate to set its measurement angle, or for a phase
      plate, its rotation angle.

      - Angles can be entered using the full expression syntax supported in the the models' YAML files:
        - Arithmetic expressions such `pi/6`, `rad(30)`, `acos(4/5)`, or `pi/2 + pi/8` produce values in radians.
        - Numeric values with no other expressions included, or suffixed with a degree symbol (°) are interpreted as degrees.
        - Anything unparseable is flagged on the gate and detailed in the status line.
    - Double-click anywhere on a particle to edit it: its name (sign
      first, as `+p1` or `-p1`, with an optional display string after a
      space) and its initial weight, which can be a number, a complex
      literal such as `0.5+0.87j`, a magnitude and phase such as `0.7@30°`,
      an expression, or a variable name. A particle wired to **two** inputs
      starts in a superposition over both (the book's U2 branching); its
      dialog then also takes the probability of the first-wired one.
    - Double-click a gate's **name** to rename it (particles rename in
      their own dialog, above)
      - Append a **display string** after the name, separated by a space
        (`g_split $g_{split}$`), to have the object drawn with that string
        instead of its name — math notation renders with real sub- and
        superscripts. Remove the display string to go back to the name.
        Saved models keep these in a top-level `display_strings` section.
      - Changing a stage or group box label renames the whole group
        - A group name that exactly matches a stage name collapses the two borders into one
    - Click a component or wire and press **delete
      selected** or the Delete key to remove it
    - Labels can be attached to wires. Double-click a wire or a port to name that wire
      segment. Double-clicking on an unconnected port labels a null input or output
      stub, drawn as a short labeled wire. Labels can use a subset of LaTeX syntax for sub- and superscripts:
      - `$w_{1a}` $\rightarrow$ $w_{1a}$
      - `$things^{that}_{group}` $\rightarrow$ $things^{that}_{group}$

    - **↩** and **↪** (or ⌘Z and ⇧⌘Z) invoke _Undo_ and _Redo_
    - Scroll (or pinch) zooms, centered on the cursor
    - Dragging empty space pans, on both the editing canvas and the results
      diagram. Also on both, double-click resets the diagram to its default magnification and position.
    - Shift-click (or ⌘-click) toggles an object's selected state.
      Only one object type can be selected at a time
    - Shift-drag a box for a marquee selection. The palette's stage
      icon shows their run stage name (drawn as a teal box) and the
      group icon their diagram group name (a dashed box; an empty name
      clears either)
    """), '- Optional fields': _sub(r"""
    - The model's **title**, **calculation mode**, and **angle unit**
      are editable above the canvas. 
    - The model's **caption**, **variables**, and free-text **notes** can be edited
      in fields that will appear when you click on the **Caption, notes, and variables**
      heading below the canvas. Angle and weight specs may reference variables by name (e.g. 'Q1').
    """)}, multiple=True)], align='stretch')
    mo.vstack([_intro, mo.accordion({
        '### Documentation\n\n<span style="font-size:0.85em">'
        'under the fold</span>': _doc})], align='stretch')
    return


@app.cell(hide_code=True)
def _(mo):
    # the last model loaded into the builder: {'graph', 'title', 'notes'}
    get_loaded, set_loaded = mo.state(None)
    # a parsed load waiting for the really-replace-the-canvas step
    get_pending, set_pending = mo.state(None)
    # which File action's controls are unfolded: 'open' | 'upload' | None
    get_file_mode, set_file_mode = mo.state(None)
    return (
        get_file_mode,
        get_loaded,
        get_pending,
        set_file_mode,
        set_loaded,
        set_pending,
    )


@app.cell(hide_code=True)
def _(mo, model_paths):
    # static pieces of the File controls: the collection picker (the
    # model picker itself is rebuilt per collection below) and the
    # upload control
    collections = sorted({k.split('/')[0] for k in model_paths})
    collection_pick = mo.ui.dropdown(
        options=collections,
        value='gr2026' if 'gr2026' in collections
        else (collections[0] if collections else None),
        label='collection')
    model_upload = mo.ui.file(filetypes=['.yaml', '.yml'],
                              label='choose a file…')
    return collection_pick, model_upload


@app.cell(hide_code=True)
def _(WASM_MODE, builder_config, config_to_yaml, file_name, mo, model_paths):
    # the File row, in the spirit of a Mac File menu: New, Open a
    # predefined model, Upload one, Save into the local models
    # directory (running from the repo only — in the browser the
    # filesystem dies with the tab, so Download is the way out),
    # Download through the browser
    new_btn = mo.ui.run_button(label='✚ new')
    open_btn = mo.ui.run_button(label='📂 open…')
    upload_btn = mo.ui.run_button(label='⬆ upload…')
    save_btn = mo.ui.run_button(label='💾 save',
                                disabled=(builder_config is None
                                          or not model_paths))
    _download = (
        mo.download(data=config_to_yaml(builder_config).encode(),
                    filename=f'{file_name.value}.yaml',
                    label='download')
        if builder_config is not None
        else mo.ui.run_button(label='⬇ download', disabled=True))
    mo.hstack([mo.md('**File:**'), new_btn, open_btn, upload_btn]
              + ([] if WASM_MODE else [save_btn])
              + [_download], justify='start', gap=0.75)
    return new_btn, open_btn, save_btn, upload_btn


@app.cell(hide_code=True)
def _(get_file_mode, open_btn, set_file_mode, upload_btn):
    # open…/upload… unfold their controls; pressing again folds them
    def _():
        if open_btn.value:
            set_file_mode(None if get_file_mode() == 'open' else 'open')
        elif upload_btn.value:
            set_file_mode(None if get_file_mode() == 'upload'
                          else 'upload')

    _()
    return


@app.cell(hide_code=True)
def _(collection_pick, get_file_mode, mo, model_paths, model_upload):
    # the unfolded controls for the chosen File action
    _collection = collection_pick.value
    model_pick = mo.ui.dropdown(
        options={k.split('/', 1)[1].removesuffix('.yaml'): k
                 for k in sorted(model_paths)
                 if k.split('/')[0] == _collection},
        label='model')
    open_go_btn = mo.ui.run_button(label='open')
    upload_go_btn = mo.ui.run_button(label='open file')
    _mode = get_file_mode()
    _row = None
    if _mode == 'open':
        _row = mo.hstack([collection_pick, model_pick, open_go_btn],
                         justify='start', gap=0.75)
    elif _mode == 'upload':
        _row = mo.hstack([model_upload, upload_go_btn],
                         justify='start', gap=0.75)
    _row
    return model_pick, open_go_btn, upload_go_btn


@app.cell(hide_code=True)
def _(
    config_to_graph,
    mo,
    model_paths,
    model_pick,
    model_upload,
    new_btn,
    open_go_btn,
    set_file_mode,
    set_pending,
    upload_go_btn,
    yaml,
):
    # every File action lands as "pending" here — the next cell applies
    # it directly when the canvas is empty, and asks first when it
    # isn't. (This cell must not read the canvas itself: it would
    # re-run when the load replaces the widget, and mis-read the
    # freshly loaded canvas as one that needs another confirmation.)
    def _tri_mode(config):
        # calculation_mode is a case-independent string; None when the
        # YAML leaves the mode unset (legacy boolean 'symbolic' still
        # read on upload of old files)
        mode = config.get('calculation_mode')
        if mode is not None:
            return str(mode).lower() == 'symbolic'
        if 'symbolic' in config:
            return bool(config['symbolic'])
        return None

    def _load():
        if new_btn.value:
            set_pending({'graph': {'gates': {}, 'particles': {},
                                   'links': []},
                         'notes': [], 'title': 'my_network',
                         'file': 'my_network', 'caption': '',
                         'variables': {}, 'symbolic': None,
                         'angle_unit': None, 'model_notes': '',
                         'source': 'a new empty model'})
            return None
        if upload_go_btn.value and model_upload.contents():
            text = model_upload.contents().decode()
            source = model_upload.name()
        elif open_go_btn.value and model_pick.value:
            text = model_paths[model_pick.value].read_text()
            source = model_pick.value
        else:
            return None
        try:
            config = yaml.safe_load(text)
            graph, notes = config_to_graph(config)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**could not load {source}** — {exc}')
        from pathlib import PurePath
        set_file_mode(None)
        set_pending({'graph': graph, 'notes': notes,
                     'title': config.get('title') or 'my_network',
                     'file': PurePath(source).stem,
                     'caption': config.get('caption') or '',
                     'variables': config.get('variables') or {},
                     'symbolic': _tri_mode(config),
                     'angle_unit': config.get('angle_unit'),
                     'model_notes': config.get('notes') or '',
                     'source': source})
        return None

    _load()
    return


@app.cell(hide_code=True)
def _(builder, get_pending, mo, set_loaded, set_pending):
    # the really? step when a load would wipe a populated canvas; an
    # empty canvas loads straight through
    confirm_load_btn = mo.ui.run_button(label='replace the canvas')
    keep_canvas_btn = mo.ui.run_button(label='keep what I have')

    def _():
        _p = get_pending()
        if _p is None:
            return None
        _g = builder.value.get('graph') or {}
        if not (_g.get('gates') or _g.get('particles')):
            set_pending(None)
            set_loaded(_p)
            return None
        return mo.vstack([
            mo.md(f"⚠ the canvas holds {len(_g.get('gates') or {})} "
                  f"gate(s) and {len(_g.get('particles') or {})} "
                  f"particle(s) — really replace it with "
                  f"**{_p['source']}**?"),
            mo.hstack([confirm_load_btn, keep_canvas_btn],
                      justify='start', gap=1),
        ], align='start')

    _()
    return confirm_load_btn, keep_canvas_btn


@app.cell(hide_code=True)
def _(confirm_load_btn, get_pending, keep_canvas_btn, set_loaded, set_pending):
    def _():
        _p = get_pending()
        if _p is None:
            return
        if confirm_load_btn.value:
            set_pending(None)
            set_loaded(_p)
        elif keep_canvas_btn.value:
            set_pending(None)

    _()
    return


@app.cell(hide_code=True)
def _(builder_config, config_to_yaml, file_name, mo, models_top, save_btn):
    # save writes into the local models directory (the web deployment
    # has no server filesystem — download covers it there)
    def _():
        if not (save_btn.value and builder_config and models_top):
            return None
        dest = models_top / 'extras' / f'{file_name.value}.yaml'
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(config_to_yaml(builder_config))
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**could not save** — {exc}')
        return mo.md('<span style="font-size: 0.9em">saved '
                     f'**{dest}**</span>')

    _()
    return


@app.cell(hide_code=True)
def _(get_loaded, mo):
    # the model's whole header is editable: title (into the YAML) and
    # file name (of the saved file) are separate; caption, variables,
    # and the calculation mode ride into the YAML too
    _loaded = get_loaded() or {}
    model_title = mo.ui.text(
        value=_loaded.get('title') or 'my_network', label='title')
    file_name = mo.ui.text(
        value=_loaded.get('file') or 'my_network', label='file name')
    # tri-state: '-' leaves the calculation mode out of the YAML
    # (the loader's defaults decide at run time)
    mode_pick = mo.ui.dropdown(
        options=['-', 'Float', 'Symbolic'],
        value={None: '-', False: 'Float',
               True: 'Symbolic'}[_loaded.get('symbolic')],
        label='calculation mode (default: Float)')
    # tri-state like the mode: '-' omits angle_unit from the YAML
    # (plain-number angles then read as radians)
    unit_pick = mo.ui.dropdown(
        options=['-', 'radians', 'degrees'],
        value=_loaded.get('angle_unit') or '-',
        label='angle unit (default: radians)')
    caption_input = mo.ui.text_area(
        value=_loaded.get('caption') or '', rows=2, full_width=True,
        placeholder='a caption to be displayed in the network diagram',
        label='**caption**')
    notes_input = mo.ui.text_area(
        value=_loaded.get('model_notes') or '', rows=3, full_width=True,
        placeholder='free-form text', label='**notes**')

    def _vars_text(vs):
        return '\n'.join(
            f"{k}: '{v}'" if isinstance(v, str) else f'{k}: {v}'
            for k, v in (vs or {}).items())

    variables_editor = mo.ui.text_area(
        value=_vars_text(_loaded.get('variables')), rows=6,
        full_width=True,
        placeholder='variable definitions in YAML format')
    _report = None
    if _loaded and _loaded.get('source'):
        _msg = ('<span style="font-size: 0.9em">loaded '
                f"**{_loaded['source']}**</span>")
        if _loaded['notes']:
            _msg += '\n' + '\n'.join(f'- {n}' for n in _loaded['notes'])
        _report = mo.md(_msg)
    mo.vstack(
        ([_report] if _report is not None else [])
        + [mo.vstack([file_name,
                      mo.hstack([model_title, mode_pick, unit_pick],
                                justify='start', gap=0.75)])],
        align='stretch')
    return (
        caption_input,
        file_name,
        mode_pick,
        model_title,
        notes_input,
        unit_pick,
        variables_editor,
    )


@app.cell(hide_code=True)
def _(mo, variables_editor, yaml):
    # the parsed variables mapping; parse trouble shows here, and
    # definitions the engine can't evaluate show in the status line
    def _():
        text = variables_editor.value.strip()
        if not text:
            return {}, None
        try:
            v = yaml.safe_load(text)
            if v is None:
                return {}, None
            if not isinstance(v, dict):
                raise ValueError('expected a name: expression mapping')
            return {str(k): val for k, val in v.items()}, None
        except Exception as exc:  # noqa: BLE001 — show, don't crash
            return {}, mo.md(f'**variables not parseable** — {exc}')

    model_vars, _err = _()
    _err
    return (model_vars,)


@app.cell(hide_code=True)
def _(BuilderWidget, get_loaded, mo):
    _loaded = get_loaded()
    builder_widget = (BuilderWidget(graph=_loaded['graph']) if _loaded
                      else BuilderWidget())
    builder = mo.ui.anywidget(builder_widget)
    builder
    return builder, builder_widget


@app.cell(hide_code=True)
def _(
    angle_degrees,
    angle_label,
    builder,
    builder_widget,
    caption_input,
    coherence_warnings,
    graph_to_config,
    mo,
    mode_pick,
    model_title,
    model_vars,
    notes_input,
    unit_pick,
    validate_graph,
    variables_env,
):
    # The live translation of the canvas: either the list of problems
    # keeping it from running, or the derived model config — caption,
    # notes, variables, calculation mode, and angle unit included.
    _graph = builder.value.get('graph') or {}
    _unit = None if unit_pick.value == '-' else unit_pick.value
    problems = validate_graph(_graph, variables=model_vars,
                              angle_unit=_unit or 'radians')
    builder_config = None
    if not problems:
        try:
            builder_config = graph_to_config(
                _graph, model_title.value,
                caption=caption_input.value.strip() or None,
                variables=model_vars or None,
                symbolic={'-': None, 'Float': False,
                          'Symbolic': True}[mode_pick.value],
                angle_unit=_unit,
                notes=notes_input.value.strip() or None)
        except ValueError as exc:  # a wiring loop
            problems = [str(exc)]
    _env, _ = variables_env(model_vars)

    # display labels for the canvas ('pi/6 (30.0°)'); a spec the
    # engine cannot parse shows flagged, with the specifics in the
    # problems list above
    def _labels():
        out = {}
        for _n, _gd in (_graph.get('gates') or {}).items():
            if _gd.get('kind') == 'delay':
                continue
            _f = 'phase' if _gd.get('kind') == 'phase' else 'angle'
            _spec = _gd.get(_f, 0)
            try:
                out[_n] = angle_label(
                    _spec, angle_degrees(_spec, _env,
                                         _unit or 'radians'), '°')
            except Exception:  # noqa: BLE001 — reported via problems
                out[_n] = f'⚠ {_spec}'
        return out

    builder_widget.angle_labels = _labels()

    def _():
        n_g = len(_graph.get('gates', {}))
        n_p = len(_graph.get('particles', {}))
        n_l = len(_graph.get('links', []))
        summary = f'{n_g} gate(s), {n_p} particle(s), {n_l} wire(s)'
        if problems:
            return mo.md(summary + ' — not runnable yet:\n' +
                         '\n'.join(f'- {p}' for p in problems))
        stages = ' | '.join(
            f"{name}: {', '.join(gs)}"
            for name, gs in builder_config['run_stages'].items())
        msg = f'{summary} — runnable. Stages: {stages}'
        warns = coherence_warnings(_graph)
        if warns:
            msg += '\n' + '\n'.join(f'- ⚠ {w}' for w in warns)
        return mo.md(msg)

    _()
    return (builder_config,)


@app.cell(hide_code=True)
def _(caption_input, mo, notes_input, variables_editor):
    # all entirely optional, so they live below the canvas
    mo.accordion({'#### Caption, notes, and variables':
                  mo.vstack([
        caption_input,
        notes_input,
        mo.md('<span style="font-size: 0.9em">**variables**</span>'),
        variables_editor], align='stretch')})
    return


@app.cell(hide_code=True)
def _(builder_config, mo):
    run_network_btn = mo.ui.run_button(label='▶ Run network',
                                       disabled=builder_config is None)
    run_network_btn
    return (run_network_btn,)


@app.cell(hide_code=True)
def _(Addict, CalcMode, Simulation, builder_config, mo, run_network_btn):
    # sim_built is None until a successful run of the CURRENT network;
    # any canvas change recreates the button unpressed, clearing stale
    # results (the same staleness scheme as the main app)
    def _build():
        if not (run_network_btn.value and builder_config):
            return None, None
        CalcMode.default(
            'Symbolic' if str(builder_config.get('calculation_mode')
                              or '').lower() == 'symbolic' else 'Float')
        base = {'string_precision': 2, 'max_symbolic_len': 40,
                'loglevel': 'warning'}
        base.update(builder_config)
        config = Addict(base)
        config.config_path = 'builder'
        try:
            s = Simulation(config)
            s.run()
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return None, mo.md(f'**run failed** — `{exc}`')
        total = sum(float(p.probability)
                    for p in s.result_space.index.values())
        return s, mo.md(
            f'Ran **{config.title}** — '
            f'{len(s.run_stages)} stage(s), '
            f'{len(s.result_space.index)} final configuration-space '
            f'point(s), total probability {total:.6f}')

    sim_built, _msg = _build()
    _msg
    return (sim_built,)


@app.cell(hide_code=True)
def _(DiagramWidget, diagram_geometry, mo, sim_built):
    mo.stop(sim_built is None)

    def _():
        # the one renderer: the results diagram drawn natively by the
        # builder's SVG widget from the shared layout/router geometry —
        # width-tracking, wheel-zoom around the cursor, drag to pan,
        # double-click to reset; no vl-convert, WASM-safe
        try:
            return mo.vstack([
                mo.md('<span style="font-size: 0.85em">scroll/pinch '
                      'to zoom · drag to pan · double-click to reset '
                      '· hover over a port for its values</span>'),
                mo.ui.anywidget(DiagramWidget(
                    geometry=diagram_geometry(sim_built, has_run=True))),
            ], gap=0)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'_circuit diagram failed: {exc}_')

    _()
    return


@app.cell(hide_code=True)
def _(coord_sort_key, cs_point_sort_key, mo, sim_built):
    mo.stop(sim_built is None)

    def _():
        rows = []
        for p in sorted(sim_built.result_space.index.values(),
                        key=lambda p: cs_point_sort_key(sim_built, p)):
            cfg = p.short_config(
                key=lambda c: coord_sort_key(sim_built, c)).replace('|', ' ')
            w = complex(p.weight)
            rows.append(f'| `{cfg}` | {w.real:+.4f}{w.imag:+.4f}i '
                        f'| {float(p.probability):.4f} |')
        return mo.md('\n'.join(
            ['', '| configuration | weight | probability |',
             '|---|---|---|'] + rows))

    _()
    return


@app.cell(hide_code=True)
def _(builder_config, config_to_yaml, mo):
    mo.stop(builder_config is None)
    _yaml = config_to_yaml(builder_config)
    mo.accordion({'Model YAML': mo.md(f'```yaml\n{_yaml}```')})
    return


if __name__ == "__main__":
    app.run()
