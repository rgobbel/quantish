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
    # (auto-loading only covers notebook-level imports). The model
    # library is materialized too: the engine reads each condition's
    # circuit from its models/extras/double_slit*.yaml file.
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
        # engine reads the four conditions from models/extras/
        # double_slit*.yaml (quantish.double_slit.MODEL_FILES)
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

    from quantish.qnumber import CalcMode

    CalcMode.default('Float')
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('quantish').setLevel(logging.WARNING)

    from quantish.builder_widget import (
        DiagramWidget,
        LinePlotWidget,
        ScreenPanelWidget,
    )
    from quantish.diagram_layout import diagram_geometry
    from quantish.double_slit import (
        DEFAULT_THETA_S,
        sample_hits,
        screen_curve,
        screen_curves_by_sign,
        screen_positions,
        slit_sim,
    )

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
        screen_curves_by_sign,
        screen_positions,
        slit_sim,
        sys,
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


@app.cell(hide_code=True)
async def build_stamp(mo, sys):
    # Which build is this? The site build (tools/build_wasm_app.sh)
    # writes public/version.json beside the page; a development copy
    # says so instead.
    _stamp = 'development copy'
    if sys.platform == 'emscripten':
        try:
            import json as _json

            from pyodide.http import pyfetch as _pyfetch
            _v = _json.loads(await (await _pyfetch(
                f'{mo.notebook_location()}/public/version.json')).string())
            _stamp = f"build {_v['build']} · {_v['built_at']}"
        except Exception:  # noqa: BLE001 — an unstamped site shows nothing
            _stamp = ''
    mo.md(f'<span style="font-size: 0.8em; color: #444">{_stamp}</span>') \
        if _stamp else None


