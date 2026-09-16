"""Quantish Physics — marimo front-end.

Pick a model, adjust gate angles with sliders, and everything downstream
reacts: exact final configuration-space points (LaTeX weights), marginal summaries, circuit
diagrams (TikZ + Mermaid), the weight-evolution graph, Monte Carlo
sampling, and the Bell/CHSH experiment. (The four-way weight-split
explorer is its own app, notebooks/weight_split_app.py.)

Run with:  marimo edit notebooks/quantish_app.py   (or `marimo run` to serve)
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full", css_file="css/quantish_app.css")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Quantish Physics
    This [Marimo](https://marimo.io) notebook contains a simulation of the quantish universe described in Chapter 4 of
    *Good and Real: Demystifying Paradoxes from Physics to Ethics* by Gary L. Drescher (MIT Press, 2006). Included are
    simulations of Fredkin gates, complex-weighted configuration space points, and the classic
    Einstein-Podolsky-Rosen experiment.

    Several types of results are available:
    - A diagram of network topology, including results after a model is run
    - A graphical trace of how weights evolve through the running of the loaded model
    - Tables with exact numeric results from a model's run

    In addition to the basic simulation, there are:
    - a Monte Carlo simulation, in which a model is run many times, tracing a single execution path depending on the
      probabilities of outputs at each gate, and tabulated to show statistics to simulate inexact results from real-world experiments
    - a simulation of the Einstein-Podolsky-Rosen (EPR) experiment, including results for both Bell's inequality and
      the Clauser–Horne–Shimony–Holt (CHSH) inequality
    """)


@app.cell(hide_code=True)
async def _(build_stamp, stamp_html):
    # which build is this? (the site build writes public/version.json
    # beside the page; a development copy says so instead)
    stamp_html(await build_stamp())


@app.cell(hide_code=True)
def _(WASM_MODE, mo):
    _closing = (
        "**Note:** this copy runs entirely in your browser (via "
        "WebAssembly) — there is no server behind it. The model library "
        "was frozen into the page when it was built, so the models and "
        "their parameters above are fixed. Gate angles and everything "
        "below remain fully adjustable."
        if WASM_MODE else
        "The **rescan models** button will reload models that have been "
        "modified since this notebook was started.")
    mo.md(f"""
    ## Model Selection

    The default model is as simple as possible, a single Fredkin gate as shown in figure 4.4 of _Good and Real_. Follow along in the book for fuller explanations of what's happening in each figure.

    The default parameters for each model are stored in a YAML file. Models are organized into *collections*. The default set of collections is:
    - **gr2026**: models implementing the figures in Chapter 4 of the 2026 revision of *Good and Real*.
    - **gr2006**: models implementing the figures in Chapter 4 of the original 2006 edition of *Good and Real*.
    - **extra**: more models demonstrating various aspects of the quantish framework. The `extras` collection includes a model taken from `MIT AIM-1026a`, the original 1988 paper which introduced the quantish framework.

    {_closing}
    """)


@app.cell(hide_code=True)
def _(
    MODELS_TOP,
    WASM_MODE,
    qa_collection_pick,
    qa_last_models_get,
    qa_last_models_set,
    mo,
    model_label,
    qa_model_rescan,
    model_title,
    qa_model_upload,
):
    qa_model_rescan  # noqa: B018 — dependency: pressing the button re-globs the directory

    def _():
        collection = qa_collection_pick.value
        cdir = MODELS_TOP / collection
        # file name first, then the model's title — the same label as
        # in every other app's picker (screen.model_label)
        options = {model_label(p.stem, model_title(p)): p
                   for p in sorted(cdir.glob('*.yaml')) if p.stem != 'defaults'}
        _by_stem = {p.stem: lab for lab, p in options.items()}
        remembered = _by_stem.get(qa_last_models_get().get(collection))
        default = remembered if remembered in options else next(iter(options))

        def remember(p):
            if p is not None:
                qa_last_models_set({**qa_last_models_get(), collection: p.stem})

        return mo.ui.dropdown(
            options=options,
            value=default,
            label='model',
            on_change=remember,
        )

    qa_model_pick = _()
    mo.hstack([qa_collection_pick, qa_model_pick]
              + ([] if WASM_MODE else [qa_model_rescan])
              + [qa_model_upload],
              justify='start', gap=1, wrap=True)
    return (qa_model_pick,)


@app.cell(hide_code=True)
def _(
    DiagramWidget,
    build_sim,
    diagram_geometry,
    mo,
    qa_show_values,
    qa_sim,
    qa_sim_model,
):
    # The circuit diagram, always current for the model loaded above.
    # Before a run it shows wiring only, but laid out (via the shadow
    # run below) exactly as the results view; once ▶ Run has computed
    # results the values fill in, in place (the switch below toggles
    # them). Any change to the model, angles, or mode resets sim to
    # None until the next run, dropping back to the values-hidden view.
    #
    # Drawn natively (the builder's renderer over diagram_geometry) in
    # a one-size-fits-all frame: every model opens at the same natural
    # text scale, left-aligned, with wheel-zoom around the cursor, drag to
    # pan, double-click to reset, values on hover; the frame's bottom
    # edge stretches to show more without rescaling. The title and
    # caption sit above it as real markdown, emphasis intact.
    def _native():
        try:
            # A shadow run pins the layout: the pre-run diagram (and
            # the values-off view after a run) is laid out exactly as
            # the results view will be, so pressing ▶ Run — or
            # toggling show values — only fills in or clears the value
            # text, moving nothing.
            _s = qa_sim
            if _s is None:
                try:
                    _s = build_sim()
                    _s.run()
                except Exception:  # noqa: BLE001 — fall back to plain wiring
                    _s = None
            if _s is not None:
                _show = qa_sim is not None and qa_show_values.value
                return mo.ui.anywidget(DiagramWidget(
                    geometry=diagram_geometry(_s, has_run=True,
                                              show_values=_show,
                                              disabled=tuple(_s.inert),
                                              absent=tuple(_s.absent))))
            return mo.ui.anywidget(DiagramWidget(
                geometry=diagram_geometry(qa_sim_model, has_run=False,
                                          disabled=tuple(qa_sim_model.inert),
                                          absent=tuple(qa_sim_model.absent))))
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'_circuit diagram failed: {exc}_')

    _s0 = qa_sim if qa_sim is not None else qa_sim_model
    _cap = getattr(_s0, 'caption', '') or ''
    mo.vstack(
        [
            mo.md(f'**{_s0.title}**' + (f' — {_cap}' if _cap else '')),
            _native(),
            mo.md('_Scroll or pinch to zoom, drag to pan, double-click '
                  '(double-tap) to reset; drag the frame\'s bottom-right '
                  'corner to make room; after a run, hover over or tap '
                  'a port for its values._'),
        ] +
        ([mo.hstack([qa_show_values], justify='start')]
         if qa_sim is not None else []), align='stretch')


