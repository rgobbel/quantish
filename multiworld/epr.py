"""EPR outcome conventions, following quantish_gld/epr_bell.py.

The intrinsic discrepancy law for the fig 4.16/4.17 family, conditioned on
p3 exiting its coupling gate on the upper wire:

    one-stage (g5/g6 only):   sin²(Q5 + Q6)
    two-stage (adds g7/g8):   sin²((Q5 + Q6) − (Q7 + Q8))

The measurement outcome is NOT plain position for one-stage circuits: an
angle-0 gate routes a PLUS particle straight and a MINUS particle across
(it is a sign sorter, not the identity), so the one-stage outcome is
position⊕sign — what a final sorting stage would turn into pure position.
The second stage of fig 4.17 plays exactly that role, which is why plain
position is the outcome there.

The Bell/CHSH experiment sweeps measurement angles (θ1, θ2) over the three
"magic" angles {Qa=0, Qb=π/8, Qc=π/4} (or the model's qa/qb/qc variables).
"Measuring p1 at θ1 and p2 at θ2" means overriding

    two-stage:  g7 = θ1,  g8 = (Q5+Q6) − θ2   (Q5/Q6 keep base values)
    one-stage:  g5 = θ1,  g6 = −θ2

which reduces the intrinsic law to sin²(θ1 − θ2) in both cases — so the
YAML angles of the overridden gates are placeholders.
"""
import logging
import random
from copy import deepcopy

import multiworld.qnumber as qn
from multiworld.qnumber import qify

log = logging.getLogger('multiworld')

# Canonical magic angles, used when the model doesn't define qa/qb/qc.
DEFAULT_VALUES = {'qa': '0', 'qb': 'pi/8', 'qc': 'pi/4'}


def is_two_stage(sim) -> bool:
    return 'g7' in sim.gates.keys() and 'g8' in sim.gates.keys()


def expected_discrepancy(sim):
    """The intrinsic sin²-law discrepancy for the sim's gate angles, or
    None when the circuit lacks the EPR structure (g5/g6)."""
    if 'g5' not in sim.gates.keys() or 'g6' not in sim.gates.keys():
        return None
    total = sim.gates['g5'].theta + sim.gates['g6'].theta
    if is_two_stage(sim):
        total = total - (sim.gates['g7'].theta + sim.gates['g8'].theta)
    return total.sin ** 2


def outcome(coord, two_stage: bool) -> str:
    """Measurement outcome for one particle's final coordinate: plain
    position ('upper'/'lower') after a second measurement stage,
    position⊕sign after one."""
    side = coord.position.origin.port
    if not two_stage and int(coord.sign) < 0:
        side = 'lower' if side == 'upper' else 'upper'
    return side


def classify(point, two_stage: bool) -> str:
    """'same' / 'diff' (p1's and p2's outcomes agree / disagree) for worlds
    where p3 exited on the upper wire, else 'uncoupled'."""
    coords = list(point.coords.values())
    if len(coords) < 3:
        return 'uncoupled'
    p1c, p2c, p3c = coords[:3]
    origin = p3c.position.origin
    if origin is None or origin.port != 'upper':
        return 'uncoupled'
    if outcome(p1c, two_stage) == outcome(p2c, two_stage):
        return 'same'
    return 'diff'


# --------------------------------------------------------------------------
# The Bell/CHSH experiment: a 3×3 sweep over the magic angles.
# --------------------------------------------------------------------------

def supports_epr(sim) -> bool:
    """True when the model has the EPR structure: the p3-coupling gate g4
    to condition on, plus measurement gates g5/g6."""
    return {'g4', 'g5', 'g6'} <= set(sim.gates.keys())