@app.cell
def _(mo):
    mo.md(r"""
    ## Overview

    The [double-slit experiment](https://en.wikipedia.org/wiki/Double-slit_experiment) is a classic result in physics, first described by [Thomas Young](https://en.wikipedia.org/wiki/Thomas_Young_(scientist)) in 1801, supporting his contention that light consists of waves. More recently, it was discovered that electrons, atoms, and even molecules show the same behavior. With detectors for individual photons, this demonstrates in a striking way the principle of [wave-particle duality](https://en.wikipedia.org/wiki/Wave%E2%80%93particle_duality).

    This application is a demonstration of the double-slit phenomenon in the quantish framework.
    """)


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
    traversing it, control input included, without affecting amplitude.)

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

        In optics, a *phase plate* is a thin slip of transparent
        material such as glass, inserted into one light path: the wave travels more
        slowly than it would in free space and comes out with its phase shifted but its brightness
        untouched or dimmed only very slightly (the idea behind Zernike's
        [phase-contrast microscope](https://en.wikipedia.org/wiki/Phase-contrast_microscopy)).
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

    _where = mo.md(r"""
    In quantish physics, only a recombining gate makes superposed
    worlds interfere (see figures 4.13 and 4.14: worlds remerge only
    when they agree in *every* particle). Here that gate really is in
    the circuit: each screen pixel is one engine run through the
    remerge gate $g_{merge}$ (matched to the split at $g_{split}$, as in
    figure 4.7), with the effective path-length difference to that
    pixel carried by the phase plate $\varphi$ and the result sorted
    into the detectors by $g_{sort}$. That is also exactly why the
    recorder kills the fringes: $p_2$ makes the two slits' worlds
    disagree, and the remerge rule then has nothing it is allowed to
    merge with. This is why blocking a slit gives a flat line. A single
    world has nothing to interfere with.
    """)

    mo.accordion({'## Details\n\n<span style="font-size:0.85em">'
                  'how this model works</span>': mo.vstack([
        mo.accordion({'### A step-by-step explanation of the quantish '
                      'model vs. the real-world experiment':
                          _step_by_step}),
        mo.accordion({'### Where the interference happens': _where}),
        mo.accordion({'### How each curve is computed': _curves}),
    ])})


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Simulation controls
    """)


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
                         value=1000, label='particles per volley',
                         show_value=True)
    fire_btn = mo.ui.run_button(label='🔫 fire particles')
    reset_btn = mo.ui.run_button(label='reset screens')
    # the tunable recorder's pre-gate angle (its own section below)
    theta_pre_sl = mo.ui.slider(0, 90, step=5, value=45,
                                label='θ pre (°)', show_value=True)
    theta_erase_sl = mo.ui.slider(0, 90, step=5, value=45,
                                  label='θ erase (°)', show_value=True)
    # The section accordions show these two sliders through plain
    # containers rather than by name: a cell that references a UI
    # element's variable reruns on every change, and re-rendering an
    # accordion re-mounts its diagram and screen. Only the engine cells
    # reference the sliders themselves.
    tunable_controls = mo.hstack([theta_pre_sl], justify='start')
    eraser_controls = mo.hstack([theta_erase_sl], justify='start')
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
    # How the curves under the screens are computed. While a slider
    # moves, each curve is redrawn from three engine runs: every path
    # crosses the phase plate at most once, so a pixel's intensity is
    # exactly A + B cos φ + C sin φ, and runs at φ = 0, π/2, π fix the
    # coefficients (double_slit.fringe_coefficients). Fire particles
    # and reset screens redraw them from one engine run per pixel. The
    # switch makes every redraw per pixel — slower, but the plot is
    # then the engine's per-pixel output at all times.
    exact_sw = mo.ui.switch(value=False,
                            label='one engine run per pixel on every change')
    _curves_note = mo.Html('<div class="gates-note">' + mo.md("""
    _Curves:_ _while a slider moves, the curve under each screen is
    redrawn from three engine runs — a pixel's intensity is exactly
    $A + B\\cos\\varphi + C\\sin\\varphi$, since every path crosses the
    phase plate at most once, and runs at $\\varphi = 0, \\pi/2, \\pi$
    fix the coefficients. **fire particles** and **reset screens**
    redraw it from one engine run per pixel; the switch does that on
    every change._
    """).text + '</div>')
    mo.vstack([_mtext,
        mo.hstack([fringes, n_points, shots, fire_btn, reset_btn],
                  wrap=True, justify='start'),
        mo.accordion({'Implementation-level controls': mo.vstack([
            mo.hstack([theta_split_sl, theta_merge_sl, theta_sort_sl],
                      wrap=True, justify='start'),
            _gates_note,
            exact_sw,
            _curves_note])}),
        _ftext])
    return (
        eraser_controls,
        exact_sw,
        fire_btn,
        fringes,
        n_points,
        reset_btn,
        shots,
        theta_erase_sl,
        theta_merge_sl,
        theta_pre_sl,
        theta_sort_sl,
        theta_split_sl,
        tunable_controls,
    )


@app.cell(hide_code=True)
def _(mo):
    # the how-it-works paragraph folds away so the first screen and the
    # fire button share the window
    mo.vstack([mo.md(r"""
    ## Simulation results

    These are best viewed with a wide window on a large screen. The black rectangles are screens,
    which will light up where particles fired at the apparatus land.
    """), mo.accordion({'### Details': mo.md(r"""
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
    """)})])


@app.cell(hide_code=True)
def _(MAIN_MODES, curves_main, set_panel_curves, xs):
    # A curve change redraws the affected panels' line areas in place;
    # the screens themselves redisplay only for a new grain (screen
    # resolution), a volley, or a reset. One cell per condition group,
    # so a slider only one group's model has a variable for (θ pre,
    # θ erase) leaves the other panels untouched.
    for _m in MAIN_MODES:
        set_panel_curves(_m, xs, curves_main[_m])


@app.cell(hide_code=True)
def _(curve_tunable, set_panel_curves, xs):
    set_panel_curves('tunable', xs, curve_tunable)


@app.cell(hide_code=True)
def _(curve_eraser, parts_eraser, set_panel_curves, xs):
    set_panel_curves('eraser', xs, curve_eraser, parts_eraser)


@app.cell(hide_code=True)
def _(diagrams, mo, panels):
    # A 4×2 grid: one condition per row — the circuit on the left, the
    # screen/curve pair to its right. The widgets are created once and
    # updated in place, so this cell never reruns.
    def _row(mode):
        return mo.hstack([diagrams[mode], panels[mode]],
                         align='center', justify='start', gap=1,
                         wrap=True)

    mo.vstack([_row('both'), _row('slit2'), _row('slit1'), _row('observed')],
              gap=2)


@app.cell(hide_code=True)
def _(diagrams, mo, panels, tunable_controls):
    # The tunable recorder — an approximate measurement — in its own
    # section: the explanation, its one control, and its row.
    _text = mo.md(r"""
    A fifth condition: the recorder circuit with one more gate,
    $g_{pre}$, on the recorder particle $p_2$'s path ahead of $g_{obs}$.
    At $g_{pre}$ the weight of $p_2$ splits: the straight component goes
    on to $g_{obs}$ and records which slit $p_1$ used, while the crossing
    component runs into a dead-end delay gate (*bypass*) and never
    meets $p_1$. The angle $\theta_{pre}$ sets the division.

    The two components of $p_2$ are separated along the $p_2$-position
    dimension of configuration space, so they never interfere with
    each other. Within the bypass component no record of $p_1$'s path
    exists, and $p_1$'s two slit branches reconverge at $g_{merge}$ and
    interfere exactly as with both slits open; within the recording
    component the observation is complete, so the branches stay
    separated and do not interfere, as in the recorder condition. The
    screen shows the weighted sum

    $$\mathcal{I} = \sin^2\theta_{pre}\,\cos^2\tfrac{\varphi}{2} + \tfrac{1}{2}\cos^2\theta_{pre},$$

    so the fringe visibility is $\sin^2\theta_{pre}$, the fraction of
    $p_2$'s weight that bypasses the recorder. $\theta_{pre} = 0$ is the
    recorder condition, $90°$ the both-slits-open condition, and $45°$
    gives half visibility.

    This is a quantish instance of what Everett's long thesis calls an
    *approximate measurement* — an observation that only partly
    correlates the observer with the observed — and of the
    complementarity between fringe visibility and which-way
    information. It goes beyond the observations of *Good and Real*
    chapter 4, all of which are complete. Compare the general case of
    the Mach–Zehnder interferometer in Wu (arXiv:2005.04812), Part I,
    where both beam-splitter mirrors are partial recorders.
    """)
    # .tight-prose (css/double_slit_app.css) closes up the paragraphs
    _text = mo.Html('<div class="tight-prose">' + _text.text + '</div>')
    mo.accordion({'### Tunable decoherence\n\n<span style="font-size:0.85em">'
                  'an approximate measurement: a recorder that only '
                  'partly records</span>': mo.vstack([
        _text,
        tunable_controls,
        mo.hstack([diagrams['tunable'], panels['tunable']],
                  align='center', justify='start', gap=1, wrap=True),
    ], gap=1)})


@app.cell(hide_code=True)
def _(diagrams, eraser_controls, mo, panels):
    # The quantum eraser in its own section: the explanation, its one
    # control, and its row (hits colored by the eraser's outcome).
    _text = mo.md(r"""
    A sixth condition: the recorder circuit with one more gate on the
    recorder particle's path. After $g_{obs}$ has swapped $p_2$ exactly
    when $p_1$ took the right slit, both of $p_2$'s possible wires feed
    the switch inputs of $g_{erase}$, and its two outputs end at the
    detectors $E_1$ and $E_2$. This is the quantish version of the
    delayed-choice quantum eraser of Kim et al. (2000), where the
    which-way paths of the idler photon are recombined on a beam
    splitter: here $g_{erase}$ is the beam splitter.

    At $\theta_{erase} = 45°$ each of $p_2$'s incoming wires splits
    evenly over both outgoing wires, so which detector $p_2$ reaches
    no longer tells which slit $p_1$ used, and neither does $p_2$'s
    sign taken alone. The record is not destroyed — a reversible gate
    keeps $p_2$'s two branch states orthogonal — but it is spread over
    $p_2$'s exit wire and sign jointly, where no single readout can
    recover it. Yet sorted by $p_2$'s *sign* the screen shows fringes:
    the hits with $p_2$ at plus sign follow $\tfrac{1}{2}\cos^2\tfrac{\varphi}{2}$
    and those at minus sign $\tfrac{1}{2}\sin^2\tfrac{\varphi}{2}$,
    whichever detector $p_2$ reached. The two patterns are
    complementary, and their sum is the recorder's flat line: the
    screen taken as a whole is as fringeless as in the recorder
    condition, which is why the erasure can be "chosen" after $p_1$ has
    hit the screen without changing anything there.

    On the film below, each hit is colored by $p_2$'s sign (orange for
    plus, blue for minus): the brightness is the flat total, the
    colors are the two fringe patterns. At $\theta_{erase} = 0$ the
    gate passes $p_2$ straight through and the condition is the plain
    recorder, every hit plus; between $0$ and $45°$ the minus-sign
    fringes keep full contrast while the plus-sign ones gain it.
    """)
    _text = mo.Html('<div class="tight-prose">' + _text.text + '</div>')
    mo.accordion({'### Quantum eraser\n\n<span style="font-size:0.85em">'
                  'the which-way record mixed away after the fact: '
                  'fringes return, one sorted subset at a time</span>':
                  mo.vstack([
        _text,
        eraser_controls,
        mo.hstack([diagrams['eraser'], panels['eraser']],
                  align='center', justify='start', gap=1, wrap=True),
    ], gap=1)})


@app.cell(hide_code=True)
def _(LinePlotWidget, mo):
    """What classical physics would predict for two open slits (the
    sum of the single-slit lines, which is also exactly the recorder
    curve) against what actually happens: super-additive at bright
    fringes, zero at dark ones. The chart widget is created here, once;
    the cell below feeds it the current curves, so a slider move
    updates the plot in place and this section never re-renders."""
    additivity_widget = LinePlotWidget(data={})
    mo.accordion({'#### Note: Interference is not additivity\n\n<span style='
                  '"font-size:0.85em">the classical sum of the single-slit '
                  'curves against what actually happens</span>': mo.vstack([
        mo.md('Opening the second slit removes particles from the dark '
              'fringes by interference, and delivers *twice both slits\' '
              'worth* to the bright ones. If we couple a which-way recorder '
              'to one slit the actual curve collapses into the classical '
              'sum.'),
        mo.ui.anywidget(additivity_widget),
    ], gap=1)})
    return (additivity_widget,)


@app.cell(hide_code=True)
def _(additivity_widget, curves_main, xs):
    additivity_widget.data = {
        'series': [
            {'name': 'both slits (actual)', 'x': list(xs),
             'y': list(curves_main['both']), 'color': '#4c78a8'},
            {'name': "slit1 + slit2 (classical sum)", 'x': list(xs),
             'y': [a + b for a, b in zip(curves_main['slit1'],
                                         curves_main['slit2'])],
             'color': '#f58518', 'dash': '6 4'},
        ],
        'xdomain': [-1, 1], 'xlabel': 'screen position',
        'ylabel': 'intensity', 'width': 940, 'height': 180,
    }


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    # the end-of-page mark (Ann's request): a small flourish so readers
    # know nothing further is loading. The editor genuinely has more
    # below (support code), so it appears in the app views only.
    mo.Html('<div style="text-align: center; color: #000; '
            'font-size: 1.6em; padding: 1.5em 0 1em;">&#8258;</div>'
            ) if not EDITOR_UI else None


@app.cell(hide_code=True)
def _(EDITOR_UI, mo):
    # shown in the editor only: in `marimo run` the code cells below
    # are hidden, so the heading would sit over nothing
    mo.md(r"""
    ## Support code
    """) if EDITOR_UI else None


@app.cell(hide_code=True)
def _(ScreenPanelWidget, mo):
    # Persistent screen panels: created once and updated in place.
    # Each volley streams only its NEW hits to the client, which adds
    # them into its raster; hit_store keeps the accumulated history as
    # the rebuild baseline (remounts, curve changes).
    # the four conditions of the main grid, plus the tunable recorder
    # in its own section; the panel machinery covers all five
    MAIN_MODES = ('both', 'slit2', 'slit1', 'observed')   # the grid
    MODES = MAIN_MODES + ('tunable', 'eraser')
    PANEL_TITLES = {'both': 'both slits open',
                    'slit2': 'left slit blocked',
                    'slit1': 'right slit blocked',
                    'observed': 'recorder on right slit (both open)',
                    'tunable': 'recorder with tunable decoherence',
                    'eraser': 'recorder with quantum eraser'}
    panel_widgets = {_m: ScreenPanelWidget() for _m in MODES}
    panels = {_m: mo.ui.anywidget(_w)
              for _m, _w in panel_widgets.items()}
    hit_store = {'seq': 0, 'hits': {_m: [] for _m in MODES}}

    panel_grain = {}   # mode -> the len(xs) its raster was built for
    # The settings the live curves were last computed for, as a plain
    # dict: the fire and reset cells read them from here instead of
    # from the sliders, so a slider move does not run those cells at
    # all (a cell that references a slider reruns on every change).
    current = {}

    def set_panel_curves(mode, xs, curve, parts=None):
        # New curves for a panel. Same grain: only the line area under
        # the screen redraws (the `curves` trait). A new grain: the
        # panel rebuilds from its baseline — title, curves, and every
        # hit so far — since the raster's pixel count follows len(xs).
        curves = {'x': list(xs), 'y': list(curve)}
        if parts:
            # a grouped condition: the film colors hits by group and
            # draws one curve per group under the total
            curves['parts'] = [{'name': name, 'y': list(ys)}
                               for name, ys in parts]
        if panel_grain.get(mode) == len(xs):
            panel_widgets[mode].curves = curves
            return
        panel_grain[mode] = len(xs)
        panel_widgets[mode].curves = curves
        panel_widgets[mode].data = {
            'title': PANEL_TITLES[mode],
            'curve': curves,
            'width': 380,
            'hits': [list(p) for p in hit_store['hits'][mode]],
        }

    return (
        MAIN_MODES,
        MODES,
        PANEL_TITLES,
        hit_store,
        panel_widgets,
        current,
        panels,
        set_panel_curves,
    )


@app.cell(hide_code=True)
def _(math, theta_merge_sl, theta_sort_sl, theta_split_sl):
    # the gate angles every condition shares, from the sliders
    main_angles = {'theta_s': math.radians(theta_split_sl.value),
                   'theta_merge': math.radians(theta_merge_sl.value),
                   'theta_sort': math.radians(theta_sort_sl.value)}
    return (main_angles,)


@app.cell(hide_code=True)
def _(exact_sw):
    # how the live curves are computed: the three-run reconstruction
    # (instant, exact) unless the switch asks for a run per pixel
    via = 'pixels' if exact_sw.value else 'fit'
    return (via,)


@app.cell(hide_code=True)
def _(
    MAIN_MODES,
    current,
    fringes,
    main_angles,
    n_points,
    screen_curve,
    screen_positions,
    via,
):
    """The live screen curves: the pixel's path difference is the phase
    plate's phase and the gate angles come from the sliders. One cell
    per condition group — the grid's four here, the tunable recorder
    and the eraser below — so a slider only one group depends on
    reruns only that group. `via` says whether each curve is the
    three-run reconstruction or one engine run per pixel; fire and
    reset always redraw per pixel."""
    # no spinner here: a transient output in this cell shifts the page,
    # and the live path is three engine runs per condition
    curves_main = {mode: screen_curve(n_points.value, fringes.value,
                                      mode, via=via, **main_angles)[1]
                   for mode in MAIN_MODES}
    xs = screen_positions(n_points.value)
    current.update(n=n_points.value, fringes=fringes.value,
                   main_angles=dict(main_angles))
    return curves_main, xs


@app.cell(hide_code=True)
def _(
    current,
    fringes,
    main_angles,
    math,
    n_points,
    screen_curve,
    theta_pre_sl,
    via,
):
    current['theta_pre'] = math.radians(theta_pre_sl.value)
    curve_tunable = screen_curve(
        n_points.value, fringes.value, 'tunable', via=via,
        theta_pre=current['theta_pre'], **main_angles)[1]
    return (curve_tunable,)


@app.cell(hide_code=True)
def _(
    current,
    fringes,
    main_angles,
    math,
    n_points,
    screen_curves_by_sign,
    theta_erase_sl,
    via,
):
    # the eraser's curve comes split by p2's sign (parts), its total
    # in curve_eraser
    current['theta_erase'] = math.radians(theta_erase_sl.value)
    _plus, _minus = screen_curves_by_sign(
        n_points.value, fringes.value, 'eraser', via=via,
        theta_erase=current['theta_erase'], **main_angles)[1]
    curve_eraser = [a + b for a, b in zip(_plus, _minus)]
    parts_eraser = [('+p₂', _plus), ('−p₂', _minus)]
    return curve_eraser, parts_eraser


@app.cell(hide_code=True)
def _(DiagramWidget, MODES, diagram_geometry, mo, slit_sim):
    """One circuit diagram per condition, rendered from the Simulation
    objects that yield the curves (Sn = slit n, Bn = a block in its
    place). The widgets are created once, here, at the models' own
    angles; the per-group cells below push new geometry into them when
    their sliders move (the widget redraws in place, keeping its view),
    so nothing else on the page re-renders."""
    DIAGRAM_WIDTH = {mode: 900 if mode in ('slit1', 'both', 'slit2')
                     else 1050 for mode in MODES}

    def diagram_geom(mode, angles, labels):
        # the grid rows size their own frames, and open with the
        # whole circuit in view (fit) rather than at natural scale
        _g = diagram_geometry(
            slit_sim(mode, **angles), has_run=False,
            angle_overrides={'g_obs': '0°', 'φ': 'φ(x)', **labels})
        _g['frame_w'] = DIAGRAM_WIDTH[mode]
        _g['frame_h'] = 330
        _g['fit'] = True
        return _g

    diagram_widgets = {mode: DiagramWidget(geometry=diagram_geom(mode, {}, {}))
                       for mode in MODES}
    diagrams = {mode: mo.ui.anywidget(w) for mode, w in diagram_widgets.items()}
    return diagram_geom, diagram_widgets, diagrams


@app.cell(hide_code=True)
def _(
    MAIN_MODES,
    diagram_geom,
    diagram_widgets,
    main_angles,
    theta_merge_sl,
    theta_sort_sl,
    theta_split_sl,
):
    # the shared gate angles: every diagram shows them
    main_labels = {'g_split': f'{theta_split_sl.value:.0f}°',
                   'g_merge': f'{theta_merge_sl.value:.0f}°',
                   'g_sort': f'{theta_sort_sl.value:.0f}°'}
    for _m in MAIN_MODES:
        diagram_widgets[_m].geometry = diagram_geom(_m, main_angles,
                                                   main_labels)
    return (main_labels,)


@app.cell(hide_code=True)
def _(diagram_geom, diagram_widgets, main_angles, main_labels, math, theta_pre_sl):
    diagram_widgets['tunable'].geometry = diagram_geom(
        'tunable',
        {**main_angles, 'theta_pre': math.radians(theta_pre_sl.value)},
        {**main_labels, 'g_pre': f'{theta_pre_sl.value:.0f}°'})


@app.cell(hide_code=True)
def _(
    diagram_geom,
    diagram_widgets,
    main_angles,
    main_labels,
    math,
    theta_erase_sl,
):
    diagram_widgets['eraser'].geometry = diagram_geom(
        'eraser',
        {**main_angles, 'theta_erase': math.radians(theta_erase_sl.value)},
        {**main_labels, 'g_erase': f'{theta_erase_sl.value:.0f}°'})


@app.cell(hide_code=True)
def _(
    MAIN_MODES,
    current,
    screen_curve,
    screen_curves_by_sign,
    set_panel_curves,
):
    def engine_curves():
        """Every condition's curve from one engine run per pixel at the
        current settings — what fire particles and reset screens draw,
        and sample from — pushed into the panels: (curves by mode,
        parts by mode)."""
        n, fringes, main_angles = (current['n'], current['fringes'],
                                   current['main_angles'])
        theta_pre, theta_erase = current['theta_pre'], current['theta_erase']
        curves = {mode: screen_curve(n, fringes, mode, via='pixels',
                                     **main_angles)[1]
                  for mode in MAIN_MODES}
        curves['tunable'] = screen_curve(n, fringes, 'tunable', via='pixels',
                                         theta_pre=theta_pre,
                                         **main_angles)[1]
        xs, (plus, minus) = screen_curves_by_sign(
            n, fringes, 'eraser', via='pixels', theta_erase=theta_erase,
            **main_angles)
        curves['eraser'] = [a + b for a, b in zip(plus, minus)]
        parts = {'eraser': [('+p₂', plus), ('−p₂', minus)]}
        for mode, curve in curves.items():
            set_panel_curves(mode, xs, curve, parts.get(mode))
        return curves, parts

    return (engine_curves,)


@app.cell(hide_code=True)
def _(
    MODES,
    engine_curves,
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
    # the engine's per-pixel curves, drawn and fired at
    with mo.status.spinner(title='running the exact simulations…'):
        _curves, _parts = engine_curves()
    _rng = random.Random()
    hit_store['seq'] += 1
    for _m in MODES:
        _new = sample_hits(xs, _curves[_m], shots.value, _rng,
                           parts=(tuple(_ys for _, _ys in _parts[_m])
                                  if _m in _parts else None))
        hit_store['hits'][_m].extend(_new)
        panel_widgets[_m].hits_chunk = {
            'seq': hit_store['seq'],
            'pts': [list(_p) for _p in _new],
            'total': len(hit_store['hits'][_m])}


@app.cell(hide_code=True)
def _(MODES, engine_curves, hit_store, mo, panel_widgets, reset_btn):
    mo.stop(not reset_btn.value)
    # a reset also redraws the curves from one engine run per pixel
    with mo.status.spinner(title='running the exact simulations…'):
        engine_curves()
    hit_store['seq'] += 1
    for _m in MODES:
        hit_store['hits'][_m] = []
        panel_widgets[_m].hits_chunk = {'seq': hit_store['seq'],
                                        'reset': True}


if __name__ == "__main__":
    app.run()
