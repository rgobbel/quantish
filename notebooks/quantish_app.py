"""Quantish Physics — marimo front-end.

Pick a model, adjust gate angles with sliders, and everything downstream
reacts: exact final configuration-space points (LaTeX weights), marginal summaries, circuit
diagrams (TikZ + Mermaid), the weight-evolution graph, Monte Carlo
sampling, the Bell/CHSH experiment, and the four-way weight-split
explorer.

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
    - a Weight-split Explorer, to show concretely the effects of various inputs to quantish Fredkin gates
    """)


@app.cell(hide_code=True)
async def build_stamp(mo, sys):
    # Which build is this? The site build (tools/build_wasm_app.sh)
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
    collection_pick,
    last_models_get,
    last_models_set,
    mo,
    model_rescan,
    model_upload,
):
    model_rescan  # noqa: B018 — dependency: pressing the button re-globs the directory

    def _():
        collection = collection_pick.value
        cdir = MODELS_TOP / collection
        options = {p.stem: p for p in sorted(cdir.glob('*.yaml'))
                   if p.stem != 'defaults'}
        remembered = last_models_get().get(collection)
        default = remembered if remembered in options else next(iter(options))

        def remember(p):
            if p is not None:
                last_models_set({**last_models_get(), collection: p.stem})

        return mo.ui.dropdown(
            options=options,
            value=default,
            label='model',
            on_change=remember,
        )

    model_pick = _()
    mo.hstack([collection_pick, model_pick]
              + ([] if WASM_MODE else [model_rescan])
              + [model_upload],
              justify='start', gap=1, wrap=True)
    return (model_pick,)


@app.cell(hide_code=True)
def _(
    DiagramWidget,
    build_sim,
    diagram_geometry,
    mo,
    show_values,
    sim,
    sim_model,
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
            _s = sim
            if _s is None:
                try:
                    _s = build_sim()
                    _s.run()
                except Exception:  # noqa: BLE001 — fall back to plain wiring
                    _s = None
            if _s is not None:
                _show = sim is not None and show_values.value
                return mo.ui.anywidget(DiagramWidget(
                    geometry=diagram_geometry(_s, has_run=True,
                                              show_values=_show)))
            return mo.ui.anywidget(DiagramWidget(
                geometry=diagram_geometry(sim_model, has_run=False)))
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'_circuit diagram failed: {exc}_')

    _s0 = sim if sim is not None else sim_model
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
        ([mo.hstack([show_values], justify='start')]
         if sim is not None else []), align='stretch')


@app.cell(hide_code=True)
def _(build_sim, inexact_note, mo, mode_pick, model_pick, run_btn):
    # Gated on the button. Rather than mo.stop (whose descendants all
    # display "this cell wasn't run because an ancestor was stopped"),
    # sim is None until the button is pressed, and each results cell
    # silently renders nothing while it is.
    def _():
        try:
            run = build_sim()
            run.run()
            return run
        except Exception as exc:  # noqa: BLE001 — old-format models raise all sorts
            mo.stop(True, mo.md(
                f"**{model_pick.value.stem} failed to run**\n\n```\n{exc}\n```"))

    sim = _() if run_btn.value else None

    # Exactly one status text shows here — the run summary once the
    # model has run, the how-to before that — with the Run button
    # alongside either way, so a run swaps the words without moving
    # anything else.
    def _():
        if sim is not None:
            angles = ', '.join(f'{g}={float(gate.theta.degrees):.1f}º'
                               for g, gate in sim.fredkin_gates.items())
            msg = mo.md(
                f"Ran **{sim.title}** ({mode_pick.value} mode) — {angles}; "
                f"{len(sim.run_stages)} steps, "
                f"{len(sim.result_space.index)} final configuration-space point(s), "
                f"total probability "
                f"{sum(float(p.probability) for p in sim.result_space.index.values()):.6f}"
                + inexact_note(sim))
        else:
            msg = mo.md(
                'Once a model has been loaded and its parameters set, '
                'the `▶ Run simulation` button will execute the loaded '
                'model, with the currently-set parameters. Results '
                'displays will appear after execution is complete.')
        return mo.vstack([msg, run_btn], align='start')

    _()
    return (sim,)


@app.cell(hide_code=True)
def _(mo):
    # displayed in the run-status cell above, next to whichever status
    # text applies
    run_btn = mo.ui.run_button(label='▶ Run simulation')
    return (run_btn,)


