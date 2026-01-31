import logging
import random
import unittest
from collections import defaultdict
from pathlib import Path
from typing import Callable

import numpy as np
import sympy as sym
# import cmath as cm
# import math as m
from quantish.qnumber import CalcMode, qify, I, PI, Modes, to_native, Complex
from quantish.particle import Particle, random_particle
from quantish.simulation import Simulation
import quantish.qnumber as qn
from quantish.gate import FredkinGate
import yaml

class TestCPair(unittest.TestCase):
    @staticmethod
    def setup():
        one = qify("1")
        m_one = -one
        angle = qify('rad(30)')
        twist = angle - PI()/qify("2")
        g = FredkinGate('g', angle)
        canon_c2ap = qify("3/4")
        canon_c2bp = qify("(1/4) * sqrt(3) * I ")
        canon_c3ap = qify("1/4")
        canon_c3bp = qify(-canon_c2bp)
        canon_quadp = (canon_c2ap, canon_c2bp, canon_c3ap, canon_c3bp)
        canon_c2am = qify("-3/4")
        canon_c2bm = qify("(1/4) * sqrt(3) * -I")
        canon_c3am = qify("-1/4")
        canon_c3bm = qify("(1/4) * sqrt(3) * I ")
        canon_quadm = (canon_c2am, canon_c2bm, canon_c3am, canon_c3bm)
        canon_c2ap_t = qify("1/4")
        canon_c2bp_t = qify("-sqrt(3) * I / 4")
        canon_c3ap_t = qify("3 / 4")
        canon_c3bp_t = qify("sqrt(3) * I / 4")
        canon_quadp_t = (canon_c2ap_t, canon_c2bp_t, canon_c3ap_t, canon_c3bp_t)
        canon_c2am_t = qify("-1 / 4")
        canon_c2bm_t = qify("sqrt(3) * I / 4")
        canon_c3am_t = qify("-3 / 4")
        canon_c3bm_t = qify("-sqrt(3) * I / 4")
        canon_quadm_t = (canon_c2am_t, canon_c2bm_t, canon_c3am_t, canon_c3bm_t)
        return one, m_one, angle, twist, g, canon_quadp, canon_quadm, canon_quadp_t, canon_quadm_t

    @staticmethod
    def check_quads(calc, canon, twist):
        for i in range(4):
            calc_i = to_native(calc[i])
            canon_i = to_native(canon[i])
            if not np.isclose(calc_i, canon_i):
                print(f'{i=}, {calc[i]=}, {canon[i]=}')
                return False
        return True

    #@unittest.skip
    def test_cpair_methods(self):
        print('test_cpair_methods:\n')
        methods = ('cpair', 'cpairx')
        # methods = ('cpair', 'cpair_alt', 'cpair0', 'cpair1', 'cpair2', 'cpair3')
        for mode in Modes:
            CalcMode.mode = mode
            one, m_one, angle, twist, g, canon_quadp, canon_quadm, canon_quadp_t, canon_quadm_t = self.setup()
            self.assertAlmostEqual(sum(canon_quadp), 1)
            self.assertAlmostEqual(sum(canon_quadm), -1)
            self.assertAlmostEqual(sum(canon_quadp_t), 1)
            self.assertAlmostEqual(sum(canon_quadm_t), -1)
            with self.subTest(mode=mode):
                for method_str in methods:
                    with self.subTest(method=method_str):
                        method: Callable = getattr(g, method_str)
            method: Callable = getattr(g, method_str)
            for twist in (False, True):
                for sign in (1, -1):
                    with self.subTest(sign=sign):
                        if sign > 0:
                            ss = '+'
                            value = one
                            canon = canon_quadp_t if twist else canon_quadp
                        else:
                            ss = '-'
                            value = m_one
                            canon = canon_quadm_t if twist else canon_quadm
                        # if method_str in ('cpair0', 'cpair_alt'):
                        #     result = method(value, angle)
                        # else:
                        #     result = method(value) # angle is built into the gate
                        result = g.cpair(value, twist=twist)  # angle is built into the gate
                        print(f'cpair{ss} ({mode}) = {result}')
                        self.assertTrue(self.check_quads(result, canon, twist), f'cpair{ss} ({mode}) failed')
                        print()

    # @unittest.skip
    # def test_cpair(self):
    #     for mode in Modes:
    #         CalcMode.mode = mode
    #         one, m_one, angle, twist, g, canon_quadp, canon_quadm = self.setup()
    #         for ss, v, canon in zip(('+', '-'), (one, m_one), (canon_quadp, canon_quadm)):
    #             result = g.cpair(v, angle)
    #             print(f'cpair{ss} ({mode}) = {result}')
    #             self.assertTrue(self.check_quads(result, canon), f'cpair{ss} ({mode}) failed')
    #     print()

    # @unittest.skip
    # def test_cpairx(self):
    #     for mode in Modes:
    #         CalcMode.mode = mode
    #         one, m_one, angle, twist, g, canon_quadp, canon_quadm = self.setup()
    #         for ss, v, canon in zip(('+', '-'), (one, m_one), (canon_quadp, canon_quadm)):
    #             result = g.cpairx(v, angle)
    #             print(f'cpair_alt{ss} ({mode}) = {result}')
    #             self.assertTrue(self.check_quads(result, canon), f'cpair_alt{ss} ({mode}) failed')
    #     print()

    # @unittest.skip
    # def test_cpair_alt(self):
    #     for mode in Modes:
    #         CalcMode.mode = mode
    #         one, m_one, angle, twist, g, canon_quadp, canon_quadm = self.setup()
    #         for ss, v, canon in zip(('+', '-'), (one, m_one), (canon_quadp, canon_quadm)):
    #             result = g.cpair_alt(v, angle)
    #             print(f'cpair_alt{ss} ({mode}) = {result}')
    #             self.assertTrue(self.check_quads(result, canon), f'cpair_alt{ss} ({mode}) failed')
    #     print()
    #
    # @unittest.skip
    # def test_cpair0(self):
    #     for mode in Modes:
    #         CalcMode.mode = mode
    #         one, m_one, angle, twist, g, canon_quadp, canon_quadm = self.setup()
    #         for ss, v, canon in zip(('+', '-'), (one, m_one), (canon_quadp, canon_quadm)):
    #             result = g.cpair0(v)
    #             print(f'cpair0{ss} ({mode}) = {result}')
    #             self.assertTrue(self.check_quads(result, canon), f'cpair0{ss} ({mode}) failed')
    #     print()
    #
    # @unittest.skip
    # def test_cpair1(self):
    #     for mode in Modes:
    #         CalcMode.mode = mode
    #         one, m_one, angle, twist, g, canon_quadp, canon_quadm = self.setup()
    #         for ss, v, canon in zip(('+', '-'), (one, m_one), (canon_quadp, canon_quadm)):
    #             result = g.cpair1(v)
    #             print(f'cpair1{ss} ({mode}) = {result}')
    #             self.assertTrue(self.check_quads(result, canon), f'cpair1{ss} ({mode}) failed')
    #     print()
    #
    # @unittest.skip
    # def test_cpair2(self):
    #     for mode in Modes:
    #         CalcMode.mode = mode
    #         one, m_one, angle, twist, g, canon_quadp, canon_quadm = self.setup()
    #         for ss, v, canon in zip(('+', '-'), (one, m_one), (canon_quadp, canon_quadm)):
    #             result = g.cpair2(v)
    #             print(f'cpair2{ss} ({mode}) = {result}')
    #             self.assertTrue(self.check_quads(result, canon), f'cpair2{ss} ({mode}) failed')
    #     print()
    #
    # @unittest.skip
    # def test_cpair3(self):
    #     for mode in Modes:
    #         CalcMode.mode = mode
    #         one, m_one, angle, twist, g, canon_quadp, canon_quadm = self.setup()
    #         for ss, v, canon in zip(('+', '-'), (one, m_one), (canon_quadp, canon_quadm)):
    #             result = g.cpair3(v)
    #             print(f'cpair3{ss} ({mode}) = {result}')
    #             self.assertTrue(self.check_quads(result, canon), 'cpair3 failed (plus)')
    #     print()

