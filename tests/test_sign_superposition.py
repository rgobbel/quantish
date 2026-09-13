"""A particle may start in a superposition of its two signs on one wire
(a 'plus; minus' weight), or carry one complex amplitude per
(destination, sign) on its links — the shape of a gate's output, so a
split's outputs can be fed back in. The squared magnitudes of a
particle's amplitudes must sum to 1, checked at load."""
import unittest

from addict import Dict as Addict

import quantish.qnumber as qn
from quantish.builder import config_to_graph, graph_to_config, validate_graph
from quantish.particle import sign_components
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation
from quantish.util import Sign


def make_config(**overrides):
    cfg = {
        'title': 'sign superposition test',
        'run_stages': {'first': ['g1']},
        'particles': {'p1': {'weight': 'sqrt(3)/2; 1/2'}},
        'gates': {'g1': {'angle': 'pi/6'}},
        'links': {'p1': 'g1.upper'},
        'loglevel': 'error',
    }
    cfg.update(overrides)
    return Addict(cfg)


ARMS = {'g1.upper': '3/4; 1/2i', 'g1.lower': '; -sqrt(3)/4'}


def total(sim):
    return qn.to_float(sum(p.probability for p in sim.result_space.index.values()))


class TestSignComponents(unittest.TestCase):
    def setUp(self):
        CalcMode.default('Float')

    def test_plain_spec_takes_the_declared_sign(self):
        comps = sign_components('1/2', Sign.minus)
        self.assertEqual(set(comps), {Sign.minus})
        self.assertAlmostEqual(complex(comps[Sign.minus]), 0.5)

    def test_two_sign_spec(self):
        comps = sign_components('3/16; -1/16i')
        self.assertAlmostEqual(complex(comps[Sign.plus]), 3 / 16)
        self.assertAlmostEqual(complex(comps[Sign.minus]), -1j / 16)

    def test_empty_half_is_zero(self):
        comps = sign_components('; 1')
        self.assertTrue(qn.zerop(comps[Sign.plus]))
        self.assertAlmostEqual(complex(comps[Sign.minus]), 1)

    def test_minus_sign_with_two_sign_weight_raises(self):
        with self.assertRaises(ValueError):
            sign_components('1/2; 1/2', Sign.minus)

    def test_three_components_raise(self):
        with self.assertRaises(ValueError):
            sign_components('1; 2; 3')


class TestSuperposedParticle(unittest.TestCase):
    def setUp(self):
        CalcMode.default('Float')

    def test_two_initial_points_one_per_sign(self):
        sim = Simulation(make_config())
        self.assertEqual(len(sim.initial_points), 2)
        signs = {pt.coords['p1'].sign: complex(pt.weight)
                 for pt in sim.initial_points}
        self.assertAlmostEqual(signs[Sign.plus], 3 ** 0.5 / 2)
        self.assertAlmostEqual(signs[Sign.minus], 0.5)
        p1 = sim.particles['p1']
        self.assertTrue(p1.superposed)
        self.assertEqual(repr(p1), '±p1')

    def test_runs_and_keeps_total_probability(self):
        sim = Simulation(make_config())
        sim.run()
        self.assertAlmostEqual(total(sim), 1, places=9)

    def test_norm_is_checked_at_load(self):
        with self.assertRaises(ValueError) as ctx:
            Simulation(make_config(particles={'p1': {'weight': '1/2; 1/2'}}))
        self.assertIn('sum to 0.5', str(ctx.exception))

    def test_plain_particle_norm_is_checked_too(self):
        with self.assertRaises(ValueError):
            Simulation(make_config(particles={'p1': {'sign': 1, 'weight': 2}}))

    def test_declared_minus_sign_contradicts(self):
        with self.assertRaises(ValueError) as ctx:
            Simulation(make_config(particles={'p1': {'sign': -1,
                                                     'weight': '1/2; 1/2'}}))
        self.assertIn("p1", str(ctx.exception))

    def test_absent_overrides_a_two_sign_weight(self):
        sim = Simulation(make_config(), absent=('p1',))
        self.assertTrue(sim.particles['p1'].absent)
        self.assertEqual(len(sim.initial_points), 1)
        self.assertNotIn('p1', sim.initial_points[0].coords)

    def test_symbolic_mode(self):
        CalcMode.default('Symbolic')
        sim = Simulation(make_config(calculation_mode='symbolic'))
        sim.run()
        self.assertAlmostEqual(total(sim), 1, places=9)


