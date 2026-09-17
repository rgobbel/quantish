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

    _repo = Path(__file__).resolve().parents[1]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    from quantish.apps.builder_ui import (
        MODE_LABELS,
        angle_labels,
        canvas_counts,
        derive_config,
        final_points_html,
        loaded_model,
        loaded_report,
        model_options,
        new_model,
        raw_sections,
        run_network,
        run_order,
        run_sweep,
        status_view,
    )
    from quantish.apps.qubits_ui import qubit_panel
    from quantish.apps.session import ModelSlot
    from quantish.apps.common import (
        build_stamp,
        in_div,
        init_engine,
        model_files,
        MODELS_TOP,
        parse_vars,
        prose,
        remember_in,
        stamp_html,
        switch_off_boxes,
        vars_text,
        WASM_MODE,
    )
    from quantish.apps.sweep_ui import editor_rows, editor_spec, sweep_controls
    from quantish.builder import config_to_yaml
    from quantish.builder_widget import (
        BuilderWidget,
        DiagramWidget,
        NetworkGraphWidget,
    )
    from quantish.diagram_layout import diagram_geometry
    from quantish.network_graph import NetworkGraph

    init_engine()
    # the model library, for loading an existing model into the
    # builder (and saving one beside them): the repo's models/
    # directory, or the frozen copy fetched above under WASM; None
    # when there is none
    nb_models_top = MODELS_TOP if MODELS_TOP.is_dir() else None
    nb_model_paths = model_files(MODELS_TOP)
    return (
        angle_labels,
        build_stamp,
        BuilderWidget,
        canvas_counts,
        config_to_yaml,
        derive_config,
        diagram_geometry,
        DiagramWidget,
        editor_rows,
        editor_spec,
        final_points_html,
        in_div,
        loaded_model,
        loaded_report,
        mo,
        MODE_LABELS,
        model_options,
        ModelSlot,
        nb_model_paths,
        nb_models_top,
        NetworkGraph,
        NetworkGraphWidget,
        new_model,
        parse_vars,
        prose,
        qubit_panel,
        raw_sections,
        remember_in,
        run_network,
        run_order,
        run_sweep,
        stamp_html,
        status_view,
        sweep_controls,
        switch_off_boxes,
        vars_text,
        WASM_MODE,
    )


@app.cell(hide_code=True)
async def _(in_div, mo, prose):
    _intro = mo.md(await prose('builder'))
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
    nb_get_loaded, nb_set_loaded = mo.state(None)
    # a parsed load waiting for the really-replace-the-canvas step
    nb_get_pending, nb_set_pending = mo.state(None)
    # which File action's controls are unfolded: 'open' | 'upload' | None
    nb_get_file_mode, nb_set_file_mode = mo.state(None)
    return (
        nb_get_file_mode,
        nb_get_loaded,
        nb_get_pending,
        nb_set_file_mode,
        nb_set_loaded,
        nb_set_pending,
    )


@app.cell(hide_code=True)
def _(mo, nb_model_paths):
    # static pieces of the File controls: the collection picker (the
    # model picker itself is rebuilt per collection below) and the
    # upload control
    collections = sorted({k.split('/')[0] for k in nb_model_paths})
    nb_collection_pick = mo.ui.dropdown(
        options=collections,
        value='gr2026' if 'gr2026' in collections
        else (collections[0] if collections else None),
        label='collection')
    nb_model_upload = mo.ui.file(filetypes=['.yaml', '.yml'],
                              label='choose a file…')
    return nb_collection_pick, nb_model_upload


