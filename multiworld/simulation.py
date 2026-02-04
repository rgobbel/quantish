from collections import defaultdict, deque
import logging
from addict import Addict
import networkx as nx
from multiworld.particle import Particle
from multiworld.gate import DelayGate, FredkinGate
from multiworld.config_space import (PCoordValue, Position, Wire, PCoordinate,
                                     ConfigSpacePoint, ConfigSpaceRunner, ConfigSpace,
                                     LIMBO)
import multiworld.qnumber as qn
from multiworld.qnumber import Real, qify, softmax, Complex
from multiworld.util import (SEP, sstr, WIRES, SWITCH_WIRES, OTHER, flat_list,
                             expand_graph, simplify_graph)

log = logging.getLogger('multiworld')

class Simulation:
    def __init__(self, config):
        def default_bool(field, subfield, default=False):
            val = config.get(field)
            if val is None:
                config[field] = Addict()
                config[field][subfield] = default
            elif val.get(subfield) is None:
                config[field][subfield] = default
            return config[field][subfield]
        self.state_dict = defaultdict(list)
        self.config = config
        self.title = config.title
        self.symbolic = config.get('symbolic', False)
        self.precision = config.get('string_precision', 2)
        self.add_with_signs = config.get('add_with_signs', False)
        self.always_forward_switch_weights = default_bool('always_forward','switch_weights')
        self.always_forward_control_weights = default_bool('always_forward', 'control_weights')
        self.alternative_measure = config.get('alternative_measure', False)
        self.merge_before_measure = default_bool('merge','before_measure')
        self.merge_before_forward = default_bool('merge','before_forwarding')
        self.add_with_signs = default_bool('merge','add_with_signs')
        self.combine_signs = default_bool('merge','combine_signs')
        self.combine_names = default_bool('merge','combine_names')
        self.sample = config.get('sample', False)
        self.n_samples = config.get('n_samples', 0)
        self.qvars = {vname: vval for vname, vval in config.variables.items()}
        self.links = config.links
        self.sources = {v: k for k, v in self.links.items()}
        self.expanded_links = expand_graph(self.links)
        self.simplified_links = simplify_graph(self.links)
        self.gate_step = Addict()
        self.run_groups = list(nx.topological_generations(self.simplified_links))[1:]
        self.run_order = flat_list(self.run_groups)
        self.particles = Addict()
        self.sinks = Addict()
        self.run_results = Addict()
        self.fredkin_gates = Addict()
        self.delay_gates = Addict()
        self.gates = Addict()
        self.pcvals = Addict()
        self.normalize_output = default_bool('normalize_weights', 'output')
        self.normalize_input = default_bool('normalize_weights','input')
        log.info(f'merge before: measure={self.merge_before_measure}, forward={self.merge_before_forward}')
        log.info(f'always forward: switch weights={self.always_forward_switch_weights}, '
                 f'control weights={self.always_forward_control_weights}')
        log.info(f'combine: signs={self.combine_signs}, names={self.combine_names},'
                 f' add with signs={self.add_with_signs}')
        log.info(f'normalize: before measure={self.normalize_input}, before forwarding={self.normalize_output}')
        log.info('')
        self.load_elements(config)
        step = 1
        log.info('')
        self.initial_point = ConfigSpacePoint(step, tuple(self.pcvals.values()))
        self.diagram_groups = config.get('diagram_groups')
        if self.diagram_groups is None:
            self.diagram_groups = {f'{"_".join([gname for gname in group])}': group for group in self.run_groups}
        self.gates = self.fredkin_gates | self.delay_gates
        self.initial_world = [self.initial_point]
        self.world_state = self.initial_world
        self.all_worlds = self.initial_world
        log.info(f'{self.qvars=}')
        # log.info(f'run stages={", ".join([f"{v}" for v in self.run_stages.values()])}')
        log.info(f'{self.gates=}')
        log.info(f'{self.particles=}')
        log.info(f'{self.normalize_input=}, {self.normalize_output=}')
        log.info('')
        log.info('run order:')
        for i, gate_name in enumerate(self.run_order):
            log.info(f'   {i+1}: {self.gates[gate_name]}')
        log.info('')
        log.info('downstream links:')
        linkages = [f'{n} -> {", ".join(list(self.simplified_links.successors(n))) or "NULL"}'
                    for n in nx.topological_sort(self.simplified_links)]
        for link in linkages:
            log.info(f'   {link}')
        log.info('')

    def particle_gates(self, links, particle):
        queue = deque()
        queue.append(links[particle])
        pgates = []
        while len(queue) > 0:
            pos = queue.popleft()
            gate, wire = pos.split(SEP)
            if gate not in pgates:
                pgates.append(gate)
            if links.get(pos):
                next_pos = links[pos]
                queue.append(next_pos)
                if wire != 'control':
                    next_other = links.get(f'{gate}{SEP}{OTHER[wire]}')
                    if next_other:
                        queue.append(next_other)
        return pgates

    def load_elements(self, config):
        links = config.links
        log.debug(f'{config.links=}')
        particles = config.particles
        gates = config.gates
        delay_gates = config.delay_gates
        for i, gate_name in enumerate(self.run_order):
            if gate_name in gates.keys() or gate_name in delay_gates:
                self.gate_step[gate_name] = i+1
        for gname, gval in gates.items():
            new_gate = FredkinGate(gname, gval.angle, start_step=self.gate_step[gname], sim=self)
            self.fredkin_gates[gname] = new_gate
            self.gates[gname] = new_gate
        for dgname in config.get('delay_gates', []):
            dgate = DelayGate(dgname, start_step=self.gate_step[dgname], sim=self)
            self.delay_gates[dgname] = dgate
            self.gates[dgname] = dgate
        for pname, pval in particles.items():
            pweight = Complex(qify(pval.weight))
            new_particle = Particle(pname, pweight, qify(pval.sign), precision=self.precision)
            self.particles[pname] = new_particle
        for source, dest in links.items():
            source_parts = source.split(SEP)
            dest_gate_name, dest_port = dest.split(SEP)
            dest_wire = Wire(dest_gate_name, dest_port)
            dest_pos = Position(endpoint=dest_wire)
            if len(source_parts) == 1:
                particle = self.particles[source]
                dest_gate = self.gates[dest_gate_name]
                particle.next_step = dest_gate.start_step
                pcoord = PCoordinate(particle.next_step, particle.pkey, dest_pos)
                self.pcvals[source] = PCoordValue(pcoord=pcoord, particle=particle)
                log.info(f'PARTICLE {particle}, INITIAL POSITION: {self.pcvals[source].pcoord}, START STEP: {particle.next_step}')
        log.debug(f'{particles=}, {gates=}')

    def run(self):
        astr = lambda x: ', '.join([str(s) for s in x]) if x else 'None'
        merge_before_measure = self.merge_before_measure
        merge_before_forward = self.merge_before_forward
        combine_signs = self.combine_signs
        combine_names = self.combine_names
        normalize_input = self.normalize_input
        normalize_output = self.normalize_output

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

        result_space = ConfigSpaceRunner(self).run(self.initial_point)
        log.info('')

        log.info('DONE!')

        return result_space #, self.sinks, self.particles

    def pos_value_str(self, pos, val_type='results'):
        parts = pos.split('.')
        if len(parts) == 1:
            merged = self.particles[parts]
        else:
            gname, gwire = parts
            gate = self.gates[gname]
            values = getattr(gate, val_type)[gwire]
            if not values: return None
            merged = Particle.merge(values)
            ss = sstr(merged.sign)
            pname = merged.name.split('>')[0]
        return f'{merged}' #f'{ss}{pname}: {wstr(merged.weight, precision=self.precision)}'
