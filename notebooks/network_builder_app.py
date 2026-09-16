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

    from addict import Dict as Addict

    _repo = Path(__file__).resolve().parents[1]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    import yaml

    from quantish.apps.common import (
        MODELS_TOP,
        WASM_MODE,
        build_stamp,
        in_div,
        init_engine,
        model_files,
        remember_in,
        stamp_html,
        switch_off_boxes,
        switched_off,
        vars_text,
    )
    from quantish.apps.sweep_ui import (
        editor_rows,
        editor_spec,
        sweep_chart,
        sweep_controls,
        sweep_run,
    )
    from quantish.builder import (
        angle_degrees,
        coherence_warnings,
        config_extras,
        config_to_graph,
        config_to_yaml,
        extract_sections,
        graph_to_config,
        section_body,
        validate_graph,
        variables_block,
        variables_env,
    )
    from quantish.builder_widget import (
        BuilderWidget,
        DiagramWidget,
        NetworkGraphWidget,
    )
    from quantish.diagram_layout import diagram_geometry
    from quantish.display import (
        coord_sort_key,
        cs_point_sort_key,
        html_table,
        particle_names,
        particle_tokens,
        sym_or_float,
    )
    from quantish.network_graph import NetworkGraph
    from quantish.qnumber import CalcMode
    from quantish.screen import model_label
    from quantish.screen import model_title as yaml_title
    from quantish.simulation import Simulation
    from quantish.sweep import check_sweep
    from quantish.util import angle_label

    init_engine()
    # the model library, for loading an existing model into the
    # builder (and saving one beside them): the repo's models/
    # directory, or the frozen copy fetched above under WASM; None
    # when there is none
    models_top = MODELS_TOP if MODELS_TOP.is_dir() else None
    model_paths = model_files(MODELS_TOP)
    return (
        Addict,
        BuilderWidget,
        CalcMode,
        DiagramWidget,
        NetworkGraph,
        NetworkGraphWidget,
        Simulation,
        check_sweep,
        model_label,
        yaml_title,
        WASM_MODE,
        angle_degrees,
        angle_label,
        build_stamp,
        coherence_warnings,
        config_extras,
        config_to_graph,
        config_to_yaml,
        extract_sections,
        section_body,
        variables_block,
        coord_sort_key,
        cs_point_sort_key,
        diagram_geometry,
        graph_to_config,
        html_table,
        in_div,
        mo,
        particle_names,
        particle_tokens,
        remember_in,
        stamp_html,
        switch_off_boxes,
        switched_off,
        editor_rows,
        editor_spec,
        sweep_chart,
        sweep_controls,
        sweep_run,
        sym_or_float,
        model_paths,
        models_top,
        validate_graph,
        variables_env,
        vars_text,
        yaml,
    )