@app.cell(hide_code=True)
def _(inexact_note, mo, qa_mode_pick, qa_model_pick, qa_new_sim, qa_run_btn, qa_run_problem, qa_sim_model):
    # Gated on the button. Rather than mo.stop (whose descendants all
    # display "this cell wasn't run because an ancestor was stopped"),
    # sim is None until the button is pressed, and each results cell
    # silently renders nothing while it is.
    def _():
        try:
            run = qa_new_sim()
            run.run()
            return run
        except Exception as exc:  # noqa: BLE001 — old-format models raise all sorts
            mo.stop(True, mo.md(
                f"**{qa_model_pick.value.stem} failed to run**\n\n```\n{exc}\n```"))

    qa_sim = _() if qa_run_btn.value else None

    # Exactly one status text shows here — the run summary once the
    # model has run, the how-to before that — with the Run button
    # alongside either way, so a run swaps the words without moving
    # anything else.
    def _():
        if qa_sim is not None:
            angles = ', '.join(f'{g}={float(gate.theta.degrees):.1f}º'
                               for g, gate in qa_sim.fredkin_gates.items())
            msg = mo.md(
                f"Ran **{qa_sim.title}** ({qa_mode_pick.value} mode) — {angles}; "
                f"{len(qa_sim.run_stages)} steps, "
                f"{len(qa_sim.result_space.index)} final configuration-space point(s), "
                f"total probability "
                f"{sum(float(p.probability) for p in qa_sim.result_space.index.values()):.6f}"
                + inexact_note(qa_sim))
        else:
            msg = mo.md(
                'Once a model has been loaded and its parameters set, '
                'the `▶ Run simulation` button will execute the loaded '
                'model, with the currently-set parameters. Results '
                'displays will appear after execution is complete.')
        button = (mo.hstack([qa_run_btn, mo.md(f'<span style="color: #b00020">{qa_run_problem}</span>')],
                            justify='start', align='center', gap=1)
                  if qa_run_problem else qa_run_btn)
        derived = ([mo.md('<span style="color: #b00020">⚠ this model declares no '
                          '`run_stages`: the gates run in wiring order, one stage per '
                          'layer — ' + ' | '.join(f"{n}: {', '.join(gs)}" for n, gs
                                                  in qa_sim_model.declared_run_stages.items())
                          + '</span>')]
                   if qa_sim_model.run_stages_derived else [])
        return mo.vstack([*derived, msg, button], align='start')

    _()
    return (qa_sim,)


@app.cell(hide_code=True)
def _(mo, qa_run_problem):
    # displayed in the run-status cell above, next to whichever status
    # text applies; disabled, with the reason beside it, whenever the
    # model cannot run
    qa_run_btn = mo.ui.run_button(label='▶ Run simulation', disabled=qa_run_problem is not None)
    return (qa_run_btn,)


@app.cell(hide_code=True)
def _():
    # the switch-off choices ('g:name' / 'p:name' -> False when off),
    # remembered across model reloads, which rebuild the checkboxes
    qa_off_memory = {}
    return (qa_off_memory,)


@app.cell(hide_code=True)
def _(qa_particle_names_model, qa_switch_off):
    # why the model cannot run, or None: every particle switched off
    # means nothing enters (a model that fails to load stops the app
    # with its own message, above)
    qa_run_problem = ('every particle is switched off — nothing would enter'
                   if qa_particle_names_model and all(
                       not qa_switch_off.value.get(f'p:{p}', True) for p in qa_particle_names_model)
                   else None)
    return (qa_run_problem,)


@app.cell(hide_code=True)
def _(qa_gate_names, qa_off_memory, qa_particle_names_model, qa_plate_names_model, switch_off_boxes):
    # switch off for the run: a gate or phase plate goes inert (a plain
    # wire), a particle absent (a null input) — the quick way to try a
    # configuration without editing the model
    # a gate's box sits after its name in its slider row, so it is bare;
    # the phase plates' and particles' boxes carry their names
    qa_switch_off = switch_off_boxes(qa_off_memory, qa_gate_names + qa_plate_names_model,
                                  qa_particle_names_model,
                                  gate_label=lambda n: '' if n in qa_gate_names else n)
    return (qa_switch_off,)


@app.cell(hide_code=True)
def _(NetworkGraph, NetworkGraphWidget, mo, qa_sim):
    # The weight-evolution graph, after the Run button and behind an
    # accordion so a run doesn't reshuffle the layout above it. Drawn
    # natively from NetworkGraph.build_model(), with the lineage
    # interaction: click a configuration-space point to highlight
    # every arrow on its ancestry and descendancy.
    mo.stop(qa_sim is None)

    def _():
        try:
            _model = NetworkGraph(qa_sim.all_points, qa_sim).build_model()
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
            return mo.md(f'_network graph failed: {exc}_')

    mo.accordion({'### Weight evolution graphic '
                  '(gate output ports × stages)': _()})


