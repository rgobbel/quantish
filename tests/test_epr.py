"""Exact checks of the EPR outcome conventions (multiworld.epr) against the
sin²-law from quantish_gld/epr_bell.py:

    one-stage (g5/g6):        discrepancy = sin²(Q5 + Q6), outcome = position⊕sign
    two-stage (adds g7/g8):   discrepancy = sin²((Q5+Q6) − (Q7+Q8)), outcome = position

Computed from the exact final worlds — no sampling involved.
"""
import logging
import unittest
from pathlib import Path

import yaml
from addict import Addict

REPO_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_DIR / 'models'

import multiworld.qnumber as qn
from multiworld.qnumber import CalcMode


def run_sim(name):
    from multiworld.simulation import Simulation
    with open(MODELS_DIR / 'defaults.yaml') as f:
        config = yaml.safe_load(f)
    with open((MODELS_DIR / name).with_suffix('.yaml')) as f:
        config.update(yaml.safe_load(f))
    config['loglevel'] = 'warning'
    sim = Simulation(Addict(config))
    sim.run()
    return sim


def exact_discrepancy(sim, two_stage):
    from multiworld.epr import classify
    probs = {'same': 0.0, 'diff': 0.0, 'uncoupled': 0.0}
    for point in sim.result_space.index.values():
        probs[classify(point, two_stage)] += float(point.probability)
    coupled = probs['same'] + probs['diff']
    return probs['diff'] / coupled


class TestEPRConventions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger('multiworld').setLevel(logging.WARNING)
        CalcMode.default('Float')
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()

    def test_one_stage_parity_outcome(self):
        # fig416plus: g5 = g6 = rad(15), so sin²(Q5+Q6) = sin²(30°) = 1/4.
        from multiworld.epr import expected_discrepancy, is_two_stage
        sim = run_sim('fig416plus_multi')
        self.assertFalse(is_two_stage(sim))
        predicted = float(expected_discrepancy(sim))
        self.assertAlmostEqual(predicted, 0.25, places=9)
        self.assertAlmostEqual(exact_discrepancy(sim, False), predicted, places=9)

    def test_two_stage_position_outcome(self):
        # fig417: Q5+Q6 = Q7+Q8 = pi/4, so the discrepancy is exactly 0 —
        # perfect correlation, read as plain position.
        from multiworld.epr import expected_discrepancy, is_two_stage
        sim = run_sim('fig417')
        self.assertTrue(is_two_stage(sim))
        predicted = float(expected_discrepancy(sim))
        self.assertAlmostEqual(predicted, 0.0, places=9)
        self.assertAlmostEqual(exact_discrepancy(sim, True), 0.0, places=9)


if __name__ == '__main__':
    unittest.main()