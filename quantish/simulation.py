import logging
from collections import defaultdict
from quantish.particle import Particle
from quantish.gate import Gate
from quantish.sink import Sink
# from quantish.config_space import ConfigurationSpace, Measurement
from quantish.qnumber import Real, qify, softmax, probability, Complex
from quantish.util import topo_sort, SEP, wstr, enough, to_float
import random

log = logging.getLogger('quantish')

class Simulation:
    def __init__(self, config):
        self.state_dict = defaultdict(list)
        self.config = config
        self.title = config['title']
        self.symbolic = config.get('symbolic', False)
        self.winner_take_all = config.get('winner_take_all', False)
        self.precision = config.get('string_precision', 2)
        self.add_with_signs = config.get('add_with_signs', False)
        self.alternative_measure = config.get('alternative_measure', False)
        self.merge_before_measure = config.get('merge', {'before_measure': False}).get('before_measure', False)
        self.merge_before_forward = config.get('merge', {'before_forwarding': False}).get('before_forwarding', False)
        self.add_with_signs = config.get('merge', {'add_with_signs': False}).get('add_with_signs', False)
        self.combine_signs = config.get('merge', {'combine_signs': True}).get('combine_signs', True)
        self.sample = config.get('sample', False)
        self.winner_take_all = config.get('winner_take_all', True)
        self.qvars = {vname: vval for vname, vval in config['variables'].items()}
        self.links = config['links']
        self.sources = {v: k for k, v in self.links.items()}
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
        # if self.sample:
        self.control_threshold = random.random()
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
            if type(gval) is Gate:
                self.gates[gname] = gval
            else:
                self.gates[gname] = Gate(gname, gval['angle'], alternative_measure=self.alternative_measure)
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

    def run(self):
        astr = lambda x: ', '.join([str(s) for s in x]) if x else 'None'
        merge_before_measure = self.merge_before_measure
        merge_before_forward = self.merge_before_forward
        combine_signs = self.combine_signs
        normalize_inputs = self.normalize_inputs
        normalize_outputs = self.normalize_outputs
        scale_by_control = self.scale_by_control
        winner_take_all = self.winner_take_all
        add_with_signs = self.add_with_signs
        sample = self.sample

        def norm_input_particles(particles):
            pw = [p.weight for p in particles]
            normed = softmax(pw)
            for p, w in zip(particles, normed):
                p.weight = w

        def scale_by(ps, multiplier):
            for p in ps:
                p.weight = p.weight * multiplier

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
                wires = ['control', 'upper', 'lower']
                switches = ['upper', 'lower']
                other = {'upper': 'lower', 'lower': 'upper'}
                gate_positions = {wire: f'{obname}{SEP}{wire}' for wire in wires}
                inputs = {wire: [] for wire in wires}
                destinations = {wire: [] for wire in wires}
                for wire in wires: # look up sources and destinations for all wires in this gate
                    pos = gate_positions[wire]
                    destinations[wire] = self.links.get(pos)
                    if pos in self.state_dict.keys():
                        inputs[wire] = self.state_dict[pos]
                    else:
                        inputs[wire] = []
                log.info(f'GATE {gate} unfiltered inputs:')
                for wire in wires:
                    log.info(f'   {wire}_inputs= {astr(inputs[wire])} -> {destinations[wire]}')
                log.info('')

                ## Set up control input. This really just amounts to deciding whether it's present or not,
                ## setting the value of swap. If the control wire goes to another gate, make a state_dict entry.
                ## Always make a sink, whether or not it goes to another gate.
                if inputs['control']:
                    control = Particle.merge(inputs['control'])
                    swap = enough(control.probability, self.control_threshold)
                    if destinations['control'] is not None:
                        self.state_dict[destinations['control']] += inputs['control']
                    self.sinks[gate_positions['control']] = Sink(
                        gate_positions['control'],
                        control.pid,
                        presence_threshold=self.presence_threshold,
                        initial_values=inputs['control'], precision=self.precision,
                        combine_signs=combine_signs)
                else:
                    control = None
                    swap = False

                if normalize_inputs:
                    for wire in switches:
                        if inputs[wire]: norm_input_particles(inputs[wire])
                if merge_before_measure:
                    log.info('MERGING INPUTS')
                    for wire in switches:
                        inputs[wire] = merge_inputs(inputs[wire])

                ## Log inputs and set up variables for output.
                log.info(f'   INPUTS:')
                presence_str = 'PRESENT' if swap else 'NOT PRESENT'
                log.info(f'      control= {control} {presence_str}')
                for wire in switches:
                    log.info(f'      {wire}=   {astr(inputs[wire])}')
                switch_results = {wire: [] for wire in switches}
                out_dict = defaultdict(list)
                if swap:
                    log.info('   SWAPPING UPPER<->LOWER')

                ## Sequence through and measure inputs. Don't deal with control input-based swap yet.
                for input_wire in switches:
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
                            output_wires = [input_wire, input_wire, other[input_wire], other[input_wire]]
                            components = [f'c{component}{subc}' for component in ['2', '3'] for subc in ['a', 'b']]

                            for i, (sign, component, output_wire) in enumerate(zip(signs, components, output_wires)):
                                pname = f'{p_in.name}>{gate.name}.{output_wire}'
                                output_particle = Particle(
                                    pname, measurement_results[i], sign,
                                    precision=self.precision, add_with_signs=self.add_with_signs)
                                log.info(f'        ->{gate.name} {input_wire}({component})->{output_wire} {output_particle}')
                                out_dict[f'{output_wire}_{component}'] += [output_particle]
                # gather results from upper and lower INPUTS
                for input_wire in switches:
                    switch_results[input_wire] += (out_dict[f'{input_wire}_c2a'] + out_dict[f'{input_wire}_c2b'] +
                                                   out_dict[f'{input_wire}_c3a'] + out_dict[f'{input_wire}_c3b'])

                # if swap:
                #     # log.info('   SWAPPING UPPER<->LOWER')
                #     switch_results['upper'], switch_results['lower'] = outs['lower'], outs['upper']
                #     # up_outs, lo_outs = lo_outs, up_outs
                #     # upper_pos, lower_pos = lower_pos, upper_pos
                log.info(f'   OUTPUTS:')
                outputs = {wire: [] for wire in switches}
                # if winner_take_all:
                #     up_merged = Particle.merge(outs['upper'])
                #     lo_merged = Particle.merge(outs['lower'])
                #     winner = max([up_merged, lo_merged], key=lambda x: 0 if x is None else x.probability)
                #     if winner is not None:
                #         in_pos = winner.name.split('>')[-1]
                #         gate_name, input_wire = in_pos.split('.')
                #         if in_pos in self.links.keys():
                #             out_pos = self.links[in_pos]
                #             self.state_dict[out_pos].append(winner)
                #             sink = Sink(out_pos, presence_threshold=self.presence_threshold,
                #                         pid=control.pid,
                #                         precision=self.precision, combine_signs=combine_signs)
                #             self.sinks[out_pos] = sink
                #             sink.add([winner])
                #             log.info(f'        {input_wire}->')
                #             log.info(f'            {winner}')
                # else:
                for input_wire in switches:
                    output_wire = input_wire if not swap else other[input_wire]
                    out_pos = f'{gate.name}.{output_wire}'
                    if not switch_results[input_wire]:
                        outputs[output_wire] = []
                    else:
                        sink = Sink(out_pos, presence_threshold=self.presence_threshold,
                                    pid=control.pid if control else 'EMPTY',
                                    precision=self.precision, combine_signs=combine_signs)
                        self.sinks[out_pos] = sink
                        for pval in switch_results[input_wire]:
                            if enough(probability(pval.weight), self.forwarding_threshold):
                                # trace = self.particles[pval.name].trace
                                if not destinations[output_wire]:
                                    pname = f'{pval.name}>{out_pos}'
                                else:
                                    pname = f'{pval.name}>{out_pos}>{destinations[output_wire]}'
                                outputs[output_wire].append(Particle(pname, pval.weight, pval.sign,
                                                        # f'{gate.name}:{trace}->{dest}',
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

                    # for (out_pos, dest, outs, msg) in zip(
                    #         (upper_pos, lower_pos),
                    #         (udest, ldest),
                    #         (up_outs, lo_outs),
                    #         ('upper', 'lower')):
                    #     if outs is not None:
                    #         sink = Sink(out_pos, presence_threshold=self.presence_threshold,
                    #                     pid=control.pid,
                    #                     precision=self.precision, combine_signs=combine_signs)
                    #         self.sinks[out_pos] = sink
                    #         outputs = []
                    #         for pval in outs:
                    #             if pval.name != 'temp' and enough(probability(pval.weight), self.forwarding_threshold):
                    #                 # trace = self.particles[pval.name].trace
                    #                 if dest is None:
                    #                     pname = f'{pval.name}>{out_pos}'
                    #                 else:
                    #                     pname = f'{pval.name}>{out_pos}>{dest}'
                    #                 outputs.append(Particle(pname, pval.weight, pval.sign,
                    #                                         # f'{gate.name}:{trace}->{dest}',
                    #                                         precision=self.precision,
                    #                                         add_with_signs=self.add_with_signs))
                    #         log.info(f'        {msg}->')
                    #         if outputs:
                    #             if merge_before_forward:
                    #                 log.info(f'        MERGED OUTPUTS')
                    #                 if combine_signs:
                    #                     merged = Particle.merge(outputs)
                    #                     if merged is not None and enough(merged.probability, self.forwarding_threshold):
                    #                         log.info(f'           ->  {merged}')
                    #                         self.state_dict[dest].append(merged)
                    #                         sink.add([merged])
                    #                     else:
                    #                         log.info(f'           None')
                    #                 else:
                    #                     for sign_test, sign_str in [('__gt__', 'plus'), ('__lt__', 'minus')]:
                    #                         merged = Particle.merge([x for x in outputs if getattr(x, sign_test)(0)])
                    #                     if merged is not None and enough(merged.probability, self.forwarding_threshold):
                    #                         log.info(f'           {sign_str}->  {merged}')
                    #                         self.state_dict[dest].append(merged)
                    #                         sink.add([merged])
                    #                     else:
                    #                         log.info(f'           {sign_str}:  None')
                    #             else:
                    #                 sink.add(outputs)
                    #                 for output_particle in outputs:
                    #                     log.info(f'            {output_particle}')
                    #                     if dest is not None:
                    #                         self.state_dict[dest].append(output_particle)
                    #         else:
                    #             log.info(f'            NO OUTPUT')
                log.info('')

        log.info('')
        log.info('RESULTS:')
        log.info('')
        log.info(f'THRESHOLD = {self.control_threshold}')
        log.info('SINK VALUE SUMMARIES:')
        by_gates = defaultdict(dict)
        for sink_name, sink in self.sinks.items():
            sink_gate, sink_wire = sink_name.split('.')
            by_gates[sink_gate][sink_wire] = sink.vstr
            if len(sink.values.values()) == 0:
                gsum = 0
                pstr = 'None'
            else:
                gsum = Particle.merge(sink.values.values())
                pstr = f'{"+" if gsum.sign == 1 else "-"}{gsum.name.split('>')[0]}({gsum.probability:.2f})'
            log.info(f'   {sink_name} -> {sink.vstr}: {pstr}')
        log.info('')
        log.info('SINK VALUES BY GATE:')
        for gate_name, values in by_gates.items():
            log.info(f'   {self.gates[gate_name]}: {values}')
        log.info('')
        log.info('DONE!')

        return self.sinks, self.particles

    def pos_value_str(self, pos):
        values = self.state_dict[pos]
        if not values: return '0'
        merged = Particle.merge(values)
        ss = f"{'+' if merged.sign > 0 else '-'}"
        pname = merged.name.split('>')[0]
        return f'{ss}{pname}: {wstr(merged.weight, precision=self.precision)}'