@app.cell(hide_code=True)
def _(
    WASM_MODE,
    nb_builder_config,
    config_to_yaml,
    nb_file_name,
    mo,
    nb_model_paths,
    nb_sections,
    nb_suite,
):
    # the File row, in the spirit of a Mac File menu: New, Open a
    # predefined model, Upload one, Save into the local models
    # directory (running from the repo only — in the browser the
    # filesystem dies with the tab, so Download is the way out),
    # Download through the browser
    nb_new_btn = mo.ui.run_button(label='✚ new')
    nb_open_btn = mo.ui.run_button(label='📂 open…')
    nb_upload_btn = mo.ui.run_button(label='⬆ upload…')
    nb_save_btn = mo.ui.run_button(label='💾 save',
                                disabled=(nb_builder_config is None
                                          or not nb_model_paths))
    # send: the model into the `uploads` collection the quantish app and
    # the decoherence lab read (from the repo: a rescan there finds it;
    # in the browser each page has its own files, so download instead)
    nb_send_btn = mo.ui.run_button(label='⇢ send to the other sections',
                                   disabled=nb_builder_config is None)
    _download = (
        mo.download(data=config_to_yaml(nb_builder_config,
                                        raw_sections=nb_sections).encode(),
                    filename=f'{nb_file_name.value}.yaml',
                    label='download')
        if nb_builder_config is not None
        else mo.ui.run_button(label='⬇ download', disabled=True))
    mo.hstack([mo.md('**File:**'), nb_new_btn, nb_open_btn, nb_upload_btn]
              + ([] if WASM_MODE else [nb_save_btn])
              + [_download]
              + ([nb_send_btn] if nb_suite or not WASM_MODE else []),
              justify='start', gap=0.75, wrap=True)
    return nb_new_btn, nb_open_btn, nb_save_btn, nb_send_btn, nb_upload_btn


@app.cell(hide_code=True)
def _(nb_get_file_mode, nb_open_btn, nb_set_file_mode, nb_upload_btn):
    # open…/upload… unfold their controls; pressing again folds them
    def _():
        if nb_open_btn.value:
            nb_set_file_mode(None if nb_get_file_mode() == 'open' else 'open')
        elif nb_upload_btn.value:
            nb_set_file_mode(None if nb_get_file_mode() == 'upload'
                          else 'upload')

    _()


@app.cell(hide_code=True)
def _(nb_collection_pick, nb_get_file_mode, mo, model_options, nb_model_paths, nb_model_upload):
    # the unfolded controls for the chosen File action
    nb_model_pick = mo.ui.dropdown(
        options=model_options(nb_model_paths, nb_collection_pick.value), label='model')
    nb_open_go_btn = mo.ui.run_button(label='open')
    nb_upload_go_btn = mo.ui.run_button(label='open file')
    _mode = nb_get_file_mode()
    _row = None
    if _mode == 'open':
        _row = mo.hstack([nb_collection_pick, nb_model_pick, nb_open_go_btn],
                         justify='start', gap=0.75, wrap=True)
    elif _mode == 'upload':
        _row = mo.hstack([nb_model_upload, nb_upload_go_btn],
                         justify='start', gap=0.75, wrap=True)
    _row  # noqa: B018 — the cell's output
    return nb_model_pick, nb_open_go_btn, nb_upload_go_btn


@app.cell(hide_code=True)
def _(
    loaded_model,
    mo,
    nb_model_paths,
    nb_model_pick,
    nb_model_upload,
    nb_new_btn,
    new_model,
    nb_open_go_btn,
    nb_set_file_mode,
    nb_set_pending,
    nb_upload_go_btn,
):
    # every File action lands as "pending" here — the next cell applies
    # it directly when the canvas is empty, and asks first when it
    # isn't. (This cell must not read the canvas itself: it would
    # re-run when the load replaces the widget, and mis-read the
    # freshly loaded canvas as one that needs another confirmation.)
    def _load():
        if nb_new_btn.value:
            nb_set_pending(new_model())
            return None
        if nb_upload_go_btn.value and nb_model_upload.contents():
            text = nb_model_upload.contents().decode()
            source = nb_model_upload.name()
        elif nb_open_go_btn.value and nb_model_pick.value:
            text = nb_model_paths[nb_model_pick.value].read_text()
            source = nb_model_pick.value
        else:
            return None
        try:
            loaded = loaded_model(text, source)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**could not load {source}** — {exc}')
        nb_set_file_mode(None)
        nb_set_pending(loaded)
        return None

    _load()