@app.cell(hide_code=True)
def _(in_div, mo):
    _intro = mo.md(r"""
    # Quantish Network Builder

    With this tool you can build a complete quantish model, either from scratch or by modifying an existing model.
    """)
    # a sub-section's body sits one list level under its '- ' heading
    # (.qb-doc-body in css/quantish_app.css, via in_div)
    _doc = mo.vstack([mo.md(r"""
    Use the icon palette beside the canvas to add components to a network. Hovering over each icon will reveal a descriptive tooltip.
    Components can be added to a network by dragging from a palette icon, or clicking on
    one of them. Basic circuit elements are above the divider, grouping elements are below.
    In most contexts, text can use [Markdown](https://docs.marimo.io/api/markdown/) formatting, including interpolated
    [LaTeX](https://www.latex-project.org/).
    """), mo.accordion({'- Types of components': in_div('qb-doc-body', r"""
    - **gates** are quantish Fredkin gates, as described in *Good and Real*.
    - **particles** are the entities that travel through a quantish network.
      Each starts with a sign (+ or −) and a complex-valued weight, and enters the network through one gate input.
    - **phase plates** (φ) are gates that rotate every traversing weight in the complex plane without
      affecting amplitude, simulating an alteration to [optical path length](https://en.wikipedia.org/wiki/Optical_path_length). One example of a real-world phase plate device is an
      [electro-optic modulator](https://en.wikipedia.org/wiki/Electro-optic_modulator). 
    - **delay gates** are simple passthroughs, useful for manipulating diagram layout, but having no effect on execution.
    """), '- Grouping': in_div('qb-doc-body', r"""
    - A **run stage** is a set of gates that fire together, one step
      of a run. By default execution proceeds serially in an order determined by network topology. Run stages can be
      used for cases in which the automatically-determined order is ambiguous.
    - A **diagram group** is purely visual, a labeled bracket in the
      network diagram. Diagram groups don't affect how a circuit runs.
    """), '- Actions': in_div('qb-doc-body', r"""
    - To modify an existing model, pick one from the list of predefined models or upload a model's YAML declaration and press
      **⬆ load into builder**. The selected model replaces the contents of canvas
    - **✕ clear** starts over with an empty canvas, with confirmation. **Note**: _Undo_ will restore the superseded canvas.

    """), '- Creating and editing a network': in_div('qb-doc-body', r"""
    - Drag from an **output port** on the right side of any gate or particle to a free
      **input port** on the left side of another element to wire them together.
    - Double-click in the middle of a Fredkin gate to set its measurement angle, or for a phase
      plate, its rotation angle.

      - Angles can be entered using the full expression syntax supported in the models' YAML files:
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
    """), '- Optional fields': in_div('qb-doc-body', r"""
    - The model's **title**, **calculation mode**, and **angle unit**
      are editable above the canvas. 
    - The model's **caption**, **variables**, and free-text **notes** can be edited
      in fields that will appear when you click on the **Caption, notes, and variables**
      heading below the canvas. Angle and weight specs may reference variables by name (e.g. 'Q1').
    """)}, multiple=True)], align='stretch')
    mo.vstack([_intro, mo.accordion({
        '### Documentation\n\n<span style="font-size:0.85em">'
        'under the fold</span>': _doc})], align='stretch')


@app.cell(hide_code=True)
async def _(build_stamp, stamp_html):
    # which build is this? (the site build writes public/version.json
    # beside the page; a development copy says so instead)
    stamp_html(await build_stamp())


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
def _(
    WASM_MODE,
    builder_config,
    config_to_yaml,
    file_name,
    mo,
    model_paths,
    raw_sections,
):
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
        mo.download(data=config_to_yaml(builder_config,
                                        raw_sections=raw_sections).encode(),
                    filename=f'{file_name.value}.yaml',
                    label='download')
        if builder_config is not None
        else mo.ui.run_button(label='⬇ download', disabled=True))
    mo.hstack([mo.md('**File:**'), new_btn, open_btn, upload_btn]
              + ([] if WASM_MODE else [save_btn])
              + [_download], justify='start', gap=0.75, wrap=True)
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


@app.cell(hide_code=True)
def _(collection_pick, get_file_mode, mo, model_label, model_paths, model_upload, yaml_title):
    # the unfolded controls for the chosen File action
    _collection = collection_pick.value
    model_pick = mo.ui.dropdown(
        options={model_label(k.split('/', 1)[1].removesuffix('.yaml'),
                             yaml_title(model_paths[k])): k
                 for k in sorted(model_paths)
                 if k.split('/')[0] == _collection},
        label='model')
    open_go_btn = mo.ui.run_button(label='open')
    upload_go_btn = mo.ui.run_button(label='open file')
    _mode = get_file_mode()
    _row = None
    if _mode == 'open':
        _row = mo.hstack([collection_pick, model_pick, open_go_btn],
                         justify='start', gap=0.75, wrap=True)
    elif _mode == 'upload':
        _row = mo.hstack([model_upload, upload_go_btn],
                         justify='start', gap=0.75, wrap=True)
    _row  # noqa: B018 — the cell's output
    return model_pick, open_go_btn, upload_go_btn


