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
        await micropip.install(['sympy', 'scipy', 'networkx', 'pandas',
                                'altair', 'pyyaml', 'anywidget'])

    import altair as alt
    from addict import Dict as Addict

    try:
        alt.data_transformers.enable('marimo_inline_csv')
    except Exception:
        try:  # marimo registers its transformers lazily
            from marimo._plugins.ui._impl.charts.altair_transformer import (
                register_transformers)
            register_transformers()
            alt.data_transformers.enable('marimo_inline_csv')
        except Exception:  # not running under marimo at all
            alt.data_transformers.enable('default')

    _repo = Path(__file__).resolve().parents[1]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    import quantish.qnumber as qn
    from quantish.qnumber import CalcMode

    CalcMode.default('Float')
    qn.ZERO_THRESHOLD = qn.zero_threshold_fn()

    import copy
    import yaml

    from quantish.altair_diagram import diagram_geometry
    from quantish.builder import (angle_degrees, coherence_warnings,
                                  config_to_graph,
                                  config_to_yaml, graph_to_config,
                                  validate_graph)
    from quantish.builder_widget import BuilderWidget, DiagramWidget
    from quantish.display import coord_sort_key, cs_point_sort_key
    from quantish.util import angle_label
    from quantish.simulation import Simulation

    # the model library, for loading an existing model into the builder
    # (present when running from the repo; empty in the WASM build)
    _models_top = _repo / 'models'
    model_paths = {str(p.relative_to(_models_top)): p
                   for p in sorted(_models_top.rglob('*.yaml'))
                   if p.name != 'defaults.yaml'
                   and not p.name.startswith('.')} \
        if _models_top.is_dir() else {}

    return (
        Addict,
        BuilderWidget,
        angle_degrees,
        angle_label,
        Simulation,
        DiagramWidget,
        coherence_warnings,
        config_to_graph,
        config_to_yaml,
        coord_sort_key,
        copy,
        cs_point_sort_key,
        graph_to_config,
        diagram_geometry,
        mo,
        model_paths,
        validate_graph,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Quantish network builder

    Build a gate network on the canvas below, then run it with the real
    quantish engine and save it as a model YAML file.

    - The icon palette beside the canvas adds components — circuit
      elements on top, the two group kinds (run stage, diagram group)
      below the divider; hover over an icon for its name. Drag components
      anywhere. A φ plate is a pure
      phase plate: an angle-0 gate used through its control wire,
      rotating every traversing weight by $e^{i\varphi}$. A delay gate
      is a portless pass-through — wire it by its body ports like a
      particle.
    - Drag from an **output port** (right side) and drop on a free
      **input port** (left side) to wire them together.
    - Double-click a gate body to set its measurement angle (a φ
      plate: its phase) — in the model files' own syntax, radians with
      expressions: `0`, `pi/6`, `rad(30)`, `acos(4/5)`, `0.5`.
      Anything unparseable is flagged on the gate and detailed in the
      status line. Double-click a particle to flip its sign.
      Double-click a **name** to rename (a particle's prompt takes the
      sign too; a stage or group box label renames the whole group,
      and a group that exactly matches a stage shares its box). Click a component or wire and press **delete
      selected** (or the Delete key) to remove it. **↩/↪** (or ⌘Z/⇧⌘Z)
      undo and redo. Scroll (or pinch) zooms around the cursor and
      dragging empty space pans — on the canvas and the results
      diagram alike (double-click resets the diagram).
    - Shift-click (or ⌘-click) toggles an object in the selection —
      one kind at a time; clicking a different kind starts over.
      Shift-drag a box to sweep up gates. Then the palette's stage
      icon names their execution stage (drawn as a teal box) and the
      group icon their display group (a dashed box; an empty name
      clears either). Ungrouped gates get automatic stages
      derived from the wiring, and a stage may contain internal
      wiring — the engine fires it in dependency order.
    - Run stages *are* the diagram groups until you create a group
      that isn't exactly a stage — that promotes every named stage to
      a diagram group of its own, which you can then edit.
    - The **Stages & diagram groups** panel below the canvas shows the
      full assignment as editable YAML: rename, regroup, and reorder
      there, then **apply stages & groups**.
    - To modify an existing model, pick or upload one and press
      **⬆ load into builder** — it replaces the canvas; **✕ clear** (in
      the canvas toolbar) starts over empty, with a confirmation —
      and undo can bring the canvas back. The **title** (in the YAML) and the **file
      name** (of the saved file) are separate fields. Angles load as
      their numeric values; captions, variable definitions, and wire
      labels aren't carried over.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # the last model loaded into the builder: {'graph', 'title', 'notes'}
    get_loaded, set_loaded = mo.state(None)
    # a parsed load waiting for the really-replace-the-canvas step
    get_pending, set_pending = mo.state(None)
    return get_loaded, get_pending, set_loaded, set_pending


@app.cell(hide_code=True)
def _(mo, model_paths):
    model_pick = mo.ui.dropdown(options=sorted(model_paths),
                                label='start from model')
    model_upload = mo.ui.file(filetypes=['.yaml', '.yml'],
                              label='or upload a model')
    load_btn = mo.ui.run_button(label='⬆ load into builder')
    mo.hstack([model_pick, model_upload, load_btn],
              justify='start', gap=1)
    return load_btn, model_pick, model_upload


@app.cell(hide_code=True)
def _(config_to_graph, load_btn, mo, model_paths, model_pick,
      model_upload, set_pending, yaml):
    # loading replaces the canvas, so a parsed load only lands as
    # "pending" here — the next cell applies it directly when the
    # canvas is empty, and asks first when it isn't. (This cell must
    # not read the canvas itself: it would re-run when the load
    # replaces the widget, and mis-read the freshly loaded canvas as
    # one that needs another confirmation.)
    def _load():
        if not load_btn.value:
            return None
        if model_upload.contents():
            text = model_upload.contents().decode()
            source = model_upload.name()
        elif model_pick.value:
            text = model_paths[model_pick.value].read_text()
            source = model_pick.value
        else:
            return mo.md('pick a model or upload one first')
        try:
            config = yaml.safe_load(text)
            graph, notes = config_to_graph(config)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**could not load {source}** — {exc}')
        from pathlib import PurePath
        set_pending({'graph': graph, 'notes': notes,
                     'title': config.get('title') or 'my_network',
                     'file': PurePath(source).stem,
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
def _(confirm_load_btn, get_pending, keep_canvas_btn, set_loaded,
      set_pending):
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
def _(get_loaded, mo):
    # the model's title (goes into the YAML) and its file name (names
    # the saved file) are separate things
    _loaded = get_loaded()
    model_title = mo.ui.text(
        value=_loaded['title'] if _loaded else 'my_network',
        label='title')
    file_name = mo.ui.text(
        value=(_loaded or {}).get('file') or 'my_network',
        label='file name')
    _report = None
    if _loaded and _loaded.get('source'):
        _msg = f"loaded **{_loaded['source']}**"
        if _loaded['notes']:
            _msg += '\n' + '\n'.join(f'- {n}' for n in _loaded['notes'])
        _report = mo.md(_msg)
    mo.vstack(
        [mo.hstack([model_title, file_name], justify='start', gap=1)]
        + ([_report] if _report is not None else []), align='start')
    return file_name, model_title


@app.cell(hide_code=True)
def _(BuilderWidget, get_loaded, mo):
    _loaded = get_loaded()
    builder_widget = (BuilderWidget(graph=_loaded['graph']) if _loaded
                      else BuilderWidget())
    builder = mo.ui.anywidget(builder_widget)
    builder
    return builder, builder_widget


@app.cell(hide_code=True)
def _(angle_degrees, angle_label, builder, builder_widget,
      coherence_warnings, graph_to_config, mo, model_title,
      validate_graph):
    # The live translation of the canvas: either the list of problems
    # keeping it from running, or the derived model config.
    _graph = builder.value.get('graph') or {}
    problems = validate_graph(_graph)
    builder_config = None
    if not problems:
        try:
            builder_config = graph_to_config(_graph, model_title.value)
        except ValueError as exc:  # a wiring loop
            problems = [str(exc)]

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
                out[_n] = angle_label(_spec, angle_degrees(_spec), '°')
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
def _(builder, builder_config, mo):
    # The stages & groups editor: the full derived picture as editable
    # YAML. Order in the text is the order in the model (within what
    # the wiring allows); gates left out get automatic stages.
    def _spec_text():
        _graph = builder.value.get('graph') or {}
        lines = []
        if builder_config is not None:
            lines.append('run_stages:')
            for s, gs in builder_config['run_stages'].items():
                lines.append(f"  {s}: [{', '.join(gs)}]")
        else:
            stages = {}
            for n, gd in _graph.get('gates', {}).items():
                if gd.get('stage'):
                    stages.setdefault(gd['stage'], []).append(n)
            if stages:
                lines.append('run_stages:')
                lines += [f"  {s}: [{', '.join(gs)}]"
                          for s, gs in stages.items()]
        dgroups = {}
        for n, gd in _graph.get('gates', {}).items():
            if gd.get('dgroup'):
                dgroups.setdefault(gd['dgroup'], []).append(n)
        if dgroups:
            rank = {d: i for i, d in
                    enumerate(_graph.get('dgroup_order') or [])}
            lines.append('diagram_groups:')
            lines += [f"  {d}: [{', '.join(gs)}]"
                      for d, gs in sorted(dgroups.items(),
                                          key=lambda kv:
                                          (rank.get(kv[0], len(rank)),
                                           kv[0]))]
        return '\n'.join(lines) or 'run_stages:\n'

    stage_editor = mo.ui.text_area(value=_spec_text(), rows=8,
                                   full_width=True)
    apply_stages_btn = mo.ui.run_button(label='apply stages & groups')
    mo.accordion({'Stages & diagram groups': mo.vstack(
        [stage_editor, apply_stages_btn], align='start')})
    return apply_stages_btn, stage_editor


@app.cell(hide_code=True)
def _(apply_stages_btn, builder, copy, file_name, mo, model_title,
      set_loaded, stage_editor, yaml):
    # applying re-creates the canvas widget from the edited assignments
    # (positions are kept); errors show here instead
    def _apply():
        if not apply_stages_btn.value:
            return None
        try:
            spec = yaml.safe_load(stage_editor.value) or {}
            if not isinstance(spec, dict):
                raise ValueError('expected run_stages / diagram_groups '
                                 'mappings')
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**could not parse** — {exc}')
        graph = copy.deepcopy(builder.value.get('graph') or {})
        gates = graph.get('gates', {})
        errors = []
        for section, field, order_key in (
                ('run_stages', 'stage', 'stage_order'),
                ('diagram_groups', 'dgroup', 'dgroup_order')):
            entries = spec.get(section) or {}
            if not isinstance(entries, dict):
                errors.append(f'{section} must map names to gate lists')
                continue
            for gd in gates.values():
                gd.pop(field, None)
            seen = {}
            for sname, members in entries.items():
                for g in (members or []):
                    if g not in gates:
                        errors.append(f'{section}: unknown gate {g} '
                                      f'in {sname}')
                    elif g in seen:
                        errors.append(f'{section}: {g} is in both '
                                      f'{seen[g]} and {sname}')
                    else:
                        seen[g] = sname
                        gates[g][field] = str(sname)
            graph[order_key] = [str(k) for k in entries]
        if errors:
            return mo.md('\n'.join(f'- {e}' for e in errors))
        set_loaded({'graph': graph, 'notes': [],
                    'title': model_title.value,
                    'file': file_name.value,
                    'source': 'the stages & groups editor'})
        return None

    _apply()
    return


@app.cell(hide_code=True)
def _(builder_config, mo):
    run_network_btn = mo.ui.run_button(label='▶ Run network',
                                       disabled=builder_config is None)
    run_network_btn
    return (run_network_btn,)


@app.cell(hide_code=True)
def _(Addict, Simulation, builder_config, mo, run_network_btn):
    # sim_built is None until a successful run of the CURRENT network;
    # any canvas change recreates the button unpressed, clearing stale
    # results (the same staleness scheme as the main app)
    def _build():
        if not (run_network_btn.value and builder_config):
            return None, None
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
def _(builder_config, config_to_yaml, file_name, mo):
    mo.stop(builder_config is None)
    _yaml = config_to_yaml(builder_config)
    mo.vstack([
        mo.accordion({'Model YAML': mo.md(f'```yaml\n{_yaml}```')}),
        mo.download(data=_yaml.encode(),
                    filename=f'{file_name.value}.yaml',
                    label='save model YAML'),
    ], align='start')
    return


if __name__ == "__main__":
    app.run()
