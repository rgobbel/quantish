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
        self.combine_names = config.get('merge', {'combine_names': True}).get('combine_names', True)
        self.sample = config.get('sample', False)
        self.n_samples = config.get('n_samples', 0)
        self.qvars = {vname: vval for vname, vval in config['variables'].items()}
        self.links = config['links']
        self.sources = {v: k for k, v in self.links.items()}
        self.particles = {}
        self.sinks = {}
        self.run_results = {}
        self.phases = config['phases']
        self.gates = {}
        self.normalize_outputs = config.get('normalize_weights', {}).get('output', False)
        self.normalize_inputs = config.get('normalize_weights', {}).get('input', False)
        self.control_threshold = Real(config.get('probability_threshold', {}).get('control', 0))
        self.forwarding_threshold = Real(config.get('probability_threshold', {}).get('forwarding', 0))
        self.presence_threshold = Real(config.get('probability_threshold', {}).get('presence', 0))
        log.info(f'merge before: measure={self.merge_before_measure}, forward={self.merge_before_forward}')
        log.info(f'combine: signs={self.combine_signs}, names={self.combine_names}')
        log.info(f'normalize: inputs={self.normalize_inputs}, outputs={self.normalize_outputs}')
        log.info('')
        for pname, pval in config['particles'].items():
            if type(pval) is Particle:
                self.particles[pname] = pval
            else:
                pweight = Complex(pval['weight'])
                self.particles[pname] = (
                    Particle(pname, pweight, qify(pval['sign']),
                             precision=self.precision,
                             add_with_signs=self.add_with_signs))
                log.info(f'PARTICLE: {self.particles[pname]}')
        log.info('')
        self.order = topo_sort(self.links)
        log.info(f'EXECUTION ORDER: {", ".join(self.order)}')
        log.info('')
        for gname, gval in config['gates'].items():
            if type(gval) is FredkinGate:
                self.gates[gname] = gval
            else:
                self.gates[gname] = FredkinGate(
                    gname, gval['angle'],
                    sim=self,
                    alternative_measure=self.alternative_measure)
        # for obname in self.order:
        #     if obname in self.gates.keys():
        #         gate = self.gates[obname]
        #         log.info(f'{gate=}')
        #         cval = gate.port_weights('control')
        #         uval = gate.port_weights('upper')
        #         lval = gate.port_weights('lower')
        #         swap = gate.p_swap
        #         log.info(f'   {swap} control:{cval}, upper:{uval}, lower: {lval}')
        log.info(f'{self.qvars=}')
        log.info(f'{self.phases=}')
        log.info(f'{self.gates=}')
        log.info(f'{self.particles=}')
        log.info(f'{self.control_threshold=:.1f}, {self.forwarding_threshold=:.1f}, {self.presence_threshold=:.1f}')
        log.info(f'{self.normalize_inputs=}, {self.normalize_outputs=}')
        log.info('')

    def propagate_weights(self):
        astr = lambda x: ', '.join([str(s) for s in x]) if x else 'None'
        merge_before_measure = self.merge_before_measure
        merge_before_forward = self.merge_before_forward
        combine_signs = self.combine_signs
        combine_names = self.combine_names
        normalize_inputs = self.normalize_inputs
        normalize_outputs = self.normalize_outputs
        selector = lambda: random.random()

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
            # if obname in self.particles.keys():
            #     particle = self.particles[obname]
            #     destination = self.links[obname]
            #     log.info(f'PARTICLE: {particle} -> {destination}')
            #     self.state_dict[destination] += [particle]
            #     log.info('')
            if obname in self.gates.keys():
                ## grab pieces to operate on
                gate = self.gates[obname]
                gate.set_inputs()
                gate.set_weights()
                gate.set_outputs()
                gate_positions = {wire: f'{obname}{SEP}{wire}' for wire in WIRES}
                inputs = gate.inputs
                weights = gate.weights
                outputs = gate.outputs
                destinations = default_wires()
                for wire in WIRES: # look up sources and destinations for all wires in this gate
                    pos = gate_positions[wire]
                    destinations[wire] = self.links.get(pos)
                    weights[wire] = gate.port_weights(wire)
                        # weights[wire] = []
                # log.info(f'GATE {gate} weights:')
                # for wire in WIRES:
                #     log.info(f'   {wire}_inputs= {astr(gate.inputs[wire])} -> {destinations[wire]}')
                # log.info('')

                ## Set up control input
                swap = 'swapped' if gate.swapping else 'straight'
                if weights['control']:
                    if type(weights['control']) is list:
                        control = Particle.merge(weights['control'])
                    else:
                        control = weights['control']
                    gate.control = control
                    # if destinations['control'] is not None: # forward control, regardless of probability
                    #     self.state_dict[destinations['control']] += weights['control']
                    #     if not self.sinks.get(gate_positions['control']):
                    #         self.sinks[gate_positions['control']] = Sink(
                    #             gate_positions['control'],
                    #             control.pid,
                    #             presence_threshold=self.presence_threshold,
                    #             initial_values=weights['control'], precision=self.precision,
                    #             combine_signs=combine_signs,
                    #             combine_names=combine_names)
                else:
                    # pname = Gensym('null_control').name
                    # placeholder = Particle(pname, 0, 1)
                    # self.sinks[gate_positions['control']] = Sink(
                    #     gate_positions['control'],
                    #     placeholder.pid,
                    #     presence_threshold=self.presence_threshold,
                    #     initial_values=[placeholder], precision=self.precision,
                    #     combine_signs=combine_signs)
                    # control = placeholder
                    control = None
                    swap = 'straight'

                if normalize_inputs:
                    for wire in SWITCH_WIRES:
                        if weights[wire]: norm_input_particles(weights[wire])
                if merge_before_measure:
                    log.info('MERGING INPUTS')
                    for wire in SWITCH_WIRES:
                        weights[wire] = merge_inputs(weights[wire])

                ## Log weights and set up variables for output.
                log.info(f'   INPUTS:')
                presence_str = 'PRESENT' if swap == 'swapped' else 'NOT PRESENT'
                log.info(f'      control: {control} {presence_str}')
                # log.info(f'      control= {control}')
                for wire in SWITCH_WIRES:
                    v = inputs[wire]
                    if isinstance(v, list):
                        v = astr(v)
                    log.info(f'      {wire}:   {v}')
                switch_results = default_switches()
                # m_result_dict = defaultdict(list)

                ## Sequence through and measure weights. Don't deal with control input-based swap yet.
                # for input_wire in SWITCH_WIRES:
                #     input_particles = weights[input_wire]
                #     for p_in in input_particles:
                #         if to_float(p_in.probability) > 0: # Zero probability particles are discarded
                #             log.info(f'      measure {p_in}')
                #             # get raw measurements
                #             measurement_results = gate.measure(p_in)
                #             # normalize to sum == 1 if we're doing that
                #             if normalize_outputs:
                #                 for i in range(len(measurement_results)):
                #                     measurement_results[i] *= 1/p_in.weight
                #
                #             signs = [p_in.sign, -p_in.sign, p_in.sign, -p_in.sign]
                #             output_wires = [input_wire, input_wire, OTHER[input_wire], OTHER[input_wire]] # internal forwarding only!
                #             components = [f'c{component}{subc}' for component in ['2', '3'] for subc in ['a', 'b']]
                #
                #             for i, (sign, component, output_wire) in enumerate(zip(signs, components, output_wires)):
                #                 pname = f'{p_in.name}>{gate.name}.{output_wire}'
                #                 m_result_particle = Particle(
                #                     pname, measurement_results[i], sign,
                #                     precision=self.precision, add_with_signs=self.add_with_signs)
                #                 log.info(f'        ->{gate.name} {input_wire}({component})->{output_wire} {m_result_particle}')
                #                 m_result_dict[f'{output_wire}_{component}'] += [m_result_particle]
                # gather results from upper and lower INPUTS
                # for input_wire in SWITCH_WIRES:
                #     switch_results[input_wire] += \
                #         (m_result_dict[f'{input_wire}_c2a'] +
                #          m_result_dict[f'{input_wire}_c2b'] +
                #          m_result_dict[f'{input_wire}_c3a'] +
                #          m_result_dict[f'{input_wire}_c3b'])

                for input_wire in SWITCH_WIRES:
                    # in_pos = gate_positions[input_wire]
                    switch_results[input_wire] = weights[input_wire]
                    # if switch_results[input_wire]:
                        # if self.combine_signs:
                        #     switch_results[input_wire] = [Particle.merge(switch_results[input_wire])]
                        # gate.outputs[input_wire] = switch_results[input_wire]
                        # self.state_dict[gate_positions[input_wire]] = switch_results[input_wire]
                        # sink = Sink(in_pos, presence_threshold=self.presence_threshold,
                        #             pid=control.pid if control else 'EMPTY',
                        #             initial_values=switch_results[input_wire],
                        #             precision=self.precision, combine_signs=combine_signs)
                        # self.sinks[in_pos] = sink
                log.info('   OUTPUTS:')
                for wire in WIRES:
                    outputs[wire] = gate.port_outputs(wire)
                    log.info(f'      {wire:7s}: {gate.port_outputs(wire)}')
                # if swap:
                #     log.info('   SWAPPING UPPER<->LOWER')
                # output_choices = []
                # for input_wire in SWITCH_WIRES:
                #     for pval in switch_results[input_wire]:
                #         output_choices += [[input_wire, pval]]
                # if output_choices:
                #     out_max = softmax([x[1].weight.real for x in output_choices])
                #     output = output_choices[select([abs(x[1].weight.real) for x in output_choices], selector())]
                #     output_wire = output[0] if not swap else OTHER[output[0]]
                #     log.info('   OUTPUT:')
                #     if destinations[output_wire]:
                #         log.info(f'      {f'{gate.name}{SEP}{output[0]}'}->{output_wire}->{destinations[output_wire]}: {output[1]}')
                #         self.state_dict[destinations[output_wire]] += [output[1]]
                #         self.run_results[gate_positions[output_wire]] = output[1]
                #     else:
                #         log.info(f'      {f'{gate.name}{SEP}{output[0]}'}->{output_wire}->SINK: {output[1]}')
                #         self.run_results[gate_positions[output_wire]] = output[1]
                # if enough(probability(pval.weight), self.forwarding_threshold):
                #         if not destinations[output_wire]:
                #             pname = f'{pval.name}>{out_pos}'
                #         else:
                #             pname = f'{pval.name}>{out_pos}>{destinations[output_wire]}'
                #         outputs[output_wire].append(Particle(pname, pval.weight, pval.sign,
                #                                 precision=self.precision,
                #                                 add_with_signs=self.add_with_signs))
                #         log.info(f'        {input_wire}->{output_wire}')
                #         out_pos = f'{gate.name}.{output_wire}'
                #         log.info(f'   OUTPUTS:')
                #         outputs = default_switches()
                #         if outputs[output_wire]:
                #             sink = Sink(out_pos, presence_threshold=self.presence_threshold,
                #                         pid=control.pid if control else 'EMPTY',
                #                         precision=self.precision, combine_signs=combine_signs,
                #                         combine_names=combine_names)
                #             self.sinks[out_pos] = sink
                #             if not merge_before_forward:
                #                 sink.add(outputs[output_wire])
                #                 for output_particle in outputs[output_wire]:
                #                     log.info(f'            {output_particle}')
                #                     if destinations[output_wire]:
                #                         self.state_dict[destinations[output_wire]].append(output_particle)
                #             else: # merging
                #                 log.info(f'        MERGED OUTPUTS')
                #                 if combine_signs:
                #                     merged = Particle.merge(outputs)
                #                     if not merged and enough(merged.probability, self.forwarding_threshold):
                #                         log.info(f'           ->  {merged}')
                #                         self.state_dict[destinations[output_wire]].append(merged)
                #                         sink.add([merged])
                #                     else:
                #                         log.info(f'           None')
                #                 else:
                #                     for sign_test, sign_str in [('__gt__', 'plus'), ('__lt__', 'minus')]:
                #                         merged = Particle.merge([x for x in outputs if getattr(x, sign_test)(0)])
                #                     if not merged and enough(merged.probability, self.forwarding_threshold):
                #                         log.info(f'           {sign_str}->  {merged}')
                #                         self.state_dict[destinations[output_wire]].append(merged)
                #                         sink.add([merged])
                #                     else:
                #                         log.info(f'           {sign_str}:  None')
                #         else:
                #             log.info(f'            NO OUTPUT')

                log.info('')

        log.info('')
        for g in self.gates.values():
            for wire in WIRES:
                out_pos = f'{g.name}{SEP}{wire}'
                if g.outputs[wire]:
                    self.run_results[out_pos] = g.outputs[wire]
                else:
                    self.run_results[out_pos] = None
        log.info('RESULTS:')
        for k, v in self.run_results.items():
            if v is not None:
                log.info(f'   {k}: {v}')
        log.info('')
        # log.info(f'CONTROL THRESHOLD = {self.control_threshold}')
        # log.info('')
        # log.info('SINK VALUE SUMMARIES:')
        # self.gate_weights = defaultdict(dict)
        # for sink_name, sink in self.sinks.items():
        #     if len(sink.values.values()) == 0:
        #         continue
        #         # pname = Gensym('null').name
        #         # placeholder = Particle(pname, 0, 1)
        #         # sink.add([placeholder])
        #     sink_gate, sink_wire = sink_name.split('.')
        #     sink_str = sink.vstr
        #     self.gate_weights[sink_gate][sink_wire] = sink_str
        #     gsum = Particle.merge(sink.values.values())
        #     if sink_str == 'None':
        #         pstr = ''
        #     else:
        #         pstr = f': {"+" if gsum.sign == 1 else "-"}{gsum.name.split('>')[0]}({gsum.probability:.2f})'
        #     log.info(f'   {sink_name} -> {sink.vstr}{pstr}')
        # log.info('')
        log.info('RESULT VALUES BY GATE:')
        gate_results = defaultdict(dict)
        for k, v in self.run_results.items():
            gate, wire = k.split('.')
            gate_results[gate][wire] = v
        gate_names = list(sorted(gate_results.keys()))
        for gate in gate_names:
            vals_list = [f'{k}: {v}' for k, v in gate_results[gate].items()]
            valstr = ', '.join(vals_list)
            log.info(f'   {gate}: {valstr}')
        log.info('')
        log.info('DONE!')

        return self.run_results #, self.sinks, self.particles

    def run_experiment(self):
        experiment_inputs = defaultdict(list)
        experiment_results = defaultdict(list)
        selector = random.random()
        print('')
        for obname in self.order:
            if obname in self.particles.keys():
                particle = self.particles[obname]
                destination = self.links[obname]
                if destination and particle.probability >= 0.5:
                    log.debug(f'PARTICLE: {particle} -> {destination}')
                    experiment_inputs[destination] += [particle]
            elif obname in self.gates.keys():
                gate = self.gates[obname]
                control_pos = f'{gate.name}.control'
                control_input = experiment_inputs.get(control_pos, [])
                if len(control_input) > 1:
                    raise RuntimeError(f'invalid control_state: {control_input}')
                control_present = len(control_input) > 0 and control_input[0].probability >= random.random()
                out_wires = SWAPPED if control_present else STRAIGHT
                upper_in_wire = f'{gate.name}.upper'
                upper_out_wire = out_wires['upper']
                lower_in_wire = f'{gate.name}.lower'
                lower_out_wire = out_wires['lower']
                upper_in_present = experiment_inputs.get(upper_in_wire) is not None
                lower_in_present = experiment_inputs.get(lower_in_wire) is not None
                choices = []
                upper_outs = self.sinks.get(f'{gate.name}.{upper_out_wire}')
                if upper_in_present and upper_outs is not None and upper_outs.value:
                    choices += [[upper_out_wire, p] for p in upper_outs.values.values()]
                lower_outs = self.sinks.get(f'{gate.name}.{lower_out_wire}')
                if lower_in_present and lower_outs is not None and lower_outs.value:
                    choices += [[lower_out_wire, p] for p in lower_outs.values.values()]
                # if upper_in_maybe is not None:
                #     upper_ins = upper_in_maybe
                # else:
                #     upper_ins = []
                # if lower_in_maybe is not None:
                #     lower_ins = lower_in_maybe
                # else:
                #     lower_ins = []
                # # choices = [['upper', p] for p in upper_outs if p.probability > 0] + \
                # #           [['lower', p] for p in lower_outs if p.probability > 0]
                # choices = [[upper_out_wire, p] for p in upper_ins] + [[lower_out_wire, p] for p in lower_ins]
                if choices:
                    # random.shuffle(choices)
                    # choices = sorted(choices, key=lambda x: x[1].probability, reverse=True)
                    out_wire, out_particle = choices[select([p[1].probability for p in choices], selector)]
                    # print(f'{out_wire=}, out_particle={out_particle.ps(short=True)}, dest={out_particle.name.split('>')[-1]}')
                    switch_output = f'{gate.name}.{out_wire}'  # Fixed: need full position, not just 'upper'/'lower'
                    switch_destination = self.links.get(switch_output)
                    if switch_destination: # forward to next stage
                        if switch_destination in experiment_inputs.keys():
                            raise RuntimeError(f'destination already set: {experiment_inputs[switch_destination]}, new value is {out_particle}')

                        experiment_inputs[switch_destination] += [out_particle]
                        experiment_results[switch_output] += [out_particle]
                        # if len(experiment_results[switch_output]) > 1:
                        #     raise RuntimeError(f'invalid result: {experiment_results[switch_output]}')
                    else: # record final state for this particle
                        final_destination = out_particle.name.split('>')[-1]
                        if final_destination in experiment_results.keys():
                            raise RuntimeError(f'result for {final_destination} was already set: {experiment_results[final_destination]}, new value is {out_particle}')
                        experiment_results[final_destination] += [out_particle]
                        # if len(experiment_results[final_destination]) > 1:
                        #     raise RuntimeError(f'invalid result: {experiment_results[switch_output]}')
                control_destination = self.links.get(control_pos)
                if len(control_input) > 0:
                    if control_destination:
                        experiment_inputs[control_destination] = control_input
                        # experiment_results[control_destination] = control_input
                    else:
                        experiment_results[control_pos] = control_input

        print('EXPERIMENT STATE:')
        for k, v in experiment_inputs.items():
            print(f'   {k}: {v}')

        print('EXPERIMENT RESULT:')
        for k, v in experiment_results.items():
            print(f'   {k}: {v}')

        return experiment_results, experiment_inputs

    def pos_value_str(self, pos):
        values = self.state_dict[pos]
        if not values: return '0'
        merged = Particle.merge(values)
        ss = f"{'+' if merged.sign > 0 else '-'}"
        pname = merged.name.split('>')[0]
        return f'{ss}{pname}: {wstr(merged.weight, precision=self.precision)}'

