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
def _(MODELS_DIR, mo):
    _model_files = sorted(p for p in MODELS_DIR.glob('*.yaml')
                          if p.stem != 'defaults')
    model_pick = mo.ui.dropdown(
        options={p.stem: p for p in _model_files},
        value='fig417' if (MODELS_DIR / 'fig417.yaml').exists() else _model_files[0].stem,
        label='model',
    )
    model_pick
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

    # One state per gate: {'deg': float, 'expr': str | None}. Slider and
    # text field both read from and write to this, which keeps them in sync
    # (marimo's mo.state pattern for tied elements). 'expr' preserves a
    # typed symbolic expression for Symbolic-mode runs.
    gate_names = list(_base_sim.fredkin_gates.keys())
    angle_state = {
        _g: mo.state({'deg': round(_centered(float(_gate.atheta.degrees)) * 2) / 2,
                      'expr': None})
        for _g, _gate in _base_sim.fredkin_gates.items()
    }
    return angle_state, base_config, gate_names, load_config, mode_pick, units_pick


@app.cell(hide_code=True)
def _(angle_state, base_config, gate_names, math, mo, mode_pick, qn, units_pick):
    def _slider_cb(_g):
        def _cb(_v):
            angle_state[_g][1]({'deg': float(_v), 'expr': None})
        return _cb

    def _text_cb(_g):
        def _cb(_raw):
            _txt = (_raw or '').strip().rstrip('º°').strip()
            if not _txt:
                return
            try:
                _num = float(_txt)
                _deg = _num if units_pick.value == 'degrees' else math.degrees(_num)
                angle_state[_g][1]({'deg': _deg, 'expr': None})
                return
            except ValueError:
                pass
            try:
                _rad = float(qn.qify(_txt))  # symbolic expression, radians
                angle_state[_g][1]({'deg': math.degrees(_rad), 'expr': _txt})
            except Exception:  # noqa: BLE001 — unparseable: keep previous value
                pass
        return _cb

    _rows = []
    for _g in gate_names:
        _cur = angle_state[_g][0]()
        _slider = mo.ui.slider(
            -180, 180, step=0.5,
            value=max(-180.0, min(180.0, round(_cur['deg'] * 2) / 2)),
            label=f'**{_g}**', show_value=True, full_width=True,
            on_change=_slider_cb(_g))
        _text = mo.ui.text(
            value=_cur['expr'] if _cur['expr'] else f"{_cur['deg']:.1f}º",
            on_change=_text_cb(_g))
        _rows.append(mo.hstack([_slider, _text], widths=[5, 1], align='center'))
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
def _(
    CalcMode,
    Simulation,
    angle_state,
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
        _cur = angle_state[_g][0]()
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
def _(cmath, mo, qn):
    def latex_weight(w) -> str:
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
            parts.append(f'{_re:.4g}')
        if abs(_im) > 1e-12:
            sign = '-' if _im < 0 else ('+' if parts else '')
            parts.append(f'{sign}{abs(_im):.4g}i')
        return ''.join(parts) if parts else '0'

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
def _(latex_weight, md_table, mo, phase_deg, short_config, sim):
    _rows = []
    for _p in sorted(sim.result_space.index.values(),
                     key=lambda x: -float(x.probability)):
        _rows.append((
            f'`{short_config(_p).replace("|", " ")}`',
            f'${latex_weight(_p.weight)}$',
            f'{float(_p.probability):.4f}',
            f'{phase_deg(_p.weight):+.1f}º',
        ))
    mo.md('### Final worlds\n' +
          md_table(['configuration', 'weight $w$', r'$\lvert w\rvert^2$', 'phase'],
                   _rows))
    return


@app.cell(hide_code=True)
def _(latex_weight, mo, short_config, sim):
    _lines = []
    for _p in sorted(sim.result_space.index.values(),
                     key=lambda x: -float(x.probability)):
        _cfg = short_config(_p).replace('|', r'\;')
        _lines.append(
            rf"w(\texttt{{{_cfg}}}) &= {latex_weight(_p.weight)}"
            rf" &\quad \lvert w\rvert^2 &= {float(_p.probability):.4f} \\")
    _latex = '$$\n\\begin{aligned}\n' + '\n'.join(_lines) + '\n\\end{aligned}\n$$'
    mo.accordion({'## Final worlds (LaTeX)': mo.md(_latex)})
    return


@app.cell(hide_code=True)
def _(md_table, mo, sim):
    _pkey = {}
    for _p in sim.result_space.index.values():
        _prob = float(_p.probability)
        for _name, _coord in _p.coords.items():
            _key = f'{_coord.pkey}@{_coord.position.origin}'
            _pkey[_key] = _pkey.get(_key, 0.0) + _prob
    _rows = [(f'`{_k}`', f'{_v:.4f}') for _k, _v in sorted(_pkey.items())]
    mo.accordion({
        '## Marginal probabilities (particle, sign, position)':
            mo.md(md_table(['coordinate', 'probability'], _rows))
    })
    return


@app.cell
def _(mo, sim):
    # Depends on sim, so it refreshes on every Run (runs are now explicit,
    # so the pdflatex cost is paid once per Run, not per slider move).
    from multiworld.circuit_diagram import render_diagram, spec_from_simulation
    try:
        _overrides = {_g: f'{float(_gate.atheta.degrees):.1f}°'
                      for _g, _gate in sim.fredkin_gates.items()}
        _img = render_diagram(spec_from_simulation(sim), dpi=150,
                              angle_overrides=_overrides)
        _out = mo.image(_img, caption='circuit (TikZ)') if _img is not None else \
            mo.md('_TikZ render unavailable (needs pdflatex + imagemagick)_')
    except Exception as _exc:  # noqa: BLE001 — show, don't crash the app
        _out = mo.md(f'_TikZ diagram failed: {_exc}_')
    mo.accordion({'## Circuit diagram (TikZ)': _out})
    return


@app.cell(hide_code=True)
def _(diagram, mo, sim):
    try:
        _mermaid_src = str(diagram(sim, output_file=None, has_run=True))
        _out = mo.mermaid(_mermaid_src)
    except Exception as _exc:  # noqa: BLE001
        _out = mo.md(f'_Mermaid diagram failed: {_exc}_')
    mo.accordion({'## Gate network with port values (Mermaid)': _out})
    return


@app.cell(hide_code=True)
def _(mo, network_graph_figure, sim):
    from matplotlib import pyplot as _plt
    _fig = network_graph_figure(sim.all_points, sim)
    # deregister from pyplot so slider-driven reruns don't accumulate open
    # figures (the Figure object itself stays renderable)
    _plt.close(_fig)
    mo.accordion({'## Weight evolution (worlds × steps)': _fig}, lazy=True)
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
    mc_trials = mo.ui.slider(100, 100000, step=100, value=20000,
                             label='trials', show_value=True)
    mc_mode = mo.ui.dropdown(options=['terminal', 'path', 'both'],
                             value='both', label='mode')
    mc_seed = mo.ui.number(value=42, label='seed')
    mc_button = mo.ui.run_button(label='Run Monte Carlo')
    mo.hstack([mc_trials, mc_mode, mc_seed, mc_button], wrap=True)
    return mc_button, mc_mode, mc_seed, mc_trials


@app.cell(hide_code=True)
def _(
    mc_button,
    mc_mode,
    mc_seed,
    mc_trials,
    md_table,
    mo,
    run_monte_carlo,
    sim,
):
    mo.stop(not mc_button.value, mo.md('_press **Run Monte Carlo** to sample_'))
    _results = run_monte_carlo(sim, mc_trials.value, mode=mc_mode.value,
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
            _freq = _tally.get(_key, 0) / mc_trials.value
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
def _(mo, sim, supports_epr):
    mo.stop(not supports_epr(sim))
    mo.md(r"""
    ## EPR-Bell experiment
    Sweeps the measurement angles $(\theta_1, \theta_2)$ over the magic set
    $\{Q_a, Q_b, Q_c\}$ and tests **Bell**
    ($d(a,c) \le d(a,b) + d(b,c)$) and **CHSH** ($|S| \le 2$).
    The intrinsic law is $d = \sin^2(\theta_1 - \theta_2)$.
    """)
    return


@app.cell(hide_code=True)
def _(mo, sim, supports_epr):
    mo.stop(not supports_epr(sim))
    epr_trials = mo.ui.slider(0, 50000, step=1000, value=10000,
                              label='trials per cell (0 = exact only)',
                              show_value=True)
    epr_button = mo.ui.run_button(label='Run EPR experiment')
    mo.hstack([epr_trials, epr_button])
    return epr_button, epr_trials


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
    ws_theta = mo.ui.slider(0, 90, step=0.5, value=30, label='θ (º)',
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
    math,
    pd,
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
                              _gate.cpair(qn.Complex(_w), twist=not ws_sign.value))
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
        width=420, height=420)
    # plain display (not mo.ui.altair_chart): no selection plumbing, and
    # with inline data no virtual-file churn on slider moves
    _chart
    return


if __name__ == "__main__":
    app.run()
