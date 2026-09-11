"""A quantish circuit as a qubit circuit.

Every quantish gate is a standard two-qubit operation. Give a particle a
sign qubit s (|0> plus, |1> minus) and a position qubit x, and a gate
at measurement angle θ with no control particle present is

    U(θ) = Rx(-2θ) on s  ·  CNOT(s -> x)  ·  Rx(+2θ) on s

— the sign is measured in the basis rotated by θ, and the position wire
records the outcome: the parallel component passes straight (x kept),
the perpendicular component crosses over (x flipped). A control
particle present swaps straight and cross, i.e. one more NOT on x,
conditioned on that particle's position. The four split components of
§4.2.3 (cos²θ, i·sinθcosθ, sin²θ, −i·sinθcosθ) are the matrix entries
of this rotated CNOT. A phase plate, or a gate's optional phase, is a
phase conditioned on the particle's position; a branching start is a
Ry rotation of the position qubit; a control-wire traversal changes
nothing but where the particle is.

The compiler here turns a loaded Simulation into that circuit and a
numpy statevector simulation of it reproduces the engine's final
configuration-space points, weight for weight (tests/test_qubit_circuit.py
checks every model). Nothing depends on Qiskit; `to_qiskit()` builds a
QuantumCircuit when Qiskit happens to be installed.

Encoding. A particle's position at a stage is a wire segment (the
engine's Position). Its qubits are x plus as many flag qubits as the
circuit needs, and a *code* — the tuple (x, flag₁, flag₂, …) — names a
position, by a table the compiler keeps per particle and updates stage
by stage. The rules that keep the table a bijection:

- a switch gate keeps a code's x for the straight output and flips it
  for the crossed one, so the code that entered on g.upper leaves on
  g.upper (straight) or g.lower (crossed) and the sibling code (x
  flipped) is the other input, or unused;
- when the sibling of a code about to enter a gate is live somewhere
  else — a particle resting at an unlinked output, or on another wire
  entirely — the two would collide after the gate, so a fresh flag
  qubit is set on that other code first (a multi-controlled NOT on its
  full pattern) and the codes stay distinct;
- a control-wire or pass-through traversal leaves the code alone and
  moves its position on;
- codes never stop being live: a particle at an unlinked output rests
  there for the remaining stages.

Two configuration-space points with the same positions and signs are
the same basis state, so the merging of the engine — interference —
is automatic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

import quantish.qnumber as qn
from quantish.config_space import ConfigSpacePoint, GatePort, PCoordinate, Position
from quantish.util import SEP, Sign

CONTROL = 'control'
SWITCH = ('upper', 'lower')


@dataclass
class Op:
    """One circuit operation: a single-qubit gate on `target` applied
    where every (qubit, value) pair in `controls` matches, or a phase
    (no target) applied to those basis states."""
    kind: str                      # 'rx' | 'ry' | 'x' | 'phase'
    target: int | None
    controls: tuple = ()           # ((qubit, 0|1), ...)
    angle: float = 0.0             # rotation angle (rx, ry) or phase
    label: str = ''                # the quantish element it comes from

    def matrix(self) -> np.ndarray:
        if self.kind == 'rx':
            c, s = math.cos(self.angle / 2), math.sin(self.angle / 2)
            return np.array([[c, -1j * s], [-1j * s, c]])
        if self.kind == 'ry':
            c, s = math.cos(self.angle / 2), math.sin(self.angle / 2)
            return np.array([[c, -s], [s, c]])
        if self.kind == 'x':
            return np.array([[0, 1], [1, 0]], dtype=complex)
        raise ValueError(self.kind)


@dataclass
class ParticleQubits:
    sign: int
    x: int
    flags: list = field(default_factory=list)
    # code (x, *flags) -> Position, for the codes that are live
    positions: dict = field(default_factory=dict)
    initial_sign: int = 1
    # a branching start: (amplitude of code x=0, amplitude of code x=1)
    branch: tuple | None = None

    def pattern(self, code) -> tuple:
        """The (qubit, value) controls that single out one code."""
        return ((self.x, code[0]),) + tuple(zip(self.flags, code[1:]))

    def flag_pattern(self, flags) -> tuple:
        return tuple(zip(self.flags, flags))


class QubitCircuit:
    """The compiled circuit: qubits, operations, and the per-particle
    code tables that decode a final basis state into positions."""

    def __init__(self, sim):
        self.sim = sim
        self.qubit_names: list[str] = []
        self.ops: list[Op] = []
        self.particles: dict[str, ParticleQubits] = {}
        self.weight = complex(1.0)          # the product of particle weights
        self.stage_marks: list[tuple[int, str]] = []   # (op index, stage label)

    # ---- construction helpers
    def new_qubit(self, name: str) -> int:
        self.qubit_names.append(name)
        return len(self.qubit_names) - 1

    @property
    def n_qubits(self) -> int:
        return len(self.qubit_names)

    # ---- simulation
    def initial_state(self) -> np.ndarray:
        psi = np.zeros(2 ** self.n_qubits, dtype=complex)
        psi[0] = self.weight
        return psi

    def apply(self, psi: np.ndarray, op: Op) -> np.ndarray:
        idx = np.arange(psi.size)
        mask = np.ones(psi.size, dtype=bool)
        for q, v in op.controls:
            mask &= ((idx >> q) & 1) == v
        if op.kind == 'phase':
            psi[mask] *= np.exp(1j * op.angle)
            return psi
        bit = 1 << op.target
        lo = idx[mask & (((idx >> op.target) & 1) == 0)]
        hi = lo | bit
        m = op.matrix()
        a, b = psi[lo].copy(), psi[hi].copy()
        psi[lo] = m[0, 0] * a + m[0, 1] * b
        psi[hi] = m[1, 0] * a + m[1, 1] * b
        return psi

    def simulate(self, upto: int | None = None) -> np.ndarray:
        """The statevector after all ops (or the first `upto`)."""
        psi = self.initial_state()
        for op in self.ops[:upto]:
            psi = self.apply(psi, op)
        return psi

    def decode(self, psi: np.ndarray, tol: float = 1e-12) -> dict:
        """{configuration-space point key: amplitude} for the basis
        states with amplitude above tol, positions read from the final
        code tables. Raises if amplitude sits on a code that names no
        position — the compiler's bijection would have failed."""
        out = {}
        for i in np.flatnonzero(np.abs(psi) > tol):
            coords = []
            for name, pq in self.particles.items():
                code = ((i >> pq.x) & 1,) + tuple((i >> f) & 1 for f in pq.flags)
                pos = pq.positions.get(code)
                if pos is None:
                    raise RuntimeError(f'amplitude on an unassigned code {code} of {name}')
                sign = Sign.plus if (i >> pq.sign) & 1 == 0 else Sign.minus
                coords.append(PCoordinate(name, sign, pos))
            key = ConfigSpacePoint(len(self.sim.run_stages), coords, 1).key
            out[key] = out.get(key, 0) + complex(psi[i])
        return out

    def final_points(self) -> dict:
        return self.decode(self.simulate())

    # ---- drawing
    def draw(self) -> str:
        """The circuit as text, one column per operation: boxes for
        rotations and NOTs, ■ / ○ for controls on 1 / 0 joined by a
        vertical line, a labeled barrier before each stage. Phases show
        as a P box on their last control qubit."""
        marks = dict(self.stage_marks)
        cols = []
        for i, op in enumerate(self.ops):
            if i in marks:
                cols.append(('barrier', marks[i]))
            if op.kind == 'phase':
                if not op.controls:
                    continue
                (last_q, last_v), rest = op.controls[-1], op.controls[:-1]
                label = f'P({_angle_text(op.angle)})' + ('' if last_v else '⁰')
                cols.append(('gate', last_q, label, rest))
            else:
                label = {'rx': f'Rx({_angle_text(op.angle)})',
                         'ry': f'Ry({_angle_text(op.angle)})', 'x': 'X'}[op.kind]
                cols.append(('gate', op.target, label, op.controls))
        return _render(self.qubit_names, cols)

    # ---- export
    def to_qiskit(self):
        """A qiskit QuantumCircuit of the same ops (Qiskit optional)."""
        from qiskit import QuantumCircuit
        from qiskit.circuit.library import PhaseGate, RXGate, RYGate, XGate
        qc = QuantumCircuit(self.n_qubits)
        for op in self.ops:
            if op.kind == 'phase':
                if not op.controls:
                    qc.global_phase += op.angle
                    continue
                # a phase on the basis states matching the controls: a
                # PhaseGate on the last control, controlled by the rest
                (last_q, last_v), rest = op.controls[-1], op.controls[:-1]
                gate = PhaseGate(op.angle) if last_v == 1 else None
                if gate is None:      # phase where last_q == 0: X-conjugate
                    qc.x(last_q)
                    gate = PhaseGate(op.angle)
                self._append_controlled(qc, gate, rest, [last_q])
                if last_v == 0:
                    qc.x(last_q)
                continue
            if op.kind == 'rx':
                base = RXGate(op.angle)
            elif op.kind == 'ry':
                base = RYGate(op.angle)
            else:
                base = XGate()
            self._append_controlled(qc, base, op.controls, [op.target])
        return qc

    @staticmethod
    def _append_controlled(qc, gate, controls, targets):
        if controls:
            state = ''.join(str(v) for _, v in reversed(controls))
            gate = gate.control(len(controls), ctrl_state=state)
            qc.append(gate, [q for q, _ in controls] + targets)
        else:
            qc.append(gate, targets)


