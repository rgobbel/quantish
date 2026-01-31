import random
from collections import namedtuple
from enum import Enum
from typing import Self, Union, NamedTuple
# import cmath as cm

from multiworld.util import wstr, Gensym, sstr, Sign, log
from multiworld.qnumber import qify, probability, isq, Complex
import multiworld.qnumber as qn

CompositeKey = namedtuple('CompositeKey', ['name', 'sign'])
class PKey(CompositeKey):
    __slots__ = ()
    def __repr__(self):
        return f'{self.name}{self.sign}'

class Particle:
    def __init__(self, name, weight, sign, next_step=0, precision=2):
        self.next_step = next_step
        self.precision = precision
        self.name = name
        self.pid = Gensym(p_first(name))
        self.weight = Complex(weight)
        self.sign = Sign(sign)
        self.frozen = False

    def __repr__(self):
        if isq(self.weight) and self.weight.mm == 'Symbolic':
            return f'{self.ps()}({self.weight})'
        else:
            return self.ps()

    def __hash__(self):
        isign = int(float(self.sign))
        ireal = int(float(self.weight.real * 10))
        iimag = int(float(self.weight.imag * 100))
        return hash(f'{self.name}|{isign}{ireal:.10f}.{iimag:.10f}')

    @property
    def probability(self):
        return probability(self.weight)

    @property
    def reality(self):
        return 1.0 - abs(self.weight.phase) % (qn.PI/2)

    @property
    def superposed(self):
        return 0 < self.probability < 1

    @property
    def v_0(self):
        return Complex(1 if self.sign == 1 else qn.I)

    @property
    def pkey(self):
        return PKey(name=self.name, sign=self.sign)

    def ps(self, with_id=False, short=False, name_only=False):
        if name_only:
            return self.name.split('>')[0]
        if short:
            nstr = self.name.split('>')[0]
        elif with_id:
            nstr = self.pid
        else:
            nstr = self.name
        return f'{sstr(self.sign)}{nstr}({wstr(self.weight, precision=self.precision)}|{self.probability:.{self.precision}f})'

    @classmethod
    def merge(cls, particles, next_step=0):
        if not isinstance(particles, list):
            return particles
        result = None
        for particle in particles:
            if result is None: result = particle
            else: result += particle
        if not result:
            result = Particle('', 0, 1, next_step=next_step)
        return result

    def equiv(self, other):
        if self.weight == other.weight and self.sign == other.sign:
            return True
        return False

    def __add__(self, other:Self):
        if self.frozen:
            log.info(f'Trying to add to frozen particle {self}, {other=}')
            return self
        if self.probability >= other.probability: new_sign = self.sign
        else: new_sign = other.sign
        new_weight = self.weight + other.weight
        return self.__class__(self.name, new_weight, new_sign,
                              # f'->{self.trace}+{other.trace}',
                              precision=self.precision)

def random_particle(name, weight=None, phase=None, sign=None):
    if sign is None:
        sign = random.randint(0, 1) * 2 - 1
    if weight is None:
        weight = random.random()
    if phase is None:
        phase = random.random() * 2 * qn.PI
        weight = weight * phase.cos + weight * qn.I * phase.sin
    return Particle(name, weight, sign)

def p_last(p: Union[str|Particle]) -> str:
    if isinstance(p, Particle): p = p.name
    return p.split('>')[-1]

def p_first(p: Union[str|Particle])->str:
    if isinstance(p, Particle): p = p.name
    return p.split('>')[0]

def dest_parts(dstr: str) -> str:
    return p_last(dstr).split('.')


