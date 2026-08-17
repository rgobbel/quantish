import cmath
import logging
import math
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
        # one group resolution drives both the stage schedule and diagram
        # labels: explicit diagram_groups, else the model's run groups
        # (either historical key), else auto-named topological stages
        self.declared_groups = self.resolve_groups(config)
        self.run_stages = self.grouped_run_stages(self.declared_groups)
        self.run_order = flat_list(self.run_stages)
        # the step whose classical worlds show a gate's just-produced outputs
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
        # The zero-in-degree nodes of the link graph must be exactly the
        # declared particles — as SETS: YAML declaration order and graph
        # insertion order are both arbitrary and must never matter.
        _roots = set(self.graph_roots)
        _pnames = set(self.particles.keys())
        if _roots != _pnames:
            raise ValueError(
                f'model links are inconsistent with its particles: '
                f'link-graph roots {sorted(_roots)} vs particles {sorted(_pnames)} '
                f'(unfed non-particles: {sorted(_roots - _pnames)}; '
                f'particles that are link targets: {sorted(_pnames - _roots)})')
        log.debug(' ')
        self.diagram_groups = self.declared_groups
        if self.diagram_groups is None:
            self.diagram_groups = {f'{"_".join(group)}': group for group in self.topo_stages}
        # Gates wired only through their control port are pure pass-throughs
        # (delays): diagrams render them as simple boxes instead of full
        # Fredkin gates.
        _ports_used = defaultdict(set)
        for _src, _dst in self.links.items():
            for _end in (_src, _dst):
                _parts = _end.split(SEP)
                if len(_parts) == 2:
                    _ports_used[_parts[0]].add(_parts[1])
        self.pass_through_gates = {g for g in self.gates.keys()
                                   if _ports_used.get(g) == {'control'}}
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

    @staticmethod
    def resolve_groups(config):
        """The model's declared gate grouping: diagram_groups when present,
        else run_groups / run_stages (both historical key names). Values
        are normalized to lists. None when the model declares nothing."""
        for key in ('diagram_groups', 'run_groups', 'run_stages'):
            groups = config.get(key)
            if groups:
                return {name: ([g] if isinstance(g, str) else list(g))
                        for name, g in groups.items()}
        return None

    def grouped_run_stages(self, groups):
        """Execution stages: gates in one stage fire logically
        simultaneously (the engine treats them so, as does the reference
        implementation). Without diagram_groups the stages are the
        topological generations of the link graph; with them, each group
        contributes one stage per dependency layer inside it (fig 4.17's
        'couple' group becomes the stages [g3], [g4]). Everything keyed on
        step numbers — the weight-evolution graph, port marginals, path
        sampling — is therefore stage-based, matching the book's figures
        rather than any serialized implementation order."""
        if not groups:
            return [list(stage) for stage in self.topo_stages]
        topo_order = flat_list(self.topo_stages)
        gate_set = set(topo_order)
        deps = {g: {p for p in self.simplified_links.predecessors(g) if p in gate_set}
                for g in topo_order}
        stages = []
        fired = set()
        for group in groups.values():
            remaining = [g for g in group if g in gate_set]
            while remaining:
                ready = [g for g in remaining if not (deps.get(g, set()) - fired)]
                if not ready:
                    # group order conflicts with the topology; don't stall
                    ready = list(remaining)
                stages.append(ready)
                fired |= set(ready)
                remaining = [g for g in remaining if g not in ready]
        for stage in self.topo_stages:
            leftover = [g for g in stage if g not in fired]
            if leftover:
                stages.append(leftover)
                fired |= set(leftover)
        return stages

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
        # the initial config space point's weight is the product of the configured particle weights
        initial_weight = qn.prod([p.weight for p in self.particles.values()])
        self.initial_point = ConfigSpacePoint(0, list(self.initial_coords.values()), initial_weight)
        # display data: the initial "factor" of each particle is its
        # configured weight (see the weight-evolution graph's band glyphs)
        self.initial_point.factors = {p.name: p.weight for p in self.particles.values()}
        log_seq('particles', particles, logging.DEBUG)
        log_seq('gates', gates, logging.DEBUG)

    def run(self):
        result_space, all_points = ConfigSpaceRunner(self).run(self.initial_point)
        self.result_space = result_space
        self.all_points = all_points
        log.debug(' ')
        log.debug('DONE!')
        return result_space, all_points

    def port_summary(self, step, port, end='origin'):
        """Formatted per-particle summary of the amplitudes at `port` over
        the worlds at `step`, one line per particle:

            p1+: 0.56, p1-: 0.19 | Σ: 0.75 ∠+30º

        The per-sign values are marginal probabilities (Σ|w|²). Σ is the
        aggregate: the two signed component amplitudes summed as complex
        numbers, shown as squared magnitude and phase — the port's
        wire-weight view. end='origin' summarizes what exited the port,
        end='endpoint' what is arriving at it. None when nothing matches
        (or symbolic weights with free symbols)."""
        if self.all_points is None:
            return None
        probs = defaultdict(lambda: defaultdict(float))   # pname -> sign -> Σ|w|²
        amps = defaultdict(complex)                       # pname -> Σ of world weights
        try:
            for point in self.all_points.index.values():
                if point.step != step or point.cancelled:
                    continue
                for pname, coord in point.coords.items():
                    where = (coord.position.origin if end == 'origin'
                             else coord.position.endpoint)
                    if where == port:
                        probs[pname][str(coord.sign)] += float(point.probability)
                        amps[pname] += complex(point.weight)
        except (TypeError, ValueError):
            return None  # symbolic weights with free symbols
        if not probs:
            return None
        lines = []
        for pname in sorted(probs.keys()):
            sign_parts = ', '.join(
                f'{pname}{sign}: {prob:.{self.precision}f}'
                for sign, prob in sorted(probs[pname].items(), reverse=True))
            agg = amps[pname]
            phase_deg = math.degrees(cmath.phase(agg)) if abs(agg) > 1e-12 else 0.0
            lines.append(f'{sign_parts}\nΣ: {abs(agg) ** 2:.{self.precision}f} '
                         f'∠{phase_deg:+.0f}º')
        return '\n'.join(lines)

    def gate_io(self):
        """Per-step gate traffic: a list of rows {step, gate, port, input,
        output} for every gate port that saw a particle — inputs are what
        was arriving at the port in the previous step's worlds (coordinate
        endpoints), outputs what exited it when the gate fired (coordinate
        origins), both in port_summary format."""
        rows = []
        if self.all_points is None:
            return rows
        for i, stage in enumerate(self.run_stages):
            step = i + 1
            for gname in stage:
                for wire in ('control', 'upper', 'lower'):
                    port = GatePort(gname, wire)
                    arriving = self.port_summary(step - 1, port, end='endpoint')
                    leaving = self.port_summary(step, port, end='origin')
                    if arriving is None and leaving is None:
                        continue
                    rows.append({'step': step, 'gate': gname, 'port': wire,
                                 'input': arriving or '—',
                                 'output': leaving or '—'})
        return rows

    # display ordering of a gate's ports: the switch wires the book's
    # figures read top-down, then the pass-through control
    PORT_DISPLAY_ORDER = {'upper': 0, 'lower': 1, 'control': 2}

    def coord_sort_key(self, coord):
        """Canonical display order for one particle coordinate: gate (in
        logical evaluation order), then port (upper, lower, control), then
        particle name, then sign (+ before −). Yields e.g.
        p3+@g4.upper, p3+@g4.lower, p1+@g7.upper, p1-@g7.upper, ..."""
        where = coord.position.origin or coord.position.endpoint
        gate = where.gate if where is not None else None
        port = where.port if where is not None else None
        return (self.gate_step.get(gate, len(self.run_stages) + 1),
                self.run_order.index(gate) if gate in self.run_order
                else len(self.run_order),
                self.PORT_DISPLAY_ORDER.get(port, len(self.PORT_DISPLAY_ORDER)),
                coord.name,
                -int(coord.sign))

    def world_sort_key(self, point):
        """Canonical display order for a whole classical world: compare worlds by
        their coordinates taken in coord_sort_key order, so rows group by
        gate, then port (upper first), then sign (+ first)."""
        return tuple(sorted(self.coord_sort_key(c) for c in point.coords.values()))

    def pos_value_str(self, pos):
        """Display string for a gate output port after a run (see
        port_summary). Returns None when nothing exited there."""
        parts = pos.split(SEP)
        if len(parts) != 2:
            return None
        gname, gport = parts
        step = self.gate_step.get(gname)
        if step is None:
            return None
        return self.port_summary(step, GatePort(gname, gport), end='origin')