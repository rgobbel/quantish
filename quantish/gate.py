import logging
import random
from enum import StrEnum, auto
from quantish.qnumber import qify, Complex, Real, ZERO, PI
import quantish.qnumber as qn
from quantish.angle import Angle
from quantish.particle import Particle
from quantish.config_space import default_switches, default_wires, OTHER, WIRES, SWITCH_WIRES, WorldState
from quantish.util import Gensym, enough, select, astr, flat_list, SEP, filter_weights, ZERO_THRESHOLD

log = logging.getLogger('quantish')

class SourceType(StrEnum):
    weights = auto()
    output = auto()
    results = auto()

INITIAL_WIRES = lambda: {k: 'undefined' for k in ['control', 'upper', 'lower']}

class FredkinGate:
    def __init__(self, name:str, theta:Real=ZERO, sim=None, norm_output=None):
        self.name = name
        self.control = 'undefined'
        self.control_weight = 'undefined'
        self.input = INITIAL_WIRES()
        self.weights = INITIAL_WIRES()
        self.output = INITIAL_WIRES()
        self.output_wire = None
        self.id = Gensym(name)
        self.sim = sim
        self._selector = None
        if type(self) is DelayGate:
            return
        self.measurement_cache = {}
        self.swapping = None
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

        # if alternative_measure:
        #     if isinstance(alternative_measure, str):
        #         meth = getattr(self.__class__, alternative_measure)
        #     else:
        #         meth = getattr(self.__class__, 'cpair_alt')
        # else:
        #     meth = getattr(self.__class__, 'cpair')
        # setattr(self.__class__, 'cpair_m', meth)

    def run(self):
        self.set_input()
        self.set_weights()
        self.set_output()

    # def __str__(self):
    #     return f'{self.name}({self.atheta.degrees:.1f}º)'

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
        self.control = 'undefined'
        self.control_weight = 'undefined'
        self.input = INITIAL_WIRES()
        self.weights = INITIAL_WIRES()
        self.output = INITIAL_WIRES()
        self.output_wire = None


    # def cpair0(self, w, theta):
    #     """from AIM-1026a"""
    #     c2a = w * theta.cos**2
    #     c2b = w * qn.I() * theta.cos * theta.sin
    #     c3a = w * theta.sin**2
    #     c3b = w * -qn.I() * theta.sin * theta.cos
    #     return c2a, c2b, c3a, c3b

    # def cpair_alt(self, w, theta):
    #     """
    #         basic weight rotation with trig scaling
    #         This version computes the actual rotation in the complex plane
    #     """
    #     twist = theta - self.deg90
    #     wplus = w * theta.cos * (qn.I() * theta).exp
    #     wminus = w * theta.sin * (qn.I() * twist).exp
    #     return Complex(wplus.real), qn.I()*wplus.imag, Complex(wminus.real), qn.I()*wminus.imag

    # def cpair1(self, w, twist=False):
    #     """This follows the series of rotations described in AIM-1026a as well as Good and Real"""
    #     """basic weight rotation with trig scaling"""
    #     theta = self.twist if twist else self.theta
    #     twisted = theta - self.deg90
    #     wplus = w * theta.cos * (qn.I() * theta).exp
    #     wminus = w * theta.sin * (qn.I() * twisted).exp
    #     return Complex(wplus.real), qn.I()*wplus.imag, Complex(wminus.real), qn.I()*wminus.imag

    # def cpair2(self, w, twist=False):
    #     theta = self.twist if twist else self.theta
    #     """This is from AIM-1026a, and is much much faster than doing the whole rotation"""
    #     c2a = w * theta.cos ** 2
    #     c2b = w * qn.I() * theta.cos * theta.sin
    #     c3a = w * theta.sin ** 2
    #     c3b = w * -qn.I() * theta.cos * theta.sin
    #     return c2a, c2b, c3a, c3b

    # def cpair3(self, w, twist=False):
    #     """This follows the series of rotations described in AIM-1026a as well as Good and Real"""
    #     """basic weight rotation with trig scaling"""
    #     if not twist:
    #         wplus = w * self.wplusf
    #         wminus = w * self.wminusf
    #     else:
    #         wplus = w * self.wplusf_twist
    #         wminus = w * self.wminusf_twist
    #     return Complex(wplus.real), qn.I()*wplus.imag, Complex(wminus.real), qn.I()*wminus.imag

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
        par_a, par_b, perp_a, perp_b = self.cpair(c1, twist=p.sign != 1)
        if self.norm_output and p.probability > 0:
            par_a, par_b, perp_a, perp_b = [x / p.weight for x in (par_a, par_b, perp_a, perp_b)]
        # self.measurement_cache[cache_key] = (par_a, par_b, perp_a, perp_b)
        if merge_wires:
            return par_a+par_b, perp_a+perp_b
        return par_a, par_b, perp_a, perp_b

    @property
    def selector(self):
        return self._selector
    @selector.setter
    def selector(self, value):
        self._selector = value

    def process_particle(self, particle):
        measurements = self.measure(particle)
        signs = [particle.sign, -particle.sign, particle.sign, -particle.sign]
        results = [Particle(particle.name, measurement, sign) for measurement, sign in zip(measurements, signs)]
        return results

    def _fetch_source(self, port, source_type:SourceType='output'):
        # source is either a particle or gate and wire (or None)
        port_source = self.sim.sources.get(f'{self.name}{SEP}{port}')
        # log.debug(f'{port_source=}')
        if port_source is None:
            return None
        else:
            parts = port_source.split('.')
            # log.debug(f'{parts=}')
            if len(parts) == 1:
                return [self.sim.particles[parts[0]]]
            else:
                source_gate, source_wire = parts
                result = self.sim.gates[source_gate].port_result(source_wire)
                log.debug(f'{self.name}:_fetch_source({port_source})={result}')
                if isinstance(result, Particle) and result.weight == 0:
                    return None
                return result

    def set_control(self):
        source_str = self.sim.sources.get(f'{self.name}{SEP}control')
        if source_str is None:
            self.control_weight = None
            self.control = None
        else:
            source_parts = source_str.split(SEP)
            if len(source_parts) == 1:
                source_value = self.sim.particles[source_str]
                control_weight = source_value
            else:
                source_gate, source_wire = source_parts
                source_value = self.sim.gates[source_gate].port_result(source_wire)
                control_weight = self.sim.gates[source_gate].port_weights(source_wire)
            if isinstance(source_value, Particle) and not source_value.weight:
                self.control = None
            else:
                self.control = source_value
            if self.sim.always_forward_weights:
                self.control_weight = control_weight
            else:
                self.control_weight = self.control
        self.input['control'] = self.control
        self.output['control'] = self.control
        self.weights['control'] = self.control_weight
        if not self.control:
            self.swapping = False
        else:
            pc = Particle.merge(flat_list(self.control))
            if pc:
                if self.sim.control_threshold == -1:
                    threshold = random.random()
                else:
                    if type(self.sim.control_threshold) is Real:
                        threshold = self.sim.control_threshold
                    else:
                        threshold = self.sim.control_threshold()
                swap_enough = enough(pc.probability, threshold)
            else:
                swap_enough = False
            self.swapping = pc and swap_enough
        assert not(self.control is None and self.swapping)

    def port_weights(self, port):
        if self.control == 'undefined': self.set_control()
        if port == 'control':
            return self.control_weight
        # else:
        if self.weights[port] != 'undefined':
            return self.weights[port]

        assert self.control != 'undefined'
        unswapped_weights = {'upper': [], 'lower': []}
        switch_sources = default_switches()
        for wire in SWITCH_WIRES:
            switch_sources[wire] = self._fetch_source(wire, 'weights')
        for switch in SWITCH_WIRES:
            split_outs = [switch, switch, OTHER[switch], OTHER[switch]]
            weight_source = switch_sources[switch]
            log.debug(f'{self.name} weight_source[{switch}]={weight_source}')
            if weight_source is not None:
                if isinstance(weight_source, Particle):
                    measurements = self.process_particle(weight_source)
                    if self.sim.merge_before_forward:
                        measurements = [Particle.merge(measurements[:2]), Particle.merge(measurements[2:])]
                        split_outs = [switch, OTHER[switch]]
                    for p, sw in zip(measurements, split_outs):
                        unswapped_weights[sw].append(p)
                elif isinstance(weight_source, list):
                    if self.sim.merge_before_measure:
                        weight_source = [Particle.merge(weight_source)]
                    for particle in weight_source:
                        measurements = self.process_particle(particle)
                        if self.sim.merge_before_forward:
                            measurements = [Particle.merge(measurements[:2]), Particle.merge(measurements[2:])]
                            split_outs = [switch, OTHER[switch]]
                        for p, sw in zip(measurements, split_outs):
                            unswapped_weights[sw].append(p)
        self.weights['upper'] = filter_weights(unswapped_weights['upper'])
        self.weights['lower'] = filter_weights(unswapped_weights['lower'])
        result = self.weights[port]
        log.debug(f'{self.swapping=}, {self.weights=}')
        return result

    def port_output(self, port):
        if port == 'control':
            return self.control
        if self.output[port] == 'undefined':
            assert self.swapping is not None
            # if self.sim.selector_value == -2:
            #     if self.theta.cos**2 < self.sim.selector():
            #         chosen_input = 'lower'
            #     else:
            #         chosen_input = 'upper'
            # else:
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
                for wire in SWITCH_WIRES:
                    self.output[wire] = None
                return None
            candidate_weights = [p[0].probability for p in candidates]
            if self.selector is not None:
                selector = self.selector
                chosen = candidates[select(candidate_weights, selector)]
            else:
                chosen = random.choices(candidates, candidate_weights)[0]
            chosen_input = chosen[1]
            if self.swapping:
                self.output[OTHER[chosen_input]] = filter_weights(self.weights[chosen_input])
                self.output[chosen_input] = filter_weights(self.weights[OTHER[chosen_input]])
                self.output_wire = OTHER[chosen_input]
            else:
                self.output[chosen_input] = filter_weights(self.weights[chosen_input])
                self.output[OTHER[chosen_input]] = filter_weights(self.weights[OTHER[chosen_input]])
                self.output_wire = chosen_input
        return self.output[port]

    def port_result(self, port):
        if port == 'control':
            if self.control == 'undefined': self.set_control()
            return self.control
        if port != self.output_wire or not self.output[port]:
            return None
        merged =  Particle.merge(self.output[port])
        if not enough(merged.probability, ZERO_THRESHOLD):
            return None
        else:
            return self.output[port]

    def set_input(self):
        if self.control == 'undefined': self.set_control()
        for wire in SWITCH_WIRES:
            self.input[wire] = self._fetch_source(wire, 'results')

    def set_weights(self):
        for port in WIRES:
            self.port_weights(port)

    def set_output(self):
        for wire in WIRES:
            self.port_output(wire)

    @property
    def results(self):
        return {wire: self.port_result(wire) for wire in WIRES}


