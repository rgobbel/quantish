import unittest

from quantish.particle import Particle
from quantish.util import Sign


class TestParticle(unittest.TestCase):
    def test_create(self):
        pname = 'p_test'
        for sign in Sign:
            p = Particle(name=pname, sign=sign)
            self.assertTrue(p.name == pname, f'{p.name=}, {pname=}')
            self.assertTrue(p.sign == sign, f'{p.sign=}, {sign=}')
            self.assertTrue(f'{p}' == f'{sign}p_test', f'{p=}, {f'{sign}p_test'}')



if __name__ == '__main__':
    unittest.main()