def magic_angles(sim) -> dict:
    """The three labeled sweep angles: the model's qa/qb/qc variables when
    all three are defined and distinct, else the canonical {0, pi/8, pi/4}."""
    found = {name: qify(value) for name, value in sim.qvars.items()
             if name.lower() in ('qa', 'qb', 'qc')}
    if len(found) == 3:
        if len({float(v) for v in found.values()}) == 3:
            return found
        log.warning(f'   model magic angles are not distinct '
                    f'({", ".join(f"{k}={float(v):.4f}" for k, v in found.items())}); '
                    f'using canonical set instead')
    return {name: qify(value) for name, value in DEFAULT_VALUES.items()}


def run_pair(sim, theta1, theta2, n_trials: int = 0, rng=None) -> dict:
    """Run one experiment cell, measuring p1 at theta1 and p2 at theta2.

    Rebuilds the simulation with the measurement gates overridden per the
    module-docstring convention and returns the conditional discrepancy:
    'exact' from the final worlds, 'sampled' from n_trials terminal draws
    (when n_trials > 0), 'analytical' = sin²(θ1−θ2), and 'classical' — the
    linear hidden-variable prediction 2|θ1−θ2|/π.
    """
    from multiworld.simulation import Simulation
    from multiworld.montecarlo import epr_tally, sample_terminal
    theta1 = qify(theta1)
    theta2 = qify(theta2)
    two_stage = is_two_stage(sim)
    cfg = deepcopy(sim.config)
    if two_stage:
        base = sim.gates['g5'].theta + sim.gates['g6'].theta
        cfg.gates['g7'].angle = theta1
        cfg.gates['g8'].angle = base - theta2
    else:
        cfg.gates['g5'].angle = theta1
        cfg.gates['g6'].angle = -theta2
    cell = Simulation(cfg)
    cell.run()
    probs = {'same': 0.0, 'diff': 0.0, 'uncoupled': 0.0}
    for point in cell.result_space.index.values():
        probs[classify(point, two_stage)] += float(point.probability)
    coupled = probs['same'] + probs['diff']
    result = {
        'exact': probs['diff'] / coupled if coupled > 0 else 0.0,
        'analytical': float(qn.simplify((theta1 - theta2).sin ** 2)),
        'classical': float(2 * abs(theta1 - theta2) / qn.PI_fn()),
    }
    if n_trials and rng is not None:
        tally = sample_terminal(cell.result_space, n_trials, rng)
        counts = epr_tally(cell.result_space, tally, two_stage)
        n_coupled = counts['same'] + counts['diff']
        result['sampled'] = counts['diff'] / n_coupled if n_coupled else 0.0
        result['counts'] = counts
    return result


def observed_rate(cell: dict) -> float:
    """The experiment's discrepancy for one grid cell: the sampled rate
    when trials were run, the exact rate otherwise."""
    return cell.get('sampled', cell['exact'])


def correlation_from_discrepancy(d) -> float:
    """E(a,b) = 1 − 2·discrepancy(a,b)."""
    return 1.0 - 2.0 * float(d)


def chsh_max(grid: dict, rate=observed_rate) -> tuple[float, tuple]:
    """Maximum |S| over all CHSH quadruples from the grid's labels:
    S = E(a,b) − E(a,b') + E(a',b) + E(a',b'). Classical hidden-variable
    theories require |S| ≤ 2; quantum mechanics can reach 2√2."""
    labels = sorted({label for pair in grid for label in pair})

    def E(x, y):
        return correlation_from_discrepancy(rate(grid[(x, y)]))

    best_s, best_quad = 0.0, (labels[0],) * 4
    for a in labels:
        for ap in labels:
            if ap == a:
                continue
            for b in labels:
                for bp in labels:
                    if bp == b:
                        continue
                    s = abs(E(a, b) - E(a, bp) + E(ap, b) + E(ap, bp))
                    if s > best_s:
                        best_s, best_quad = s, (a, ap, b, bp)
    return best_s, best_quad


