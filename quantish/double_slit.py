"""The classic double-slit experiment, built entirely from quantish Fredkin
gates — every screen pixel is one exact engine run.

As described in *Good and Real* (p. 200), the two slits are the two
switch-wire inputs of a recombining gate. The apparatus, per pixel:

    p1 -> g_split (split, theta_s) -> upper output -> S1 (left slit)  -> g_merge.upper
                              -> lower output -> S2 (right slit) -> φ -> g_merge.lower
    g_merge (remerge, theta_s) -> upper output -> g_sort (sign sorter, angle 0)
    g_sort.upper -> S (this pixel's detector)      g_sort.lower -> D (dark channel)

φ is a PhasePlate (the model's phase_plates section): a pass-through
entered through its control wire that rotates the traversing weight by
e^(i*phi) and changes nothing else. It stands for the path-length difference from the
slits to THIS pixel: phi(x) = fringes*pi*x, zero at the screen center.
The slit boxes S1/S2, the blocks B1/B2, and the detectors S/D are delay
gates: a particle is routed in through their single control input and
passes through unchanged. The slits are idealized as infinitely narrow
(no diffraction envelope), so the pixel intensity is just the probability
that p1 ends at S.

Why the sorter g_sort is there: at the matched remerge g_merge, the relative phase
phi does NOT move p1 between g_merge's output wires — it moves it between the
SIGN components of the upper wire. (The exiting amplitudes are
(1+e^(i*phi))/2 on the plus component and i(1-e^(i*phi))/2 on the minus
component: position-space probability stays flat while the sign
distribution oscillates.) But a minus-sign particle entering a switch
wire exits the OTHER wire, so the angle-0 gate g_sort converts sign back to
position: plus-sign arrivals exit to S, minus-sign to D. A plain
position detector at S then sees

    P(S) = (1 + cos phi)/2

The three regimes need no case analysis:

- 'both': fringes — P(S) sweeps 1 (matched remerge reconstitutes p1
  perfectly at phi=0) down to 0 (everything sorted to D), peaking at 4x
  the single-slit intensity.
- 'slit1'/'slit2': the barrier absorbs the other path at a block box ->
  flat 1/4, independent of phi: a pure phase never changes a magnitude,
  so one path alone cannot show fringes.
- 'observed': a which-way recorder particle (fig 4.15's lesson). The wire
  to the right slit passes through gate g_obs's control input on its way to
  S2; a control input never changes the particle traversing it, but its
  occupancy decides whether g_obs swaps its switch wires, so the recorder
  particle p2's exit wire records which slit p1 used. The two paths'
  configuration-space points then differ in p2's position, so they can
  no longer interfere: P(S) = 1/4 + 1/4 = the classical sum, flat, with
  nothing blocking either path.
"""
import copy
import functools
import math
import random
from pathlib import Path

import yaml
from addict import Addict

DEFAULT_THETA_S = math.radians(45.0)  # split angle (equal slit amplitudes)

MODES = ('both', 'slit1', 'slit2', 'observed')

_BASE_CACHE = None


def _base_config() -> dict:
    """The apparatus network, from models/extras/double_slit.yaml (the
    repo copy, or the frozen library under WASM) — one parse, deep-
    copied per use so per-pixel overrides never leak."""
    global _BASE_CACHE
    if _BASE_CACHE is None:
        for cand in (Path('/wasm-data/models/extras/double_slit.yaml'),
                     Path(__file__).resolve().parent.parent / 'models'
                     / 'extras' / 'double_slit.yaml'):
            if cand.is_file():
                _BASE_CACHE = yaml.safe_load(cand.read_text())
                break
        else:
            raise FileNotFoundError(
                'models/extras/double_slit.yaml not found')
    return copy.deepcopy(_BASE_CACHE)


