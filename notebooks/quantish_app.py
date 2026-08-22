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
def initialization():
    import cmath
    import logging
    import math
    import sys
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import pandas as pd
    import yaml
    from addict import Addict

    # Inline chart data in the Vega-Lite spec. 'default' is not enough:
    # mo.ui.altair_chart overrides any non-marimo transformer with
    # marimo_arrow, whose virtual files are disposed on every cell re-run
    # while the browser still requests them ("Virtual file not found"
    # tracebacks flooding the server log). marimo respects transformers
    # named marimo_*, and marimo_inline_csv embeds the data as a base64
    # data: URL, so no virtual files exist at all.
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

    # make the repo importable no matter where marimo was launched from
    def _():
        repo = Path(__file__).resolve().parents[1]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))

    _()

    import quantish.qnumber as qn
    from quantish.qnumber import CalcMode

    CalcMode.default('Float')
    qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('quantish').setLevel(logging.WARNING)

    from quantish.config_space import GatePort
    from quantish.display import coord_sort_key, cs_point_sort_key, gate_io
    from quantish.epr import run_epr_experiment, supports_epr
    from quantish.gate import FredkinGate
    from quantish.montecarlo import run_monte_carlo
    from quantish.simulation import Simulation
    from quantish.mermaid_diagram import diagram
    from quantish.network_graph import NetworkGraph

    REPO_DIR = Path(__file__).resolve().parents[1]
    MODELS_TOP = REPO_DIR / 'models'
    return (
        Addict,
        CalcMode,
        FredkinGate,
        GatePort,
        MODELS_TOP,
        NetworkGraph,
        Simulation,
        alt,
        cmath,
        coord_sort_key,
        cs_point_sort_key,
        diagram,
        gate_io,
        math,
        mo,
        pd,
        qn,
        run_epr_experiment,
        run_monte_carlo,
        supports_epr,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Quantish Physics
    This [Marimo](https://marimo.io) notebook contains a simulation of the quantish universe described in Chapter 4 of
    *Good and Real: Demystifying Paradoxes from Physics to Ethics* by Gary L. Drescher (MIT Press, 2006). Included are simulations of Fredkin gates, complex-weighted
    configuration space points, and the classic Einstein-Podolsky-Rosen experiment.

    Several types of results are available:
    - A diagram of network topology generated using TikZ, a vector graphics package that uses LaTeX for rendering
    - A diagram showing network topology as well as gate inputs and outputs, generated using the Mermaid graphing framework
    - A graphical trace of how weights evolve through the running of the model
    - A table with exact numeric results of a model's run
    - A table of the final set of configuration space points (i.e., "classical worlds")
    - Marginal probabilities: the probability that any given particle will appear at a particular gate output
    - A trace of input and output values at every execution stage

    In addition to the basic simulation, there are:
    - a Monte Carlo simulation, in which a model is run many times, tracing a single execution path depending on the probabilities of outputs at each gate, and tabulated to show statistics consistent with the results of running equivalent real-world experiments
    - a weight-split explorer, to show concretely effects of various inputs to quantish Fredkin gates
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Model Selection

    The default model is as simple as possible, a single Fredkin gate as shown in figure 4.4 of _Good and Real_. Follow along in the book for fuller explanations of what's happening in each figure.

    The default parameters for each model are stored in a YAML file. Models are organized into *collections*. The default set of collections is:
    - **gr2026**: models implementing the figures in Chapter 4 of the 2026 revision of *Good and Real*.
    - **gr2006**: models implementing the figures in Chapter 4 of the original 2006 edition of *Good and Real*.
    - **extra**: more models demonstrating various aspects of the quantish framework. The `extras` collection includes a model taken from `MIT AIM-1026a`, the original 1989 paper which introduced the quantish framework.

    The **rescan models** button will reload models that have been modified since this notebook was started.
    """)
    return


@app.cell(hide_code=True)
def _(
    MODELS_TOP,
    collection_pick,
    last_models_get,
    last_models_set,
    mo,
    model_rescan,
):
    model_rescan  # dependency: pressing the button re-globs the directory

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
    mo.hstack([collection_pick, model_pick, model_rescan],
              justify='start', gap=1)
    return (model_pick,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Model Parameters

    Each model has a set of particles, a set of gates each with a particular angle, and links that connect particles and gates. Once a model is loaded, its gate angles can be modified below. Angles can be input using the sliders, each with a range from -180º to 180º, or the text entry fields, using values in either degrees or radians, according to the radio button selector. Added specifically for the simulation of the double-slit experiment, gates have an optional _phase_ parameter, allowing a gate with a zero angle to act as a _phase plate_, but that option is not surfaced in this application.

    Calculations within models often produce very small values, and floating-point roundoff errors can compound, appreciably affecting final results. Models can be run using exact values using symbolic arithmetic. In order to take best advantage of symbolic math, input values such gate angles should be specified symbolically (e.g., "pi/6" rather than "30.0º"). All numeric values can be in the form of expressions parsable by SymPy, such as "rad(30)", equivalent to "pi/6" arithmetic expressions such as "pi/6 + pi/8", and references to variables defined in a `variables` clause in a model's YAML specification.

    _Note:_ Symbolic math is much slower than floating-point, so model execution in Symbolic mode may take several seconds, especially for large models like the EPR setup (2026 figure 4.17, 2006 figure 4.16).
    """)
    return


@app.cell(hide_code=True)
def _(
    angle_slider_elems,
    angle_text_elems,
    base_config,
    gate_names,
    mo,
    mode_pick,
    units_pick,
):
    def _():
        rows = [mo.hstack([angle_slider_elems[g], angle_text_elems[g]],
                          widths=[5, 1], align='center')
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
        ])

    _()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Run the selected model

    Once a model has been loaded and its parameters set, the `Run simulation` button will execute the loaded model with the parameters shown above. Results displays will appear after execution is complete.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    run_btn = mo.ui.run_button(label='▶ Run simulation')
    run_btn
    return (run_btn,)


