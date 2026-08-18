"""Monte Carlo simulation of quantish experiments.

Replaces the old spacewalk module. Each trial produces one observed outcome,
as a real-world run of the experiment would; tabulating many trials
approximates the exact CS point probabilities.

Two sampling modes:

terminal
    Draw a final CS point with probability |weight|^2 (renormalized). The
    superposition evolves undisturbed until the end, so interference is
    fully preserved and observed frequencies converge on point.probability.
    This is the faithful simulation of a real experiment.

path
    Walk the full quantish state's DAG one stage at a time: from the current
    CS point, choose a successor with probability proportional to
    |the amplitude this world contributed to it|^2. Each trial yields a
    full world-line (a story of the run), but choosing per stage amounts to
    collapsing at every stage: on circuits where worlds interfere, path
    statistics legitimately diverge from the exact probabilities.
    The divergence itself is informative — it measures how much
    interference matters downstream.
"""
import logging
import random
from collections import Counter, defaultdict

log = logging.getLogger('multiworld')


def _prob(weight) -> float:
    return abs(complex(weight)) ** 2


def predicted_distribution(result_space) -> dict:
    """Exact final-world distribution: key -> normalized |weight|^2."""
    probs = {p.key: _prob(p.weight) for p in result_space.index.values()}
    total = sum(probs.values())
    if total > 0:
        probs = {k: v / total for k, v in probs.items()}
    return probs


def sample_terminal(result_space, n_trials: int, rng: random.Random) -> Counter:
    """Draw n_trials outcomes from the final CS points, |weight|^2 each."""
    points = list(result_space.index.values())
    weights = [_prob(p.weight) for p in points]
    picks = rng.choices(points, weights=weights, k=n_trials)
    return Counter(p.key for p in picks)


def sample_paths(initial_point, n_steps: int, n_trials: int,
                 rng: random.Random) -> tuple[Counter, int]:
    """Walk the world DAG stage by stage, n_trials times.

    At each stage the next world is chosen among the current world's
    successors with probability proportional to |contributed amplitude|^2.
    Returns (tally of final-world keys, number of dead-ended trials).
    Trials dead-end only when every successor's weight was cancelled by
    interference (the contributed amplitude went nowhere observable).
    """
    tally = Counter()
    dead_ends = 0
    for _ in range(n_trials):
        world = initial_point
        for _step in range(n_steps):
            children = [s for s in world.successors if s.step == world.step + 1]
            weights = [_prob(s.contributions[world]) for s in children
                       if world in s.contributions]
            children = [s for s in children if world in s.contributions]
            if not children or sum(weights) <= 0:
                dead_ends += 1
                world = None
                break
            world = rng.choices(children, weights=weights, k=1)[0]
        if world is not None:
            tally[world.key] += 1
    return tally, dead_ends


def epr_tally(result_space, tally: Counter, two_stage: bool) -> dict:
    """Same/diff counts for EPR-style models, using the outcome convention
    from multiworld.epr (plain position after two measurement stages,
    position⊕sign after one)."""
    from multiworld.epr import classify
    by_key = {p.key: p for p in result_space.index.values()}
    counts = {'same': 0, 'diff': 0, 'uncoupled': 0}
    for key, n in tally.items():
        point = by_key.get(key)
        if point is None:
            continue
        counts[classify(point, two_stage)] += n
    return counts


def log_tally(label: str, tally: Counter, predicted: dict, n_trials: int):
    log.info(f'{label}:')
    log.info(f'   {"observed":>10} {"frequency":>10} {"predicted":>10}   configuration')
    tvd = 0.0
    for key in sorted(set(tally) | set(predicted), key=lambda k: -predicted.get(k, 0)):
        observed = tally.get(key, 0)
        freq = observed / n_trials if n_trials else 0.0
        pred = predicted.get(key, 0.0)
        tvd += abs(freq - pred)
        log.info(f'   {observed:>10} {freq:>10.4f} {pred:>10.4f}   {key}')
    log.info(f'   total variation distance from prediction: {tvd / 2:.4f}')
    log.info(' ')
    return tvd / 2


def run_monte_carlo(sim, n_trials: int, mode: str = 'both', seed=None) -> dict:
    """Run Monte Carlo trials against a finished simulation.

    mode: 'terminal', 'path', or 'both'. Returns a dict with the predicted
    distribution, per-mode tallies, and (for epr_stats models) same/diff
    counts.
    """
    from multiworld.epr import expected_discrepancy, is_two_stage
    if sim.result_space is None:
        sim.run()
    rng = random.Random(seed)
    predicted = predicted_distribution(sim.result_space)
    two_stage = is_two_stage(sim)
    results = {'n_trials': n_trials, 'predicted': predicted, 'seed': seed}
    log.info(' ')
    log.info(f'MONTE CARLO: {n_trials} trials'
             f'{f", seed={seed}" if seed is not None else ""}')
    log.info(' ')

    if mode in ('terminal', 'both'):
        tally = sample_terminal(sim.result_space, n_trials, rng)
        results['terminal'] = tally
        log_tally('terminal sampling (one draw from the final superposition per trial)',
                  tally, predicted, n_trials)
        if sim.config.get('epr_stats'):
            results['terminal_epr'] = epr_tally(sim.result_space, tally, two_stage)
            log_epr('terminal', results['terminal_epr'], expected_discrepancy(sim))

    if mode in ('path', 'both'):
        n_steps = len(sim.run_stages)
        tally, dead_ends = sample_paths(sim.initial_point, n_steps, n_trials, rng)
        results['path'] = tally
        results['path_dead_ends'] = dead_ends
        log_tally('path sampling (one world-line per trial; collapses at every stage)',
                  tally, predicted, n_trials)
        if dead_ends:
            log.info(f'   {dead_ends} trial(s) dead-ended in fully-cancelled worlds')
        if sim.config.get('epr_stats'):
            results['path_epr'] = epr_tally(sim.result_space, tally, two_stage)
            log_epr('path', results['path_epr'], expected_discrepancy(sim))

    return results


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