def slit_config(mode: str = 'both', theta_s: float = DEFAULT_THETA_S,
                phi: float = 0.0, theta_merge: float | None = None,
                theta_sort: float = 0.0) -> Addict:
    """The full apparatus for one screen pixel, whose path-length
    difference from the slits is the phase phi. Each switch output of g_split
    reaches the slit plane: the upper output at the left slit (box S1),
    the lower at the right slit (S2), and a blocked slit n has the block
    Bn in its place (the book's "diversion away", fig 4.14). The right
    slit's path continues through the phase plate φ to the remerge gate
    g_merge, whose upper output the sorter g_sort splits into the detectors S
    (plus sign) and D (minus sign). 'observed' routes the right slit's
    wire through the control input of the angle-0 gate g_obs on its way to
    S2, with the recorder particle p2 on g_obs's switch wires."""
    if mode not in MODES:
        raise ValueError(f'unknown mode {mode!r}; expected one of {MODES}')
    cfg = _base_config()
    cfg['title'] = f'double slit ({mode})'
    cfg['loglevel'] = 'error'
    cfg['variables'].update(
        theta_split=theta_s,
        theta_merge=theta_s if theta_merge is None else theta_merge,
        theta_sort=theta_sort,
        phi=phi)
    gates, links = cfg['gates'], cfg['links']
    stages = cfg['run_stages']
    slits = stages['slits']
    if mode == 'slit1':
        slits[:] = ['S1', 'B2']
        links['g_split.lower'] = 'B2'
        del links['S2'], links['φ.control'], cfg['phase_plates']['φ']
        del stages['phase']
    elif mode == 'slit2':
        slits[:] = ['B1', 'S2']
        links['g_split.upper'] = 'B1'
        del links['S1']
    elif mode == 'observed':
        gates['g_obs'] = {'angle': 0}
        cfg.setdefault('display_strings', {})['g_obs'] = '$g_{obs}$'
        cfg['particles']['p2'] = {'sign': 1, 'weight': 1}
        links.update({'g_split.lower': 'g_obs.control',
                      'g_obs.control': 'S2', 'p2': 'g_obs.upper'})
        cfg['run_stages'] = {'split': stages.pop('split'),
                             'observe': ['g_obs'], **stages}
    cfg['delay_gates'] = slits + ['S', 'D']
    return Addict(cfg)


def slit_sim(mode: str = 'both', theta_s: float = DEFAULT_THETA_S,
             phi: float = 0.0, theta_merge: float | None = None,
             theta_sort: float = 0.0):
    """A loaded (unrun) Simulation of the mode's apparatus — e.g. for
    rendering its circuit diagram."""
    from quantish.simulation import Simulation
    return Simulation(slit_config(mode, theta_s, phi, theta_merge,
                                  theta_sort))


@functools.lru_cache(maxsize=1 << 17)
def pixel_probability(phi: float, mode: str = 'both',
                      theta_s: float = DEFAULT_THETA_S,
                      theta_merge: float | None = None,
                      theta_sort: float = 0.0) -> float:
    """One exact engine run: the probability that p1 ends at this pixel's
    detector S, given the pixel's path-difference phase phi. Memoized —
    the engine run is the expensive thing, and slider moves revisit the
    same (phi, angles) points constantly (returning a slider to 45°
    re-renders every curve from cache instead of rerunning the engine
    4 × n_points times)."""
    sim = slit_sim(mode, theta_s, phi, theta_merge, theta_sort)
    sim.run()
    return sum(abs(complex(point.weight.v)) ** 2
               for point in sim.result_space.index.values()
               if (origin := point.coords['p1'].position.origin) is not None
               and origin.gate == 'S')


def screen_positions(n_points: int) -> list[float]:
    """Screen coordinates x in [-1, 1]."""
    return [-1.0 + 2.0 * i / (n_points - 1) for i in range(n_points)]


def screen_curve(n_points: int, fringes: float, mode: str = 'both',
                 theta_s: float = DEFAULT_THETA_S,
                 theta_merge: float | None = None,
                 theta_sort: float = 0.0) -> tuple[list[float], list[float]]:
    """(positions, intensities) across the screen — one engine run per
    pixel. The right slit's path difference sweeps `fringes` pattern
    periods over the screen; a blocked slit's wire ends at its block
    inside the circuit and contributes nothing."""
    xs = screen_positions(n_points)
    return xs, [pixel_probability(fringes * math.pi * x, mode, theta_s,
                                  theta_merge, theta_sort)
                for x in xs]


def sample_hits(xs: list[float], intensities: list[float], n: int,
                rng: random.Random) -> list[tuple[float, float]]:
    """The impacts on the screen from a volley of n particles FIRED at
    the apparatus: x drawn from the intensity distribution with
    within-bin jitter, y uniform — the dots that build up the pattern,
    one particle at a time. How many of the n actually land is the
    intensity's integral over the screen (blocking a slit absorbs about
    half the volley, so those rasters fill half as fast)."""
    if sum(intensities) <= 0:
        return []
    bin_w = (xs[-1] - xs[0]) / (len(xs) - 1) if len(xs) > 1 else 0.02
    # The endpoint pixels represent half-width bins at the screen edges,
    # so they carry half weight (the trapezoidal rule). A plain mean
    # would count one edge twice: with f fringes both edges are bright
    # (f even) or dark (f odd), skewing the landing fraction to
    # (81±1)/81 instead of exactly 1.
    weights = list(intensities)
    weights[0] /= 2
    weights[-1] /= 2
    landing = min(n, round(n * sum(weights) * bin_w))
    picks = rng.choices(range(len(xs)), weights=weights, k=landing)
    return [(xs[i] + rng.uniform(-bin_w / 2, bin_w / 2), rng.random())
            for i in picks]