@app.cell(hide_code=True)
def _(build_sim, mo, mode_pick, model_pick, run_btn):
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

    def _():
        if sim is None:
            return mo.md('_press **▶ Run simulation** to compute results '
                         'with the settings above_')
        angles = ', '.join(f'{g}={float(gate.theta.degrees):.1f}º'
                           for g, gate in sim.fredkin_gates.items())
        return mo.md(
            f"Ran **{sim.title}** ({mode_pick.value} mode) — {angles}; "
            f"{len(sim.run_stages)} steps, "
            f"{len(sim.result_space.index)} final configuration-space point(s), "
            f"total probability "
            f"{sum(float(p.probability) for p in sim.result_space.index.values()):.6f}")

    _()
    return (sim,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Results
    """)
    return


@app.cell(hide_code=True)
def _(mo, sim, tikz_zoom, zoomable):
    mo.stop(sim is None)  # nothing to show until ▶ Run
    # Depends on sim, so it refreshes on every Run (runs are now explicit,
    # so the pdflatex cost is paid once per Run, not per slider move).
    # SVG, not PNG: vector output stays crisp at any zoom.
    def _():
        from quantish.tikz_diagram import render_diagram_svg, spec_from_simulation
        try:
            # gate labels come from the sim's config: symbolic angle
            # expressions display verbatim, numeric ones as degrees
            svg = render_diagram_svg(spec_from_simulation(sim))
            if svg is None:
                return mo.md('_TikZ render unavailable (needs pdflatex + pdf2svg)_')
            return mo.Html(svg)
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'_TikZ diagram failed: {exc}_')

    mo.accordion({'## TikZ circuit diagram': mo.vstack([tikz_zoom,
               zoomable(_(), tikz_zoom.value)])})
    return


@app.cell(hide_code=True)
def _(diagram, mermaid_zoom, mo, sim, zoomable):
    mo.stop(sim is None)  # nothing to show until ▶ Run

    def _():
        # The generated source carries no theme, and mo.mermaid's own
        # theme choice is unreadable on nested subgraphs — so pin the
        # palette of the old CLI-rendered SVGs (mermaid's classic
        # 'default' look): light-yellow group/gate clusters, light-gray
        # port nodes. Injected into the frontmatter alongside the title.
        theme = ('config:\n'
                 '  theme: base\n'
                 '  themeVariables:\n'
                 "    clusterBkg: '#ffffde'\n"
                 "    clusterBorder: '#aaaa33'\n"
                 "    primaryColor: '#ececec'\n"
                 "    primaryBorderColor: '#999999'\n"
                 "    primaryTextColor: '#333333'\n"
                 "    lineColor: '#333333'\n"
                 "    titleColor: '#333333'\n"
                 "    edgeLabelBackground: 'rgba(232,232,232,0.8)'\n"
                 'title:')
        try:
            src = str(diagram(sim, output_file=None, has_run=True)).replace(
                'title:', theme, 1)
            return mo.mermaid(src)
        except Exception as exc:  # noqa: BLE001
            return mo.md(f'_Mermaid diagram failed: {exc}_')

    mo.accordion({'## Mermaid circuit diagram, including calculated values': mo.vstack([
               mermaid_zoom, zoomable(_(), mermaid_zoom.value)])})
    return


@app.cell(hide_code=True)
def _(NetworkGraph, mo, sim):
    mo.stop(sim is None)  # nothing to show until ▶ Run
    # native Altair: live SVG with tooltips, pans/zooms itself. Shown
    # directly — mo.ui.altair_chart injects a selection param, which
    # Vega-Lite rejects on layered charts that carry configure_* options.
    def _():
        try:
            return NetworkGraph(sim.all_points, sim).chart().interactive()
        except Exception as exc:  # noqa: BLE001 — surface, don't crash the app
            return mo.md(f'_network graph failed: {exc}_')

    mo.accordion({'## Weight evolution graphic (configuration-space points × stages)': mo.vstack([_()])})
    return


@app.cell(hide_code=True)
def _(
    GatePort,
    coord_sort_key,
    cs_point_sort_key,
    math_weight,
    md_table,
    mo,
    qn,
    sim,
):
    mo.stop(sim is None)  # nothing to show until ▶ Run
    # Tabular twin of the weight-evolution graph: per stage, one row per
    # parent→child branch — the input configuration-space point and its weight, the
    # per-particle components the gate applied (cos²θ, ±i·sinθcosθ, sin²θ),
    # the branch amplitude, and the output configuration-space point's total weight. Where
    # branch w ≠ point w, interfering branches merged into that configuration-space point.
    def _():
        def label(p):
            return f'`{p.short_config(key=lambda c: coord_sort_key(sim, c)).replace("|", " ")}`'

        def particle_cell(w, parent, contrib):
            # A merged configuration-space point stores only its FIRST branch's per-particle
            # components; for other branches show just the branch's overall
            # multiplier Π (recovered as branch w / input w).
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
                return f'Π: {math_weight(complex(contrib) / complex(parent.weight))}'
            except (TypeError, ValueError, ZeroDivisionError):
                return 'Π: ?'

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
                sections['Step 0 — initial configuration-space point'] = mo.md(md_table(
                    ['configuration-space point', 'weight $w$'],
                    [(label(w), math_weight(w.weight)) for w in points]))
                continue
            stage = sim.run_stages[step - 1]
            parents = by_step.get(step - 1, [])
            rows = []
            for w in points:
                out_label = label(w) + (' _(cancelled)_' if w.cancelled else '')
                branches = sorted(w.contributions.items(),
                                  key=lambda kv: cs_point_sort_key(sim, kv[0]))
                if len(branches) == 1:
                    parent, contrib = branches[0]
                    rows.append((label(parent),
                                 ', '.join(controlled_gates(parent, stage)) or '∅',
                                 math_weight(parent.weight),
                                 particle_cell(w, parent, contrib),
                                 math_weight(contrib), out_label,
                                 math_weight(w.weight)))
                    continue
                # a merged output: its weight belongs to the SUM of the
                # branches, not to each branch — blank the output columns
                # on branch rows and close the group with a merged row
                # showing the addition
                for parent, contrib in branches:
                    rows.append((label(parent),
                                 ', '.join(controlled_gates(parent, stage)) or '∅',
                                 math_weight(parent.weight),
                                 particle_cell(w, parent, contrib),
                                 math_weight(contrib), '', ''))
                rows.append(('**merged**', '', '', '',
                             ' '.join(math_weight(c) for _, c in branches),
                             out_label, math_weight(w.weight)))
            total = qn.to_float(sum(w.probability for w in points
                                    if not w.cancelled))
            # md_table needs a blank line before it; its output starts
            # with one newline, so add the other after the header text
            sections[f'Step {step} — {", ".join(stage)}'] = mo.md(
                control_header(stage, parents) + '\n' +
                md_table(['input configuration-space point', 'control', '$w_{in}$', 'particles',
                          'branch $w$', 'output configuration-space point', '$w_{out}$'], rows) +
                f'\n\ntotal probability after step: {total:.6f}')
        return mo.accordion({'## Weight evolution table (configuration-space points)':
                             mo.accordion(sections, multiple=True, lazy=True)})

    _()
    return


@app.cell(hide_code=True)
def _(
    coord_sort_key,
    cs_point_sort_key,
    math_weight,
    md_table,
    mo,
    phase_deg,
    sim,
):
    mo.stop(sim is None)  # nothing to show until ▶ Run
    # Worlds sorted canonically: gate (in evaluation order), then port
    # (upper before lower), then sign (+ before −); the configuration
    # label's coordinates are reordered to match.
    def _():
        rows = [(
            f'`{p.short_config(key=lambda c: coord_sort_key(sim, c)).replace("|", " ")}`',
            math_weight(p.weight, prec=3),
            f'${float(p.probability):.4f}$',
            f'${phase_deg(p.weight):+.1f}º$',
        ) for p in sorted(sim.result_space.index.values(),
                          key=lambda p: cs_point_sort_key(sim, p))]
        return mo.accordion({'## Final configuration-space points\n': mo.md(md_table(
            ['configuration', 'weight $w$', r'$\lvert w\rvert^2$', 'phase'],
            rows))})

    _()
    return


@app.cell(hide_code=True)
def _(coord_sort_key, md_table, mo, sim):
    mo.stop(sim is None)  # nothing to show until ▶ Run
    # Marginal in the statistics sense: each row sums |w|² over every
    # final configuration-space point containing that coordinate — the chance of finding that
    # particle, with that sign, at that port, regardless of where the
    # other particles ended up. Rows follow gate evaluation order (upper
    # before lower, + before −), so a port's +/− pair sits together and
    # sums to the port's total output probability.
    def _():
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
            '## Marginal probabilities (one coordinate at a time)':
                mo.md(r'Each row sums $\lvert w\rvert^2$ over every final configuration-space point '
                      'in which that particle, with that sign, sits at that '
                      'port — its probability there *regardless of where the '
                      'other particles ended up* (the marginal over the rest '
                      'of the configuration). The +/− rows at one port '
                      "together give the port's total output probability.\n" +
                      md_table(['coordinate', 'probability'], rows))
        })

    _()
    return


@app.cell(hide_code=True)
def _(gate_io, md_table, mo, sim):
    mo.stop(sim is None)  # nothing to show until ▶ Run
    # Per-step gate traffic: what arrived at each port (previous step's
    # coordinate endpoints) and what left it (that step's origins), with
    # per-sign probabilities and the aggregate Σ (|Σ|² and phase).
    def _():
        rows = [(row['step'], row['gate'], row['port'],
                 row['input'].replace('\n', '<br>'),
                 row['output'].replace('\n', '<br>'))
                for row in gate_io(sim)]
        return mo.accordion({
            '## Gate inputs and outputs by step':
                mo.md(md_table(['step', 'gate', 'port', 'input', 'output'], rows))
        })

    _()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Monte Carlo sampling
    Optional sampled trials on top of the exact run above. Monte Carlo sampling can be run in either or both of two modes:

    - **terminal** — each trial draws one final configuration-space point from the
      evolved superposition with probability $\lvert w\rvert^2$. This is
      the faithful simulation of a real experiment: interference stays
      intact until observation, and frequencies converge on the exact
      values as trials grow.
    - **path** — each trial walks the configuration-space point graph one stage at a
      time, picking a successor in proportion to the amplitude it
      received. That yields a world-line story per trial, but choosing
      per stage amounts to *collapsing at every stage*: where configuration-space points
      interfere, path statistics will diverge from the
      exact values — the divergence measures how much interference
      matters.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mc_trials = mo.ui.slider(
        steps=[100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000,
               100000, 200000, 500000, 1000000],
        value=20000, label='trials', show_value=True)
    mc_trials_text = mo.ui.text(value='', placeholder='custom trial count')
    mc_mode = mo.ui.dropdown(options=['terminal', 'path', 'both'],
                             value='both', label='mode')
    mc_seed = mo.ui.number(value=42, label='seed')
    mc_button = mo.ui.run_button(label='Run Monte Carlo')
    mo.hstack([mc_trials, mc_trials_text, mc_mode, mc_seed, mc_button],
              wrap=True)
    return mc_button, mc_mode, mc_seed, mc_trials, mc_trials_text


@app.cell(hide_code=True)
def _(
    coord_sort_key,
    mc_button,
    mc_mode,
    mc_seed,
    mc_trials,
    mc_trials_text,
    md_table,
    mo,
    run_monte_carlo,
    sim,
):
    mo.stop(sim is None)  # nothing to sample until ▶ Run
    mo.stop(not mc_button.value, mo.md('_press **Run Monte Carlo** to sample_'))

    def _():
        try:  # the text entry, when it parses, overrides the slider
            n_trials = max(1, int(mc_trials_text.value.strip()))
        except ValueError:
            n_trials = int(mc_trials.value)
        results = run_monte_carlo(sim, n_trials, mode=mc_mode.value,
                                  seed=int(mc_seed.value))
        pred = results['predicted']
        # compact row labels: the same short-config form the final-points
        # table uses, looked up from the terminal points (raw keys are
        # unreadably long for multi-particle models)
        short = {p.key: p.short_config(
                     key=lambda c: coord_sort_key(sim, c)).replace('|', ' ')
                 for p in sim.result_space.index.values()}
        sections = []
        # terminal first: it is the faithful baseline the path mode's
        # per-stage collapse is measured against
        for label, note in (
                ('terminal', 'one draw from the final superposition per trial'),
                ('path', 'one world-line per trial — collapses at every stage')):
            if label not in results:
                continue
            tally = results[label]
            rows = []
            tvd = 0.0
            for key in sorted(set(tally) | set(pred), key=lambda k: -pred.get(k, 0)):
                freq = tally.get(key, 0) / n_trials
                tvd += abs(freq - pred.get(key, 0.0))
                bare = key.split(':')[0]
                label_str = short.get(bare, bare[:60].replace('|', ' '))
                rows.append((f'`{label_str}`',
                             tally.get(key, 0),
                             f'{freq:.4f}', f'{pred.get(key, 0.0):.4f}'))
            sections.append(f'**{label}** — {note}; '
                            f'total variation distance {tvd / 2:.4f}\n\n' +
                            md_table(['configuration-space point', 'count', 'freq', 'exact'],
                                     rows))
        return mo.md('\n\n'.join(sections))

    _()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The Einstein-Podolsky-Rosen / Bell Experiment

    The EPR experiment user interface is hidden until a suitable model (e.g. Figure 4.17) is loaded.
    """)
    return


