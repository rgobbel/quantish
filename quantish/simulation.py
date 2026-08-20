import cmath
import logging
import math
from collections import defaultdict
from addict import Addict
import networkx as nx
from quantish.particle import Particle
from quantish.gate import DelayGate, FredkinGate
from quantish.config_space import (Position, GatePort, PCoordinate,
                                     ConfigSpacePoint, ConfigSpaceRunner)
import quantish.qnumber as qn
from quantish.qnumber import qify, Complex
from quantish.util import SEP, flat_list, simplify_graph, log_seq

log = logging.getLogger('quantish')

class Simulation:
    def __init__(self, config):
        self.config = config
        self.title = config.title
        self.symbolic = config.get('symbolic', False)
        self.precision = config.get('string_precision', 2)
        self.sample = config.get('sample', False)
        self.n_samples = config.get('n_samples', 0)
        # Model variables, usable by name in any angle/weight expression
        # ('(q5 + q6) - theta2'). Built in declaration order so a variable
        # may reference the ones above it; names that sympify already
        # binds (pi, I, rad, ...) are rejected — they would shadow.
        self.qvars = {}
        for vname, vval in config.variables.items():
            if qn.reserved_name(vname):
                raise ValueError(
                    f"variable '{vname}' shadows a builtin math name")
            self.qvars[vname] = qify(vval, self.qvars)
        # A delay gate has exactly one port (control), so links may name it
        # bare — 'd5: d6' — with the '.control' implied.
        _delays = set(config.get('delay_gates', []))
        def _canon(end):
            return f'{end}{SEP}control' if end in _delays else end
        self.links = {_canon(src): _canon(dst)
                      for src, dst in config.links.items()}
        self.sources = {v: k for k, v in self.links.items()}
        self.validate_wiring(config)
        self.simplified_links = simplify_graph(self.links)
        self.graph_roots = [node for node, degree in self.simplified_links.in_degree() if degree == 0]
        self.topo_stages = list(nx.topological_generations(self.simplified_links))[1:]
        # Run order comes ONLY from the model's declared run_stages;
        # diagram grouping (diagram_groups) is a separate concern and is
        # never used for scheduling. A model without run_stages is a bug.
        self.declared_run_stages = self.normalize_groups(config.get('run_stages'))
        if not self.declared_run_stages:
            raise ValueError(
                f"model '{config.title}' declares no run_stages — "
                f"run order must be explicit")
        self.run_stages = self.grouped_run_stages(self.declared_run_stages)
        self.run_order = flat_list(self.run_stages)
        # the step whose CS points show a gate's just-produced outputs
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
        # diagrams use their own grouping when declared, else the run stages
        self.diagram_groups = (self.normalize_groups(config.get('diagram_groups'))
                               or self.declared_run_stages)
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
    def normalize_groups(groups):
        """Normalize a declared gate grouping ({name: gate-or-list}) to
        {name: [gates]}. None when nothing declared."""
        if not groups:
            return None
        return {name: ([g] if isinstance(g, str) else list(g))
                for name, g in groups.items()}

    def grouped_run_stages(self, groups):
        """Execution stages from the model's declared run_stages: gates in
        one stage fire logically simultaneously. A declared stage with
        internal dependencies contributes one sub-stage per dependency
        layer (a 'couple: [g3, g4]' where g3 feeds g4 becomes [g3], [g4]).
        Everything keyed on step numbers — the weight-evolution graph,
        port displays, path sampling — is stage-based, matching the
        book's figures rather than any serialized implementation order."""
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
        # Run order comes only from the declared run_stages, so a gate the
        # model wires up but forgets to schedule (delay gates included)
        # would otherwise never fire — or fire at some arbitrary implicit
        # time. Refuse instead.
        missing = [g for g in topo_order if g not in fired]
        if missing:
            raise ValueError(
                f"run_stages omits linked gates {missing} — every gate, "
                f"delay gates included, must be scheduled explicitly")
        return stages

    def validate_wiring(self, config):
        """A declared element the links never use is a modeling mistake —
        catch it at load, loudly and all at once, rather than mid-run or
        (worse) never: particles must feed a gate input, every gate must
        have at least one input, and every link must target a declared
        gate. Works from the raw config so it can run before anything is
        built on top of the links."""
        declared = set(config.gates.keys()) | set(config.get('delay_gates', []))
        problems = []
        for pname in config.particles.keys():
            if pname not in self.links:
                problems.append(
                    f"particle '{pname}' is not linked to any gate input")
        for src, dst in self.links.items():
            dest_gate = dst.split(SEP)[0]
            if dest_gate not in declared:
                problems.append(
                    f"link '{src}: {dst}' targets undeclared gate "
                    f"'{dest_gate}'")
        fed = {dst.split(SEP)[0] for dst in self.links.values()}
        for gname in declared:
            if gname not in fed:
                problems.append(f"gate '{gname}' has no inputs")
        if problems:
            raise ValueError('bad model wiring:\n  ' + '\n  '.join(sorted(problems)))

    def load_elements(self, config):
        links = self.links
        log.debug(f'links:')
        for k, v in links.items():
            log.debug(f'   {k}: {v}')
        log.debug(' ')
        particles = config.particles
        for pname, pval in particles.items():
            pweight = Complex(qify(pval.get('weight', 1), self.qvars))
            new_particle = Particle(pname, pweight, qify(pval.sign, self.qvars),
                                    precision=self.precision)
            self.particles[pname] = new_particle
        gates = config.gates
        for gname, gval in gates.items():
            # .get, not .angle: Addict would auto-create an empty Dict for
            # a missing key and crash unrecognizably inside qify
            angle = gval.get('angle')
            if angle is None or isinstance(angle, dict):
                raise ValueError(
                    f"gate '{gname}' declares no angle "
                    f"(found keys: {sorted(gval.keys())})")
            new_gate = FredkinGate(gname, qify(angle, self.qvars))
            self.fredkin_gates[gname] = new_gate
            self.gates[gname] = new_gate
        for dgname in config.get('delay_gates', []):
            # .get: a missing source/sink is reported by validate_wiring,
            # which runs after loading and names every problem at once
            dport = f'{dgname}{SEP}control'
            dgate = DelayGate(dgname, self.sources.get(dport, ''),
                              self.links.get(dport, ''))
            self.delay_gates[dgname] = dgate
            self.gates[dgname] = dgate
        for source, dest in links.items():
            source_parts = source.split(SEP)
            dest_gate_name, dest_port = dest.split(SEP)
            dest_wire = GatePort(dest_gate_name, dest_port)
            dest_pos = Position(endpoint=dest_wire)
            if len(source_parts) == 1:
                # .get, not [..]: Addict would silently auto-create a
                # phantom for an undeclared name (e.g. a stale link after
                # renaming a particle) and crash much later
                particle = self.particles.get(source)
                if particle is None:
                    raise ValueError(
                        f"link source '{source}' is neither a gate port nor "
                        f"a declared particle ({sorted(self.particles.keys())})")
                if qn.zerop(particle.weight):
                    # a zero-weight particle marks an ABSENT occupant (e.g.
                    # fig 4.4's control): no coordinate, so control-presence
                    # checks read False and no weight branches from it
                    log.debug(f'PARTICLE {particle} has zero weight: absent')
                    continue
                pcoord = PCoordinate(particle.name, particle.sign, dest_pos)
                self.initial_coords[source] = pcoord
                log.debug(f'PARTICLE {particle}, INITIAL POSITION: {pcoord}')
        log.debug(' ')
        # the initial config space point's weight is the product of the configured particle weights
        # absent (zero-weight) particles route gates by their absence but
        # must not zero the initial CS point's weight, so they stay out of the product
        initial_weight = qn.prod([p.weight for p in self.particles.values()
                                  if not qn.zerop(p.weight)])
        self.initial_point = ConfigSpacePoint(0, list(self.initial_coords.values()), initial_weight)
        # display data: each particle's initial "component" is its
        # configured weight (see the weight-evolution graph's band glyphs)
        self.initial_point.particles = {p.name: p.weight for p in self.particles.values()}
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
        the CS points at `step`, one line per particle:

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
        amps = defaultdict(complex)                       # pname -> Σ of CS-point weights
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
        was arriving at the port in the previous step's CS points (coordinate
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

    def cs_point_sort_key(self, point):
        """Canonical display order for a whole CS point: compare CS points by
        their coordinates taken in coord_sort_key order, so rows group by
        gate, then port (upper first), then sign (+ first)."""
        return tuple(sorted(self.coord_sort_key(c) for c in point.coords.values()))

    def port_particle_amps(self, step, port, end='origin'):
        """Per-particle summed amplitude (qnumber Complex) at `port` over
        the CS points at `step`. end='origin' sums what exited the
        port, end='endpoint' what is arriving at it. Empty dict when
        nothing matches."""
        amps = {}
        if self.all_points is None:
            return amps
        for point in self.all_points.index.values():
            if point.step != step or point.cancelled:
                continue
            for pname, coord in point.coords.items():
                where = (coord.position.origin if end == 'origin'
                         else coord.position.endpoint)
                if where == port:
                    amps[pname] = (amps[pname] + point.weight
                                   if pname in amps else point.weight)
        return amps

    def amp_value_str(self, pname, amp):
        """Display block for one particle's summed amplitude at a port:

            p1 +0.75,+0.43i
            Pr: 0.75 (0.56+0.19) ∠+30º

        Line 1: the amplitude as a signed (real, imaginary) pair, the
        imaginary part suffixed i. Line 2: the combined probability, its
        decomposition into real- and imaginary-part contributions, and
        the phase in degrees. (In this circuit family the real part is
        the plus-sign component and the imaginary part the minus-sign
        component.)"""
        prec = self.precision
        re_v = qn.to_float(amp.real)
        im_v = qn.to_float(amp.imag)
        pr = qn.to_float(qn.probability(amp))
        pr_re = qn.to_float(qn.probability(amp.real))
        pr_im = qn.to_float(qn.probability(amp.imag))
        deg = qn.to_float(amp.phase.degrees)
        return (f'{pname} {re_v:+.{prec}f},{im_v:+.{prec}f}i\n'
                f'Pr: {pr:.{prec}f} ({pr_re:.{prec}f}+{pr_im:.{prec}f}) ∠{deg:+.0f}º')

    def pos_value_str(self, pos):
        """Display string for a gate output port after a run: one
        amp_value_str block per particle present. Returns None when
        nothing exited there."""
        parts = pos.split(SEP)
        if len(parts) != 2:
            return None
        gname, gport = parts
        step = self.gate_step.get(gname)
        if step is None:
            return None
        amps = self.port_particle_amps(step, GatePort(gname, gport))
        if not amps:
            return None
        return '\n'.join(self.amp_value_str(p, amps[p]) for p in sorted(amps))