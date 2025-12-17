from collections import defaultdict

from quantish.qnumber import qify, Complex, Real
import quantish.qnumber as qn
from quantish.angle import Angle
from quantish.particle import Particle
from quantish.config_space import default_switches, OTHER
from quantish.util import Gensym, enough
import numpy as np

class FredkinGate:

    def __init__(self, name, theta:Real, sim=None, alternative_measure=False):
        self.name = name
        self.id = Gensym(name)
        self.sim = sim
        self.measurement_cache = {}
        self.swapping = None
        self.control = 'undefined'
        self.inputs = {'upper': 'undefined', 'lower': 'undefined'}
        self.outputs = {'upper': {'straight': 'undefined', 'swapped': 'undefined'},
                        'lower': {'straight': 'undefined', 'swapped': 'undefined'}}
        if type(theta) is Angle:
            self.atheta = theta
            self.theta = theta.radians
        else:
            self.atheta = Angle(theta, unit='radians')
            self.theta = self.atheta.radians
        self.deg90 = qn.PI() / 2
        self.twist = self.theta - self.deg90

        self.cos_theta = self.theta.cos
        self.sin_theta = self.theta.sin
        self.cos2_theta = self.cos_theta**2
        self.cos_sin_theta = qn.I() * self.cos_theta * self.sin_theta
        self.mcos_sin_theta = -qn.I() * self.cos_theta * self.sin_theta
        self.sin2_theta = self.sin_theta**2
        self.wplusf = self.cos_theta * (qn.I() * self.theta).exp
        self.wminusf = self.sin_theta * (qn.I() * self.twist).exp

        self.cos_twist = self.twist.cos
        self.sin_twist = self.twist.sin
        self.cos2_twist = self.cos_twist**2
        self.cos_sin_twist = qn.I() * self.cos_twist * self.sin_twist
        self.mcos_sin_twist = -qn.I() * self.cos_twist * self.sin_twist
        self.sin2_twist = self.sin_twist**2
        self.wplusf_twist = self.cos_twist * (qn.I() * self.twist).exp
        self.wminusf_twist = self.sin_twist * (qn.I() * self.twist).exp

        if alternative_measure:
            if isinstance(alternative_measure, str):
                meth = getattr(self.__class__, alternative_measure)
            else:
                meth = getattr(self.__class__, 'cpair_alt')
        else:
            meth = getattr(self.__class__, 'cpair')
        setattr(self.__class__, 'cpair_m', meth)

    def __str__(self):
        return f'{self.name}({self.atheta.degrees:.1f}º)'

    def __repr__(self):
        return f'{self.name}({self.atheta.degrees:.2f}º)'

    def cpair0(self, w, theta):
        """from AIM-1026a"""
        c2a = w * theta.cos**2
        c2b = w * qn.I() * theta.cos * theta.sin
        c3a = w * theta.sin**2
        c3b = w * -qn.I() * theta.sin * theta.cos
        return c2a, c2b, c3a, c3b

    def cpair_alt(self, w, theta):
        """
            basic weight rotation with trig scaling
            This version computes the actual rotation in the complex plane
        """
        twist = theta - self.deg90
        wplus = w * theta.cos * (qn.I() * theta).exp
        wminus = w * theta.sin * (qn.I() * twist).exp
        return Complex(wplus.real), qn.I()*wplus.imag, Complex(wminus.real), qn.I()*wminus.imag

    def cpair(self, w, twist=False):
        """This is from AIM-1026a"""
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

    def cpair1(self, w, twist=False):
        """This follows the series of rotations described in AIM-1026a as well as Good and Real"""
        """basic weight rotation with trig scaling"""
        theta = self.twist if twist else self.theta
        twist = theta - self.deg90
        wplus = w * theta.cos * (qn.I() * theta).exp
        wminus = w * theta.sin * (qn.I() * twist).exp
        return Complex(wplus.real), qn.I()*wplus.imag, Complex(wminus.real), qn.I()*wminus.imag

    def cpair2(self, w, twist=False):
        theta = self.twist if twist else self.theta
        """This is from AIM-1026a, and is much much faster than doing the whole rotation"""
        c2a = w * theta.cos ** 2
        c2b = w * qn.I() * theta.cos * theta.sin
        c3a = w * theta.sin ** 2
        c3b = w * -qn.I() * theta.cos * theta.sin
        return c2a, c2b, c3a, c3b

    def cpair3(self, w, twist=False):
        """This follows the series of rotations described in AIM-1026a as well as Good and Real"""
        """basic weight rotation with trig scaling"""
        if not twist:
            wplus = w * self.wplusf
            wminus = w * self.wminusf
        else:
            wplus = w * self.wplusf_twist
            wminus = w * self.wminusf_twist
        return Complex(wplus.real), qn.I()*wplus.imag, Complex(wminus.real), qn.I()*wminus.imag

    def relative_angle(self, p:Particle):
        return  self.theta - p.v_0.phase

    def measure(self, p:Particle):
        """measure a particle through a gate, using floating point math

        weight -- complex-valued weight
        theta -- rotation angle
        sign -- plus or minus one
        """
        # following figure 4.4 in Good and Real
        cache_key = (self.swapping, p.__hash__())
        if self.measurement_cache.get(cache_key) is not None:
            return self.measurement_cache[cache_key]
        c1 = p.weight
        if self.cpair_m.__name__ in ('cpair0', 'cpair_alt'):
            if p.sign > 0:  # straightforward rotation by theta
                par_a, par_b, perp_a, perp_b = self.cpair_m(c1, self.theta)
            else:
                par_a, par_b, perp_a, perp_b = self.cpair_m(c1, self.twist)
        else:
            par_a, par_b, perp_a, perp_b = self.cpair_m(c1, twist=p.sign != 1)
        self.measurement_cache[cache_key] = (par_a, par_b, perp_a, perp_b)
        return (par_a, par_b, perp_a, perp_b)

    def port_value(self, port):
        if self.control == 'undefined':
            self.control = self._fetch_source('control')
            self.inputs['control'] = self.control
            if self.control:
                if type(self.control) == list:
                    self.control = Particle.merge(self.control)
                if enough(self.control.probability, 0):
                    self.swapping = 'swapped'
                else:
                    self.swapping = 'straight'
            else:
                self.swapping = 'straight'
        if port == 'control':
            return self.control
        else:
            if self.outputs[port][self.swapping] != 'undefined':
                return self.outputs[port][self.swapping]
            for switch in ['upper', 'lower']:
                if self.inputs[switch] == 'undefined':
                    self.inputs[switch] = self._fetch_source(switch)
                    print(f'{self.name} inputs[{switch}]={self.inputs[switch]}')
                    if self.inputs[switch] is not None:
                        s_in = self.inputs[switch]
                        if isinstance(s_in, Particle):
                            self.process_particle(s_in, switch)
                        elif isinstance(s_in, list):
                            for particle in s_in:
                                self.process_particle(particle, switch)
                        elif isinstance(s_in, dict):
                            for s_k in ['straight', 'swapped']:
                                particle = s_in[s_k]
                                self.process_particle(particle, switch)
            return self.outputs[port][self.swapping]

    def _fetch_source(self, port):
        port_source = self.sim.sources.get(f'{self.name}.{port}')
        print(f'{port_source=}')
        if port_source is None:
            return None
        else:
            parts = port_source.split('.')
            print(f'{parts=}')
            if len(parts) == 1:
                return [self.sim.particles[parts[0]]]
            else:
                source_gate, source_wire = parts
                return self.sim.gates[source_gate].port_value(source_wire)

    def process_particle(self, particle, switch):
        measurements = self.measure(particle)
        signs = [particle.sign, -particle.sign, particle.sign, -particle.sign]
        switches = [switch, switch, OTHER[switch], OTHER[switch]]
        for weight, sign, sw in zip(measurements, signs, switches):
            new_p = Particle(particle.name, weight, sign)
            print(f'{sw=}, {new_p=}')
            if self.outputs[sw][self.swapping] == 'undefined':
                self.outputs[sw][self.swapping] = []
            self.outputs[sw][self.swapping].append(new_p)


class DelayGate:
    def __init__(self, name, particle=None):
        self.name = name
        self.dgid = Gensym(f'dg_{name}')
        self.particle = particle