@app.cell(hide_code=True)
def _(epr_angle_elems, epr_button, epr_trials, mo, sim_model, supports_epr):
    mo.stop(not supports_epr(sim_model))
    mo.vstack([
        mo.md(r"""
    **What the sweep does:** it re-runs the whole circuit **nine times**,
    once per pair $(\theta_1, \theta_2)$ from the sweep angles
    $\{q_a, q_b, q_c\}$ chosen below — "measuring $p_1$ at $\theta_1$
    and $p_2$ at $\theta_2$" by overriding the measurement gates
    ($g_7 = \theta_1$, $g_8 = (Q_5{+}Q_6) - \theta_2$ on two-stage
    circuits; $g_5/g_6$ on one-stage). Each cell tabulates the conditional
    discrepancy of the two outcomes; the grid then tests **Bell**
    ($d(a,c) \le d(a,b)+d(b,c)$) and **CHSH** ($|S| \le 2$) against the
    intrinsic law $d = \sin^2(\theta_1 - \theta_2)$.
    """),
        mo.accordion({'How the fig 4.17 circuit works': mo.md(r"""
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
    """)}),
        mo.md(r"""
    **Choosing the sweep angles.** Only differences matter — the law is
    $\sin^2(\theta_1-\theta_2)$, with period $\pi$ — so the one hard
    constraint is that the three angles be **distinct (mod π)**: equal
    angles make cells compare an angle with itself and the inequalities
    degenerate. Any distinct triple is a valid experiment; whether it
    *violates* the classical bounds depends on spacing. With equal
    spacing $\delta$, Bell is violated exactly when $0 < \delta < 45°$
    (largest excess at $\delta = 30°$), and the canonical set
    $(0°, 22.5°, 45°)$ drives CHSH to $1{+}\sqrt2 \approx 2.414$.
    A bare number below uses the units selector at the top; anything
    else is read as a symbolic radian expression (`pi/8`, `rad(30)`).

    With trials = 0 (the default) each cell uses only the exact final
    configuration-space points — fast. Setting trials adds per-cell Monte Carlo sampling on
    top.

    **Note: Symbolic mode (set above) multiplies the cost**: nine exact symbolic runs
    with non-special angles may take several seconds even at 0 trials.
    Values may be entered here as either symbolic or floating-point expressions.
    Computation will use the selected mode in either case.

    """),
        mo.hstack([epr_angle_elems['qa'], epr_angle_elems['qb'],
                   epr_angle_elems['qc']],
                  justify='start', gap=2),
        mo.hstack([epr_trials, epr_button], justify='start'),
    ])
    return


