import logging
import random
from collections import defaultdict
from enum import StrEnum, auto
from quantish.qnumber import qify, Complex, Real, ZERO, PI
import quantish.qnumber as qn
from quantish.angle import Angle
from quantish.particle import Particle
from quantish.config_space import default_switches, default_wires, OTHER, WIRES, SWITCH_WIRES, WorldState
from quantish.util import Gensym, enough, select, astr, flat_list, SEP
import numpy as np
from abc import ABC

log = logging.getLogger('quantish')

class ST(StrEnum):
    weights = auto()
    output = auto()

class Gate(ABC):
    def __init__(self):
        self.control = 'undefined'
        self.input = {'control': 'undefined', 'upper': 'undefined', 'lower': 'undefined'}
        self.weights = {'upper': 'undefined', 'lower': 'undefined'}
        self.output = {'control': 'undefined', 'upper': 'undefined', 'lower': 'undefined'}
        self.output_wire = None

    def set_input(self):
        pass

    def set_weights(self):
        pass

    def set_output(self):
        pass

class FredkinGate(Gate):
    def __init__(self, name:str, theta:Real=ZERO, sim=None, norm_output=None):
        self.name = name
        self.id = Gensym(name)
        self.sim = sim
        self.measurement_cache = {}
        self.swapping = None
        if norm_output is None:
            if sim is not None:
                self.norm_output = sim.normalize_output
            else:
                self.norm_output = False
        else:
            self.norm_output = norm_output
        self.control = 'undefined'
        self.input = {'control': 'undefined', 'upper': 'undefined', 'lower': 'undefined'}
        self.weights = {'upper': 'undefined', 'lower': 'undefined'}
        self.output = {'control': 'undefined', 'upper': 'undefined', 'lower': 'undefined'}
        self.output_wire = None
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

    def __str__(self):
        return f'{self.name}({self.atheta.degrees:.1f}º)'

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
        self.input = {'control': 'undefined', 'upper': 'undefined', 'lower': 'undefined'}
        self.weights = {'upper': 'undefined', 'lower': 'undefined'}
        self.weights = {'upper': 'undefined', 'lower': 'undefined'}
        self.output = {'control': 'undefined', 'upper': 'undefined', 'lower': 'undefined'}
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
        if self.norm_output and p.weight_probability > 0:
            par_a, par_b, perp_a, perp_b = [x / p.weight for x in (par_a, par_b, perp_a, perp_b)]
        # self.measurement_cache[cache_key] = (par_a, par_b, perp_a, perp_b)
        if merge_wires:
            return par_a+par_b, perp_a+perp_b
        return par_a, par_b, perp_a, perp_b

    def port_weights(self, port):
        # if self.control == 'undefined':
        self.control = self.control_source()
        self.input['control'] = self.control
        self.output['control'] = self.control
        if port == 'control':
            return self.control
        else:
            if self.weights[port] != 'undefined':
                return self.weights[port]

            assert self.control != 'undefined'
            unswapped_weights = {'upper': [], 'lower': []}
            # for switch in SWITCH_WIRES:
            #     self.weights[switch] = self._fetch_source(switch, 'weights')
            for switch in SWITCH_WIRES:
                split_outs = [switch, switch, OTHER[switch], OTHER[switch]]
                weight_source = self.input[switch]
                log.debug(f'{self.name} weight_source[{switch}]={weight_source}')
                if weight_source is not None:
                    # print(f'{type(weight_source)=}, {weight_source=}')
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
            # assert self.swapping is not None
            # if self.swapping:
            #     self.weights['upper'] = unswapped_weights['lower']
            #     self.weights['lower'] = unswapped_weights['upper']
            # else:
            self.weights['upper'] = unswapped_weights['upper']
            self.weights['lower'] = unswapped_weights['lower']
            for wire in SWITCH_WIRES:
                if self.weights[wire]:
                    if self.sim.merge_before_measure:
                        self.weights[wire] = [Particle.merge(self.weights[wire])]
                    else:
                        self.weights[wire] = self.weights[wire]
            result = self.weights[port]
            # print(f'{self.swapping=}, {self.weights=}')
            return result

    def port_output(self, port):
        # if self.output[port] == 'undefined':
        #     port_source = self.sim.sources.get(f'{self.name}{SEP}{port}')
        #     if port_source is None:
        #         self.output[port] = None
        #         return None
        #     parts = port_source.split('.')
        #     if len(parts) == 1:
        #         self.output[port] = self.sim.particles[port_source]
        #     elif parts[1] == 'control':
        #         self.output['control'] = self._fetch_source(port)
        #     else:
        #         self.output[port] = self._fetch_source(port)
        #     # if port == 'control':
        #     #     self.output[port] = self._fetch_source(port, 'output')
        #     # else:
        #     #     self.output[port] = self._fetch_source(port, 'output')
        if port == 'control':
            return self.control
        for switch in SWITCH_WIRES:
            if self.swapping:
                self.output[switch] = self.input[OTHER[switch]]
            else:
                self.output[switch] = self.input[switch]
        # if self.output_wire is None:
        #     for switch in SWITCH_WIRES:
        #         self.output[switch] = self.weights[switch]
        #     for wire in WIRES:
        #         assert self.output[wire] != 'undefined'
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
            # print(f'{self.swapping=}, {candidates=}')
            # if self.swapping:
            #     candidate_weights = [0.25, 0.75]
            # else:
            #     candidate_weights = [0.75, 0.25]
            # if p_sum > 0:
            #     normed = [x/p_sum for x in (p_upper, p_lower)]
            #     chosen = random.choice()
            #     selector = random.random()
            #     if selector < normed[0]:
            #         self.output_wire = 'upper'
            #     else:
            #         self.output_wire = 'lower'
        if self.sim.selector is not None:
            selector = self.sim.selector()
            chosen = candidates[select(candidate_weights, selector)]
        else:
            chosen = random.choices(candidates, candidate_weights)[0]
        if self.sim.selector_value >= 0:
            selector = self.sim.selector_value
        else:
            selector = self.sim.selector()
        selector = random.random()
        if abs(self.theta) % PI()/2 >= selector:
            self.output_wire = 'upper'
        else:
            self.output_wire = 'lower'
        # self.output_wire = chosen[1]
        # self.output[self.output_wire] = flat_list(chosen[0])
        # self.output[self.output_wire] = self.weights[self.output_wire]
        # self.output[OTHER[self.output_wire]] = self.weights[OTHER[self.output_wire]]
        # self.output[self.output_wire] = self.weights[self.output_wire]
        return self.output[self.output_wire]

    def control_source(self):
        source_str = self.sim.sources.get(f'{self.name}{SEP}control')
        if source_str is None: return None
        source_parts = source_str.split(SEP)
        if len(source_parts) == 1:
            source_value = self.sim.particles[source_str]
        else:
            source_gate, source_wire = source_parts
            source_value = self.sim.gates[source_gate].results[source_wire]
        if isinstance(source_value, Particle) and source_value.weight == 0:
            return None
        return source_value

    def port_result(self, port):
        if port == 'control': return self.control_source()
        if port != self.output_wire or not self.output[port]:
            return None
        merged =  Particle.merge(self.output[port])
        if not enough(merged.probability, 1e-15):
            return None
        else:
            return merged

    def set_input(self):
        for wire in SWITCH_WIRES:
            self.input[wire] = self._fetch_source(wire)
        self.control = self.control_source()
        self.output['control'] = self.input['control'] = self.control
        # for wire in WIRES:
        #     self.input[wire] = gstate[wire]
        #     if wire == 'control': self.control = self.output[wire] = self.input[wire]
        assert self.control == self.input['control']
        if not self.control:
            self.swapping = False
        else:
            pc = Particle.merge(flat_list(self.control))
            if pc:
                if self.sim.selector is not None:
                    threshold = self.sim.selector()
                else:
                    if self.sim.control_threshold == -1:
                        threshold = random.random()
                    else:
                        threshold = self.sim.control_threshold
                swap_enough = enough(pc.probability, threshold)
            else:
                swap_enough = False
            self.swapping = pc and swap_enough
        assert self.output['control'] == self.input['control']
        assert not(self.control is None and self.swapping)

    def set_weights(self):
        weights = [self.port_weights(port) for port in WIRES]
        # s_swapped = f'{"NOT SWAPPING" if not self.swapping else "SWAPPING"}'
        # log.info(f'GATE {self} ({s_swapped}):')
        log.info(f'   WEIGHTS:')
        for sw, w in zip(WIRES, weights):
            if isinstance(w, list):
                w = astr(w)
            log.info(f'      {sw:7s}: {w}')
        log.info('')

    def set_output(self):
        self.output_wire = None
        for wire in SWITCH_WIRES:
            self.output[wire] = 'undefined'
        for wire in WIRES:
            self.port_output(wire)

    @property
    def results(self):
        return {wire: self.port_result(wire) for wire in WIRES}

    def _fetch_source(self, port, source_type='output'):
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
                if port == 'control':
                    result = self.sim.gates[source_gate].results['control']
                elif source_type == 'weights':
                    result = self.sim.gates[source_gate].port_weights(source_wire)
                    log.debug(f'{self.name}:_fetch_source({port_source}, {source_type})={result}')
                else:
                    result = self.sim.gates[source_gate].port_output(source_wire)
                    log.debug(f'{self.name}:_fetch_source({port_source})={result}')
                if isinstance(result, Particle) and result.weight == 0:
                    return None
                return result

    def process_particle(self, particle):
        measurements = self.measure(particle)
        signs = [particle.sign, -particle.sign, particle.sign, -particle.sign]
        results = [Particle(particle.name, measurement, sign) for measurement, sign in zip(measurements, signs)]
        return results


class DelayGate(Gate):
    def __init__(self, name, sim=None):
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
        return self.state
    @input.setter
    def input(self, value):
        self.state = value

    @property
    def weights(self):
        return self.state
    @weights.setter
    def weights(self, value):
        self.state = value

    @property
    def output(self):
        return self.state
    @output.setter
    def output(self, value):
        self.state = value

    @property
    def results(self):
        return {k: self.output for k in ['output', 'control', 'upper', 'lower']}

    @property
    def theta(self):
        return qify(0)

    def _fetch_source(self, _=None):
        source = self.sim.sources[f'{self.name}{SEP}input']
        source_gate, source_wire = source.split(SEP)
        result = self.sim.gates[source_gate].results[source_wire]
        return result

    def set_input(self):
        self.state = self.input = self.weights = self.output == self._fetch_source()

    def set_weights(self):
        self.weights = self._fetch_source()

    def set_output(self):
        self.output = self._fetch_source()

    def port_input(self, _):
        return self.input

    def port_weights(self, _):
        return self.weights

    def port_output(self, _):
        return self.output

    def measure(self, p:Particle):
        return p