@app.cell(hide_code=True)
def _(
    qa_angle_slider_elems,
    qa_angle_text_elems,
    qa_base_config,
    qa_gate_names,
    mo,
    qa_mode_pick,
    qa_particle_names_model,
    qa_plate_names_model,
    qa_switch_off,
    qa_units_pick,
    qa_variables_editor,
    qa_vars_error,
    qa_vars_problem,
):
    # The whole Model Parameters section lives in one accordion so it is
    # collapsed by default in BOTH edit and app mode (accordions are the
    # one hide-by-default mechanism that behaves identically in the two
    # modes). The UI elements inside stay fully reactive.
    _explanation = mo.md(r"""
    Each model has a set of particles, a set of gates each with a particular angle, and links that connect particles and gates. Once a model is loaded, its gate angles can be modified below. Angles can be input using the sliders, each with a range from -180º to 180º, or the text entry fields, using values in either degrees or radians, according to the radio button selector. Added specifically for the simulation of the double-slit experiment, gates have an optional _phase_ parameter, allowing a gate with a zero angle to act as a _phase plate_, but that option is not surfaced in this application.

    Calculations within models often produce very small values, and floating-point roundoff errors can compound, appreciably affecting final results. Models can be run using exact values using symbolic arithmetic. In order to take best advantage of symbolic math, input values such as gate angles should be specified symbolically (e.g., "pi/6" rather than "30.0º"). All numeric values can be in the form of expressions parsable by SymPy, such as "rad(30)", equivalent to "pi/6" arithmetic expressions such as "pi/6 + pi/8", and references to variables defined in a `variables` clause in a model's YAML specification.

    _Note:_ Symbolic math is much slower than floating-point, so model execution in Symbolic mode may take several seconds, especially for large models like the EPR setup (2026 figure 4.17, 2006 figure 4.16).
    """)

    def _():
        # each gate's row: its name with its on/off box (unchecked, the
        # gate is a plain wire for the run and its controls go gray),
        # its slider, and its text entry
        # a label column (name and box, right-aligned, so the box sits
        # against the slider and the column's slack is before the
        # name), the slider, and the entry
        rows = [mo.hstack([mo.hstack([mo.md(f'**{g}**'), qa_switch_off.elements[f'g:{g}']],
                                     justify='end', align='center', gap=0.5),
                           qa_angle_slider_elems[g], qa_angle_text_elems[g]],
                          widths=[1, 6, 1], align='center', gap=0.75)
                for g in qa_gate_names]
        # the model's caption (typically the book figure's) is Markdown
        # and passes through verbatim — no added styling
        _caption = ' '.join(str(qa_base_config.get('caption', '')).split())
        _title = (f"**{qa_base_config.title}**: {_caption}" if _caption
                  else f"**{qa_base_config.title}**")
        return mo.vstack([
            mo.md(_title),
            mo.md("Gate angles: Slider and entry track "
                  "each other; sliders are degrees (0-centered). Typed numbers "
                  "use the units selector; anything else is a symbolic radian "
                  "expression (`pi/8`, `rad(30)`, `acos(4/5)`)."),
            mo.hstack([qa_mode_pick, qa_units_pick], wrap=True, justify='start', gap=2),
            mo.vstack(rows),
            mo.md("**Switch off**: uncheck a gate (the box after its name) "
                  "to make it a plain wire that every particle passes straight "
                  "through, a particle to leave it out of the run (a null "
                  "input); the diagram grays and crosses out whatever is off."),
            *([mo.hstack([mo.md('phase plates:')]
                         + [qa_switch_off.elements[f'g:{g}'] for g in qa_plate_names_model],
                         justify='start', align='center', wrap=True, gap=1.5)]
              if qa_plate_names_model else []),
            mo.hstack([mo.md('particles:')]
                      + [qa_switch_off.elements[f'p:{p}'] for p in qa_particle_names_model],
                      justify='start', align='center', wrap=True, gap=1.5),
            mo.md("**Variables**: the model's named constants, one "
                  "`name: expression` per line (`theta_split: pi/4`); "
                  "gate angles and weights that refer to them follow."),
            qa_variables_editor,
            mo.md(f'<span style="color: #b00020">⚠ {qa_vars_error or qa_vars_problem}'
                  '</span>') if (qa_vars_error or qa_vars_problem) else mo.md(''),
        ])

    # the accordion label is markdown: the heading plus a short
    # always-visible explanation in the normal (smaller) text size
    # black text for the label comes from the app stylesheet (the
    # no-gray-text rule), not from inline styling
    mo.accordion({
        '## Custom Model Parameters\n\n<span style="font-size: 0.85em">'
        'Gate angle and '
        'calculation mode settings for the current model</span>':
            mo.vstack([_explanation, _()])})


@app.cell(hide_code=True)
def _(detailed_results, mo, qa_sim):
    mo.stop(qa_sim is None)  # nothing to show until ▶ Run
    # the detailed-results subsections (quantish.apps.results), each
    # in its own accordion under one outer one
    detailed_results(qa_sim)


@app.cell(hide_code=True)
def _(
    SAMPLER_LABELS,
    qa_mc_button,
    qa_mc_cancel,
    qa_mc_job_slot,
    qa_mc_modes,
    qa_mc_note,
    qa_mc_seed,
    qa_mc_tick_get,
    qa_mc_trials,
    qa_mc_trials_text,
    mo,
    picked_modes,
    progress_view,
    projection,
    results_view,
    sampling_explanation,
    sampling_seconds,
    qa_sim,
    trial_count,
):
    qa_mc_button      # noqa: B018 — re-render when a job starts
    qa_mc_tick_get()  # ...and on every worker chunk and at completion

    def _projection():
        chosen = picked_modes(qa_mc_modes, SAMPLER_LABELS)
        if qa_sim is None or not chosen:
            return mo.md('')
        n = trial_count(qa_mc_trials_text.value, qa_mc_trials.value)
        return projection(sampling_seconds(qa_sim, chosen, n), n)

    def _results_area():
        if qa_sim is None:
            return mo.md('_run the model first (**▶ Run simulation** '
                         'above) to have something to sample_')
        _job = qa_mc_job_slot.get('job')
        if qa_mc_note is not None:
            return qa_mc_note
        if _job is None:
            return mo.md('_press **Run Monte Carlo** to sample_')
        return progress_view(_job, qa_mc_cancel) if not _job['done'] else results_view(_job)

    mo.accordion({'## Monte Carlo Sampling\n\n<span style="font-size:0.85em">Optional sampled trials on top of the exact run above</span>':
        mo.vstack([
            sampling_explanation(),
            # the slider's count formatted here (1,000,000), not by the
            # slider's own show_value, which shows 1e6 at the top step
            mo.hstack([qa_mc_trials, mo.md(f'{int(qa_mc_trials.value):,}'), qa_mc_trials_text,
                       mo.Html('<div class="mode-boxes">' + mo.hstack(
                           [mo.md('interpretations:'),
                            *qa_mc_modes.elements.values()],
                           gap=0.75, align='center').text + '</div>'),
                       qa_mc_seed, qa_mc_button, _projection()],
                      justify='start', gap=1, wrap=True, align='center'),
            _results_area(),
        ])})


