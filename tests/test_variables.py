"""Model variables usable by name in YAML expressions (eager substitution)."""
import unittest

from addict import Addict

import quantish.qnumber as qn
from quantish.qnumber import CalcMode, qify, reserved_name
from quantish.simulation import Simulation


def make_config(**overrides):
    cfg = {
        'title': 'variables test',
        'variables': {'qx': 'pi/8', 'qy': 'pi/8', 'qz': '(qx + qy) - pi/8'},
        'run_stages': {'only': ['g1']},
        'particles': {'p1': {'sign': 1, 'weight': 1}},
        'gates': {'g1': {'angle': 'qz'}},
        'links': {'p1': 'g1.upper'},
        'loglevel': 'error',
    }
    cfg.update(overrides)
    return Addict(cfg)


class TestVariables(unittest.TestCase):
    def setUp(self):
        CalcMode.default('Float')

    def test_variable_references_earlier_variable(self):
        sim = Simulation(make_config())
        self.assertAlmostEqual(float(sim.gates['g1'].theta), 3.14159265 / 8, places=6)

    def test_expression_in_gate_angle(self):
        cfg = make_config()
        cfg.gates.g1.angle = 'qx + qy'
        sim = Simulation(cfg)
        self.assertAlmostEqual(float(sim.gates['g1'].theta), 3.14159265 / 4, places=6)

    def test_unknown_name_raises_with_variable_list(self):
        cfg = make_config()
        cfg.gates.g1.angle = 'qx + bogus'
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn('bogus', str(ctx.exception))
        self.assertIn('qx', str(ctx.exception))

    def test_forward_reference_raises(self):
        cfg = make_config()
        cfg.variables = {'early': 'late + 1', 'late': '2'}
        with self.assertRaises(ValueError):
            Simulation(cfg)

    def test_shadowing_builtin_raises(self):
        cfg = make_config()
        cfg.variables = {'pi': '3'}
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn('shadows', str(ctx.exception))

    def test_phase_accepts_the_same_expression_forms_as_angle(self):
        # degrees via rad(), and model variables, just like gate angles
        cfg = make_config()
        cfg.gates.g1.phase = 'rad(60)'
        sim = Simulation(cfg)
        self.assertAlmostEqual(float(sim.gates['g1'].phase),
                               3.14159265 / 3, places=6)
        cfg = make_config()
        cfg.gates.g1.phase = 'qx + qy'
        sim = Simulation(cfg)
        self.assertAlmostEqual(float(sim.gates['g1'].phase),
                               3.14159265 / 4, places=6)

    def test_caption_is_optional_and_normalized(self):
        sim = Simulation(make_config())
        self.assertEqual(sim.caption, '')
        cfg = make_config(caption='A caption\n  spanning folded  lines.')
        sim = Simulation(cfg)
        self.assertEqual(sim.caption, 'A caption spanning folded lines.')

    def test_qify_still_parses_plain_expressions(self):
        self.assertAlmostEqual(float(qify('pi/4')), 0.785398, places=5)
        self.assertAlmostEqual(complex(qify('1+0j')).real, 1.0)

    def test_reserved_names(self):
        for name in ('pi', 'I', 'E', 'rad', 'acos'):
            self.assertTrue(reserved_name(name), name)
        for name in ('q45', 'zero', 'theta2'):
            self.assertFalse(reserved_name(name), name)


if __name__ == '__main__':
    unittest.main()


class TestThetaRebinding(unittest.TestCase):
    """run_pair rebinds theta1/theta2 variables when the model declares
    them, instead of overwriting gate angle expressions."""

    def setUp(self):
        CalcMode.default('Float')

    def fig417_theta_convention(self):
        import yaml
        from pathlib import Path
        models = Path(__file__).resolve().parents[1] / 'models'
        with open(models / 'defaults.yaml') as f:
            cfg = yaml.safe_load(f)
        with open(models / 'gr2026' / 'fig4.17.yaml') as f:
            cfg.update(yaml.safe_load(f))
        cfg['loglevel'] = 'error'
        cfg['calculation_mode'] = 'float'
        cfg = Addict(cfg)
        cfg.variables.theta1 = '0'
        cfg.variables.theta2 = '0'
        cfg.gates.g7.angle = 'theta1'
        cfg.gates.g8.angle = '(Q5 + Q6) - theta2'
        return cfg

    def test_sweep_rebinds_variables_and_matches_law(self):
        from quantish.epr import run_epr_experiment
        sim = Simulation(self.fig417_theta_convention())
        sim.run()
        results = run_epr_experiment(sim, n_trials=0)
        for (l1, l2), cell in results['grid'].items():
            self.assertAlmostEqual(cell['exact'], cell['analytical'],
                                   places=9, msg=f'cell ({l1},{l2})')


if __name__ == '__main__':
    unittest.main()
