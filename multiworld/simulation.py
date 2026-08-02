import logging
from collections import defaultdict
from addict import Addict
import networkx as nx
from multiworld.particle import Particle
from multiworld.gate import DelayGate, FredkinGate
from multiworld.config_space import (Position, GatePort, PCoordinate,
                                     ConfigSpacePoint, ConfigSpaceRunner)
import multiworld.qnumber as qn
from multiworld.qnumber import qify, Complex
from multiworld.util import SEP, flat_list, simplify_graph, log_seq

log = logging.getLogger('multiworld')

class Simulation:
    def __init__(self, config):
        self.config = config
        self.title = config.title
        self.symbolic = config.get('symbolic', False)
        self.precision = config.get('string_precision', 2)
        self.sample = config.get('sample', False)
        self.n_samples = config.get('n_samples', 0)
        self.qvars = {vname: vval for vname, vval in config.variables.items()}
        self.links = config.links
        self.sources = {v: k for k, v in self.links.items()}
        self.simplified_links = simplify_graph(self.links)
        self.graph_roots = [node for node, degree in self.simplified_links.in_degree() if degree == 0]
        self.topo_stages = list(nx.topological_generations(self.simplified_links))[1:]
        self.run_order = flat_list(self.topo_stages)
        self.run_stages = [[x] for x in self.run_order]
        # the step whose worlds show a gate's just-produced outputs
        self.gate_step = {g: i + 1 for i, stage in enumerate(self.run_stages) for g in stage}
        self.particles = Addict()
        self.fredkin_gates = Addict()
        self.delay_gates = Addict()
        self.gates = Addict()
        self.initial_coords = {}
        self.initial_point = None
        self.result_space = None
        self.all_points = None
        log.debug(' ')
        self.load_elements(config)
        assert self.graph_roots == list(self.particles.keys())
        log.debug(' ')
        self.diagram_groups = config.get('diagram_groups')
        if self.diagram_groups is None:
            self.diagram_groups = {f'{"_".join(group)}': group for group in self.topo_stages}
        self.gates = self.fredkin_gates | self.delay_gates
        log_seq('self.qvars', self.qvars, logging.DEBUG)
        log_seq('self.gates', self.gates, logging.DEBUG)
        log_seq('self.particles', self.particles, logging.DEBUG)
        log_seq('run stages',
                [[str(self.gates[gate]) for gate in gates]
                 for gates in [stage for stage in self.run_stages]],
                logging.DEBUG, enum_items=True)
        linkages = [f'{str(n)} -> {", ".join(list(self.simplified_links.successors(n))) or "NULL"}'
                    for n in nx.topological_sort(self.simplified_links)]
        log_seq('downstream links', linkages, logging.DEBUG)

    def load_elements(self, config):
        links = config.links
        log.debug(f'config.links:')
        for k, v in config.links.items():
            log.debug(f'   {k}: {v}')
        log.debug(' ')
        particles = config.particles
        for pname, pval in particles.items():
            pweight = Complex(qify(pval.get('weight', 1)))
            new_particle = Particle(pname, pweight, qify(pval.sign),
                                    precision=self.precision)
            self.particles[pname] = new_particle
        gates = config.gates
        for gname, gval in gates.items():
            new_gate = FredkinGate(gname, gval.angle)
            self.fredkin_gates[gname] = new_gate
            self.gates[gname] = new_gate
        for dgname in config.get('delay_gates', []):
            dgate = DelayGate(dgname, self.sources[dgname], self.links[dgname])
            self.delay_gates[dgname] = dgate
            self.gates[dgname] = dgate
        for source, dest in links.items():
            source_parts = source.split(SEP)
            dest_gate_name, dest_port = dest.split(SEP)
            dest_wire = GatePort(dest_gate_name, dest_port)
            dest_pos = Position(endpoint=dest_wire)
            if len(source_parts) == 1:
                particle = self.particles[source]
                pcoord = PCoordinate(particle.name, particle.sign, dest_pos)
                self.initial_coords[source] = pcoord
                log.debug(f'PARTICLE {particle}, INITIAL POSITION: {pcoord}')
        log.debug(' ')
        # the initial world's weight is the product of the configured particle weights
        initial_weight = qn.prod([p.weight for p in self.particles.values()])
        self.initial_point = ConfigSpacePoint(0, list(self.initial_coords.values()), initial_weight)
        log_seq('particles', particles, logging.DEBUG)
        log_seq('gates', gates, logging.DEBUG)

    def run(self):
        result_space, all_points = ConfigSpaceRunner(self).run(self.initial_point)
        self.result_space = result_space
        self.all_points = all_points
        log.debug(' ')
        log.debug('DONE!')
        return result_space, all_points

    def pos_value_str(self, pos, val_type='results'):
        """Display string for a gate output port after a run: the marginal
        probability of each (particle, sign) that exited through the port,
        summed over the worlds at the step where the gate fired. Returns
        None when nothing exited there (or before a run)."""
        if self.all_points is None:
            return None
        parts = pos.split(SEP)
        if len(parts) != 2:
            return None
        gname, gport = parts
        step = self.gate_step.get(gname)
        if step is None:
            return None
        port = GatePort(gname, gport)
        by_pkey = defaultdict(float)
        try:
            for point in self.all_points.index.values():
                if point.step != step:
                    continue
                for pname, coord in point.coords.items():
                    if coord.position.origin == port:
                        by_pkey[str(coord.pkey)] += float(point.probability)
        except (TypeError, ValueError):
            return None  # symbolic weights with free symbols
        if not by_pkey:
            return None
        return ', '.join(f'{pkey}: {prob:.{self.precision}f}'
                         for pkey, prob in sorted(by_pkey.items()))