def _angle_text(angle: float) -> str:
    """An angle as a short multiple of π when it is one, else degrees."""
    for denom in (1, 2, 3, 4, 6, 8, 12, 16):
        k = angle * denom / math.pi
        if abs(k - round(k)) < 1e-9 and round(k) != 0:
            k = round(k)
            num = {1: '', -1: '-'}.get(k, str(k))
            return f'{num}π' + ('' if denom == 1 else f'/{denom}')
    if abs(angle) < 1e-12:
        return '0'
    return f'{math.degrees(angle):.4g}°'


def _render(names, cols) -> str:
    """Lay out columns of ('gate', target, label, controls) and
    ('barrier', label) over one three-line row per qubit."""
    name_w = max(len(n) for n in names) + 2
    rows = {q: ['', '', ''] for q in range(len(names))}
    header = ' ' * name_w
    for col in cols:
        if col[0] == 'barrier':
            w = max(3, len(col[1]) + 2)
            header += col[1].center(w)
            for row in rows.values():
                row[0] += '░'.center(w); row[1] += '░'.center(w, '─'); row[2] += '░'.center(w)
            continue
        _, target, label, controls = col
        w = len(label) + 4
        header += ' ' * w
        involved = [target] + [q for q, _ in controls]
        top, bot = min(involved), max(involved)
        ctl = dict(controls)
        for q, row in rows.items():
            if q == target:
                t = '┌' + '─' * (w - 2) + '┐'
                b = '└' + '─' * (w - 2) + '┘'
                if q > top:
                    t = t[:w // 2] + '┴' + t[w // 2 + 1:]
                if q < bot:
                    b = b[:w // 2] + '┬' + b[w // 2 + 1:]
                row[0] += t; row[1] += '┤' + label.center(w - 2) + '├'; row[2] += b
            elif q in ctl:
                row[0] += ('│' if q > top else ' ').center(w)
                row[1] += ('■' if ctl[q] else '○').center(w, '─')
                row[2] += ('│' if q < bot else ' ').center(w)
            elif top < q < bot:
                row[0] += '│'.center(w); row[1] += '┼'.center(w, '─'); row[2] += '│'.center(w)
            else:
                row[0] += ' ' * w; row[1] += '─' * w; row[2] += ' ' * w
    out = [header.rstrip()]
    for q, name in enumerate(names):
        out.append(' ' * name_w + rows[q][0])
        out.append(f'{name}: '.rjust(name_w) + rows[q][1])
        out.append(' ' * name_w + rows[q][2])
    return '\n'.join(line.rstrip() for line in out)


# --------------------------------------------------------------------------
# the compiler
# --------------------------------------------------------------------------

def _link_dest(sim, origin: GatePort) -> GatePort:
    """Where a particle leaving on `origin` lands: the linked input port,
    or resting at the gate's own output (the engine's rule)."""
    dest = sim.links.get(str(origin))
    if dest is None:
        return GatePort(origin.gate, origin.port)
    parts = dest.split(SEP)
    return GatePort(*parts) if len(parts) == 2 else GatePort(parts[0], None)


def _is_pass_through(gate, port) -> bool:
    return gate.report_type() in ('DelayGate', 'PhasePlate') or port in (None, CONTROL)


def compile_qubits(sim) -> QubitCircuit:
    """Compile a loaded Simulation (run or not) into a QubitCircuit."""
    qc = QubitCircuit(sim)
    weight = complex(1.0)
    # ---- particles: qubits, start positions, sign
    starts: dict[str, list] = {}
    for point in sim.initial_points:
        for name, coord in point.coords.items():
            alts = starts.setdefault(name, [])
            if all(c.position != coord.position for c in alts):
                alts.append(coord)
    for name, particle in sim.particles.items():
        if name not in starts:
            continue                                    # absent (zero weight)
        weight *= complex(particle.weight)
        pq = ParticleQubits(sign=qc.new_qubit(f'{name}.s'), x=qc.new_qubit(f'{name}.x'),
                            initial_sign=int(particle.sign))
        alts = starts[name]
        if int(particle.sign) < 0:
            qc.ops.append(Op('x', pq.sign, label=f'{name} starts minus'))
        if len(alts) == 1:
            pq.positions[(0,)] = alts[0].position
        else:
            # a branching start: real amplitudes sqrt(p), sqrt(1-p) on
            # the two arms, the first arm being code x=0
            amp0, amp1 = (complex(a) for a in sim.branch_amps[name])
            first = sim.links[name]
            order = sorted(alts, key=lambda c: str(c.position.endpoint) != first)
            pq.positions[(0,)] = order[0].position
            pq.positions[(1,)] = order[1].position
            pq.branch = (amp0, amp1)
            qc.ops.append(Op('ry', pq.x, angle=2 * math.acos(min(1.0, abs(amp0))),
                             label=f'{name} branches'))
        qc.particles[name] = pq
    qc.weight = weight

    def add_flag(pq: ParticleQubits, name: str, moved_code):
        """A fresh flag qubit for the particle, set to 1 on `moved_code`
        (so it no longer collides) and 0 on every other code."""
        f = qc.new_qubit(f'{name}.f{len(pq.flags)}')
        qc.ops.append(Op('x', f, controls=pq.pattern(moved_code),
                         label=f'{name}: keep {pq.positions[moved_code]} apart'))
        pq.flags.append(f)
        pq.positions = {code + ((1,) if code == moved_code else (0,)): pos
                        for code, pos in pq.positions.items()}

    # ---- stages
    for stage_index, stage in enumerate(sim.run_stages):
        stage_gates = {g: sim.gates[g] for g in stage}
        qc.stage_marks.append((len(qc.ops), ', '.join(stage)))

        def at_switch(pq, code, gates=stage_gates):
            ep = pq.positions[code].endpoint
            return (ep is not None and ep.gate in gates and ep.port in SWITCH
                    and not _is_pass_through(gates[ep.gate], ep.port))

        # 1. collisions: a code entering a switch gate needs its sibling
        #    (x flipped) free, or at the same gate's other input
        for name, pq in qc.particles.items():
            changed = True
            while changed:
                changed = False
                for code in list(pq.positions):
                    if not at_switch(pq, code):
                        continue
                    sibling = (1 - code[0],) + code[1:]
                    if sibling not in pq.positions:
                        continue
                    ep, sep = pq.positions[code].endpoint, pq.positions[sibling].endpoint
                    if at_switch(pq, sibling) and sep.gate == ep.gate:
                        continue                        # the other input of the same gate
                    add_flag(pq, name, sibling)
                    changed = True
                    break

        # 2. emit the stage from a snapshot of the code tables
        snapshot = {name: dict(pq.positions) for name, pq in qc.particles.items()}
        for gname, gate in stage_gates.items():
            theta = float(qn.to_float(gate.theta)) if gate.report_type() == 'FredkinGate' else 0.0
            phi = float(qn.to_float(gate.phase)) if not qn.zerop(gate.phase) else 0.0
            for name, pq in qc.particles.items():
                # switch-wire entries, grouped by flag pattern
                groups = {}
                for code, pos in snapshot[name].items():
                    ep = pos.endpoint
                    if (ep is not None and ep.gate == gname and ep.port in SWITCH
                            and not _is_pass_through(gate, ep.port)):
                        groups.setdefault(code[1:], []).append(code)
                for flags in groups:
                    ctl = pq.flag_pattern(flags)
                    lab = f'{gname} on {name}'
                    qc.ops.append(Op('rx', pq.sign, ctl, 2 * theta, lab))
                    qc.ops.append(Op('x', pq.x, ctl + ((pq.sign, 1),), 0.0, lab))
                    qc.ops.append(Op('rx', pq.sign, ctl, -2 * theta, lab))
                    if phi:
                        qc.ops.append(Op('phase', None, ctl, phi, f'{gname} phase'))
                    # a control particle present swaps straight and cross
                    for oname, opq in qc.particles.items():
                        if oname == name:
                            continue
                        for ocode, opos in snapshot[oname].items():
                            if opos.endpoint == GatePort(gname, CONTROL):
                                qc.ops.append(Op('x', pq.x, ctl + opq.pattern(ocode), 0.0,
                                                 f'{gname} control by {oname}'))
                # pass-throughs with a phase (plates, control wires of a
                # phased gate)
                if phi:
                    for code, pos in snapshot[name].items():
                        ep = pos.endpoint
                        if ep is not None and ep.gate == gname and _is_pass_through(gate, ep.port):
                            qc.ops.append(Op('phase', None, pq.pattern(code), phi,
                                             f'{gname} phase on {name}'))

        # 3. move the positions on
        for name, pq in qc.particles.items():
            new_positions = {}
            for code, pos in snapshot[name].items():
                ep = pos.endpoint
                if ep is None or ep.gate not in stage_gates:
                    new_positions[code] = pos
                    continue
                gate = stage_gates[ep.gate]
                if _is_pass_through(gate, ep.port):
                    origin = GatePort(gate.name, ep.port)
                    new_positions[code] = Position(origin=origin, endpoint=_link_dest(sim, origin))
                    continue
                # switch: straight keeps x (same side), crossed flips it
                other = 'lower' if ep.port == 'upper' else 'upper'
                for port, c in ((ep.port, code), (other, (1 - code[0],) + code[1:])):
                    origin = GatePort(gate.name, port)
                    new_positions[c] = Position(origin=origin, endpoint=_link_dest(sim, origin))
            pq.positions = new_positions
    return qc