@app.cell(hide_code=True)
def _(
    config_extras,
    config_to_graph,
    extract_sections,
    mo,
    model_paths,
    model_pick,
    model_upload,
    new_btn,
    open_go_btn,
    section_body,
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
                         'variables': {}, 'variables_text': '',
                         'symbolic': None,
                         'angle_unit': None, 'model_notes': '',
                         'extras': {}, 'extras_text': {},
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
                     # the file's variables section as written (comments
                     # kept) seeds the editor; the parsed dict is the
                     # fallback for files with none
                     'variables_text': section_body(
                         extract_sections(text).get('variables', '')),
                     'symbolic': _tri_mode(config),
                     'angle_unit': config.get('angle_unit'),
                     'model_notes': config.get('notes') or '',
                     # sections the builder does not edit (a sweep,
                     # epr_stats, …) ride through to the saved file
                     'extras': config_extras(config),
                     # … and their raw text, so their comments survive
                     'extras_text': extract_sections(text),
                     'source': source})
        return None

    _load()


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
                      justify='start', gap=1, wrap=True),
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


@app.cell(hide_code=True)
def _(
    builder_config,
    config_to_yaml,
    file_name,
    mo,
    models_top,
    raw_sections,
    save_btn,
):
    # save writes into the local models directory (the web deployment
    # has no server filesystem — download covers it there)
    def _():
        if not (save_btn.value and builder_config and models_top):
            return None
        dest = models_top / 'extras' / f'{file_name.value}.yaml'
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(config_to_yaml(builder_config,
                                           raw_sections=raw_sections))
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**could not save** — {exc}')
        return mo.md('<span style="font-size: 0.9em">saved '
                     f'**{dest}**</span>')

    _()


@app.cell(hide_code=True)
def _(get_loaded, mo, vars_text):
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

    variables_editor = mo.ui.text_area(
        value=(_loaded.get('variables_text')
               or vars_text(_loaded.get('variables'))), rows=6,
        full_width=True,
        placeholder='variable definitions in YAML format')
    # the loaded model's unhandled sections, kept for the save — their
    # parsed values (for the config) and their raw text (for the file)
    loaded_extras = _loaded.get('extras') or {}
    loaded_extras_text = _loaded.get('extras_text') or {}
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
                                justify='start', gap=0.75, wrap=True)])],
        align='stretch')
    return (
        caption_input,
        file_name,
        loaded_extras,
        loaded_extras_text,
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
                raise TypeError('expected a name: expression mapping')
            return {str(k): val for k, val in v.items()}, None
        except Exception as exc:  # noqa: BLE001 — show, don't crash
            return {}, mo.md(f'**variables not parseable** — {exc}')

    model_vars, _err = _()
    _err  # noqa: B018 — the cell's output
    return (model_vars,)


@app.cell(hide_code=True)
def _(BuilderWidget, get_loaded, mo):
    _loaded = get_loaded()
    builder_widget = (BuilderWidget(graph=_loaded['graph']) if _loaded
                      else BuilderWidget())
    builder = mo.ui.anywidget(builder_widget)
    # the run's switch-off choices ('g:name' / 'p:name' -> False when
    # off), remembered across canvas edits, which rebuild the checkboxes
    off_memory = {}
    # the sweep editor's entries, remembered the same way
    sweep_memory = {}
    builder  # noqa: B018 — the cell's output
    return builder, builder_widget, off_memory, sweep_memory


@app.cell(hide_code=True)
def _(
    Addict,
    Simulation,
    angle_degrees,
    angle_label,
    builder,
    builder_widget,
    caption_input,
    check_sweep,
    coherence_warnings,
    graph_to_config,
    loaded_extras,
    loaded_extras_text,
    mo,
    mode_pick,
    model_title,
    model_vars,
    notes_input,
    sweep_cfg,
    switch_off,
    switch_off_particles,
    unit_pick,
    validate_graph,
    variables_block,
    variables_editor,
    variables_env,
):
    # The live translation of the canvas: either the list of problems
    # keeping it from running, or the derived model config — caption,
    # notes, variables, calculation mode, angle unit, and the loaded
    # model's other sections (extras) included.
    _graph = builder.value.get('graph') or {}
    _unit = None if unit_pick.value == '-' else unit_pick.value
    problems = validate_graph(_graph, variables=model_vars,
                              angle_unit=_unit or 'radians')
    if switch_off_particles and all(
            not switch_off.value.get(f'p:{p}', True) for p in switch_off_particles):
        problems.append('every particle is switched off — nothing would enter')
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
                notes=notes_input.value.strip() or None,
                extras={**{k: v for k, v in loaded_extras.items() if k != 'sweep'},
                        **({'sweep': sweep_cfg} if sweep_cfg else {})})
        except ValueError as exc:  # a wiring loop
            problems = [str(exc)]
    if builder_config is not None and sweep_cfg:
        # the sweep must name the model's own variable, particle, and gate
        try:
            check_sweep(Simulation(Addict({'loglevel': 'warning', **builder_config})),
                        sweep_cfg)
        except Exception as exc:  # noqa: BLE001 — the engine's own wording
            problems = [f'sweep: {exc}']
            builder_config = None
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
                                         _unit or 'radians'), '°',
                    variables=model_vars)
            except Exception:  # noqa: BLE001 — reported via problems
                out[_n] = f'⚠ {_spec}'
        return out

    builder_widget.angle_labels = _labels()

    # what the save writes verbatim: the loaded file's unhandled sections
    # and, when the editor holds variables, its text — comments included
    raw_sections = {k: v for k, v in loaded_extras_text.items() if k != 'sweep'}   # regenerated
    if model_vars and variables_editor.value.strip():
        raw_sections['variables'] = variables_block(variables_editor.value)

    def _status():
        n_g = len(_graph.get('gates', {}))
        n_p = len(_graph.get('particles', {}))
        n_l = len(_graph.get('links', []))
        summary = f'{n_g} gate(s), {n_p} particle(s), {n_l} wire(s)'
        if problems:
            msg = (summary + ' — **not runnable yet:**\n'
                   + '\n'.join(f'- {p}' for p in problems))
            # bright red: this is the one message that says why the Run
            # button is disabled
            return mo.Html(f'<div class="not-runnable">{mo.md(msg).text}</div>')
        stages = ' | '.join(f"{name}: {', '.join(gs)}"
                            for name, gs in builder_config['run_stages'].items())
        msg = f'{summary} — runnable. Stages: {stages}'
        warns = coherence_warnings(_graph)
        if warns:
            msg += '\n' + '\n'.join(f'- ⚠ {w}' for w in warns)
        return mo.md(msg)

    _status()
    return builder_config, raw_sections