@app.cell(hide_code=True)
def _(nb_builder, canvas_counts, nb_get_pending, mo, nb_set_loaded, nb_set_pending):
    # the really? step when a load would wipe a populated canvas; an
    # empty canvas loads straight through
    nb_confirm_load_btn = mo.ui.run_button(label='replace the canvas')
    nb_keep_canvas_btn = mo.ui.run_button(label='keep what I have')

    def _():
        _p = nb_get_pending()
        if _p is None:
            return None
        _n_g, _n_p = canvas_counts(nb_builder.value.get('graph') or {})
        if not (_n_g or _n_p):
            nb_set_pending(None)
            nb_set_loaded(_p)
            return None
        return mo.vstack([
            mo.md(f"⚠ the canvas holds {_n_g} gate(s) and {_n_p} "
                  f"particle(s) — really replace it with "
                  f"**{_p['source']}**?"),
            mo.hstack([nb_confirm_load_btn, nb_keep_canvas_btn],
                      justify='start', gap=1, wrap=True),
        ], align='start')

    _()
    return nb_confirm_load_btn, nb_keep_canvas_btn


@app.cell(hide_code=True)
def _(nb_confirm_load_btn, nb_get_pending, nb_keep_canvas_btn, nb_set_loaded, nb_set_pending):
    def _():
        _p = nb_get_pending()
        if _p is None:
            return
        if nb_confirm_load_btn.value:
            nb_set_pending(None)
            nb_set_loaded(_p)
        elif nb_keep_canvas_btn.value:
            nb_set_pending(None)

    _()


@app.cell(hide_code=True)
def _(
    nb_builder_config,
    config_to_yaml,
    nb_file_name,
    mo,
    nb_models_top,
    nb_sections,
    nb_save_btn,
):
    # save writes into the local models directory (the web deployment
    # has no server filesystem — download covers it there)
    def _():
        if not (nb_save_btn.value and nb_builder_config and nb_models_top):
            return None
        dest = nb_models_top / 'extras' / f'{nb_file_name.value}.yaml'
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(config_to_yaml(nb_builder_config,
                                           raw_sections=nb_sections))
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**could not save** — {exc}')
        return mo.md('<span style="font-size: 0.9em">saved '
                     f'**{dest}**</span>')

    _()


@app.cell(hide_code=True)
def _():
    # True when this notebook runs embedded in the suite (the suite
    # overrides it): the sent model then opens in the other tabs
    nb_suite = False
    return (nb_suite,)


@app.cell(hide_code=True)
def _(MODELS_TOP, mo, nb_send_btn, nb_slot, nb_suite):
    # send writes the slot into the shared `uploads` collection; nb_sent
    # is the slot last sent (None before any) — what the suite hands to
    # the quantish app and the lab
    def _():
        if not (nb_send_btn.value and nb_slot):
            return None, None
        try:
            dest = nb_slot.save(MODELS_TOP)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return None, mo.md(f'**could not send** — {exc}')
        if nb_suite:
            return nb_slot, mo.md('<span style="font-size: 0.9em">sent — the '
                                  '[book figures](#sec-quantish) and the '
                                  '[decoherence lab](#sec-lab) open it</span>')
        return nb_slot, mo.md('<span style="font-size: 0.9em">sent as '
                              f'**{dest}** — rescan the models in the book figures or the '
                              'decoherence lab to open it</span>')

    nb_sent, _note = _()
    _note  # noqa: B018 — the cell's output
    return (nb_sent,)


