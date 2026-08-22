"""Exact checks of the EPR outcome conventions (quantish.epr) against the
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

import quantish.qnumber as qn
from quantish.qnumber import CalcMode


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


def exact_discrepancy(sim, two_stage):
    from quantish.epr import classify
    probs = {'same': 0.0, 'diff': 0.0, 'uncoupled': 0.0}
    for point in sim.result_space.index.values():
        probs[classify(point, two_stage)] += float(point.probability)
    coupled = probs['same'] + probs['diff']
    return probs['diff'] / coupled


class TestEPRConventions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger('quantish').setLevel(logging.WARNING)
        CalcMode.default('Float')
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()

    def test_one_stage_parity_outcome(self):
        # The coupling-stage-only EPR circuit is a 2006-edition figure (the
        # 2026 draft folds it into fig 4.17's discussion), so it lives in
        # gr2006. Its g5/g6 angles are working values Randy edits freely, so
        # assert consistency rather than a fixed number: the exact
        # discrepancy from the final worlds must match sin²(Q5+Q6) with the
        # parity (position⊕sign) outcome, for whatever the YAML says.
        from quantish.epr import expected_discrepancy, is_two_stage
        sim = run_sim('gr2006/fig4.16')
        self.assertFalse(is_two_stage(sim))
        predicted = float(expected_discrepancy(sim))
        self.assertAlmostEqual(exact_discrepancy(sim, False), predicted, places=9)

    def test_epr_with_qnumber_angles_in_config(self):
        # Regression: run_pair deep-copies sim.config, and qnumber Reals
        # stored as gate angles (as the marimo app does, especially with
        # symbolic expressions) used to break deepcopy — Real.__new__
        # requires its value argument, so Complex.__getnewargs__ must
        # supply it.
        from copy import deepcopy

        from quantish.epr import run_pair
        for _mode in ('Float', 'Symbolic'):
            CalcMode.default(_mode)
            qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
            val = qn.qify('pi/8')
            self.assertEqual(complex(deepcopy(val)), complex(val))
        CalcMode.default('Float')
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
        sim = run_sim('gr2026/fig4.17')
        # g5's declared angle is Q5 = 0; storing the same value as a qnumber
        # Real exercises the deepcopy path without perturbing the circuit
        # (g7/g8 are owned by run_pair's theta1/theta2 rebinding).
        sim.config.gates['g5'].angle = qn.qify('0')
        cell = run_pair(sim, qn.qify('0'), qn.qify('pi/8'))
        self.assertAlmostEqual(cell['exact'], cell['analytical'], places=9)

    def test_bell_chsh_sweep(self):
        # Exact 3x3 sweep on fig417: every cell must match sin²(θ1−θ2),
        # Bell's three-angle inequality is violated by 1/2 − 2·sin²(π/8),
        # and CHSH reaches 1 + √2 on the canonical set {0, π/8, π/4}.
        import math
        from quantish.epr import run_epr_experiment
        sim = run_sim('gr2026/fig4.17')
        results = run_epr_experiment(sim, n_trials=0)
        for cell in results['grid'].values():
            self.assertAlmostEqual(cell['exact'], cell['analytical'], places=9)
        bell_excess, _ = results['bell_exact']
        self.assertAlmostEqual(bell_excess, 0.5 - 2 * math.sin(math.pi / 8) ** 2,
                               places=9)
        chsh_s, _ = results['chsh_exact']
        self.assertAlmostEqual(chsh_s, 1 + math.sqrt(2), places=9)

    def test_two_stage_position_outcome(self):
        # fig417's g5..g8 angles are placeholders for the sweep, so assert
        # consistency rather than a fixed value: the exact discrepancy from
        # the final worlds must match sin²((Q5+Q6)−(Q7+Q8)) for whatever
        # the YAML currently says, with the plain-position outcome.
        from quantish.epr import expected_discrepancy, is_two_stage
        sim = run_sim('gr2026/fig4.17')
        self.assertTrue(is_two_stage(sim))
        predicted = float(expected_discrepancy(sim))
        self.assertAlmostEqual(exact_discrepancy(sim, True), predicted, places=9)


if __name__ == '__main__':
    unittest.main()