@app.cell(hide_code=True)
def _(
    SAMPLER_LABELS,
    WASM_MODE,
    qa_mc_button,
    qa_mc_job_slot,
    qa_mc_modes,
    qa_mc_seed,
    qa_mc_tick_set,
    qa_mc_trials,
    qa_mc_trials_text,
    mo,
    new_job,
    picked_modes,
    run_job,
    run_job_async,
    qa_sim,
    trial_count,
):
    # Pressing Run starts the sampling in a background thread, chunk by
    # chunk, so the app stays responsive, progress is visible, and
    # Cancel can stop it between chunks (keeping the partial tallies).
    # The display cell depends on mc_note, so it always renders after
    # this cell: the progress row appears the moment Run is pressed,
    # not at the worker's first tick.
    qa_mc_note = None
    _modes = picked_modes(qa_mc_modes, SAMPLER_LABELS) if qa_sim is not None and qa_mc_button.value else None
    if _modes == []:
        qa_mc_note = mo.md('_tick at least one interpretation to sample_')
    elif _modes:
        _prev = qa_mc_job_slot.get('job')
        if _prev is not None and not _prev['done']:
            _prev['cancel'].set()
        _job = new_job(qa_sim, trial_count(qa_mc_trials_text.value, qa_mc_trials.value), _modes)
        qa_mc_job_slot['job'] = _job
        # the worker's arguments are bound now: a rerun of this cell
        # deletes its locals, which a thread holding names would miss.
        # Under Pyodide (the WASM export) a mo.Thread is a coroutine on
        # the page's event loop, so the async run yields between chunks
        # and Cancel works there too
        mo.Thread(target=run_job_async if WASM_MODE else run_job,
                  args=(_job, int(qa_mc_seed.value), qa_mc_tick_set), daemon=True).start()
    return (qa_mc_note,)


@app.cell(hide_code=True)
def _(
    qa_epr_angle_elems,
    qa_epr_button,
    qa_epr_modes,
    EPR_SAMPLER_LABELS,
    qa_epr_trials,
    qa_epr_view,
    in_div,
    mo,
    picked_modes,
    projection,
    sampling_seconds,
    qa_sim_model,
    supports_epr,
):
    # .tight-paragraphs (css/quantish_app.css): the section's prose
    # blocks run with less space between paragraphs and lists (in_div)
    _content = mo.md(
        '_The EPR experiment needs a suitable model like the one for Figure 4.17 (fig4.17) '
        'to be loaded above._'
    ) if not supports_epr(qa_sim_model) else mo.vstack([
        in_div('tight-paragraphs', mo.md(r"""
    **What the sweep does:** it re-runs the whole circuit **nine times**,
    once per pair $(\theta_1, \theta_2)$ from the sweep angles
    $\{q_a, q_b, q_c\}$ chosen below — "measuring $p_1$ at $\theta_1$
    and $p_2$ at $\theta_2$" by overriding the measurement gates
    ($g_7 = \theta_1$, $g_8 = (Q_5{+}Q_6) - \theta_2$ on two-stage
    circuits; $g_5/g_6$ on one-stage). Each cell tabulates the conditional
    discrepancy of the two outcomes; the grid then tests **Bell**
    ($d(a,c) \le d(a,b)+d(b,c)$) and **CHSH** ($|S| \le 2$) against the
    intrinsic law $d = \sin^2(\theta_1 - \theta_2)$.

    **Exact or sampled.** With trials = 0 (the default) each cell's
    discrepancy is computed exactly from the cell's final
    configuration-space points. Setting trials > 0 runs every model chosen
    under **sampling** for that many trials per cell, and reports one
    grid and one verdict per model. A sampled discrepancy is the
    ratio of disagreements to coupled trials, so it fluctuates by about
    $\tfrac{1}{2}/\sqrt{n}$ around the model's own law; that is the
    *sampling noise*, and a verdict is called VIOLATED only when the
    excess clears three times that, *saturated* when it sits within that
    distance of the bound.
    """)),
        mo.accordion({'The sampling models': in_div('tight-paragraphs', mo.md(r"""
    Every model is random in exactly one place: the draw that makes a
    trial. Nothing else is random, and the noise in a sampled grid comes
    only from the finite number of trials.

    - **Terminal (Everett).** *One trial:* draw one final
      configuration-space point of the cell's exact run, with
      probability $\lvert w\rvert^2$, and read both detectors' outcomes
      from it. Converges to the exact grid, $\sin^2\Delta$.
      On this sweep, it violates Bell and CHSH.
    - **Pilot wave (Bohm, nonlocal).** *One trial:* start one
      configuration at the initial configuration-space point and
      advance it one stage at a time, drawing each stage's next point
      from transition probabilities fitted to the wave, so that over
      many trials the configurations are distributed as
      $\lvert w\rvert^2$ at every stage, and read the outcomes from the
      final point. Converges to the exact grid, like terminal. On this
      sweep, it violates Bell and CHSH. The transition probabilities
      at each stage depend on the whole wave, both branches, which is
      where the model is nonlocal.
    - **Local hidden variable (Bell's example).** *One trial:* draw one
      hidden angle $\lambda$ uniformly from $[0°, 180°)$ — this is the
      "hidden variable" that the source hands to both particles, and the
      model's only randomness. Each detector then reads its outcome
      *deterministically* from $\lambda$ and its own setting
      $\theta$: *upper* if $\lambda$ is within $45°$ of $\theta$
      (mod $180°$), else *lower*. No wave and no circuit are involved;
      nothing passes between the two detectors. Converges to the
      linear law $2\Delta/\pi$ of the classical grid, since the two
      readings disagree exactly when $\lambda$ falls within $\Delta$
      of one of the two boundary lines. On this sweep, it saturates —
      the Bell excess is $0$ and CHSH is $2$, up to noise.

    The last is Bell's own example (1964), in this circuit's angle
    convention (the doubled angle matches the law's period of $180°$).
    It is included because it shows what a local hidden-variable
    model looks like when run the same way as the wave samplers, cell
    by cell with the same trial count: its linear law reaches Bell's
    bound exactly, and by Bell's theorem no local model can go past
    it. The wave's $\sin^2\Delta$ lies below the line in the oblique
    cells ($0.146$ against $0.25$ at $22.5°$), and that shortfall is
    what carries the wave past the bound. The **Classical
    hidden-variable law** grid and its verdict below show the same
    saturation exactly, without sampling.
    """)),
                      'How the fig 4.17 circuit works': in_div('tight-paragraphs', mo.md(r"""
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
    """))}),
        in_div('tight-paragraphs', mo.md(r"""
    **Choosing the sweep angles.** Only differences matter — the law is
    $\sin^2(\theta_1-\theta_2)$, with period $\pi$ — so the one hard
    constraint is that the three angles be **distinct (mod π)**: equal
    angles make cells compare an angle with itself and the inequalities
    degenerate. Any distinct triple is a valid experiment; whether it
    violates the classical bounds depends on spacing. With equal
    spacing $\delta$, Bell is violated exactly when $0 < \delta < 45°$
    (largest excess at $\delta = 30°$), and the default set
    $(0°, 22.5°, 45°)$ drives CHSH to $1{+}\sqrt2 \approx 2.414$.
    A bare number below uses the units selector at the top; anything
    else is read as a symbolic radian expression (`pi/8`, `rad(30)`).

    **Note: Symbolic mode (settable above in [Custom Model Parameters](#custom-model-parameters)) multiplies the cost**: nine exact symbolic runs
    with non-special angles may take several seconds even at 0 trials.
    Values may be entered here as either symbolic or floating-point expressions.
    Computation will use the selected mode in either case.

    """)),
        mo.hstack([qa_epr_angle_elems['qa'], qa_epr_angle_elems['qb'],
                   qa_epr_angle_elems['qc']],
                  justify='start', gap=2, wrap=True),
        mo.hstack([qa_epr_trials,
                   # the slider's own readout turns to 1.0e6 at a million
                   mo.md(f'{int(qa_epr_trials.value):,}'),
                   mo.Html('<div class="mode-boxes">' + mo.hstack(
                       [mo.md('sampling (when trials > 0):'),
                        *qa_epr_modes.elements.values()],
                       gap=0.75, align='center').text + '</div>'),
                   qa_epr_button,
                   (projection(sampling_seconds(
                       qa_sim_model, picked_modes(qa_epr_modes, EPR_SAMPLER_LABELS),
                       int(qa_epr_trials.value), cells=9))
                    if qa_epr_trials.value and picked_modes(qa_epr_modes, EPR_SAMPLER_LABELS)
                    else mo.md(''))],
                  justify='start', wrap=True, align='center'),
        qa_epr_view,
    ])

    mo.accordion({'## The Einstein-Podolsky-Rosen / Bell Experiment\n\n'
                  '<span style="font-size:0.85em">Sweep the measurement '
                  'angles of an EPR-capable model and test the Bell and '
                  'CHSH inequalities</span>': _content})


