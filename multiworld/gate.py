import logging
import cmath as cm
from collections import defaultdict

import multiworld.qnumber as qn
from multiworld.angle import Angle
from multiworld.particle import Particle
from multiworld.qnumber import qify, Complex, Real
from multiworld.util import Gensym, enough, SEP, Sign, OTHER, SWITCH_WIRES, default_wires, default_switches, \
    switch_splits

log = logging.getLogger('multiworld')

class FredkinGate:
    def __init__(self, name:str, theta:Real=0):
        self.name = name
        self.theta = qify(theta)
        self.inputs = default_wires()
        self.weights = default_wires()
        self.swapping = None
        self.output_wire = None
        self.id = Gensym(name)
        # self.sim = sim
        self.discards = defaultdict(list)
        self.input_particles = set()
        if type(self) is DelayGate:
            return
        self.measurement_cache = {}
        # if norm_output is None:
        #     if sim is not None:
        #         self.norm_output = sim.normalize_output
        #     else:
        #         self.norm_output = False
        # else:
        #     self.norm_output = norm_output
        if type(self.theta) is Angle:
            self.atheta = self.theta
            self.theta = self.theta.radians
        else:
            self.atheta = Angle(self.theta, unit='radians')
            self.theta = self.atheta.radians
        self.twist = self.theta - qn.PI/2

        self.cos_theta = self.theta.cos
        self.sin_theta = self.theta.sin
        self.cos2_theta = Complex(self.cos_theta**2)
        self.cos_sin_theta = self.cos_theta * self.sin_theta * qn.I
        self.mcos_sin_theta = self.cos_theta * self.sin_theta * -qn.I
        self.sin2_theta = Complex(self.sin_theta**2)
        self.wplusf = self.cos_theta * (qn.I * self.theta).exp
        self.wminusf = self.sin_theta * (qn.I * self.twist).exp

        self.cos_twist = self.twist.cos
        self.sin_twist = self.twist.sin
        self.cos2_twist = Complex(self.cos_twist**2)
        self.cos_sin_twist = qn.I * self.cos_twist * self.sin_twist
        self.mcos_sin_twist = -qn.I * self.cos_twist * self.sin_twist
        self.sin2_twist = Complex(self.sin_twist**2)
        self.wplusf_twist = self.cos_twist * (qn.I * self.twist).exp
        self.wminusf_twist = self.sin_twist * (qn.I * self.twist).exp

    def report_type(self): ## HACK TO AVOID A DEPENDENCY LOOP
        return 'FredkinGate'

    def run(self):
        self.init_inputs()
        self.set_weights()

    def __repr__(self):
        return f'{self.name}({self.atheta.degrees:.2f}º)'

    def cpair(self, w:Complex, twist=False):
        """
        From AIM-1026a
        Values are precomputed for speed
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

    def reset(self):
        self.swapping = None
        self.inputs = default_wires()
        self.weights = default_wires()
        self.outputs = default_wires()
        self.output_wire = None

    def rot_theta(self, w:Complex, theta:Real):
        """
            basic weight rotation with scaling
            This version computes rotation in the complex plane
            in the most straightforward but not fastest way
        """
        twist = theta - qn.PI/2
        wplus = w * theta.cos * (qn.I * theta).exp
        wminus = w * theta.sin * (qn.I * twist).exp
        return Complex(wplus.real), qn.I*wplus.imag, Complex(wminus.real), qn.I*wminus.imag

    def relative_angle(self, p:Particle):
        return self.theta - p.v_0.phase

    def measure(self, p:Particle, merge_wires=False):
        """measure a particle through a gate

        weight -- complex-valued weight
        theta -- rotation angle
        sign -- plus or minus one
        """
        cache_key = p #(self.swapping, p.__hash__())
        if self.measurement_cache.get(cache_key) is not None:
            return self.measurement_cache[cache_key]
        c1 = p.weight
        par_a, par_b, perp_a, perp_b = self.cpair(c1, twist=p.sign == Sign.minus)
        # if self.norm_output and p.probability > 0:
        #     par_a, par_b, perp_a, perp_b = [x / p.weight for x in (par_a, par_b, perp_a, perp_b)]
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
            self.swapping = False
            self.weights['control'] = self.inputs['control']
            if bool(self.weights['control']):
                merged = Particle.merge(self.weights['control'], combine_signs=True)[0]
                if enough(abs(merged.weight), qn.ZERO_THRESHOLD):
                    self.swapping = True
            # self.swapping = bool(self.weights['control'] and enough(
            #     Particle.merge(self.weights['control']).probability, qn.ZERO_THRESHOLD))
        unswapped_weights = default_switches()
        for switch in SWITCH_WIRES:
            split_outs = switch_splits(switch)
            for particle in self.inputs[switch]:
                if particle is None: continue
                splits = self.measure(particle)
                signs = [particle.sign.value, -particle.sign.value, particle.sign.value, -particle.sign.value]
                labels = ['c2a', 'c2b', 'c3a', 'c3b']
                measurements = [Particle(name=particle.name, weight=measurement, sign=sign,
                                         next_step=particle.next_step, active_gates=particle.active_gates,
                                         trace=particle.trace+[f'{label}:{self.name}{SEP}{switch}',],
                                         splits=particle.splits+[f'{self.name}{SEP}{switch}:{label}',])
                                for measurement, sign, label in zip(splits, signs, labels)]
                for p, sw in zip(measurements, split_outs):
                    if enough(abs(p.weight), qn.ZERO_THRESHOLD):
                        unswapped_weights[sw].append(p)
                        # particle.family_tree.add_edge(particle, p)
                    else:
                        self.discards[p.pkey] += [p]
        # for wire in SWITCH_WIRES:
        #     for weight in unswapped_weights[wire]:
        #         if (not unswapped_weights[wire]) or (not enough(sum([abs(p.weight) for p in unswapped_weights[wire]]), qn.ZERO_THRESHOLD)):
        #         unswapped_weights[wire] = []
        if self.swapping:
            self.weights['upper'], self.weights['lower'] = unswapped_weights['lower'], unswapped_weights['upper']
        else:
            for wire in SWITCH_WIRES:
                self.weights[wire] = unswapped_weights[wire]
        # log.debug(f'      {self}.weights: {self.swapping=}, {self.weights=}')

class DelayGate(FredkinGate):
    def __init__(self, name, source:str='', sink:str=''):#, start_step):#, sim=None):
        super().__init__(name)
        self.dgid = Gensym(f'dg_{name}')
        # self.start_step = start_step
        # self.sim = sim
        self.source = source
        self.self.sink = ''
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
        source = self.source
        sink = self.sink
        s_source = port_str(source)
        s_sink = port_str(sink)
        return f'{self.name}({s_source}>{s_sink})'

    def reset(self):
        self.state = None
        super().reset()

    @property
    def theta(self):
        return qify(0)
    @theta.setter
    def theta(self, value):
        pass

    def init_inputs(self):
        self.inputs = default_wires()

    def set_weights(self):
        self.weights = self.inputs

    def measure(self, p: Particle, **kwargs):
        return p