@app.cell(hide_code=True)
def _(MODE_LABELS, nb_get_loaded, loaded_report, mo, vars_text):
    # the model's whole header is editable: title (into the YAML) and
    # file name (of the saved file) are separate; caption, variables,
    # and the calculation mode ride into the YAML too
    _loaded = nb_get_loaded() or {}
    nb_model_title = mo.ui.text(
        value=_loaded.get('title') or 'my_network', label='title')
    nb_file_name = mo.ui.text(
        value=_loaded.get('file') or 'my_network', label='file name')
    # tri-state: '-' leaves the calculation mode out of the YAML
    # (the loader's defaults decide at run time)
    nb_mode_pick = mo.ui.dropdown(
        options=['-', 'Float', 'Symbolic'],
        value=MODE_LABELS[_loaded.get('symbolic')],
        label='calculation mode (default: Float)')
    # tri-state like the mode: '-' omits angle_unit from the YAML
    # (plain-number angles then read as radians)
    nb_unit_pick = mo.ui.dropdown(
        options=['-', 'radians', 'degrees'],
        value=_loaded.get('angle_unit') or '-',
        label='angle unit (default: radians)')
    nb_caption_input = mo.ui.text_area(
        value=_loaded.get('caption') or '', rows=2, full_width=True,
        placeholder='a caption to be displayed in the network diagram',
        label='**caption**')
    nb_notes_input = mo.ui.text_area(
        value=_loaded.get('model_notes') or '', rows=3, full_width=True,
        placeholder='free-form text', label='**notes**')

    nb_variables_editor = mo.ui.text_area(
        value=(_loaded.get('variables_text')
               or vars_text(_loaded.get('variables'))), rows=6,
        full_width=True,
        placeholder='variable definitions in YAML format')
    # the loaded model's unhandled sections, kept for the save — their
    # parsed values (for the config) and their raw text (for the file)
    nb_loaded_extras = _loaded.get('extras') or {}
    nb_loaded_extras_text = _loaded.get('extras_text') or {}
    _report = loaded_report(_loaded)
    mo.vstack(
        ([_report] if _report is not None else [])
        + [mo.vstack([nb_file_name,
                      mo.hstack([nb_model_title, nb_mode_pick, nb_unit_pick],
                                justify='start', gap=0.75, wrap=True)])],
        align='stretch')
    return (
        nb_caption_input,
        nb_file_name,
        nb_loaded_extras,
        nb_loaded_extras_text,
        nb_mode_pick,
        nb_model_title,
        nb_notes_input,
        nb_unit_pick,
        nb_variables_editor,
    )


@app.cell(hide_code=True)
def _(mo, parse_vars, nb_variables_editor):
    # the parsed variables mapping; parse trouble shows here, and
    # definitions the engine can't evaluate show in the status line
    nb_model_vars, _err = parse_vars(nb_variables_editor.value)
    mo.md(f'**{_err}**') if _err else None
    return (nb_model_vars,)

@app.cell(hide_code=True)
def _(BuilderWidget, nb_get_loaded, mo):
    _loaded = nb_get_loaded()
    nb_builder_widget = (BuilderWidget(graph=_loaded['graph']) if _loaded
                      else BuilderWidget())
    nb_builder = mo.ui.anywidget(nb_builder_widget)
    # the run's switch-off choices ('g:name' / 'p:name' -> False when
    # off), remembered across canvas edits, which rebuild the checkboxes
    nb_off_memory = {}
    # the sweep editor's entries, remembered the same way
    nb_sweep_memory = {}
    nb_builder  # noqa: B018 — the cell's output
    return nb_builder, nb_builder_widget, nb_off_memory, nb_sweep_memory