@app.cell(hide_code=True)
def _(declared_sweep, mo, qa_sim_model, sweep_controls):
    # The sweep is defined here, in the UI: which variable, over what
    # range, how many points, what to record, and how to sort — seeded
    # from the loaded model's own sweep section when it has one, so the
    # editor follows a model change. A run button keeps the cost (one
    # engine run per point) explicit, as for the EPR sweep.
    qa_sweep_editor = sweep_controls(qa_sim_model.qvars, qa_sim_model.particles,
                                  qa_sim_model.gates, declared_sweep(qa_sim_model))
    qa_sweep_button = mo.ui.run_button(label='Run sweep')
    return qa_sweep_button, qa_sweep_editor


@app.cell(hide_code=True)
def _(checked_spec, qa_sim_model, qa_sweep_editor):
    # the editor's sweep, validated against the loaded model
    qa_sweep_decl, qa_sweep_problem = checked_spec(qa_sim_model, qa_sweep_editor.value)
    qa_sweep_points = qa_sweep_editor.elements['points']
    return qa_sweep_decl, qa_sweep_points, qa_sweep_problem


@app.cell(hide_code=True)
def _(
    mo,
    qa_sim_model,
    qa_sweep_button,
    sweep_chart,
    qa_sweep_decl,
    qa_sweep_points,
    qa_sweep_problem,
    sweep_run,
    sweep_table,
    qa_units_pick,
):
    def _():
        if qa_sweep_problem:
            return mo.md('<span style="color:#b00">**sweep declaration '
                         f'problem** — {qa_sweep_problem}</span>')
        if qa_sweep_decl is None:
            return None
        if not qa_sweep_button.value:
            return mo.md('_press **Run sweep** to run the model across '
                         'the range_')
        with mo.status.spinner(title='running the sweep…'):
            res = sweep_run(qa_sim_model, qa_sweep_decl, int(qa_sweep_points.value))
        degrees = qa_units_pick.value == 'degrees'
        # the chart, and the values — exact in Symbolic mode where short
        table = mo.accordion({'values': mo.md(sweep_table(res, qa_sweep_decl, degrees))},
                             lazy=True)
        return mo.vstack([sweep_chart(res, qa_sweep_decl, degrees), table])

    qa_sweep_view = _()
    return (qa_sweep_view,)


