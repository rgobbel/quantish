import logging
import random
from collections import defaultdict

import quantish.qnumber as qn
from quantish.angle import Angle
from quantish.config_space import default_switches, OTHER, WIRES, SWITCH_WIRES, default_wires, ConfigSpacePoint
from quantish.particle import Particle
from quantish.qnumber import qify, Real, ZERO, Complex
from quantish.util import Gensym, enough, select, flat_list, SEP, filter_weights, ZERO_THRESHOLD, sstr

log = logging.getLogger('quantish')

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
        # if type(self) is DelayGate:
        #     return
        self.measurement_cache = {}
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
        self.cos_sin_theta = self.cos_theta * self.sin_theta * qn.PI_fn()
        self.mcos_sin_theta = self.cos_theta * self.sin_theta * -qn.PI_fn()
        self.sin2_theta = Complex(self.sin_theta**2)
        self.wplusf = self.cos_theta * (qn.PI_fn() * self.theta).exp
        self.wminusf = self.sin_theta * (qn.PI_fn() * self.twist).exp

        self.cos_twist = self.twist.cos
        self.sin_twist = self.twist.sin
        self.cos2_twist = Complex(self.cos_twist**2)
        self.cos_sin_twist = qn.PI_fn() * self.cos_twist * self.sin_twist
        self.mcos_sin_twist = -qn.PI_fn() * self.cos_twist * self.sin_twist
        self.sin2_twist = Complex(self.sin_twist**2)
        self.wplusf_twist = self.cos_twist * (qn.PI_fn() * self.twist).exp
        self.wminusf_twist = self.sin_twist * (qn.PI_fn() * self.twist).exp

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
        twist = theta - qn.PI_fn()/2
        wplus = w * theta.cos * (qn.PI_fn() * theta).exp
        wminus = w * theta.sin * (qn.PI_fn() * twist).exp
        return Complex(wplus.real), qn.PI_fn()*wplus.imag, Complex(wminus.real), qn.PI_fn()*wminus.imag

    def relative_angle(self, p:ConfigSpacePoint):
        return self.theta - p.weight.phase

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
        par_a, par_b, perp_a, perp_b = self.cpair(c1, twist=p.sign != 1)
        if self.norm_output and p.probability > 0:
            par_a, par_b, perp_a, perp_b = [x / p.weight for x in (par_a, par_b, perp_a, perp_b)]
        # self.measurement_cache[cache_key] = (par_a, par_b, perp_a, perp_b)
        if merge_wires:
            return par_a+par_b, perp_a+perp_b
        return par_a, par_b, perp_a, perp_b

    @property
    def swap_threshold(self):
        val = self._swap_threshold()
        self.last_swap_threshold = val
        return self._swap_threshold
    @swap_threshold.setter
    def swap_threshold(self, value):
        self._swap_threshold = value
        self.last_swap_threshold = None

    @property
    def forwarding_threshold(self):
        val = self._forwarding_threshold()
        self.last_forwarding_threshold = val
        return self._forwarding_threshold
    @forwarding_threshold.setter
    def forwarding_threshold(self, value):
        self._forwarding_threshold = value
        self.last_forwarding_threshold = None

    def process_particle(self, particle):
        measurements = self.measure(particle)
        signs = [particle.sign, -particle.sign, particle.sign, -particle.sign]
        results = [Particle(particle.name, measurement, sign) for measurement, sign in zip(measurements, signs)]
        return results

    def set_control(self):
        source_output = []
        source_str = self.sim.sources.get(f'{self.name}{SEP}control')
        source_is_output = False
        swap_threshold = self.swap_threshold()
        if not source_str:
            self.swapping = False
        else:
            source_parts = source_str.split(SEP)
            if len(source_parts) == 1: # it's a particle
                source_output = [self.sim.particles[source_str]]
                # source_weight = source_output
                source_is_output = True
            else: # it's a gate wire
                source_gate, source_wire = source_parts
                source_output = self.sim.gates[source_gate].port_outputs(source_wire)
                if source_wire == 'control':
                    source_is_output = True
                else:
                    source_is_output = self.sim.gates[source_gate].output_wire == source_wire
            # if isinstance(source_output, Particle) and not enough(source_output.weight, swap_threshold):
            #     self.swapping = False
        merged_source = Particle.merge(source_output)
        if not enough(merged_source.probability, ZERO_THRESHOLD):
            source_output = []
            self.inputs['control'] = []
            self.weights['control'] = []
            self.swapping = False
            self.outputs['control'] = []
        else:
            self.inputs['control'] = source_output
            self.weights['control'] = source_output
        if source_output:
            swap_enough = enough(merged_source.probability, swap_threshold)
            if self.sim.swap_if_selected and swap_enough and source_is_output:
                self.swapping = True
            else:
                    self.swapping = swap_enough
            swapstr = f'{"swapping" if self.swapping else "not swapping"}'
            log.info(f'GATE {self} swap_threshold={swap_threshold:.2f}, {swapstr}')
            if self.sim.always_forward_control_weights:
                self.outputs['control'] = self.weights['control']
            elif self.swapping: # if it was present enough to cause a swap, it's present enough to pass on
                self.outputs['control'] = self.weights['control']
            else:
                self.outputs['control'] = []
        assert isinstance(self.swapping, bool)

    def _fetch_source(self, port, source_type='outputs'):
        # source is either a particle or gate and wire (or [])
        port_source = self.sim.sources.get(f'{self.name}{SEP}{port}')
        if not port_source:
            return []
        else:
            parts = port_source.split('.')
            if len(parts) == 1:
                return [self.sim.particles[parts[0]]]
            else:
                source_gate, source_wire = parts
                if source_type == 'weights':
                    result = self.sim.gates[source_gate].port_weights(source_wire)
                else:
                    result = self.sim.gates[source_gate].port_outputs(source_wire)
                log.debug(f'{self.name}:_fetch_source({port_source}, {source_type})={result}')
                return result

    def setup_inputs(self):
        if self.swapping is None: self.set_control()
        for wire in SWITCH_WIRES:
            self.inputs[wire] = self._fetch_source(wire)

    def setup_weights(self):
        if self.inputs['control'] == 'undefined': self.set_control()
        assert self.swapping is not None
        if self.weights['upper'] == 'undefined' or self.weights['lower'] == 'undefined':
            unswapped_weights = {'upper': [], 'lower': []}
            switch_sources = default_switches()
            if self.weights['upper'] == 'undefined' or self.weights['lower'] == 'undefined':
                for switch in SWITCH_WIRES:
                    switch_sources[switch] = self._fetch_source(switch)
                    split_outs = [switch, switch, OTHER[switch], OTHER[switch]]
                    weight_source = switch_sources[switch]
                    log.debug(f'{self.name} weight_source[{switch}]={weight_source}')
                    if weight_source:
                        if isinstance(weight_source, Particle):
                            measurements = self.process_particle(weight_source)
                            # if self.sim.merge_before_forward:
                            #     measurements = [Particle.merge(measurements[:2]), Particle.merge(measurements[2:])]
                            #     split_outs = [switch, OTHER[switch]]
                            for p, sw in zip(measurements, split_outs):
                                unswapped_weights[sw].append(p)
                        elif isinstance(weight_source, list):
                            for particle in weight_source:
                                if not particle: continue
                                measurements = self.process_particle(particle)
                                # if self.sim.merge_before_forward:
                                #     measurements = [Particle.merge(measurements[:2]), Particle.merge(measurements[2:])]
                                #     split_outs = [switch, OTHER[switch]]
                                for p, sw in zip(measurements, split_outs):
                                    unswapped_weights[sw].append(p)
                if self.swapping:
                    self.weights['upper'] = filter_weights(unswapped_weights['lower'])
                    self.weights['lower'] = filter_weights(unswapped_weights['upper'])
                else:
                    self.weights['upper'] = filter_weights(unswapped_weights['upper'])
                    self.weights['lower'] = filter_weights(unswapped_weights['lower'])

    def port_weights(self, port):
        if self.swapping is None: self.set_control()
        if port == 'control':
            # if self.sim.always_forward_control_weights:
            #     return self.weights['control']
            if self.swapping:
                return self.weights['control']
            else:
                return []
        if self.weights[port] == 'undefined':
            self.setup_weights()
        assert self.weights[port] != 'undefined'
        return self.weights[port]

    def port_outputs(self, port):
        if self.outputs[port] == 'undefined':
            self.setup_outputs()
        assert self.swapping is not None
        return self.outputs[port]

    def setup_outputs(self):
        if self.swapping is None: self.set_control()
        for wire in SWITCH_WIRES:
            self.outputs[wire] = self.weights[wire]
        # calculate output_wire. only turn off other output if always_forward not set
        if self.weights['upper']:
            upper = [[Particle.merge(self.weights['upper']), 'upper']]
        else:
            upper = []
        if self.weights['lower']:
            lower = [[Particle.merge(self.weights['lower']), 'lower']]
        else:
            lower = []
        candidates = upper + lower
        if len(candidates) == 0:
            if not self.sim.always_forward_switch_weights:
                for wire in SWITCH_WIRES:
                    self.outputs[wire] = []
        else:
            candidate_weights = [p[0].probability for p in candidates]
            threshold = random.random()#self.forwarding_threshold()
            chosen = candidates[select(candidate_weights, threshold)]
            self.output_wire = chosen[1]
            if self.norm_output:
                output_sum = Particle.merge(self.outputs['upper'] + self.outputs['lower']).weight
                for wire in SWITCH_WIRES:
                    for p in self.outputs[wire]:
                        p.weight = p.weight / output_sum
            if not self.sim.always_forward_switch_weights:
                self.outputs[OTHER[self.output_wire]] = []
            log.info(f'GATE {self}, forwarding_threshold={threshold:.2f}, output_wire={self.output_wire}')


    @property
    def results(self):
        result = self.outputs
        if self.output_wire is not None and not self.sim.always_forward_switch_weights:
            result[OTHER[self.output_wire]] = []
        return result