class TestWeightedLinks(unittest.TestCase):
    def setUp(self):
        CalcMode.default('Float')

    def test_one_start_per_destination_and_sign(self):
        sim = Simulation(make_config(particles={'p1': {}},
                                     links={'p1': ARMS}))
        self.assertEqual(len(sim.initial_points), 3)
        got = {(str(pt.coords['p1'].position.endpoint), pt.coords['p1'].sign):
               complex(pt.weight) for pt in sim.initial_points}
        self.assertAlmostEqual(got[('g1.upper', Sign.plus)], 0.75)
        self.assertAlmostEqual(got[('g1.upper', Sign.minus)], 0.5j)
        self.assertAlmostEqual(got[('g1.lower', Sign.minus)], -3 ** 0.5 / 4)
        # the arms are labeled with their specs
        self.assertEqual(sim.wire_labels['p1'], '3/4; 1/2i')
        self.assertEqual(sim.wire_labels['p1|2'], '; -sqrt(3)/4')
        sim.run()
        self.assertAlmostEqual(total(sim), 1, places=9)

    def test_plain_weight_factor_multiplies(self):
        sim = Simulation(make_config(
            particles={'p1': {'weight': '1/2'}},
            links={'p1': {'g1.upper': '1; 1', 'g1.lower': '1; 1'}}))
        self.assertEqual(len(sim.initial_points), 4)
        for pt in sim.initial_points:
            self.assertAlmostEqual(complex(pt.weight), 0.5)

    def test_declared_sign_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            Simulation(make_config(particles={'p1': {'sign': 1}},
                                   links={'p1': ARMS}))
        self.assertIn('per destination', str(ctx.exception))

    def test_norm_is_checked(self):
        with self.assertRaises(ValueError):
            Simulation(make_config(particles={'p1': {}},
                                   links={'p1': {'g1.upper': '1; 1'}}))

    def test_three_arms_raise(self):
        with self.assertRaises(ValueError):
            Simulation(make_config(
                particles={'p1': {}}, gates={'g1': {'angle': 0}},
                links={'p1': {'g1.upper': '1', 'g1.lower': '',
                              'g1.control': ''}}))


class TestBuilderRoundTrip(unittest.TestCase):
    def setUp(self):
        CalcMode.default('Float')

    def test_two_sign_weight_survives(self):
        cfg = dict(make_config())
        graph, _ = config_to_graph(cfg)
        self.assertEqual(graph['particles']['p1']['weight'], 'sqrt(3)/2; 1/2')
        self.assertEqual(validate_graph(graph), [])
        back = graph_to_config(graph, "t")
        self.assertEqual(back['particles']['p1'], {'weight': 'sqrt(3)/2; 1/2'})
        Simulation(Addict({**back, 'loglevel': 'error'}))

    def test_weighted_links_survive(self):
        arms = ARMS
        cfg = dict(make_config(particles={'p1': {}}, links={'p1': arms}))
        graph, _ = config_to_graph(cfg)
        self.assertEqual(graph['arm_weights'], {'p1': arms})
        self.assertEqual(validate_graph(graph), [])
        back = graph_to_config(graph, "t")
        self.assertEqual(back['links']['p1'], arms)
        self.assertEqual(back['particles']['p1'], {})
        Simulation(Addict({**back, 'loglevel': 'error'}))

    def test_bad_arm_weight_is_a_problem(self):
        graph, _ = config_to_graph(dict(make_config(
            particles={'p1': {}}, links={'p1': {'g1.upper': '; 1'}})))
        graph['arm_weights']['p1']['g1.upper'] = 'bogus; 1'
        self.assertTrue(any('p1' in pr for pr in validate_graph(graph)))