class TestMeasure(unittest.TestCase):

    @unittest.skip
    def test_g0(self):
        for mode in Modes:
            CalcMode.mode = mode
            g0 = FredkinGate('g0', 0)
            one = Complex('1')
            p_plus = Particle('p_plus', one, 1)
            result_plus  = g0.measure(p_plus)
            print(f'gate={g0}, particle={p_plus}, result={result_plus}')
            self.assertTrue(result_plus[0] == p_plus.weight)
            self.assertTrue(result_plus[1] == 0)
            self.assertTrue(result_plus[2] == 0)
            self.assertTrue(result_plus[3] == 0)
            p_minus = Particle('p_minus', one, -1)
            result_minus = g0.measure(p_minus)
            print(f'gate={g0}, particle={p_minus}, result={result_minus}')
            self.assertAlmostEqual(result_minus[0], 0)
            self.assertAlmostEqual(result_minus[1], 0)
            self.assertEqual(result_minus[2], p_minus.weight)
            self.assertAlmostEqual(result_minus[3], 0)

    @unittest.skip
    def test_g30(self):
        for mode in Modes:
            CalcMode.mode = mode
            one = Complex('1')
            g30 = FredkinGate('g30', qify('rad(30)'))
            p_plus = Particle('p_plus', one, 1)
            result_plus  = g30.measure(p_plus)
            print(f'gate={g30}, particle={p_plus}, result={result_plus}')
            self.assertAlmostEqual(sum(result_plus)**2, p_plus.probability)
            self.assertAlmostEqual(result_plus[0], qify('3/4'))
            self.assertAlmostEqual(result_plus[1], qify('(1/4) * sqrt(3) * I'))
            self.assertAlmostEqual(result_plus[2], qify('1/4'))
            self.assertAlmostEqual(result_plus[3], qify('(1/4) * sqrt(3) * -I'))
            p_minus = Particle('p_minus', one, -1)
            result_minus = g30.measure(p_minus)
            self.assertAlmostEqual(sum(result_minus)**2, p_minus.probability)
            print(f'gate={g30}, particle={p_minus}, result={result_minus}')
            self.assertAlmostEqual(result_minus[0], qify('1/4'))
            self.assertAlmostEqual(result_minus[1], qify('(1/4) * sqrt(3) * -I'))
            self.assertAlmostEqual(result_minus[2], qify('3/4'))
            self.assertAlmostEqual(result_minus[3], qify('(1/4) * sqrt(3) * I'))

    # def test_discrepancy(self):
    #     log = logging.getLogger('quantish')
    #     log.setLevel(logging.DEBUG)
    #     CalcMode.mode = 'Float'
    #     config_dir = Path(Path.cwd(), 'configs')
    #     config_path = Path(config_dir, 'test_1gate').with_suffix('.yaml')
    #     with open(Path(config_dir, 'defaults.yaml'), 'r') as f:
    #         config = yaml.safe_load(f)
    #     with open(config_path, 'r') as f:
    #         config.update(yaml.safe_load(f))
    #     histogram = defaultdict(int)
    #     iterations = 10000
    #     for i in range(iterations):
    #         sim = Simulation(config)
    #         p1 = Particle('p1', 1, 1)
    #         sim.particles['p1'] = p1
    #         p2 = Particle('p2', 1, 1)
    #         sim.particles['p2'] = p2
    #         g1 = FredkinGate('g1', qn.qify('rad(40)'), sim=sim)
    #         g2 = FredkinGate('g2', qn.qify('rad(30)'), sim=sim)
    #         if i == 0:
    #             print(f'GATES: {g1}, {g2}')
    #             print(f'g1 cos^2={g1.cos2_theta:.3f}, sin^2={g1.sin2_theta:.3f}')
    #             print(f'g2 cos^2={g2.cos2_theta:.3f}, sin^2={g2.sin2_theta:.3f}')
    #             print(f'deltas cos^2={(g2.theta-g1.theta).cos**2:.3f}, sin^2={(g2.theta-g1.theta).sin**2:.3f}')
    #             print('')
    #         selector = random.random()
    #         g1.selector = selector
    #         g2.selector = selector
    #         # g1.selector = random.random()
    #         # g2.selector = random.random()
    #         # g30_result = g30.cpair(1)
    #         sim.gates['g1'] = g1
    #         sim.links['p1'] = 'g1.upper'
    #         sim.links['p2'] = 'g2.upper'
    #         # control_angle = sum(g45_result[:2])
    #         # control = Particle('control', control_angle, 1)
    #         # sim.particles['control'] = control
    #         # print(f'{sim.particles["control"]=}')
    #         # g1 = FredkinGate('g1', qn.qify('rad(30)'), sim)
    #         # print(f'{g1=}')
    #         # sim.gates['g1'] = g1
    #         # g1.set_inputs()
    #         # print(f'{g1.inputs=}')
    #         # g1.set_weights()
    #         # print(f'{g1.weights=}')
    #         # g1.set_outputs()
    #         # print(f'{g1.outputs=}')
    #         # print(f'{g30=}, {p1=}')
    #         # result30 = g30.measure(p1)
    #         # print(f'{g30=}, {p1=}')
    #         # result45 = g30.measure(p1)
    #         # print(f'{result30=}, {result45=}')
    #         for gate in (g1, g2):
    #             # gate.reset()
    #             gate.set_inputs()
    #             gate.set_weights()
    #             gate.set_outputs()
    #             if gate.output_wire == 'upper':
    #                 histogram[f'{gate.name}.upper'] += 1
    #             else:
    #                 histogram[f'{gate.name}.lower'] += 1
    #         if g1.output_wire != g2.output_wire:
    #             histogram['discrepancy'] += 1
    #     print(f'g1.upper: {histogram["g1.upper"] / iterations:.3f}')
    #     print(f'g1.lower: {histogram["g1.lower"] / iterations:.3f}')
    #     print(f'g2.upper: {histogram["g2.upper"] / iterations:.3f}')
    #     print(f'g2.lower: {histogram["g2.lower"] / iterations:.3f}')
    #     print(f'discrepancy: {histogram["discrepancy"] / iterations:.3f}')

    def test_discrepancy2(self):
        log = logging.getLogger('quantish')
        log.setLevel(logging.DEBUG)
        CalcMode.mode = 'Float'
        config_dir = Path(Path.cwd(), 'configs')
        config_path = Path(config_dir, 'test_discrepancy').with_suffix('.yaml')
        with open(Path(config_dir, 'defaults.yaml'), 'r') as f:
            config = yaml.safe_load(f)
        with open(config_path, 'r') as f:
            config.update(yaml.safe_load(f))
        histogram = defaultdict(int)
        iterations = 1000
        sim = None
        config['links'] = {}
        for i in range(iterations):
            # p1 = Particle('p1', 1, 1)
            # p2 = Particle('p2', 1, -1)
            # g1 = FredkinGate('g1', qn.qify('rad(30)'))
            # g2 = FredkinGate('g2', qn.qify('rad(30)'))
            config['particles'] = {
                'p1': {'weight': '1', 'sign': '1'},
                'p2': {'weight': '1', 'sign': '1'}
            }
            config['gates'] = {
                'g1': {'angle': 'pi/8'},
                'g2': {'angle': 'pi/4'}
            }
            config['links'] = {
                'p1': 'g1.upper',
                # 'g1.upper': 'g2.upper',
                'g1.lower': 'g2.upper'
            }
            # config['run_stages'] = {
            #     'one': ['g1'],
            #     'two': ['g2']
            # }
            config['run_stages'] = {
                'one': ['g1', 'g2']
            }
            if sim is not None:
                del sim
            sim = Simulation(config)
            g1 = sim.gates['g1']
            g2 = sim.gates['g2']
            # sim.gates['g1'] = g1
            # sim.links['p1'] = 'g1.upper'
            # sim.links['g1.upper'] = 'g2.upper'
            # sim.particles['p1'] = p1
            # sim.particles['p2'] = p2
            if i == 0:
                print(f'GATES: {g1} sel={g1.selector:.2f}, {g2} sel={g2.selector:.2f}')
                print(f'g1 cos^2={g1.cos2_theta:.3f}, sin^2={g1.sin2_theta:.3f}')
                print(f'g2 cos^2={g2.cos2_theta:.3f}, sin^2={g2.sin2_theta:.3f}')
                print(f'deltas angles={(g2.theta-g1.theta).degrees:.2f}, cos^2={(g2.theta-g1.theta).cos**2:.3f}, sin^2={(g2.theta-g1.theta).sin**2:.3f}')
                print('')
            selector = random.random()
            g1.selector = selector
            g2.selector = selector
            # g1.selector = random.random()
            # g2.selector = random.random()
            # g30_result = g30.cpair(1)
            # sim.links['g1.lower'] = 'g2.upper'
            # sim.links['p2'] = 'g2.lower'
            # control_angle = sum(g45_result[:2])
            # control = Particle('control', control_angle, 1)
            # sim.particles['control'] = control
            # print(f'{sim.particles["control"]=}')
            # g1 = FredkinGate('g1', qn.qify('rad(30)'), sim)
            # print(f'{g1=}')
            # sim.gates['g1'] = g1
            # g1.set_inputs()
            # print(f'{g1.inputs=}')
            # g1.set_weights()
            # print(f'{g1.weights=}')
            # g1.set_outputs()
            # print(f'{g1.outputs=}')
            # print(f'{g30=}, {p1=}')
            # result30 = g30.measure(p1)
            # print(f'{g30=}, {p1=}')
            # result45 = g30.measure(p1)
            # print(f'{result30=}, {result45=}')
            for stage in sim.run_stages.values():
                stage.run()
            for gate in (g1, g2):
                # gate.reset()
                # gate.set_inputs()
                # gate.set_weights()
                # gate.set_outputs()
                if gate.output_wire == 'upper':
                    histogram[f'{gate.name}.upper'] += 1
                else:
                    histogram[f'{gate.name}.lower'] += 1
            if g1.output_wire != g2.output_wire:
                histogram['discrepancy'] += 1
        print(f'g1.upper: {histogram["g1.upper"] / iterations:.3f}')
        print(f'g1.lower: {histogram["g1.lower"] / iterations:.3f}')
        print(f'g2.upper: {histogram["g2.upper"] / iterations:.3f}')
        print(f'g2.lower: {histogram["g2.lower"] / iterations:.3f}')
        print(f'discrepancy: {histogram["discrepancy"] / iterations:.3f}')


    def test_random_gate(self):
        log = logging.getLogger('quantish')
        log.setLevel(logging.DEBUG)
        CalcMode.mode = 'Float'
        config_dir = Path(Path.cwd(), 'configs')
        config_path = Path(config_dir, 'test_1gate').with_suffix('.yaml')
        with open(Path(config_dir, 'defaults.yaml'), 'r') as f:
            config = yaml.safe_load(f)
        with open(config_path, 'r') as f:
            config.update(yaml.safe_load(f))
        sim = Simulation(config)
        random_angle = random.random() * qn.PI() * 2
        # p1 = random_particle('p1')
        p1 = Particle('p1', 1, 1)
        sim.particles['p1'] = p1
        g45 = FredkinGate('g45', qn.qify('rad(45)'))
        g30 = FredkinGate('g30', qn.qify('rad(30)'))
        g30_result = g30.cpair(1)
        control_angle = sum(g30_result[:2])
        control = Particle('control', control_angle, 1)
        sim.particles['control'] = control
        print(f'{sim.particles["control"]=}')
        g1 = FredkinGate('g1', qn.qify('rad(30)'), sim)
        print(f'{g1=}')
        sim.gates['g1'] = g1
        # g1.set_inputs()
        # print(f'{g1.inputs=}')
        # g1.set_weights()
        # print(f'{g1.weights=}')
        # g1.set_outputs()
        # print(f'{g1.outputs=}')
        print(f'{g1=}, {p1=}')
        result = g1.measure(p1)
        print(f'{result=}')
        up_count = 0
        up_lo = 0
        up_up = 0
        lo_lo = 0
        lo_up = 0
        n_iter = 1000
        sel_sum = 0.0
        for i in range(n_iter):
            # g1.swapping = random.choice([True, False])
            g1.reset()
            selector = random.random()
            sel_sum += selector
            # print(f'{selector=}')
            if selector < 0.5:
                sim.links['control0'] = 'g1.control'
                sim.sources['g1.control'] = 'control0'
                if 'control1' in sim.links.keys():
                    del sim.links['control1']
            else:
                sim.links['control1'] = 'g1.control'
                sim.sources['g1.control'] = 'control1'
                if 'control0' in sim.links.keys():
                    del sim.links['control0']
            g1.init_inputs()
            # print(f'{g1.inputs=}')
            g1.set_weights()
            g1.output_wire = None
            # print(f'{g1.weights=}')
            g1.set_outputs()
            ctrl_in = g1.input['control']
            upper_in = g1.input['upper']
            lower_in = g1.input['lower']
            ctrl_w = g1.port_weights('control')
            upper_w = g1.port_weights('upper')
            lower_w = g1.port_weights('lower')
            ctrl_o = g1.port_outputs('control')
            upper_r = g1.port_results('upper')
            lower_r = g1.port_results('lower')
            if g1.swapping:
                if lower_r:
                    up_lo += 1
                    up_count += 1
                else:
                    lo_up += 1
            else:
                if upper_r:
                    up_up += 1
                    up_count += 1
                else:
                    lo_lo += 1
            if g1.port_results('upper'):
                self.assertTrue(not lower_r)
                r_up = Particle.merge(upper_r)
                self.assertTrue(r_up.equiv(Particle.merge(g1.port_results('upper'))))
            else:
                self.assertTrue(not upper_r)
                r_lo = Particle.merge(lower_r)
                self.assertTrue(r_lo.equiv(Particle.merge(g1.port_results('lower'))))
            # print(f'{g1.outputs=}')
            # print(f'INPUTS: {g1.swapping=}, {ctrl_in=}, {upper_in=}, {lower_in=}')
            # print(f'WEIGHTS: {g1.swapping=}, {ctrl_w=}, {upper_w=}, {lower_w=}')
            # print(f'OUTPUT: {g1.swapping=}, {ctrl_o=}, {upper_o=}, {lower_o=}')
        up_rate = up_count/n_iter
        print(f'{up_count=}, {up_rate=}, {up_lo=}, {up_up=}, {lo_lo=}, {lo_up=}')
        print(f'{up_up/up_lo=}, {lo_lo/lo_up=}')
        print(f'{sel_sum/(n_iter/2)=}')
        self.assertEqual(up_lo+up_up+lo_lo+lo_up, n_iter)
        # self.assertAlmostEqual(sel_sum, n_iter/2)
        self.assertAlmostEqual(up_rate, g1.cos2_theta, 1)

if __name__ == '__main__':
    unittest.main()