class DelayGate(FredkinGate):
    def __init__(self, name, sim=None):
        super().__init__(name)
        self.name = name
        self.dgid = Gensym(f'dg_{name}')
        self.sim = sim
        self.state = None
        self.output_wire = 'control'

    def __repr__(self):
        source = self.sim.sources.get(f'{self.name}{SEP}input')
        s_source = f'{source}->' if source else ''
        sink = self.sim.links.get(f'{self.name}{SEP}output')
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
    def output(self):
        return {k: self.state for k in WIRES + ('output',)}
    @output.setter
    def output(self, value):
        self.state = value

    @property
    def results(self):
        if not self.state:
            merged = None
        else:
            merged =  Particle.merge(self.state)
            if not enough(merged.probability, ZERO_THRESHOLD):
                merged = None
        return {k: merged for k in ['output', 'control', 'upper', 'lower']}

    @property
    def theta(self):
        return qify(0)

    def _fetch_source(self, port, source_type:SourceType='output'):
        source = self.sim.sources[f'{self.name}{SEP}input']
        source_gate, source_wire = source.split(SEP)
        result = getattr(self.sim.gates[source_gate], source_type)[source_wire]
        return result

    def set_input(self):
        self.state = self.input = self.weights = self.output = self._fetch_source('input')

    def set_weights(self):
        self.weights = self._fetch_source('weights')

    def set_output(self):
        self.output = self._fetch_source('output')

    def port_input(self, _):
        return self.input

    def port_weights(self, _):
        return self.weights

    def port_output(self, _):
        return self.output

    def measure(self, p: Particle, **kwargs):
        return p
