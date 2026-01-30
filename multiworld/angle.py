import sympy as sym
import math as m
import logging

from multiworld.qnumber import PI, isq, CalcMode, qify
from multiworld.util import angstr

log = logging.getLogger('multiworld')

class Angle:
    def __init__(self, value, unit='degrees'):
        if not isq(value):
            value = qify(value)
        if unit == 'degrees':
            if CalcMode.mode == 'Symbolic':
                value = sym.rad(value)
            else:
                value = m.radians(qify(value))
        twopi = 2 * PI
        modded = value % twopi
        self.value = modded

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return angstr(self.radians)

    def __add__(self, other):
        if type(other) is type(self):
            value = other.radians
        else:
            value = other
        return self.__class__(self.radians + value, unit='radians')

    @property
    def degrees(self):
        return self.value.degrees

    @property
    def radians(self):
        return self.value
