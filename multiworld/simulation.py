from collections import defaultdict, deque
import logging
from addict import Addict
import networkx as nx
from multiworld.particle import Particle
from multiworld.gate import DelayGate, FredkinGate
from multiworld.config_space import (PCoordValue, Position, Wire, PCoordinate,
                                     ConfigSpacePoint, ConfigSpaceRunner, ConfigSpace,
                                     LIMBO)
import matplotlib.pyplot as plt
import multiworld.qnumber as qn
from multiworld.qnumber import Real, qify, softmax, Complex
from multiworld.util import (SEP, sstr, WIRES, SWITCH_WIRES, OTHER,
                             path_lengths, normalize_list, topo_sort, expand_graph, simplify_graph)

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
        self.run_order = list(nx.topological_generations(self.simplified_links))
        self.particles = Addict()
        self.sinks = Addict()
        self.run_results = Addict()
        self.run_stages = config.run_stages
        self.fredkin_gates = Addict()
        self.delay_gates = Addict()
        self.gates = Addict()
        self.pcvals = Addict()
        self.gate_depths = Addict()
        self.particle_depths = Addict()
        self.depths = Addict()
        self.ppositions = Addict()
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
        # for pname, pval in config.particles.items():
        #     pweight = Complex(pval.weight)
        #     new_particle = (
        #         Particle(pname, pweight, qify(pval.sign),
        #                  precision=self.precision))
        #     self.particles[pname] = new_particle
        #     dest_gate, dest_wire = self.links[pname].split(SEP)
        #     coord = PCoordinate(step, new_particle.pkey, Position(endpoint=Wire(dest_gate, dest_wire)))
        #     self.pcvals[pname] = PCoordValue(pcoord=coord, particle=new_particle)
        #     log.info(f'PARTICLE: {self.particles[pname]}')
        log.info('')
        # coords = []
        # for particle_name, particle in self.particles.items():
        #     particle_initial = self.links[particle_name]
        #     gate, port = particle_initial.split(SEP)
        #     pos = Position(endpoint=Wire(gate, port))
        #     pkey = particle.pkey
        #     coord = PCoordinate(step, pkey, pos)
        #     coord_val = PCoordValue(coord, particle)
        #     coords.append(coord_val)
        self.initial_point = ConfigSpacePoint(step, tuple(self.pcvals.values()))
        # for gname, gval in config.gates.items():
        #     self.fredkin_gates[gname] = FredkinGate(
        #         gname, gval.angle, sim=self)
        # for dgname in config.get('delay_gates', []):
        #     self.delay_gates[dgname] = DelayGate(dgname, sim=self)
        self.diagram_groups = config.get('diagram_groups', self.run_stages)
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
        for i, gate_group in enumerate(self.run_order[1:]):
            ggstr = ', '.join([str(self.gates[gname]) for gname in gate_group])
            log.info(f'   {i+1}: {ggstr}')
        log.info('')
        log.info('downstream links:')
        linkages = [f'{n} -> {", ".join(list(self.simplified_links.successors(n))) or "NULL"}'
                    for n in nx.topological_sort(self.simplified_links)]
        for link in linkages:
            log.info(f'   {link}')
        log.info('')

    def enumerate_paths(self, links, start, path=None):
        # Add the current node to the path
        if path is None:
            path = []
        path = path + [start]

        # If the current node is the end node, we've found a complete path
        if not links.get(start):
            return [path]

        # If the start node is not in the graph or has no neighbors, return an empty list
        if start not in links:
            return []

        paths = []
        # Recurse for all neighbors of the current node
        neighbors = links.get(start)
        if neighbors is not None:
            if not isinstance(neighbors, list): neighbors = [neighbors]
            for node in neighbors:
                # Ensure that nodes are not revisited within a single path (automatic in DAGs if logic is sound)
                if node not in path:
                    newpaths = self.enumerate_paths(links, node, path)
                    for newpath in newpaths:
                        paths.append(newpath)

        return paths

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

    def bfs(self):
        links = Addict()
        links.root = list(self.config.particles)
        visited = set('root')
        queue = deque(['root'])
        while len(queue) > 0:
            node = queue.popleft()

    def load_elements(self, config):
        links = config.links
        log.debug(f'{config.links=}')
        particles = config.particles
        gates = config.gates
        delay_gates = config.delay_gates
        for i, gate_names in enumerate(self.run_order):
            for gate_name in gate_names:
                if gate_name in gates.keys() or gate_name in delay_gates:
                    self.gate_step[gate_name] = i
        list_links = Addict()
        # for pname, pval in particles.items():
        #     pweight = Complex(pval.weight)
        #     new_particle = (
        #         Particle(pname, pweight, qify(pval.sign),
        #                  precision=self.precision))
        #     self.particles[pname] = new_particle
        #     self.pcvals.pname = PCoordValue(pcoord=LIMBO, particle=new_particle)
        #     log.info(f'PARTICLE: {self.particles[pname]}')
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
        for origin in links.keys():
            depth = 0
            while links.get(origin):
                next_destination = links[origin]
                gate, port = next_destination.split(SEP)
                if port in SWITCH_WIRES:
                    list_links[origin] = [next_destination, f'{gate}{SEP}{OTHER[port]}']
                else:
                    list_links[origin] = [next_destination]
                log.debug(f'list_links[{origin}]={list_links[origin]}')
                depth += 1
                origin = next_destination
        log.debug(f'{list_links=}')

        for particle in particles:
            queue = deque([particle])
            depth = 0
            while queue:
                log.debug(f'{queue=}')
                for _ in range(len(queue)):
                    node = queue.popleft()
                    self.ppositions[particle] += [node]
                    node_parts = node.split(SEP)
                    if len(node_parts) == 2:
                        gate, port = node.split(SEP)
                        if gate not in self.gate_depths.keys():
                            self.gate_depths[gate] = {particle: depth}
                        elif particle not in self.gate_depths[gate].keys():
                            self.gate_depths[gate][particle] = depth
                        else:
                            self.gate_depths[gate][particle] = max(self.gate_depths[gate][particle], depth)
                        if particle not in self.particle_depths.keys():
                            self.particle_depths[particle] = {gate: depth}
                        elif gate not in self.particle_depths[particle].keys():
                            self.particle_depths[particle][gate] = depth
                        else:
                            self.particle_depths[particle][gate] = max(self.particle_depths[particle][gate], depth)
                    children = list_links.get(node)
                    if children: queue += children
                depth += 1
            self.depths[particle] = depth
        log.debug(f'{self.depths=}')
        log.debug(f'{self.gate_depths=}')
        log.debug(f'{self.particle_depths=}')
        log.debug(f'{self.ppositions=}')

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

        world = ConfigSpace(self.initial_point)
        runner = ConfigSpaceRunner(self)
        # runner.run_gates(self.initial_point)
        result_space, steps = runner.run(self.initial_point)
        final_points = [v for k, v in result_space.index.items() if int(k.split('/')[0]) == steps]
        log.info(f'finished after {steps} steps, {len(result_space.index)} total points in final config space, {len(final_points)} points from last step')
        log.info('')
        by_result_position = Addict()
        # if len(final_points) > 0:
        #     for cs_point_list in final_points:
        #         if len(cs_point_list) > 1:
        #             log.warn(f'more than one! {cs_point_list}')
        #         cs_point = cs_point_list[0]
        #         for k, pcv in cs_point.pcvals.items():
        #             pos = pcv.pcoord.position.origin
        #             if pos.gate not in by_result_position.keys():
        #                 by_result_position[pos.gate] = {pos.port: pcv.particle}
        #             else:
        #                 if pos.port not in by_result_position[pos.gate].keys():
        #                     by_result_position[pos.gate][pos.port] = pcv.particle
        #                 else:
        #                     by_result_position[pos.gate][pos.port].weight += pcv.particle.weight
        if len(final_points) > 0:
            pad_len = [0] * len(final_points[0].pcvals.values())
            for point in final_points:
                pcvals = list(point.pcvals.values())
                positions = [p.pcoord.position.origin for p in pcvals]
                particles = [p.particle for p in pcvals]
                logstr = [f'{particle}@{pos}' for particle, pos in zip(particles, positions)]
                for i, s in enumerate(logstr):
                    pad_len[i] = max(pad_len[i], len(s))
            log.info('final results:')
            for point in final_points:
                pcvals = list(point.pcvals.values())
                positions = [p.pcoord.position.origin for p in pcvals]
                particles = [p.particle for p in pcvals]
                logstr = '  |  '.join([f'{f"{particle}@{pos}":<{pad_len[i]}}' for i, (particle, pos) in enumerate(zip(particles, positions))])
                log.info(f'   {logstr}')
            exe_graph = nx.MultiDiGraph()
            exe_graph.add_nodes_from(result_space.index.values())
            exe_nodes = list(exe_graph.nodes)
            cur_nodes = len(exe_nodes)
            new_nodes = True
            while new_nodes:
                new_nodes = False
                for node in exe_nodes:
                    for succ in node.successors:
                        if succ not in exe_graph:
                            new_nodes = True
                            exe_graph.add_node(succ)
                    for pred in node.predecessors:
                        if pred not in exe_graph:
                            new_nodes = True
                            exe_graph.add_node(pred)
                exe_nodes = list(exe_graph.nodes)
            for node in exe_nodes:
                for succ in node.successors:
                    exe_graph.add_edge(node, succ)
            layers = defaultdict(list)
            for p in exe_graph.nodes:
                layers[p.key[0]] += [p]
            pos = nx.multipartite_layout(exe_graph, layers)
            nx.draw(exe_graph, pos=pos)
            plt.draw()
            plt.show()
                # log.info(point)
            # for k, v in by_result_position.items():
            #     if 'upper' in by_result_position[k].keys() and 'lower' in by_result_position[k].keys():
            #         ps = [by_result_position[k].upper, by_result_position[k].lower]
            #         merged = Particle.merge(ps)
            #         sumstr = f' (sum: {merged})'
            #     else:
            #         sumstr = ''
            #     log.info(f'   {k}: {v}{sumstr}')
        else:
            log.info('NO RESULTS')
        log.info('')

        # for g in self.gates.values():
        #     if type(g) is FredkinGate:
        #         for wire in WIRES:
        #             out_pos = f'{g.name}{SEP}{wire}'
        #             if g.weights and g.weights[wire]:
        #                 self.run_results[out_pos] = g.weights[wire]
        #             else:
        #                 self.run_results[out_pos] = None
        # log.info('RESULTS:')
        # for k, v in self.run_results.items():
        #     if v is not None:
        #         log.info(f'   {k}: {v}')
        # log.info('')

        # log.info('RESULT VALUES BY GATE:')
        # gate_results = defaultdict(dict)
        # for k, v in self.run_results.items():
        #     gate, wire = k.split('.')
        #     if self.combine_signs:
        #         gate_results[gate][wire] = Particle.merge(v)
        #     else:
        #         pluses = [Particle.merge([x for x in v if x.sign > 0])]
        #         pluses = [] if not pluses else pluses
        #         minuses = [Particle.merge([x for x in v if x.sign < 0])]
        #         minuses = [] if not minuses else minuses
        #         merged = pluses + minuses
        #         gate_results[gate][wire] = merged
        # gate_names = list(sorted(gate_results.keys()))
        # for gate in gate_names:
        #     vals_list = [f'{k}: {v}' for k, v in gate_results[gate].items()]
        #     valstr = ', '.join(vals_list)
        #     log.info(f'   {gate}: {valstr}')
        # log.info('')
        log.info('DONE!')

        return result_space, steps #, self.sinks, self.particles

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
