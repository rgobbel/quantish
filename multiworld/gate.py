import itertools
import logging
import random
from enum import StrEnum, auto
from collections import defaultdict
import cmath as cm

import multiworld.qnumber as qn
from multiworld.angle import Angle
from multiworld.particle import Particle
from multiworld.qnumber import qify
from multiworld.util import (Gensym, enough, select, flat_list, SEP, filter_weights, ZERO_THRESHOLD, sstr,
                           Sign, OTHER, WIRES, SWITCH_WIRES, INITIAL_WIRES, default_switches, default_wires)

log = logging.getLogger('multiworld')

class SourceType(StrEnum):
    weights = auto()
    outputs = auto()
    results = auto()

INITIAL_WIRES = lambda: {k: 'undefined' for k in ['control', 'upper', 'lower']}

class FredkinGate:
    def __init__(self, name:str, theta:float=0, start_step=0, sim=None, norm_output=None):
        self.name = name
        self.start_step = start_step
        self.inputs = default_wires()
        self.weights = default_wires()
        self.outputs = default_wires()
        self.swapping = None
        self.output_wire = None
        self.id = Gensym(name)
        self.sim = sim
        if type(self) is DelayGate:
            return
        self.measurement_cache = {}
        if norm_output is None:
            if sim is not None:
                self.norm_output = sim.normalize_output
            else:
                self.norm_output = False
        else:
            self.norm_output = norm_output
        if type(theta) is Angle:
            self.atheta = theta
            self.theta = theta.radians
        else:
            self.atheta = Angle(theta, unit='radians')
            self.theta = self.atheta.radians
        self.deg90 = cm.pi / 2
        self.twist = self.theta - self.deg90

        self.cos_theta = self.theta.cos
        self.sin_theta = self.theta.sin
        self.cos2_theta = self.cos_theta**2
        self.cos_sin_theta = 1j * self.cos_theta * self.sin_theta
        self.mcos_sin_theta = -1j * self.cos_theta * self.sin_theta
        self.sin2_theta = self.sin_theta**2
        self.wplusf = self.cos_theta * cm.exp(1j * self.theta)
        self.wminusf = self.sin_theta * cm.exp(1j * self.twist)

        self.cos_twist = self.twist.cos
        self.sin_twist = self.twist.sin
        self.cos2_twist = self.cos_twist**2
        self.cos_sin_twist = 1j * self.cos_twist * self.sin_twist
        self.mcos_sin_twist = -1j * self.cos_twist * self.sin_twist
        self.sin2_twist = self.sin_twist**2
        self.wplusf_twist = self.cos_twist * cm.exp(1j * self.twist)
        self.wminusf_twist = self.sin_twist * cm.exp(1j * self.twist)

        self.c2_factor = cm.exp(1j*self.theta) * self.theta.cos
        self.c3_factor = cm.exp(1j*self.twist) * self.theta.sin
        self.c2t_factor = cm.exp(1j*self.twist) * self.twist.cos
        self.c3t_factor = cm.exp(1j*self.twist) * self.twist.sin

    def report_type(self): ## TOTAL HACK
        return 'FredkinGate'

    def run(self):
        self.init_inputs()
        self.set_weights()

    def __repr__(self):
        return f'{self.name}({self.atheta.degrees:.2f}º)'

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

    def reset(self):
        self.swapping = None
        self.inputs = default_wires()
        self.weights = default_wires()
        self.outputs = default_wires()
        self.output_wire = None

    def cpairx(self, w, twist=False):
        if twist:
            c2 = w * self.c2t_factor
            c3 = w * self.c3t_factor
        else:
            c2 = w * self.c2_factor
            c3 = w * self.c3_factor
        c2a = c2.real
        c2b = c2.imag
        c3a = c3.real
        c3b = c3.imag
        return c2a, c2b, c3a, c3b

    def rot_theta(self, w, theta):
        """
            basic weight rotation with trig scaling
            This version computes the actual rotation in the complex plane
        """
        twist = theta - self.deg90
        wplus = w * theta.cos * cm.exp(1j * theta)
        wminus = w * theta.sin * cm.exp(1j * twist)
        return complex(wplus.real), 1j*wplus.imag, complex(wminus.real), 1j*wminus.imag

    # def cpair0(self, w, theta):
    #     """from AIM-1026a"""
    #     c2a = w * theta.cos**2
    #     c2b = w * 1j * theta.cos * theta.sin
    #     c3a = w * theta.sin**2
    #     c3b = w * -1j * theta.sin * theta.cos
    #     return c2a, c2b, c3a, c3b
    #
    # def cpair1(self, w, twist=False):
    #     """This follows the series of rotations described in AIM-1026a as well as Good and Real"""
    #     """basic weight rotation with trig scaling"""
    #     theta = self.twist if twist else self.theta
    #     twisted = theta - self.deg90
    #     wplus = w * theta.cos * cm.exp(1j * theta)
    #     wminus = w * theta.sin * cm.exp(1j * twisted)
    #     return Complex(wplus.real), 1j*wplus.imag, Complex(wminus.real), 1j*wminus.imag
    #
    # def cpair2(self, w, twist=False):
    #     theta = self.twist if twist else self.theta
    #     """This is from AIM-1026a, and is much much faster than doing the whole rotation"""
    #     c2a = w * theta.cos ** 2
    #     c2b = w * 1j * theta.cos * theta.sin
    #     c3a = w * theta.sin ** 2
    #     c3b = w * -1j * theta.cos * theta.sin
    #     return c2a, c2b, c3a, c3b
    #
    # def cpair3(self, w, twist=False):
    #     """This follows the series of rotations described in AIM-1026a as well as Good and Real"""
    #     """basic weight rotation with trig scaling"""
    #     if not twist:
    #         wplus = w * self.wplusf
    #         wminus = w * self.wminusf
    #     else:
    #         wplus = w * self.wplusf_twist
    #         wminus = w * self.wminusf_twist
    #     return Complex(wplus.real), 1j*wplus.imag, Complex(wminus.real), 1j*wminus.imag

    def relative_angle(self, p:Particle):
        return self.theta - p.v_0.phase

    def measure(self, p:Particle, merge_wires=False):
        """measure a particle through a gate

        weight -- complex-valued weight
        theta -- rotation angle
        sign -- plus or minus one
        """
        # cache_key = p #(self.swapping, p.__hash__())
        # if self.measurement_cache.get(cache_key) is not None:
        #     return self.measurement_cache[cache_key]
        c1 = p.weight
        # if self.cpair_m.__name__ in ('cpair0', 'cpair_alt'):
        #     if p.sign > 0:  # straightforward rotation by theta
        #         par_a, par_b, perp_a, perp_b = self.cpair_m(c1, self.theta)
        #     else:
        #         par_a, par_b, perp_a, perp_b = self.cpair_m(c1, self.twist)
        # else:
        par_a, par_b, perp_a, perp_b = self.cpair(c1, twist=p.sign != Sign.plus)
        if self.norm_output and p.probability > 0:
            par_a, par_b, perp_a, perp_b = [x / p.weight for x in (par_a, par_b, perp_a, perp_b)]
        # self.measurement_cache[cache_key] = (par_a, par_b, perp_a, perp_b)
        if merge_wires:
            return par_a+par_b, perp_a+perp_b
        return par_a, par_b, perp_a, perp_b

    def inputs_from(self, pcvs):
        for pcv in pcvs:
            pcv_gate = pcv.pcoord.position.endpoint.gate
            pcv_wire = pcv.pcoord.position.endpoint.port
            if pcv_gate == self.name:
                self.inputs[pcv_wire] += [pcv.particle]

    def set_weights(self):
        if self.swapping is None:
            self.weights['control'] = self.inputs['control']
            self.swapping = bool(self.weights['control'] and enough(
                Particle.merge(self.weights['control']).probability, ZERO_THRESHOLD))
        unswapped_weights = {'upper': [], 'lower': []}
        for switch in SWITCH_WIRES:
            split_outs = [switch, switch, OTHER[switch], OTHER[switch]]
            for particle in self.inputs[switch]:
                if particle is None: continue
                splits = self.measure(particle)
                signs = [particle.sign.value, -particle.sign.value, particle.sign.value, -particle.sign.value]
                measurements = [Particle(name=particle.name, weight=measurement, sign=sign,
                                         next_step=particle.next_step)
                                for measurement, sign in zip(splits, signs)]
                for p, sw in zip(measurements, split_outs):
                    unswapped_weights[sw].append(p)
        if self.swapping:
            self.weights['upper'] = unswapped_weights['lower']
            self.weights['lower'] = unswapped_weights['upper']
        else:
            self.weights['upper'] = unswapped_weights['upper']
            self.weights['lower'] = unswapped_weights['lower']
        log.debug(f'{self.swapping=}, {self.weights=}')