@app.cell(hide_code=True)
def _(NetworkGraph, NetworkGraphWidget, mo, sim):
    # The weight-evolution graph, after the Run button and behind an
    # accordion so a run doesn't reshuffle the layout above it. Drawn
    # natively from NetworkGraph.build_model(), with the lineage
    # interaction: click a configuration-space point to highlight
    # every arrow on its ancestry and descendancy.
    mo.stop(sim is None)

    def _():
        try:
            _model = NetworkGraph(sim.all_points, sim).build_model()
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
    angle_slider_elems,
    angle_text_elems,
    base_config,
    gate_names,
    mo,
    mode_pick,
    units_pick,
    variables_editor,
    vars_error,
    vars_problem,
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
        rows = [mo.hstack([angle_slider_elems[g], angle_text_elems[g]],
                          widths=[5, 1], align='center', wrap=True)
                for g in gate_names]
        # the model's caption (typically the book figure's) is Markdown
        # and passes through verbatim — no added styling
        _caption = ' '.join(str(base_config.get('caption', '')).split())
        _title = (f"**{base_config.title}**: {_caption}" if _caption
                  else f"**{base_config.title}**")
        return mo.vstack([
            mo.md(_title),
            mo.md("Gate angles: Slider and entry track "
                  "each other; sliders are degrees (0-centered). Typed numbers "
                  "use the units selector; anything else is a symbolic radian "
                  "expression (`pi/8`, `rad(30)`, `acos(4/5)`)."),
            mo.hstack([mode_pick, units_pick], wrap=True, justify='start', gap=2),
            mo.vstack(rows),
            mo.md("**Variables**: the model's named constants, one "
                  "`name: expression` per line (`theta_split: pi/4`); "
                  "gate angles and weights that refer to them follow."),
            variables_editor,
            mo.md(f'<span style="color: #b00020">⚠ {vars_error or vars_problem}'
                  '</span>') if (vars_error or vars_problem) else mo.md(''),
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
def _(
    short_label,
    GatePort,
    coord_sort_key,
    cs_point_sort_key,
    gate_io,
    html_table,
    math_prob,
    math_weight,
    md_cell,
    md_table,
    mo,
    particle_names,
    particle_tokens,
    phase_deg,
    qn,
    sim,
):
    mo.stop(sim is None)  # nothing to show until ▶ Run

    # All the detailed-results subsections live under one outer
    # accordion; each keeps its own inner accordion, so a reader can
    # open the section and then just the tables they care about.

    def _evolution_table():
        # Tabular twin of the weight-evolution graph: per stage, one row per
        # parent→child branch — the input configuration-space point and its weight, the
        # per-particle components the gate applied (cos²θ, ±i·sinθcosθ, sin²θ),
        # the branch amplitude, and the output configuration-space point's total weight. Where
        # branch w ≠ point w, interfering branches merged into that configuration-space point.
        pnames = particle_names(sim)

        def label(p):
            # one cell per particle (particle-name order), each the
            # abbreviated position; the header names the particle
            return [f'`{tok}`' for _, tok in particle_tokens(sim, p)]

        # the product sign, in a math serif so it doesn't read as a
        # gateway glyph, with the explanation on hover
        _prod = ('<span title="the product of this branch&#39;s '
                 'per-particle components, shown as one multiplier: a '
                 'merged configuration-space point stores only its '
                 'first branch&#39;s per-particle components" '
                 'style="font-family: STIXTwoMath, STIXGeneral, '
                 '\'Cambria Math\', \'Times New Roman\', serif">'
                 '∏</span>')

        def particle_cell(w, parent, contrib):
            # A merged configuration-space point stores only its FIRST branch's per-particle
            # components; for other branches show just the branch's overall
            # multiplier ∏ (recovered as branch w / input w).
            facts = {name: f for name, f in w.particles.items() if f is not None}
            try:
                expected = complex(parent.weight)
                for f in facts.values():
                    expected *= complex(f)
                stored_ok = abs(expected - complex(contrib)) < 1e-9
            except (TypeError, ValueError):
                stored_ok = True  # symbolic with free symbols: trust the stored components
            if stored_ok:
                return '<br>'.join(f'{name}: {math_weight(f)}'
                                   for name, f in facts.items()) or '—'
            try:
                return (f'{_prod}: '
                        f'{math_weight(complex(contrib) / complex(parent.weight))}')
            except (TypeError, ValueError, ZeroDivisionError):
                return f'{_prod}: ?'

        def controlled_gates(cs_point, stage):
            # per-configuration-space point positional check, as in the engine
            return [g for g in stage
                    if any(c.position.endpoint == GatePort(g, 'control')
                           for c in cs_point.coords.values())]

        def control_header(stage, parents):
            # per-gate control occupancy: source port and merged Pr, the
            # same summary the debug log's CONTROL suffix shows
            parts = []
            for g in stage:
                amp, source = None, None
                for w in parents:
                    for c in w.coords.values():
                        if c.position.endpoint == GatePort(g, 'control'):
                            amp = w.weight if amp is None else amp + w.weight
                            source = c.position.origin or c.name
                if amp is not None:
                    pr = qn.to_float(qn.probability(amp))
                    parts.append(f'`{source}` → {g}, Pr {pr:.2f}')
            return 'control: ' + (', '.join(parts) if parts else '∅')

        by_step = {}
        for pt in sim.all_points.index.values():
            by_step.setdefault(pt.step, []).append(pt)
        sections = {}
        for step in sorted(by_step):
            points = sorted(by_step[step], key=lambda p: cs_point_sort_key(sim, p))
            if step == 0:
                sections['Step 0 — initial configuration-space point'] = mo.md(html_table(
                    [('configuration-space point', pnames), ('weight $w$', None)],
                    [label(w) + [math_weight(w.weight)] for w in points], md_cell))
                continue
            stage = sim.run_stages[step - 1]
            parents = by_step.get(step - 1, [])
            rows = []
            n = len(pnames)
            for w in points:
                out_label = label(w)
                if w.canceled:
                    out_label = out_label[:-1] + [out_label[-1] + ' _(canceled)_']
                branches = sorted(w.contributions.items(),
                                  key=lambda kv: cs_point_sort_key(sim, kv[0]))
                if len(branches) == 1:
                    parent, contrib = branches[0]
                    rows.append(label(parent) + [
                                 ', '.join(controlled_gates(parent, stage)) or '∅',
                                 math_weight(parent.weight),
                                 particle_cell(w, parent, contrib),
                                 math_weight(contrib)] + out_label + [
                                 math_weight(w.weight)])
                    continue
                # a merged output: its weight belongs to the SUM of the
                # branches, not to each branch — blank the output columns
                # on branch rows and close the group with a merged row
                # showing the addition
                for parent, contrib in branches:
                    rows.append(label(parent) + [
                                 ', '.join(controlled_gates(parent, stage)) or '∅',
                                 math_weight(parent.weight),
                                 particle_cell(w, parent, contrib),
                                 math_weight(contrib), ('', n), ''])
                rows.append([('**merged**', n), '', '', '',
                             ' '.join(math_weight(c) for _, c in branches)]
                            + out_label + [math_weight(w.weight)])
            total = qn.to_float(sum(w.probability for w in points
                                    if not w.canceled))
            # md_table needs a blank line before it; its output starts
            # with one newline, so add the other after the header text
            sections[f'Step {step} — {", ".join(stage)}'] = mo.md(
                control_header(stage, parents) + '\n\n' +
                html_table([('input configuration-space point', pnames),
                            ('control', None), ('$w_{in}$', None),
                            ('particles', None), ('branch $w$', None),
                            ('output configuration-space point', pnames),
                            ('$w_{out}$', None)], rows, md_cell) +
                f'\n\ntotal probability after step: {total:.6f}')
        return mo.accordion({'### Weight evolution table (configuration-space points)':
                             mo.accordion(sections, multiple=True, lazy=True)})

    def _final_points():
        # Worlds sorted canonically: gate (in evaluation order), then port
        # (upper before lower), then sign (+ before −); the configuration
        # label's coordinates are reordered to match.
        # weights and probabilities at one fixed precision (three
        # decimals); the phase is an angle, which gets at most two
        rows = [[f'`{tok}`' for _, tok in particle_tokens(sim, p)] + [
            math_weight(p.weight, prec=3),
            math_prob(p.probability, prec=3),
            f'${phase_deg(p.weight):.2f}º$',
        ] for p in sorted(sim.result_space.index.values(),
                          key=lambda p: cs_point_sort_key(sim, p))]
        return mo.accordion({'### Final configuration-space points\n': mo.md(html_table(
            [('configuration', particle_names(sim)), ('weight $w$', None),
             (r'$\lvert w\rvert^2$', None), ('phase', None)], rows, md_cell))})

    def _marginals():
        # Marginal in the statistics sense: each row sums |w|² over every
        # final configuration-space point containing that coordinate — the chance of finding that
        # particle, with that sign, at that port, regardless of where the
        # other particles ended up. Rows follow gate evaluation order (upper
        # before lower, + before −), so a port's +/− pair sits together and
        # sums to the port's total output probability.
        acc = {}
        for p in sim.result_space.index.values():
            prob = float(p.probability)
            for coord in p.coords.values():
                entry = acc.setdefault(f'{coord.pkey}@{coord.position.origin}',
                                       [coord, 0.0])
                entry[1] += prob
        rows = [(f'`{key}`', f'{entry[1]:.4f}')
                for key, entry in sorted(acc.items(),
                                         key=lambda kv: coord_sort_key(sim, kv[1][0]))]
        return mo.accordion({
            '### Marginal probabilities (one coordinate at a time)':
                mo.md(r'Each row sums $\lvert w\rvert^2$ over every final configuration-space point '
                      'in which that particle, with that sign, sits at that '
                      'port — its probability there *regardless of where the '
                      'other particles ended up* (the marginal over the rest '
                      "of the configuration). The +/− rows at one port "
                      "together give the port's total output probability.\n" +
                      md_table(['coordinate', 'probability'], rows))
        })

    def _gate_io_table():
        # Per-step gate traffic: what arrived at each port (previous step's
        # coordinate endpoints) and what left it (that step's origins), with
        # per-sign probabilities and the aggregate Σ (|Σ|² and phase).
        rows = [(row['step'], row['gate'], row['port'],
                 row['input'].replace('\n', '<br>'),
                 row['output'].replace('\n', '<br>'))
                for row in gate_io(sim)]
        return mo.accordion({
            '### Gate inputs and outputs by step':
                mo.md(md_table(['step', 'gate', 'port', 'input', 'output'], rows))
        })

    mo.accordion({'## Detailed Results\n\n<span style="font-size:0.85em">Numerical simulation results</span>': mo.vstack([
        _evolution_table(),
        _final_points(),
        _marginals(),
        _gate_io_table(),
    ])})


@app.cell(hide_code=True)
def _(
    short_label,
    coord_sort_key,
    SAMPLER_LABELS,
    html_table,
    mc_button,
    mc_cancel,
    mc_job_slot,
    mc_modes,
    mc_seed,
    mc_tick_get,
    mc_trials,
    mc_trials_text,
    mo,
    particle_names,
    particle_tokens,
    picked_modes,
    projection,
    sampling_seconds,
    sim,
):
    mc_button      # noqa: B018 — re-render when a job starts
    mc_tick_get()  # ...and on every worker chunk and at completion
    _explanation = mo.md(r"""
    The engine always computes the whole wave: every final
    configuration-space point with its exact weight. Sampling asks what
    a **single run** of the experiment looks like. Each trial makes one
    random draw, whose rule is the interpretation; tallying many trials
    gives observed frequencies that converge on the exact probabilities
    as the trial count grows, with a spread of about $1/\sqrt{n}$ from
    the finite count — the *sampling noise*. Two interpretations of the
    same wave are offered here:

    - **Terminal (Everett).** *One trial:* one final configuration-space
      point is drawn from the evolved superposition, with probability
      $\lvert w\rvert^2$ — "which branch am I in". Converges to the
      exact probabilities. The faithful simulation of a real experiment:
      interference stays intact until the observation at the end.
    - **Pilot wave (Bohm, nonlocal).** *One trial:* one actual
      configuration starts at the initial configuration-space point
      and advances one stage at a time. At each stage its next point
      is drawn from transition probabilities fitted to the wave, so
      that over many trials the configurations are distributed as
      $\lvert w\rvert^2$ at every stage. Converges to the exact
      probabilities, the same as terminal. The difference is that a
      single trial has one definite configuration at every stage, and
      the transition probabilities at each stage depend on the whole
      wave — both branches — which is the model's nonlocality.
      (Discrete pilot-wave dynamics are not unique; this is the
      maximum-entropy coupling on the graph's edges, in the stochastic
      form of Bell 1984 / Vink 1993.)

    A third model, Bell's local hidden-variable example, samples no
    wave at all; it belongs to the EPR section below, where the
    comparison is the point.
    """)
    # .tight-list (css/quantish_app.css): the list follows its lead-in
    _explanation = mo.Html('<div class="tight-list">' + _explanation.text
                           + '</div>')

    def _projection():
        chosen = picked_modes(mc_modes, SAMPLER_LABELS)
        if sim is None or not chosen:
            return mo.md('')
        try:
            n = max(1, int(mc_trials_text.value.strip()))
        except ValueError:
            n = int(mc_trials.value)
        return projection(sampling_seconds(sim, chosen, n))

    def _progress(_job):
        pct = 100 * _job['progress'] / max(1, _job['total'])
        return mo.hstack([
            mo.Html(f'<progress value="{_job["progress"]}" '
                    f'max="{_job["total"]}" '
                    'style="width: 24em; max-width: 100%">'
                    '</progress>'),
            mo.md(f'{pct:.0f}% — {_job["progress"]:,} of '
                  f'{_job["total"]:,} draws'),
            mc_cancel,
        ], justify='start', gap=1, align='center', wrap=True)

    def _results(_job):
        if _job['error'] is not None:
            return mo.md(f'**Monte Carlo failed** — `{_job["error"]}`')
        results = _job['results']
        job_sim = _job['sim']
        pred = results['predicted']
        # compact row labels: one abbreviated position per particle, the
        # form the final-points table uses, looked up from the terminal
        # points (raw keys are unreadably long for multi-particle models)
        pnames = particle_names(job_sim)
        tokens = {p.key: [tok for _, tok in particle_tokens(job_sim, p)]
                  for p in job_sim.result_space.index.values()}
        sections = []
        if _job['cancel'].is_set():
            sections.append('_canceled — partial tallies below_')
        for label, note in (
                ('terminal', 'Everett — one draw from the final superposition per trial'),
                ('pilot', 'Bohm — one wave-guided trajectory per trial, nonlocal')):
            if label not in results:
                continue
            n_done = _job['n_done'].get(label, 0)
            if not n_done:
                continue
            tally = results[label]
            rows = []
            tvd = 0.0
            for key in sorted(set(tally) | set(pred), key=lambda k: -pred.get(k, 0)):
                freq = tally.get(key, 0) / n_done
                tvd += abs(freq - pred.get(key, 0.0))
                bare = key.split(':')[0]
                toks = tokens.get(bare, [bare[:60].replace('|', ' ')] + [''] * (len(pnames) - 1))
                rows.append([f'<code>{_esc(t)}</code>' for t in toks] + [
                             str(tally.get(key, 0)),
                             f'{freq:.4f}', f'{pred.get(key, 0.0):.4f}'])
            # an HTML table (markdown tables cannot span columns): the
            # particle columns share the 'point' heading, the two
            # frequency columns share theirs
            table = html_table([('configuration-space point', pnames),
                                ('count', None),
                                ('frequencies', ['observed', 'analytical'])],
                               rows)
            sections.append(f'**{label}** — {note}; {n_done:,} trials, '
                            f'total variation distance {tvd / 2:.4f}\n\n'
                            + table)
        return mo.md('\n\n'.join(sections))

    from html import escape as _esc

    def _results_area():
        if sim is None:
            return mo.md('_run the model first (**▶ Run simulation** '
                         'above) to have something to sample_')
        _job = mc_job_slot.get('job')
        if _job is None:
            return mo.md('_press **Run Monte Carlo** to sample_')
        return _progress(_job) if not _job['done'] else _results(_job)

    mo.accordion({'## Monte Carlo Sampling\n\n<span style="font-size:0.85em">Optional sampled trials on top of the exact run above</span>':
        mo.vstack([
            _explanation,
            mo.hstack([mc_trials, mc_trials_text,
                       mo.Html('<div class="mode-boxes">' + mo.hstack(
                           [mo.md('interpretations:'),
                            *mc_modes.elements.values()],
                           gap=0.75, align='center').text + '</div>'),
                       mc_seed, mc_button, _projection()],
                      wrap=True, align='center'),
            _results_area(),
        ])})


@app.cell(hide_code=True)
def _(
    SAMPLER_LABELS,
    mc_button,
    mc_job_slot,
    mc_modes,
    mc_seed,
    picked_modes,
    mc_tick_set,
    mc_trials,
    mc_trials_text,
    mo,
    sim,
):
    # Pressing Run starts the sampling in a background thread, chunk by
    # chunk, so the app stays responsive, progress is visible, and
    # Cancel can stop it between chunks (keeping the partial tallies).
    # Under Pyodide (the WASM export) threads cannot start, so the same
    # chunked run happens synchronously with marimo's progress bar
    # instead (no Cancel — closing the tab is the escape hatch). This
    # cell sits right after the Monte Carlo display cell so that bar
    # appears under the sampling section, not at the foot of the page.
    mo.stop(sim is None)
    if mc_button.value:
        import sys as _sys
        import threading
        import time as _time

        _prev = mc_job_slot.get('job')
        if _prev is not None and not _prev['done']:
            _prev['cancel'].set()

        try:  # the text entry, when it parses, overrides the slider
            _n = max(1, int(mc_trials_text.value.strip()))
        except ValueError:
            _n = int(mc_trials.value)
        _modes = picked_modes(mc_modes, SAMPLER_LABELS)
        mo.stop(not _modes, mo.md('_tick at least one interpretation to sample_'))
        _job = {'cancel': threading.Event(), 'done': False,
                'progress': 0, 'total': _n * len(_modes),
                'n_trials': _n, 'modes': _modes, 'sim': sim,
                'results': None, 'n_done': {}, 'error': None}
        mc_job_slot['job'] = _job

        # Everything the worker touches is bound through parameter
        # defaults: cell-local names are module globals under marimo's
        # per-cell mangling, and a rerun of this cell (any control
        # change) deletes them — a thread still holding them by name
        # would die with NameError mid-run.
        def _worker(tick=None, job=_job, job_n=_n, job_sim=sim,
                    seed=int(mc_seed.value), bump=mc_tick_set,
                    clock=_time.monotonic):
            import random
            from collections import Counter

            from quantish.montecarlo import (
                pilot_transitions,
                predicted_distribution,
                sample_pilot,
                sample_terminal,
            )
            last_bump = 0.0
            try:
                rng = random.Random(seed)
                res = {'predicted':
                       predicted_distribution(job_sim.result_space)}
                chunk_size = 2000
                done = 0
                for m in job['modes']:
                    tally = Counter()
                    remaining = job_n
                    # the pilot wave's guidance is fitted once per job
                    guidance = (pilot_transitions(job_sim.initial_points)
                                if m == 'pilot' else None)
                    while remaining and not job['cancel'].is_set():
                        k = min(chunk_size, remaining)
                        if m == 'terminal':
                            tally += sample_terminal(job_sim.result_space,
                                                     k, rng)
                        else:
                            tally += sample_pilot(job_sim.initial_points, k,
                                                  rng, transitions=guidance)
                        remaining -= k
                        done += k
                        job['progress'] = done
                        if tick is not None:
                            tick(k)
                        elif clock() - last_bump > 0.25:
                            last_bump = clock()
                            bump(lambda v: v + 1)
                    res[m] = tally
                    job['n_done'][m] = job_n - remaining
                job['results'] = res
            except Exception as exc:  # noqa: BLE001 — surface in the display
                job['error'] = repr(exc)
            finally:
                job['done'] = True
                if tick is None:
                    bump(lambda v: v + 1)  # final render, full results

        if _sys.platform == 'emscripten':
            with mo.status.progress_bar(total=_job['total'],
                                        title='sampling…') as _bar:
                _worker(tick=_bar.update)
            # the bar was this cell's output; the results cell renders
            # the tallies once the counter moves
            mo.output.clear()
            mc_tick_set(lambda v: v + 1)
        else:
            mo.Thread(target=_worker, daemon=True).start()


@app.cell(hide_code=True)
def _(
    EPR_SAMPLER_LABELS,
    epr_angle_elems,
    epr_button,
    epr_modes,
    epr_trials,
    epr_view,
    picked_modes,
    projection,
    sampling_seconds,
    mo,
    sim_model,
    supports_epr,
):
    def _tight(md):
        # .tight-paragraphs (css/quantish_app.css): the section's prose
        # blocks run with less space between paragraphs and lists
        return mo.Html('<div class="tight-paragraphs">' + md.text + '</div>')

    _content = mo.md(
        '_The EPR experiment needs a suitable model like the one for Figure 4.17 (fig4.17) '
        'to be loaded above._'
    ) if not supports_epr(sim_model) else mo.vstack([
        _tight(mo.md(r"""
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
        mo.accordion({'The sampling models': _tight(mo.md(r"""
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
                      'How the fig 4.17 circuit works': _tight(mo.md(r"""
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
        _tight(mo.md(r"""
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
        mo.hstack([epr_angle_elems['qa'], epr_angle_elems['qb'],
                   epr_angle_elems['qc']],
                  justify='start', gap=2, wrap=True),
        mo.hstack([epr_trials,
                   # the slider's own readout turns to 1.0e6 at a million
                   mo.md(f'{int(epr_trials.value):,}'),
                   mo.Html('<div class="mode-boxes">' + mo.hstack(
                       [mo.md('sampling (when trials > 0):'),
                        *epr_modes.elements.values()],
                       gap=0.75, align='center').text + '</div>'),
                   epr_button,
                   (projection(sampling_seconds(
                       sim_model, picked_modes(epr_modes, EPR_SAMPLER_LABELS),
                       int(epr_trials.value), cells=9))
                    if epr_trials.value and picked_modes(epr_modes, EPR_SAMPLER_LABELS)
                    else mo.md(''))],
                  justify='start', wrap=True, align='center'),
        epr_view,
    ])

    mo.accordion({'## The Einstein-Podolsky-Rosen / Bell Experiment\n\n'
                  '<span style="font-size:0.85em">Sweep the measurement '
                  'angles of an EPR-capable model and test the Bell and '
                  'CHSH inequalities</span>': _content})


@app.cell(hide_code=True)
def _(mo, sim_model, sweep_spec):
    # The sweep's controls, seeded from the loaded model's declaration
    # so they follow a model change. A run button keeps the cost
    # (one engine run per point) explicit, as for the EPR sweep.
    def _():
        try:
            spec = sweep_spec(sim_model)
            problem = None
        except ValueError as exc:
            spec, problem = None, str(exc)
        points = mo.ui.number(2, 401, value=(spec or {}).get('points', 41),
                              label='points')
        return spec, problem, points, mo.ui.run_button(label='Run sweep')

    sweep_decl, sweep_problem, sweep_points, sweep_button = _()
    return sweep_button, sweep_decl, sweep_points, sweep_problem


@app.cell(hide_code=True)
def _(
    LinePlotWidget,
    math,
    md_table,
    mo,
    qn,
    run_sweep,
    sim_model,
    sweep_button,
    sweep_decl,
    sweep_points,
    sweep_problem,
    sweep_values,
    sym_or_float,
    units_pick,
):
    def _():
        if sweep_problem:
            return mo.md('<span style="color:#b00">**sweep declaration '
                         f'problem** — {sweep_problem}</span>')
        if sweep_decl is None:
            return None
        if not sweep_button.value:
            return mo.md('_press **Run sweep** to run the model across '
                         'the range_')
        spec = sweep_decl
        with mo.status.spinner(title='running the sweep…'):
            res = run_sweep(sim_model, spec,
                            values=sweep_values(spec, int(sweep_points.value)))
        degrees = units_pick.value == 'degrees'
        xs = [math.degrees(qn.to_float(x)) if degrees else qn.to_float(x)
              for x in res['x']]
        var, obs, grp = spec['variable'], spec['observe'], spec.get('group_by')
        # series names carry the grouping particle ('p2 +', 'p2 −')
        # series names carry the grouping particle, sign first ('+p2')
        names = {lab: f"{lab}{grp['particle']}" if grp else lab
                 for lab in res['series']}
        palette = ['#4c78a8', '#f58518', '#54a24b', '#e45756', '#72b7b2',
                   '#b279a2', '#ff9da6', '#9d755d']
        series = [{'name': names[lab], 'x': xs,
                   'y': [qn.to_float(v) for v in ys],
                   'color': palette[i % len(palette)]}
                  for i, (lab, ys) in enumerate(res['series'].items())]
        if grp:
            series.append({'name': 'total', 'x': xs,
                           'y': [qn.to_float(v) for v in res['total']],
                           'color': '#333', 'dash': '6 4'})
        chart = mo.ui.anywidget(LinePlotWidget(data={
            'series': series, 'xdomain': [min(xs), max(xs)],
            'xlabel': f'{var} ({"degrees" if degrees else "radians"})',
            'ylabel': f"P({obs['particle']} at {obs['at']})",
            'width': 900, 'height': 220}))
        # the values, exact in Symbolic mode where short
        headers = [var] + [names[lab] for lab in res['series']] \
            + (['total'] if grp else [])
        rows = []
        for i, x in enumerate(xs):
            cells = [f'{x:.2f}'] + [
                sym_or_float(res['series'][lab][i],
                             f"{qn.to_float(res['series'][lab][i]):.4f}")
                for lab in res['series']]
            if grp:
                cells.append(sym_or_float(res['total'][i],
                                          f"{qn.to_float(res['total'][i]):.4f}"))
            rows.append(cells)
        table = mo.accordion({'values': mo.md(md_table(headers, rows))},
                             lazy=True)
        return mo.vstack([chart, table])

    sweep_view = _()
    return (sweep_view,)


@app.cell(hide_code=True)
def _(mo, sweep_button, sweep_decl, sweep_points, sweep_problem, sweep_view):
    def _():
        if sweep_decl is None and not sweep_problem:
            return mo.md('_The loaded model declares no sweep. A model may '
                         'declare one in its `sweep` section — see the '
                         'double-slit models under **extras**, where the '
                         'sweep is the screen: the pixel phase across one '
                         'fringe period._')
        if sweep_decl is None:
            return sweep_view
        spec = sweep_decl
        obs, grp = spec['observe'], spec.get('group_by')
        what = (f"the probability that **{obs['particle']}** ends at "
                f"**{obs['at']}**")
        if grp:
            coord = ('sign and position' if grp['coordinate'] == 'both'
                     else grp['coordinate'])
            what += f", split by **{grp['particle']}**'s final {coord}"
        return mo.vstack([
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
            mo.md(f"**{spec.get('title', 'declared sweep')}** — "
                  f"`{spec['variable']}` from `{spec['from']}` to "
                  f"`{spec['to']}`, recording {what}."),
            mo.hstack([sweep_points, sweep_button], justify='start',
                      wrap=True),
            sweep_view,
        ])

    mo.accordion({'## Sweep\n\n<span style="font-size:0.85em">Run the '
                  'model across a range of one variable — for models '
                  'that declare a sweep, such as the double-slit '
                  'circuits</span>': _()})


@app.cell(hide_code=True)
def _(mo, ws_components, ws_sign, ws_theta, ws_view, ws_wmag, ws_wphase):
    mo.accordion({'## Weight-split Explorer\n\n'
                  '<span style="font-size:0.85em">An interactive tool '
                  'showing what happens to weights going through a '
                  'Fredkin gate</span>': mo.vstack([
        mo.md(r"""
    This tool demonstrates the four-way split of one Fredkin gate measurement at angle $\theta$:
    $c_{2a} = w\cos^2\theta$, $c_{2b} = i\,w\sin\theta\cos\theta$
    (straight), $c_{3a} = w\sin^2\theta$,
    $c_{3b} = -i\,w\sin\theta\cos\theta$ (cross); $c_2 = c_{2a}+c_{2b}$,
    $c_3 = c_{3a}+c_{3b}$. A minus-sign particle swaps the roles.

    **Note:** Individual components can be selected by clicking on either their vectors on the chart or their entry in the legend. Shift-click toggles a component's selected state. Drag the chart's bottom-right corner to resize it; double-click the chart to reset the zoom.
    """),
        mo.hstack([ws_theta, ws_sign, ws_wmag, ws_wphase, ws_components],
                  wrap=True),
        ws_view,
    ])})


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    # the end-of-page mark (Ann's request): a small flourish so readers
    # know nothing further is loading. The editor genuinely has more
    # below (support code), so it appears in the app views only.
    mo.Html('<div style="text-align: center; color: #000; '
            'font-size: 1.6em; padding: 1.5em 0 1em;">&#8258;</div>'
            ) if not EDITOR_UI else None


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    # shown in the editor only: in `marimo run` the code cells below are
    # hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Loaded Configuration Details
    """) if EDITOR_UI else None


@app.cell(hide_code=True)
def _(EDITOR_UI, mo, model_pick, sim):
    # editor-only section: hidden with its heading in `marimo run`
    mo.stop(sim is None or not EDITOR_UI)
    mo.accordion({str(model_pick.value.stem): mo.accordion(sim.__dict__, multiple=True, lazy=True)})


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    # shown in the editor only: in `marimo run` the code cells below are
    # hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Support Code
    """) if EDITOR_UI else None


@app.cell(hide_code=True)
async def initialization():
    import cmath
    import logging
    import math
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

    import yaml
    from addict import Dict as Addict

    # make the repo importable no matter where marimo was launched from
    def _():
        repo = Path(__file__).resolve().parents[1]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))

    _()

    import quantish.qnumber as qn
    from quantish.qnumber import CalcMode

    CalcMode.default('Float')
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('quantish').setLevel(logging.WARNING)

    from quantish.builder_widget import (
        DiagramWidget,
        LinePlotWidget,
        NetworkGraphWidget,
        WeightSplitWidget,
    )
    from quantish.config_space import GatePort
    from quantish.diagram_layout import diagram_geometry
    from quantish.display import (
        coord_sort_key,
        cs_point_sort_key,
        gate_io,
        html_table,
        particle_names,
        particle_tokens,
        short_label,
        sym_or_float,
    )
    from quantish.epr import run_epr_experiment, supports_epr, verdict, verdict_slack
    from quantish.gate import FredkinGate
    from quantish.network_graph import NetworkGraph
    from quantish.simulation import Simulation
    from quantish.sweep import run_sweep, sweep_spec, sweep_values

    REPO_DIR = Path(__file__).resolve().parents[1]
    WASM_MODE = sys.platform == 'emscripten'
    # True whenever the surrounding UI is the marimo editor (local
    # `marimo edit` or a WASM edit-mode export): editor-only sections
    # key off this
    EDITOR_UI = (_wasm_editor if WASM_MODE
                 else mo.app_meta().mode == 'edit')
    MODELS_TOP = (Path('/wasm-data/models') if WASM_MODE
                  else REPO_DIR / 'models')
    return (
        Addict,
        CalcMode,
        DiagramWidget,
        LinePlotWidget,
        NetworkGraphWidget,
        EDITOR_UI,
        FredkinGate,
        GatePort,
        MODELS_TOP,
        NetworkGraph,
        Simulation,
        WASM_MODE,
        WeightSplitWidget,
        cmath,
        coord_sort_key,
        cs_point_sort_key,
        diagram_geometry,
        gate_io,
        html_table,
        math,
        mo,
        particle_names,
        particle_tokens,
        qn,
        run_epr_experiment,
        run_sweep,
        short_label,
        supports_epr,
        sweep_spec,
        sweep_values,
        sym_or_float,
        verdict,
        verdict_slack,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    model_rescan = mo.ui.run_button(label='↻ rescan models')
    model_upload = mo.ui.file(filetypes=['.yaml'], kind='button',
                              label='⬆ upload model')
    # per-collection selection memory, seeded with each collection's
    # designated default; a new collection falls back to first-by-name
    last_collection_get, last_collection_set = mo.state('gr2026')
    last_models_get, last_models_set = mo.state(
        {'extras': 'AIM_Figure12', 'gr2006': 'fig4.04', 'gr2026': 'fig4.04'})
    return (
        last_collection_get,
        last_collection_set,
        last_models_get,
        last_models_set,
        model_rescan,
        model_upload,
    )


@app.cell(hide_code=True)
def _(
    MODELS_TOP,
    last_collection_set,
    last_models_get,
    last_models_set,
    model_upload,
):
    # An uploaded YAML lands in the 'uploads' collection (under WASM
    # that is the page's virtual filesystem; from the repo it is the
    # gitignored models/uploads/) and becomes the current selection —
    # the collection and model dropdowns follow via their memory
    # state.
    def _():
        if not model_upload.contents():
            return
        from pathlib import PurePath
        _name = PurePath(model_upload.name()).name
        if not _name.endswith('.yaml'):
            _name += '.yaml'
        _updir = MODELS_TOP / 'uploads'
        _updir.mkdir(parents=True, exist_ok=True)
        (_updir / _name).write_bytes(model_upload.contents())
        last_models_set({**last_models_get(),
                         'uploads': _name.removesuffix('.yaml')})
        last_collection_set('uploads')

    _()


@app.cell(hide_code=True)
def _(MODELS_TOP, last_collection_get, last_collection_set, mo, model_rescan):
    model_rescan  # noqa: B018 — dependency: pressing the button re-scans the directory

    def _():
        options = sorted(d.name for d in MODELS_TOP.iterdir()
                         if d.is_dir() and d.name != 'HIDEME'
                         and not d.name.startswith('.'))
        default = last_collection_get() if last_collection_get() in options \
            else options[0]
        return mo.ui.dropdown(
            options=options,
            value=default,
            label='collection',
            on_change=lambda name: last_collection_set(name)
            if name is not None else None,
        )

    collection_pick = _()
    return (collection_pick,)


@app.cell(hide_code=True)
def _(
    CalcMode,
    Simulation,
    angles_get,
    base_env,
    gate_names,
    load_config,
    math,
    mo,
    mode_pick,
    model_pick,
    model_vars,
    qn,
):
    # Model construction is cheap and needs no ▶ Run: cells that only need
    # the loaded model (the EPR sweep) depend on sim_model; cells that show
    # run results depend on sim (gated on the button, next cell).
    def build_sim():
        def angle_for(g):
            cur = angles_get()[g]
            if cur['expr']:
                # keep the expression a STRING: the Simulation loader
                # qifies it against the model's variables, so names like
                # theta1 stay live and the EPR sweep's variable rebinding
                # (run_pair) still has something to rebind. Qifying here
                # would freeze the current value into the gate.
                qn.qify(cur['expr'], base_env)  # validate early, clear error
                return cur['expr']
            if mode_pick.value == 'Symbolic':
                # a degree-marked spec stays exact (30.0° → pi/6); a
                # float in radians would turn every result into a
                # sympy Float and the displays into 15-digit decimals
                return f"{cur['deg']}°"
            return math.radians(cur['deg'])

        CalcMode.default(mode_pick.value)
        config = load_config(model_pick.value)[0]
        config.variables.update(model_vars)
        for g in gate_names:
            config.gates[g].angle = angle_for(g)
        return Simulation(config)

    try:
        sim_model = build_sim()
    except Exception as exc:  # noqa: BLE001 — old-format models raise all sorts
        mo.stop(True, mo.md(
            f"**{model_pick.value.stem} failed to load** — probably "
            f"an old-format model.\n\n```\n{exc}\n```"))
    return build_sim, sim_model


@app.cell(hide_code=True)
def _(mo, sim):
    # Only shown once the model has been run (the plain wiring view is
    # all there is before that). Depending on sim recreates the switch
    # at every run, so a run always opens in the values view no matter
    # where the switch was left.
    sim  # noqa: B018 — dependency: a run rebuilds the switch
    show_values = mo.ui.switch(value=True, label='show values')
    return (show_values,)


@app.cell(hide_code=True)
def _(Addict, MODELS_TOP, Simulation, mo, model_pick, yaml):
    def load_config(path):
        with open(MODELS_TOP / 'defaults.yaml') as f:
            cfg = yaml.safe_load(f)
        with open(path) as f:
            model = yaml.safe_load(f)
        # variables merge deeply: the defaults' standard names (zero,
        # one, eye) stay available underneath the model's own
        default_vars = dict(cfg.get('variables') or {})
        cfg.update(model)
        if default_vars:
            cfg['variables'] = {**default_vars,
                                **(model.get('variables') or {})}
        cfg['loglevel'] = 'warning'
        return Addict(cfg), model

    base_config, _model_raw = load_config(model_pick.value)

    # the radio follows a mode the model file itself sets (a
    # case-independent string); otherwise it opens on Float
    mode_pick = mo.ui.radio(
        ['Float', 'Symbolic'],
        value={'symbolic': 'Symbolic', 'float': 'Float'}.get(
            str(_model_raw.get('calculation_mode') or '').lower(),
            'Float'),
        label='math mode', inline=True)
    units_pick = mo.ui.radio(['degrees', 'radians'], value='degrees',
                             label='displayed angle values are',
                             inline=True)

    # the model's own variables, editable as `name: expression` lines
    # (the builder's format); reseeded when the model changes
    def _vars_text(vs):
        return '\n'.join(
            f"{k}: '{v}'" if isinstance(v, str) else f'{k}: {v}'
            for k, v in (vs or {}).items())

    variables_editor = mo.ui.text_area(
        value=_vars_text(_model_raw.get('variables')),
        rows=max(2, min(8, len(_model_raw.get('variables') or {}) + 1)),
        full_width=True,
        placeholder='name: expression   (e.g. theta_split: pi/4)')
    return (
        base_config,
        load_config,
        mode_pick,
        units_pick,
        variables_editor,
    )


@app.cell(hide_code=True)
def _(mo, variables_editor, yaml):
    # the edited variables as a mapping; a parse problem shows under the
    # editor and the model's own definitions stand meanwhile
    def _():
        text = variables_editor.value.strip()
        if not text:
            return {}, None
        try:
            v = yaml.safe_load(text)
            if v is None:
                return {}, None
            if not isinstance(v, dict):
                raise TypeError('expected name: expression lines')
            return {str(k): val for k, val in v.items()}, None
        except Exception as exc:  # noqa: BLE001 — show, don't crash
            return {}, f'variables not parseable — {exc}'

    model_vars, vars_error = _()
    return model_vars, vars_error


@app.cell(hide_code=True)
def _(Simulation, base_config, load_config, mo, model_pick, model_vars):
    # ONE state for all gate angles: {gate: {'deg': float, 'expr': str|None}}.
    # marimo's state reactivity keys on the getter being referenced as a
    # global variable — a dict of per-gate states breaks the subscription
    # (the earlier bug), so everything lives under a single getter/setter.
    # 'expr' preserves the symbolic form (model YAML or typed) alongside
    # its numeric degree equivalent. Reseeded when the model or its
    # variables change, since the variables define the angles.
    def _():
        def centered(deg):
            d = deg % 360.0
            return d - 360.0 if d > 180.0 else d

        def spec_expr(g):
            # Only a genuinely symbolic string spec is worth carrying
            # verbatim; numeric and degree-marked specs are represented
            # by 'deg' (whose value came through the Simulation, so
            # angle_unit and degree marks are already applied).
            spec = base_config.gates[g].angle
            if not isinstance(spec, str):
                return None
            s = spec.strip()
            if s and s[-1] in '°º˚':
                return None
            try:
                float(s)
                return None
            except ValueError:
                return s

        config = load_config(model_pick.value)[0]
        config.variables.update(model_vars)
        problem = None
        try:
            base_sim = Simulation(config)
        except Exception as exc:  # noqa: BLE001 — bad variable definitions
            problem = f'variables rejected — {exc}'
            base_sim = Simulation(load_config(model_pick.value)[0])
        names = list(base_sim.fredkin_gates.keys())
        angles = mo.state({
            g: {'deg': round(centered(float(gate.theta.degrees)) * 2) / 2,
                'expr': spec_expr(g)}
            for g, gate in base_sim.fredkin_gates.items()})
        # the model's variables, so typed expressions can use them by name
        return names, angles, dict(base_sim.qvars), problem

    gate_names, (angles_get, angles_set), base_env, vars_problem = _()
    return angles_get, angles_set, base_env, gate_names, vars_problem


@app.cell(hide_code=True)
def _(angles_get, angles_set, gate_names, mo):
    # Sliders live in their OWN cell (and the text entries in theirs):
    # marimo never re-runs the cell that invoked a state setter, so tied
    # elements must be defined in separate cells — a text edit re-runs
    # this cell (rebuilding the sliders), a slider move re-runs the text
    # cell. Registration through mo.ui.dictionary globals keeps on_change
    # events flowing.
    def _():
        def slider_cb(g):
            def cb(v):
                angles_set({**angles_get(), g: {'deg': float(v), 'expr': None}})
            return cb

        return mo.ui.dictionary({
            g: mo.ui.slider(
                -180, 180, step=0.5,
                value=max(0.0, min(180.0, round(angles_get()[g]['deg'] * 2) / 2)),
                label=f'**{g}**', show_value=True, full_width=True,
                on_change=slider_cb(g))
            for g in gate_names})

    angle_slider_elems = _()
    return (angle_slider_elems,)


@app.cell(hide_code=True)
def _(
    angles_get,
    angles_set,
    base_env,
    gate_names,
    math,
    mo,
    mode_pick,
    qn,
    units_pick,
):
    def _():
        def text_cb(g):
            def cb(raw):
                txt = (raw or '').strip()
                # an explicit degree mark IS the unit, whatever the
                # units radio says
                marked = txt.endswith(('°', 'º', '˚'))
                txt = txt.rstrip('º°˚').strip()
                if not txt:
                    return
                try:
                    num = float(txt)
                    deg = (num if marked or units_pick.value == 'degrees'
                           else math.degrees(num))
                    angles_set({**angles_get(), g: {'deg': deg, 'expr': None}})
                    return
                except ValueError:
                    pass
                try:
                    rad = float(qn.qify(txt, base_env))  # symbolic expression (may use model variables), radians
                    angles_set({**angles_get(),
                                g: {'deg': math.degrees(rad), 'expr': txt}})
                except Exception:  # noqa: BLE001, S110 — unparseable: keep previous value
                    pass
            return cb

        def shown(cur):
            # Displayed angle values follow the math mode: Symbolic
            # shows the model's own symbolic spec while it is untouched
            # (a slider or typed number clears it), and the simplest
            # exact form of the set angle otherwise; Float shows a
            # number in the selected units.
            if mode_pick.value == 'Symbolic':
                if cur['expr']:
                    return cur['expr']
                return str(qn.sym.Rational(str(cur['deg'])) *
                           qn.sym.pi / 180)
            if units_pick.value == 'degrees':
                return f"{cur['deg']:.1f}º"
            return f"{math.radians(cur['deg']):.4f}"

        return mo.ui.dictionary({
            g: mo.ui.text(value=shown(angles_get()[g]), on_change=text_cb(g))
            for g in gate_names})

    angle_text_elems = _()
    return (angle_text_elems,)


@app.cell(hide_code=True)
def _(cmath, mo, qn):
    def latex_weight(w, prec=3, max_len=40) -> str:
        # In Symbolic mode, render the exact sympy expression as LaTeX —
        # unless its plain-text form is longer than max_len characters
        # (the display.sym_or_float policy): complex models and awkward
        # inputs can produce unreadably long expressions, and those fall
        # back to the numeric form below.
        if qn.CalcMode.default() == 'Symbolic' and qn.isq(w):
            import sympy
            # sympy's simplify can choke on an odd but valid expression:
            # the unsimplified form is still exact and still symbolic
            try:
                expr = qn.simplify(w).v
            except Exception:  # noqa: BLE001 — keep the exact form
                expr = w.v
            if len(str(expr)) <= max_len and not qn.inexact(expr):
                return sympy.latex(expr)
        wc = complex(w)
        # always the full pair re±im·i at exactly prec decimals (0 is
        # 0.0000+0.0000i): every weight in a column has the same shape,
        # so right-aligned cells line their decimal points up. No forced
        # leading '+' on the real part — that would read as a particle
        # sign; the sign between the parts is the imaginary part's
        real = 0.0 if abs(wc.real) < 1e-12 else wc.real     # no '-0.0000'
        imag = 0.0 if abs(wc.imag) < 1e-12 else wc.imag
        return f'{real:.{prec}f}{imag:+.{prec}f}i'

    def math_weight(w, prec=3) -> str:
        # latex_weight wrapped as inline math. Whitespace is normalized
        # because markdown doesn't recognize '$ x$' (leading space) as
        # math — symbolic LaTeX often leads with '- \frac{...}'.
        return f'${" ".join(latex_weight(w, prec).split())}$'

    def inexact_note(sim) -> str:
        # Symbolic mode with inputs that cannot be exact: say so, gently
        bad = sim.inexact_inputs()
        if not bad:
            return ''
        return ('<br><span style="color: #b00020">⚠ Symbolic mode, but '
                + ', '.join(bad) + (' is' if len(bad) == 1 else ' are')
                + ' not exact (a floating-point or long decimal '
                'value), so these results carry floating point.</span>')

    def phase_deg(w) -> float:
        return cmath.phase(complex(w)) * 180.0 / cmath.pi

    def math_prob(pr, prec=4) -> str:
        # a probability as inline math: the exact form in Symbolic mode
        # when it is short (9/16), the fixed-precision float otherwise
        if qn.CalcMode.default() == 'Symbolic' and qn.isq(pr):
            import sympy
            try:
                expr = qn.simplify(pr).v
            except Exception:  # noqa: BLE001 — keep the exact form
                expr = pr.v
            if len(str(expr)) <= 40 and not qn.inexact(expr):
                return f'${sympy.latex(expr)}$'
        return f'${float(pr):.{prec}f}$'

    def md_cell(text: str) -> str:
        # html_table's cell renderer: markdown/math cells go through the
        # markdown renderer (its arithmatex spans are typeset in the
        # browser); plain cells are passed straight through
        if any(ch in text for ch in '$`*_<'):
            return mo.md(text).text
        return text

    def md_table(headers, rows) -> str:
        # NB: markdown needs a blank line before a table, and literal '|'
        # inside cells (configuration-space point keys use it as a separator) must be escaped
        # or they read as column breaks.
        def cell(c):
            return str(c).replace('|', r'\|')
        lines = ['',
                 '| ' + ' | '.join(headers) + ' |',
                 '|' + '|'.join(['---'] * len(headers)) + '|']
        lines += ['| ' + ' | '.join(cell(c) for c in row) + ' |' for row in rows]
        return '\n'.join(lines)

    _ = mo.md('')  # helpers only
    return (inexact_note, latex_weight, math_prob, math_weight, md_cell,
            md_table, phase_deg)


@app.cell(hide_code=True)
def _(Simulation, mo):
    # The three sampling interpretations, labeled by what each assumes
    # (see the Monte Carlo section's explanation); the value is the
    # engine's mode name
    SAMPLER_LABELS = {'terminal (Everett)': 'terminal',
                      'pilot wave (Bohm, nonlocal)': 'pilot'}
    # the EPR sweep also offers Bell's local hidden-variable example,
    # which samples no wave: a shared hidden angle and two independent
    # detector readings (epr.sample_hidden_variable)
    EPR_SAMPLER_LABELS = {**SAMPLER_LABELS,
                          "local hidden variable (Bell's example)": 'hidden'}
    SAMPLER_NAMES = {v: k for k, v in EPR_SAMPLER_LABELS.items()}

    def picked_modes(boxes, labels):
        """The mode names whose checkboxes are ticked, in the labels'
        order — the order the results are shown in."""
        return [labels[k] for k, v in boxes.value.items() if v]

    _calibration = {}

    def sampling_seconds(model_sim, modes, n_trials, cells=1):
        """A projection of how long a sampling job will take, from a
        calibration on this circuit: a few hundred trials of each
        interpretation are timed once per loaded model (and one run of
        the circuit, for a sweep's per-cell rebuild), then scaled to
        n_trials × cells. Measured where it will run, so the browser
        build's slower Python is accounted for."""
        import random
        import time
        from copy import deepcopy

        from quantish.epr import sample_hidden_variable
        from quantish.montecarlo import pilot_transitions, sample_pilot, sample_terminal
        key = id(model_sim)
        if key not in _calibration:
            t0 = time.perf_counter()
            cfg = deepcopy(model_sim.config)
            cfg['loglevel'] = 'warning'
            probe = Simulation(cfg)
            probe.run()
            run_cost = time.perf_counter() - t0
            rng, k, per_trial = random.Random(0), 300, {}
            t0 = time.perf_counter()
            sample_terminal(probe.result_space, k, rng)
            per_trial['terminal'] = (time.perf_counter() - t0) / k
            t0 = time.perf_counter()
            guidance = pilot_transitions(probe.initial_points)
            fit_cost = time.perf_counter() - t0
            t0 = time.perf_counter()
            sample_pilot(probe.initial_points, k, rng, transitions=guidance)
            per_trial['pilot'] = (time.perf_counter() - t0) / k
            t0 = time.perf_counter()
            sample_hidden_variable(0.0, 1.0, k, rng)
            per_trial['hidden'] = (time.perf_counter() - t0) / k
            _calibration[key] = (run_cost, fit_cost, per_trial)
        run_cost, fit_cost, per_trial = _calibration[key]
        secs = (run_cost if cells > 1 else 0.0) * cells
        for m in modes:
            secs += cells * (n_trials * per_trial[m]
                             + (fit_cost if m == 'pilot' else 0.0))
        return secs

    LONG_RUN_SECONDS = 30

    def projection(secs):
        """The predicted-runtime line: italic, and red bold past
        LONG_RUN_SECONDS so a long wait is announced before the Run
        button is pressed. (Html rather than markdown: marimo's markdown
        strips inline styles.)"""
        if secs < 1:
            text = 'under a second'
        elif secs < 90:
            text = f'about {secs:.0f} s'
        else:
            text = f'about {secs / 60:.1f} min'
        # explicit colors: bare Html output would inherit marimo's muted
        # gray, and a prose wrapper overrides the red
        style = ('color: #ff1f1f; font-weight: 700' if secs > LONG_RUN_SECONDS
                 else 'color: #000')
        return mo.Html(f'<em style="{style}">Predicted runtime: {text}</em>')

    return (EPR_SAMPLER_LABELS, SAMPLER_LABELS, SAMPLER_NAMES, picked_modes,
            projection, sampling_seconds)


@app.cell(hide_code=True)
def _(SAMPLER_LABELS, mo):
    mc_trials = mo.ui.slider(
        steps=[100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000,
               100000, 200000, 500000, 1000000],
        value=20000, label='trials', show_value=True)
    mc_trials_text = mo.ui.text(value='', placeholder='custom trial count')
    # two interpretations sampling the same wave, labeled by what each
    # assumes; terminal (the faithful simulation of a real experiment)
    # is the default
    # one checkbox per interpretation, in the results' order, none
    # ticked until the user chooses
    mc_modes = mo.ui.dictionary({k: mo.ui.checkbox(label=k)
                                 for k in SAMPLER_LABELS})
    mc_seed = mo.ui.number(value=42, label='seed')
    mc_button = mo.ui.run_button(label='Run Monte Carlo')
    mc_cancel = mo.ui.run_button(label='Cancel')
    return mc_button, mc_cancel, mc_modes, mc_seed, mc_trials, mc_trials_text


@app.cell(hide_code=True)
def _(mo):
    # Shared, mutable job slot for the background Monte Carlo worker,
    # plus a version counter the worker bumps (it runs in a mo.Thread,
    # so state setters reach the frontend). The display cell depends
    # on the counter and re-renders as sampling progresses — no
    # polling, and results land even if the section is collapsed
    # while the job runs.
    mc_job_slot = {}
    mc_tick_get, mc_tick_set = mo.state(0)
    return mc_job_slot, mc_tick_get, mc_tick_set


@app.cell(hide_code=True)
def _(mc_cancel, mc_job_slot):
    # the Cancel button flags the running job; the worker stops at the
    # next chunk boundary and reports its partial tallies
    if mc_cancel.value:
        _job = mc_job_slot.get('job')
        if _job is not None and not _job['done']:
            _job['cancel'].set()


@app.cell(hide_code=True)
def _(base_config, mo, model_vars):
    # Sweep-angle entries, reseeded from the model's qa/qb/qc variables
    # (or the default 0, pi/8, pi/4) when the model or its variables
    # change. Same input forms as the gate-angle entries: a bare number
    # in the selected units, anything else a symbolic radian expression.
    def _():
        from quantish.epr import DEFAULT_VALUES
        _vars = {str(k).lower(): str(v)
                 for k, v in {**base_config.variables, **model_vars}.items()}
        return mo.ui.dictionary({
            k: mo.ui.text(value=_vars.get(k, v), label=f'**{k}** =')
            for k, v in DEFAULT_VALUES.items()})

    epr_angle_elems = _()
    return (epr_angle_elems,)


@app.cell(hide_code=True)
def _(EPR_SAMPLER_LABELS, mo):
    # Defined independently of sim/mode so a math-mode change or a Run can
    # never reset the user's chosen trial count.
    epr_trials = mo.ui.slider(
        steps=[0, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000,
               500000, 1000000],
        value=0, label='trials per cell (0 = exact only)', show_value=False)
    # the models the sampled cells run under, compared side by side:
    # the wave samplers show the violation, Bell's hidden-variable
    # example sits exactly at the classical bound
    epr_modes = mo.ui.dictionary({k: mo.ui.checkbox(label=k)
                                  for k in EPR_SAMPLER_LABELS})
    epr_button = mo.ui.run_button(label='Run EPR experiment')
    return epr_button, epr_modes, epr_trials


@app.cell(hide_code=True)
def _(
    EPR_SAMPLER_LABELS,
    base_env,
    epr_angle_elems,
    SAMPLER_NAMES,
    epr_button,
    epr_modes,
    picked_modes,
    epr_trials,
    math,
    md_table,
    mo,
    qn,
    run_epr_experiment,
    sim_model,
    supports_epr,
    sym_or_float,
    units_pick,
    verdict,
    verdict_slack,
):
    def _():
        if not supports_epr(sim_model):
            return None
        if not epr_button.value:
            return mo.md('_press **Run EPR experiment** to sweep_')

        def parse_angle(raw):
            # same convention as the gate-angle entries: a bare number is in
            # the selected units, anything else a symbolic radian expression
            txt = (raw or '').strip().rstrip('º°').strip()
            try:
                float(txt)   # a bare number, in the selected units
                # as a spec string, so Symbolic mode keeps it exact
                # (22.5 → pi/8), never a float in radians
                return qn.qify(txt if units_pick.value == 'radians'
                               else f'{txt}°')
            except ValueError:
                # symbolic radian expression; may use model variables
                return qn.qify(txt, base_env)

        try:
            values = {k: parse_angle(v)
                      for k, v in epr_angle_elems.value.items()}
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'**unparseable sweep angle** — {exc}')
        if len({round(float(v) % math.pi, 9) for v in values.values()}) < 3:
            return mo.md('**sweep angles must be distinct (mod π)** — equal '
                         'angles make cells compare an angle with itself and '
                         'the inequalities degenerate')
        n = int(epr_trials.value)
        # one sweep per chosen interpretation (the exact, analytical and
        # classical grids are the same in each; the observed grid and
        # its verdict differ — that comparison is the demonstration)
        modes = picked_modes(epr_modes, EPR_SAMPLER_LABELS) if n else []
        runs = {m: run_epr_experiment(sim_model, n_trials=n, seed=1,
                                      values=values, mode=m)
                for m in modes}
        # the exact grids come with any run; with no model ticked (or
        # no trials) one exact run supplies them
        res = (runs[modes[0]] if modes
               else run_epr_experiment(sim_model, n_trials=0, values=values))
        labels = list(res['values'].keys())

        def grid_table(getter, grid, fmt='{:.4f}'):
            # exact rates show as such in Symbolic mode when short
            # (sin²(π/8) = 1/2 - √2/4); floats otherwise
            def cell(v):
                return sym_or_float(v, fmt.format(qn.to_float(v)))
            rows = [[f'**{l1}**'] + [cell(getter(grid[(l1, l2)]))
                                     for l2 in labels]
                    for l1 in labels]
            return md_table([r'$\theta_1 \backslash \theta_2$'] + labels, rows)

        def verdicts(tag, r, bell_key, chsh_key, bell_slack, chsh_slack):
            # a sampled excess needs to clear sampling noise to count;
            # the words are epr.verdict's (VIOLATED / saturated / satisfied)
            def word(excess, slack):
                v = verdict(excess, slack)
                return f'**{v}**' if v == 'VIOLATED' else v
            bell, bell_at = r[bell_key]
            chsh, chsh_at = r[chsh_key]
            return (f'Bell excess ({tag}): **{bell:+.4f}** at {bell_at} — '
                    f'{word(bell, bell_slack)}  \n'
                    f'CHSH $|S|$ ({tag}): **{chsh:.4f}** at {chsh_at} — '
                    f'{word(chsh - 2, chsh_slack)}')

        # the exact laws first — quantish, analytical (one verdict:
        # they agree), classical — then one sampled block per model in
        # the interpretations' fixed order, each a grid and its verdicts
        parts = ['sweep angles: ' + ', '.join(
            f'{k} = {math.degrees(float(v)):.1f}º' for k, v in values.items()),
                 '**Exact quantish simulation** results',
                 grid_table(lambda c: c['exact'], res['grid']),
                 r'**Analytical law** $\sin^2(\theta_1-\theta_2)$',
                 grid_table(lambda c: c['analytical'], res['grid']),
                 verdicts('exact', res, 'bell_exact', 'chsh_exact', 1e-9, 1e-9),
                 ('**Classical hidden-variable law** — the best a local '
                  'model can do: it sits exactly on the bound'),
                 grid_table(lambda c: c['classical'], res['grid']),
                 verdicts('classical law', res, 'bell_classical',
                          'chsh_classical', 1e-9, 1e-9)]
        if modes:
            # a sampled excess must clear sampling noise (3σ) to count
            bell_slack, chsh_slack = verdict_slack(n)
            for m in [m for m in SAMPLER_NAMES if m in runs]:
                name = SAMPLER_NAMES[m]
                parts += [(f'**{name[0].upper()}{name[1:]}** sampled results: '
                           f'{n:,} trials per cell'),
                          grid_table(lambda c: c['sampled'], runs[m]['grid']),
                          verdicts('sampled', runs[m],
                                   'bell', 'chsh', bell_slack, chsh_slack)]
        # .tight-paragraphs (css/quantish_app.css): headings, grids and
        # verdicts run as close as the section's prose
        return mo.Html('<div class="tight-paragraphs">'
                       + mo.md('\n\n'.join(parts)).text + '</div>')

    epr_view = _()
    return (epr_view,)


@app.cell(hide_code=True)
def _(mo):
    ws_theta = mo.ui.slider(-90, 90, step=5, value=30, label='θ (º)',
                            show_value=True)
    ws_sign = mo.ui.switch(value=True, label='sign + (off = −)')
    ws_wmag = mo.ui.slider(0.0, 1.0, step=0.05, value=1.0, label='|w|',
                           show_value=True)
    ws_wphase = mo.ui.slider(-180, 180, step=5, value=0, label='φ(w) (º)',
                             show_value=True)
    ws_components = mo.ui.multiselect(
        options=['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b'],
        value=['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b'],
        label='components')
    # the mouse selection, persisted across parameter changes (the chart
    # is rebuilt on every slider move; the param is reseeded from here)
    ws_sel_get, ws_sel_set = mo.state(())
    return (
        ws_components,
        ws_sel_get,
        ws_sel_set,
        ws_sign,
        ws_theta,
        ws_wmag,
        ws_wphase,
    )


@app.cell(hide_code=True)
def _(
    FredkinGate,
    WeightSplitWidget,
    cmath,
    cpair,
    latex_weight,
    math,
    mo,
    phase_deg,
    qn,
    ws_components,
    ws_sel_get,
    ws_sign,
    ws_theta,
    ws_wmag,
    ws_wphase,
):
    def _():
        gate = FredkinGate('ws', qn.qify(math.radians(ws_theta.value)))
        w = ws_wmag.value * cmath.exp(1j * math.radians(ws_wphase.value))
        c2a, c2b, c3a, c3b = (complex(x) for x in
            cpair(gate, qn.Complex(w), twist=not ws_sign.value))
        data = {'c2': c2a + c2b, 'c3': c3a + c3b,
                'c2a': c2a, 'c2b': c2b, 'c3a': c3a, 'c3b': c3b}
        order = ['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b']
        sel = [c for c in order if c in ws_components.value]
        sign_str = '+' if ws_sign.value else '−'
        lines = []
        for name in sel:
            val = data[name]
            lines.append(
                rf"{name} &= {latex_weight(val, prec=2)}"
                rf" &\quad \texttt{{Pr}} &= {abs(val)**2:.2f} & \phi &= {phase_deg(val):.1f}\degree\\")
        joined = '\n'.join(lines)
        latex = rf"""
    $$
    \begin{{aligned}}
    {joined}
    \end{{aligned}}
    $$
    """
        # native SVG (builder-renderer idiom): Finder-style selection
        # synced through the widget's `selected` trait, wheel zoom, drag
        # pan, and a resizable frame in place of the old size slider
        native = mo.ui.anywidget(WeightSplitWidget(
            data={'vectors': {c: [data[c].real, data[c].imag]
                              for c in sel},
                  'order': sel,
                  'title': f'θ = {ws_theta.value}º, sign = {sign_str}',
                  'size': 500},
            selected=[c for c in ws_sel_get() if c in sel]))
        view = mo.hstack([native, mo.md(latex)],
                         align='center', justify='start', wrap=True)
        return native, view

    ws_native, ws_view = _()
    return ws_native, ws_view


@app.cell(hide_code=True)
def _(ws_native, ws_sel_get, ws_sel_set):
    # Persist the explorer's mouse selection across parameter changes:
    # the widget is rebuilt on every slider move and reseeded from this
    # state. An explicit empty (clicking empty plot space) clears it.
    def _():
        _nsel = (ws_native.value or {}).get('selected')
        if _nsel is not None and tuple(_nsel) != tuple(ws_sel_get()):
            ws_sel_set(tuple(_nsel))

    _()


@app.cell(hide_code=True)
def _(FredkinGate, qn):
    def cpair(g: FredkinGate, w:qn.Complex, twist=False):
        """
        From AIM-1026a: the four split components of weight w.
        Values are precomputed for speed. twist=True gives the minus-sign
        column (cos/sin of theta - pi/2, i.e. sin/cos of theta).
        """
        if not twist:
            c2a = w * g.cos2_theta
            c2b = w * g.cos_sin_theta
            c3a = w * g.sin2_theta
            c3b = w * g.mcos_sin_theta
        else:
            c2a = w * g.cos2_twist
            c2b = w * g.cos_sin_twist
            c3a = w * g.sin2_twist
            c3b = w * g.mcos_sin_twist
        return c2a, c2b, c3a, c3b

    return (cpair,)


if __name__ == "__main__":
    app.run()
