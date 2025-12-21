from collections import defaultdict
import logging
import random

from quantish.particle import Particle
from quantish.gate import DelayGate, FredkinGate
from quantish.config_space import WIRES, RunStage
from quantish.qnumber import Real, qify, softmax, Complex, PI
from quantish.util import SEP

log = logging.getLogger('quantish')

class Simulation:
    def __init__(self, config):
        self.state_dict = defaultdict(list)
        self.config = config
        self.title = config['title']
        self.symbolic = config.get('symbolic', False)
        self.precision = config.get('string_precision', 2)
        self.add_with_signs = config.get('add_with_signs', False)
        self.always_forward_weights = config.get('always_forward_weights', False)
        self.alternative_measure = config.get('alternative_measure', False)
        self.merge_before_measure = config.get('merge', {'before_measure': False}).get('before_measure', False)
        self.merge_before_forward = config.get('merge', {'before_forwarding': False}).get('before_forwarding', False)
        self.add_with_signs = config.get('merge', {'add_with_signs': False}).get('add_with_signs', False)
        self.combine_signs = config.get('merge', {'combine_signs': True}).get('combine_signs', True)
        self.combine_names = config.get('merge', {'combine_names': True}).get('combine_names', True)
        self.sample = config.get('sample', False)
        self.n_samples = config.get('n_samples', 0)
        self.qvars = {vname: vval for vname, vval in config['variables'].items()}
        self.links = config['links']
        self.sources = {v: k for k, v in self.links.items()}
        self.particles = {}
        self.sinks = {}
        self.run_results = {}
        self.run_stages = {}
        self.gates = {}
        self.normalize_output = config.get('normalize_weights', {}).get('output', False)
        self.normalize_input = config.get('normalize_weights', {}).get('input', False)
        self.selector_value =  self.config.get('probability_threshold', {}).get('selector')
        self.control_threshold = None
        self.forwarding_threshold = None
        self.presence_threshold = None
        if self.selector_value is not None:
            if self.selector_value == -1:
                val = random.random()
                self.selector = lambda: val
            elif self.selector_value == -2:
                val = (random.random() * PI() / 2).cos ** 2
                self.selector = lambda: val
            elif self.selector_value == -3:
                self.selector = random.random
            else:
                self.selector = lambda: self.selector_value
            self.control_threshold = self.forwarding_threshold = self.presence_threshold = self.selector
        else:
            var = random.random()
            self.selector = lambda: var
        if config.get('probability_threshold', {}).get('control') is not None:
            self.control_threshold = Real(config.get('probability_threshold', {}).get('control', 0))
            # if self.control_threshold == -1:
            #     self.control_threshold = random.random()
        elif self.control_threshold is None:
            self.control_threshold = 0
        if config.get('probability_threshold', {}).get('forwarding') is not None:
            self.forwarding_threshold = Real(config.get('probability_threshold', {}).get('forwarding', 0))
            if self.forwarding_threshold == -1:
                self.forwarding_threshold = random.random()
        elif self.forwarding_threshold is None:
            self.forwarding_threshold = 0
        if config.get('probability_threshold', {}).get('presence') is not None:
            self.presence_threshold = Real(config.get('probability_threshold', {}).get('presence', 0))
            if self.presence_threshold == -1:
                self.presence_threshold = random.random()
        elif self.presence_threshold is None:
            self.presence_threshold = 0
        log.info(f'merge before: measure={self.merge_before_measure}, forward={self.merge_before_forward}')
        log.info(f'combine: signs={self.combine_signs}, names={self.combine_names}')
        log.info(f'normalize: input={self.normalize_input}, output={self.normalize_output}')
        log.info('')
        # initial_world_state = WorldState()
        for pname, pval in config['particles'].items():
            pweight = Complex(pval['weight'])
            self.particles[pname] = (
                Particle(pname, pweight, qify(pval['sign']),
                         precision=self.precision,
                         add_with_signs=self.add_with_signs))
            log.info(f'PARTICLE: {self.particles[pname]}')
        log.info('')
        for gname, gval in config['gates'].items():
            self.gates[gname] = FredkinGate(
                gname, gval['angle'],
                sim=self)
        for dgname in config.get('delay_gates', []):
            self.gates[dgname] = DelayGate(dgname, sim=self)
        self.diagram_groups = config.get('diagram_groups')
        for stage_name, gate_names in config['run_stages'].items():
            next_stage = RunStage(stage_name, [self.gates[gname] for gname in gate_names])
            self.run_stages[stage_name] = next_stage

        log.info(f'{self.qvars=}')
        log.info(f'run stages={", ".join([f"{v}" for v in self.run_stages.values()])}')
        log.info(f'{self.gates=}')
        log.info(f'{self.particles=}')
        log.info(f'{self.control_threshold=}, {self.forwarding_threshold=}, {self.presence_threshold=}')
        log.info(f'{self.normalize_input=}, {self.normalize_output=}')
        log.info('')

    def run(self):
        astr = lambda x: ', '.join([str(s) for s in x]) if x else 'None'
        merge_before_measure = self.merge_before_measure
        merge_before_forward = self.merge_before_forward
        combine_signs = self.combine_signs
        combine_names = self.combine_names
        normalize_input = self.normalize_input
        normalize_output = self.normalize_output
        selector = lambda: random.random()

        def norm_input_particles(particles):
            pw = [p.weight for p in particles]
            normed = softmax(pw)
            for p, w in zip(particles, normed):
                p.weight = w

        def merge_input(group):
            pluses = [Particle.merge([x for x in group if x.sign > 0])]
            pluses = [] if not pluses else pluses
            minuses = [Particle.merge([x for x in group if x.sign < 0])]
            minuses = [] if not minuses else minuses
            group = pluses + minuses
            if group and combine_signs:
                group = Particle.merge(group)
                group = [] if not group else [group]
            return group

        for stage in self.run_stages.values():
            stage.run()
        log.info('')

        for g in self.gates.values():
            if type(g) is FredkinGate:
                for wire in WIRES:
                    out_pos = f'{g.name}{SEP}{wire}'
                    if g.output and g.output[wire]:
                        self.run_results[out_pos] = g.output[wire]
                    else:
                        self.run_results[out_pos] = None
        log.info('RESULTS:')
        for k, v in self.run_results.items():
            if v is not None:
                log.info(f'   {k}: {v}')
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
            ss = f"{'+' if merged.sign > 0 else '-'}"
            pname = merged.name.split('>')[0]
        return f'{merged}' #f'{ss}{pname}: {wstr(merged.weight, precision=self.precision)}'

