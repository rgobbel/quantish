import logging
from collections import defaultdict
from quantish.particle import Particle
from quantish.gate import FredkinGate
from quantish.sink import Sink
from quantish.config_space import default_switches, default_wires, WIRES, SWITCH_WIRES, OTHER, STRAIGHT, SWAPPED
from quantish.qnumber import Real, qify, softmax, probability, Complex
from quantish.util import topo_sort, SEP, wstr, enough, to_float, Gensym, select
import random

log = logging.getLogger('quantish')

class Simulation:
    def __init__(self, config):
        self.state_dict = defaultdict(list)
        self.config = config
        self.title = config['title']
        self.symbolic = config.get('symbolic', False)
        self.precision = config.get('string_precision', 2)
        self.add_with_signs = config.get('add_with_signs', False)
        self.alternative_measure = config.get('alternative_measure', False)
        self.merge_before_measure = config.get('merge', {'before_measure': False}).get('before_measure', False)
        self.merge_before_forward = config.get('merge', {'before_forwarding': False}).get('before_forwarding', False)
        self.add_with_signs = config.get('merge', {'add_with_signs': False}).get('add_with_signs', False)
        self.combine_signs = config.get('merge', {'combine_signs': True}).get('combine_signs', True)
        self.sample = config.get('sample', False)
        self.n_samples = config.get('n_samples', 0)
        self.qvars = {vname: vval for vname, vval in config['variables'].items()}
        self.links = config['links']
        self.reverse_links = {v: k for k, v in self.links.items()}
        self.particles = {}
        self.sinks = {}
        self.phases = config['phases']
        self.gates = {}
        self.normalize_outputs = config.get('normalize_weights', {}).get('output', False)
        self.normalize_inputs = config.get('normalize_weights', {}).get('input', False)
        self.scale_by_control = config.get('normalize_weights', {}).get('by_control', False)
        self.control_threshold = Real(config.get('probability_threshold', {}).get('control', 0))
        self.forwarding_threshold = Real(config.get('probability_threshold', {}).get('forwarding', 0))
        self.presence_threshold = Real(config.get('probability_threshold', {}).get('presence', 0))
        log.info(f'merge before measure={self.merge_before_measure}, merge before forwarding={self.merge_before_forward}, combine signs={self.combine_signs}')
        log.info(f'normalize inputs={self.normalize_inputs}, normalize outputs={self.normalize_outputs}')
        log.info('')
        for pname, pval in config['particles'].items():
            if type(pval) is Particle:
                self.particles[pname] = pval
            else:
                pweight = Complex(pval['weight'])
                self.particles[pname] = Particle(pname, pweight, qify(pval['sign']),
                                                 precision=self.precision,
                                                 add_with_signs=self.add_with_signs)
        self.order = topo_sort(self.links)
        for gname, gval in config['gates'].items():
            if type(gval) is FredkinGate:
                self.gates[gname] = gval
            else:
                self.gates[gname] = FredkinGate(gname, gval['angle'], alternative_measure=self.alternative_measure)
        log.info('')
        log.info(f'{self.qvars=}')
        log.info(f'{self.phases=}')
        log.info(f'{self.gates=}')
        log.info(f'{self.particles=}')
        log.info(f'{self.control_threshold=:.1f}, {self.forwarding_threshold=:.1f}, {self.presence_threshold=:.1f}')
        log.info(f'{self.normalize_inputs=}, {self.normalize_outputs=}')
        log.info('')
        log.info(f'EXECUTION ORDER: {", ".join(self.order)}')
        log.info('')

    def propagate_weights(self):
        astr = lambda x: ', '.join([str(s) for s in x]) if x else 'None'
        merge_before_measure = self.merge_before_measure
        merge_before_forward = self.merge_before_forward
        combine_signs = self.combine_signs
        normalize_inputs = self.normalize_inputs
        normalize_outputs = self.normalize_outputs

        def norm_input_particles(particles):
            pw = [p.weight for p in particles]
            normed = softmax(pw)
            for p, w in zip(particles, normed):
                p.weight = w

        def merge_inputs(group):
            pluses = Particle.merge([x for x in group if x.sign > 0])
            pluses = [] if not pluses else [pluses]
            minuses = Particle.merge([x for x in group if x.sign < 0])
            minuses = [] if not minuses else [minuses]
            group = pluses + minuses
            if group and combine_signs:
                group = Particle.merge(group)
                group = [] if not group else [group]
            return group

        for obname in self.order:
            if obname in self.particles.keys():
                particle = self.particles[obname]
                destination = self.links[obname]
                log.info(f'PARTICLE: {particle} -> {destination}')
                self.state_dict[destination] += [particle]
                log.info('')
            elif obname in self.gates.keys():
                ## grab pieces to operate on
                gate = self.gates[obname]
                gate_positions = {wire: f'{obname}{SEP}{wire}' for wire in WIRES}
                inputs = default_wires()
                destinations = default_wires()
                for wire in WIRES: # look up reverse_links and destinations for all wires in this gate
                    pos = gate_positions[wire]
                    destinations[wire] = self.links.get(pos)
                    if pos in self.state_dict.keys():
                        inputs[wire] = self.state_dict[pos]
                    else:
                        inputs[wire] = []
                log.info(f'GATE {gate} inputs:')
                for wire in WIRES:
                    log.info(f'   {wire}_inputs= {astr(inputs[wire])} -> {destinations[wire]}')
                log.info('')

                ## Set up control input. This really just amounts to deciding whether it's present or not,
                ## setting the value of swap. If the control wire goes to another gate, make a state_dict entry.
                ## Always make a sink, whether or not it goes to another gate.
                if inputs['control']:
                    merged_control = Particle.merge(inputs['control'])
                    swap = enough(merged_control.probability, self.control_threshold)
                    if destinations['control'] is not None:
                        self.state_dict[destinations['control']] += inputs['control']
                    self.sinks[gate_positions['control']] = Sink(
                        gate_positions['control'],
                        merged_control.pid,
                        presence_threshold=self.presence_threshold,
                        initial_values=inputs['control'], precision=self.precision,
                        combine_signs=combine_signs)
                else:
                    pname = Gensym('null_control').name
                    placeholder = Particle(pname, 0, 1)
                    self.sinks[gate_positions['control']] = Sink(
                        gate_positions['control'],
                        placeholder.pid,
                        presence_threshold=self.presence_threshold,
                        initial_values=[placeholder], precision=self.precision,
                        combine_signs=combine_signs)
                    merged_control = placeholder
                    swap = False

                if normalize_inputs:
                    for wire in SWITCH_WIRES:
                        if inputs[wire]: norm_input_particles(inputs[wire])
                if merge_before_measure:
                    log.info('MERGING INPUTS')
                    for wire in SWITCH_WIRES:
                        inputs[wire] = merge_inputs(inputs[wire])

                ## Log inputs and set up variables for output.
                log.info(f'   INPUTS:')
                presence_str = 'PRESENT' if swap else 'NOT PRESENT'
                log.info(f'      merged control= {merged_control} {presence_str}')
                for wire in SWITCH_WIRES:
                    log.info(f'      {wire}=   {astr(inputs[wire])}')
                switch_results = default_switches()
                out_dict = defaultdict(list)
                if swap:
                    log.info('   SWAPPING UPPER<->LOWER')

                ## Sequence through and measure inputs. Don't deal with control input-based swap yet.
                for input_wire in SWITCH_WIRES:
                    input_particles = inputs[input_wire]
                    for p_in in input_particles:
                        if to_float(p_in.probability) > 0: # Zero probability particles are discarded
                            log.info(f'      measure {p_in}')
                            # get raw measurements
                            measurement_results = gate.measure(p_in)
                            # normalize to sum == 1 if we're doing that
                            if normalize_outputs:
                                for i in range(len(measurement_results)):
                                    measurement_results[i] *= 1/p_in.weight

                            signs = [p_in.sign, -p_in.sign, p_in.sign, -p_in.sign]
                            output_wires = [input_wire, input_wire, OTHER[input_wire], OTHER[input_wire]]
                            components = [f'c{component}{subc}' for component in ['2', '3'] for subc in ['a', 'b']]

                            for i, (sign, component, output_wire) in enumerate(zip(signs, components, output_wires)):
                                pname = f'{p_in.name}>{gate.name}.{output_wire}'
                                output_particle = Particle(
                                    pname, measurement_results[i], sign,
                                    precision=self.precision, add_with_signs=self.add_with_signs)
                                log.info(f'        ->{gate.name} {input_wire}({component})->{output_wire} {output_particle}')
                                out_dict[f'{output_wire}_{component}'] += [output_particle]
                # gather results from upper and lower INPUTS
                for input_wire in SWITCH_WIRES:
                    switch_results[input_wire] += (out_dict[f'{input_wire}_c2a'] + out_dict[f'{input_wire}_c2b'] +
                                                   out_dict[f'{input_wire}_c3a'] + out_dict[f'{input_wire}_c3b'])

                log.info(f'   OUTPUTS:')
                outputs = default_switches()
                for input_wire in SWITCH_WIRES:
                    output_wire = input_wire if not swap else OTHER[input_wire]
                    out_pos = f'{gate.name}.{output_wire}'
                    if not switch_results[input_wire]:
                        outputs[output_wire] = []
                    else:
                        sink = Sink(out_pos, presence_threshold=self.presence_threshold,
                                    pid=merged_control.pid if merged_control else 'EMPTY',
                                    precision=self.precision, combine_signs=combine_signs)
                        self.sinks[out_pos] = sink
                        for pval in switch_results[input_wire]:
                            if enough(probability(pval.weight), self.forwarding_threshold):
                                if not destinations[output_wire]:
                                    pname = f'{pval.name}>{out_pos}'
                                else:
                                    pname = f'{pval.name}>{out_pos}>{destinations[output_wire]}'
                                outputs[output_wire].append(Particle(pname, pval.weight, pval.sign,
                                                        precision=self.precision,
                                                        add_with_signs=self.add_with_signs))
                        log.info(f'        {input_wire}->')
                        if outputs[output_wire]:
                            if not merge_before_forward:
                                sink.add(outputs[output_wire])
                                for output_particle in outputs[output_wire]:
                                    log.info(f'            {output_particle}')
                                    if destinations[output_wire]:
                                        self.state_dict[destinations[output_wire]].append(output_particle)
                            else: # merging
                                log.info(f'        MERGED OUTPUTS')
                                if combine_signs:
                                    merged = Particle.merge(outputs)
                                    if not merged and enough(merged.probability, self.forwarding_threshold):
                                        log.info(f'           ->  {merged}')
                                        self.state_dict[destinations[output_wire]].append(merged)
                                        sink.add([merged])
                                    else:
                                        log.info(f'           None')
                                else:
                                    for sign_test, sign_str in [('__gt__', 'plus'), ('__lt__', 'minus')]:
                                        merged = Particle.merge([x for x in outputs if getattr(x, sign_test)(0)])
                                    if not merged and enough(merged.probability, self.forwarding_threshold):
                                        log.info(f'           {sign_str}->  {merged}')
                                        self.state_dict[destinations[output_wire]].append(merged)
                                        sink.add([merged])
                                    else:
                                        log.info(f'           {sign_str}:  None')
                        else:
                            log.info(f'            NO OUTPUT')

                log.info('')

        log.info('')
        log.info('RESULTS:')
        log.info('')
        log.info(f'CONTROL THRESHOLD = {self.control_threshold}')
        log.info('')
        log.info('SINK VALUE SUMMARIES:')
        self.gate_weights = defaultdict(dict)
        for sink_name, sink in self.sinks.items():
            if len(sink.values.values()) == 0:
                pname = Gensym('null').name
                placeholder = Particle(pname, 0, 1)
                sink.add([placeholder])
            sink_gate, sink_wire = sink_name.split('.')
            sink_str = sink.vstr
            self.gate_weights[sink_gate][sink_wire] = sink_str
            gsum = Particle.merge(sink.values.values())
            if sink_str == 'None':
                pstr = ''
            else:
                pstr = f': {"+" if gsum.sign == 1 else "-"}{gsum.name.split('>')[0]}({gsum.probability:.2f})'
            log.info(f'   {sink_name} -> {sink.vstr}{pstr}')
        log.info('')
        log.info('SINK VALUES BY GATE:')
        for gate_name in sorted(self.gate_weights.keys()):
            values = self.gate_weights[gate_name]
            vals_list = [f'{k}: {v}' for k, v in values.items()]
            valstr = ', '.join(vals_list)
            log.info(f'   {self.gates[gate_name]}: {valstr}')
        log.info('')
        log.info('DONE!')

        return self.sinks, self.particles

    def run_experiment(self):
        experiment_inputs = defaultdict(list)
        experiments_results = defaultdict(list)
        selector = random.random()
        for obname in self.order:
            if obname in self.particles.keys():
                particle = self.particles[obname]
                destination = self.links[obname]
                log.debug(f'PARTICLE: {particle} -> {destination}')
                experiment_inputs[destination] += [particle]
            elif obname in self.gates.keys():
                gate = self.gates[obname]
                control_pos = f'{gate.name}.control'
                control_state = experiment_inputs.get(control_pos, [])
                control_present = len(control_state) > 0 and control_state[0].probability > 0
                out_wires = SWAPPED if control_present else STRAIGHT
                upper_outs = self.sinks.get(f'{gate.name}.{out_wires["upper"]}').values.values()
                lower_outs = self.sinks.get(f'{gate.name}.{out_wires["lower"]}').values.values()
                choices = [['upper', p] for p in upper_outs if p.probability > 0] + \
                          [['lower', p] for p in lower_outs if p.probability > 0]
                choices = sorted(choices, key=lambda x: x[1].probability)
                chosen = choices[select([p[1].probability for p in choices], selector)]
                switch_output = f'{gate.name}.{chosen[0]}'
                switch_destination = self.links.get(switch_output)
                if switch_destination: # forward to next stage
                    experiment_inputs[switch_destination] += [chosen[1]]
                    experiments_results[switch_destination] += [chosen[1]]
                else: # record final state for this particle
                    final_destination = chosen[1].name.split('>')[-1]
                    experiments_results[final_destination] += [chosen[1]]
                control_destination = self.links.get(control_pos)
                if len(control_state) > 0:
                    if control_destination:
                        experiment_inputs[control_destination] = control_state
                    else:
                        experiments_results[control_pos] = control_state

        log.info('EXPERIMENT STATE:')
        for k, v in experiment_inputs.items():
            log.info(f'   {k}: {v}')

        log.info('EXPERIMENT RESULT:')
        for k, v in experiments_results.items():
            log.info(f'   {k}: {v}')

        return experiments_results, experiment_inputs

    def pos_value_str(self, pos):
        values = self.state_dict[pos]
        if not values: return '0'
        merged = Particle.merge(values)
        ss = f"{'+' if merged.sign > 0 else '-'}"
        pname = merged.name.split('>')[0]
        return f'{ss}{pname}: {wstr(merged.weight, precision=self.precision)}'

