"""Double-slit experiment — a quantish teaching demo.

Fires particles one at a time at a two-slit barrier built from Fredkin
gates and watches the interference pattern build up dot by dot — then
turns on a which-way observer and watches the fringes wash out.

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

    import multiworld.qnumber as qn
    from multiworld.qnumber import CalcMode

    CalcMode.default('Float')
    qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('multiworld').setLevel(logging.WARNING)

    from multiworld.double_slit import sample_hits, screen_curve
    return alt, mo, pd, random, sample_hits, screen_curve


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # The double-slit experiment, in quantish physics

    Particles are fired one at a time at a barrier with two slits and land
    on a screen. Each **screen position** is one run of a small Fredkin-gate
    interferometer: a *split* gate is the two slits, an *unsplit* gate whose
    angle encodes the path-length difference at that position recombines
    the arms, and a *test* gate is the screen pixel.

    - **Slits open, nobody watching** — each particle traverses *both* arms
      in superposed worlds that recombine: bright and dark **fringes**
      appear, one dot at a time. No single particle "makes" the pattern;
      the pattern is interference between worlds.
    - **Which-way observer on** — a second particle is coupled to one arm
      (it crosses a gate iff the first particle takes that arm). Nothing
      else changes, nobody "looks" — yet the recombination fails and the
      fringes **wash out**, because worlds that differ in the observer's
      record can no longer interfere.

    A quantish twist worth teaching: without the prepare/test gates that
    bracket the interferometer, the bare cos² pattern of this circuit
    *survives* observation — that version of the pattern is classically
    reproducible, and the genuinely quantum coherence is exactly the part
    the observer destroys.
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
    hits_get, hits_set = mo.state({'open': [], 'observed': []})
    return hits_get, hits_set


@app.cell(hide_code=True)
def _(envelope, fringes, mo, n_points, screen_curve):
    # Exact screen intensities from engine runs — one tiny simulation per
    # screen position, for each of the two setups.
    with mo.status.spinner(title='running the exact simulations…'):
        xs, open_curve = screen_curve(n_points.value, fringes.value,
                                      observe=False, envelope=envelope.value)
        _, observed_curve = screen_curve(n_points.value, fringes.value,
                                         observe=True, envelope=envelope.value)
    return observed_curve, open_curve, xs


@app.cell(hide_code=True)
def _(fire_btn, hits_get, hits_set, mo, observed_curve, open_curve, random,
      sample_hits, shots, xs):
    mo.stop(not fire_btn.value)
    _rng = random.Random()
    _cur = hits_get()
    hits_set({
        'open': _cur['open'] + sample_hits(xs, open_curve, shots.value, _rng),
        'observed': _cur['observed'] + sample_hits(xs, observed_curve,
                                                   shots.value, _rng),
    })
    return


@app.cell(hide_code=True)
def _(hits_get, hits_set, mo, reset_btn):
    mo.stop(not reset_btn.value)
    hits_get()  # subscription keeps ordering sane
    hits_set({'open': [], 'observed': []})
    return


@app.cell(hide_code=True)
def _(alt, hits_get, mo, observed_curve, open_curve, pd, xs):
    def _panel(title, curve, hits):
        _screen = alt.Chart(pd.DataFrame({
            'x': [h[0] for h in hits],
            'y': [h[1] for h in hits],
        })).mark_circle(size=6, color='#f5f0c0', opacity=0.65).encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]), axis=None),
            y=alt.Y('y:Q', scale=alt.Scale(domain=[0, 1]), axis=None),
        ).properties(width=430, height=190, title=f'{title} — {len(hits)} hits')
        _screen = _screen.configure_view(fill='#101018', stroke='#444')
        _line = alt.Chart(pd.DataFrame({'x': xs, 'P': curve})).mark_line(
            color='#4477cc').encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]),
                    axis=alt.Axis(title='screen position')),
            y=alt.Y('P:Q', scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(title='P(hit)')),
        ).properties(width=430, height=110)
        return mo.vstack([_screen, _line])

    _hits = hits_get()
    mo.hstack([
        _panel('slits open — unobserved', open_curve, _hits['open']),
        _panel('which-way observer on', observed_curve, _hits['observed']),
    ], justify='center', gap=2)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    *Every volley fires the same particles at both apparatuses. The dots are
    Monte Carlo draws from the exact world probabilities computed by the
    quantish engine — the left screen accumulates fringes; the right screen,
    identical except for one untouched observer particle, does not.*
    """)
    return


if __name__ == "__main__":
    app.run()