@app.cell(hide_code=True)
def _(
    angle_labels,
    nb_builder,
    nb_builder_widget,
    nb_caption_input,
    derive_config,
    nb_loaded_extras,
    nb_loaded_extras_text,
    nb_mode_pick,
    nb_model_title,
    ModelSlot,
    nb_model_vars,
    nb_notes_input,
    raw_sections,
    status_view,
    nb_file_name,
    nb_sweep_cfg,
    nb_switch_off,
    nb_switch_off_particles,
    nb_unit_pick,
    nb_variables_editor,
):
    # The live translation of the canvas: either the list of problems
    # keeping it from running, or the derived model config — caption,
    # notes, variables, calculation mode, angle unit, and the loaded
    # model's other sections (extras) included.
    _graph = nb_builder.value.get('graph') or {}
    nb_builder_config, problems = derive_config(
        _graph, title=nb_model_title.value, caption=nb_caption_input.value,
        model_vars=nb_model_vars, mode_label=nb_mode_pick.value,
        unit_label=nb_unit_pick.value, notes=nb_notes_input.value,
        extras=nb_loaded_extras, sweep_cfg=nb_sweep_cfg,
        all_particles_off=bool(nb_switch_off_particles) and all(
            not nb_switch_off.value.get(f'p:{p}', True) for p in nb_switch_off_particles))
    # display labels for the canvas ('pi/6 (30.0°)')
    nb_builder_widget.angle_labels = angle_labels(_graph, nb_model_vars, nb_unit_pick.value)
    # what the save writes verbatim
    nb_sections = raw_sections(nb_loaded_extras_text, nb_model_vars, nb_variables_editor.value)
    status_view(_graph, problems, nb_builder_config)
    # the model as a value the other apps take (see quantish.apps.session)
    nb_slot = (ModelSlot.from_builder(nb_builder_config, nb_sections, nb_file_name.value)
               if nb_builder_config is not None else None)
    return nb_builder_config, nb_sections, nb_slot

@app.cell(hide_code=True)
def _(nb_builder, nb_loaded_extras, nb_model_vars, sweep_controls, nb_sweep_memory):
    # the model's sweep, entered here: the variable to sweep (one of
    # the editor's), its range and point count, the particle and gate
    # whose arrival is recorded, and an optional sort. Seeded from a
    # loaded model's sweep section, remembered across rebuilds (the
    # elements are remade whenever the variables or the canvas change)
    _graph = nb_builder.value.get('graph') or {}
    _decl = nb_loaded_extras.get('sweep')
    nb_sweep_ui = sweep_controls(nb_model_vars or {}, _graph.get('particles') or {},
                              _graph.get('gates') or {},
                              _decl if isinstance(_decl, dict) else None,
                              memory=nb_sweep_memory, declare_box=True)
    return (nb_sweep_ui,)


@app.cell(hide_code=True)
def _(editor_spec, nb_sweep_ui):
    # the sweep as the model declares it (None when not declared)
    nb_sweep_cfg = editor_spec(nb_sweep_ui.value)
    return (nb_sweep_cfg,)


@app.cell(hide_code=True)
def _(nb_builder_config, mo, nb_sweep_cfg):
    # the sweep runs on its own button (one engine run per point);
    # disabled until the network runs and a sweep is declared
    nb_sweep_button = mo.ui.run_button(label='Run sweep',
                                    disabled=nb_builder_config is None or nb_sweep_cfg is None)
    return (nb_sweep_button,)


@app.cell(hide_code=True)
def _(nb_builder_config, mo, run_sweep, nb_sweep_button, nb_sweep_cfg, nb_switch_off, nb_unit_pick):
    # the declared sweep, run and plotted: the switched-off gates and
    # particles apply to every point, as to a run of the network
    nb_sweep_view = (
        run_sweep(nb_builder_config, nb_sweep_cfg, nb_switch_off.value,
                  nb_unit_pick.value == 'degrees')
        if nb_sweep_button.value else
        mo.md('_press **Run sweep** to run the network across the range_'
              if nb_sweep_cfg else ''))
    return (nb_sweep_view,)

@app.cell(hide_code=True)
def _(nb_caption_input, editor_rows, mo, nb_notes_input, nb_sweep_button, nb_sweep_ui, nb_sweep_view, nb_variables_editor):
    # all entirely optional, so they live below the canvas
    mo.accordion({'#### Caption, notes, variables, and sweep':
                  mo.vstack([
        nb_caption_input,
        nb_notes_input,
        mo.md('<span style="font-size: 0.9em">**variables**</span>'),
        nb_variables_editor,
        mo.md('<span style="font-size: 0.9em">**sweep** — rerun the model across a '
              'range of one variable, recording a particle\'s arrival at a gate; a '
              'sweep on a phase plate\'s variable is a screen in the decoherence lab</span>'),
        nb_sweep_ui.elements['on'],
        *editor_rows(nb_sweep_ui),
        nb_sweep_button,
        nb_sweep_view,
    ], align='stretch')})


