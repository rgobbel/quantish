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

The Bell/CHSH experiment sweeps measurement angles (θ1, θ2) over three
sweep angles, by default {qa=0, qb=π/8, qc=π/4} (the model's Qa/Qb/Qc
variables when it defines them).
"Measuring p1 at θ1 and p2 at θ2" means overriding

    two-stage:  g7 = θ1,  g8 = (Q5+Q6) − θ2   (Q5/Q6 keep base values)
    one-stage:  g5 = θ1,  g6 = −θ2

which reduces the intrinsic law to sin²(θ1 − θ2) in both cases — so the
YAML angles of the overridden gates are placeholders.

Models may instead declare `theta1` and `theta2` in their variables and
reference them by name in the gate expressions (two-stage:
g7: {angle: Q7} with Q7: 'theta1', g8: {angle: Q8} with
Q8: '(Q5 + Q6) - theta2'); the sweep then
rebinds the two variables and never touches the gates, keeping the model
the single source of truth for how the measurement angles enter.
"""
import logging
import math
import random
from collections import Counter
from copy import deepcopy

import quantish.qnumber as qn
from quantish.qnumber import qify

log = logging.getLogger('quantish')

# The default sweep angles (0°, 22.5°, 45°), used when the model doesn't
# define qa/qb/qc; the models that do use the same set.
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
    """'same' / 'diff' (the two measured particles' outcomes agree /
    disagree) for configuration-space points where the coupling particle exited g4 on the
    upper wire, else 'uncoupled'.

    The coupling particle is identified structurally — the one whose final
    origin is the coupling gate g4 — so renaming or reordering particles
    in the model can't silently misassign the roles. (Falls back to the
    positional p1/p2/p3 convention if the structure is ambiguous.)"""
    coords = list(point.coords.values())
    if len(coords) < 3:
        return 'uncoupled'
    couplers = [c for c in coords
                if c.position.origin is not None
                and c.position.origin.gate == 'g4']
    others = [c for c in coords if c not in couplers]
    if len(couplers) != 1 or len(others) < 2:
        couplers = [coords[2]]
        others = coords[:2]
    origin = couplers[0].position.origin
    if origin is None or origin.port != 'upper':
        return 'uncoupled'
    if outcome(others[0], two_stage) == outcome(others[1], two_stage):
        return 'same'
    return 'diff'


def epr_tally(result_space, tally: Counter, two_stage: bool) -> dict:
    """Same/diff counts for EPR-style models over a Monte Carlo tally,
    using classify's outcome convention (plain position after two
    measurement stages, position⊕sign after one)."""
    by_key = {p.key: p for p in result_space.index.values()}
    counts = {'same': 0, 'diff': 0, 'uncoupled': 0}
    for key, n in tally.items():
        point = by_key.get(key)
        if point is None:
            continue
        counts[classify(point, two_stage)] += n
    return counts


def log_epr(label: str, counts: dict, predicted=None):
    coupled = counts['same'] + counts['diff']
    if coupled == 0:
        log.info(f'   EPR ({label}): no coupled trials')
        return
    predstr = f', predicted={float(predicted):.4f}' if predicted is not None else ''
    log.info(f"   EPR ({label}): same={counts['same']}, diff={counts['diff']}, "
             f"uncoupled={counts['uncoupled']}, "
             f"discrepancy rate={counts['diff'] / coupled:.4f}{predstr}")
    log.info(' ')


# --------------------------------------------------------------------------
# The Bell/CHSH experiment: a 3×3 sweep over the three sweep angles.
# --------------------------------------------------------------------------

def supports_epr(sim) -> bool:
    """True when the model has the EPR structure: the p3-coupling gate g4
    to condition on, plus measurement gates g5/g6."""
    return {'g4', 'g5', 'g6'} <= set(sim.gates.keys())


def sweep_angles(sim) -> dict:
    """The three labeled sweep angles: the model's qa/qb/qc variables when
    all three are defined and distinct, else the default {0, pi/8, pi/4}."""
    found = {name: qify(value) for name, value in sim.qvars.items()
             if name.lower() in ('qa', 'qb', 'qc')}
    if len(found) == 3:
        if len({float(v) for v in found.values()}) == 3:
            return found
        log.warning(f'   model sweep angles are not distinct '
                    f'({", ".join(f"{k}={float(v):.4f}" for k, v in found.items())}); '
                    f'using the default set instead')
    return {name: qify(value) for name, value in DEFAULT_VALUES.items()}


SAMPLERS = ('terminal', 'pilot', 'hidden')


def hidden_outcome(theta: float, hidden: float) -> str:
    """Bell's local hidden-variable example, in this circuit's angle
    convention: a detector at angle theta reports 'upper' when the
    hidden angle lies within 45° of theta (mod π), 'lower' otherwise —
    sign(cos 2(theta − λ)). The doubled angle matches the circuit's law
    sin²(θ1 − θ2), whose period is π."""
    return 'upper' if math.cos(2 * (theta - hidden)) >= 0 else 'lower'


def folded_difference(theta1, theta2):
    """|θ1 − θ2| folded into [0, π/2]: the angle difference a detector
    pair actually sees, since the circuit's law has period π and is
    symmetric about π/2. The classical linear law needs this fold
    explicitly (2|Δ|/π would exceed 1 past π/2 and read 2 at Δ = π,
    where the hidden-variable model correctly gives 0); sin²Δ folds
    itself, which is the kink versus the smooth law in one line."""
    d = abs(qify(theta1) - qify(theta2)) % qn.PI
    return qn.PI - d if d > qn.PI / 2 else d


def sample_hidden_variable(theta1, theta2, n_trials: int, rng) -> dict:
    """n_trials of Bell's local hidden-variable model: each trial draws
    one hidden angle λ uniformly on [0, π), shared by both particles at
    the source, and each detector reads its outcome from λ and its own
    angle alone (hidden_outcome) — nothing passes between the two
    measurements. The discrepancy rate is 2|θ1 − θ2|/π: the linear law
    of the 'classical' grid, which saturates Bell's inequality and
    respects the CHSH bound. Same/diff counts, like epr_tally's."""
    t1, t2 = qn.to_float(qify(theta1)), qn.to_float(qify(theta2))
    counts = {'same': 0, 'diff': 0, 'uncoupled': 0}
    for _ in range(n_trials):
        hidden = rng.uniform(0.0, math.pi)
        counts['same' if hidden_outcome(t1, hidden) == hidden_outcome(t2, hidden)
               else 'diff'] += 1
    return counts


