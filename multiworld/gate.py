import logging

import multiworld.qnumber as qn
from multiworld.angle import Angle
from multiworld.qnumber import qify, Complex, Real
from multiworld.util import Sign, OTHER

log = logging.getLogger('multiworld')

class FredkinGate:
    """A quantish Fredkin gate: an angle plus the four precomputed weight
    factors of the switch-wire split. Gates are stateless — the runner in
    config_space.py asks for factors per world via switch_factors()."""

    def __init__(self, name:str, theta:Real=0):
        self.name = name
        self.theta = qify(theta)
        if type(self) is DelayGate:
            return
        if type(self.theta) is Angle:
            self.atheta = self.theta
            self.theta = self.theta.radians
        else:
            self.atheta = Angle(self.theta, unit='radians')
            self.theta = self.atheta.radians
        self.twist = self.theta - qn.PI_fn()/2

        self.cos_theta = self.theta.cos
        self.sin_theta = self.theta.sin
        self.cos2_theta = Complex(self.cos_theta**2)
        self.cos_sin_theta = self.cos_theta * self.sin_theta * qn.I_fn()
        self.mcos_sin_theta = self.cos_theta * self.sin_theta * -qn.I_fn()
        self.sin2_theta = Complex(self.sin_theta**2)

        self.cos_twist = self.twist.cos
        self.sin_twist = self.twist.sin
        self.cos2_twist = Complex(self.cos_twist**2)
        self.cos_sin_twist = qn.I_fn() * self.cos_twist * self.sin_twist
        self.mcos_sin_twist = -qn.I_fn() * self.cos_twist * self.sin_twist
        self.sin2_twist = Complex(self.sin_twist**2)

    def report_type(self): ## HACK TO AVOID A DEPENDENCY LOOP
        return 'FredkinGate'

    def __repr__(self):
        return f'{self.name}({self.atheta.degrees:.2f}º)'

    def cpair(self, w:Complex, twist=False):
        """
        From AIM-1026a: the four split components of weight w.
        Values are precomputed for speed. twist=True gives the minus-sign
        column (cos/sin of theta - pi/2, i.e. sin/cos of theta).
        """
        if not twist:
            c2a = w * self.cos2_theta
            c2b = w * self.cos_sin_theta
            c3a = w * self.sin2_theta
            c3b = w * self.mcos_sin_theta
        else:
            c2a = w * self.cos2_twist
            c2b = w * self.cos_sin_twist
            c3a = w * self.sin2_twist
            c3b = w * self.mcos_sin_twist
        return c2a, c2b, c3a, c3b

    def switch_factors(self, port:str, sign:Sign, control_present:bool):
        """
        The four-way split for a particle entering switch wire *port* with
        *sign* (from §4.2.3 of Good and Real): a list of
        (output port, output sign, weight factor) triples.
        The first two stay on the straight-through wire, the last two cross
        over; control presence (or a minus sign, but not both) swaps the
        factor columns.
        """
        column = int((not control_present) ^ (sign == Sign.plus))
        rows = ((port, sign, (self.cos2_theta, self.sin2_theta)),
                (port, -sign, (self.cos_sin_theta, self.mcos_sin_theta)),
                (OTHER[port], sign, (self.sin2_theta, self.cos2_theta)),
                (OTHER[port], -sign, (self.mcos_sin_theta, self.cos_sin_theta)))
        return [(out_port, out_sign, factors[column]) for out_port, out_sign, factors in rows]


class DelayGate(FredkinGate):
    """A control-only pass-through gate: one particle in, same particle out,
    weight unchanged. Exists so diagrams can show explicit timing delays."""

    def __init__(self, name, source:str='', sink:str=''):
        super().__init__(name)
        self.source = source
        self.sink = sink

    def report_type(self): ## TOTAL HACK
        return 'DelayGate'

    def __repr__(self):
        return f'{self.name}({self.source}>{self.sink})'

    @property
    def theta(self):
        return qify(0)
    @theta.setter
    def theta(self, value):
        pass