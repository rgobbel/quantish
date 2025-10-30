import logging
from collections import defaultdict

from quantish.particle import Particle, p_last, dest_parts
from quantish.gate import Gate
from quantish.sink import Sink
# from quantish.config_space import ConfigurationSpace, Measurement
from quantish.qnumber import Real, qify, softmax, probability, Complex
from quantish.util import topo_sort, SEP, wstr, enough, to_float
from quantish.config_space import GateState, Coordinate, WIRES, SWITCH_WIRES, default_wires
import random

log = logging.getLogger('quantish')

other = {'upper': 'lower', 'lower': 'upper'}

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
        self.downstream = config['links']
        self.upstream = {v: k for k, v in self.downstream.items()}
        self.particles = {}
        self.sinks = {}
        self.phases = config['phases']
        self.gates = {}
        self.inputs = defaultdict(list)
        self.initial_values = defaultdict(dict)
        self.normalize_outputs = config.get('normalize_weights', {}).get('output', False)
        self.normalize_inputs = config.get('normalize_weights', {}).get('input', False)
        self.scale_by_control = config.get('normalize_weights', {}).get('by_control', False)
        self.control_threshold = Real(config.get('probability_threshold', {}).get('control', 0))
        self.forwarding_threshold = Real(config.get('probability_threshold', {}).get('forwarding', 0))
        self.presence_threshold = Real(config.get('probability_threshold', {}).get('presence', 0))
        self.control_threshold = random.random()
        log.info(f'merge before measure={self.merge_before_measure}, merge before forwarding={self.merge_before_forward}, combine signs={self.combine_signs}')
        log.info(f'normalize inputs={self.normalize_inputs}, normalize outputs={self.normalize_outputs}')
        log.info('')
        for gname, gval in config['gates'].items():
            self.gates[gname] = Gate(gname, gval['angle'], alternative_measure=self.alternative_measure)
            # self.inputs[gname] += [{'control': [], 'upper': [], 'lower': []}]
        for pname, pval in config['particles'].items():
            pweight = Complex(pval['weight'])
            position = self.downstream.get(pname)
            if position:
                gate_name, wire = position.split('.')
                if gate_name not in self.initial_values.keys():
                    self.initial_values[gate_name] = {'control': [], 'upper': [], 'lower': []}
                particle = Particle(pname, pweight, qify(pval['sign']),
                    precision=self.precision,
                    add_with_signs=self.add_with_signs)
                self.initial_values[gate_name][wire] = [particle]
                log.info(f'PARTICLE: {particle.pid} -> {position}')
        self.order = topo_sort(self.downstream)
        log.info('')
        log.info(f'{self.qvars=}')
        log.info(f'{self.phases=}')
        log.info(f'{self.gates=}')
        log.info(f'{self.particles=}')
        log.info('self.initial_values=')
        for gname, ginput in self.initial_values.items():
            log.info(f'   {gname}, initial_values=:')
            for k, v in ginput.items():
                log.info(f'      {k}={[x.ps(with_id=True) for x in list(v)]}')
        log.info(f'{self.control_threshold=:.1f}, {self.forwarding_threshold=:.1f}, {self.presence_threshold=:.1f}')
        log.info(f'{self.normalize_inputs=}, {self.normalize_outputs=}')
        log.info('')
        log.info(f'EXECUTION ORDER: {", ".join(self.order)}')
        log.info('')

    def run(self):
        def astr(x):
            if not x:
                return 'None'
            elif isinstance(x, Particle):
                return x.pid
            else:
                contents = ', '.join([p.ps(with_id=True) for p in x])
                return f'[{contents}]'
        merge_before_measure = self.merge_before_measure
        merge_before_forward = self.merge_before_forward
        combine_signs = self.combine_signs
        normalize_inputs = self.normalize_inputs
        normalize_outputs = self.normalize_outputs
        scale_by_control = self.scale_by_control
        winner_take_all = self.winner_take_all
        add_with_signs = self.add_with_signs
        sample = self.sample

        for obname in self.order:
            if obname in self.gates.keys():
                gate_name = obname
                gate = self.gates[gate_name]
                inputs = self.inputs.get(gate_name, [default_wires()])
                initial_values = self.initial_values.get(gate_name)
                if initial_values:
                    for inp in inputs:
                        for wire in WIRES:
                            if wire in initial_values.keys():
                                inp[wire] = initial_values[wire]
                log.info(f'GATE {gate}, {len(inputs)} input{"s" if len(inputs) > 1 else ""}:')
                gate_positions = {wire: f'{gate_name}{SEP}{wire}' for wire in WIRES}
                destinations = default_wires()
                for wire in WIRES:  # look up sources and destinations for all wires in this gate
                    pos = gate_positions[wire]
                    destinations[wire] = self.downstream.get(pos)
                dest_gates = set([x.split('.')[0] for x in destinations.values() if x])

                for i, input_dict in enumerate(inputs):

                    outputs = []
                    if input_dict['control']:
                        control = input_dict['control'][0]
                    else:
                        control = Particle(f'{gate_name}_DEFAULT', weight=0, sign=1)

                    log.info(f'   inputs[{i}]:')
                    for wire in WIRES:
                        log.info(f'      {wire:8s} = {astr(input_dict[wire])}')
                    log.info(f'   destinations[{i}]:')
                    for wire in WIRES:
                        log.info(f'      {wire:7s} -> {destinations[wire]}')
                    log.info('')

                    unswapped_results = {wire: [] for wire in SWITCH_WIRES}
                    # result_dict = defaultdict(list)
                    ## Sequence through and measure inputs. Don't deal with upper/lower swap yet.
                    for input_switch in SWITCH_WIRES:
                        if input_dict[input_switch]:
                            result = self.one_switch_result(gate, input_switch, input_dict[input_switch])
                            unswapped_results['upper'] += result['upper']
                            unswapped_results['lower'] += result['lower']

                    ## Log inputs and set up variables for output.
                    swap = enough(control.probability, self.control_threshold)
                    if swap: log.info('   SWAPPING UPPER<->LOWER')
                    log.info(f'   MEASUREMENTS:')
                    presence_str = 'PRESENT' if swap else 'NOT PRESENT'
                    log.info(f'      control= {control.ps(with_id=True)} {presence_str}')

                    # add outputs from one input, possibly swapped upper/lower
                    outputs.append({
                        'control': [control],# if to_float(control.probability) > 0 else [],
                        'upper': unswapped_results['lower' if swap else 'upper'],
                        'lower': unswapped_results['upper' if swap else 'lower']})

                    log.info('   SUCCESSOR STATES:')
                    ## all outputs have been calculated. Forward them to the next stage
                    for output in outputs:
                        dest_result = defaultdict(dict) # new Particles, created from outputs
                        for source_wire in WIRES:
                            pos = f'{gate_name}.{source_wire}'
                            destination = destinations[source_wire]
                            if destination:
                                dest_gate_name, dest_wire = destination.split('.')
                                if output[source_wire]:
                                    dest_source = output[source_wire]
                                    dest_pos = f'{dest_gate_name}.{dest_wire}'
                                    if isinstance(dest_source, Particle):
                                        raise RuntimeError(f'dest_source should be a list, but is {dest_source}')
                                        # dest_name = f'{output[source_wire].name}_{i}'
                                        # dest_particle = Particle(dest_name, dest_source.weight, dest_source.sign)
                                        # dest_result[dest_gate_name][dest_wire] = dest_particle
                                    elif isinstance(dest_source, list):
                                        result_list = [
                                            Particle(f'{x.name}', x.weight, x.sign,
                                                     add_with_signs=self.add_with_signs,
                                                     precision=self.precision) for x in dest_source]
                                        dest_result[dest_gate_name][dest_wire] = result_list
                                    else:
                                        raise RuntimeError(f'Invalid source: {dest_source}')
                            else:
                                if source_wire == 'control':
                                    sink_name = f'{control.pid}-{pos}'
                                    sink = Sink(sink_name, control.pid, initial_values=[control],
                                                precision=self.precision, presence_threshold=self.presence_threshold,
                                                combine_signs=self.combine_signs)
                                    self.sinks[sink_name] = sink
                                elif len(output[source_wire]) > 0:
                                    if pos not in self.sinks.keys():
                                        sink_name = f'{control.pid}-{pos}'
                                        sink = Sink(sink_name, control.pid, initial_values=output[source_wire])
                                        self.sinks[sink_name] = sink
                                    else:
                                        self.sinks[pos].add(output[source_wire])

                        assert set(dest_result.keys()) == dest_gates
                        for dest_gate_name in dest_gates:
                            successor_inputs = []
                            if dest_gate_name in self.inputs.keys():
                                existing_inputs = self.inputs[dest_gate_name]
                            else:
                                existing_inputs = [default_wires()]
                            successor_dict = {}
                            for successor_input in existing_inputs:
                                gate_result = dest_result[dest_gate_name]
                                for wire in WIRES: # fill in initial values, if any
                                    if wire not in gate_result.keys() and wire in successor_input.keys():
                                        gate_result[wire] = successor_input[wire]
                                if gate_result['control']:
                                    control_result = gate_result['control']
                                    for control_successor in control_result:
                                        successor_dict = self.collect_successor_switches(dest_gate_name, gate_result)
                                        successor_dict['control'] += [control_successor]
                                        successor_inputs.append(successor_dict)
                                else:
                                    successor_dict = self.collect_successor_switches(dest_gate_name, gate_result)
                                    successor_inputs.append(successor_dict)

                                log.info(f'      ->{dest_gate_name}')
                                for successor in successor_inputs:
                                    for wire in WIRES:
                                        if wire in successor.keys():
                                            log.info(f'         {wire:7s}: {successor[wire]}')
                                    log.info('')
                            self.inputs[dest_gate_name] = successor_inputs
                                # print(f'{successor_inputs=}')
                                # for wire in WIRES:
                                #     if wire in dest_wires:
                                #         print(f'{dest_gate_name}[{wire}]: {dest_result.get(wire)=}, {wire=} IN')
                                #     else:
                                #         print(f'{dest_gate_name}[{wire}]: {dest_result.get(wire)=}, {wire=} NOT IN')


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

    def one_switch_result(self, gate, input_switch, input):
        result = {'upper': [], 'lower': []}
        for p_in in input:
            if p_in:  # and to_float(p_in.probability) > 0:  # Zero probability particles are discarded
                log.info(f'      {p_in.ps(with_id=True)} ->')
                # get raw measurements
                measurement_results = gate.measure(p_in)

                signs = [p_in.sign, -p_in.sign, p_in.sign, -p_in.sign]
                output_switches = [input_switch, input_switch, other[input_switch], other[input_switch]]
                components = [f'c{component}{subc}' for component in ['2', '3'] for subc in ['a', 'b']]

                for i, (sign, component, output_switch) in enumerate(
                        zip(signs, components, output_switches)):
                    pname = f'{p_in.name}>{gate.name}.{output_switch}'
                    output_particle = Particle(
                        pname, measurement_results[i], sign,
                        precision=self.precision, add_with_signs=self.add_with_signs)
                    log.info(
                        f'        ->{gate.name} {input_switch}->{output_switch}({component}) {output_particle.ps(with_id=True)}')
                    result[output_switch].append(output_particle)
                    # result_dict[f'{output_switch}_{component}'].append(output_particle)
        return result

    def collect_successor_switches(self, dest_gate_name, gate_result):
        successor_dict = {'control': [], 'upper': [], 'lower': []}
        for wire in SWITCH_WIRES:
            if wire in gate_result.keys():
                if not isinstance(gate_result[wire], list):
                    print(f'oops: {gate_result[wire]=}')
                for result_particle in gate_result[wire]:
                    successor_dict[wire] += [
                        Particle(f'{result_particle.name}>{dest_gate_name}.{wire}',
                                 weight=result_particle.weight,
                                 sign=result_particle.sign,
                                 precision=self.precision,
                                 add_with_signs=self.add_with_signs
                                 )]
        return successor_dict

    def pos_value_str(self, pos):
        values = self.state_dict[pos]
        if not values: return '0'
        merged = Particle.merge(values)
        ss = f"{'+' if merged.sign > 0 else '-'}"
        pname = merged.name.split('>')[0]
        return f'{ss}{pname}: {wstr(merged.weight, precision=self.precision)}'

