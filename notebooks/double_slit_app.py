"""The double-slit experiment: A Quantish teaching demo.

**Note:** All references to figures use the numbering in the 2026 revision of chapter 4 of *Good and Real*.

In this notebook, particles are fired one at a time at a two-slit barrier built from Fredkin
gates, and we see the interference pattern building up particle by
particle. Then
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
        # the model library, frozen into the page at build time — the
        # engine reads the apparatus from models/extras/double_slit.yaml
        import json as _json

        from pyodide.http import pyfetch
        _base = str(mo.notebook_location())
        _resp = await pyfetch(f'{_base}/public/models.json')
        for _rel, _text in _json.loads(await _resp.string()).items():
            _p = Path('/wasm-data/models') / _rel
            _p.parent.mkdir(parents=True, exist_ok=True)
            _p.write_text(_text)
        # Under WASM, mo.app_meta().mode reports 'edit' for BOTH export
        # modes; the page's own mount config records which one this is.
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
    engine ran to produce it. Every
    particle's landing point is drawn from exact world-amplitudes
    computed by the quantish engine.
    """)
    return


@app.cell
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
    - gate $g_{split}$'s **upper** switch output
    leads to the **left** slit ($S_1$) and its **lower** switch output to
    the **right** slit ($S_2$). 
    - Several wires route a particle through
    a **control input** (the slit boxes $S_n$, the blocks $B_n$, the
    recorder gate $g_{obs}$, and the phase plate $\varphi$). A control input never changes the particle
    passing through it–its occupancy decides only whether or not that gate
    swaps its switch wires. (One deliberate exception: a gate with a
    **phase** setting, like $\varphi$, rotates the weight of every particle
    traversing it, control input included, without effecting amplitude.)

    #####  **Real-world vs. quantish model**

    | real-world experiment                                            | quantish circuit                                           |
    |------------------------------------------------------------------|:-----------------------------------------------------------|
    | a photon or electron, fired at the barrier                       | particle $p_1$, weight 1                                   |
    | the two slits                                                    | the two switch outputs of Fredkin gate $g_{split}$ (angle 45°): upper for the left slit, lower for the right   |
    | passing through both slits at once                               | Fredkin gate $g_{split}$ splits $p_1$'s world into superposed configuration-space points, one per slit, each carrying part of the weight |
    | the two slits themselves                                         | delay gates $S_1$ and $S_2$ (passthroughs) |
    | different path lengths from the two slits to screen position $x$ | the phase plate $\varphi$ rotates the passing amplitude by its *angle* parameter and changes nothing else                      |
    | the screen pixel at $x$                                          | the remerge gate $g_{merge}$ (matched to the split) followed by the sign sorter $g_{sort}$. A particle reaching the detector box $S$ is a hit at this pixel |
    | blocking slit $n$                                                | the block $B_n$ standing in that slit's place. The wire is diverted into it and those worlds never reach the screen |
    | a which-way detector at one slit                                 | recorder particle $p_2$ enters gate $g_{obs}$'s upper switch input, and the wire to the right slit passes through $g_{obs}$'s `control` input on its way to $S_2$. In the worlds where $p_1$ heads for the right slit, the occupied control makes $g_{obs}$ swap its switch wires and $p_2$ exits on the lower wire, otherwise on the upper wire. $p_2$'s exit records which slit $p_1$ used, without touching $p_1$ |

    ##### **Components of the model**

    - ##### The **splitter** $g_{split}$

        $g_{split}$ puts each input particle into superposition. Its 45° angle splits its input evenly between top and bottom, so left and right slits.

    - ##### **slits** $S_1$ and $S_2$ and **blocks** $B_1$ and $B_2$

        The slit and block gates are implemented by delay gates. Slits have connected outputs, blocks have none. They are not essential to the
        functioning of the circuit, and are added only to make the diagram easier to understand.

    - ##### The **phase plate** $\varphi$

        In optics, a *phase plate* it is a thin slip of transparent
        material inserted into one light path: the wave crosses it more
        slowly and comes out with its phase shifted but its brightness
        untouched (the trick behind Zernike's phase-contrast microscope).
        Our $\varphi$ is its quantish counterpart: a simple gate that rotates every traversing weight
        in the complex plane by its only parameter, an angle.

        We sweep phase rather than gate angle because changing a gate's angle changes magnitudes
        and phase together, so sweeping a gate's angle changes even a single
        slit's result, a modulation that would show fringes even with
        only one slit open. The phase setting is different: the phase plate changes angles without
        affecting amplitudes.

    - ##### The **merge** $g_{merge}$

        As we sweep $\varphi$ through a series of phase angles, the two
        inputs to $g_{merge}$ stay equal in size and change only in
        relative direction. The merge gate is the split gate applied
        again at the same angle, so at $\varphi = 0$ it exactly undoes
        the split (figure 4.7's lesson) and everything returns on the
        upper wire. At other phases the recombination is only partial —
        but the leftover does *not* exit on the lower wire, as one
        might expect. It stays on the upper wire with its **sign**
        flipped, which is why a sorter has to come next.

    - ##### The **sorter** $g_{sort}$

        At the matched remerge, the relative phase 
        doesn't steer $p_1$ between $g_{merge}$'s output wires. Rather, it moves weight
        between the two sign components of the upper wire, and a position
        detector placed right there would see nothing. But a minus-sign
        particle entering a switch wire exits on the opposite wire, so the
        angle-0 gate $g_{sort}$ turns the sign difference back into a position
        difference: plus-sign arrivals exit toward the detector $S$,
        minus-sign toward $D$. A plain position detector at $S$ then reads
        $P = \tfrac{1}{2}(1 + \cos\varphi)$: the fringes.

    - ##### the **recorder** $g_{obs}$

        A second particle, $p_2$, is input to $g_{obs}$'s upper input. The control input of $g_{obs}$ is fed by the right slit.
        If $p_1$ travels through the right slit, $p_2$ exits on the lower wire, otherwise on the upper wire, so $p_2$'s exit position records which slit $p_1$ went through without affecting $p_1$.


    """)

    _deg = math.degrees(DEFAULT_THETA_S)
    _curves = mo.md(rf"""
    A **condition** consists of a complete setup for one version of
    the experiment. Every condition contains the source particle $p_1$,
    the split gate $g_{{split}}$, the remerge gate $g_{{merge}}$, and the sign sorter
    $g_{{sort}}$; conditions differ in what stands at each slit ($S_n$ where it
    is open, the block $B_n$ where it is blocked) and, in the recorder
    condition only, in gate $g_{{obs}}$, which couples the which-way particle
    $p_2$ to the right slit's wire. The four conditions (both open, left
    blocked, right blocked, recorder) are shown in the four networks
    drawn beneath their screens.

    **There is one engine run per screen pixel:** the pixel at $x$ is
    reached through path lengths that differ between the slits, and the
    phase plate $\varphi$ carries that difference as its phase setting
    $\varphi(x) = f\pi x$ ($f$ = the fringes slider). For each $x$ the
    engine propagates $p_1$ (weight 1) through the circuit exactly: the
    split rule at $g_{{split}}$ (angle $\theta = {_deg:.0f}°$) divides $p_1$'s
    world into superposed configuration-space points headed for the two
    slits. The right slit's points pick up $e^{{i\varphi(x)}}$ at $\varphi$;
    the matched remerge $g_{{merge}}$ recombines whatever the engine's remerge
    rule allows to interfere; and $g_{{sort}}$ sorts the result into the
    detectors $S$ and $D$. What the screen shows at $x$ is the
    **intensity** $\mathcal{{I}}(x)$: the probability that $p_1$ ends at
    $S$, the arrival rate a long exposure at that pixel records. (Intensity is designated by a script
    $\mathcal{{I}}$, to keep it clearly apart from the imaginary unit
    $i$.). $y$ coordinates are chosen from a uniform random distribution.

    ##### **Conditions**

    - **Both slits**: the two slits' worlds interfere at $g_{{merge}}$. Where
      the fringes come from: each slit delivers a weight to this
      pixel — draw it as an arrow of length $\tfrac{{1}}{{2}}$. Weights
      have direction as well as magnitude, and the phase plate turns the
      right slit's arrow by $\varphi(x) = f\pi x$ without changing its
      magnitude. The pixel's brightness is the squared length of the two
      arrows added tip to tail:
      $\tfrac{{1}}{{4}} + \tfrac{{1}}{{4}} +
      2\cdot\tfrac{{1}}{{2}}\cdot\tfrac{{1}}{{2}}\cos\varphi$ —
      what each slit would deliver alone, plus a third piece set by the
      angle between the arrows. Arrows pointing the same way reinforce:
      $\mathcal{{I}} = 1$, four times what one slit alone delivers.
      Opposed arrows cancel: $\mathcal{{I}} = 0$. In between,
      $\mathcal{{I}} = \tfrac{{1}}{{2}}\bigl(1 + \cos(f\pi x)\bigr)$: the
      fringes.
          <span style="font-size:0.85em">*(Note: Optics texts write the same law
      in intensities: $\mathcal{{I}} = \mathcal{{I}}_{{left}} + \mathcal{{I}}_{{right}} +
      2\sqrt{{\mathcal{{I}}_{{left}} \mathcal{{I}}_{{right}}}}\cos\varphi$.)*</span>
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
        - **fire particles** does just that: it fires a volley in each of the four conditions displayed, and displays every particle that reaches the screen. Not all of them do: blocking a slit absorbs about half the volley, so those rasters fill half as fast. The hit counts in the titles record how many particles went through in each condition.
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
    # gate-angle experiments: break the ideal conditions and watch
    theta_split_sl = mo.ui.slider(0, 90, step=5, value=45,
                                  label='θ split (°)', show_value=True)
    theta_merge_sl = mo.ui.slider(0, 90, step=5, value=45,
                                  label='θ merge (°)', show_value=True)
    theta_sort_sl = mo.ui.slider(0, 90, step=5, value=0,
                                label='θ sorter (°)', show_value=True)
    # .gates-note (css/double_slit_app.css) keeps the lead-in line snug
    # against its list
    _gates_note = mo.Html('<div class="gates-note">' + mo.md("""
    _Gate angles:_
    - _an unequal split (θ split ≠ 45°) fills in the dark fringes_
    - _a mismatched merge (θ merge ≠ θ split) reduces the maximum intensity_
    - _changing the sorter angle reduces the contrast between high and low intensities._
    """).text + '</div>')
    mo.vstack([_mtext,
        mo.hstack([fringes, n_points, shots, fire_btn, reset_btn],
                  wrap=True, justify='start'),
        mo.accordion({'Implementation-level controls': mo.vstack([
            mo.hstack([theta_split_sl, theta_merge_sl, theta_sort_sl],
                      wrap=True, justify='start'),
            _gates_note])}),
        _ftext])
    return (
        fire_btn,
        fringes,
        n_points,
        reset_btn,
        shots,
        theta_merge_sl,
        theta_sort_sl,
        theta_split_sl,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Simulation results

    These are best viewed with a wide window on a large screen. The black rectangles are screens,
    which will light up where particles fired at the apparatus land.

    Each particle brightens the pixel where it lands, like a grain of
    photographic film: a pixel's first hit turns it dim gray, and
    repeated hits build it toward white. The **horizontal** landing
    position is drawn at random from that condition's exact intensity
    distribution — the curve under the screen — so the fringes develop
    out of the dark, the way a long exposure builds them up. The
    **vertical** position is uniformly random and purely decorative:
    the quantish model is one-dimensional, so all of the physics lives
    in $x$, and the $y$ spread only makes the screen look like a
    physical screen. Interference never happens *between* particles —
    each particle's own superposed worlds interfere (in $x$) before it
    lands, one particle at a time.
    """)
    return


@app.cell(hide_code=True)
def _(MODES, PANEL_TITLES, curves, hit_store, panel_widgets, xs):
    # a curve change rebuilds each panel in place; the client replays
    # the accumulated hits from this baseline
    for _m in MODES:
        panel_widgets[_m].data = {
            'title': PANEL_TITLES[_m],
            'curve': {'x': list(xs), 'y': list(curves[_m])},
            'width': 380,
            'hits': [list(_p) for _p in hit_store['hits'][_m]],
        }
    return


@app.cell(hide_code=True)
def _(diagrams, mo, panels):
    # A 4×2 grid: one condition per row — the circuit on the left, the
    # screen/curve pair to its right.
    def _row(mode):
        return mo.hstack([diagrams[mode], panels[mode]],
                         align='center', justify='start', gap=1,
                         wrap=True)

    mo.vstack([_row('both'), _row('slit2'), _row('slit1'),
               _row('observed')], gap=2)
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
    the remerge gate $g_{merge}$ (matched to the split at $g_{split}$, as in figure
    4.7), with the effective path-length difference to that pixel carried by the
    phase plate $\varphi$ and the result sorted into the detectors by $g_{sort}$.
    That is also exactly why the
    recorder kills the fringes: $p_2$ makes the two slits' worlds disagree, and the
    remerge rule then has nothing it is allowed to merge with. This is why
    blocking a slit gives a flat
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
def _(ScreenPanelWidget, mo):
    # Persistent screen panels: created once and updated in place.
    # Each volley streams only its NEW hits to the client, which adds
    # them into its raster; hit_store keeps the accumulated history as
    # the rebuild baseline (remounts, curve changes).
    MODES = ('both', 'slit2', 'slit1', 'observed')
    PANEL_TITLES = {'both': 'both slits open',
                    'slit2': 'left slit blocked',
                    'slit1': 'right slit blocked',
                    'observed': 'recorder on right slit (both open)'}
    panel_widgets = {_m: ScreenPanelWidget() for _m in MODES}
    panels = {_m: mo.ui.anywidget(_w)
              for _m, _w in panel_widgets.items()}
    hit_store = {'seq': 0, 'hits': {_m: [] for _m in MODES}}
    return MODES, PANEL_TITLES, hit_store, panel_widgets, panels


@app.cell(hide_code=True)
def _(
    fringes,
    math,
    mo,
    n_points,
    screen_curve,
    screen_positions,
    theta_merge_sl,
    theta_sort_sl,
    theta_split_sl,
):
    """Exact screen intensities: one engine run per screen pixel per
    condition, the pixel's path difference set as the phase plate's
    phase and the gate angles taken from the sliders."""
    with mo.status.spinner(title='running the exact simulations…'):
        curves = {mode: screen_curve(
                      n_points.value, fringes.value, mode,
                      theta_s=math.radians(theta_split_sl.value),
                      theta_merge=math.radians(theta_merge_sl.value),
                      theta_sort=math.radians(theta_sort_sl.value))[1]
                  for mode in ('slit1', 'both', 'slit2', 'observed')}
        xs = screen_positions(n_points.value)
    return curves, xs


@app.cell(hide_code=True)
def _(
    DiagramWidget,
    diagram_geometry,
    math,
    mo,
    slit_sim,
    theta_merge_sl,
    theta_sort_sl,
    theta_split_sl,
):
    """One circuit diagram per condition, rendered from the Simulation
    objects that yield the curves (Sn = slit n, Bn = a block in its place)."""
    def _diagram(mode, width):
        try:
            _g = diagram_geometry(
                slit_sim(mode,
                         theta_s=math.radians(theta_split_sl.value),
                         theta_merge=math.radians(theta_merge_sl.value),
                         theta_sort=math.radians(theta_sort_sl.value)),
                has_run=False,
                angle_overrides={
                    'g_split': f'{theta_split_sl.value:.0f}°',
                    'g_merge': f'{theta_merge_sl.value:.0f}°',
                    'g_obs': '0°',
                    'g_sort': f'{theta_sort_sl.value:.0f}°', 'φ': 'φ(x)'})
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
    MODES,
    curves,
    fire_btn,
    hit_store,
    mo,
    panel_widgets,
    random,
    sample_hits,
    shots,
    xs,
):
    mo.stop(not fire_btn.value)
    _rng = random.Random()
    hit_store['seq'] += 1
    for _m in MODES:
        _new = sample_hits(xs, curves[_m], shots.value, _rng)
        hit_store['hits'][_m].extend(_new)
        panel_widgets[_m].hits_chunk = {
            'seq': hit_store['seq'],
            'pts': [list(_p) for _p in _new],
            'total': len(hit_store['hits'][_m])}
    return


@app.cell(hide_code=True)
def _(MODES, hit_store, mo, panel_widgets, reset_btn):
    mo.stop(not reset_btn.value)
    hit_store['seq'] += 1
    for _m in MODES:
        hit_store['hits'][_m] = []
        panel_widgets[_m].hits_chunk = {'seq': hit_store['seq'],
                                        'reset': True}
    return


if __name__ == "__main__":
    app.run()