def sample_cell(cell, n_trials: int, rng, mode: str = 'terminal'):
    """n_trials draws from a run cell under one sampling interpretation
    of the wave: 'terminal' (the final superposition) or 'pilot' (one
    wave-guided trajectory per trial). Returns the tally. The 'hidden'
    model samples no wave at all: see sample_hidden_variable, dispatched
    by run_pair."""
    from quantish.montecarlo import sample_pilot, sample_terminal
    if mode == 'terminal':
        return sample_terminal(cell.result_space, n_trials, rng)
    if mode == 'pilot':
        return sample_pilot(cell.initial_points, n_trials, rng)
    raise ValueError(f'mode must be one of {SAMPLERS}, not {mode!r}')


def run_pair(sim, theta1, theta2, n_trials: int = 0, rng=None,
             mode: str = 'terminal') -> dict:
    """Run one experiment cell, measuring p1 at theta1 and p2 at theta2.

    Rebuilds the simulation with the measurement gates overridden per the
    module-docstring convention and returns the conditional discrepancy:
    'exact' from the final configuration-space points, 'sampled' from
    n_trials draws under `mode` (see sample_cell, or for 'hidden'
    sample_hidden_variable; when n_trials > 0), 'analytical' =
    sin²(θ1−θ2), and 'classical' — the linear hidden-variable
    prediction 2|θ1−θ2|/π with the difference folded into [0, π/2]
    (folded_difference), which Bell's example (mode 'hidden') samples.
    """
    # local imports: montecarlo imports this module at top level, so the
    # reverse direction must stay deferred (and Simulation likewise)
    from quantish.simulation import Simulation
    theta1 = qify(theta1)
    theta2 = qify(theta2)
    two_stage = is_two_stage(sim)
    cfg = deepcopy(sim.config)
    if 'theta1' in cfg.variables and 'theta2' in cfg.variables:
        # Variable convention: the model's own gate expressions reference
        # theta1/theta2 by name (e.g. g7: {angle: theta1},
        # g8's angle depending on theta2), so the sweep just rebinds
        # the variables and the model stays the single source of truth
        # for how the measurement angles enter the circuit.
        cfg.variables['theta1'] = theta1
        cfg.variables['theta2'] = theta2
    elif two_stage:
        base = sim.gates['g5'].theta + sim.gates['g6'].theta
        cfg.gates['g7'].angle = theta1
        cfg.gates['g8'].angle = base - theta2
    else:
        cfg.gates['g5'].angle = theta1
        cfg.gates['g6'].angle = -theta2
    cell = Simulation(cfg)
    cell.run()
    # the cell's probabilities and rates stay in the engine's number
    # system (exact in Symbolic mode); callers convert for display or
    # for the Bell/CHSH comparisons
    probs = {'same': qn.ZERO, 'diff': qn.ZERO, 'uncoupled': qn.ZERO}
    for point in cell.result_space.index.values():
        c = classify(point, two_stage)
        probs[c] = probs[c] + point.probability
    coupled = probs['same'] + probs['diff']
    result = {
        'exact': (qn.simplify(probs['diff'] / coupled)
                  if not qn.zerop(coupled) else qn.ZERO),
        'analytical': qn.simplify((theta1 - theta2).sin ** 2),
        'classical': qn.simplify(2 * folded_difference(theta1, theta2) / qn.PI),
    }
    if n_trials and rng is not None:
        if mode == 'hidden':
            counts = sample_hidden_variable(theta1, theta2, n_trials, rng)
        else:
            tally = sample_cell(cell, n_trials, rng, mode)
            counts = epr_tally(cell.result_space, tally, two_stage)
        n_coupled = counts['same'] + counts['diff']
        result['sampled'] = counts['diff'] / n_coupled if n_coupled else 0.0
        # a sampled rate is a float by nature (a count ratio)
        result['counts'] = counts
    return result


