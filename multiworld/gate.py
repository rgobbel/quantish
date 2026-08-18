import logging

import multiworld.qnumber as qn
from multiworld.angle import Angle
from multiworld.qnumber import qify, Complex, Real
from multiworld.util import Sign, OTHER

log = logging.getLogger('multiworld')

class FredkinGate:
    """A quantish Fredkin gate: an angle plus the four precomputed weight
    factors of the switch-wire split. Gates are stateless — the runner in
    config_space.py asks for factors per config space point via switch_factors()."""

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

    def switch_factors(self, port:str, sign:Sign, control_present:bool):
        """
        The four-way split for a particle entering switch wire *port* with
        *sign*, in the book's component order c2a, c2b, c3a, c3b
        (§4.2.3 of Good and Real): a list of
        (output port, output sign, weight component) triples.
        The component values are fixed by the measurement angle —
        (cos²θ, i·sinθcosθ, sin²θ, −i·sinθcosθ) — and only their
        DESTINATIONS move: the measurement-parallel pair (c2a, c2b)
        passes straight through and the perpendicular pair (c3a, c3b)
        crosses over, unless control presence, or a minus sign (but not
        both), swaps the two destinations.
        """
        swapped = (not control_present) ^ (sign == Sign.plus)
        straight, cross = port, OTHER[port]
        c2_dest, c3_dest = (cross, straight) if swapped else (straight, cross)
        return [(c2_dest, sign, self.cos2_theta),
                (c2_dest, -sign, self.cos_sin_theta),
                (c3_dest, sign, self.sin2_theta),
                (c3_dest, -sign, self.mcos_sin_theta)]


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