@app.cell(hide_code=True)
def _(editor_rows, mo, qa_sweep_button, qa_sweep_decl, qa_sweep_editor, qa_sweep_problem, qa_sweep_view):
    def _():
        rows = editor_rows(qa_sweep_editor)
        if qa_sweep_decl is None:
            return mo.vstack([*rows, qa_sweep_view or mo.md('')])
        spec = qa_sweep_decl
        obs, grp = spec['observe'], spec.get('group_by')
        what = (f"the probability that **{obs['particle']}** ends at "
                f"**{obs['at']}**")
        if grp:
            coord = ('sign and position' if grp['coordinate'] == 'both'
                     else grp['coordinate'])
            what += f", split by **{grp['particle']}**'s final {coord}"
        return mo.vstack([
            *rows,
            mo.md(r"""
    **What a sweep does:** it re-runs the whole circuit once per point,
    with one of the model's variables rebound to each value across the
    declared range, and records a probability from the final
    configuration-space points. The model's own gate expressions say
    how the variable enters the circuit, so the model file stays the
    single source of truth. Symbolic mode keeps every point exact (the
    values are rational fractions of the range) at a cost of several
    seconds; Float mode is quick.
    """),
            mo.md(f"`{spec['variable']}` from `{spec['from']}` to "
                  f"`{spec['to']}` in {spec['points']} points, recording {what}."),
            mo.hstack([qa_sweep_button], justify='start', wrap=True),
            qa_sweep_view,
        ])

    mo.accordion({'## Sweep\n\n<span style="font-size:0.85em">Run the '
                  'model across a range of one of its variables — as '
                  'defined here, seeded from the model\'s own sweep '
                  'section when it has one</span>': _()})


@app.cell(hide_code=True)
def _(QA_EDITOR_UI, mo):
    # the end-of-page mark (Ann's request): a small flourish so readers
    # know nothing further is loading. The editor genuinely has more
    # below (support code), so it appears in the app views only.
    mo.Html('<div style="text-align: center; color: #000; '
            'font-size: 1.6em; padding: 1.5em 0 1em;">&#8258;</div>'
            ) if not QA_EDITOR_UI else None


@app.cell(hide_code=True)
def _(QA_EDITOR_UI, mo):
    # shown in the editor only: in `marimo run` the code cells below are
    # hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Loaded Configuration Details
    """) if QA_EDITOR_UI else None


@app.cell(hide_code=True)
def _(QA_EDITOR_UI, mo, qa_model_pick, qa_sim):
    # editor-only section: hidden with its heading in `marimo run`
    mo.stop(qa_sim is None or not QA_EDITOR_UI)
    mo.accordion({str(qa_model_pick.value.stem): mo.accordion(qa_sim.__dict__, multiple=True, lazy=True)})


@app.cell(hide_code=True)
def _(QA_EDITOR_UI, mo):
    # shown in the editor only: in `marimo run` the code cells below are
    # hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Support Code
    """) if QA_EDITOR_UI else None


@app.cell(hide_code=True)
async def initialization():
    import sys
    from pathlib import Path

    import marimo as mo

    # Under Pyodide (the WASM export) the quantish package, its one
    # non-Pyodide dependency, and the model library are not on any
    # filesystem: install the bundled wheels (deps=False — micropip
    # would otherwise stall resolving marimo/sympy from PyPI in the
    # browser), load the Pyodide-shipped packages the quantish package
    # imports internally (auto-loading only covers notebook-level
    # imports), and materialize models/ into the virtual filesystem so
    # the Path-based model browsing below works unchanged.
    if sys.platform == 'emscripten':
        # dynamic import: a literal `import micropip` makes server-side
        # marimo install a mock micropip meta-path finder whose globals
        # die with the notebook session, breaking all later imports
        import importlib
        import json as _json
        micropip = importlib.import_module('micropip')
        from pyodide.http import pyfetch
        _base = str(mo.notebook_location())
        await micropip.install([
            f'{_base}/public/wheels/addict-2.4.0-py3-none-any.whl',
            f'{_base}/public/wheels/quantish-0.1.0-py3-none-any.whl',
        ], deps=False)
        await micropip.install(['sympy', 'scipy', 'networkx',
                                'pyyaml', 'anywidget'])
        _resp = await pyfetch(f'{_base}/public/models.json')
        for _rel, _text in _json.loads(await _resp.string()).items():
            _p = Path('/wasm-data/models') / _rel
            _p.parent.mkdir(parents=True, exist_ok=True)
            _p.write_text(_text)
        # Under WASM, mo.app_meta().mode reports 'edit' for BOTH export
        # modes; the page's own mount config records which one this is.
        _page = await (await pyfetch(f'{_base}/index.html')).string()
        _wasm_editor = '"mode": "edit"' in _page

    # make the repo importable no matter where marimo was launched from
    def _():
        repo = Path(__file__).resolve().parents[1]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))

    _()

    import quantish.qnumber as qn
    from quantish.apps.common import (
        MODELS_TOP,
        WASM_MODE,
        build_stamp,
        editor_ui,
        in_div,
        init_engine,
        load_config,
        parse_vars,
        stamp_html,
        switch_off_boxes,
        vars_text,
    )
    from quantish.apps.epr_ui import epr_angle_entries, epr_report
    from quantish.apps.results import detailed_results
    from quantish.apps.run import (
        angle_entries,
        angle_sliders,
        build_sim,
        model_angles,
    )
    from quantish.apps.sampling import (
        EPR_SAMPLER_LABELS,
        SAMPLER_LABELS,
        new_job,
        picked_modes,
        progress_view,
        projection,
        results_view,
        run_job,
        run_job_async,
        sampling_explanation,
        sampling_seconds,
        trial_count,
    )
    from quantish.apps.sweep_ui import (
        checked_spec,
        declared_sweep,
        editor_rows,
        sweep_chart,
        sweep_controls,
        sweep_run,
        sweep_table,
    )
    from quantish.builder_widget import (
        DiagramWidget,
        NetworkGraphWidget,
    )
    from quantish.diagram_layout import diagram_geometry
    from quantish.display import (
        inexact_note,
    )
    from quantish.epr import supports_epr
    from quantish.network_graph import NetworkGraph
    from quantish.screen import model_label, model_title

    init_engine()
    # True whenever the surrounding UI is the marimo editor (local
    # `marimo edit` or a WASM edit-mode export): editor-only sections
    # key off this
    QA_EDITOR_UI = editor_ui(_wasm_editor) if WASM_MODE else editor_ui()
    return (
        DiagramWidget,
        NetworkGraphWidget,
        QA_EDITOR_UI,
        MODELS_TOP,
        NetworkGraph,
        model_label,
        model_title,
        WASM_MODE,
        build_stamp,
        diagram_geometry,
        in_div,
        inexact_note,
        load_config,
        mo,
        parse_vars,
        qn,
        stamp_html,
        supports_epr,
        switch_off_boxes,
        checked_spec,
        declared_sweep,
        editor_rows,
        sweep_chart,
        sweep_controls,
        sweep_run,
        sweep_table,
        EPR_SAMPLER_LABELS,
        SAMPLER_LABELS,
        angle_entries,
        angle_sliders,
        build_sim,
        detailed_results,
        epr_angle_entries,
        epr_report,
        model_angles,
        new_job,
        picked_modes,
        progress_view,
        projection,
        results_view,
        run_job,
        run_job_async,
        sampling_explanation,
        sampling_seconds,
        trial_count,
        vars_text,
    )


