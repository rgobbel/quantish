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
        # dynamic import: a literal `import micropip` makes server-side
        # marimo install a mock micropip meta-path finder whose globals
        # die with the notebook session, breaking all later imports
        import importlib
        micropip = importlib.import_module('micropip')
        _base = str(mo.notebook_location())
        await micropip.install([
            f'{_base}/public/wheels/addict-2.4.0-py3-none-any.whl',
            f'{_base}/public/wheels/quantish-0.1.0-py3-none-any.whl',
        ], deps=False)
        await micropip.install(['sympy', 'scipy', 'networkx',
                                'pyyaml', 'anywidget'])
        # Under WASM, mo.app_meta().mode reports 'edit' for BOTH export
        # modes; the page's own mount config records which one this is.
        from pyodide.http import pyfetch
        _page = await (await pyfetch(f'{_base}/index.html')).string()
        _wasm_editor = '"mode": "edit"' in _page

    _repo = Path(__file__).resolve().parents[1]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    import logging

    import quantish.qnumber as qn
    from quantish.qnumber import CalcMode

    CalcMode.default('Float')
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('quantish').setLevel(logging.WARNING)

    from quantish.diagram_layout import diagram_geometry
    from quantish.builder_widget import (DiagramWidget, LinePlotWidget,
                                         ScreenPanelWidget)
    from quantish.double_slit import (DEFAULT_THETA_S, sample_hits,
                                      screen_curve, screen_positions,
                                      slit_sim)

    WASM_MODE = sys.platform == 'emscripten'
    EDITOR_UI = (_wasm_editor if WASM_MODE
                 else mo.app_meta().mode == 'edit')
    return (
        DEFAULT_THETA_S,
        DiagramWidget,
        EDITOR_UI,
        LinePlotWidget,
        ScreenPanelWidget,
        diagram_geometry,
        math,
        mo,
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
    recorder gate $g_4$, and the phase plate $\varphi$). A control input never changes the particle
    passing through it–its occupancy decides only whether or not that gate
    swaps its switch wires. (One deliberate exception: a gate with a
    **phase** setting, like $\varphi$, rotates the weight of every particle
    traversing it, control input included, without effecting amplitude.)

    | real-world experiment | quantish circuit |
    |---|:---|
    | a photon or electron, fired at the barrier | particle $p_1$, weight 1 |
    | the two slits | the two switch outputs of gate $g_1$ (angle 45°): upper for the left slit, lower for the right |
    | passing through both slits at once | $g_1$ splits $p_1$'s world into superposed configuration-space points, one per slit, each carrying part of the weight |
    | the two slits themselves | the boxes $S_1$ and $S_2$, entered through their control inputs (pass-throughs; they change no amplitudes) |
    | different path lengths from the two slits to screen position $x$ | the phase plate $\varphi$ (an angle-0 gate with phase $\varphi(x)$) on the right slit's wire: it rotates the passing amplitude by $e^{i\varphi(x)}$ and changes nothing else |
    | the screen pixel at $x$ | the remerge gate $g_2$ (matched to the split) followed by the sign sorter $g_5$; a particle reaching the detector box $S$ is a hit at this pixel |
    | blocking slit $n$ | the block $B_n$ standing in that slit's place. The wire is diverted into it and those worlds never reach the screen |
    | a which-way detector at one slit | recorder particle $p_2$ enters gate $g_4$'s upper switch input, and the wire to the right slit passes through $g_4$'s `control` input on its way to $S_2$. In the worlds where $p_1$ heads for the right slit, the occupied control makes $g_4$ swap its switch wires and $p_2$ exits on the lower wire; in the other worlds it exits on the upper wire. $p_2$'s exit records which slit $p_1$ used, without touching $p_1$ |

    In optics, a *phase plate* it is a thin slip of transparent
    material inserted into one light path: the wave crosses it more
    slowly and comes out with its phase shifted but its brightness
    untouched (the trick behind Zernike's phase-contrast microscope).
    Our $\varphi$ is its quantish counterpart: an angle-0 gate whose
    **phase** setting rotates every traversing weight by $e^{i\varphi}$.
    The book's gates have only a measurement angle — the phase setting is
    this simulator's one extension beyond chapter 4's physics, and its
    default of 0 leaves every circuit from the book exactly as printed.

    Why sweep a phase and not a gate angle? A gate's angle changes magnitudes
    and phase together, so sweeping any gate's angle changes even a single
    slit's throughput, a $\cos^2$ modulation that would show fringes even with
    only one slit open. The phase knob is different: $\lvert e^{i\varphi}\rvert = 1$,
    so $\varphi$ can never change what a single path delivers, and anything
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
    phase plate $\varphi$ carries that difference as its phase setting
    $\varphi(x) = f\pi x$ ($f$ = the fringes slider). For each $x$ the
    engine propagates $p_1$ (weight 1) through the circuit exactly: the
    split rule at $g_1$ (angle $\theta = {_deg:.0f}°$) divides $p_1$'s
    world into superposed configuration-space points headed for the two
    slits; the right slit's points pick up $e^{{i\varphi(x)}}$ at $\varphi$;
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
      worlds, so the remerge rule forbids their interference — the
      configuration-space points can never merge, so there is no
      interference term at all. The two paths' intensities simply add:
      $\mathcal{{I}} = \tfrac{{1}}{{4}} + \tfrac{{1}}{{4}} =
      \tfrac{{1}}{{2}}$, flat at exactly the classical sum, with both
      slits open.
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
        The single-slit and recorder curves have no interference term
        for the phase to act on, which is why the slider affects only
        the both-slits-open panel.
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

    These are best viewed with a wide window on a large screen. The black rectangles are screens, 
    which will light up where particles fired at the apparatus land.

    Each dot is one particle. Its **horizontal** position is drawn at
    random from that condition's exact intensity distribution — the
    curve under the screen — so the fringes emerge dot by dot, the way
    a long exposure builds them up. Its **vertical** position is
    uniformly random and purely decorative: the quantish model is
    one-dimensional, so all of the physics lives in $x$, and the $y$
    spread only makes the raster look like a physical screen.
    Interference never happens *between* dots — each particle's own
    superposed worlds interfere (in $x$) before it lands, one particle
    at a time.
    """)
    return


@app.cell(hide_code=True)
def _(ScreenPanelWidget, curves, diagrams, hits_get, mo, xs):
    def _panel(title, curve, hits, width=380):
        # one SVG for the dark screen and its intensity curve, so the
        # two plot areas stay flush by construction
        return mo.ui.anywidget(ScreenPanelWidget(data={
            'title': f'{title} ({len(hits)} hits)',
            'hits': [[h[0], h[1]] for h in hits],
            'curve': {'x': list(xs), 'y': list(curve)},
            'width': width,
        }))

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
def _(LinePlotWidget, curves, mo, xs):
    """What classical physics would predict for two
    open slits (the sum of the single-slit lines, which is also exactly
    the recorder curve) against what actually happens: super-additive at
    bright fringes, zero at dark ones."""
    _chart = mo.ui.anywidget(LinePlotWidget(data={
        'series': [
            {'name': 'both slits (actual)', 'x': list(xs),
             'y': list(curves['both']), 'color': '#4c78a8'},
            {'name': "slit1 + slit2 (classical sum)", 'x': list(xs),
             'y': [a + b for a, b in zip(curves['slit1'],
                                         curves['slit2'])],
             'color': '#f58518', 'dash': '6 4'},
        ],
        'xdomain': [-1, 1], 'xlabel': 'screen position',
        'ylabel': 'intensity', 'width': 940, 'height': 180,
    }))
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
    phase plate $\varphi$ and the result sorted into the detectors by $g_5$.
    That is also exactly why the
    recorder kills the fringes: $p_2$ makes the two slits' worlds disagree, and the
    remerge rule then has nothing it is allowed to merge, and why
    blocking a slit (diverting its wire into the block $B_n$) gives a flat
    line. A single world has nothing to interfere with.
    """)
    return


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    # the end-of-page mark (Ann's request): a small flourish so readers
    # know nothing further is loading. The editor genuinely has more
    # below (support code), so it appears in the app views only.
    mo.Html('<div style="text-align: center; color: #000; '
            'font-size: 1.6em; padding: 1.5em 0 1em;">&#8258;</div>'
            ) if not EDITOR_UI else None
    return


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    # shown in the editor only: in `marimo run` the code cells below
    # are hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Support code
    """) if EDITOR_UI else None
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
def _(
    DEFAULT_THETA_S,
    DiagramWidget,
    diagram_geometry,
    math,
    mo,
    slit_sim,
):
    """One circuit diagram per condition, rendered from the Simulation
    objects that yield the curves (Sn = slit n, Bn = a block in its place)."""
    def _diagram(mode, width):
        try:
            _g = diagram_geometry(
                slit_sim(mode), has_run=False,
                angle_overrides={
                    'g1': f'{math.degrees(DEFAULT_THETA_S):.0f}°',
                    'g2': f'{math.degrees(DEFAULT_THETA_S):.0f}°',
                    'g4': '0°', 'g5': '0°', 'φ': 'φ(x)'})
            # the grid rows size their own frames
            _g['frame_w'] = width
            _g['frame_h'] = 330
            return mo.ui.anywidget(DiagramWidget(geometry=_g))
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
