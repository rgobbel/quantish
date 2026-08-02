import logging
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
        self.run_stages = list(nx.topological_generations(self.simplified_links))[1:]
        self.run_order = flat_list(self.run_stages)
        self.run_stages = [[x] for x in self.run_order]
        self.particles = Addict()
        self.fredkin_gates = Addict()
        self.delay_gates = Addict()
        self.gates = Addict()
        self.initial_coords = {}
        self.initial_point = None
        self.result_space = None
        self.all_points = None
        log.info(' ')
        self.load_elements(config)
        assert self.graph_roots == list(self.particles.keys())
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
        linkages = [f'{str(n)} -> {", ".join(list(self.simplified_links.successors(n))) or "NULL"}'
                    for n in nx.topological_sort(self.simplified_links)]
        log_seq('downstream links', linkages)

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
                log.info(f'PARTICLE {particle}, INITIAL POSITION: {pcoord}')
        log.info(' ')
        # the initial world's weight is the product of the configured particle weights
        initial_weight = qn.prod([p.weight for p in self.particles.values()])
        self.initial_point = ConfigSpacePoint(0, list(self.initial_coords.values()), initial_weight)
        log_seq('particles', particles, logging.DEBUG)
        log_seq('gates', gates, logging.DEBUG)

    def run(self):
        result_space, all_points = ConfigSpaceRunner(self).run(self.initial_point)
        self.result_space = result_space
        self.all_points = all_points
        log.info(' ')
        log.info('DONE!')
        return result_space, all_points

    def pos_value_str(self, pos, val_type='results'):
        # TODO(roadmap: Mermaid after-diagrams): recompute port values as
        # marginal probabilities over the final worlds in result_space,
        # instead of the per-gate particle state that no longer exists.
        return None