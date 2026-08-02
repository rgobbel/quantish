import itertools
import random
from collections import namedtuple
from enum import Enum
from typing import Self, Union, NamedTuple, List
from copy import deepcopy
# from multiworld.link_cut_tree import SubtreeSumNode, build_link_cut_tree
import networkx as nx

from BitVector import BitVector

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
    SUPPRESS_WEIGHT_WARNINGS = False

    def __init__(self, name:str, weight, sign, next_step=0, precision=2,
                 trace=None, active_gates=None, family_tree=None,
                 splits=None):
        assert isinstance(next_step, int)
        assert len(name) > 0
        self.next_step = next_step
        self.precision = precision
        self.name = name
        self.pid = Gensym(p_first(name))
        self.weight = Complex(weight)
        self.sign = Sign(sign)
        self.frozen = False
        if active_gates is not None:
            self.active_gates = active_gates
        else:
            self.active_gates = set()
        if trace is None:
            self.trace = ['']
        else:
            self.trace = list(trace)
        if splits is None:
            self.splits = []
        else:
            self.splits = splits

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

    def copy(self):
        return self.__class__(self.name, deepcopy(self.weight), self.sign, self.next_step, self.precision,
                              deepcopy(self.trace), deepcopy(self.active_gates))

    @property
    def trace_s(self):
        return '>'.join(self.trace)

    @property
    def split_s(self):
        if not self.splits:
            return ''
        return '#'.join(self.splits)

    @property
    def probability(self):
        return probability(self.weight)

    @property
    def reality(self):
        return 1.0 - abs(self.weight.phase) % (qn.PI_fn()/2)

    @property
    def superposed(self):
        return not self.definite

    @property
    def definite(self):
        return ((self.weight.real == 1 and self.weight.imag == 0) or
                (self.weight.real == 0 and self.weight.imag == 1))

    @property
    def v_0(self):
        return Complex(1 if self.sign == Sign.plus else qn.I_fn())

    @property
    def pkey(self):
        return PKey(name=self.name, sign=self.sign)

    def ps(self, with_id=False, short=False, name_only=False, float=False):
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
    def merge(cls, particles, next_step=0, combine_signs=False):
        if not particles:
            return []
        if not isinstance(particles, list):
            return [particles]
        if combine_signs:
            return [sum(particles[1:], start=particles[0])]
        else:
            pluses = [p for p in particles if p.sign == Sign.plus]
            minuses = [p for p in particles if p.sign == Sign.minus]
            if len(pluses) > 1:
                pluses = [sum(pluses[1:], start=pluses[0])]
            if len(minuses) > 1:
                minuses = [sum(minuses[1:], start=minuses[0])]
            return pluses + minuses

    def equiv(self, other):
        if self.weight == other.weight and self.sign == other.sign:
            return True
        return False

    def __add__(self, other:Self):
        global SUPPRESS_WEIGHT_WARNINGS
        if self.frozen:
            log.info(f'Trying to add to frozen particle {self}, {other=}')
            return self
        # new_family = nx.
        # if self.split_s == other.split_s:
        #     log.info(f'meeting ourselves: {self}, {other}')
        #     return self
        # else:
        if self.probability >= other.probability: new_sign = self.sign
        else: new_sign = other.sign
        new_weight = self.weight + other.weight
        if abs(new_weight) > 1 and not Particle.SUPPRESS_WEIGHT_WARNINGS:
            log.warning(f'PARTICLE.ADD Weights add to more than 1: {self.pkey}, {self.weight=}, {other.weight=}')
            # log.debug(f'   {self.trace}')
            # log.debug(f'   {other.trace}')
        return self.__class__(
            self.name, new_weight, new_sign,
            precision=self.precision, next_step=self.next_step,
            active_gates=self.active_gates.union(other.active_gates),
            trace = ['+('] + self.trace + [','] + other.trace + [')'],
            splits = self.splits + ['+'] + other.splits
        )

    # def split(self, children:List[Self]):
    #     root = self.family_tree.nodes[0]
    #     for c in children:
    #         root.lc_link(c.family_tree.nodes[0])
    #     root.set_value(Complex(0))

def random_particle(name, weight=None, phase=None, sign=None):
    if sign is None:
        sign = random.randint(0, 1) * 2 - 1
    if weight is None:
        weight = random.random()
    if phase is None:
        phase = random.random() * 2 * qn.PI_fn()
        weight = weight * phase.cos + weight * qn.I_fn() * phase.sin
    return Particle(name, weight, sign, trace='RANDOM')

def p_last(p: Union[str|Particle]) -> str:
    if isinstance(p, Particle): p = p.name
    return p.split('>')[-1]

def p_first(p: Union[str|Particle])->str:
    if isinstance(p, Particle): p = p.name
    return p.split('>')[0]

def dest_parts(dstr: str) -> str:
    return p_last(dstr).split('.')


