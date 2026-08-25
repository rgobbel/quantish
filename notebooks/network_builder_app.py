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

    from quantish.altair_diagram import circuit_chart
    from quantish.builder import (coherence_warnings, config_to_graph,
                                  config_to_yaml, graph_to_config,
                                  validate_graph)
    from quantish.builder_widget import BuilderWidget
    from quantish.display import coord_sort_key, cs_point_sort_key
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
        Simulation,
        circuit_chart,
        coherence_warnings,
        config_to_graph,
        config_to_yaml,
        coord_sort_key,
        copy,
        cs_point_sort_key,
        graph_to_config,
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

    - **+ gate**, **+ φ plate**, and **+ particle** add components; drag
      them anywhere. A φ plate is a pure phase plate: an angle-0 gate
      used through its control wire, rotating every traversing weight
      by $e^{i\varphi}$.
    - Drag from an **output port** (right side) and drop on a free
      **input port** (left side) to wire them together.
    - Double-click a gate to set its measurement angle (a φ plate: its
      phase); double-click a particle to flip its sign. Click a
      component or wire and press **delete selected** (or the Delete
      key) to remove it.
    - Shift-click gates to select several, then **stage…** names their
      execution stage and **diagram group…** their display group (an
      empty name clears it). Ungrouped gates get automatic stages
      derived from the wiring. A stage may contain internal wiring —
      the engine fires such a stage in dependency order.
    - The **Stages & diagram groups** panel below the canvas shows the
      full assignment as editable YAML: rename, regroup, and reorder
      there, then **apply stages & groups**.
    - To modify an existing model, pick or upload one and press
      **⬆ load into builder** — it replaces the canvas. Angles load as
      their numeric values; captions, variable definitions, and wire
      labels aren't carried over.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # the last model loaded into the builder: {'graph', 'title', 'notes'}
    get_loaded, set_loaded = mo.state(None)
    return get_loaded, set_loaded


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
      model_upload, set_loaded, yaml):
    # loading replaces the canvas: the widget below is re-created from
    # the loaded graph, and further edits proceed from there
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
        set_loaded({'graph': graph, 'notes': notes,
                    'title': config.get('title') or 'my_network',
                    'source': source})
        return None

    _load()
    return


@app.cell(hide_code=True)
def _(get_loaded, mo):
    _loaded = get_loaded()
    project_name = mo.ui.text(
        value=_loaded['title'] if _loaded else 'my_network',
        label='project')
    _report = None
    if _loaded:
        _msg = f"loaded **{_loaded['source']}**"
        if _loaded['notes']:
            _msg += '\n' + '\n'.join(f'- {n}' for n in _loaded['notes'])
        _report = mo.md(_msg)
    mo.vstack([x for x in (project_name, _report) if x is not None],
              align='start')
    return (project_name,)


@app.cell(hide_code=True)
def _(BuilderWidget, get_loaded, mo):
    _loaded = get_loaded()
    builder = mo.ui.anywidget(
        BuilderWidget(graph=_loaded['graph']) if _loaded
        else BuilderWidget())
    builder
    return (builder,)


@app.cell(hide_code=True)
def _(builder, coherence_warnings, graph_to_config, mo, project_name,
      validate_graph):
    # The live translation of the canvas: either the list of problems
    # keeping it from running, or the derived model config.
    _graph = builder.value.get('graph') or {}
    problems = validate_graph(_graph)
    builder_config = None
    if not problems:
        try:
            builder_config = graph_to_config(_graph, project_name.value)
        except ValueError as exc:  # a wiring loop
            problems = [str(exc)]

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
def _(apply_stages_btn, builder, copy, mo, project_name, set_loaded,
      stage_editor, yaml):
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
                    'title': project_name.value,
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
def _(circuit_chart, mo, sim_built):
    mo.stop(sim_built is None)

    def _():
        try:
            return circuit_chart(sim_built, has_run=True)
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
def _(builder_config, config_to_yaml, mo, project_name):
    mo.stop(builder_config is None)
    _yaml = config_to_yaml(builder_config)
    mo.vstack([
        mo.accordion({'Model YAML': mo.md(f'```yaml\n{_yaml}```')}),
        mo.download(data=_yaml.encode(),
                    filename=f'{project_name.value}.yaml',
                    label='save model YAML'),
    ], align='start')
    return


if __name__ == "__main__":
    app.run()
