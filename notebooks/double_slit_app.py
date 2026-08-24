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
app = marimo.App(width="full", css_file="css/double_slit_app.css")


@app.cell(hide_code=True)
async def initialization():
    import math
    import random
    import sys
    from pathlib import Path

    import marimo as mo

    # Under Pyodide (the WASM export) the quantish package and its one
    # non-Pyodide dependency are installed from the bundled wheels
    # (deps=False — micropip would otherwise stall resolving
    # marimo/sympy from PyPI in the browser), and the Pyodide-shipped
    # packages the engine imports internally are loaded explicitly
    # (auto-loading only covers notebook-level imports). This app needs
    # no model files: its circuits are built in code.
    if sys.platform == 'emscripten':
        import micropip
        _base = str(mo.notebook_location())
        await micropip.install([
            f'{_base}/public/wheels/addict-2.4.0-py3-none-any.whl',
            f'{_base}/public/wheels/quantish-0.1.0-py3-none-any.whl',
        ], deps=False)
        await micropip.install(['sympy', 'scipy', 'networkx', 'pandas',
                                'altair', 'pyyaml'])

    import altair as alt
    import pandas as pd

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

    The [double-slit experiment](https://en.wikipedia.org/wiki/Double-slit_experiment) is a classic result in physics, first described by [Thomas Young](https://en.wikipedia.org/wiki/Thomas_Young_(scientist)) in 1801, supporting his contention that light consists of waves. More recently, it was discovered that electrons, atoms, and even molecules show the same behavior. With detectors for individual photons, this demonstrates in a striking way the principle of [wave-particle duality](https://en.wikipedia.org/wiki/Wave%E2%80%93particle_duality).

    This application is a demonstration of the double-slit phenomenon in the quantish framework.
    """)
    return


@app.cell(hide_code=True)
def _(DEFAULT_THETA_S, math, mo):
    """The comparison table's readability styles (black text, larger
    headers) live in css/double_slit_app.css, loaded via the App's css_file:
    a <style> tag emitted from a cell gets sanitized away."""
    _step_by_step = mo.md(r"""
    Two conventions are used throughout:
    - gate $g_1$'s **upper** switch output
    leads to the **left** slit ($S_1$) and its **lower** switch output to
    the **right** slit ($S_2$). 
    - Several wires route a particle through
    a **control input** (the slit boxes $S_n$, the blocks $B_n$, the
    recorder gate $g_4$, and the phase plate $g_p$). A control input never changes the particle
    passing through it–its occupancy decides only whether or not that gate
    swaps its switch wires. (One deliberate exception: a gate with a
    **phase** setting, like $g_p$, rotates the weight of every particle
    traversing it, control input included, without effecting amplitude.)

    | real-world experiment | quantish circuit |
    |---|:---|
    | a photon or electron, fired at the barrier | particle $p_1$, weight 1 |
    | the two slits | the two switch outputs of gate $g_1$ (angle 45°): upper for the left slit, lower for the right |
    | passing through both slits at once | $g_1$ splits $p_1$'s world into superposed configuration-space points, one per slit, each carrying part of the weight |
    | the two slits themselves | the boxes $S_1$ and $S_2$, entered through their control inputs (pass-throughs; they change no amplitudes) |
    | different path lengths from the two slits to screen position $x$ | the phase plate $g_p$ (an angle-0 gate with phase $\varphi(x)$) on the right slit's wire: it rotates the passing amplitude by $e^{i\varphi(x)}$ and changes nothing else |
    | the screen pixel at $x$ | the remerge gate $g_2$ (matched to the split) followed by the sign sorter $g_5$; a particle reaching the detector box $S$ is a hit at this pixel |
    | blocking slit $n$ | the block $B_n$ standing in that slit's place. The wire is diverted into it and those worlds never reach the screen |
    | a which-way detector at one slit | recorder particle $p_2$ enters gate $g_4$'s upper switch input, and the wire to the right slit passes through $g_4$'s `control` input on its way to $S_2$. In the worlds where $p_1$ heads for the right slit, the occupied control makes $g_4$ swap its switch wires and $p_2$ exits on the lower wire; in the other worlds it exits on the upper wire. $p_2$'s exit records which slit $p_1$ used, without touching $p_1$ |

    In optics, a *phase plate* it is a thin slip of transparent
    material inserted into one light path: the wave crosses it more
    slowly and comes out with its phase shifted but its brightness
    untouched (the trick behind Zernike's phase-contrast microscope).
    Our $g_p$ is its quantish counterpart: an angle-0 gate whose
    **phase** setting rotates every traversing weight by $e^{i\varphi}$.
    The book's gates have only a measurement angle — the phase setting is
    this simulator's one extension beyond chapter 4's physics, and its
    default of 0 leaves every circuit from the book exactly as printed.

    Why sweep a phase and not a gate angle? A gate's angle changes magnitudes
    and phase together, so sweeping any gate's angle changes even a single
    slit's throughput, a $\cos^2$ modulation that would show fringes even with
    only one slit open. The phase knob is different: $\lvert e^{i\varphi}\rvert = 1$,
    so $g_p$ can never change what a single path delivers, and anything
    the screen shows beyond a flat line is genuine two-path interference.

    And why the sorter, $g_5$? At the matched remerge, the relative phase
    does *not* steer $p_1$ between $g_2$'s output wires. Rather, it moves weight
    between the two sign components of the upper wire, and a position
    detector placed right there would see nothing. But a minus-sign
    particle entering a switch wire exits on the *other* wire, so the
    angle-0 gate $g_5$ turns the sign difference back into a position
    difference: plus-sign arrivals exit toward the detector $S$,
    minus-sign toward $D$. A plain position detector at $S$ then reads
    $P = \tfrac{1}{2}(1 + \cos\varphi)$: the fringes.
    """)

    _deg = math.degrees(DEFAULT_THETA_S)
    _curves = mo.md(rf"""
    A **condition** consists of a complete apparatus for one version of
    the experiment. Every condition contains the source particle $p_1$,
    the split gate $g_1$, the remerge gate $g_2$, and the sign sorter
    $g_5$; conditions differ in what stands at each slit ($S_n$ where it
    is open, the block $B_n$ where it is blocked) and, in the recorder
    condition only, in gate $g_4$, which couples the which-way particle
    $p_2$ to the right slit's wire. The four conditions (both open, left
    blocked, right blocked, recorder) are shown in the four networks
    drawn beneath their screens.

    **There is one engine run per screen pixel:** the pixel at $x$ is
    reached through path lengths that differ between the slits, and the
    phase plate $g_p$ carries that difference as its phase setting
    $\varphi(x) = f\pi x$ ($f$ = the fringes slider). For each $x$ the
    engine propagates $p_1$ (weight 1) through the circuit exactly: the
    split rule at $g_1$ (angle $\theta = {_deg:.0f}°$) divides $p_1$'s
    world into superposed configuration-space points headed for the two
    slits; the right slit's points pick up $e^{{i\varphi(x)}}$ at $g_p$;
    the matched remerge $g_2$ recombines whatever the engine's remerge
    rule allows to interfere; and $g_5$ sorts the result into the
    detectors $S$ and $D$. What the screen shows at $x$ is the
    **intensity** $\mathcal{{I}}(x)$: the probability that $p_1$ ends at
    $S$, the arrival rate a long exposure at that pixel records. (Intensity is designated by a script
    $\mathcal{{I}}$, to keep it clearly apart from the imaginary unit
    $i$.)

    - **Both slits**: the two slits' worlds interfere at $g_2$, and
      $\mathcal{{I}} = \tfrac{{1}}{{2}}\bigl(1 + \cos(f\pi x)\bigr)$:
      fringes from 0 to 1, peaking at 4 times the single-slit intensity,
      with true zeros where the worlds cancel.
    - **One slit blocked**: the other wire ends at its block $B_n$, and
      a pure phase cannot change a lone path's magnitude, so the resulting intensity
      $\mathcal{{I}} = \tfrac{{1}}{{4}}$ is flat.
    - **Recorder**: $p_2$'s position differs between the two slits'
      worlds, so the remerge rule forbids their interference. The cross
      term is structurally impossible and $\mathcal{{I}} =
      \tfrac{{1}}{{4}} + \tfrac{{1}}{{4}} = \tfrac{{1}}{{2}}$ is flat at
      exactly the classical sum, with both slits open.
    """)

    mo.accordion({'## Details\n\n<span style="font-size:0.85em">'
                  'how this model works</span>': mo.vstack([
        mo.accordion({'### A step-by-step explanation of the quantish '
                      'model vs. the real-world experiment':
                          _step_by_step}),
        mo.accordion({'### How each curve is computed': _curves}),
    ])})
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
        - **fringes**&#42; ($f$) controls how many bright fringes fit across
          the screen when both slits are open. We allow odd values only, so that the
          screen edges always sit on dark fringes.
        - **screen resolution** controls the granularity of each raster display.
        - **particles per volley** controls how many simulated particles will be fired at the apparatus with each press of **fire particles**.
        - **fire particles** does just that: it fires a volley in each of the four conditions displayed, and displays every particle that reaches the screen. Not all of them do: blocking a slit absorbs about half the volley, so those rasters fill half as fast. The hit counts in the titles keep score.
        - **reset screens** erases the raster displays.
        """)
        # Book-style footnote: a plain <details> element styled small by
        # the .qfootnote rules in css/double_slit_app.css (a marimo accordion
        # always renders at full prose size).
        note = mo.as_html(mo.md(r"""
        At screen position $x$ (running from $-1$ to $+1$), the phase
        plate on the right slit's wire is set to
        $\varphi(x) = f\pi x$, so the relative phase between
        the two slits advances through $f$ full turns across the screen, and
        the open-slits intensity
        $\mathcal{I}(x) = \tfrac{1}{2}\bigl(1 + \cos(f\pi x)\bigr)$ shows
        exactly $f$ bright fringes, with the central one pinned at $x = 0$,
        where the two paths match. Only odd values are offered: the
        screen edges sit at phase $\pm f\pi$, so an even count would put
        half a bright fringe at each edge and the pattern would read as
        $f$ dark fringes instead. In a real apparatus this one number
        stands in for the slit geometry. The phase difference there is about
        $2\pi d x / (\lambda L)$ for slit separation $d$, wavelength
        $\lambda$, and screen distance $L$, so wider spacing, a shorter
        wavelength, or a closer screen will all put more fringes on the screen.
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
    fringes = mo.ui.slider(steps=[1, 3, 5, 7, 9], value=3, label='fringes',
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

    (best viewed with a wide window on a large screen)
    """)
    return


@app.cell(hide_code=True)
def _(alt, curves, diagrams, hits_get, mo, pd, xs):
    def _panel(title, curve, hits, width=380):
        _screen = alt.Chart(pd.DataFrame({
            'x': [h[0] for h in hits],
            'y': [h[1] for h in hits],
        })).mark_circle(size=6, color='#f5f0c0', opacity=0.65).encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]), axis=None),
            y=alt.Y('y:Q', scale=alt.Scale(domain=[0, 1]), axis=None),
        ).properties(
            width=width, height=190,
            title=f'{title} ({len(hits)} hits)',
            view=alt.ViewBackground(fill='#101018', stroke='#444'))
        _line = alt.Chart(pd.DataFrame({'x': xs, 'I': curve})).mark_line(
            color='#4477cc').encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-1, 1]),
                    axis=alt.Axis(title='screen position')),
            y=alt.Y('I:Q', scale=alt.Scale(domain=[0, 1.05]),
                    axis=alt.Axis(title='intensity')),
        ).properties(width=width, height=100)
        # bounds='flush' aligns the two plot AREAS exactly (axis labels and
        # titles no longer shift one chart relative to the other).
        return alt.vconcat(_screen, _line, spacing=4, bounds='flush')

    _hits = hits_get()

    # A 4×2 grid: one condition per row — the circuit on the left, the
    # screen/curve pair to its right.
    def _row(title, mode):
        return mo.hstack([diagrams[mode],
                          _panel(title, curves[mode], _hits[mode])],
                         align='center', justify='start', gap=1, wrap=True)

    mo.vstack([
        _row('both slits open', 'both'),
        _row('left slit blocked', 'slit2'),
        _row('right slit blocked', 'slit1'),
        _row('recorder on right slit (both open)', 'observed'),
    ], gap=2)
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
    remerge only when they agree in *every* particle). Here that gate
    really is in the circuit: each screen pixel is one engine run through
    the remerge gate $g_2$ (matched to the split at $g_1$, as in figure
    4.7), with the path-length difference to that pixel carried by the
    phase plate $g_p$ and the result sorted into the detectors by $g_5$.
    That is also exactly why the
    recorder kills the fringes: $p_2$ makes the two slits' worlds disagree, and the
    remerge rule then has nothing it is allowed to merge, and why
    blocking a slit (diverting its wire into the block $B_n$) gives a flat
    line. A single world has nothing to interfere with.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # shown in the editor only: in `marimo run` the code cells below are
    # hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Support code
    """) if mo.app_meta().mode != 'run' else None
    return


@app.cell(hide_code=True)
def _(mo):
    hits_get, hits_set = mo.state(
        {'slit1': [], 'both': [], 'slit2': [], 'observed': []})
    return hits_get, hits_set


@app.cell(hide_code=True)
def _(fringes, mo, n_points, screen_curve, screen_positions):
    """Exact screen intensities: one engine run per screen pixel per
    condition, the pixel's path difference set as the phase plate's
    phase."""
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
            from quantish.altair_diagram import circuit_chart
            return circuit_chart(
                slit_sim(mode), has_run=False, width=width,
                angle_overrides={
                    'g1': f'{math.degrees(DEFAULT_THETA_S):.0f}°',
                    'g2': f'{math.degrees(DEFAULT_THETA_S):.0f}°',
                    'g4': '0°', 'g5': '0°', 'gp': 'φ(x)'})
        except Exception as exc:  # noqa: BLE001--show, don't crash the app
            return mo.md(f'_diagram failed: {exc}_')

    # Grid layout: the circuit fills the row beside the narrower raster.
    diagrams = {mode: _diagram(mode, 1050 if mode == 'observed' else 900)
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
