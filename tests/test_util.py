import unittest

import numpy as np

from quantish.util import select
import random

class TestSelect(unittest.TestCase):
    choices = [0.1, 0.2, 0.0, 0.7]
    def test_low_to_high(self):
        choices = sorted(TestSelect.choices)
        selections = [0] * len(choices)
        iterations = 1000000
        for i in range(iterations):
            selections[select(choices, random.random())] += 1
        result = [x/iterations for x in selections]
        self.assertTrue(np.allclose(choices, result, atol=1e-3), f'{choices=}, {result=}')  # add assertion here

    def test_high_to_low(self):
        choices = sorted(TestSelect.choices, reverse=True)
        selections = [0] * len(choices)
        iterations = 1000000
        for i in range(iterations):
            selections[select(choices, random.random())] += 1
        result = [x/iterations for x in selections]
        self.assertTrue(np.allclose(choices, result, atol=1e-3), f'{choices=}, {result=}')  # add assertion here

    def test_shuffled(self):
        choices = TestSelect.choices
        random.shuffle(choices)
        selections = [0] * len(choices)
        iterations = 1000000
        for i in range(iterations):
            selections[select(choices, random.random())] += 1
        result = [x/iterations for x in selections]
        self.assertTrue(np.allclose(choices, result, atol=1e-3), f'{choices=}, {result=}')  # add assertion here

if __name__ == '__main__':
    unittest.main()
