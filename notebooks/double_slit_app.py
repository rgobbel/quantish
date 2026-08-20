"""Double-slit experiment — a quantish teaching demo.

Fires particles one at a time at a two-slit barrier built from Fredkin
gates and watches the interference pattern build up dot by dot — then
blocks a slit, or couples a which-way recorder to one arm, and watches
the fringes give way to flat single-slit light, as in *Good and Real*
figs. 4.13–4.15 (2026 numbering). Each screen is shown together with a
diagram of the actual gate network that produced it.

Run with:  marimo run notebooks/double_slit_app.py
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def initialization():
    import math
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

    from quantish.double_slit import (DEFAULT_THETA_S, sample_hits,
                                      screen_curve, screen_positions,
                                      slit_sim)

    return (DEFAULT_THETA_S, alt, math, mo, pd, random, sample_hits,
            screen_curve, screen_positions, slit_sim)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # The double-slit experiment, in quantish physics

    Particles are fired **one at a time** at a barrier with two slits.
    In the quantish universe of *Good and Real* (ch. 4), the two slits
    are the two arms of a splitting Fredkin gate; blocking a slit is
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
      but a which-way particle rides the right arm. The two arms now end
      in distinguishable configurations, so the engine's remerge rule
      forbids their interference: the fringes wash out and the screen
      shows exactly the classical sum — though nothing blocked either path.

    Below each screen is a diagram of the **actual gate network** the
    engine ran to produce it. No single particle makes a pattern; every
    dot is one particle, drawn from exact world-amplitudes computed by
    the quantish engine.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.accordion({'### The analogy, piece by piece': mo.md(r"""
    | real-world experiment | quantish circuit |
    |---|---|
    | a photon or electron, fired at the barrier | particle $p_1$, weight 1 |
    | the two slits | the two switch-wire outputs of gate $g_1$ (angle 45°) — the **left arm** (upper wire) and **right arm** (lower wire) |
    | passing through both slits at once | $g_1$ splits $p_1$'s world into superposed configuration-space points, one per arm, each carrying part of the weight |
    | the two slits themselves | the boxes $S_1$ and $S_2$, where the arms arrive (pass-throughs; they change no amplitudes) |
    | different path lengths from the two slits to screen position $x$ | a relative phase $e^{i\varphi(x)}$ applied to the right arm's amplitude — the flight to the screen is idealized, which is the one non-circuit ingredient |
    | the screen pixel at $x$ | a detector that recombines the two arms coherently (a remerge matched to the split) and registers $\lvert\text{amplitude}\rvert^2$ |
    | blocking slit $n$ | the block $B_n$ standing in that slit's place — the arm is diverted into it and those worlds never reach the screen |
    | a which-way detector at one slit | recorder particle $p_2$ on gate $g_4$'s upper wire, with the right arm wired to $g_4$'s **control**: exactly in the worlds where $p_1$ took the right arm, $p_2$ is switched to $g_4$'s lower wire |

    Why must the phase be applied *outside* the gate network? Because a
    quantish gate has no pure-phase knob: its angle sets magnitudes and
    phase together, so sweeping any gate's angle changes even a single
    arm's throughput (a $\cos^2$ modulation that would fake fringes with
    one slit open). Path-length difference is therefore modeled where it
    physically lives — in the flight from the slits to the pixel.
    """)})
    return


@app.cell(hide_code=True)
def _(DEFAULT_THETA_S, math, mo):
    _deg = math.degrees(DEFAULT_THETA_S)
    mo.accordion({'### Exactly how each curve is computed': mo.md(rf"""
    **One engine run per condition.** The engine propagates $p_1$
    (weight 1) through the circuit exactly. At $g_1$ (angle
    $\theta = {_deg:.0f}°$) the split rule produces the two arms with
    amplitudes

    $$a_{{\text{{left}}}} = e^{{i\theta}}\cos\theta,\qquad
      a_{{\text{{right}}}} = i\,e^{{i\theta}}\sin\theta ,$$

    each arriving at its screen-plane box as two configuration-space
    points (the split's same-sign and flipped-sign components), which a
    matched remerge sums coherently into the arm amplitude.

    **The screen.** Position $x$ assigns the right arm the propagation
    phase $\varphi(x) = f\pi x + \tfrac{{\pi}}{{2}}$ ($f$ = the fringes
    slider; the fixed $\tfrac{{\pi}}{{2}}$ cancels the crossed arm's
    intrinsic phase so equal path lengths give the central bright
    fringe). The intensity sums amplitudes **within classes** of
    configuration-space points that agree in every particle other than
    $p_1$ — the engine's own rule for which worlds may interfere:

    $$I(x) \;=\; \sum_{{\text{{classes}}}}\;\Bigl|\sum_{{\text{{arms}}}}
      a_{{\text{{arm}}}}\, e^{{i\varphi_{{\text{{arm}}}}(x)}}\Bigr|^2$$

    - **Both slits**: one class, two arms —
      $I = 1 + \cos(f\pi x)$: fringes from 0 to 2, peaking at **4×** the
      single-slit intensity, with true zeros where the worlds cancel.
    - **One slit blocked**: the other arm ends at its block $B_n$, so one
      amplitude remains — $I = \lvert a\rvert^2 = \tfrac{{1}}{{2}}$,
      flat.
    - **Recorder**: $p_2$'s position differs between the two arms'
      classes, so the arms cannot share a class; the cross term is
      structurally impossible and
      $I = \lvert a_{{\text{{left}}}}\rvert^2 +
      \lvert a_{{\text{{right}}}}\rvert^2 = 1$, flat — the classical
      sum, with both slits open.
    """)})
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
def _(fringes, mo, n_points, screen_curve, screen_positions):
    # Exact screen intensities — one engine run per condition; the screen
    # sweep is analytic in the resulting arm amplitudes.
    with mo.status.spinner(title='running the exact simulations…'):
        curves = {mode: screen_curve(n_points.value, fringes.value, mode)[1]
                  for mode in ('slit1', 'both', 'slit2', 'observed')}
        xs = screen_positions(n_points.value)
    return curves, xs


@app.cell(hide_code=True)
def _(DEFAULT_THETA_S, math, mo, slit_sim):
    # Circuit diagram per condition, rendered from the very Simulation
    # objects the curves come from (Sn = slit n, Bn = a block in its place).
    def _diagram(mode, width):
        try:
            from quantish.tikz_diagram import (render_diagram_svg,
                                               spec_from_simulation)
            svg = render_diagram_svg(
                spec_from_simulation(slit_sim(mode)),
                angle_overrides={
                    'g1': f'{math.degrees(DEFAULT_THETA_S):.0f}°',
                    'g4': '0°'})
            if svg is None:
                return mo.md('_diagram unavailable (needs pdflatex + pdf2svg)_')
            return mo.Html(
                f'<div class="qslit" style="width:{width}px; margin:auto">'
                f'<style>.qslit svg {{ width:100%; height:auto; }}</style>'
                f'{svg}</div>')
        except Exception as exc:  # noqa: BLE001 — show, don't crash the app
            return mo.md(f'_diagram failed: {exc}_')

    diagrams = {mode: _diagram(mode, 620 if mode == 'observed' else 330)
                for mode in ('slit1', 'both', 'slit2', 'observed')}
    return (diagrams,)


@app.cell(hide_code=True)
def _(
    curves,
    fire_btn,
    hits_get,
    hits_set,
    mo,
    random,
    sample_hits,
    shots,
    xs,
):
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
def _(alt, curves, diagrams, hits_get, mo, pd, xs):
    def _panel(title, curve, hits, width=300):
        _screen = alt.Chart(pd.DataFrame({
            'x': [h[0] for h in hits],
            'y': [h[1] for h in hits],
        })).mark_circle(size=6, color='#f5f0c0', opacity=0.65).encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]), axis=None),
            y=alt.Y('y:Q', scale=alt.Scale(domain=[0, 1]), axis=None),
        ).properties(
            width=width, height=170,
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

    def _column(title, mode):
        return mo.vstack([_panel(title, curves[mode], _hits[mode]),
                          diagrams[mode]], align='center', gap=0.5)

    mo.vstack([
        mo.hstack([
            _column('left slit blocked', 'slit2'),
            _column('both slits open', 'both'),
            _column('right slit blocked', 'slit1'),
        ], justify='center', gap=1.5, wrap=True),
        mo.md('#### …and with a which-way recorder on the right arm '
              '(both slits open):'),
        mo.hstack([
            _panel('recorder on right arm', curves['observed'],
                   _hits['observed']),
            diagrams['observed'],
        ], justify='center', gap=1.5, wrap=True, align='center'),
    ], gap=1.5)
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
    here acts as a remerge gate matched to the split at $g_1$, with the
    path-length difference to that pixel entering as a relative phase
    between the two arms — the one idealized ingredient, since a quantish
    gate angle can't carry a pure phase. That is also exactly why the
    recorder kills the fringes: $p_2$ makes the two arms disagree, and the
    remerge rule then has nothing it is allowed to merge — and why
    blocking a slit (diverting its arm into the block $B_n$) gives a flat
    line: a single world has nothing to interfere with.
    """)
    return


if __name__ == "__main__":
    app.run()