@app.cell(hide_code=True)
def _(builder, loaded_extras, model_vars, sweep_controls, sweep_memory):
    # the model's sweep, entered here: the variable to sweep (one of
    # the editor's), its range and point count, the particle and gate
    # whose arrival is recorded, and an optional sort. Seeded from a
    # loaded model's sweep section, remembered across rebuilds (the
    # elements are remade whenever the variables or the canvas change)
    _graph = builder.value.get('graph') or {}
    _decl = loaded_extras.get('sweep')
    sweep_ui = sweep_controls(model_vars or {}, _graph.get('particles') or {},
                              _graph.get('gates') or {},
                              _decl if isinstance(_decl, dict) else None,
                              memory=sweep_memory, declare_box=True)
    return (sweep_ui,)


@app.cell(hide_code=True)
def _(editor_spec, sweep_ui):
    # the sweep as the model declares it (None when not declared)
    sweep_cfg = editor_spec(sweep_ui.value)
    return (sweep_cfg,)


@app.cell(hide_code=True)
def _(builder_config, mo, sweep_cfg):
    # the sweep runs on its own button (one engine run per point);
    # disabled until the network runs and a sweep is declared
    sweep_button = mo.ui.run_button(label='Run sweep',
                                    disabled=builder_config is None or sweep_cfg is None)
    return (sweep_button,)


