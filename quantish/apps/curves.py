"""Screen curves for the double-slit demo and the decoherence lab:
the engine's per-pixel curves at the current settings (what fire and
reset draw, and sample hits from), and pushing curves into a
ScreenPanelWidget at the right grain.
"""
from __future__ import annotations

from quantish.double_slit import screen_curve, screen_curves_by_sign

__all__ = ['double_slit_curves', 'eraser_curves', 'grouped_curves', 'main_curves',
           'push_curves', 'tunable_curve']


def push_curves(panel, xs, curve, parts=None, *, grain, title, width, hits) -> int:
    """New curves for a screen panel. Same grain (pixel count): only the
    line area under the screen redraws (the `curves` trait). A new
    grain: the panel rebuilds from its baseline — title, curves, and
    every hit so far — since the raster's pixel count follows len(xs).
    `parts` (name, ys pairs) are a sorted screen's per-group curves,
    drawn under the total, the hits colored by group. Returns the new
    grain, for the caller to keep."""
    curves = {'x': list(xs), 'y': list(curve)}
    if parts:
        curves['parts'] = [{'name': name, 'y': list(ys)} for name, ys in parts]
    panel.curves = curves
    if grain != len(xs):
        panel.data = {'title': title, 'curve': curves, 'width': width,
                      'hits': [list(p) for p in hits]}
    return len(xs)


def grouped_curves(curves: dict, particle: str = ''):
    """A lab screen's curves by group ({'all': ys}, or {'+': ys, '−':
    ys, …} keyed by the sorting particle's coordinate) as (the total,
    the parts as (name, ys) pairs or None when unsorted); a one-character
    group name is a sign, shown before the particle ('+p2')."""
    total = [sum(col) for col in zip(*curves.values())]
    if list(curves) == ['all']:
        return total, None
    return total, [(f'{g}{particle}' if len(g) == 1 else g, ys)
                   for g, ys in curves.items()]


def main_curves(n, fringes, main_angles: dict, via: str = 'pixels',
                modes=('both', 'slit2', 'slit1', 'observed')) -> dict:
    """The grid conditions' curves by mode at the shared gate angles;
    `via` is the three-run reconstruction ('fit') or one engine run per
    pixel ('pixels')."""
    return {mode: screen_curve(n, fringes, mode, via=via, **main_angles)[1]
            for mode in modes}


def tunable_curve(n, fringes, main_angles: dict, theta_pre, via: str = 'pixels'):
    """The tunable recorder's curve at recorder angle `theta_pre`."""
    return screen_curve(n, fringes, 'tunable', via=via, theta_pre=theta_pre,
                        **main_angles)[1]


def eraser_curves(n, fringes, main_angles: dict, theta_erase, via: str = 'pixels'):
    """The eraser's curve at eraser angle `theta_erase`: (xs, the total,
    the parts by p₂'s sign — what the film colors its hits by)."""
    xs, (plus, minus) = screen_curves_by_sign(
        n, fringes, 'eraser', via=via, theta_erase=theta_erase, **main_angles)
    return xs, [a + b for a, b in zip(plus, minus)], [('+p₂', plus), ('−p₂', minus)]


def double_slit_curves(settings: dict, main_modes):
    """Every double-slit condition's curve from one engine run per
    pixel at `settings` (n, fringes, main_angles, theta_pre,
    theta_erase — the demo's `current`): (xs, curves by mode, parts by
    mode — the eraser's two signs)."""
    n, fringes, main_angles = (settings['n'], settings['fringes'],
                               settings['main_angles'])
    curves = main_curves(n, fringes, main_angles, 'pixels', main_modes)
    curves['tunable'] = tunable_curve(n, fringes, main_angles, settings['theta_pre'])
    xs, curves['eraser'], parts = eraser_curves(n, fringes, main_angles,
                                                settings['theta_erase'])
    return xs, curves, {'eraser': parts}
