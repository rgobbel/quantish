"""Double-slit experiment — a quantish teaching demo.

Fires particles one at a time at a two-slit barrier built from Fredkin
gates and watches the interference pattern build up dot by dot — then
blocks a slit, or couples a which-way recorder to one arm, and watches
the fringes give way to flat single-slit light, as in *Good and Real*
figs. 4.13–4.15 (2026 numbering).

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
    the two arms of a splitting Fredkin gate; each screen position receives
    the two arms with a path-length difference; blocking a slit is
    diverting an arm away (figs. 4.13/4.14). The slits are idealized as
    infinitely narrow, so there is no single-slit diffraction envelope.

    - **Both slits open**: each particle traverses both slits in superposed
      worlds that interfere. Dark fringes appear where the worlds cancel —
      positions where *either slit alone* would deliver particles receive
      **none** — and bright fringes receive up to **twice** what the two
      single-slit curves sum to.
    - **One slit blocked**: one world, nothing to interfere with — a flat
      line at that slit's intensity.
    - **Recorder on one arm** (fig 4.15's lesson): both slits stay open,
      but a which-way particle rides the lower arm. The two arms now end
      in distinguishable configurations, so the engine's remerge rule
      forbids their interference: the fringes wash out and the screen
      shows exactly the classical sum — though nothing blocked either path.

    No single particle makes a pattern; every dot below is one particle,
    drawn from exact world-amplitudes computed by the quantish engine.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    fringes = mo.ui.slider(1, 8, step=1, value=3, label='fringes',
                           show_value=True)
    n_points = mo.ui.slider(41, 161, step=20, value=81,
                            label='screen resolution', show_value=True)
    shots = mo.ui.slider(steps=[100, 200, 500, 1000, 2000, 5000, 10000],
                         value=500, label='particles per volley',
                         show_value=True)
    fire_btn = mo.ui.run_button(label='🔫 fire particles')
    reset_btn = mo.ui.run_button(label='reset screens')
    mo.hstack([fringes, n_points, shots, fire_btn, reset_btn],
              wrap=True, justify='start')
    return fire_btn, fringes, n_points, reset_btn, shots


@app.cell(hide_code=True)
def _(mo):
    hits_get, hits_set = mo.state(
        {'slit1': [], 'both': [], 'slit2': [], 'observed': []})
    return hits_get, hits_set


@app.cell(hide_code=True)
def _(fringes, mo, n_points, screen_curve):
    # Exact screen intensities — one engine run per condition; the screen
    # sweep is analytic in the resulting arm amplitudes.
    with mo.status.spinner(title='running the exact simulations…'):
        curves = {mode: screen_curve(n_points.value, fringes.value, mode)[1]
                  for mode in ('slit1', 'both', 'slit2', 'observed')}
        from quantish.double_slit import screen_positions
        xs = screen_positions(n_points.value)
    return curves, xs


@app.cell(hide_code=True)
def _(curves, fire_btn, hits_get, hits_set, random, sample_hits, shots, xs, mo):
    mo.stop(not fire_btn.value)
    _rng = random.Random()
    _cur = hits_get()
    hits_set({mode: _cur[mode] + sample_hits(xs, curve, shots.value, _rng)
              for mode, curve in curves.items()})
    return


@app.cell(hide_code=True)
def _(hits_get, hits_set, mo, reset_btn):
    mo.stop(not reset_btn.value)
    hits_get()  # subscription keeps ordering sane
    hits_set({'slit1': [], 'both': [], 'slit2': [], 'observed': []})
    return


@app.cell(hide_code=True)
def _(alt, curves, hits_get, mo, pd, xs):
    def _panel(title, curve, hits, width=280):
        _screen = alt.Chart(pd.DataFrame({
            'x': [h[0] for h in hits],
            'y': [h[1] for h in hits],
        })).mark_circle(size=6, color='#f5f0c0', opacity=0.65).encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]), axis=None),
            y=alt.Y('y:Q', scale=alt.Scale(domain=[0, 1]), axis=None),
        ).properties(
            width=width, height=180,
            title=f'{title} — {len(hits)} hits',
            view=alt.ViewBackground(fill='#101018', stroke='#444'))
        _line = alt.Chart(pd.DataFrame({'x': xs, 'I': curve})).mark_line(
            color='#4477cc').encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]),
                    axis=alt.Axis(title='screen position')),
            y=alt.Y('I:Q', scale=alt.Scale(domain=[0, 2.05]),
                    axis=alt.Axis(title='intensity')),
        ).properties(width=width, height=100)
        # bounds='flush' aligns the two plot AREAS exactly (axis labels and
        # titles no longer shift one chart relative to the other).
        return alt.vconcat(_screen, _line, spacing=4, bounds='flush')

    _hits = hits_get()
    mo.hstack([
        _panel('slit 2 blocked', curves['slit1'], _hits['slit1']),
        _panel('both slits open', curves['both'], _hits['both']),
        _panel('slit 1 blocked', curves['slit2'], _hits['slit2']),
        _panel('recorder on arm 2', curves['observed'], _hits['observed']),
    ], justify='center', gap=1.5, wrap=True)
    return


@app.cell(hide_code=True)
def _(alt, curves, mo, pd, xs):
    # The punchline chart: what classical physics would predict for two
    # open slits (the sum of the single-slit lines — also exactly the
    # recorder curve) against what actually happens: super-additive at
    # bright fringes, ZERO at dark ones.
    _frame = pd.concat([
        pd.DataFrame({'x': xs, 'I': curves['both'],
                      'curve': ['both slits (actual)'] * len(xs)}),
        pd.DataFrame({'x': xs,
                      'I': [a + b for a, b in zip(curves['slit1'],
                                                  curves['slit2'])],
                      'curve': ['slit1 + slit2 (classical sum)'] * len(xs)}),
    ])
    _chart = alt.Chart(_frame).mark_line().encode(
        x=alt.X('x:Q', axis=alt.Axis(title='screen position')),
        y=alt.Y('I:Q', axis=alt.Axis(title='intensity')),
        color=alt.Color('curve:N', legend=alt.Legend(orient='top')),
        strokeDash=alt.condition(
            alt.datum.curve == 'slit1 + slit2 (classical sum)',
            alt.value([6, 4]), alt.value([0])),
    ).properties(width=940, height=180)
    mo.vstack([
        mo.md('### Interference is not additivity\n'
              'Opening the second slit *removes* particles from the dark '
              'fringes and delivers *twice both slits\' worth* to the '
              'bright ones. Couple a which-way recorder to one arm and the '
              'actual curve collapses onto the classical sum.'),
        _chart,
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    *Where does the interference happen?* In quantish physics, only a
    recombining gate makes superposed worlds interfere (fig 4.13 — worlds
    remerge only when they agree in **every** particle). Each screen pixel
    here acts as a remerge gate matched to the split, with the path-length
    difference to that pixel entering as a relative phase between the two
    arms — the one idealized ingredient, since a quantish gate angle can't
    carry a pure phase. That is also exactly why the recorder kills the
    fringes: its particle makes the two arms disagree, and the remerge
    rule then has nothing it is allowed to merge.
    """)
    return


if __name__ == "__main__":
    app.run()
