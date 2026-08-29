"""Load-time wiring validation and bare-name delay links."""
import unittest

from addict import Addict

import quantish.qnumber as qn
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation


def make_config(**overrides):
    cfg = {
        'title': 'wiring test',
        'run_stages': {'first': ['g1'], 'second': ['d1', 'g2']},
        'particles': {'p1': {'sign': 1, 'weight': 1}},
        'gates': {'g1': {'angle': 0}, 'g2': {'angle': 0}},
        'delay_gates': ['d1'],
        'links': {'p1': 'g1.upper',
                  'g1.upper': 'g2.upper',
                  'g1.control': 'd1'},
        'loglevel': 'error',
    }
    cfg.update(overrides)
    return Addict(cfg)


class TestWiring(unittest.TestCase):
    def setUp(self):
        CalcMode.default('Float')

    def test_valid_model_loads(self):
        sim = Simulation(make_config())
        self.assertIn('d1', sim.delay_gates)

    def test_bare_delay_links_imply_control(self):
        sim = Simulation(make_config())
        self.assertEqual(sim.links['g1.control'], 'd1.control')
        self.assertEqual(sim.delay_gates['d1'].source, 'g1.control')

    def test_bare_phase_plate_links_imply_control(self):
        cfg = make_config(
            run_stages={'first': ['g1'], 'second': ['d1', 'g2'],
                        'third': ['pp']},
            phase_plates={'pp': 0})
        cfg.links['g2.upper'] = 'pp'
        sim = Simulation(cfg)
        self.assertEqual(sim.links['g2.upper'], 'pp.control')
        self.assertIn('pp', sim.phase_plates)

    def test_phase_plate_on_switch_wire_raises(self):
        cfg = make_config(
            run_stages={'first': ['g1'], 'second': ['d1', 'g2'],
                        'third': ['pp']},
            phase_plates={'pp': 0})
        cfg.links['g2.upper'] = 'pp.upper'
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn('control wire', str(ctx.exception))

    def test_phase_plate_also_declared_as_gate_raises(self):
        cfg = make_config(phase_plates={'g2': 0})
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn('both gates and phase_plates', str(ctx.exception))

    def test_wire_labels_load_with_delay_sugar(self):
        cfg = make_config(wire_labels={'p1': 'w2', 'g1.upper': 'w2a',
                                       'g1.control': 'w1a'})
        sim = Simulation(cfg)
        self.assertEqual(sim.wire_labels['p1'], 'w2')
        # bare delay names canonicalize the same way links do — but
        # 'g1.control' is already canonical here
        self.assertEqual(sim.wire_labels['g1.control'], 'w1a')

    def test_wire_label_on_unknown_source_raises(self):
        cfg = make_config(wire_labels={'g9.upper': 'w1'})
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn('g9.upper', str(ctx.exception))

    def test_stub_labels_null_input_and_output(self):
        # '>' = an empty input; an unlinked output port = a stub to sink
        cfg = make_config(wire_labels={'>g1.lower': 'w3',
                                       'g2.upper': 'w2b'})
        sim = Simulation(cfg)
        self.assertEqual(sim.wire_labels['>g1.lower'], 'w3')
        self.assertEqual(sim.wire_labels['g2.upper'], 'w2b')

    def test_null_input_label_on_fed_port_raises(self):
        # g1.upper is fed by p1: the label belongs on the source
        cfg = make_config(wire_labels={'>g1.upper': 'w2'})
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn("label its source", str(ctx.exception))

    def test_unlinked_particle_raises(self):
        cfg = make_config()
        cfg.particles.p9.sign = 1
        cfg.particles.p9.weight = 1
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn("particle 'p9' is not linked", str(ctx.exception))

    def test_gate_without_inputs_raises(self):
        cfg = make_config()
        cfg.gates.g9.angle = 0
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn("gate 'g9' has no inputs", str(ctx.exception))

    def test_link_to_undeclared_gate_raises(self):
        cfg = make_config()
        cfg.links['g2.upper'] = 'g9.upper'
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn("targets undeclared gate 'g9'", str(ctx.exception))

    def test_gate_omitted_from_run_stages_raises(self):
        cfg = make_config()
        cfg.run_stages = {'first': ['g1'], 'second': ['g2']}   # forgets d1
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn("run_stages omits linked gates ['d1']", str(ctx.exception))


    def test_branching_particle_starts_in_superposition(self):
        cfg = make_config(
            run_stages={'first': ['g1', 'g2'], 'second': ['d1']},
            links={'p1': ['g1.upper', 'g2.upper', 0.25],
                   'g1.control': 'd1'})
        sim = Simulation(cfg)
        self.assertEqual(len(sim.initial_points), 2)
        probs = sorted(round(float(p.probability), 6)
                       for p in sim.initial_points)
        self.assertEqual(probs, [0.25, 0.75])
        # the arms are labeled with their probabilities
        self.assertEqual(sim.wire_labels['p1'], '0.25')
        self.assertEqual(sim.wire_labels['p1|2'], '0.75')

    def test_branching_link_shape_is_checked(self):
        for bad in (['g1.upper', 'g2.upper', 'g1.control'],
                    ['g1.upper'], ['g1.upper', 'g2.upper', 0.25, 0.5]):
            cfg = make_config(links={'p1': bad, 'g1.control': 'd1'})
            with self.assertRaises(ValueError):
                Simulation(cfg)
        # only particles branch
        cfg = make_config(links={'p1': 'g1.upper',
                                 'g1.upper': ['g2.upper', 'g2.lower'],
                                 'g1.control': 'd1'})
        with self.assertRaises(ValueError):
            Simulation(cfg)
        # the probability stays in 0..1
        cfg = make_config(links={'p1': ['g1.upper', 'g2.upper', 1.5],
                                 'g1.control': 'd1'})
        with self.assertRaises(ValueError) as ctx:
            Simulation(cfg)
        self.assertIn('outside 0..1', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
