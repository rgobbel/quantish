from collections import defaultdict
import logging
import random
from addict import Dict

from quantish.particle import Particle
from quantish.gate import DelayGate, FredkinGate
from quantish.config_space import WIRES, RunStage, OTHER
from quantish.util import SEP, sstr

log = logging.getLogger('quantish')

class Simulation:
    def __init__(self, config):
        def setprob(key):
            long_key = f'{key}_threshold'
            if key in config.probability_threshold:
                config_val = config.probability_threshold[key]
                if config_val == -1:
                    setattr(self, long_key, lambda: fixed_random)
                elif config_val == -3:
                    setattr(self, long_key, random.random)
                else:
                    setattr(self, long_key, lambda: config_val)
            else:
                setattr(self, long_key, lambda: self.selector())

        self.state_dict = defaultdict(list)
        self.config = config
        self.title = config['title']
        self.symbolic = config.get('symbolic', False)
        self.precision = config.get('string_precision', 2)
        # self.add_with_signs = config.get('add_with_signs', False)
        # self.swap_if_selected = config.get('swap_if_selected', False)
        # self.always_forward_switch_weights = config.get('always_forward', {}).get('switch_weights', False)
        # self.always_forward_control_weights = config.get('always_forward', {}).get('control_weights', False)
        # self.alternative_measure = config.get('alternative_measure', False)
        # self.merge_before_measure = config.get('merge', {'before_measure': False}).get('before_measure', False)
        # self.merge_before_forward = config.get('merge', {'before_forwarding': False}).get('before_forwarding', False)
        # self.add_with_signs = config.get('merge', {'add_with_signs': False}).get('add_with_signs', False)
        # self.combine_signs = config.get('merge', {'combine_signs': True}).get('combine_signs', True)
        # self.combine_names = config.get('merge', {'combine_names': True}).get('combine_names', True)
        self.sample = config.get('sample', False)
        self.n_samples = config.get('n_samples', 0)
        self.qvars = {vname: vval for vname, vval in config['variables'].items()}
        self.links = config['links']
        self.sources = {v: k for k, v in self.links.items()}
        self.particles = Dict()
        self.sinks = Dict()
        self.run_results = {}
        self.run_stages = {}
        self.gates = Dict()
        # self.normalize_output = config.normalize_weights.output
        # self.normalize_input = config.normalize_weights.input

        # selector chooses a value to determine probability thresholds
        # no value: a fixed random value,
        # -1:       same as no value, a fixed random value
        # -2:       fixed value based on a random angle from 0 to 90 degrees (doesn't really make sense)
        # -3:       callable, random value between 0 and 1
        # any other value: fixed value from config file
        fixed_random = random.random()
        if 'probability_threshold' not in config:
            config.probability_threshold = Dict()
        if 'selector' in config.probability_threshold:
            self.selector_value =  self.config.probability_threshold.selector
        else:
            self.selector_value = fixed_random
        # self.swap_threshold = None
        # self.forwarding_threshold = None
        # self.presence_threshold = None
        if self.selector_value is None:
            self.selector = lambda: fixed_random
        else:
            if self.selector_value == -1:
                # val = lambda: random.random()
                self.selector = lambda: fixed_random
            # elif self.selector_value == -2:
            #     val = (random.random() * PI() / 2).cos ** 2
            #     self.selector = lambda: fixed_random
            elif self.selector_value == -3:
                self.selector = random.random
            else:
                self.selector = lambda: self.selector_value
            # self.swap_threshold = self.forwarding_threshold = self.presence_threshold = self.selector
        setprob('swap')
        setprob('forwarding')
        # if 'probability_threshold' in config and 'presence' in config.probability_threshold:
        #     self.presence_threshold = config.probability_threshold.presence
        #     if self.presence_threshold == -1:
        #         self.presence_threshold = lambda: random.random()
        #     elif self.presence_threshold == -3:
        #             self.presence_threshold = random.random
        # else:
        #     self.presence_threshold = self.selector
        # log.info(f'merge:')
        # log.info(f'   before measure={self.merge_before_measure}')
        # log.info(f'   before forward={self.merge_before_forward}')
        # log.info(f'always forward:')
        # log.info(f'   switch weights={self.always_forward_switch_weights}')
        # log.info(f'   control weights={self.always_forward_control_weights}')
        # log.info(f'combine:')
        # log.info(f'   signs={self.combine_signs}')
        # log.info(f'   names={self.combine_names}')
        # log.info(f'   add with signs={self.add_with_signs}')
        # log.info(f'normalize:')
        # log.info(f'   before measure={self.normalize_input}')
        # log.info(f'   before forwarding={self.normalize_output}')
        # log.info(f'swap if selected={self.swap_if_selected}')
        log.info('')
        for pname, pval in config['particles'].items():
            self.particles[pname] = Particle(pname, pval['sign'], precision=self.precision,add_with_signs=self.add_with_signs)
            log.info(f'PARTICLE: {self.particles[pname]}')
        log.info('')
        for gname, gval in config.gates.items():
            # if 'swap_threshold' in gval:
            #     swap_threshold = gval.swap_threshold
            # else:
            #     swap_threshold = self.swap_threshold
            # if 'forwarding_threshold' in gval:
            #     forwarding_threshold = gval.forwarding_threshold
            # else:
            #     forwarding_threshold = self.forwarding_threshold
            self.gates[gname] = FredkinGate(gname, gval.angle)
        if 'delay_gates' in config:
            for dgname in config.delay_gates:
                self.gates[dgname] = DelayGate(dgname, sim=self)
        self.diagram_groups = config.get('diagram_groups', config['run_stages'])
        for stage_name, gate_names in config['run_stages'].items():
            next_stage = RunStage(stage_name, [self.gates[gname] for gname in gate_names])
            self.run_stages[stage_name] = next_stage

        log.info(f'{self.qvars=}')
        log.info(f'run stages={", ".join([f"{v}" for v in self.run_stages.values()])}')
        log.info(f'{self.gates=}')
        log.info(f'{self.particles=}')
        # log.info(f'{self.swap_threshold=}, {self.forwarding_threshold=}, {self.presence_threshold=}')
        # log.info(f'{self.normalize_input=}, {self.normalize_output=}')
        log.info('')

    def run(self):

        for stage in self.run_stages.values():
            stage.run()
        log.info('')

        for g in self.gates.values():
            if type(g) is FredkinGate:
                if g.outputs and g.output_wire is not None:
                    out_pos = f'{g.name}{SEP}{g.output_wire}'
                    other_pos = f'{g.name}{SEP}{OTHER[g.output_wire]}'
                    self.run_results[out_pos] = g.results[g.output_wire]
                    self.run_results[other_pos] = []
                # for wire in WIRES:
                #     out_pos = f'{g.name}{SEP}{wire}'
                #     if g.outputs and g.output_wire == wire:
                #         self.run_results[out_pos] = g.results[wire]
                #     else:
                #         self.run_results[out_pos] = None
        log.info('RESULTS:')
        for k, v in self.run_results.items():
            if v is not None:
                log.info(f'   {k}: {Particle.merge(v)}: {v}')
        log.info('')

        log.info('RESULT VALUES BY GATE:')
        gate_results = defaultdict(dict)
        for k, v in self.run_results.items():
            gate, wire = k.split('.')
            gate_results[gate][wire] = Particle.merge(v)
        gate_names = list(sorted(gate_results.keys()))
        for gate in gate_names:
            vals_list = [f'{k}: {v}' for k, v in gate_results[gate].items()]
            valstr = ', '.join(vals_list)
            log.info(f'   {gate}: {valstr}')
        log.info('')
        log.info('DONE!')

        return self.run_results #, self.sinks, self.particles

    def pos_value_str(self, pos, val_type='results'):
        parts = pos.split('.')
        if len(parts) == 1:
            merged = self.particles[parts]
        else:
            gname, gwire = parts
            gate = self.gates[gname]
            # if val_type == 'output' and swap_output and gate.swapping:
            #     gwire = OTHER[gwire]
            values = getattr(gate, val_type)[gwire]
            if not values: return None
            merged = Particle.merge(values)
            ss = sstr(merged.sign)
            pname = merged.name.split('>')[0]
        return f'{merged}' #f'{ss}{pname}: {wstr(merged.weight, precision=self.precision)}'

