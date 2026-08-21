"""The double-slit experiment: A Quantish teaching demo.

**Note:** All references to figures use the numbering in the 2026 revision of chapter 4 of *Good and Real*.

In this notebook, particles are fired one at a time at a two-slit barrier built from Fredkin
gates, and we see the interference pattern building up dot by dot. Then
one slit is blocked, or a "which-way recorder" is attached to one source (as in figure 4.10), and
the fringes give way to flat single-slit light, as in
figures 4.13 to 4.15.

Each screen is shown together with a
diagram of the actual gate network that produced it.

Run with: ``marimo run notebooks/double_slit_app.py``
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full", css_file="double_slit_app.css")


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

    return (
        DEFAULT_THETA_S,
        alt,
        math,
        mo,
        pd,
        random,
        sample_hits,
        screen_curve,
        screen_positions,
        slit_sim,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # The double-slit experiment, in quantish physics

    Particles are fired one at a time at a barrier with two slits.
    In the quantish universe of *Good and Real* (chapter 4), the two slits
    are the two switch outputs of a splitting Fredkin gate; blocking a slit is
    diverting an output wire away (figures 4.13 and 4.14). The slits are idealized as
    infinitely narrow, so there is no single-slit diffraction envelope.

    Three conditions are simulated:

    1. **Both slits open**: each particle traverses both slits in superposed
      worlds that interfere. Dark fringes appear where the worlds cancel
      (positions where either slit alone would deliver particles receive
      none), and bright fringes receive up to twice what the two
      single-slit curves sum to.
    2. **One slit blocked**: there is only one world, so there is nothing to interfere with.
      We see a flat line at that slit's intensity.
    3. **Recorder on one slit** (figures 4.10 and 4.15): both slits stay open,
      but on the right-hand slit we place a particle whose output destination
      indicates which slit (i.e., which switch wire) the main input particle
      went through. The two outputs now end
      in distinguishable configurations, so the engine's remerge rule
      forbids their interference: the fringes wash out and the screen
      shows exactly the classical sum, though nothing blocked either path.

    Below each screen is a diagram of the actual gate network the
    engine ran to produce it. No single particle makes a pattern; every
    dot is one particle, drawn from exact world-amplitudes computed by
    the quantish engine.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Overview
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    """The comparison table's readability styles (black text, larger
    headers) live in double_slit_app.css, loaded via the App's css_file:
    a <style> tag emitted from a cell gets sanitized away."""
    mo.accordion(
        {'### Quantish vs. real-world: A step-by-step explanation': mo.md(r"""
    Two conventions are used throughout:
    - gate $g_1$'s **upper** switch output
    leads to the **left** slit ($S_1$) and its **lower** switch output to
    the **right** slit ($S_2$). 
    - Several wires route a particle through
    a **control input** (the slit boxes $S_n$, the blocks $B_n$, and the
    recorder gate $g_4$). A control input never changes the particle
    passing through it–its occupancy decides only whether or not that gate
    swaps its switch wires.

    | real-world experiment | quantish circuit |
    |---|:---|
    | a photon or electron, fired at the barrier | particle $p_1$, weight 1 |
    | the two slits | the two switch outputs of gate $g_1$ (angle 45°): upper for the left slit, lower for the right |
    | passing through both slits at once | $g_1$ splits $p_1$'s world into superposed configuration-space points, one per slit, each carrying part of the weight |
    | the two slits themselves | the boxes $S_1$ and $S_2$, entered through their control inputs (pass-throughs; they change no amplitudes) |
    | different path lengths from the two slits to screen position $x$ | a relative phase $e^{i\varphi(x)}$ applied to the right slit's amplitude. The flight to the screen is idealized, which is the one non-circuit ingredient |
    | the screen pixel at $x$ | a detector that recombines the two slits' amplitudes coherently (a remerge matched to the split) and registers $\lvert\text{amplitude}\rvert^2$ |
    | blocking slit $n$ | the block $B_n$ standing in that slit's place. The wire is diverted into it and those worlds never reach the screen |
    | a which-way detector at one slit | recorder particle $p_2$ enters gate $g_4$'s upper switch input, and the wire to the right slit passes through $g_4$'s **control** input on its way to $S_2$. In the worlds where $p_1$ heads for the right slit, the occupied control makes $g_4$ swap its switch wires and $p_2$ exits on the lower wire; in the other worlds it exits on the upper wire. $p_2$'s exit records which slit $p_1$ used, without touching $p_1$ |

    Phase must be applied *outside* the gate network because a
    quantish gate has no pure-phase knob: its angle sets magnitudes and
    phase together, so sweeping any gate's angle changes even a single
    slit's throughput, a $\cos^2$ modulation that would fake fringes with
    only one slit open. Path-length difference is therefore modeled where it
    physically lives: in the flight from the slits to the pixel.
    """)})
    return


@app.cell(hide_code=True)
def _(DEFAULT_THETA_S, math, mo):
    _deg = math.degrees(DEFAULT_THETA_S)
    mo.accordion({'### How each curve is computed': mo.md(rf"""
    A **condition** consists of a complete apparatus for one version of
    the experiment. Every condition contains the source particle $p_1$
    and the split gate $g_1$; conditions differ in what stands at each
    slit ($S_n$ where it is open, the block $B_n$ where it is blocked)
    and in the recorder condition only, in gate $g_4$, which couples the
    which-way particle $p_2$ to the right slit's wire. The four conditions (left
    blocked, both open, right blocked, recorder) are shown in the four
    networks drawn beneath their screens.

    **There is one engine run per condition:** The engine propagates $p_1$
    (weight 1) through the circuit exactly. At $g_1$ (angle
    $\theta = {_deg:.0f}°$) the split rule produces the two slits'
    amplitudes

    $$a_{{\text{{left}}}} = e^{{i\theta}}\cos\theta,\qquad
      a_{{\text{{right}}}} = i\,e^{{i\theta}}\sin\theta ,$$

    each arriving at its slit box as two configuration-space
    points (the split's same-sign and flipped-sign components), which a
    matched remerge sums coherently into that slit's amplitude.

    **From engine output to the screen:** Position $x$ assigns the right slit the propagation
    phase $\varphi(x) = f\pi x + \tfrac{{\pi}}{{2}}$ ($f$ = the fringes
    slider; the fixed $\tfrac{{\pi}}{{2}}$ cancels the crossed output's
    intrinsic phase so equal path lengths give the central bright
    fringe). What the screen shows at $x$ is the **intensity**
    $\mathcal{{I}}(x)$: the expected arrival rate there, the quantity a
    long exposure records. (Script $\mathcal{{I}}$, to keep it clearly
    apart from the imaginary unit $i$. It is a relative brightness, not a
    probability; it reaches 2 at the brightest fringe.) The screen sums
    amplitudes within each **interference group**: a set of
    configuration-space points whose coordinates agree for every particle
    except $p_1$. This grouping is the engine's own rule for which worlds
    may interfere. Amplitudes add coherently inside a group; separate
    groups contribute separately, as probabilities:

    $$\mathcal{{I}}(x) \;=\; \sum_{{\text{{groups}}}}\;\Bigl|\sum_{{\text{{slits}}}}
      a_{{\text{{slit}}}}\, e^{{i\varphi_{{\text{{slit}}}}(x)}}\Bigr|^2$$

    - **Both slits**: one group, two slits, so
      $\mathcal{{I}} = 1 + \cos(f\pi x)$: fringes from 0 to 2, peaking at **4×** the
      single-slit intensity, with true zeros where the worlds cancel.
    - **One slit blocked**: the other wire ends at its block $B_n$, so one
      amplitude remains, and $\mathcal{{I}} = \lvert a\rvert^2 = \tfrac{{1}}{{2}}$ is
      flat.
    - **Recorder**: $p_2$'s position differs between the two slits'
      worlds, so they cannot share a group. The cross term is
      structurally impossible and
      $\mathcal{{I}} = \lvert a_{{\text{{left}}}}\rvert^2 +
      \lvert a_{{\text{{right}}}}\rvert^2 = 1$ is flat at exactly the
      classical sum, with both slits open.
    """)})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Simulation controls
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    def _():
        mtext = mo.md(r"""
        - **fringes**&#42; ($f$) controls how many bright-dark cycles fit across
          the screen when both slits are open.
        - **screen resolution** controls the granularity of each raster display.
        - **particles per volley** controls how many simulated particles will be generated with each press of **fire particles**.
        - **fire particles** does just that: it generates a number of simulated particles, and displays the results for each of the four conditions shown.
        - **reset screens** erases the raster displays.
        """)
        # Book-style footnote: a plain <details> element styled small by
        # the .qfootnote rules in double_slit_app.css (a marimo accordion
        # always renders at full prose size).
        note = mo.as_html(mo.md(r"""
        At screen position $x$ (running from $-1$ to $+1$), the right slit's
        amplitude picks up the propagation phase
        $\varphi(x) = f\pi x + \tfrac{\pi}{2}$, so the relative phase between
        the two slits advances through $f$ full turns across the screen, and
        the open-slits intensity $\mathcal{I}(x) = 1 + \cos(f\pi x)$ shows
        exactly $f$ bright fringes. In a real apparatus this one number
        stands in for the slit geometry: the phase difference there is about
        $2\pi d x / (\lambda L)$ for slit separation $d$, wavelength
        $\lambda$, and screen distance $L$, so wider spacing, a shorter
        wavelength, or a closer screen all put more fringes on the screen.
        The single-slit and recorder curves contain no cross term for the
        phase to modulate, which is why the slider affects only the
        both-slits-open panel.
        """)).text
        ftext = mo.Html(
            '<div class="qfootnote"><details>'
            '<summary>&#42; about the <em>fringes</em> parameter</summary>'
            f'{note}</details></div>')
        return mtext, ftext

    _mtext, _ftext = _()
    fringes = mo.ui.slider(1, 8, step=1, value=3, label='fringes',
                           show_value=True)
    n_points = mo.ui.slider(41, 161, step=20, value=81,
                            label='screen resolution', show_value=True)
    shots = mo.ui.slider(steps=[100, 200, 500, 1000, 2000, 5000, 10000],
                         value=500, label='particles per volley',
                         show_value=True)
    fire_btn = mo.ui.run_button(label='🔫 fire particles')
    reset_btn = mo.ui.run_button(label='reset screens')
    mo.vstack([_mtext,
        mo.hstack([fringes, n_points, shots, fire_btn, reset_btn],
                  wrap=True, justify='start'),
        _ftext])
    return fire_btn, fringes, n_points, reset_btn, shots


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Simulation results
    """)
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
            title=f'{title} ({len(hits)} hits)',
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
        mo.md('#### …and with a which-way recorder on the right slit '
              '(both slits open):'),
        mo.hstack([
            _panel('recorder on right slit', curves['observed'],
                   _hits['observed']),
            diagrams['observed'],
        ], justify='center', gap=1.5, wrap=True, align='center'),
    ], gap=1.5)
    return