def bell_max(grid: dict, rate=observed_rate) -> tuple[float, tuple]:
    """Largest violation of Bell's original three-angle inequality in
    discrepancy form: d(a,c) ≤ d(a,b) + d(b,c). Returns (excess, (a,b,c));
    positive excess ⇒ violation."""
    labels = sorted({label for pair in grid for label in pair})

    def d(x, y):
        return float(rate(grid[(x, y)]))

    best_excess, best_triple = None, (labels[0],) * 3
    for a in labels:
        for b in labels:
            if b == a:
                continue
            for c in labels:
                if c in (a, b):
                    continue
                excess = d(a, c) - d(a, b) - d(b, c)
                if best_excess is None or excess > best_excess:
                    best_excess, best_triple = excess, (a, b, c)
    return best_excess, best_triple


def run_epr_experiment(sim, n_trials: int = 0, seed=None) -> dict:
    """The full Bell/CHSH experiment: sweep (θ1, θ2) over the 3×3 grid of
    magic angles, tabulate discrepancy rates, and test both inequalities.
    Logs a report; returns {'grid', 'bell', 'chsh', 'values'}.
    """
    if not supports_epr(sim):
        log.info('model lacks the EPR structure (g4/g5/g6); skipping experiment')
        return None
    values = magic_angles(sim)
    labels = list(values.keys())
    rng = random.Random(seed)
    two_stage = is_two_stage(sim)

    # The 9 cell simulations re-log the whole setup at INFO; quiet them.
    saved_level = log.level
    log.setLevel(logging.WARNING)
    try:
        grid = {(l1, l2): run_pair(sim, values[l1], values[l2], n_trials, rng)
                for l1 in labels for l2 in labels}
    finally:
        log.setLevel(saved_level)

    log.info(' ')
    log.info(f'EPR-BELL EXPERIMENT ({"two-stage" if two_stage else "one-stage"}: '
             f'{"g7/g8" if two_stage else "g5/g6"} overridden, '
             f'{n_trials or "no"} trials per cell'
             f'{f", seed={seed}" if seed is not None else ""})')
    angle_strs = [f'{label}={float(values[label].degrees):.1f}º' for label in labels]
    log.info(f'   magic angles: {", ".join(angle_strs)}')
    log.info(' ')

    def table(title, getter, fmt='{:.4f}'):
        log.info(f'   {title}:')
        header = '        ' + ''.join(f'{label:>10}' for label in labels)
        log.info(f'   {header}')
        for l1 in labels:
            row = ''.join(f'{fmt.format(getter(grid[(l1, l2)])):>10}' for l2 in labels)
            log.info(f'   {l1:>8}{row}')
        log.info(' ')

    if n_trials:
        table('observed discrepancy (sampled)', observed_rate)
    table('exact discrepancy', lambda c: c['exact'])
    table('analytical sin²(θ1−θ2)', lambda c: c['analytical'])
    table('classical hidden-variable prediction', lambda c: c['classical'])

    exact_rate = lambda cell: cell['exact']
    for label, rate in (('observed', observed_rate), ('exact', exact_rate)):
        if label == 'observed' and not n_trials:
            continue
        bell_excess, bell_triple = bell_max(grid, rate)
        chsh_s, chsh_quad = chsh_max(grid, rate)
        a, b, c = bell_triple
        log.info(f'   Bell d(a,c) ≤ d(a,b)+d(b,c) [{label}]: '
                 f'max excess = {bell_excess:+.4f} at (a={a}, b={b}, c={c}) — '
                 f'{"VIOLATED" if bell_excess > 1e-9 else "satisfied"}')
        a, ap, b, bp = chsh_quad
        log.info(f'   CHSH |S| ≤ 2 [{label}]: max |S| = {chsh_s:.4f} '
                 f'at (a={a}, a\'={ap}, b={b}, b\'={bp}) — '
                 f'{"VIOLATED" if chsh_s > 2 + 1e-9 else "satisfied"}')
    log.info(' ')
    return {'grid': grid, 'values': values,
            'bell': bell_max(grid), 'chsh': chsh_max(grid),
            'bell_exact': bell_max(grid, exact_rate),
            'chsh_exact': chsh_max(grid, exact_rate)}