@app.cell(hide_code=True)
def _(mo):
    qa_model_rescan = mo.ui.run_button(label='↻ rescan models')
    qa_model_upload = mo.ui.file(filetypes=['.yaml'], kind='button',
                              label='⬆ upload model')
    # per-collection selection memory, seeded with each collection's
    # designated default; a new collection falls back to first-by-name
    qa_last_collection_get, qa_last_collection_set = mo.state('gr2026')
    qa_last_models_get, qa_last_models_set = mo.state(
        {'extras': 'AIM_Figure12', 'gr2006': 'fig4.04', 'gr2026': 'fig4.04'})
    return (
        qa_last_collection_get,
        qa_last_collection_set,
        qa_last_models_get,
        qa_last_models_set,
        qa_model_rescan,
        qa_model_upload,
    )


@app.cell(hide_code=True)
def _(
    MODELS_TOP,
    qa_last_collection_set,
    qa_last_models_get,
    qa_last_models_set,
    qa_model_upload,
):
    # An uploaded YAML lands in the 'uploads' collection (under WASM
    # that is the page's virtual filesystem; from the repo it is the
    # gitignored models/uploads/) and becomes the current selection —
    # the collection and model dropdowns follow via their memory
    # state.
    def _():
        if not qa_model_upload.contents():
            return
        from pathlib import PurePath
        _name = PurePath(qa_model_upload.name()).name
        if not _name.endswith('.yaml'):
            _name += '.yaml'
        _updir = MODELS_TOP / 'uploads'
        _updir.mkdir(parents=True, exist_ok=True)
        (_updir / _name).write_bytes(qa_model_upload.contents())
        qa_last_models_set({**qa_last_models_get(),
                         'uploads': _name.removesuffix('.yaml')})
        qa_last_collection_set('uploads')

    _()


@app.cell(hide_code=True)
def _(MODELS_TOP, qa_last_collection_get, qa_last_collection_set, mo, qa_model_rescan):
    qa_model_rescan  # noqa: B018 — dependency: pressing the button re-scans the directory

    def _():
        options = sorted(d.name for d in MODELS_TOP.iterdir()
                         if d.is_dir() and d.name != 'HIDEME'
                         and not d.name.startswith('.'))
        default = qa_last_collection_get() if qa_last_collection_get() in options \
            else options[0]
        return mo.ui.dropdown(
            options=options,
            value=default,
            label='collection',
            on_change=lambda name: qa_last_collection_set(name)
            if name is not None else None,
        )

    qa_collection_pick = _()
    return (qa_collection_pick,)


@app.cell(hide_code=True)
def _(qa_angles_get, qa_base_env, build_sim, mo, qa_mode_pick, qa_model_pick, qa_model_vars, qa_switch_off):
    # Model construction is cheap and needs no ▶ Run: cells that only need
    # the loaded model (the EPR sweep) depend on sim_model; cells that show
    # run results depend on sim (gated on the button, next cell).
    def qa_new_sim():
        return build_sim(qa_model_pick.value, qa_model_vars, qa_mode_pick.value,
                         qa_angles_get(), qa_switch_off.value, qa_base_env)

    try:
        qa_sim_model = qa_new_sim()
    except Exception as exc:  # noqa: BLE001 — old-format models raise all sorts
        mo.stop(True, mo.md(
            f"**{qa_model_pick.value.stem} failed to load** — probably "
            f"an old-format model.\n\n```\n{exc}\n```"))
    return qa_new_sim, qa_sim_model


@app.cell(hide_code=True)
def _(mo, qa_sim):
    # Only shown once the model has been run (the plain wiring view is
    # all there is before that). Depending on sim recreates the switch
    # at every run, so a run always opens in the values view no matter
    # where the switch was left.
    qa_sim  # noqa: B018 — dependency: a run rebuilds the switch
    qa_show_values = mo.ui.switch(value=True, label='show values')
    return (qa_show_values,)


@app.cell(hide_code=True)
def _(load_config, mo, qa_model_pick, vars_text):
    # the model over the defaults (the standard variables underneath
    # its own); the raw model for what the file itself says
    qa_base_config, _model_raw = load_config(qa_model_pick.value)

    # the radio follows a mode the model file itself sets (a
    # case-independent string); otherwise it opens on Float
    qa_mode_pick = mo.ui.radio(
        ['Float', 'Symbolic'],
        value={'symbolic': 'Symbolic', 'float': 'Float'}.get(
            str(_model_raw.get('calculation_mode') or '').lower(),
            'Float'),
        label='math mode', inline=True)
    qa_units_pick = mo.ui.radio(['degrees', 'radians'], value='degrees',
                             label='displayed angle values are',
                             inline=True)

    # the model's own variables, editable as `name: expression` lines
    # (the builder's format); reseeded when the model changes
    qa_variables_editor = mo.ui.text_area(
        value=vars_text(_model_raw.get('variables')),
        rows=max(2, min(8, len(_model_raw.get('variables') or {}) + 1)),
        full_width=True,
        placeholder='name: expression   (e.g. theta_split: pi/4)')
    return qa_base_config, qa_mode_pick, qa_units_pick, qa_variables_editor


@app.cell(hide_code=True)
def _(parse_vars, qa_variables_editor):
    # the edited variables as a mapping; a parse problem shows under the
    # editor and the model's own definitions stand meanwhile
    qa_model_vars, qa_vars_error = parse_vars(qa_variables_editor.value)
    return qa_model_vars, qa_vars_error


