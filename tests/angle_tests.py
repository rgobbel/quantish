import unittest
from quantish.qnumber import Real, CalcMode, Modes
from quantish.angle import Angle
import math as m
import sympy as sym

def angle_rad(x, unit='degrees'):
    if CalcMode.mode == 'Symbolic':
        if unit == 'degrees':
            return sym.rad(x)
        else:
            return x
    else:
        if unit == 'degrees':
            return m.radians(x)
        else:
            return x


class TestAngles(unittest.TestCase):
    def test_basic(self):
        for mode in Modes:
            CalcMode.mode = mode
            rad30 = Real(angle_rad(30))
            self.assertAlmostEqual(Angle(rad30, unit='radians').radians, m.radians(30))  # add assertion here
            self.assertAlmostEqual(Angle(rad30, unit='radians').degrees, 30)  # add assertion here
            self.assertAlmostEqual(Angle(Real(30), unit='degrees').radians, m.radians(30))  # add assertion here
            self.assertAlmostEqual(Angle(Real(30), unit='degrees').degrees, 30)  # add assertion here


if __name__ == '__main__':
    unittest.main()