@app.cell(hide_code=True)
def _(
    base_env,
    epr_angle_elems,
    epr_button,
    epr_trials,
    math,
    md_table,
    mo,
    qn,
    run_epr_experiment,
    sim_model,
    supports_epr,
    units_pick,
):
    mo.stop(not supports_epr(sim_model))
    mo.stop(not epr_button.value, mo.md('_press **Run EPR experiment** to sweep_'))

    def _():
        def parse_angle(raw):
            # same convention as the gate-angle entries: a bare number is in
            # the selected units, anything else a symbolic radian expression
            txt = (raw or '').strip().rstrip('º°').strip()
            try:
                num = float(txt)
                return qn.qify(num if units_pick.value == 'radians'
                               else math.radians(num))
            except ValueError:
                # symbolic radian expression; may use model variables
                return qn.qify(txt, base_env)

        try:
            values = {k: parse_angle(v)
                      for k, v in epr_angle_elems.value.items()}
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            mo.stop(True, mo.md(f'**unparseable sweep angle** — {exc}'))
        mo.stop(len({round(float(v) % math.pi, 9) for v in values.values()}) < 3,
                mo.md('**sweep angles must be distinct (mod π)** — equal angles '
                      'make cells compare an angle with itself and the '
                      'inequalities degenerate'))
        res = run_epr_experiment(sim_model, n_trials=int(epr_trials.value), seed=1,
                                 values=values)
        labels = list(res['values'].keys())

        def grid_table(getter, fmt='{:.4f}'):
            rows = [[f'**{l1}**'] + [fmt.format(getter(res['grid'][(l1, l2)]))
                                     for l2 in labels]
                    for l1 in labels]
            return md_table([r'$\theta_1 \backslash \theta_2$'] + labels, rows)

        parts = [
            'sweep angles: ' + ', '.join(
                f'{k} = {math.degrees(float(v)):.1f}º'
                for k, v in values.items()),
            '**observed discrepancy** (sampled)' if epr_trials.value else '**exact discrepancy**',
            grid_table(lambda c: c.get('sampled', c['exact'])),
            r'**analytical** $\sin^2(\theta_1-\theta_2)$',
            grid_table(lambda c: c['analytical']),
            '**classical hidden-variable prediction**',
            grid_table(lambda c: c['classical']),
        ]
        bell, bell_at = res['bell_exact']
        chsh, chsh_at = res['chsh_exact']
        parts.append(
            f'Bell excess (exact): **{bell:+.4f}** at {bell_at} — '
            f'{"**VIOLATED**" if bell > 1e-9 else "satisfied"}  \n'
            f'CHSH $|S|$ (exact): **{chsh:.4f}** at {chsh_at} — '
            f'{"**VIOLATED**" if chsh > 2 + 1e-9 else "satisfied"}')
        return mo.md('\n\n'.join(parts))

    _()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Weight-split explorer

    An interactive tool showing what happens to weights going through a Fredkin gate.

    It demonstrates the four-way split of one Fredkin gate measurement at angle $\theta$:
    $c_{2a} = w\cos^2\theta$, $c_{2b} = i\,w\sin\theta\cos\theta$
    (straight), $c_{3a} = w\sin^2\theta$,
    $c_{3b} = -i\,w\sin\theta\cos\theta$ (cross); $c_2 = c_{2a}+c_{2b}$,
    $c_3 = c_{3a}+c_{3b}$. A minus-sign particle swaps the roles.

    **Note:** Individual components can be selected by clicking on either their vectors on the chart or their entry in the legend. Shift-click toggles a component's selected state.
    """)
    return


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
    # one value drives both chart dimensions, so the 1:1 aspect (which
    # keeps the unit circle circular) can't be broken by stretching
    ws_size = mo.ui.slider(300, 1000, step=25, value=500,
                           label='chart size (px)', show_value=True)
    # the mouse selection, persisted across parameter changes (the chart
    # is rebuilt on every slider move; the param is reseeded from here)
    ws_sel_get, ws_sel_set = mo.state(())
    mo.hstack([ws_theta, ws_sign, ws_wmag, ws_wphase, ws_components, ws_size],
              wrap=True)
    return (
        ws_components,
        ws_sel_get,
        ws_sel_set,
        ws_sign,
        ws_size,
        ws_theta,
        ws_wmag,
        ws_wphase,
    )


@app.cell(hide_code=True)
def _(
    FredkinGate,
    alt,
    cmath,
    cpair,
    latex_weight,
    math,
    mo,
    pd,
    phase_deg,
    qn,
    ws_components,
    ws_sel_get,
    ws_sign,
    ws_size,
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
        frame = pd.DataFrame({
            'parallel': [data[c].real for c in sel],
            'perpendicular': [data[c].imag for c in sel],
            'component': sel,
        })
        # Finder-style selection: click a vector or a legend entry to
        # make it the selection; shift/cmd/ctrl-click toggles items in and
        # out; click empty space to clear. One selection with on='click'
        # AND bind='legend' receives both event streams (verified in the
        # compiled Vega), so the legend highlighting tracks mark clicks
        # and vice versa — no difference which you click.
        mods = 'event.shiftKey || event.metaKey || event.ctrlKey'
        seed = [{'component': c} for c in ws_sel_get() if c in sel]
        picked = alt.selection_point(name='picked', fields=['component'],
                                     on='click', bind='legend', toggle=mods,
                                     **({'value': seed} if seed else {}))
        base = alt.Chart(frame)
        vectors = base.mark_rule().encode(
            x2=alt.datum(0.0),
            x=alt.X('parallel:Q', axis=alt.Axis(title='Parallel (Re)'),
                    scale=alt.Scale(domain=[-1.1, 1.1])),
            y2=alt.datum(0.0),
            y=alt.Y('perpendicular:Q', axis=alt.Axis(title='Perpendicular (Im)'),
                    scale=alt.Scale(domain=[-1.1, 1.1])),
            color=alt.Color('component:N', sort=order,
                            scale=alt.Scale(domain=order)),
            strokeWidth=alt.when(picked).then(alt.value(4.0))
                           .otherwise(alt.value(2.5)),
            opacity=alt.when(picked).then(alt.value(1.0))
                       .otherwise(alt.value(0.35)),
        ).add_params(picked)
        labels = base.mark_text(align='left', baseline='middle', dx=7).encode(
            x='parallel:Q', y='perpendicular:Q', text='component:N',
            color=alt.Color('component:N', sort=order,
                            scale=alt.Scale(domain=order)),
            opacity=alt.when(picked).then(alt.value(1.0))
                       .otherwise(alt.value(0.35)),
        )
        sign_str = '+' if ws_sign.value else '−'
        # .interactive(): mouse-wheel zoom, drag to pan
        chart = (vectors + labels).properties(
            title=f'θ = {ws_theta.value}º, sign = {sign_str}',
            width=int(ws_size.value), height=int(ws_size.value)).interactive()
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
        # mo.ui.altair_chart carries the 'picked' selection back to
        # Python so the capture cell below can persist it
        widget = mo.ui.altair_chart(chart, chart_selection=False,
                                    legend_selection=False)
        return widget, mo.hstack([widget, mo.md(latex)],
                                 align='center', justify='start')

    ws_chart, _view = _()
    _view
    return (ws_chart,)


@app.cell(hide_code=True)
def _(mo):
    # shown in the editor only: in `marimo run` the code cells below are
    # hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Loaded Configuration Details
    """) if mo.app_meta().mode != 'run' else None
    return