class DelayGate(FredkinGate):
    def __init__(self, name, start_step, sim=None):
        super().__init__(name)
        self.dgid = Gensym(f'dg_{name}')
        self.start_step = start_step
        self.sim = sim
        self.state = None

    def report_type(self): ## TOTAL HACK
        return 'DelayGate'

    def __repr__(self):
        def port_str(other_end):
            if not other_end:
                return ''
            other_end_parts = other_end.split(SEP)
            if len(other_end_parts) == 1:
                res_str = f'{other_end_parts[0]}'
            else:
                gate_name, port = other_end_parts
                gate = self.sim.gates[gate_name]
                if isinstance(gate, DelayGate):
                    res_str = f'{gate_name}'
                else:
                    res_str = f'{other_end}'
            return res_str
        source = self.sim.sources.get(f'{self.name}{SEP}control')
        sink = self.sim.links.get(f'{self.name}{SEP}control')
        s_source = port_str(source)
        s_sink = port_str(sink)
        return f'{self.name}({s_source}>{s_sink})'

    def reset(self):
        self.state = None
        super().reset()

    @property
    def theta(self):
        return qify(0)

    def init_inputs(self):
        self.inputs = default_wires()


    def set_weights(self):
        self.weights = self.inputs

    def port_weights(self, _):
        return self.weights

    def port_outputs(self, _):
        return self.outputs

    def measure(self, p: Particle, **kwargs):
        return p
