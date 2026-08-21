"""The classic double-slit experiment, built entirely from quantish Fredkin
gates — every screen pixel is one exact engine run.

As described in *Good and Real* (p. 200), the two slits are the two
switch-wire inputs of a recombining gate. The apparatus, per pixel:

    p1 -> g1 (split, theta_s) -> upper output -> S1 (left slit)  -> g2.upper
                              -> lower output -> S2 (right slit) -> gp -> g2.lower
    g2 (remerge, theta_s) -> upper output -> g5 (sign sorter, angle 0)
    g5.upper -> S (this pixel's detector)      g5.lower -> D (dark channel)

gp is a pure phase plate: an angle-0 gate with a `phase`, entered through
its control wire, which rotates the traversing weight by e^(i*phi) and
changes nothing else. It stands for the path-length difference from the
slits to THIS pixel: phi(x) = fringes*pi*x, zero at the screen center.
The slit boxes S1/S2, the blocks B1/B2, and the detectors S/D are delay
gates: a particle is routed in through their single control input and
passes through unchanged. The slits are idealized as infinitely narrow
(no diffraction envelope), so the pixel intensity is just the probability
that p1 ends at S.

Why the sorter g5 is there: at the matched remerge g2, the relative phase
phi does NOT move p1 between g2's output wires — it moves it between the
SIGN components of the upper wire. (The exiting amplitudes are
(1+e^(i*phi))/2 on the plus component and i(1-e^(i*phi))/2 on the minus
component: position-space probability stays flat while the sign
distribution oscillates.) But a minus-sign particle entering a switch
wire exits the OTHER wire, so the angle-0 gate g5 converts sign back to
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
  to the right slit passes through gate g4's control input on its way to
  S2; a control input never changes the particle traversing it, but its
  occupancy decides whether g4 swaps its switch wires, so the recorder
  particle p2's exit wire records which slit p1 used. The two paths'
  configuration-space points then differ in p2's position, so they can
  no longer interfere: P(S) = 1/4 + 1/4 = the classical sum, flat, with
  nothing blocking either path.
"""
import math
import random

from addict import Addict

DEFAULT_THETA_S = math.radians(45.0)  # split angle (equal slit amplitudes)

MODES = ('both', 'slit1', 'slit2', 'observed')


def slit_config(mode: str = 'both', theta_s: float = DEFAULT_THETA_S,
                phi: float = 0.0) -> Addict:
    """The full apparatus for one screen pixel, whose path-length
    difference from the slits is the phase phi. Each switch output of g1
    reaches the slit plane: the upper output at the left slit (box S1),
    the lower at the right slit (S2), and a blocked slit n has the block
    Bn in its place (the book's "diversion away", fig 4.14). The right
    slit's path continues through the phase plate gp to the remerge gate
    g2, whose upper output the sorter g5 splits into the detectors S
    (plus sign) and D (minus sign). 'observed' routes the right slit's
    wire through the control input of the angle-0 gate g4 on its way to
    S2, with the recorder particle p2 on g4's switch wires."""
    if mode not in MODES:
        raise ValueError(f'unknown mode {mode!r}; expected one of {MODES}')
    gates = {'g1': {'angle': theta_s},
             'g2': {'angle': theta_s},
             'g5': {'angle': 0}}
    particles = {'p1': {'sign': 1, 'weight': 1}}
    links = {'p1': 'g1.upper',
             'g1.upper': 'S1', 'S1': 'g2.upper',
             'g1.lower': 'S2', 'S2': 'gp.control', 'gp.control': 'g2.lower',
             'g2.upper': 'g5.upper', 'g5.upper': 'S', 'g5.lower': 'D'}
    slits = ['S1', 'S2']
    stages = {'split': ['g1'], 'slits': slits, 'phase': ['gp'],
              'merge': ['g2'], 'sort': ['g5'], 'detect': ['S', 'D']}
    if mode != 'slit1':          # the right slit is open: phase plate in play
        gates['gp'] = {'angle': 0, 'phase': phi}
    if mode == 'slit1':
        slits[:] = ['S1', 'B2']
        links['g1.lower'] = 'B2'
        del links['S2'], links['gp.control']
        del stages['phase']
    elif mode == 'slit2':
        slits[:] = ['B1', 'S2']
        links['g1.upper'] = 'B1'
        del links['S1']
    elif mode == 'observed':
        gates['g4'] = {'angle': 0}
        particles['p2'] = {'sign': 1, 'weight': 1}
        links.update({'g1.lower': 'g4.control', 'g4.control': 'S2',
                      'p2': 'g4.upper'})
        stages = {'split': ['g1'], 'observe': ['g4'], **stages}
    delay_gates = slits + ['S', 'D']
    return Addict({'title': f'double slit ({mode})', 'symbolic': False,
                   'loglevel': 'error', 'variables': {},
                   'run_stages': stages, 'delay_gates': delay_gates,
                   'particles': particles, 'gates': gates, 'links': links})


def slit_sim(mode: str = 'both', theta_s: float = DEFAULT_THETA_S,
             phi: float = 0.0):
    """A loaded (unrun) Simulation of the mode's apparatus — e.g. for
    rendering its circuit diagram."""
    from quantish.simulation import Simulation
    return Simulation(slit_config(mode, theta_s, phi))


def pixel_probability(phi: float, mode: str = 'both',
                      theta_s: float = DEFAULT_THETA_S) -> float:
    """One exact engine run: the probability that p1 ends at this pixel's
    detector S, given the pixel's path-difference phase phi."""
    sim = slit_sim(mode, theta_s, phi)
    sim.run()
    return sum(abs(complex(point.weight.v)) ** 2
               for point in sim.result_space.index.values()
               if (origin := point.coords['p1'].position.origin) is not None
               and origin.gate == 'S')


def screen_positions(n_points: int) -> list[float]:
    """Screen coordinates x in [-1, 1]."""
    return [-1.0 + 2.0 * i / (n_points - 1) for i in range(n_points)]


def screen_curve(n_points: int, fringes: float, mode: str = 'both',
                 theta_s: float = DEFAULT_THETA_S) -> tuple[list[float], list[float]]:
    """(positions, intensities) across the screen — one engine run per
    pixel. The right slit's path difference sweeps `fringes` pattern
    periods over the screen; a blocked slit's wire ends at its block
    inside the circuit and contributes nothing."""
    xs = screen_positions(n_points)
    return xs, [pixel_probability(fringes * math.pi * x, mode, theta_s)
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
