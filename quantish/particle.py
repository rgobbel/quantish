import random
from typing import Self, Union
import cmath as cm

from quantish.util import wstr, Gensym
from quantish.qnumber import qify, probability, isq, Complex, PI

class Particle:
    def __init__(self, name, weight, sign, add_with_signs=False, precision=2):
        if sign not in (-1, 1):
            raise ValueError(f'Invalid value for sign: {sign.__repr__()}')
        self.precision = precision
        self.add_with_signs = add_with_signs
        self.name = name
        self.pid = Gensym(p_first(name))
        self.weight = qify(weight)
        self.sign = qify(sign)
        # if trace is not None:
        #     self.trace = trace
        # else:
        #     self.trace = ''

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
        return 1.0 - abs(self.weight.phase) % (PI()/2)

    @property
    def superposed(self):
        return 0 < self.probability < 1

    @property
    def v_0(self):
        return Complex(1+0j if self.sign == 1 else 1j)

    def ps(self, with_id=False, short=False, name_only=False):
        x = complex(self.weight)
        ss = f"{'+' if self.sign > 0 else '-'}"
        pstr = f'%.{self.precision}f'
        probstr = pstr % self.probability
        if name_only:
            return self.name.split('>')[0]
        if short:
            nstr = self.name.split('>')[0]
        elif with_id:
            nstr = self.pid
        else:
            nstr = self.name
        return f'{ss}{nstr}({wstr(x, precision=self.precision)}|{probstr})'

    @classmethod
    def merge(cls, particles):
        if not isinstance(particles, list):
            return particles
        result = None
        for particle in particles:
            if result is None: result = particle
            else: result += particle
        return result or Particle('', 0, 1)

    def equiv(self, other):
        if self.weight == other.weight and self.sign == other.sign:
            return True
        return False

    def __add__(self, other:Self):
        if self.probability >= other.probability: new_sign = self.sign
        else: new_sign = other.sign
        if self.add_with_signs:
            new_weight = self.sign * self.weight + other.sign * other.weight
        else:
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
        phase = random.random() * 2 * cm.pi
        weight = weight * cm.cos(phase) + weight * 1j * cm.sin(phase)
    return Particle(name, weight, sign)

def p_last(p: Union[str|Particle]) -> str:
    if isinstance(p, Particle): p = p.name
    return p.split('>')[-1]

def p_first(p: Union[str|Particle])->str:
    if isinstance(p, Particle): p = p.name
    return p.split('>')[0]

def dest_parts(dstr: str) -> str:
    return p_last(dstr).split('.')