def observed_rate(cell: dict) -> float:
    """The experiment's discrepancy for one grid cell as a float: the
    sampled rate when trials were run, the exact rate otherwise."""
    return qn.to_float(cell.get('sampled', cell['exact']))


def correlation_from_discrepancy(d) -> float:
    """E(a,b) = 1 − 2·discrepancy(a,b)."""
    return 1.0 - 2.0 * qn.to_float(d)


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
        return qn.to_float(rate(grid[(x, y)]))

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


def verdict_slack(n_trials: int) -> tuple[float, float]:
    """How far a sampled Bell excess and CHSH sum may exceed their bounds
    by noise alone: 3σ, where a rate from n trials has σ ≤ ½/√n, the
    Bell excess combines three rates, and the CHSH sum four correlations
    E = 1 − 2d. Returns (bell_slack, chsh_slack)."""
    sigma = 0.5 / math.sqrt(n_trials)
    return 3 * math.sqrt(3) * sigma, 3 * 4 * sigma


def verdict(excess: float, slack: float) -> str:
    """The word for how a statistic stands to its bound, given its
    excess over the bound and the slack noise allows: 'VIOLATED' beyond
    the slack, 'saturated' within it on either side — the statistic
    sits on the bound, which is where Bell's own hidden-variable model
    lands — and 'satisfied' below it."""
    if excess > slack:
        return 'VIOLATED'
    if excess >= -slack:
        return 'saturated (on the bound)'
    return 'satisfied'


