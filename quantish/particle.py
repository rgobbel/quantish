"""Particles, post-refactor: a particle is a named thing with a sign and an
initial weight. During simulation, weights belong to configuration-space
points (see config_space.py) — a Particle only supplies the initial
conditions parsed from the model YAML, and labels for diagrams.
"""
from collections import namedtuple

from quantish.qnumber import Complex, probability
from quantish.util import Sign, sstr, wstr

CompositeKey = namedtuple('CompositeKey', ['name', 'sign'])

class PKey(CompositeKey):
    __slots__ = ()
    def __repr__(self):
        return f'{self.name}{self.sign}'


class Particle:
    def __init__(self, name: str, weight=1, sign=Sign.plus, precision: int = 2):
        assert len(name) > 0
        self.name = name
        self.weight = Complex(weight)
        self.sign = Sign(sign)
        self.precision = precision

    def __repr__(self):
        return f'{sstr(self.sign)}{self.name}'

    @property
    def pkey(self):
        return PKey(name=self.name, sign=self.sign)

    @property
    def probability(self):
        return probability(self.weight)

    def ps(self, short=False, name_only=False):
        """Decorated display string: sign, name, weight, probability."""
        nstr = self.name.split('>')[0] if (short or name_only) else self.name
        if name_only:
            return nstr
        return (f'{sstr(self.sign)}{nstr}'
                f'({wstr(self.weight, precision=self.precision)}|{self.probability:.{self.precision}f})')