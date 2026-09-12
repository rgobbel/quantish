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
from addict import Dict as Addict

REPO_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_DIR / 'models'

from quantish.qnumber import CalcMode

N_TRIALS = 20000
SEED = 12345
NOISE_TOLERANCE = 0.02


def run_sim(name):
    from quantish.simulation import Simulation
    with open(MODELS_DIR / 'defaults.yaml') as f:
        config = yaml.safe_load(f)
    with open(MODELS_DIR / f'{name}.yaml') as f:
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

    def test_terminal_matches_exact_distribution(self):
        from quantish.montecarlo import predicted_distribution, sample_terminal
        sim = run_sim('gr2026/fig4.10')
        predicted = predicted_distribution(sim.result_space)
        tally = sample_terminal(sim.result_space, N_TRIALS, random.Random(SEED))
        self.assertEqual(sum(tally.values()), N_TRIALS)
        self.assertLessEqual(tvd(tally, predicted, N_TRIALS), NOISE_TOLERANCE)

    def test_pilot_matches_exact_when_no_interference(self):
        # fig 4.10 has no merging, so a stage-by-stage walk is equivalent
        # to sampling the final superposition
        from quantish.montecarlo import predicted_distribution, sample_pilot
        sim = run_sim('gr2026/fig4.10')
        predicted = predicted_distribution(sim.result_space)
        tally = sample_pilot(sim.initial_points, N_TRIALS, random.Random(SEED))
        self.assertEqual(sum(tally.values()), N_TRIALS)
        self.assertLessEqual(tvd(tally, predicted, N_TRIALS), NOISE_TOLERANCE)

    def test_interference_is_kept_by_both_samplers(self):
        # fig 4.12 interferes: terminal sampling tracks the exact
        # distribution by construction, and the pilot wave must too —
        # its walk crosses the stage where the points merge. This also
        # guards the per-edge contribution data the pilot coupling is
        # fitted from.
        from quantish.montecarlo import (
            predicted_distribution,
            sample_pilot,
            sample_terminal,
        )
        sim = run_sim('gr2026/fig4.12')
        predicted = predicted_distribution(sim.result_space)
        terminal = sample_terminal(sim.result_space, N_TRIALS, random.Random(SEED))
        self.assertLessEqual(tvd(terminal, predicted, N_TRIALS), NOISE_TOLERANCE)
        pilot = sample_pilot(sim.initial_points, N_TRIALS, random.Random(SEED))
        self.assertLessEqual(tvd(pilot, predicted, N_TRIALS), NOISE_TOLERANCE)


if __name__ == '__main__':
    unittest.main()

class TestPilotWave(unittest.TestCase):
    """The pilot-wave sampler (one wave-guided trajectory per trial)
    reproduces the exact distribution on interfering circuits and never
    dead-ends. Numbers from the 2026-09-08 handoff, reproduced here at
    seed 7."""
    @classmethod
    def setUpClass(cls):
        logging.getLogger('quantish').setLevel(logging.WARNING)
        CalcMode.default('Float')

    @staticmethod
    def run_with(name, **variables):
        from quantish.simulation import Simulation
        with open(MODELS_DIR / 'defaults.yaml') as f:
            config = yaml.safe_load(f)
        with open(MODELS_DIR / f'{name}.yaml') as f:
            config.update(yaml.safe_load(f))
        config['loglevel'] = 'warning'
        config['variables'].update(variables)
        sim = Simulation(Addict(config))
        sim.run()
        return sim

    def test_pilot_matches_exact_distribution(self):
        from quantish.montecarlo import predicted_distribution, sample_pilot
        for name, variables in (('gr2026/fig4.13', {}),
                                ('decoherence/double_slit_eraser', {'phi': '90°'}),
                                ('decoherence/double_slit_tunable',
                                 {'theta_pre': '45°', 'phi': '60°'}),
                                ('gr2026/fig4.17', {})):
            sim = self.run_with(name, **variables)
            predicted = predicted_distribution(sim.result_space)
            tally = sample_pilot(sim.initial_points, N_TRIALS, random.Random(7))
            # never dead-ends: every trial lands on a final point
            self.assertEqual(sum(tally.values()), N_TRIALS, name)
            self.assertLessEqual(tvd(tally, predicted, N_TRIALS),
                                 NOISE_TOLERANCE, name)

    def test_bell_cells_pilot_follows_the_law(self):
        # discrepancy rate per cell of the fig 4.17 sweep: the pilot wave
        # follows the sin² law (0.146 in the two oblique cells)
        from quantish.epr import run_pair
        sim = self.run_with('gr2026/fig4.17')
        for t1, t2, expected in (('pi/4', 'pi/8', 0.146),
                                 ('pi/8', '3*pi/8', 0.500),
                                 ('pi/4', '3*pi/8', 0.146)):
            pilot = run_pair(sim, t1, t2, N_TRIALS, random.Random(11), 'pilot')
            self.assertAlmostEqual(float(pilot['exact']), expected, places=2)
            self.assertLess(abs(pilot['sampled'] - expected), 0.03, (t1, t2))

    def test_hidden_variable_model_sits_at_the_classical_bound(self):
        # Bell's local hidden-variable example: each cell's sampled rate
        # follows the linear law 2|θ1−θ2|/π (the 'classical' grid), the
        # full sweep saturates Bell's inequality (excess ≈ 0, never
        # positive beyond noise) and respects CHSH (|S| ≤ 2)
        import math

        from quantish.epr import run_epr_experiment, run_pair
        sim = self.run_with('gr2026/fig4.17')
        for t1, t2 in (('pi/4', 'pi/8'), ('pi/8', '3*pi/8'),
                       ('pi/4', '3*pi/8'), ('pi/8', 'pi/8')):
            cell = run_pair(sim, t1, t2, N_TRIALS, random.Random(11), 'hidden')
            self.assertLess(abs(cell['sampled'] - float(cell['classical'])),
                            0.02, (t1, t2))
            self.assertEqual(sum(cell['counts'].values()), N_TRIALS)
        # outside the chapter's sweep range the linear law must fold
        # like the sampler does: period π, symmetric about π/2
        for t1, t2, classical in (('2*pi/3', '0', 2 / 3), ('3*pi/4', '0', 0.5),
                                  ('pi', '0', 0.0), ('7*pi/6', 'pi/6', 0.0),
                                  ('0', '5*pi/8', 0.75)):
            cell = run_pair(sim, t1, t2, N_TRIALS, random.Random(5), 'hidden')
            self.assertAlmostEqual(float(cell['classical']), classical, places=9)
            self.assertLess(abs(cell['sampled'] - classical), 0.02, (t1, t2))
        res = run_epr_experiment(sim, n_trials=N_TRIALS, seed=11, mode='hidden')
        sigma = 0.5 / math.sqrt(N_TRIALS)
        self.assertLess(res['bell'][0], 3 * math.sqrt(3) * sigma)
        self.assertGreater(res['bell'][0], -0.05)      # saturated, not slack
        self.assertLess(res['chsh'][0], 2 + 12 * sigma)
        # the classical law itself saturates both bounds exactly
        self.assertAlmostEqual(res['bell_classical'][0], 0.0, places=12)
        self.assertAlmostEqual(res['chsh_classical'][0], 2.0, places=12)
        # the exact wave crosses the bound the hidden variables sit at
        self.assertGreater(res['bell_exact'][0], 0.1)
        self.assertGreater(res['chsh_exact'][0], 2.3)
