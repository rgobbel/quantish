"""The Weight-split Explorer's library side: one quantish Fredkin gate's four-way
split of a weight at a measurement angle, the controls that set the
angle, sign, and weight (seedable, for a gate picked out of a run), and
the view — the vector chart and the components' table. The notebook
binds the controls, keeps the chart's selection in state, and lays the
page out.
"""
from __future__ import annotations

import cmath
import math

import marimo as mo

import quantish.qnumber as qn
from quantish.builder_widget import WeightSplitWidget
from quantish.display import latex_weight, phase_deg
from quantish.gate import FredkinGate

# the chart's entries in display order: the two destination sums, then
# the four components
COMPONENTS = ['c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b']
CHART_SIZE = 500
# the controls' defaults; a seed (a gate out of a run) overrides them
DEFAULT_SEED = {'theta_deg': 30, 'plus_sign': True, 'wmag': 1.0, 'wphase_deg': 0}

def split_components(theta_deg: float, weight: complex, plus_sign: bool = True) -> dict:
    """The split of `weight` at `theta_deg`, by name: the four
    components and the two destination sums, as Python complexes."""
    gate = FredkinGate('ws', qn.qify(math.radians(theta_deg)))
    c2a, c2b, c3a, c3b = (complex(c) for c in
                          gate.components(qn.Complex(weight), plus_sign))
    return {'c2': c2a + c2b, 'c3': c3a + c3b,
            'c2a': c2a, 'c2b': c2b, 'c3a': c3a, 'c3b': c3b}


def polar_weight(wmag: float, wphase_deg: float) -> complex:
    """The weight the |w| and φ(w) sliders describe."""
    return wmag * cmath.exp(1j * math.radians(wphase_deg))


def explorer_controls(seed: dict | None = None) -> mo.ui.dictionary:
    """The explorer's controls as one element the cell binds: θ, the
    sign, |w|, φ(w), and which components to show. A seed — a gate's
    angle and a particle's incoming weight, from a run — opens them at
    those values."""
    s = {**DEFAULT_SEED, **(seed or {})}
    return mo.ui.dictionary({
        'theta': mo.ui.slider(-90, 90, step=5, value=_snap(s['theta_deg'], 5, -90, 90),
                              label='θ (º)', show_value=True),
        'sign': mo.ui.switch(value=bool(s['plus_sign']), label='sign + (off = −)'),
        'wmag': mo.ui.slider(0.0, 1.0, step=0.05, value=_snap(s['wmag'], 0.05, 0, 1),
                             label='|w|', show_value=True),
        'wphase': mo.ui.slider(-180, 180, step=5,
                               value=_snap(s['wphase_deg'], 5, -180, 180),
                               label='φ(w) (º)', show_value=True),
        'components': mo.ui.multiselect(options=COMPONENTS, value=list(COMPONENTS),
                                        label='components'),
    })


def _snap(x, step, lo, hi):
    """A seed value onto a slider's grid, inside its range."""
    return min(hi, max(lo, round(round(x / step) * step, 10)))


def explorer_view(values: dict, selected=()) -> tuple:
    """(the chart widget, the view): the vector chart of the chosen
    components, its selection reseeded from `selected`, beside their
    values, probabilities, and phases. The cell binds the widget (its
    `selected` trait comes back through it) and shows the view."""
    data = split_components(values['theta'], polar_weight(values['wmag'], values['wphase']),
                            values['sign'])
    shown = [c for c in COMPONENTS if c in values['components']]
    sign_str = '+' if values['sign'] else '−'
    lines = [rf"{name} &= {latex_weight(data[name], prec=2)}"
             rf" &\quad \texttt{{Pr}} &= {abs(data[name])**2:.2f}"
             rf" & \phi &= {phase_deg(data[name]):.1f}\degree\\"
             for name in shown]
    latex = '$$\n\\begin{aligned}\n' + '\n'.join(lines) + '\n\\end{aligned}\n$$'
    # native SVG: Finder-style selection synced through the widget's
    # `selected` trait, wheel zoom, drag pan, a resizable frame
    native = mo.ui.anywidget(WeightSplitWidget(
        data={'vectors': {c: [data[c].real, data[c].imag] for c in shown},
              'order': shown,
              'title': f"θ = {values['theta']}º, sign = {sign_str}",
              'size': CHART_SIZE},
        selected=[c for c in selected if c in shown]))
    return native, mo.hstack([native, mo.md(latex)], align='center', justify='start',
                             wrap=True)


def chart_selection(native, current: tuple):
    """The chart's mouse selection as the state should hold it, or None
    when nothing changed — the widget is rebuilt on every slider move
    and reseeded from the state; an explicit empty (a click on empty
    plot space) clears it."""
    sel = (native.value or {}).get('selected')
    if sel is not None and tuple(sel) != tuple(current):
        return tuple(sel)
    return None
