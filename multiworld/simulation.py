from collections import defaultdict, deque
import logging
from addict import Addict
import networkx as nx
from scipy.cluster.hierarchy import DisjointSet
from multiworld.particle import Particle
from multiworld.gate import DelayGate, FredkinGate
from multiworld.config_space import (Position, GatePort, PCoordinate,
                                     ConfigSpacePoint, ConfigSpaceRunner, ConfigSpace,
                                     LIMBO, stage_step_encode)
import multiworld.qnumber as qn
from multiworld.qnumber import Real, qify, softmax, Complex
from multiworld.util import (SEP, sstr, WIRES, SWITCH_WIRES, OTHER, flat_list,
                             expand_graph, simplify_graph, log_seq)

log = logging.getLogger('multiworld')

class ExecutionStage:
    def __init__(self, gate, step):
        self.gate = gate
        self.step = step
        self.particles = []
        self.inputs = []
        self.outputs = []

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
        self.sample = config.get('sample', False)
        self.n_samples = config.get('n_samples', 0)
        self.delete_zeros = config.get('delete_zeros', False)
        self.skip_zeros = config.get('skip_zeros', True)
        self.disappear_zeros = config.get('disappear_zeros', False)
        self.disallow_excess_weights = config.get('disallow_excess_weights', False)
        self.qvars = {vname: vval for vname, vval in config.variables.items()}
        self.links = config.links
        self.sources = {v: k for k, v in self.links.items()}
        self.expanded_links = expand_graph(self.links)
        self.simplified_links = simplify_graph(self.links)
        self.graph_roots = [node for node, degree in self.simplified_links.in_degree() if degree == 0]
        self.gate_step = Addict()
        self.step_gate = {}
        self.gate_stage = defaultdict(int)
        self.stage_gate = {}
        self.step_particles = defaultdict(set)
        self.discards = defaultdict(list)
        self.run_stages = list(nx.topological_generations(self.simplified_links))[1:]
        # self.run_stages = list(config.run_groups.values())
        # self.run_stages = [['g1', 'g2'], ['g3'], ['g4'], ['g5', 'g6']]
        # self.run_stages = [['g1'], ['g2'], ['g3'], ['g4'], ['g5'], ['g6']]
        self.run_order = flat_list(self.run_stages)
        self.run_stages = [[x] for x in self.run_order]
        self.stages = []
        self.particles = Addict()
        self.particle_weights = Addict()
        self.sinks = Addict()
        self.run_results = Addict()
        self.fredkin_gates = Addict()
        self.delay_gates = Addict()
        self.gates = Addict()
        self.initial_coords = {}
        self.initial_point = None
        self.result_space = None
        log.info(' ')
        self.load_elements(config)
        assert self.graph_roots == list(self.particles.keys())
        for pname in self.particles.keys():
            self.particle_weights[pname] = DisjointSet([self.particles[pname]])
            self.particles[pname].active_gates = (
                set([self.expanded_links.nodes[dn].get('gate')
                     for dn in [n for n in nx.descendants(self.expanded_links, pname)]
                     if self.expanded_links.nodes[dn].get('direction') == 'input']))
            for gname in self.particles[pname].active_gates:
                self.gates[gname].input_particles.add(pname)
        # step = 1
        log.info(' ')
        self.diagram_groups = config.get('diagram_groups')
        if self.diagram_groups is None:
            self.diagram_groups = {f'{"_".join(group)}': group for group in self.run_stages}
        self.gates = self.fredkin_gates | self.delay_gates
        log_seq('self.qvars', self.qvars)
        log_seq('self.gates', self.gates)
        log_seq('self.particles', self.particles)
        log_seq('run stages',
                [[str(self.gates[gate]) for gate in gates]
                 for gates in [stage for stage in self.run_stages]],
                enum_items=True)
        log_seq('run order',
                [(str(self.gates[stage.gate]),
                  f'{", particles: " if stage.particles 
                  else ""}{", ".join([str(particle)
                                      for particle in stage.particles])}')
                 for stage in self.stages])
        # log.info('run order:')
        # for i, stage in enumerate(self.stages):
        #     log.info(f'   {i}: {self.gates[stage.gate]}{", particles: " if stage.particles else ""}{", ".join([str(particle) for particle in stage.particles])}')
        # log.info(' ')
        # log.info('downstream links:')
        linkages = [f'{str(n)} -> {", ".join(list(self.simplified_links.successors(n))) or "NULL"}'
                    for n in nx.topological_sort(self.simplified_links)]
        log_seq('downstream links', linkages)
        # for link in linkages:
        #     log.info(f'   {link}')
        # log.info(' ')

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
        log.debug(f'config.links:')
        for k, v in config.links.items():
            log.debug(f'   {k}: {v}')
        log.debug(' ')
        # log.debug(f'{config.links=}')
        particles = config.particles
        for pname, pval in particles.items():
            pweight = Complex(qify(pval.weight))
            new_particle = Particle(pname, pweight, qify(pval.sign),
                                    precision=self.precision, trace=['ORIGIN'])
            self.particles[pname] = new_particle
        gates = config.gates
        delay_gates = config.delay_gates
        for i, gate_name in enumerate(self.run_order):
            if gate_name in gates.keys() or gate_name in delay_gates:
                self.gate_step[gate_name] = i
                self.step_gate[i] = gate_name
        for i, stage in enumerate(self.run_stages):
            for j, gate_name in enumerate(stage):
                gs = stage_step_encode(i, j)
                self.gate_stage[gate_name] = gs
                self.stage_gate[gs] = gate_name
        for gname, gval in gates.items():
            new_gate = FredkinGate(gname, gval.angle)
            self.fredkin_gates[gname] = new_gate
            self.gates[gname] = new_gate
        for dgname in config.get('delay_gates', []):
            dgate = DelayGate(dgname, self.sources[dgname], self.links[dgname])
            self.delay_gates[dgname] = dgate
            self.gates[dgname] = dgate
        self.stages = [ExecutionStage(stage, i) for i, stage in enumerate(self.run_order)]
        for source, dest in links.items():
            source_parts = source.split(SEP)
            dest_gate_name, dest_port = dest.split(SEP)
            dest_wire = GatePort(dest_gate_name, dest_port)
            dest_pos = Position(endpoint=dest_wire)
            if len(source_parts) == 1:
                particle = self.particles[source]
                particle.trace = [f'{dest_pos}']
                pcoord = PCoordinate(particle.name, particle.sign, dest_pos)
                self.initial_coords[source] = pcoord
                log.info(f'PARTICLE {particle}, INITIAL POSITION: {pcoord}')
        log.info(' ')
        # the initial world's weight is the product of the configured particle weights
        initial_weight = qn.prod([p.weight for p in self.particles.values()])
        self.initial_point = ConfigSpacePoint(0, list(self.initial_coords.values()), initial_weight)
        self.stages[0].inputs = [self.initial_point]
        log_seq('particles', particles, logging.DEBUG)
        log_seq('gates', gates, logging.DEBUG)
        # log.debug(f'{particles=}, {gates=}')

    def run(self):
        result_space, all_points = ConfigSpaceRunner(self).run(self.initial_point)
        self.result_space = result_space
        self.all_points = all_points
        log.info(' ')
        log.info('DONE!')
        return result_space, all_points #, self.sinks, self.particles

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
