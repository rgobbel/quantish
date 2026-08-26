import logging

import quantish.qnumber as qn
from quantish.qnumber import qify, Complex, Real, I, PI, zerop
from quantish.util import Sign, OTHER

log = logging.getLogger('quantish')

class FredkinGate:
    """A quantish Fredkin gate: an angle plus the four precomputed weight
    components of the switch-wire split. Gates are stateless — the runner
    in config_space.py asks for components per configuration-space point
    via switch_components().

    The optional *phase* rotates the weight of EVERY particle traversing
    the gate by e^{iφ} — switch-wire particles via the split components
    (multiplied through below), control-wire pass-throughs via
    phase_factor in the runner (config_space.particle_splits). A phase
    never changes a magnitude, so an angle-0 gate with a phase, entered
    through its control wire, is a pure phase plate: one particle in,
    same particle out, weight rotated by φ in the complex plane.

    The phase is an extension beyond the book's gates, which have only
    the measurement angle; its default of 0 leaves every book circuit
    unchanged. The name comes from the optics device — a thin
    transparent plate inserted into one light path, delaying the wave so
    its phase shifts without its amplitude changing."""

    def __init__(self, name:str, theta:Real=0, phase:Real=0):
        self.name = name
        # radians, kept exactly as given (no normalization into [0, 2π),
        # so an angle entered as -30º displays as -30º, not 330º)
        self.theta = qify(theta)
        self.phase = qify(phase)
        if type(self) is DelayGate:
            return
        self.twist = self.theta - PI/2

        self.cos_theta = self.theta.cos
        self.sin_theta = self.theta.sin
        self.cos2_theta = Complex(self.cos_theta**2)
        self.cos_sin_theta = self.cos_theta * self.sin_theta * I
        self.mcos_sin_theta = self.cos_theta * self.sin_theta * -I
        self.sin2_theta = Complex(self.sin_theta**2)

        self.cos_twist = self.twist.cos
        self.sin_twist = self.twist.sin
        self.cos2_twist = Complex(self.cos_twist**2)
        self.cos_sin_twist = I * self.cos_twist * self.sin_twist
        self.mcos_sin_twist = -I * self.cos_twist * self.sin_twist
        self.sin2_twist = Complex(self.sin_twist**2)

        if not zerop(self.phase):
            self.phase_factor = Complex(1).rotate(self.phase)   # e^{iφ}
            self.cos2_theta = self.cos2_theta * self.phase_factor
            self.cos_sin_theta = self.cos_sin_theta * self.phase_factor
            self.mcos_sin_theta = self.mcos_sin_theta * self.phase_factor
            self.sin2_theta = self.sin2_theta * self.phase_factor
            self.cos2_twist = self.cos2_twist * self.phase_factor
            self.cos_sin_twist = self.cos_sin_twist * self.phase_factor
            self.mcos_sin_twist = self.mcos_sin_twist * self.phase_factor
            self.sin2_twist = self.sin2_twist * self.phase_factor

    def report_type(self): ## HACK TO AVOID A DEPENDENCY LOOP
        return 'FredkinGate'

    def __repr__(self):
        if zerop(self.phase):
            return f'{self.name}({self.theta.degrees:.2f}º)'
        return f'{self.name}({self.theta.degrees:.2f}º, φ={self.phase.degrees:.2f}º)'

    def switch_components(self, port:str, sign:Sign, control_present:bool):
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