def classical_rate(cell: dict) -> float:
    """The classical hidden-variable law's discrepancy for a grid cell."""
    return qn.to_float(cell['classical'])


def run_epr_experiment(sim, n_trials: int = 0, seed=None, values=None,
                       mode: str = 'terminal') -> dict:
    """The full Bell/CHSH experiment: sweep (θ1, θ2) over the 3×3 grid of
    sweep angles, tabulate discrepancy rates, and test both inequalities.
    `values` overrides the angle set ({label: angle-in-radians}, any qify
    form); default is the model's qa/qb/qc or the default set. `mode`
    is the sampling interpretation for the sampled rates (sample_cell).
    Logs a report; returns {'grid', 'bell', 'chsh', 'values'}.
    """
    if not supports_epr(sim):
        log.info('model lacks the EPR structure (g4/g5/g6); skipping experiment')
        return None
    values = ({name: qify(value) for name, value in values.items()}
              if values is not None else sweep_angles(sim))
    labels = list(values.keys())
    rng = random.Random(seed)
    two_stage = is_two_stage(sim)

    # The 9 cell simulations re-log the whole setup at INFO; quiet them.
    saved_level = log.level
    log.setLevel(logging.WARNING)
    try:
        grid = {(l1, l2): run_pair(sim, values[l1], values[l2], n_trials, rng, mode)
                for l1 in labels for l2 in labels}
    finally:
        log.setLevel(saved_level)

    log.info(' ')
    log.info(f'EPR-BELL EXPERIMENT ({"two-stage" if two_stage else "one-stage"}: '
             f'{"g7/g8" if two_stage else "g5/g6"} overridden, '
             f'{n_trials or "no"} trials per cell'
             f'{f" [{mode}]" if n_trials else ""}'
             f'{f", seed={seed}" if seed is not None else ""})')
    angle_strs = [f'{label}={float(values[label].degrees):.1f}º' for label in labels]
    log.info(f'   sweep angles: {", ".join(angle_strs)}')
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
        table(f'{mode} sampled results ({n_trials} trials per cell)', observed_rate)
    table('exact quantish simulation results', lambda c: c['exact'])
    table('analytical law sin²(θ1−θ2)', lambda c: c['analytical'])
    table('classical hidden-variable law', lambda c: c['classical'])

    exact_rate = lambda cell: cell['exact']
    # the classical law's own verdict shows what a local model can do
    # at best: it saturates Bell's bound (excess exactly 0, |S| = 2)
    for label, rate in (('observed', observed_rate), ('exact', exact_rate),
                        ('classical', classical_rate)):
        if label == 'observed' and not n_trials:
            continue
        # a sampled excess must clear sampling noise to count (the
        # hidden-variable model sits exactly at the bound); the slack
        # is verdict_slack's 3σ, zero for exact rates
        bell_slack, chsh_slack = (verdict_slack(n_trials) if label == 'observed'
                                  else (1e-9, 1e-9))
        bell_excess, bell_triple = bell_max(grid, rate)
        chsh_s, chsh_quad = chsh_max(grid, rate)
        a, b, c = bell_triple
        log.info(f'   Bell d(a,c) ≤ d(a,b)+d(b,c) [{label}]: '
                 f'max excess = {bell_excess:+.4f} at (a={a}, b={b}, c={c}) — '
                 f'{verdict(bell_excess, bell_slack)}')
        a, ap, b, bp = chsh_quad
        log.info(f'   CHSH |S| ≤ 2 [{label}]: max |S| = {chsh_s:.4f} '
                 f'at (a={a}, a\'={ap}, b={b}, b\'={bp}) — '
                 f'{verdict(chsh_s - 2, chsh_slack)}')
    log.info(' ')
    return {'grid': grid, 'values': values,
            'bell': bell_max(grid), 'chsh': chsh_max(grid),
            'bell_exact': bell_max(grid, exact_rate),
            'chsh_exact': chsh_max(grid, exact_rate),
            'bell_classical': bell_max(grid, classical_rate),
            'chsh_classical': chsh_max(grid, classical_rate)}