"""The double-slit demo's textbook relations."""
import math
import unittest

import quantish.qnumber as qn
from quantish.qnumber import CalcMode
from quantish.double_slit import pixel_probability, screen_curve


class TestDoubleSlit(unittest.TestCase):
    def setUp(self):
        CalcMode.default('Float')
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()

    def curves(self, fringes=3, n=81):
        return {mode: screen_curve(n, fringes, mode)[1]
                for mode in ('both', 'slit1', 'slit2', 'observed')}

    def test_single_slit_is_flat(self):
        c = self.curves()
        for mode in ('slit1', 'slit2'):
            self.assertAlmostEqual(min(c[mode]), max(c[mode]), places=12)

    def test_both_slits_interfere(self):
        c = self.curves()
        self.assertAlmostEqual(min(c['both']), 0.0, places=9)   # dark fringes
        # bright fringes reach 4x the single-slit intensity
        self.assertAlmostEqual(max(c['both']), 4 * c['slit1'][0], places=9)
        # central bright fringe at the screen center (equal path lengths)
        mid = len(c['both']) // 2
        self.assertAlmostEqual(c['both'][mid], max(c['both']), places=9)

    def test_pixel_follows_the_cos_law(self):
        # remerge + sign sorter: P(S) = (1 + cos phi)/2, exact per engine run
        for degrees in (0, 60, 90, 120, 180):
            phi = math.radians(degrees)
            self.assertAlmostEqual(pixel_probability(phi),
                                   (1 + math.cos(phi)) / 2, places=12)

    def test_observation_restores_classical_sum(self):
        c = self.curves()
        for obs, s1, s2 in zip(c['observed'], c['slit1'], c['slit2']):
            self.assertAlmostEqual(obs, s1 + s2, places=12)


if __name__ == '__main__':
    unittest.main()
