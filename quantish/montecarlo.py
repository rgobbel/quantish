"""Monte Carlo simulation of quantish experiments.

Replaces the old spacewalk module. Each trial produces one observed outcome,
as a real-world run of the experiment would; tabulating many trials
approximates the exact configuration-space point probabilities.

Two samplers here — two interpretations sampling the same wave — and
a third model in epr.py that samples no wave at all:

terminal
    Draw a final configuration-space point with probability |weight|^2
    (renormalized). The superposition evolves undisturbed until the end,
    so interference is fully preserved and observed frequencies converge
    on point.probability. The Everettian "which branch am I in" sampler,
    and the faithful simulation of a real experiment.

pilot
    One guided trajectory per trial, steered by the full wave (de
    Broglie-Bohm, in the discrete stochastic form of Bell 1984 / Vink
    1993): at each stage the actual configuration moves to a successor
    with a probability from a coupling whose marginals are the stage's
    exact |w|^2 (pilot_transitions), so the walker is distributed as
    the wave at every stage, never dead-ends, and matches every
    prediction — nonlocally, since the whole wave steers it. Discrete
    pilot-wave dynamics are not unique; this picks the maximum-entropy
    coupling on the DAG's edges.

hidden (epr.sample_hidden_variable, for the Bell/CHSH sweep only)
    Bell's local hidden-variable example: each trial draws one hidden
    angle shared by both particles at the source, and each detector
    reads its outcome from that angle and its own setting alone. Its
    discrepancy is the linear law 2|θ1 − θ2|/π, which saturates Bell's
    inequality — the most a local model can do, and the bound the wave
    crosses.
"""
import logging
import random
from collections import Counter

import quantish.qnumber as qn
from quantish.epr import epr_tally, expected_discrepancy, is_two_stage, log_epr

log = logging.getLogger('quantish')


def _prob(weight) -> float:
    # sampling needs floats: the exact |w|², converted once, here
    return qn.to_float(qn.probability(weight))


def predicted_distribution(result_space) -> dict:
    """Exact final-world distribution: key -> normalized |weight|^2."""
    probs = {p.key: _prob(p.weight) for p in result_space.index.values()}
    total = sum(probs.values())
    if total > 0:
        probs = {k: v / total for k, v in probs.items()}
    return probs


def sample_terminal(result_space, n_trials: int, rng: random.Random) -> Counter:
    """Draw n_trials outcomes from the final configuration-space points, |weight|^2 each."""
    points = list(result_space.index.values())
    weights = [_prob(p.weight) for p in points]
    picks = rng.choices(points, weights=weights, k=n_trials)
    return Counter(p.key for p in picks)


def _sinkhorn(kernel: dict, row_mass: dict, col_mass: dict,
              iters: int = 500, tol: float = 1e-12) -> dict:
    """Scale a nonnegative kernel on the predecessor->successor edges so
    its row sums equal each predecessor's |w|^2 and its column sums each
    successor's |w'|^2 (iterative proportional fitting). The result is a
    coupling: a joint distribution over (predecessor, successor) whose
    marginals are the stage's exact probabilities."""
    coupling = dict(kernel)
    rows = {i: [e for e in coupling if e[0] is i] for i in row_mass}
    cols = {j: [e for e in coupling if e[1] is j] for j in col_mass}
    for _ in range(iters):
        worst = 0.0
        for i, edges in rows.items():
            s = sum(coupling[e] for e in edges)
            if s > 0:
                f = row_mass[i] / s
                for e in edges:
                    coupling[e] *= f
        for j, edges in cols.items():
            s = sum(coupling[e] for e in edges)
            if s > 0:
                f = col_mass[j] / s
                for e in edges:
                    coupling[e] *= f
        for i, edges in rows.items():
            s = sum(coupling[e] for e in edges)
            worst = max(worst, abs(s - row_mass[i]))
        if worst < tol:
            break
    return coupling


def pilot_transitions(initial_points) -> tuple[list[dict], list[list]]:
    """Bell-Vink style guidance for the discrete pilot wave.

    For each stage, a transition table P(successor | predecessor) over the
    live configuration-space points, chosen so that a walker distributed as
    |w|^2 over the predecessors is distributed as |w'|^2 over the successors
    (equivariance). The walker therefore tracks the wave exactly, stage by
    stage, and can never step onto a point whose weight interference has
    canceled. The discrete pilot wave is not unique; this picks the
    maximum-entropy coupling on the DAG's edges, seeded with each edge's
    squared contributed amplitude and fitted to the exact marginals.
    Returns (per-stage transition tables, per-stage live point lists).
    """
    live = [p for p in (initial_points if isinstance(initial_points, (list, tuple))
                        else [initial_points]) if _prob(p.weight) > 0]
    tables, levels = [], [list(live)]
    while True:
        nxt = {}
        for p in live:
            for s in p.successors:
                if s.step == p.step + 1 and _prob(s.weight) > 0:
                    nxt[id(s)] = s
        succ = list(nxt.values())
        if not succ:
            break
        row = {p: _prob(p.weight) for p in live}
        col = {s: _prob(s.weight) for s in succ}
        kernel = {(p, s): _prob(s.contributions[p])
                  for p in live for s in succ if p in s.contributions}
        coupling = _sinkhorn(kernel, row, col)
        table = {}
        for (p, s), mass in coupling.items():
            if mass > 0:
                table.setdefault(p, []).append((s, mass / row[p]))
        # the fit is feasible when every live predecessor has a live
        # successor on its edges — unitarity plus the merge rule should
        # guarantee it; say so if a model ever breaks it
        stranded = [p for p in live if p not in table]
        if stranded:
            log.warning(f'pilot wave: {len(stranded)} configuration-space '
                        f'point(s) at step {live[0].step} have no live '
                        f'successor; guided trajectories from them stop there')
        tables.append(table)
        live = succ
        levels.append(list(live))
    return tables, levels


def sample_pilot(initial_points, n_trials: int, rng: random.Random,
                 transitions=None) -> Counter:
    """One pilot-wave trajectory per trial: the wave (all weights, every
    branch) is computed as usual; a single actual configuration moves along
    the DAG using pilot_transitions. Never dead-ends. `transitions` (a
    pilot_transitions result) lets a chunked caller fit the guidance
    once and draw many times."""
    tables, levels = (transitions if transitions is not None
                      else pilot_transitions(initial_points))
    starts = levels[0]
    start_w = [_prob(p.weight) for p in starts]
    tally = Counter()
    for _ in range(n_trials):
        world = rng.choices(starts, weights=start_w)[0]
        for table in tables:
            opts = table.get(world)
            if not opts:
                break
            world = rng.choices([o[0] for o in opts], weights=[o[1] for o in opts])[0]
        tally[world.key] += 1
    return tally


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


def run_monte_carlo(sim, n_trials: int, mode: str = 'terminal', seed=None) -> dict:
    """Run Monte Carlo trials against a finished simulation.

    mode: 'terminal', 'pilot', or 'both'. Returns a dict with the
    predicted distribution, per-mode tallies, and (for epr_stats models)
    same/diff counts.
    """
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

    if mode in ('pilot', 'both'):
        tally = sample_pilot(sim.initial_points, n_trials, rng)
        results['pilot'] = tally
        log_tally('pilot-wave sampling (one guided trajectory per trial; never dead-ends)',
                  tally, predicted, n_trials)
        if getattr(sim, 'epr_stats', False) or two_stage:
            results['pilot_epr'] = epr_tally(sim.result_space, tally, two_stage)
            log_epr('pilot', results['pilot_epr'], expected_discrepancy(sim))

    return results

