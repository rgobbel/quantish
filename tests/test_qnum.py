import math
import unittest
from quantish.qnumber import CalcMode, Modes, Real, Complex
from sympy import exp
import sympy as sym
import cmath as cm
import math as m

rot = lambda x: exp(1j * x.v)

class TestQNumbers(unittest.TestCase):

    def test_create(self):
        for mode in Modes:
            CalcMode.mode = mode
            intable = 1+0j
            floatable = 1.5+0j
            onlycomplex = 1+1j
            real_intable = Real(intable.real)
            complex_intable = Complex(intable)
            real_floatable = Real(floatable.real)
            complex_floatable = Complex(floatable)
            complex_onlycomplex = Complex(onlycomplex)

            self.assertTrue(type(real_intable) is Real)
            if mode == 'Float':
                self.assertTrue(type(real_intable.v) is int)
            else:
                self.assertTrue(type(real_intable.v) is sym.Float)
            self.assertEqual(real_intable, 1)
            self.assertTrue(type(complex_intable) is Complex)
            self.assertEqual(complex_intable.v, intable.real)
            self.assertTrue(type(real_floatable) is Real)
            if mode == 'Float':
                self.assertTrue(type(real_floatable.v) is float)
            else:
                self.assertTrue(type(real_floatable.v) is sym.Float)
            self.assertTrue(type(complex_floatable) is Complex)
            if mode == 'Float':
                self.assertTrue(type(complex_floatable.v) is complex)
            else:
                self.assertTrue(type(complex_floatable.v) is sym.Float)
            self.assertEqual(complex_floatable.v, floatable.real)
            self.assertEqual(complex_floatable.real, floatable.real)

    def test_float_int(self):
        CalcMode.mode = 'Float'
        num = 2
        q2 = Real(num)
        self.assertEqual(q2, num)
        self.assertEqual(q2+1, num+1)

    def test_sym_int(self):
        CalcMode.mode = 'Symbolic'
        num = 2
        q2 = Real(num)
        self.assertEqual(q2, num)
        self.assertEqual(q2+1, num+1)

    def test_float_float(self):
        CalcMode.mode = 'Float'
        num = 2.13
        q213 = Real(num, mode=CalcMode.mode)
        self.assertEqual(float(q213 ** 2), num ** 2)

    def test_sym_float(self):
        CalcMode.mode = 'Symbolic'
        num = 2.13
        q213 = Real(num, mode=CalcMode.mode)
        self.assertEqual(float(q213 ** 2), num ** 2)

    def test_arithmetic_float(self):
        for mode in Modes:
            CalcMode.mode = mode
            num1 = 3.2
            qn1 = Real(num1, mode=CalcMode.mode)
            self.assertEqual(float(qn1 + 4), num1 + 4)
            self.assertEqual(float(qn1 * 4), num1 * 4, f'qn1={qn1.__repr__()}')
            self.assertEqual(float(qn1 ** 4), num1 ** 4)
            self.assertEqual(float(4 + qn1), num1 + 4)
            self.assertEqual(float(4 * qn1), num1 * 4)
            self.assertEqual(4**qn1, 4**num1)

    def test_arithmetic_float2(self):
        for mode in Modes:
            CalcMode.mode = mode
            num1 = 3.2
            num2 = 4.7
            qn1 = Real(num1, mode=CalcMode.mode)
            qn2 = Real(num2, mode=CalcMode.mode)
            self.assertEqual(float(qn1 + qn2), num1 + num2)
            self.assertEqual(float(qn2 + qn1), num2 + num1)
            self.assertEqual(float(qn1 % qn2), num1 % num2)
            self.assertEqual(float(qn2 % qn1), num2 % num1)
            self.assertEqual(float(qn1 * qn2), num1 * num2)
            self.assertEqual(float(qn2 * qn1), num2 * num1)
            self.assertEqual(float(qn1 ** qn2), num1 ** num2)
            self.assertEqual(float(qn2 ** qn1), num2 ** num1)

    def test_arithmetic_float3(self):
        for i in range(len(Modes)):
            num1 = 3.2
            num2 = 4.7
            CalcMode.mode = Modes[i]
            qn1 = Real(num1, mode=CalcMode.mode)
            CalcMode.mode = Modes[(i + 1) % 2]
            qn2 = Real(num2, mode=CalcMode.mode)
            self.assertEqual(float(qn1 + qn2), num1 + num2)
            self.assertEqual(float(qn2 + qn1), num2 + num1)
            self.assertEqual(float(qn1 * qn2), num1 * num2)
            self.assertEqual(float(qn2 * qn1), num2 * num1)
            self.assertEqual(float(qn1 ** qn2), num1 ** num2)
            self.assertEqual(float(qn2 ** qn1), num2 ** num1)

    def test_complex_base(self):
        for mode in Modes:
            CalcMode.mode = mode
            num1 = 1.1
            num2 = 1+0j
            num3 = 1+1j
            num4 = 1j
            if mode == 'Symbolic':
                angle30 = sym.pi/6
            else:
                angle30 = m.radians(30)
            rad30 = Real(angle30, mode=CalcMode.mode)
            qc1 = Complex(num1, mode=CalcMode.mode)
            qc2 = Complex(num2, mode=CalcMode.mode)
            qc3 = Complex(num3, mode=CalcMode.mode)
            qc4 = Complex(num4, mode=CalcMode.mode)
            self.assertEqual(num1.imag, 0)
            self.assertEqual(num2.imag, 0)
            self.assertEqual(num3.imag, 1)
            self.assertEqual(num4.imag, 1)
            self.assertAlmostEqual(complex(rot(rad30)), cm.exp(1j * math.radians(30)))
            self.assertEqual(qc1, num1)
            self.assertEqual(qc2, num2)
            self.assertEqual(qc3, num3)