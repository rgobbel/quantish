"""The double-slit experiment, built from quantish Fredkin gates.

Per *Good and Real* (p. 200), the setup of figures 4.12/4.13 is the
double-slit analog: "The two slits are like the two switch-wire inputs to
g2 … The diversion away from the lower input to g2 in fig. 4.13 is like
blocking one of the two slits."

    p1 -> g0 (prepare, theta0) -> g1 (split)   [the barrier]
        -> upper arm -> g2.upper  \\  the two slits = g2's switch inputs
        -> lower arm -> g2.lower  /   (blocking = diverting an arm away)
        -> g2 (unsplit, theta_s + delta(x)) -> g3 (test, theta0)

Each screen position x is one run with recombination offset delta(x); the
intensity is P(p1 exits g3's upper switch wire). With both slits open the
superposed path-worlds interfere — constructively (arrivals EXCEED the sum
of the single-slit curves) and destructively (arrivals vanish where either
slit alone would deliver them). Blocking either slit removes the
interference and "returns the probability to normal".

Modes: 'both', 'slit1' (lower arm diverted), 'slit2' (upper arm diverted),
plus 'observed' — the fig 4.14-style which-way recorder in the lower arm,
the follow-on lesson.
"""
import math
import random
from collections import Counter

from addict import Addict

DEFAULT_THETA0 = math.radians(22.5)   # prepare/test angle
DEFAULT_THETA_S = math.radians(45.0)  # split/unsplit base angle (equal arms)

MODES = ('both', 'slit1', 'slit2', 'observed')


def slit_config(delta_rad: float, mode: str = 'both',
                theta0: float = DEFAULT_THETA0,
                theta_s: float = DEFAULT_THETA_S) -> Addict:
    """The apparatus for one screen position (delta = recombination offset
    in radians). A blocked slit is a diverted arm: its link to g2 simply
    doesn't exist, so those worlds exit the apparatus."""
    if mode not in MODES:
        raise ValueError(f'unknown mode {mode!r}; expected one of {MODES}')
    gates = {'g0': {'angle': theta0},
             'g1': {'angle': theta_s},
             'g2': {'angle': theta_s + delta_rad},
             'g3': {'angle': theta0}}
    particles = {'p1': {'sign': 1, 'weight': 1}}
    links = {'p1': 'g0.upper',
             'g0.control': 'g1.control', 'g0.upper': 'g1.upper',
             'g1.control': 'g2.control',
             'g2.control': 'g3.control',
             'g2.upper': 'g3.upper', 'g2.lower': 'g3.lower'}
    if mode in ('both', 'slit1', 'observed'):
        links['g1.upper'] = 'g2.upper'
    if mode in ('both', 'slit2'):
        links['g1.lower'] = 'g2.lower'
    if mode == 'observed':
        gates['g4'] = {'angle': 0}
        particles['p2'] = {'sign': 1, 'weight': 1}
        links['p2'] = 'g4.upper'
        links['g1.lower'] = 'g4.control'
        links['g4.control'] = 'g2.lower'
    return Addict({'title': 'double slit', 'symbolic': False,
                   'loglevel': 'error', 'variables': {},
                   'particles': particles, 'gates': gates, 'links': links})


def screen_probability(delta_rad: float, mode: str = 'both',
                       theta0: float = DEFAULT_THETA0,
                       theta_s: float = DEFAULT_THETA_S) -> float:
    """P(p1 exits the test gate's upper switch wire) for one screen
    position, from an exact engine run."""
    from quantish.simulation import Simulation
    sim = Simulation(slit_config(delta_rad, mode, theta0, theta_s))
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


def screen_curve(n_points: int, fringes: float, mode: str = 'both',
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
        p = screen_probability(delta, mode, theta0, theta_s)
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