@app.cell(hide_code=True)
def _(
    Addict,
    CalcMode,
    Simulation,
    builder_config,
    mo,
    sweep_button,
    sweep_cfg,
    sweep_chart,
    sweep_run,
    switch_off,
    switched_off,
    unit_pick,
):
    # the declared sweep, run and plotted: the switched-off gates and
    # particles apply to every point, as to a run of the network
    def _():
        if not sweep_button.value or builder_config is None or sweep_cfg is None:
            return mo.md('_press **Run sweep** to run the network across the range_'
                         if sweep_cfg else '')
        CalcMode.default(
            'Symbolic' if str(builder_config.get('calculation_mode')
                              or '').lower() == 'symbolic' else 'Float')
        config = Addict({'string_precision': 2, 'max_symbolic_len': 40,
                         'loglevel': 'warning', **builder_config})
        inert, absent = switched_off(switch_off.value)
        try:
            with mo.status.spinner(title='running the sweep…'):
                res = sweep_run(Simulation(config), sweep_cfg, inert=inert, absent=absent)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**sweep failed** — `{exc}`')
        off = ''.join(f' — {what} off: {", ".join(ns)}'
                      for what, ns in (('gates', inert), ('particles', absent)) if ns)
        return mo.vstack([mo.md(f"{len(res['x'])} points{off}"),
                          sweep_chart(res, sweep_cfg, unit_pick.value == 'degrees')],
                         gap=0.3)

    sweep_view = _()
    return (sweep_view,)


@app.cell(hide_code=True)
def _(caption_input, editor_rows, mo, notes_input, sweep_button, sweep_ui, sweep_view, variables_editor):
    # all entirely optional, so they live below the canvas
    mo.accordion({'#### Caption, notes, variables, and sweep':
                  mo.vstack([
        caption_input,
        notes_input,
        mo.md('<span style="font-size: 0.9em">**variables**</span>'),
        variables_editor,
        mo.md('<span style="font-size: 0.9em">**sweep** — rerun the model across a '
              'range of one variable, recording a particle\'s arrival at a gate; a '
              'sweep on a phase plate\'s variable is a screen in the decoherence lab</span>'),
        sweep_ui.elements['on'],
        *editor_rows(sweep_ui),
        sweep_button,
        sweep_view,
    ], align='stretch')})


@app.cell(hide_code=True)
def _(builder, graph_to_config, mo, off_memory, switch_off_boxes):
    # switch off for the run: a checkbox per gate (a plain wire when
    # off) and per particle (a null input when off) — the quick way to
    # try a configuration without rewiring; the canvas crosses out
    # whatever is off
    _graph = builder.value.get('graph') or {}
    # gates in run order (the stages the translation derives), any it
    # cannot place after, by name
    try:
        _staged = [g for stage in graph_to_config(_graph, 'x')
                   .get('run_stages', {}).values() for g in stage]
    except Exception:  # noqa: BLE001 — a wiring loop: no order to speak of
        _staged = []
    _gates = [n for n, g in (_graph.get('gates') or {}).items() if g.get('kind') != 'delay']
    _gates = sorted(_gates, key=lambda n: (_staged.index(n) if n in _staged else len(_staged), n))
    _particles = list(_graph.get('particles') or {})

    switch_off = switch_off_boxes(off_memory, _gates, _particles)
    _rows = []
    if _gates:
        _rows.append(mo.hstack([mo.md('<span style="color: #000">gates on:</span>')]
                               + [switch_off.elements[f'g:{n}'] for n in _gates],
                               justify='start', align='center', wrap=True, gap=1.5))
    if _particles:
        _rows.append(mo.hstack([mo.md('<span style="color: #000">particles on:</span>')]
                               + [switch_off.elements[f'p:{n}'] for n in _particles],
                               justify='start', align='center', wrap=True, gap=1.5))
    switch_off_particles = _particles
    mo.vstack(_rows, gap=0.5) if _rows else None
    return switch_off, switch_off_particles


@app.cell(hide_code=True)
def _(builder_config, mo):
    # the Run button: disabled whenever the network cannot run — the
    # status line above says why, in red
    run_network_btn = mo.ui.run_button(label='▶ Run network',
                                       disabled=builder_config is None)
    run_network_btn  # noqa: B018 — the cell's output
    return (run_network_btn,)