@app.cell(hide_code=True)
def _(mo, model_angles, qa_model_pick, qa_model_vars):
    # ONE state for all gate angles: {gate: {'deg': float, 'expr': str|None}}.
    # marimo's state reactivity keys on the getter being referenced as a
    # global variable — a dict of per-gate states breaks the subscription
    # (the earlier bug), so everything lives under a single getter/setter.
    # Reseeded when the model or its variables change, since the
    # variables define the angles (quantish.apps.run.model_angles).
    _seed = model_angles(qa_model_pick.value, qa_model_vars)
    qa_gate_names, qa_base_env, qa_vars_problem = _seed['gates'], _seed['env'], _seed['problem']
    qa_particle_names_model, qa_plate_names_model = _seed['particles'], _seed['plates']
    qa_angles_get, qa_angles_set = mo.state(_seed['angles'])
    return (qa_angles_get, qa_angles_set, qa_base_env, qa_gate_names, qa_particle_names_model,
            qa_plate_names_model, qa_vars_problem)


@app.cell(hide_code=True)
def _(angle_sliders, qa_angles_get, qa_angles_set, qa_gate_names, qa_switch_off):
    # Sliders live in their OWN cell (and the text entries in theirs):
    # marimo never re-runs the cell that invoked a state setter, so tied
    # elements must be defined in separate cells — a text edit re-runs
    # this cell (rebuilding the sliders), a slider move re-runs the text
    # cell. Registration through mo.ui.dictionary globals keeps on_change
    # events flowing. A switched-off gate's controls are disabled.
    qa_angle_slider_elems = angle_sliders(qa_angles_get, qa_angles_set, qa_gate_names, qa_switch_off.value)
    return (qa_angle_slider_elems,)


@app.cell(hide_code=True)
def _(
    angle_entries,
    qa_angles_get,
    qa_angles_set,
    qa_base_env,
    qa_gate_names,
    qa_mode_pick,
    qa_switch_off,
    qa_units_pick,
):
    qa_angle_text_elems = angle_entries(qa_angles_get, qa_angles_set, qa_gate_names, qa_switch_off.value,
                                     qa_mode_pick.value, qa_units_pick.value, qa_base_env)
    return (qa_angle_text_elems,)


@app.cell(hide_code=True)
def _(SAMPLER_LABELS, mo):
    qa_mc_trials = mo.ui.slider(
        steps=[100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000,
               100000, 200000, 500000, 1000000],
        value=20000, label='trials', show_value=False)
    qa_mc_trials_text = mo.ui.text(value='', placeholder='custom trial count')
    # two interpretations sampling the same wave, labeled by what each
    # assumes; terminal (the faithful simulation of a real experiment)
    # is the default
    # one checkbox per interpretation, in the results' order, none
    # ticked until the user chooses
    qa_mc_modes = mo.ui.dictionary({k: mo.ui.checkbox(label=k)
                                 for k in SAMPLER_LABELS})
    qa_mc_seed = mo.ui.number(value=42, label='seed')
    qa_mc_button = mo.ui.run_button(label='Run Monte Carlo')
    qa_mc_cancel = mo.ui.run_button(label='Cancel')
    return qa_mc_button, qa_mc_cancel, qa_mc_modes, qa_mc_seed, qa_mc_trials, qa_mc_trials_text


@app.cell(hide_code=True)
def _(mo):
    # Shared, mutable job slot for the background Monte Carlo worker,
    # plus a version counter the worker bumps (it runs in a mo.Thread,
    # so state setters reach the frontend). The display cell depends
    # on the counter and re-renders as sampling progresses — no
    # polling, and results land even if the section is collapsed
    # while the job runs.
    qa_mc_job_slot = {}
    qa_mc_tick_get, qa_mc_tick_set = mo.state(0)
    return qa_mc_job_slot, qa_mc_tick_get, qa_mc_tick_set


@app.cell(hide_code=True)
def _(qa_mc_cancel, qa_mc_job_slot):
    # the Cancel button flags the running job; the worker stops at the
    # next chunk boundary and reports its partial tallies
    if qa_mc_cancel.value:
        _job = qa_mc_job_slot.get('job')
        if _job is not None and not _job['done']:
            _job['cancel'].set()


@app.cell(hide_code=True)
def _(qa_base_config, epr_angle_entries, qa_model_vars):
    # the sweep-angle entries, reseeded from the model's qa/qb/qc
    # variables when the model or its variables change
    qa_epr_angle_elems = epr_angle_entries({**qa_base_config.variables, **qa_model_vars})
    return (qa_epr_angle_elems,)


@app.cell(hide_code=True)
def _(EPR_SAMPLER_LABELS, mo):
    # Defined independently of sim/mode so a math-mode change or a Run can
    # never reset the user's chosen trial count.
    qa_epr_trials = mo.ui.slider(
        steps=[0, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000,
               500000, 1000000],
        value=0, label='trials per cell (0 = exact only)', show_value=False)
    # the models the sampled cells run under, compared side by side:
    # the wave samplers show the violation, Bell's hidden-variable
    # example sits exactly at the classical bound
    qa_epr_modes = mo.ui.dictionary({k: mo.ui.checkbox(label=k)
                                  for k in EPR_SAMPLER_LABELS})
    qa_epr_button = mo.ui.run_button(label='Run EPR experiment')
    return qa_epr_button, qa_epr_modes, qa_epr_trials


@app.cell(hide_code=True)
def _(
    EPR_SAMPLER_LABELS,
    qa_base_env,
    qa_epr_angle_elems,
    qa_epr_button,
    qa_epr_modes,
    epr_report,
    qa_epr_trials,
    mo,
    picked_modes,
    qa_sim_model,
    supports_epr,
    qa_units_pick,
):
    def _():
        if not supports_epr(qa_sim_model):
            return None
        if not qa_epr_button.value:
            return mo.md('_press **Run EPR experiment** to sweep_')
        return epr_report(qa_sim_model, qa_epr_angle_elems.value, int(qa_epr_trials.value),
                          picked_modes(qa_epr_modes, EPR_SAMPLER_LABELS),
                          qa_units_pick.value, qa_base_env)

    qa_epr_view = _()
    return (qa_epr_view,)


if __name__ == "__main__":
    app.run()
