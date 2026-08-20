"""The double-slit experiment, built from quantish Fredkin gates.

Per *Good and Real* (p. 200), the two slits are the two switch-wire inputs
of a recombining gate, and blocking a slit is diverting an arm away
(figs. 4.13/4.14 in the 2026 numbering). Here the apparatus is just the
barrier:

    p1 -> g1 (split, theta_s) -> upper arm  = slit 1
                              -> lower arm  = slit 2

and the flight from the slits to a screen position x is idealized (the
slits are infinitely narrow, so there is no diffraction envelope). Each
screen pixel acts as a remerge gate MATCHED to the split — in quantish,
interference only ever happens at a recombining gate (fig 4.13; splits
at rate sin^2(Q1-Q2)) — so each arm's sign components (the split rule's
same-sign and flipped-sign pieces) are summed coherently into one arm
amplitude, exact from the engine's CS points; the path-length difference
to x enters as a relative phase between the arms; and arms interfere
only within a class of CS points that agree in every OTHER particle:

    I(x) = sum over classes |sum over arms a_arm * e^(i*phi_arm(x))|^2

The three regimes then need no case analysis:

- 'both': one class, two arms -> the cross term oscillates with x:
  fringes, peaking at 4x the single-slit intensity, zero at the darks.
- 'slit1'/'slit2': the barrier absorbs the other arm -> one amplitude,
  |a|^2, flat (infinitely narrow slit: no envelope).
- 'observed': a which-way recorder particle (fig 4.15's lesson) rides the
  lower arm; its position differs between the arm classes, so the arms
  can no longer share a class and the cross term vanishes: fringes wash
  out, I = |a_u|^2 + |a_l|^2 = the classical sum, with nothing blocking
  either path.

Why the sweep can't be a gate angle: quantish has no pure phase-shifter.
Any gate offset delta multiplies single-path throughput by cos-squared
terms too, so a swept recombination angle shows "fringes" even with one
slit open — a basis-rotation artifact, not interference. And a bare
position-detecting screen with NO remerge would show no fringes at all:
the sign components record path parity, and summing |w|^2 over them
cancels the cross terms exactly.
"""
import cmath
import math
import random
from collections import Counter

from addict import Addict

DEFAULT_THETA_S = math.radians(45.0)  # split angle (equal arms)

MODES = ('both', 'slit1', 'slit2', 'observed')

# The engine's crossed arm amplitude carries a fixed -pi/2 phase relative
# to the straight one; this propagation offset on the lower arm cancels it
# so equal path lengths (screen center) give the central bright fringe.
_CROSS_PHASE = math.pi / 2


def slit_config(mode: str = 'both',
                theta_s: float = DEFAULT_THETA_S) -> Addict:
    """The barrier apparatus. It does not depend on the screen position —
    the screen is outside the gate network. 'observed' couples a recorder
    particle to the lower arm (an angle-0 gate used via its control wire)."""
    if mode not in MODES:
        raise ValueError(f'unknown mode {mode!r}; expected one of {MODES}')
    gates = {'g1': {'angle': theta_s}}
    particles = {'p1': {'sign': 1, 'weight': 1}}
    links = {'p1': 'g1.upper'}
    run_stages = {'split': ['g1']}
    if mode == 'observed':
        gates['g4'] = {'angle': 0}
        particles['p2'] = {'sign': 1, 'weight': 1}
        links['p2'] = 'g4.upper'
        links['g1.lower'] = 'g4.control'
        run_stages['observe'] = ['g4']
    return Addict({'title': 'double slit', 'symbolic': False,
                   'loglevel': 'error', 'variables': {},
                   'run_stages': run_stages,
                   'particles': particles, 'gates': gates, 'links': links})


def arm_amplitudes(mode: str = 'both',
                   theta_s: float = DEFAULT_THETA_S) -> list[dict[str, complex]]:
    """One exact engine run; returns per-class {arm: amplitude} dicts,
    arm in ('upper', 'lower'). A class is a distinct assignment of every
    particle other than p1 — amplitudes interfere only within a class.
    Each arm's two sign components sum coherently (the matched-remerge
    idealization; see the module docstring)."""
    from quantish.simulation import Simulation
    sim = Simulation(slit_config(mode, theta_s))
    sim.run()
    classes: dict[tuple, dict[str, complex]] = {}
    for point in sim.result_space.index.values():
        origin = point.coords['p1'].position.origin
        arm = 'upper' if (origin.gate, origin.port) == ('g1', 'upper') else 'lower'
        key = tuple((name, str(coord.pkey.sign), str(coord.position))
                    for name, coord in sorted(point.coords.items())
                    if name != 'p1')
        by_arm = classes.setdefault(key, {})
        by_arm[arm] = by_arm.get(arm, 0j) + complex(point.weight.v)
    return list(classes.values())


def screen_positions(n_points: int) -> list[float]:
    """Screen coordinates x in [-1, 1]."""
    return [-1.0 + 2.0 * i / (n_points - 1) for i in range(n_points)]


def screen_curve(n_points: int, fringes: float, mode: str = 'both',
                 theta_s: float = DEFAULT_THETA_S) -> tuple[list[float], list[float]]:
    """(positions, intensities) across the screen. The lower arm's path
    difference sweeps `fringes` pattern periods over the screen; blocked
    arms (the barrier absorbs them) contribute no amplitude."""
    open_arms = {'both': ('upper', 'lower'), 'observed': ('upper', 'lower'),
                 'slit1': ('upper',), 'slit2': ('lower',)}[mode]
    classes = arm_amplitudes(mode, theta_s)
    xs = screen_positions(n_points)
    intensities = []
    for x in xs:
        phase = {'upper': 0.0, 'lower': fringes * math.pi * x + _CROSS_PHASE}
        total = 0.0
        for amps in classes:
            summed = sum(amps[arm] * cmath.exp(1j * phase[arm])
                         for arm in open_arms if arm in amps)
            total += abs(summed) ** 2
        intensities.append(total)
    return xs, intensities


def sample_hits(xs: list[float], intensities: list[float], n: int,
                rng: random.Random) -> list[tuple[float, float]]:
    """n particle impacts on the screen: x drawn from the (normalized)
    intensity distribution with within-bin jitter, y uniform — the dots
    that build up the pattern, one particle at a time."""
    total = sum(intensities)
    if total <= 0:
        return []
    bin_w = (xs[-1] - xs[0]) / (len(xs) - 1) if len(xs) > 1 else 0.02
    picks = rng.choices(range(len(xs)), weights=intensities, k=n)
    return [(xs[i] + rng.uniform(-bin_w / 2, bin_w / 2), rng.random())
            for i in picks]


def hit_histogram(hits: list[tuple[float, float]], n_bins: int = 41) -> Counter:
    counts = Counter()
    for x, _y in hits:
        b = min(n_bins - 1, max(0, int((x + 1.0) / 2.0 * n_bins)))
        counts[b] += 1
    return counts