@app.cell(hide_code=True)
def _(
    Addict,
    CalcMode,
    Simulation,
    builder_config,
    builder_widget,
    mo,
    run_network_btn,
    switch_off,
):
    # what is switched off: gates go inert (wires), particles absent
    # (null inputs); the canvas crosses them out as soon as they are
    _inert = [k[2:] for k, v in switch_off.value.items() if k.startswith('g:') and not v]
    _absent = [k[2:] for k, v in switch_off.value.items() if k.startswith('p:') and not v]
    builder_widget.off = _inert + _absent

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
            s = Simulation(config, inert=_inert, absent=_absent)
            s.run()
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return None, mo.md(f'**run failed** — `{exc}`')
        total = sum(float(p.probability)
                    for p in s.result_space.index.values())
        bad = s.inexact_inputs()
        note = ('' if not bad else
                '<br><span style="color: #b00020">⚠ Symbolic mode, but '
                + ', '.join(bad) + (' is' if len(bad) == 1 else ' are')
                + ' not exact (a floating-point or long decimal value), '
                'so these results carry floating point.</span>')
        off_note = ''.join(
            f' — {what} off: {", ".join(names)}'
            for what, names in (('gates', _inert), ('particles', _absent)) if names)
        return s, mo.md(
            f'Ran **{config.title}** — '
            f'{len(s.run_stages)} stage(s), '
            f'{len(s.result_space.index)} final configuration-space '
            f'point(s), total probability {total:.6f}' + off_note + note)

    sim_built, _msg = _build()
    _msg  # noqa: B018 — the cell's output
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
                      'to zoom · drag to pan · double-click or double-tap '
                      'to reset · hover over or tap a port for its '
                      'values</span>'),
                mo.ui.anywidget(DiagramWidget(
                    geometry=diagram_geometry(sim_built, has_run=True,
                                              disabled=tuple(sim_built.inert),
                                              absent=tuple(sim_built.absent)))),
            ], gap=0)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'_circuit diagram failed: {exc}_')

    _()


@app.cell(hide_code=True)
def _(NetworkGraph, NetworkGraphWidget, mo, sim_built):
    # The weight-evolution graph, as in the main app: configuration-
    # space points × stages, with the lineage interaction
    mo.stop(sim_built is None)

    def _():
        try:
            _model = NetworkGraph(sim_built.all_points, sim_built).build_model()
            return mo.vstack([
                mo.ui.anywidget(NetworkGraphWidget(model=_model)),
                mo.md('_Scroll or pinch to zoom, drag to pan, '
                      'double-click (double-tap) to reset. '
                      'Hover over (or tap) a cell for its values; '
                      'click a node to highlight its '
                      'full ancestry and descendancy (shift-click for '
                      'immediate neighbors only), click again to '
                      'clear._'),
            ])
        except Exception as exc:  # noqa: BLE001 — surface, don't crash the app
            return mo.md(f'_weight evolution graph failed: {exc}_')

    mo.accordion({'#### Weight evolution graphic (gate output '
                  'ports × stages)': _()})


@app.cell(hide_code=True)
def _(cs_point_sort_key, html_table, mo, particle_names, particle_tokens, sim_built, sym_or_float):
    mo.stop(sim_built is None)

    def _():
        rows = []
        for p in sorted(sim_built.result_space.index.values(),
                        key=lambda p: cs_point_sort_key(sim_built, p)):
            w = complex(p.weight)
            # exact forms in Symbolic mode when short, floats otherwise;
            # every number at the same fixed precision
            w_txt = sym_or_float(p.weight, f'{w.real:.3f}{w.imag:+.3f}i')
            pr_txt = sym_or_float(p.probability,
                                  f'{float(p.probability):.3f}')
            rows.append([f'`{tok}`' for _, tok in particle_tokens(sim_built, p)]
                        + [w_txt, pr_txt])
        # one column per particle under a 'configuration' heading that
        # names each; cells with markdown go through the renderer
        return mo.md(html_table(
            [('configuration', particle_names(sim_built)), ('weight', None),
             ('probability', None)], rows,
            lambda t: mo.md(t).text if any(ch in t for ch in '$`*') else t))

    _()


@app.cell(hide_code=True)
def _(builder_config, config_to_yaml, mo, raw_sections):
    mo.stop(builder_config is None)
    _yaml = config_to_yaml(builder_config, raw_sections=raw_sections)
    mo.accordion({'Model YAML': mo.md(f'```yaml\n{_yaml}```')})


if __name__ == "__main__":
    app.run()