@app.cell(hide_code=True)
def _(mo, model_pick, sim):
    # editor-only section: hidden with its heading in `marimo run`
    mo.stop(sim is None or mo.app_meta().mode == 'run')
    mo.accordion({str(model_pick.value.stem): mo.accordion(sim.__dict__, multiple=True, lazy=True)})
    return


@app.cell(hide_code=True)
def _(mo):
    # shown in the editor only: in `marimo run` the code cells below are
    # hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Support Code
    """) if mo.app_meta().mode != 'run' else None
    return


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
            return math.radians(cur['deg'])

        CalcMode.default(mode_pick.value)
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
        config = load_config(model_pick.value)
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
def _(MODELS_TOP, last_collection_get, last_collection_set, mo, model_rescan):
    model_rescan  # dependency: pressing the button re-scans the directory

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
def _(mo):
    model_rescan = mo.ui.run_button(label='↻ rescan models')
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
    )


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


@app.cell(hide_code=True)
def _(ws_chart, ws_sel_get, ws_sel_set):
    # Persist the explorer's mouse selection. A freshly rebuilt chart
    # reports no selection until clicked, so an empty report never clears
    # a remembered selection — clearing happens by toggling items off.
    def _():
        try:
            comps = tuple(ws_chart.selections.get('picked', {})
                          .get('component', ()))
        except Exception:  # noqa: BLE001 — selection shape varies by marimo version
            return
        if comps and comps != tuple(ws_sel_get()):
            ws_sel_set(comps)

    _()
    return


@app.cell(hide_code=True)
def _(Addict, MODELS_TOP, Simulation, mo, model_pick, yaml):
    def load_config(path):
        with open(MODELS_TOP / 'defaults.yaml') as f:
            cfg = yaml.safe_load(f)
        with open(path) as f:
            cfg.update(yaml.safe_load(f))
        cfg['loglevel'] = 'warning'
        return Addict(cfg)

    base_config = load_config(model_pick.value)

    mode_pick = mo.ui.radio(['Float', 'Symbolic'], value='Float',
                            label='math mode', inline=True)
    units_pick = mo.ui.radio(['degrees', 'radians'], value='degrees',
                             label='typed numbers are', inline=True)

    # ONE state for all gate angles: {gate: {'deg': float, 'expr': str|None}}.
    # marimo's state reactivity keys on the getter being referenced as a
    # global variable — a dict of per-gate states breaks the subscription
    # (the earlier bug), so everything lives under a single getter/setter.
    # 'expr' preserves the symbolic form (model YAML or typed) alongside
    # its numeric degree equivalent.
    def _():
        def centered(deg):
            d = deg % 360.0
            return d - 360.0 if d > 180.0 else d

        base_sim = Simulation(load_config(model_pick.value))
        names = list(base_sim.fredkin_gates.keys())
        angles = mo.state({
            g: {'deg': round(centered(float(gate.theta.degrees)) * 2) / 2,
                'expr': str(base_config.gates[g].angle)}
            for g, gate in base_sim.fredkin_gates.items()})
        # the model's variables, so typed expressions can use them by name
        return names, angles, dict(base_sim.qvars)

    gate_names, (angles_get, angles_set), base_env = _()
    return (
        angles_get,
        angles_set,
        base_config,
        base_env,
        gate_names,
        load_config,
        mode_pick,
        units_pick,
    )


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
                txt = (raw or '').strip().rstrip('º°').strip()
                if not txt:
                    return
                try:
                    num = float(txt)
                    deg = num if units_pick.value == 'degrees' else math.degrees(num)
                    angles_set({**angles_get(), g: {'deg': deg, 'expr': None}})
                    return
                except ValueError:
                    pass
                try:
                    rad = float(qn.qify(txt, base_env))  # symbolic expression (may use model variables), radians
                    angles_set({**angles_get(),
                                g: {'deg': math.degrees(rad), 'expr': txt}})
                except Exception:  # noqa: BLE001 — unparseable: keep previous value
                    pass
            return cb

        def shown(cur):
            # The entry mirrors the current math mode: symbolic form when in
            # Symbolic mode (and one exists), numeric degrees otherwise.
            if mode_pick.value == 'Symbolic' and cur['expr']:
                return cur['expr']
            return f"{cur['deg']:.1f}º"

        return mo.ui.dictionary({
            g: mo.ui.text(value=shown(angles_get()[g]), on_change=text_cb(g))
            for g in gate_names})

    angle_text_elems = _()
    return (angle_text_elems,)


@app.cell(hide_code=True)
def _(mo):
    # One zoom slider per diagram, defined together so a zoom change
    # re-runs only the cell that displays that diagram.
    def _():
        def zslider():
            return mo.ui.slider(0.5, 3.0, step=0.25, value=1.0,
                                label='zoom', show_value=True)
        return zslider(), zslider(), zslider()

    tikz_zoom, mermaid_zoom, graph_zoom = _()
    return mermaid_zoom, tikz_zoom


@app.cell(hide_code=True)
def _(cmath, mo, qn):
    def latex_weight(w, prec=4, max_len=40) -> str:
        # In Symbolic mode, render the exact sympy expression as LaTeX —
        # unless its plain-text form is longer than max_len characters
        # (the display.sym_or_float policy): complex models and awkward
        # inputs can produce unreadably long expressions, and those fall
        # back to the numeric form below.
        try:
            if qn.CalcMode.default() == 'Symbolic' and qn.isq(w):
                import sympy
                simplified = qn.simplify(w).v
                if len(str(simplified)) <= max_len:
                    return sympy.latex(simplified)
        except Exception:  # noqa: BLE001 — fall back to the numeric form
            pass
        wc = complex(w)
        real, imag = wc.real, wc.imag
        parts = []
        if abs(real) > 1e-12:
            sign = '-' if real < 0 else '+'
            parts.append(f'{sign}{abs(round(real, 2))}')
        if abs(imag) > 1e-12:
            sign = '-' if imag < 0 else '+'
            parts.append(f' {sign}{abs(imag):.{prec}g}i')
        return ''.join(parts) if parts else f'{0.00:+.2f}'

    def math_weight(w, prec=4) -> str:
        # latex_weight wrapped as inline math. Whitespace is normalized
        # because markdown doesn't recognize '$ x$' (leading space) as
        # math — symbolic LaTeX often leads with '- \frac{...}'.
        return f'${" ".join(latex_weight(w, prec).split())}$'

    def phase_deg(w) -> float:
        return cmath.phase(complex(w)) * 180.0 / cmath.pi

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
    def inline_png(png_bytes):
        # a data-URI <img> instead of marimo's shared-memory virtual
        # files: re-running a cell disposes the old virtual file while the
        # browser still holds its URL, producing FileNotFoundError noise
        # in the server log (same reason the Altair data is inlined)
        import base64
        b64 = base64.b64encode(png_bytes).decode()
        return mo.Html(f'<img src="data:image/png;base64,{b64}">')

    def zoomable(obj, factor):
        # Width-based zoom: widen an inner container and make the media
        # fill it. CSS zoom fails here because mo.image and Mermaid SVGs
        # are max-width-clamped to the container — the clamp scales along
        # with the zoom, so only the caption text grew. Full height, no
        # inner vertical scrolling; zoomed-in content scrolls sideways.
        return mo.Html(
            f'<div style="overflow-x:auto">'
            f'<div class="qzoom" style="width:{factor * 100:.0f}%">'
            f'<style>.qzoom img, .qzoom svg '
            f'{{ width:100% !important; max-width:none !important; '
            f'height:auto !important; }}</style>'
            f'{mo.as_html(obj).text}</div></div>')

    return latex_weight, math_weight, md_table, phase_deg, zoomable


@app.cell(hide_code=True)
def _(base_config, mo):
    # Sweep-angle entries, reseeded from the model's qa/qb/qc variables
    # (or the canonical 0, pi/8, pi/4) when the model changes. Same input
    # forms as the gate-angle entries: a bare number in the selected
    # units, anything else a symbolic radian expression.
    def _():
        from quantish.epr import DEFAULT_VALUES
        model_vars = {str(k).lower(): str(v)
                      for k, v in base_config.variables.items()}
        return mo.ui.dictionary({
            k: mo.ui.text(value=model_vars.get(k, v), label=f'**{k}** =')
            for k, v in DEFAULT_VALUES.items()})

    epr_angle_elems = _()
    return (epr_angle_elems,)


@app.cell(hide_code=True)
def _(mo):
    # Defined independently of sim/mode so a math-mode change or a Run can
    # never reset the user's chosen trial count.
    epr_trials = mo.ui.slider(0, 50000, step=1000, value=0,
                              label='trials per cell (0 = exact only)',
                              show_value=True)
    epr_button = mo.ui.run_button(label='Run EPR experiment')
    return epr_button, epr_trials


if __name__ == "__main__":
    app.run()
