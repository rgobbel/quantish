"""The double-slit experiment, built from quantish Fredkin gates.

The analogy
-----------
Each position x on the detection screen corresponds to one run of a small
interferometer whose recombination angle depends on x (the path-length
difference at that screen position):

    p1 -> g0 (prepare, theta0) -> g1 (split, theta_s)  [the two slits]
        -> upper arm ----------------------> g2 (unsplit, theta_s + delta(x))
        -> lower arm --[g4 observer, opt.]-> g2
        -> g3 (test, theta0)   [the screen pixel]

The screen intensity at x is P(p1 exits g3 upper). Open slits give the
textbook fringes; inserting the which-way observer g4 (an angle-0 gate
whose control is threaded by the lower arm, with a recorder particle p2
on its switch wire) visibly washes them out.

A quantish subtlety worth teaching: WITHOUT the prepare/test bracket
(g0/g3), this circuit's cos²-pattern survives observation untouched — the
marginal is classically reproducible and is not a genuine interference
signature. The coherence that observation destroys lives in the sign
dimension that g0 creates and g3 tests.
"""
import math
import random
from collections import Counter

from addict import Addict

DEFAULT_THETA0 = math.radians(22.5)   # prepare/test angle
DEFAULT_THETA_S = math.radians(45.0)  # split/unsplit base angle (equal arms)


def slit_config(delta_rad: float, observe: bool,
                theta0: float = DEFAULT_THETA0,
                theta_s: float = DEFAULT_THETA_S) -> Addict:
    """The interferometer for one screen position (delta = recombination
    offset in radians), with or without the which-way observer."""
    gates = {'g0': {'angle': theta0},
             'g1': {'angle': theta_s},
             'g2': {'angle': theta_s + delta_rad},
             'g3': {'angle': theta0}}
    particles = {'p1': {'sign': 1, 'weight': 1}}
    links = {'p1': 'g0.upper',
             'g0.control': 'g1.control', 'g0.upper': 'g1.upper',
             'g1.control': 'g2.control', 'g1.upper': 'g2.upper',
             'g2.control': 'g3.control',
             'g2.upper': 'g3.upper', 'g2.lower': 'g3.lower'}
    if observe:
        gates['g4'] = {'angle': 0}
        particles['p2'] = {'sign': 1, 'weight': 1}
        links['p2'] = 'g4.upper'
        links['g1.lower'] = 'g4.control'
        links['g4.control'] = 'g2.lower'
    else:
        links['g1.lower'] = 'g2.lower'
    return Addict({'title': 'double slit', 'symbolic': False,
                   'loglevel': 'error', 'variables': {},
                   'particles': particles, 'gates': gates, 'links': links})


def screen_probability(delta_rad: float, observe: bool,
                       theta0: float = DEFAULT_THETA0,
                       theta_s: float = DEFAULT_THETA_S) -> float:
    """P(p1 exits the test gate on the upper wire) for one screen position,
    from an exact engine run."""
    from multiworld.simulation import Simulation
    sim = Simulation(slit_config(delta_rad, observe, theta0, theta_s))
    sim.run()
    total = 0.0
    for point in sim.result_space.index.values():
        origin = point.coords['p1'].position.origin
        if origin and origin.gate == 'g3' and origin.port == 'upper':
            total += float(point.probability)
    return total


def screen_positions(n_points: int) -> list[float]:
    """Screen coordinates x in [-1, 1]."""
    return [-1.0 + 2.0 * i / (n_points - 1) for i in range(n_points)]


def screen_curve(n_points: int, fringes: float, observe: bool,
                 envelope: bool = True,
                 theta0: float = DEFAULT_THETA0,
                 theta_s: float = DEFAULT_THETA_S) -> tuple[list[float], list[float]]:
    """(positions, intensities) across the screen. delta(x) sweeps `fringes`
    full pattern periods over the screen; the optional gaussian envelope
    stands in for single-slit diffraction (visual realism only)."""
    xs = screen_positions(n_points)
    intensities = []
    for x in xs:
        delta = fringes * math.pi * x
        p = screen_probability(delta, observe, theta0, theta_s)
        if envelope:
            p *= math.exp(-(x * 1.6) ** 2)
        intensities.append(p)
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
