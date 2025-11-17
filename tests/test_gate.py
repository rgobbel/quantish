import unittest
from typing import Callable

import numpy as np
import sympy as sym
# import cmath as cm
# import math as m
from quantish.qnumber import CalcMode, qify, I, PI, Modes, to_native, Complex
from quantish.particle import Particle
import quantish.qnumber as qn
from quantish.gate import FredkinGate

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
        return one, m_one, angle, twist, g, canon_quadp, canon_quadm

    @staticmethod
    def check_quads(calc, canon):
        for i in range(4):
            calc_i = to_native(calc[i])
            canon_i = to_native(canon[i])
            if not np.isclose(calc_i, canon_i):
                print(f'{i=}, {calc[i]=}, {canon[i]=}')
                return False
        return True

    def test_cpair_methods(self):
        print('test_cpair_methods:\n')
        methods = ('cpair', 'cpair_alt', 'cpair0', 'cpair1', 'cpair2', 'cpair3')
        for mode in Modes:
            CalcMode.mode = mode
            one, m_one, angle, twist, g, canon_quadp, canon_quadm = self.setup()
            self.assertAlmostEqual(sum(canon_quadp), 1)
            self.assertAlmostEqual(sum(canon_quadm), -1)
            with self.subTest(mode=mode):
                for method_str in methods:
                    with self.subTest(method=method_str):
                        method: Callable = getattr(g, method_str)
                        for sign in (1, -1):
                            with self.subTest(sign=sign):
                                if sign > 0:
                                    ss = '+'
                                    value = one
                                    canon = canon_quadp
                                else:
                                    ss = '-'
                                    value = m_one
                                    canon = canon_quadm
                                if method_str in ('cpair0', 'cpair_alt'):
                                    result = method(value, angle)
                                else:
                                    result = method(value) # angle is built into the gate
                                print(f'{method_str}{ss} ({mode}) = {result}')
                                self.assertTrue(self.check_quads(result, canon), f'{method}{ss} ({mode}) failed')
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
    #
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


if __name__ == '__main__':
    unittest.main()
