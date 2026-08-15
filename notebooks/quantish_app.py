"""Quantish Physics — marimo front-end.

Pick a model, adjust gate angles with sliders, and everything downstream
reacts: exact final worlds (LaTeX weights), marginal summaries, circuit
diagrams (TikZ + Mermaid), the weight-evolution graph, Monte Carlo
sampling, the Bell/CHSH experiment, and the four-way weight-split
explorer.

Run with:  marimo edit notebooks/quantish_app.py   (or `marimo run` to serve)
"""

import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
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

    # Inline chart data in the Vega-Lite spec instead of marimo's
    # shared-memory virtual files: our frames are tiny, and virtual files
    # produce noisy 404/KeyError tracebacks when a slider re-creates a
    # chart while the browser still holds the old data URL.
    alt.data_transformers.enable('default')

    # make the repo importable no matter where marimo was launched from
    _repo = Path(__file__).resolve().parents[1]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    import multiworld.qnumber as qn
    from multiworld.qnumber import CalcMode

    CalcMode.default('Float')
    qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('multiworld').setLevel(logging.WARNING)

    from multiworld.epr import run_epr_experiment, supports_epr
    from multiworld.gate import FredkinGate
    from multiworld.montecarlo import run_monte_carlo
    from multiworld.simulation import Simulation
    from multiworld.visualizations import diagram, network_graph_figure, short_config

    REPO_DIR = Path(__file__).resolve().parents[1]
    MODELS_DIR = REPO_DIR / 'models'
    return (
        Addict,
        CalcMode,
        FredkinGate,
        MODELS_DIR,
        Simulation,
        alt,
        cmath,
        diagram,
        math,
        mo,
        network_graph_figure,
        pd,
        qn,
        run_epr_experiment,
        run_monte_carlo,
        short_config,
        supports_epr,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Quantish Physics
    A simulation of the quantish universe from Chapter 4 of
    *Good and Real* (Drescher, 2006): Fredkin gates, complex-weighted
    worlds, and EPR experiments.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    model_rescan = mo.ui.run_button(label='↻ rescan models')
    # remembers the selection across rescans (see the dropdown's on_change)
    last_model_get, last_model_set = mo.state('fig417')
    return last_model_get, last_model_set, model_rescan


@app.cell(hide_code=True)
def _(MODELS_DIR, last_model_get, last_model_set, mo, model_rescan):
    model_rescan  # dependency: pressing the button re-globs the directory
    _options = {p.stem: p for p in sorted(MODELS_DIR.glob('*.yaml'))
                if p.stem != 'defaults'}
    _default = last_model_get() if last_model_get() in _options \
        else next(iter(_options))
    model_pick = mo.ui.dropdown(
        options=_options,
        value=_default,
        label='model',
        on_change=lambda _p: last_model_set(_p.stem) if _p is not None else None,
    )
    mo.hstack([model_pick, model_rescan], justify='start', gap=1)
    return (model_pick,)


@app.cell(hide_code=True)
def _(Addict, MODELS_DIR, Simulation, mo, model_pick, yaml):
    def load_config(path):
        with open(MODELS_DIR / 'defaults.yaml') as _f:
            _cfg = yaml.safe_load(_f)
        with open(path) as _f:
            _cfg.update(yaml.safe_load(_f))
        _cfg['loglevel'] = 'warning'
        return Addict(_cfg)

    base_config = load_config(model_pick.value)
    _base_sim = Simulation(load_config(model_pick.value))

    mode_pick = mo.ui.radio(['Float', 'Symbolic'], value='Float',
                            label='math mode', inline=True)
    units_pick = mo.ui.radio(['degrees', 'radians'], value='degrees',
                             label='typed numbers are', inline=True)

    def _centered(deg):
        _d = deg % 360.0
        return _d - 360.0 if _d > 180.0 else _d

    # ONE state for all gate angles: {gate: {'deg': float, 'expr': str|None}}.
    # marimo's state reactivity keys on the getter being referenced as a
    # global variable — a dict of per-gate states breaks the subscription
    # (the earlier bug), so everything lives under a single getter/setter.
    # 'expr' preserves the symbolic form (model YAML or typed) alongside
    # its numeric degree equivalent.
    gate_names = list(_base_sim.fredkin_gates.keys())
    angles_get, angles_set = mo.state({
        _g: {'deg': round(_centered(float(_gate.atheta.degrees)) * 2) / 2,
             'expr': str(base_config.gates[_g].angle)}
        for _g, _gate in _base_sim.fredkin_gates.items()
    })
    return (
        angles_get,
        angles_set,
        base_config,
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
    def _slider_cb(_g):
        def _cb(_v):
            angles_set({**angles_get(), _g: {'deg': float(_v), 'expr': None}})
        return _cb

    angle_slider_elems = mo.ui.dictionary({
        _g: mo.ui.slider(
            -180, 180, step=0.5,
            value=max(0.0, min(180.0, round(angles_get()[_g]['deg'] * 2) / 2)),
            label=f'**{_g}**', show_value=True, full_width=True,
            on_change=_slider_cb(_g))
        for _g in gate_names})
    return (angle_slider_elems,)


@app.cell(hide_code=True)
def _(angles_get, angles_set, gate_names, math, mo, mode_pick, qn, units_pick):
    def _text_cb(_g):
        def _cb(_raw):
            _txt = (_raw or '').strip().rstrip('º°').strip()
            if not _txt:
                return
            try:
                _num = float(_txt)
                _deg = _num if units_pick.value == 'degrees' else math.degrees(_num)
                angles_set({**angles_get(), _g: {'deg': _deg, 'expr': None}})
                return
            except ValueError:
                pass
            try:
                _rad = float(qn.qify(_txt))  # symbolic expression, radians
                angles_set({**angles_get(),
                            _g: {'deg': math.degrees(_rad), 'expr': _txt}})
            except Exception:  # noqa: BLE001 — unparseable: keep previous value
                pass
        return _cb

    def _shown(_cur):
        # The entry mirrors the current math mode: symbolic form when in
        # Symbolic mode (and one exists), numeric degrees otherwise.
        if mode_pick.value == 'Symbolic' and _cur['expr']:
            return _cur['expr']
        return f"{_cur['deg']:.1f}º"

    angle_text_elems = mo.ui.dictionary({
        _g: mo.ui.text(value=_shown(angles_get()[_g]), on_change=_text_cb(_g))
        for _g in gate_names})
    return (angle_text_elems,)


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
    _rows = [mo.hstack([angle_slider_elems[_g], angle_text_elems[_g]],
                       widths=[5, 1], align='center')
             for _g in gate_names]
    mo.vstack([
        mo.md(f"**{base_config.title}** — gate angles. Slider and entry track "
              "each other; sliders are degrees (0-centered). Typed numbers "
              "use the units selector; anything else is a symbolic radian "
              "expression (`pi/8`, `rad(30)`, `acos(4/5)`)."),
        mo.hstack([mode_pick, units_pick], wrap=True, justify='start', gap=2),
        mo.vstack(_rows),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    run_btn = mo.ui.run_button(label='▶ Run simulation')
    run_btn
    return (run_btn,)


@app.cell(hide_code=True)
def _(mo, sim):
    mo.accordion({'## Loaded Configuration': mo.accordion(sim.__dict__, multiple=True, lazy=True)})
    return


@app.cell(hide_code=True)
def _(
    CalcMode,
    Simulation,
    angles_get,
    gate_names,
    load_config,
    math,
    mo,
    mode_pick,
    model_pick,
    qn,
    run_btn,
):
    # Gated on the button: changing sliders/text/model/mode marks results
    # stale (this message) but leaves the previous results visible below.
    mo.stop(not run_btn.value,
            mo.md('_settings changed — press **▶ Run simulation** to (re)compute; '
                  'results below are from the previous run_'))

    def _angle_for(_g):
        _cur = angles_get()[_g]
        if _cur['expr']:
            return qn.qify(_cur['expr'])  # symbolic expression, in radians
        return math.radians(_cur['deg'])

    try:
        CalcMode.default(mode_pick.value)
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
        _config = load_config(model_pick.value)
        for _g in gate_names:
            _config.gates[_g].angle = _angle_for(_g)
        sim = Simulation(_config)
        sim.run()
        _error = None
    except Exception as _exc:  # noqa: BLE001 — old-format models raise all sorts
        sim = None
        _error = _exc
    mo.stop(sim is None,
            mo.md(f"**{model_pick.value.stem} failed to load or run** — probably "
                  f"an old-format model.\n\n```\n{_error}\n```"))
    _angles = ', '.join(f'{_g}={float(_gate.atheta.degrees):.1f}º'
                        for _g, _gate in sim.fredkin_gates.items())
    mo.md(f"Ran **{sim.title}** ({mode_pick.value} mode) — {_angles}; "
          f"{len(sim.run_stages)} steps, "
          f"{len(sim.result_space.index)} final world(s), "
          f"total probability "
          f"{sum(float(_p.probability) for _p in sim.result_space.index.values()):.6f}")
    return (sim,)


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
def _(cmath, mo, qn):
    def latex_weight(w, prec=4) -> str:
        # In Symbolic mode, render the exact sympy expression as LaTeX.
        try:
            if qn.CalcMode.default() == 'Symbolic' and qn.isq(w):
                import sympy as _sym
                return _sym.latex(qn.simplify(w).v)
        except Exception:  # noqa: BLE001 — fall back to the numeric form
            pass
        _w = complex(w)
        _re, _im = _w.real, _w.imag
        parts = []
        if abs(_re) > 1e-12:
            # parts.append(f'{_re:5.{prec}g}')
            sign = '-' if _re < 0 else '+'
            parts.append(f'{sign}{abs(round(_re, 2))}')
        if abs(_im) > 1e-12:
            sign = '-' if _im < 0 else '+'
            parts.append(f' {sign}{abs(_im):.{prec}g}i')
        return ''.join(parts) if parts else f'{0.00:+.2f}'

    def phase_deg(w) -> float:
        return cmath.phase(complex(w)) * 180.0 / cmath.pi

    def md_table(headers, rows) -> str:
        # NB: markdown needs a blank line before a table, and literal '|'
        # inside cells (world keys use it as a separator) must be escaped
        # or they read as column breaks.
        def cell(c):
            return str(c).replace('|', r'\|')
        lines = ['',
                 '| ' + ' | '.join(headers) + ' |',
                 '|' + '|'.join(['---'] * len(headers)) + '|']
        lines += ['| ' + ' | '.join(cell(c) for c in row) + ' |' for row in rows]
        return '\n'.join(lines)

    _ = mo.md('')  # helpers only
    return latex_weight, md_table, phase_deg


@app.cell(hide_code=True)
def _(md_table, mo, phase_deg, short_config, sim):
    # Worlds sorted canonically: gate (in evaluation order), then port
    # (upper before lower), then sign (+ before −); the configuration
    # label's coordinates are reordered to match.
    _rows = []
    for _p in sorted(sim.result_space.index.values(), key=sim.world_sort_key):
        _rows.append((
            f'`{short_config(_p, key=sim.coord_sort_key).replace("|", " ")}`',
            f'{_p.weight}',
            f'${float(_p.probability):.4f}$',
            f'${phase_deg(_p.weight):+.1f}º$',
        ))
    mo.accordion({'## Final worlds\n':
          mo.md(md_table(['configuration', 'weight $w$', r'$\lvert w\rvert^2$', 'phase'],
                   _rows))})
    return


@app.cell(hide_code=True)
def _(md_table, mo, sim):
    # Marginal in the statistics sense: each row sums |w|² over every
    # final world containing that coordinate — the chance of finding that
    # particle, with that sign, at that port, regardless of where the
    # other particles ended up. Rows follow gate evaluation order (upper
    # before lower, + before −), so a port's +/− pair sits together and
    # sums to the port's total output probability.
    _acc = {}
    for _p in sim.result_space.index.values():
        _prob = float(_p.probability)
        for _coord in _p.coords.values():
            _key = f'{_coord.pkey}@{_coord.position.origin}'
            _entry = _acc.setdefault(_key, [_coord, 0.0])
            _entry[1] += _prob
    _rows = [(f'`{_k}`', f'{_e[1]:.4f}')
             for _k, _e in sorted(_acc.items(),
                                  key=lambda kv: sim.coord_sort_key(kv[1][0]))]
    mo.accordion({
        '## Marginal probabilities (one coordinate at a time)':
            mo.md(r'Each row sums $\lvert w\rvert^2$ over every final world '
                  'in which that particle, with that sign, sits at that '
                  'port — its probability there *regardless of where the '
                  'other particles ended up* (the marginal over the rest '
                  'of the configuration). The +/− rows at one port '
                  "together give the port's total output probability.\n" +
                  md_table(['coordinate', 'probability'], _rows))
    })
    return


@app.cell(hide_code=True)
def _(md_table, mo, sim):
    # Per-step gate traffic: what arrived at each port (previous step's
    # coordinate endpoints) and what left it (that step's origins), with
    # per-sign probabilities and the aggregate Σ (|Σ|² and phase).
    _rows = [(_r['step'], _r['gate'], _r['port'],
              _r['input'].replace('\n', '<br>'),
              _r['output'].replace('\n', '<br>'))
             for _r in sim.gate_io()]
    mo.accordion({
        '## Gate inputs and outputs by step':
            mo.md(md_table(['step', 'gate', 'port', 'input', 'output'], _rows))
    })
    return


@app.cell(hide_code=True)
def _(mo, sim):
    # Depends on sim, so it refreshes on every Run (runs are now explicit,
    # so the pdflatex cost is paid once per Run, not per slider move).
    from multiworld.tikz_diagram import render_diagram, spec_from_simulation
    try:
        _overrides = {_g: f'{float(_gate.atheta.degrees):.1f}°'
                      for _g, _gate in sim.fredkin_gates.items()}
        _img = render_diagram(spec_from_simulation(sim), dpi=150,
                              angle_overrides=_overrides)
        _out = mo.image(_img, caption='circuit (TikZ)') if _img is not None else \
            mo.md('_TikZ render unavailable (needs pdflatex + imagemagick)_')
    except Exception as _exc:  # noqa: BLE001 — show, don't crash the app
        _out = mo.md(f'_TikZ diagram failed: {_exc}_')
    mo.vstack([mo.md('## Circuit diagram (TikZ)'), _out])
    return


@app.cell(hide_code=True)
def _(diagram, mo, sim):
    try:
        _mermaid_src = str(diagram(sim, output_file=None, has_run=True))
        _out = mo.mermaid(_mermaid_src)
    except Exception as _exc:  # noqa: BLE001
        _out = mo.md(f'_Mermaid diagram failed: {_exc}_')
    mo.vstack([mo.md('## Gate network with port values (Mermaid)'), _out])
    return


@app.cell(hide_code=True)
def _(mo, network_graph_figure, sim):
    from matplotlib import pyplot as _plt
    _fig = network_graph_figure(sim.all_points, sim)
    # deregister from pyplot so slider-driven reruns don't accumulate open
    # figures (the Figure object itself stays renderable)
    _plt.close(_fig)
    mo.vstack([mo.md('## Weight evolution (worlds × steps)'), _fig])
    return


@app.cell(hide_code=True)
def _(latex_weight, md_table, mo, short_config, sim):
    # Tabular twin of the weight-evolution graph: per stage, one row per
    # parent→child branch — the input world and its weight, the literal
    # per-particle factors the gate applied (cos²θ, ±i·sinθcosθ, sin²θ),
    # the branch amplitude, and the output world's total weight. Where
    # branch w ≠ world w, interfering branches merged into that world.
    def _label(_p):
        return f'`{short_config(_p, key=sim.coord_sort_key).replace("|", " ")}`'

    def _wfmt(_x):
        # latex_weight can emit a leading space (pure-imaginary values);
        # '$ ...$' is not valid inline math in markdown, so normalize.
        return f'${" ".join(latex_weight(_x).split())}$'

    def _factor_cell(_w, _parent, _contrib):
        # A merged world stores only its FIRST branch's per-particle
        # factors; for other branches show just the branch's overall
        # multiplier Π (recovered as branch w / input w).
        _facts = {_n: _f for _n, _f in _w.factors.items() if _f is not None}
        try:
            _expected = complex(_parent.weight)
            for _f in _facts.values():
                _expected *= complex(_f)
            _stored_ok = abs(_expected - complex(_contrib)) < 1e-9
        except (TypeError, ValueError):
            _stored_ok = True  # symbolic with free symbols: trust the stored factors
        if _stored_ok:
            return '<br>'.join(f'{_n}: {_wfmt(_f)}'
                               for _n, _f in _facts.items()) or '—'
        try:
            return f'Π: {_wfmt(complex(_contrib) / complex(_parent.weight))}'
        except (TypeError, ValueError, ZeroDivisionError):
            return 'Π: ?'

    _by_step = {}
    for _pt in sim.all_points.index.values():
        _by_step.setdefault(_pt.step, []).append(_pt)
    _sections = {}
    for _step in sorted(_by_step):
        _worlds = sorted(_by_step[_step], key=sim.world_sort_key)
        if _step == 0:
            _sections['Step 0 — initial world'] = mo.md(md_table(
                ['world', 'weight $w$'],
                [(_label(_w), _wfmt(_w.weight)) for _w in _worlds]))
            continue
        _rows = []
        for _w in _worlds:
            for _parent, _contrib in sorted(_w.contributions.items(),
                                            key=lambda kv: sim.world_sort_key(kv[0])):
                _rows.append((_label(_parent), _wfmt(_parent.weight),
                              _factor_cell(_w, _parent, _contrib),
                              _wfmt(_contrib), _label(_w), _wfmt(_w.weight)))
        _gates = ', '.join(sim.run_stages[_step - 1])
        _sections[f'Step {_step} — {_gates}'] = mo.md(md_table(
            ['input world', '$w_{in}$', 'factors', 'branch $w$',
             'output world', '$w_{out}$'], _rows))
    mo.accordion({'## Weight evolution table':
                  mo.accordion(_sections, multiple=True, lazy=True)})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Monte Carlo sampling
    Optional sampled trials on top of the exact run above. Two modes:

    - **terminal** — each trial draws one final world from the evolved
      superposition with probability $\lvert w\rvert^2$. This is the
      faithful simulation of a real experiment: interference stays intact
      until observation, and frequencies converge on the exact values.
    - **path** — each trial walks the world graph one stage at a time,
      picking a successor in proportion to the amplitude it received. That
      yields a world-line story per trial, but choosing per stage amounts
      to *collapsing at every stage*: where worlds interfere, path
      statistics legitimately diverge from the exact values — the
      divergence measures how much interference matters.
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
    mo.stop(not mc_button.value, mo.md('_press **Run Monte Carlo** to sample_'))
    try:  # the text entry, when it parses, overrides the slider
        _n_trials = max(1, int(mc_trials_text.value.strip()))
    except ValueError:
        _n_trials = int(mc_trials.value)
    _results = run_monte_carlo(sim, _n_trials, mode=mc_mode.value,
                               seed=int(mc_seed.value))
    _sections = []
    for _label, _note in (('terminal', 'one draw from the final superposition per trial'),
                          ('path', 'one world-line per trial — collapses at every stage')):
        if _label not in _results:
            continue
        _tally = _results[_label]
        _pred = _results['predicted']
        _rows = []
        _tvd = 0.0
        for _key in sorted(set(_tally) | set(_pred), key=lambda k: -_pred.get(k, 0)):
            _freq = _tally.get(_key, 0) / _n_trials
            _tvd += abs(_freq - _pred.get(_key, 0.0))
            _rows.append((f'`{_key.split(":")[0][:60].replace("|", " ")}`',
                          _tally.get(_key, 0),
                          f'{_freq:.4f}', f'{_pred.get(_key, 0.0):.4f}'))
        _sections.append(f'**{_label}** — {_note}; '
                         f'total variation distance {_tvd / 2:.4f}\n\n' +
                         md_table(['world', 'count', 'freq', 'exact'], _rows))
    mo.md('\n\n'.join(_sections))
    return


@app.cell(hide_code=True)
def _(mo):
    # Defined independently of sim/mode so a math-mode change or a Run can
    # never reset the user's chosen trial count.
    epr_trials = mo.ui.slider(0, 50000, step=1000, value=0,
                              label='trials per cell (0 = exact only)',
                              show_value=True)
    epr_button = mo.ui.run_button(label='Run EPR experiment')
    return epr_button, epr_trials


@app.cell(hide_code=True)
def _(epr_button, epr_trials, mo, sim, supports_epr):
    mo.stop(not supports_epr(sim))
    mo.vstack([
        mo.md(r"""
    ## EPR-Bell experiment
    **What the sweep does:** it re-runs the whole circuit **nine times**,
    once per pair $(\theta_1, \theta_2)$ from the magic angle set
    $\{Q_a, Q_b, Q_c\}$ — "measuring $p_1$ at $\theta_1$ and $p_2$ at
    $\theta_2$" by overriding the measurement gates
    ($g_7 = \theta_1$, $g_8 = (Q_5{+}Q_6) - \theta_2$ on two-stage
    circuits; $g_5/g_6$ on one-stage). Each cell tabulates the conditional
    discrepancy of the two outcomes; the grid then tests **Bell**
    ($d(a,c) \le d(a,b)+d(b,c)$) and **CHSH** ($|S| \le 2$) against the
    intrinsic law $d = \sin^2(\theta_1 - \theta_2)$.

    With trials = 0 (the default) each cell uses only the exact final
    worlds — fast. Setting trials adds per-cell Monte Carlo sampling on
    top. **Symbolic mode multiplies the cost**: nine exact symbolic runs
    with non-special angles take several seconds even at 0 trials.
    """),
        mo.hstack([epr_trials, epr_button], justify='start'),
    ])
    return


@app.cell(hide_code=True)
def _(
    epr_button,
    epr_trials,
    md_table,
    mo,
    run_epr_experiment,
    sim,
    supports_epr,
):
    mo.stop(not supports_epr(sim))
    mo.stop(not epr_button.value, mo.md('_press **Run EPR experiment** to sweep_'))
    _r = run_epr_experiment(sim, n_trials=int(epr_trials.value), seed=1)
    _labels = list(_r['values'].keys())

    def _grid_table(getter, fmt='{:.4f}'):
        _rows = [[f'**{_l1}**'] + [fmt.format(getter(_r['grid'][(_l1, _l2)]))
                                   for _l2 in _labels]
                 for _l1 in _labels]
        return md_table([r'$\theta_1 \backslash \theta_2$'] + _labels, _rows)

    _parts = [
        '**observed discrepancy** (sampled)' if epr_trials.value else '**exact discrepancy**',
        _grid_table(lambda c: c.get('sampled', c['exact'])),
        r'**analytical** $\sin^2(\theta_1-\theta_2)$',
        _grid_table(lambda c: c['analytical']),
        '**classical hidden-variable prediction**',
        _grid_table(lambda c: c['classical']),
    ]
    _bell, _bell_at = _r['bell_exact']
    _chsh, _chsh_at = _r['chsh_exact']
    _parts.append(
        f'Bell excess (exact): **{_bell:+.4f}** at {_bell_at} — '
        f'{"**VIOLATED**" if _bell > 1e-9 else "satisfied"}  \n'
        f'CHSH $|S|$ (exact): **{_chsh:.4f}** at {_chsh_at} — '
        f'{"**VIOLATED**" if _chsh > 2 + 1e-9 else "satisfied"}')
    mo.md('\n\n'.join(_parts))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Weight-split explorer
    The four-way split of one Fredkin-gate measurement at angle $\theta$:
    $c_{2a} = w\cos^2\theta$, $c_{2b} = i\,w\sin\theta\cos\theta$
    (straight), $c_{3a} = w\sin^2\theta$,
    $c_{3b} = -i\,w\sin\theta\cos\theta$ (cross); $c_2 = c_{2a}+c_{2b}$,
    $c_3 = c_{3a}+c_{3b}$. A minus-sign particle swaps the roles.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    ws_theta = mo.ui.slider(-90, 90, step=5, value=30, label='θ (º)',
                            show_value=True)
    ws_sign = mo.ui.switch(value=True, label='sign + (off = −)')
    ws_wmag = mo.ui.slider(0.0, 1.0, step=0.05, value=1.0, label='|w|',
                           show_value=True)
    ws_wphase = mo.ui.slider(-180, 180, step=5, value=0, label='arg(w) (º)',
                             show_value=True)
    ws_components = mo.ui.multiselect(
        options=['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b'],
        value=['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b'],
        label='components')
    mo.hstack([ws_theta, ws_sign, ws_wmag, ws_wphase, ws_components], wrap=True)
    return ws_components, ws_sign, ws_theta, ws_wmag, ws_wphase


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
    ws_sign,
    ws_theta,
    ws_wmag,
    ws_wphase,
):
    _gate = FredkinGate('ws', qn.qify(math.radians(ws_theta.value)))
    _w = ws_wmag.value * cmath.exp(1j * math.radians(ws_wphase.value))
    _c2a, _c2b, _c3a, _c3b = (complex(_x) for _x in
        cpair(_gate, qn.Complex(_w), twist=not ws_sign.value))
    _data = {'c2': _c2a + _c2b, 'c3': _c3a + _c3b,
            'c2a': _c2a, 'c2b': _c2b, 'c3a': _c3a, 'c3b': _c3b}
    _order = ['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b']
    _sel = [c for c in _order if c in ws_components.value]
    _frame = pd.DataFrame({
        'parallel': [_data[c].real for c in _sel],
        'perpendicular': [_data[c].imag for c in _sel],
        'component': _sel,
    })
    _base = alt.Chart(_frame)
    _vectors = _base.mark_rule(strokeWidth=2.5).encode(
        x2=alt.datum(0.0),
        x=alt.X('parallel:Q', axis=alt.Axis(title='Parallel (Re)'),
                scale=alt.Scale(domain=[-1.1, 1.1])),
        y2=alt.datum(0.0),
        y=alt.Y('perpendicular:Q', axis=alt.Axis(title='Perpendicular (Im)'),
                scale=alt.Scale(domain=[-1.1, 1.1])),
        color=alt.Color('component:N', sort=_order,
                        scale=alt.Scale(domain=_order)),
    )
    _labels = _base.mark_text(align='left', baseline='middle', dx=7).encode(
        x='parallel:Q', y='perpendicular:Q', text='component:N',
        color=alt.Color('component:N', sort=_order,
                        scale=alt.Scale(domain=_order)),
    )
    _sign_str = '+' if ws_sign.value else '−'
    _chart = (_vectors + _labels).properties(
        title=f'θ = {ws_theta.value}º, sign = {_sign_str}',
        width=400, height=400)
    _lines = []
    for _label in _sel:
        _val = _data[_label]
        _lines.append(
            rf"{_label} &= {latex_weight(_val, prec=2)}"
            rf" &\quad \texttt{{Pr}} &= {abs(_val)**2:.2f} & \phi &= {phase_deg(_val):.1f}\degree\\")
    _lj = '\n'.join(_lines)
    _latex = rf"""
    $$
    \begin{{aligned}}
    {_lj}
    \end{{aligned}}
    $$
    """
    # plain display (not mo.ui.altair_chart): no selection plumbing, and
    # with inline data no virtual-file churn on slider moves
    mo.hstack([_chart, mo.md(_latex)], align='center', justify='start')
    return


if __name__ == "__main__":
    app.run()
