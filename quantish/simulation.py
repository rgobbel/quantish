import logging
from collections import defaultdict
from addict import Addict
import networkx as nx
from quantish.particle import Particle
from quantish.gate import DelayGate, FredkinGate, PhasePlate
from quantish.config_space import (Position, GatePort, PCoordinate,
                                     ConfigSpacePoint, ConfigSpaceRunner)
import quantish.qnumber as qn
from quantish.qnumber import qify, Complex
from quantish.util import (BRANCH_MARK, SEP, WIRES, base_name, flat_list,
                           simplify_graph, log_seq)

log = logging.getLogger('quantish')

def _prob_text(spec, rest: bool = False) -> str:
    """How a branch probability reads on its wire: the spec as written
    ('0.25', 'p'), or its complement for the second arm ('0.75',
    '1-p')."""
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        val = 1 - spec if rest else spec
        return f'{val:g}'
    return f'1-({spec})' if rest else str(spec)


class Simulation:
    def __init__(self, config):
        self.config = config
        self.title = config.title
        # optional model caption (typically the book figure's caption);
        # .get, not .caption: Addict would auto-create an empty Dict.
        # Whitespace is normalized so folded YAML blocks read as one line.
        self.caption = ' '.join(str(config.get('caption', '')).split())
        self.precision = config.get('string_precision', 2)
        # display-only: Symbolic-mode expressions longer than this fall
        # back to floats (see display.sym_or_float)
        self.max_symbolic_len = config.get('max_symbolic_len', 40)
        self.n_samples = config.get('n_samples', 0)
        self.load_variables(config)
        self.canonicalize_links(config)
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
        # the step whose configuration-space points show a gate's just-produced outputs
        self.gate_step = {g: i + 1 for i, stage in enumerate(self.run_stages) for g in stage}
        self.particles = Addict()
        self.fredkin_gates = Addict()
        self.delay_gates = Addict()
        self.phase_plates = Addict()
        self.gates = Addict()
        self.initial_coords = {}
        self.initial_point = None
        self.result_space = None
        self.all_points = None
        log.debug(' ')
        self.load_elements(config)
        self.check_roots()
        log.debug(' ')
        # diagrams use their own grouping when declared, else the run stages
        self.diagram_groups = (self.normalize_groups(config.get('diagram_groups'))
                               or self.declared_run_stages)
        self.find_pass_through_gates()
        self.gates = (self.fredkin_gates | self.delay_gates
                      | self.phase_plates)
        self.log_model(logging.DEBUG)

    def load_variables(self, config):
        """Model variables, usable by name in any angle/weight expression
        ('(q5 + q6) - theta2'). Built in declaration order so a variable
        may reference the ones above it; names that sympify already
        binds (pi, I, rad, ...) are rejected — they would shadow."""
        self.qvars = {}
        for vname, vval in config.variables.items():
            if qn.reserved_name(vname):
                raise ValueError(
                    f"variable '{vname}' shadows a builtin math name")
            self.qvars[vname] = qify(vval, self.qvars)

    def canonicalize_links(self, config):
        """A delay gate (phase plates included) has exactly one port
        (control), so links may name it bare — 'd5: d6' — with the
        '.control' implied. Canonicalize both link endpoints and build
        the reverse (sources) map."""
        delays = (set(config.get('delay_gates', []))
                  | set(config.get('phase_plates', {})))

        def canon(end):
            return f'{end}{SEP}control' if end in delays else end

        # A particle may branch: `p1: [g1.control, g2.control, 0.25]`
        # starts it in a superposition over two destinations, with the
        # given probability (default an even split) of the FIRST one.
        # The first arm is linked under the particle's own name, the
        # second under the name plus BRANCH_MARK; the probability spec
        # waits in branch_specs until the variables can resolve it.
        self.links = {}
        self.branch_specs = {}
        for src, dst in config.links.items():
            if isinstance(dst, (list, tuple)):
                arms = [d for d in dst if isinstance(d, str)]
                probs = [d for d in dst if not isinstance(d, str)]
                if src not in config.particles or len(arms) != 2 \
                        or len(probs) > 1 or len(dst) != len(arms) + len(probs):
                    raise ValueError(
                        f"link '{src}': a branching link is a particle "
                        f"with exactly two destinations and at most one "
                        f"probability ([g1.control, g2.control, 0.25]), "
                        f"got {list(dst)!r}")
                self.links[src] = canon(arms[0])
                self.links[f'{src}{BRANCH_MARK}'] = canon(arms[1])
                self.branch_specs[src] = probs[0] if probs else 0.5
            else:
                self.links[canon(src)] = canon(dst)
        self.sources = {v: k for k, v in self.links.items()}

        # Optional wire labels (the book's w₂, w₂ₐ, ... segment names).
        # A key names the LINK the label sits on, with the same
        # delay-name sugar as links:
        #   'p1' / 'g1.upper'  — the link leaving that source; an output
        #                        port with no link is a labeled stub
        #                        wire out to a sink
        #   '>g1.lower'        — the empty (null) input INTO that port,
        #                        drawn as a labeled stub wire in
        ports = {f'{g}{SEP}{w}'
                 for g in set(config.gates or []) | delays
                 for w in WIRES}
        self.wire_labels = {}
        problems = []
        for key, label in dict(config.get('wire_labels', {})).items():
            if key.startswith('>'):
                port = canon(key[1:])
                if port not in ports:
                    problems.append(f"'>{key[1:]}' names no gate port")
                elif port in self.sources:
                    problems.append(
                        f"'>{key[1:]}' has an incoming link — label its "
                        f"source ('{self.sources[port]}') instead")
                else:
                    self.wire_labels[f'>{port}'] = str(label)
            elif '>' in key and key.split('>', 1)[0] in self.branch_specs:
                # one arm of a branching particle, named by where it
                # goes: 'p1>g2.control'
                pname, dst = key.split('>', 1)
                arm = next((k for k in (pname, f'{pname}{BRANCH_MARK}')
                            if self.links.get(k) == canon(dst)), None)
                if arm is None:
                    problems.append(f"'{key}': {pname} does not branch "
                                    f"to {dst}")
                else:
                    self.wire_labels[arm] = str(label)
            else:
                src = canon(key)
                if src in self.links or src in ports:
                    self.wire_labels[src] = str(label)
                else:
                    problems.append(f"'{key}' is neither a link source "
                                    f"nor a gate port")
        if problems:
            raise ValueError('bad wire_labels:\n  ' + '\n  '.join(problems))

    def inexact_inputs(self) -> list[str]:
        """Symbolic mode only: the inputs whose values cannot be
        exact ('g1 angle', 'p2 weight' — see qnumber.inexact), so the
        results built on them will carry floating point too. Empty in
        Float mode and for a clean symbolic model."""
        if qn.CalcMode.default() != 'Symbolic':
            return []
        out = []
        for gname, gate in self.fredkin_gates.items():
            if qn.inexact(gate.theta):
                out.append(f'{gname} angle')
            if getattr(gate, 'phase', None) is not None \
                    and qn.inexact(gate.phase):
                out.append(f'{gname} phase')
        for pname, plate in getattr(self, 'phase_plates', {}).items():
            if qn.inexact(plate.phase):
                out.append(f'{pname} phase')
        for pname, particle in self.particles.items():
            if qn.inexact(particle.weight):
                out.append(f'{pname} weight')
        for pname, amps in getattr(self, 'branch_amps', {}).items():
            if any(qn.inexact(a) for a in amps):
                out.append(f'{pname} branch probability')
        return out

    def check_roots(self):
        """The zero-in-degree nodes of the link graph must be exactly the
        declared particles — as SETS: YAML declaration order and graph
        insertion order are both arbitrary and must never matter."""
        roots = set(self.graph_roots)
        pnames = set(self.particles.keys())
        if roots != pnames:
            raise ValueError(
                f'model links are inconsistent with its particles: '
                f'link-graph roots {sorted(roots)} vs particles {sorted(pnames)} '
                f'(unfed non-particles: {sorted(roots - pnames)}; '
                f'particles that are link targets: {sorted(pnames - roots)})')

    def find_pass_through_gates(self):
        """Gates wired only through their control port are pure
        pass-throughs (delays): diagrams render them as simple boxes
        instead of full Fredkin gates."""
        ports_used = defaultdict(set)
        for src, dst in self.links.items():
            for end in (src, dst):
                parts = end.split(SEP)
                if len(parts) == 2:
                    ports_used[parts[0]].add(parts[1])
        self.pass_through_gates = {g for g in self.gates.keys()
                                   if ports_used.get(g) == {'control'}}

    def log_model(self, loglevel):
        if self.caption:
            log.log(loglevel, f'caption: {self.caption}')
        log_seq('self.qvars', self.qvars, loglevel)
        log_seq('self.gates', self.gates, loglevel)
        log_seq('self.particles', self.particles, loglevel)
        log_seq('run stages',
                [[str(self.gates[gate]) for gate in gates]
                 for gates in [stage for stage in self.run_stages]],
                loglevel, enum_items=True)
        linkages = [f'{str(n)} -> {", ".join(list(self.simplified_links.successors(n))) or "NULL"}'
                    for n in nx.topological_sort(self.simplified_links)]
        log_seq('downstream links', linkages, loglevel)

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
        plates = set(config.get('phase_plates', {}))
        declared = (set(config.gates.keys())
                    | set(config.get('delay_gates', [])) | plates)
        problems = []
        both = plates & set(config.gates.keys())
        if both:
            problems.append(
                f'{sorted(both)} declared in both gates and phase_plates')
        for end in list(self.links.keys()) + list(self.links.values()):
            parts = end.split(SEP)
            if len(parts) == 2 and parts[0] in plates \
                    and parts[1] != 'control':
                problems.append(
                    f"'{end}': a phase plate only uses its control wire")
        # display_strings maps object names to display text; a key that
        # names nothing is a stale leftover (e.g. after a rename)
        nameable = declared | set(config.particles.keys())
        for dname in dict(config.get('display_strings', {})):
            if dname not in nameable:
                problems.append(
                    f"display_strings entry '{dname}' names no declared "
                    f"gate, delay gate, phase plate, or particle")
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
            if 'display_string' in pval:
                raise ValueError(
                    f"particle '{pname}': display_string moved to the "
                    f"top-level display_strings section "
                    f"({{{pname}: ...}})")
            pweight = Complex(qify(pval.get('weight', 1), self.qvars))
            new_particle = Particle(pname, pweight, qify(pval.sign, self.qvars),
                                    precision=self.precision)
            self.particles[pname] = new_particle
        gates = config.gates
        # angle_unit says how plain-number angle specs read: 'radians'
        # (the default) or 'degrees'. Degree-marked expressions ('30°',
        # '(q5+q6)°') are qify's own business — exact pi fractions in
        # Symbolic mode. Other expression specs ('rad(30)', 'pi/8', a
        # variable name) are never converted.
        degrees = str(config.get('angle_unit',
                                 'radians')).lower() == 'degrees'

        def angle_spec(v):
            if degrees and isinstance(v, (int, float)) \
                    and not isinstance(v, bool):
                # as a degree-marked spec, so qify keeps it exact in
                # Symbolic mode (30 → pi/6), not a float in radians
                return f'{v}°'
            return v

        for gname, gval in gates.items():
            # .get, not .angle: Addict would auto-create an empty Dict for
            # a missing key and crash unrecognizably inside qify
            angle = gval.get('angle')
            if angle is None or isinstance(angle, dict):
                raise ValueError(
                    f"gate '{gname}' declares no angle "
                    f"(found keys: {sorted(gval.keys())})")
            if 'display_string' in gval:
                raise ValueError(
                    f"gate '{gname}': display_string moved to the "
                    f"top-level display_strings section "
                    f"({{{gname}: ...}})")
            new_gate = FredkinGate(
                gname, qify(angle_spec(angle), self.qvars),
                phase=qify(angle_spec(gval.get('phase', 0)), self.qvars))
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
        # a phase plate's declaration is its phase spec ({φ: phi});
        # like any angle it resolves through the model's variables and
        # honors angle_unit for plain numbers
        for ppname, ppspec in dict(config.get('phase_plates', {})).items():
            if isinstance(ppspec, dict):
                raise ValueError(
                    f"phase plate '{ppname}' should map straight to its "
                    f"phase spec ({ppname}: phi), not a mapping "
                    f"(found keys: {sorted(ppspec.keys())})")
            pport = f'{ppname}{SEP}control'
            plate = PhasePlate(ppname,
                               qify(angle_spec(ppspec), self.qvars),
                               self.sources.get(pport, ''),
                               self.links.get(pport, ''))
            self.phase_plates[ppname] = plate
            self.gates[ppname] = plate
        # Branch probabilities: p for the first arm, 1-p for the second,
        # each arm's amplitude the square root (real, so the two start
        # states carry exactly those probabilities and no phase — the
        # U2 reading of a superposition; see the schema notes)
        self.branch_amps = {}
        for pname, spec in self.branch_specs.items():
            prob = qify(spec, self.qvars)
            if not 0 <= float(prob) <= 1:
                raise ValueError(
                    f"particle '{pname}': branch probability {spec!r} "
                    f"is {float(prob):g}, outside 0..1")
            self.branch_amps[pname] = (
                qify(f'sqrt({spec})', self.qvars),
                qify(f'sqrt(1 - ({spec}))', self.qvars))
            # every renderer labels the two arms with their probabilities
            # (alongside any model label), so which arm got the number is
            # never a matter of memory
            for arm, ptxt in ((pname, _prob_text(spec)),
                              (f'{pname}{BRANCH_MARK}', _prob_text(spec, rest=True))):
                lab = self.wire_labels.get(arm)
                self.wire_labels[arm] = f'{lab} ({ptxt})' if lab else ptxt
        # each particle's possible starts: [(coordinate, amplitude)]
        starts = {}
        for source, dest in links.items():
            source_parts = source.split(SEP)
            dest_gate_name, dest_port = dest.split(SEP)
            dest_wire = GatePort(dest_gate_name, dest_port)
            dest_pos = Position(endpoint=dest_wire)
            if len(source_parts) == 1:
                pname = base_name(source)
                # .get, not [..]: Addict would silently auto-create a
                # phantom for an undeclared name (e.g. a stale link after
                # renaming a particle) and crash much later
                particle = self.particles.get(pname)
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
                amp = None
                if pname in self.branch_amps:
                    amp = self.branch_amps[pname][0 if source == pname else 1]
                starts.setdefault(pname, []).append((pcoord, amp))
                log.debug(f'PARTICLE {particle}, INITIAL POSITION: {pcoord}'
                          + (f' (branch amplitude {amp})' if amp is not None else ''))
        log.debug(' ')
        # the initial configuration-space points: one per combination of
        # the particles' starts (a single point unless something
        # branches), each weighted by the product of the configured
        # particle weights and its branch amplitudes. Absent
        # (zero-weight) particles route gates by their absence but must
        # not zero the weight, so they stay out of the product.
        base_weight = qn.prod([p.weight for p in self.particles.values()
                               if not qn.zerop(p.weight)])
        combos = [[]]
        for pname, alts in starts.items():
            combos = [c + [(pname, coord, amp)] for c in combos
                      for coord, amp in alts]
        self.initial_points = []
        for combo in combos:
            weight = base_weight
            for _, _, amp in combo:
                if amp is not None:
                    weight = weight * amp
            point = ConfigSpacePoint(0, [coord for _, coord, _ in combo], weight)
            # display data: each particle's initial "component" is its
            # configured weight (see the weight-evolution graph's band glyphs)
            point.particles = {p.name: p.weight for p in self.particles.values()}
            self.initial_points.append(point)
        self.initial_point = self.initial_points[0]
        self.initial_coords = {pname: coord for pname, coord, _ in combos[0]}
        log_seq('particles', particles, logging.DEBUG)
        log_seq('gates', gates, logging.DEBUG)

    def run(self):
        result_space, all_points = ConfigSpaceRunner(self).run(self.initial_points)
        self.result_space = result_space
        self.all_points = all_points
        log.debug(' ')
        log.debug('DONE!')
        return result_space, all_points
