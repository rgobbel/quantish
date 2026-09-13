import logging
from collections import defaultdict
from copy import deepcopy

import networkx as nx
from addict import Dict as Addict

import quantish.qnumber as qn
from quantish.config_space import (
    ConfigSpacePoint,
    ConfigSpaceRunner,
    GatePort,
    PCoordinate,
    Position,
)
from quantish.gate import DelayGate, FredkinGate, PhasePlate
from quantish.particle import Particle, sign_components
from quantish.qnumber import qify
from quantish.util import (
    BRANCH_MARK,
    SEP,
    WIRES,
    Sign,
    base_name,
    flat_list,
    log_seq,
    simplify_graph,
)

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
    def __init__(self, config, inert=(), absent=()):
        # runtime knobs, never model-file keys: `inert` names gates to
        # switch off (wires, applied once the gates exist, in
        # load_elements); `absent` names particles to leave out of the
        # run — a null input, the loader's zero-weight particle: the
        # particle stays declared and drawn, but never enters, so the
        # gates it would have fed see an empty wire
        self.inert_requested = tuple(str(g) for g in inert)
        self.absent = [str(p) for p in absent]
        if self.absent:
            config = deepcopy(config)
            for pname in self.absent:
                if pname not in (config.get('particles') or {}):
                    raise ValueError(f"absent names no declared particle: '{pname}'")
                config.particles[pname].weight = 0
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
        # Run order comes from the model's declared run_stages; diagram
        # grouping (diagram_groups) is a separate concern and is never
        # used for scheduling. A model that declares none runs in wiring
        # order — one stage per topological layer of the link graph —
        # and says so (run_stages_derived, for the apps to show)
        self.declared_run_stages = self.normalize_groups(config.get('run_stages'))
        self.run_stages_derived = not self.declared_run_stages
        if self.run_stages_derived:
            self.declared_run_stages = {
                f'stage_{i}': sorted(layer) for i, layer in enumerate(self.topo_stages, 1)}
            log.warning(
                f"model '{config.title}' declares no run_stages: running in wiring "
                f"order — " + ' | '.join(f"{n}: {', '.join(gs)}"
                                        for n, gs in self.declared_run_stages.items()))
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
        # A particle's link may instead map each destination to a weight
        # spec — `p1: {g1.upper: '3/16; 1/16i', g1.lower: '9/16; -3/16i'}`
        # — the general form: one complex amplitude per (destination,
        # sign), the shape of a gate's four-way output fed back in. The
        # specs wait in arm_specs (a list in arm order, resolved with
        # the variables in load_elements).
        self.links = {}
        self.branch_specs = {}
        self.arm_specs = {}
        for src, dst in config.links.items():
            if isinstance(dst, dict):
                arms = list(dst)
                if src not in config.particles or not 1 <= len(arms) <= 2:
                    raise ValueError(
                        f"link '{src}': a weighted link is a particle with "
                        f"one or two destinations, each mapped to a weight "
                        f"({{g1.upper: '3/16; 1/16i', g1.lower: '9/16; "
                        f"-3/16i'}}), got {dict(dst)!r}")
                for arm, mark in zip(arms, ('', BRANCH_MARK)):
                    self.links[f'{src}{mark}'] = canon(arm)
                self.arm_specs[src] = [dst[arm] for arm in arms]
            elif isinstance(dst, (list, tuple)):
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
                    # the stub grew a wire: the wire inherits the stub's
                    # label (unless the wire's source is labeled itself)
                    src = self.sources[port]
                    if src in self.wire_labels or src in config.get('wire_labels', {}):
                        log.warning(f"wire label '>{key[1:]}': {port} now has an "
                                    f"incoming link from {src}, which carries its "
                                    f"own label; the stub label is dropped")
                    else:
                        self.wire_labels[src] = str(label)
                else:
                    self.wire_labels[f'>{port}'] = str(label)
            elif '>' in key and key.split('>', 1)[0] in (
                    self.branch_specs.keys() | self.arm_specs.keys()):
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
            if any(qn.inexact(w) for w in particle.components.values()):
                out.append(f'{pname} weight')
        for pname, amps in getattr(self, 'arm_comps', {}).items():
            if any(qn.inexact(w) for comps in amps for w in comps.values()):
                out.append(f'{pname} link weight')
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
        self.pass_through_gates = {g for g in self.gates
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
        linkages = [f'{n!s} -> {", ".join(list(self.simplified_links.successors(n))) or "NULL"}'
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
        for pname in config.particles:
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

    def entry_components(self, source: str) -> dict:
        """The nonzero amplitudes a particle enters the circuit with
        along one link source ('p1', or 'p1|2' for a second arm), by
        sign — what a circuit-entry port shows."""
        pname = base_name(source)
        particle = self.particles[pname]
        arm_i = 0 if source == pname else 1
        if pname in self.arm_comps:
            comps = {s: particle.weight * w
                     for s, w in self.arm_comps[pname][arm_i].items()}
        else:
            comps = dict(particle.components)
            if pname in self.branch_amps:
                amp = self.branch_amps[pname][arm_i]
                comps = {s: w * amp for s, w in comps.items()}
        return {s: w for s, w in sorted(comps.items(), reverse=True)
                if not qn.zerop(w)}

    def load_elements(self, config):
        links = self.links
        log.debug('links:')
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
            sign = pval.get('sign')
            if sign is not None:
                sign = Sign(int(qn.to_float(qify(sign, self.qvars))))
            try:
                comps = sign_components(pval.get('weight', 1), sign, self.qvars)
            except ValueError as exc:
                raise ValueError(f"particle '{pname}': {exc}") from None
            if pname in self.arm_specs and (sign is not None or len(comps) > 1):
                raise ValueError(
                    f"particle '{pname}': its link carries the weights "
                    f"per destination, so declare no sign and at most a "
                    f"plain weight factor here")
            self.particles[pname] = Particle(pname, components=comps,
                                             precision=self.precision)
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
                raise ValueError(  # noqa: TRY004 — model errors are ValueErrors (tests rely on it)
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
        # inert gates: wires. Every particle passes straight through,
        # sign, weight, and phase untouched — a runtime knob (the lab's
        # gate toggles, its virtual screens), never a model-file key
        self.inert = list(self.inert_requested)
        for gname in self.inert:
            if gname not in self.gates:
                raise ValueError(f"inert names no declared gate: '{gname}'")
            self.gates[gname].inert = True
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
        # weighted arms: each arm's spec resolves to {sign: amplitude};
        # the wire shows the spec as written (alongside any model label)
        self.arm_comps = {}
        for pname, specs in self.arm_specs.items():
            try:
                self.arm_comps[pname] = [sign_components(spec, None, self.qvars)
                                         for spec in specs]
            except ValueError as exc:
                raise ValueError(f"link '{pname}': {exc}") from None
            for arm, spec in zip((pname, f'{pname}{BRANCH_MARK}'), specs):
                lab = self.wire_labels.get(arm)
                self.wire_labels[arm] = f'{lab} ({spec})' if lab else str(spec)
            self.particles[pname].arms = self.arm_comps[pname]
        # each particle's possible starts: [(coordinate, amplitude)] —
        # one per (destination, sign) with a nonzero amplitude, the
        # amplitude being the particle's weight component for that sign
        # times the arm's (branch amplitude or weighted-link component).
        # A particle with no start is ABSENT (e.g. fig 4.4's zero-weight
        # control): no coordinate, so control-presence checks read False
        # and no weight branches from it.
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
                arm_i = 0 if source == pname else 1
                if pname in self.arm_comps:
                    factor = particle.weight   # a plain factor, default 1
                    comps = {s: factor * w
                             for s, w in self.arm_comps[pname][arm_i].items()}
                else:
                    comps = dict(particle.components)
                    if pname in self.branch_amps:
                        amp = self.branch_amps[pname][arm_i]
                        comps = {s: w * amp for s, w in comps.items()}
                for sign, amp in sorted(comps.items(), reverse=True):
                    if qn.zerop(amp):
                        continue
                    pcoord = PCoordinate(particle.name, sign, dest_pos)
                    starts.setdefault(pname, []).append((pcoord, amp))
                    log.debug(f'PARTICLE {particle}, INITIAL POSITION: {pcoord}'
                              f' (amplitude {amp})')
        for pname, particle in self.particles.items():
            if pname not in starts:
                log.debug(f'PARTICLE {particle} has zero weight: absent')
        # the constraint, checked per particle before any run: the
        # squared magnitudes of a particle's start amplitudes sum to 1
        # (the initial points are the cartesian product of the
        # particles' starts, so the total is the product of these)
        for pname, alts in starts.items():
            norm = qn.to_float(sum(qn.probability(amp) for _, amp in alts))
            if abs(norm - 1) > 1e-6:
                raise ValueError(
                    f"particle '{pname}': the squared magnitudes of its "
                    f"weights sum to {norm:.6g}, not 1")
        log.debug(' ')
        # the initial configuration-space points: one per combination of
        # the particles' starts (a single point unless something branches
        # or carries both signs), each weighted by the product of the
        # start amplitudes
        combos = [[]]
        for pname, alts in starts.items():
            combos = [c + [(pname, coord, amp)] for c in combos
                      for coord, amp in alts]
        self.initial_points = []
        for combo in combos:
            weight = qn.prod([amp for _, _, amp in combo])
            point = ConfigSpacePoint(0, [coord for _, coord, _ in combo], weight)
            # display data: each particle's initial "component" is its
            # start amplitude in this point (see the weight-evolution
            # graph's band glyphs); an absent particle's is its weight, 0
            point.particles = {p.name: p.weight for p in self.particles.values()}
            point.particles.update({pname: amp for pname, _, amp in combo})
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
