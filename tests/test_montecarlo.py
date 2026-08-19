"""Statistical checks for the Monte Carlo sampler.

Fixed seeds and generous tolerances: at n trials the expected total
variation distance from the exact distribution is O(1/sqrt(n)), so 0.02 at
n=20000 gives a wide margin against flakiness while still catching real
distribution errors.
"""
import logging
import random
import unittest
from pathlib import Path

import yaml
from addict import Addict

REPO_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_DIR / 'models'

import quantish.qnumber as qn
from quantish.qnumber import CalcMode

N_TRIALS = 20000
SEED = 12345
NOISE_TOLERANCE = 0.02


def run_sim(name):
    from quantish.simulation import Simulation
    with open(MODELS_DIR / 'defaults.yaml') as f:
        config = yaml.safe_load(f)
    with open((MODELS_DIR / name).with_suffix('.yaml')) as f:
        config.update(yaml.safe_load(f))
    config['loglevel'] = 'warning'
    sim = Simulation(Addict(config))
    sim.run()
    return sim


def tvd(tally, predicted, n):
    keys = set(tally) | set(predicted)
    return sum(abs(tally.get(k, 0) / n - predicted.get(k, 0.0)) for k in keys) / 2


class TestMonteCarlo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger('quantish').setLevel(logging.WARNING)
        CalcMode.default('Float')
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()

    def test_terminal_matches_exact_distribution(self):
        from quantish.montecarlo import predicted_distribution, sample_terminal
        sim = run_sim('gr2026/fig410')
        predicted = predicted_distribution(sim.result_space)
        tally = sample_terminal(sim.result_space, N_TRIALS, random.Random(SEED))
        self.assertEqual(sum(tally.values()), N_TRIALS)
        self.assertLessEqual(tvd(tally, predicted, N_TRIALS), NOISE_TOLERANCE)

    def test_path_matches_exact_when_no_interference(self):
        # fig49 has no world merging, so per-stage sampling is equivalent to
        # sampling the final superposition.
        from quantish.montecarlo import predicted_distribution, sample_paths
        sim = run_sim('gr2026/fig410')
        predicted = predicted_distribution(sim.result_space)
        tally, dead_ends = sample_paths(sim.initial_point, len(sim.run_stages),
                                        N_TRIALS, random.Random(SEED))
        self.assertEqual(dead_ends, 0)
        self.assertEqual(sum(tally.values()), N_TRIALS)
        self.assertLessEqual(tvd(tally, predicted, N_TRIALS), NOISE_TOLERANCE)

    def test_interference_separates_the_modes(self):
        # fig411 interferes: terminal sampling must track the exact
        # distribution, and path sampling (collapse at every stage) must
        # measurably diverge from it. This also guards the per-edge
        # contribution data the path sampler walks.
        from quantish.montecarlo import (predicted_distribution,
                                           sample_paths, sample_terminal)
        sim = run_sim('gr2026/fig412')
        predicted = predicted_distribution(sim.result_space)
        terminal = sample_terminal(sim.result_space, N_TRIALS, random.Random(SEED))
        self.assertLessEqual(tvd(terminal, predicted, N_TRIALS), NOISE_TOLERANCE)
        paths, _ = sample_paths(sim.initial_point, len(sim.run_stages),
                                N_TRIALS, random.Random(SEED))
        self.assertGreaterEqual(tvd(paths, predicted, N_TRIALS), 0.05)


if __name__ == '__main__':
    unittest.main()