@app.cell(hide_code=True)
def _(nb_builder, mo, nb_off_memory, run_order, switch_off_boxes):
    # switch off for the run: a checkbox per gate (a plain wire when
    # off) and per particle (a null input when off) — the quick way to
    # try a configuration without rewiring; the canvas crosses out
    # whatever is off
    _graph = nb_builder.value.get('graph') or {}
    _gates, _particles = run_order(_graph)

    nb_switch_off = switch_off_boxes(nb_off_memory, _gates, _particles)
    _rows = []
    if _gates:
        _rows.append(mo.hstack([mo.md('<span style="color: #000">gates on:</span>')]
                               + [nb_switch_off.elements[f'g:{n}'] for n in _gates],
                               justify='start', align='center', wrap=True, gap=1.5))
    if _particles:
        _rows.append(mo.hstack([mo.md('<span style="color: #000">particles on:</span>')]
                               + [nb_switch_off.elements[f'p:{n}'] for n in _particles],
                               justify='start', align='center', wrap=True, gap=1.5))
    nb_switch_off_particles = _particles
    mo.vstack(_rows, gap=0.5) if _rows else None
    return nb_switch_off, nb_switch_off_particles


@app.cell(hide_code=True)
def _(nb_builder_config, mo):
    # the Run button: disabled whenever the network cannot run — the
    # status line above says why, in red
    nb_run_network_btn = mo.ui.run_button(label='▶ Run network',
                                       disabled=nb_builder_config is None)
    nb_run_network_btn  # noqa: B018 — the cell's output
    return (nb_run_network_btn,)


@app.cell(hide_code=True)
def _(nb_builder_config, nb_builder_widget, run_network, nb_run_network_btn, nb_switch_off):
    # what is switched off: gates go inert (wires), particles absent
    # (null inputs); the canvas crosses them out as soon as they are
    nb_builder_widget.off = [k[2:] for k, v in nb_switch_off.value.items() if not v]

    # sim_built is None until a successful run of the CURRENT network;
    # any canvas change recreates the button unpressed, clearing stale
    # results (the same staleness scheme as the main app)
    nb_sim_built, _msg = run_network(nb_builder_config if nb_run_network_btn.value else None,
                                  nb_switch_off.value)
    _msg  # noqa: B018 — the cell's output
    return (nb_sim_built,)

@app.cell(hide_code=True)
def _(DiagramWidget, diagram_geometry, mo, nb_sim_built):
    mo.stop(nb_sim_built is None)

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
                    geometry=diagram_geometry(nb_sim_built, has_run=True,
                                              disabled=tuple(nb_sim_built.inert),
                                              absent=tuple(nb_sim_built.absent)))),
            ], gap=0)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'_circuit diagram failed: {exc}_')

    _()


@app.cell(hide_code=True)
def _(NetworkGraph, NetworkGraphWidget, mo, nb_sim_built):
    # The weight-evolution graph, as in the main app: configuration-
    # space points × stages, with the lineage interaction
    mo.stop(nb_sim_built is None)

    def _():
        try:
            _model = NetworkGraph(nb_sim_built.all_points, nb_sim_built).build_model()
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
def _(final_points_html, mo, nb_sim_built):
    mo.stop(nb_sim_built is None)
    mo.md(final_points_html(nb_sim_built))

@app.cell(hide_code=True)
async def _(mo, nb_sim_built, prose, qubit_panel):
    # the run as a qubit circuit (quantish.apps.qubits_ui); its
    # explanation is notebooks/text/qubits.md
    mo.stop(nb_sim_built is None)
    mo.accordion({'#### As a qubit circuit': qubit_panel(nb_sim_built, await prose('qubits'))})


@app.cell(hide_code=True)
def _(nb_builder_config, config_to_yaml, mo, nb_sections):
    mo.stop(nb_builder_config is None)
    _yaml = config_to_yaml(nb_builder_config, raw_sections=nb_sections)
    mo.accordion({'Model YAML': mo.md(f'```yaml\n{_yaml}```')})


if __name__ == "__main__":
    app.run()
