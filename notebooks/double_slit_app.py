"""Double-slit experiment — a quantish teaching demo.

Fires particles one at a time at a two-slit barrier built from Fredkin
gates and watches the interference pattern build up dot by dot — then
blocks a slit and watches the fringes give way to the smooth single-slit
curve, exactly as in *Good and Real* figs. 4.12/4.13.

Run with:  marimo run notebooks/double_slit_app.py
"""

import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import random
    import sys
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import pandas as pd

    alt.data_transformers.enable('default')
    _repo = Path(__file__).resolve().parents[1]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    import logging

    import quantish.qnumber as qn
    from quantish.qnumber import CalcMode

    CalcMode.default('Float')
    qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('quantish').setLevel(logging.WARNING)

    from quantish.double_slit import sample_hits, screen_curve

    return alt, mo, pd, random, sample_hits, screen_curve


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # The double-slit experiment, in quantish physics

    Particles are fired **one at a time** at a barrier with two slits.
    In the quantish universe of *Good and Real* (ch. 4), the two slits are
    the two switch-wire inputs of a recombining Fredkin gate; each screen
    position is one run of the apparatus with a path-length offset;
    blocking a slit is diverting that arm away (figs. 4.12/4.13).

    - **Both slits open**: each particle traverses both slits in superposed
      worlds that interfere. Dark fringes appear where the worlds cancel —
      positions where *either slit alone* would deliver particles receive
      **none**. Bright fringes exceed what the two single-slit curves sum to.
    - **One slit blocked**: no superposition, no interference — the smooth
      single-slit curve, "the probability returns to normal."

    No single particle makes a pattern; every dot below is one particle,
    drawn from exact world-probabilities computed by the quantish engine.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    fringes = mo.ui.slider(1, 8, step=1, value=3, label='fringes',
                           show_value=True)
    n_points = mo.ui.slider(41, 161, step=20, value=81,
                            label='screen resolution', show_value=True)
    envelope = mo.ui.switch(value=True, label='diffraction envelope')
    shots = mo.ui.slider(steps=[100, 200, 500, 1000, 2000, 5000, 10000],
                         value=500, label='particles per volley',
                         show_value=True)
    fire_btn = mo.ui.run_button(label='🔫 fire particles')
    reset_btn = mo.ui.run_button(label='reset screens')
    mo.hstack([fringes, n_points, envelope, shots, fire_btn, reset_btn],
              wrap=True, justify='start')
    return envelope, fire_btn, fringes, n_points, reset_btn, shots


@app.cell(hide_code=True)
def _(mo):
    hits_get, hits_set = mo.state({'slit1': [], 'both': [], 'slit2': []})
    return hits_get, hits_set


@app.cell(hide_code=True)
def _(envelope, fringes, mo, n_points, screen_curve):
    # Exact screen intensities from engine runs — one tiny simulation per
    # screen position, for each of the three slit configurations.
    with mo.status.spinner(title='running the exact simulations…'):
        xs, both_curve = screen_curve(n_points.value, fringes.value,
                                      mode='both', envelope=envelope.value)
        _, slit1_curve = screen_curve(n_points.value, fringes.value,
                                      mode='slit1', envelope=envelope.value)
        _, slit2_curve = screen_curve(n_points.value, fringes.value,
                                      mode='slit2', envelope=envelope.value)
    return both_curve, slit1_curve, slit2_curve, xs


@app.cell(hide_code=True)
def _(
    both_curve,
    fire_btn,
    hits_get,
    hits_set,
    mo,
    random,
    sample_hits,
    shots,
    slit1_curve,
    slit2_curve,
    xs,
):
    mo.stop(not fire_btn.value)
    _rng = random.Random()
    _cur = hits_get()
    hits_set({
        'slit1': _cur['slit1'] + sample_hits(xs, slit1_curve, shots.value, _rng),
        'both': _cur['both'] + sample_hits(xs, both_curve, shots.value, _rng),
        'slit2': _cur['slit2'] + sample_hits(xs, slit2_curve, shots.value, _rng),
    })
    return


@app.cell(hide_code=True)
def _(hits_get, hits_set, mo, reset_btn):
    mo.stop(not reset_btn.value)
    hits_get()  # subscription keeps ordering sane
    hits_set({'slit1': [], 'both': [], 'slit2': []})
    return


@app.cell(hide_code=True)
def _(alt, both_curve, hits_get, mo, pd, slit1_curve, slit2_curve, xs):
    def _panel(title, curve, hits, width=300):
        _screen = alt.Chart(pd.DataFrame({
            'x': [h[0] for h in hits],
            'y': [h[1] for h in hits],
        })).mark_circle(size=6, color='#f5f0c0', opacity=0.65).encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]), axis=None),
            y=alt.Y('y:Q', scale=alt.Scale(domain=[0, 1]), axis=None),
        ).properties(width=width, height=180,
                     title=f'{title} — {len(hits)} hits')
        _screen = _screen.configure_view(fill='#101018', stroke='#444')
        _line = alt.Chart(pd.DataFrame({'x': xs, 'P': curve})).mark_line(
            color='#4477cc').encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]),
                    axis=alt.Axis(title='screen position')),
            y=alt.Y('P:Q', scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(title='P(hit)')),
        ).properties(width=width, height=100)
        return mo.vstack([_screen, _line], align='end')

    _hits = hits_get()
    mo.hstack([
        _panel('slit 2 blocked', slit1_curve, _hits['slit1']),
        _panel('both slits open', both_curve, _hits['both']),
        _panel('slit 1 blocked', slit2_curve, _hits['slit2']),
    ], justify='center', gap=1.5)
    return


@app.cell(hide_code=True)
def _(alt, both_curve, mo, pd, slit1_curve, slit2_curve, xs):
    # The punchline chart: what classical physics would predict for two
    # open slits (the sum of the single-slit curves) against what actually
    # happens — super-additive at bright fringes, ZERO at dark ones.
    _frame = pd.concat([
        pd.DataFrame({'x': xs, 'P': both_curve,
                      'curve': ['both slits (actual)'] * len(xs)}),
        pd.DataFrame({'x': xs,
                      'P': [a + b for a, b in zip(slit1_curve, slit2_curve)],
                      'curve': ['slit1 + slit2 (classical sum)'] * len(xs)}),
    ])
    _chart = alt.Chart(_frame).mark_line().encode(
        x=alt.X('x:Q', axis=alt.Axis(title='screen position')),
        y=alt.Y('P:Q', axis=alt.Axis(title='P(hit)')),
        color=alt.Color('curve:N', legend=alt.Legend(orient='top')),
        strokeDash=alt.condition(
            alt.datum.curve == 'slit1 + slit2 (classical sum)',
            alt.value([6, 4]), alt.value([0])),
    ).properties(width=940, height=180)
    mo.vstack([
        mo.md('### Interference is not additivity\n'
              'Opening the second slit *removes* particles from the dark '
              'fringes and delivers *more than both slits\' worth* to the '
              'bright ones:'),
        _chart,
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    *A follow-on lesson (figs. 4.14/4.15): keep both slits open but couple a
    which-way recorder particle to one arm — the fringes wash out even
    though nothing blocks either path. The engine module
    (`quantish.double_slit`, mode `'observed'`) already supports it.*
    """)
    return


if __name__ == "__main__":
    app.run()