@app.cell(hide_code=True)
def _(alt, curves, mo, pd, xs):
    """The punchline chart: what classical physics would predict for two
    open slits (the sum of the single-slit lines, which is also exactly
    the recorder curve) against what actually happens: super-additive at
    bright fringes, zero at dark ones."""
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
        mo.md('### Note: Interference is not additivity\n'
              'Opening the second slit removes particles from the dark '
              'fringes by interference, and delivers *twice both slits\' worth* to the '
              'bright ones. If we couple a which-way recorder to one slit the '
              'actual curve collapses into the classical sum.'),
        _chart,
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    **Where the interference happens:** In quantish physics, only a
    recombining gate makes superposed worlds interfere (see figures 4.13 and 4.14: worlds
    remerge only when they agree in **every** particle). Each screen pixel
    here acts as a remerge gate (as in figure 4.7) matched to the split at $g_1$, with the
    path-length difference to that pixel entering as a relative phase
    between the two slits. This is the one idealized ingredient, since a quantish
    gate angle can't carry a pure phase. That is also exactly why the
    recorder kills the fringes: $p_2$ makes the two slits' worlds disagree, and the
    remerge rule then has nothing it is allowed to merge, and why
    blocking a slit (diverting its wire into the block $B_n$) gives a flat
    line. A single world has nothing to interfere with.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Support code
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    hits_get, hits_set = mo.state(
        {'slit1': [], 'both': [], 'slit2': [], 'observed': []})
    return hits_get, hits_set


@app.cell(hide_code=True)
def _(fringes, mo, n_points, screen_curve, screen_positions):
    """Exact screen intensities: one engine run per condition. The screen
    sweep is analytic in the resulting slit amplitudes."""
    with mo.status.spinner(title='running the exact simulations…'):
        curves = {mode: screen_curve(n_points.value, fringes.value, mode)[1]
                  for mode in ('slit1', 'both', 'slit2', 'observed')}
        xs = screen_positions(n_points.value)
    return curves, xs


@app.cell(hide_code=True)
def _(DEFAULT_THETA_S, math, mo, slit_sim):
    """One circuit diagram per condition, rendered from the Simulation
    objects that yield the curves (Sn = slit n, Bn = a block in its place)."""
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
        except Exception as exc:  # noqa: BLE001--show, don't crash the app
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


if __name__ == "__main__":
    app.run()