class DelayGate(FredkinGate):
    def __init__(self, name, sim=None):
        super().__init__(name)
        self.dgid = Gensym(f'dg_{name}')
        self.state = None
        self.output_wire = 'control'

    def report_type(self): ## TOTAL HACK
        return 'DelayGate'

    def __repr__(self):
        source = self.sim.sources.get(f'{self.name}{SEP}inputs')
        s_source = f'{source}->' if source else ''
        sink = self.sim.links.get(f'{self.name}{SEP}outputs')
        s_sink = f'->{sink}' if sink else ''
        return f'{s_source}{self.name}{s_sink}'

    def reset(self):
        self.state = None

    @property
    def input(self):
        return {k: self.state for k in WIRES}
    @input.setter
    def input(self, value):
        self.state = value

    @property
    def weights(self):
        return {k: self.state for k in WIRES}
    @weights.setter
    def weights(self, value):
        self.state = value

    @property
    def outputs(self):
        return {k: self.state for k in WIRES + ('outputs',)}
    @outputs.setter
    def outputs(self, value):
        self.state = value

    @property
    def results(self):
        if not self.state:
            merged = None
        else:
            merged =  Particle.merge(self.state)
            if not enough(merged.probability, ZERO_THRESHOLD):
                merged = None
        return {k: merged for k in ['outputs', 'control', 'upper', 'lower']}

    @property
    def theta(self):
        return qify(0)

    def _fetch_source(self, port, source_type='outputs'):
        source = self.sim.sources[f'{self.name}{SEP}inputs']
        source_gate, source_wire = source.split(SEP)
        result = getattr(self.sim.gates[source_gate], source_type, {}).get(source_wire, [])
        return result

    def setup_inputs(self):
        self.state = self.inputs = self.weights = self.outputs= self._fetch_source('inputs')

    def setup_weights(self):
        self.weights = self._fetch_source('weights')

    def setup_outputs(self):
        self.outputs = self._fetch_source('outputs')

    def port_inputs(self, _):
        return self.inputs

    def port_weights(self, _):
        return self.weights

    def port_outputs(self, _):
        return self.outputs

    def measure(self, p: Particle, **kwargs):
        return p
