"""Configuration space for the quantish simulation.

The quantish state is a superposition of configuration-space points ("CS
points" — the book's classical states). Each CS point assigns every particle
a coordinate — a position and a sign — and carries ONE complex weight for the
whole point. Weights belong to CS points, not to particles: interference
happens between CS points, so when two arrive at identical coordinates their
weights simply add.

The runner advances the state one stage at a time. Within a stage, each
particle in a CS point contributes a list of alternatives (a single pass-through,
or the four-way split of a switch wire); the successors are the
cartesian product of those per-particle alternatives, each weighted by the
parent CS point's weight times the product of the chosen components.
"""

import logging
import itertools
from dataclasses import dataclass
from typing import Final, Iterable, Optional, Self, Union, Dict

import quantish.qnumber as qn
from quantish.gate import FredkinGate
from quantish.qnumber import Complex, probability
from quantish.particle import PKey
from quantish.util import SEP, Sign, wstr

log = logging.getLogger('quantish')

# a GatePort is a specific input or output wire on a specific gate
@dataclass(slots=True)
class GatePort:
    gate: Optional[str] = None
    port: Optional[str] = None
    def __repr__(self):
        if self.gate is None and self.port is None:
            return 'NOWHERE'
        sepstr = SEP if self.gate and self.port else ''
        gatestr = '' if self.gate is None else str(self.gate)
        portstr = '' if self.port is None else str(self.port)
        return f'{gatestr}{sepstr}{portstr}'
    def __hash__(self):
        return self.__repr__().__hash__()

NOWHERE: Final[GatePort] = GatePort(None, None)

# positions are connections between gates
@dataclass(slots=True)
class Position:
    # origin and endpoint are each a GatePort or None
    origin: Optional[GatePort] = None
    endpoint: Optional[GatePort] = None
    def __repr__(self):
        if self.origin is None and self.endpoint is None:
            return 'ABSENT'
        elif self.origin is NOWHERE and self.endpoint is NOWHERE:
            return 'LIMBO'
        elif self.origin is None:
            return f'ORIGIN>{self.endpoint}_in'
        elif self.endpoint is None or self.endpoint == NOWHERE:
            return f'{self.origin}_out>NOWHERE'
        else:
            if self.origin.gate == self.endpoint.gate:
                return f'{self.origin}_in>{self.endpoint}_out'
            else:
                return f'{self.origin}_out>{self.endpoint}_in'

# Configuration space has 2p dimensions, where p is the number of particles:
# for each particle, a position and a sign. A PCoordinate is one particle's
# pair of those dimension values. Coordinates are immutable by convention —
# the runner never mutates one, it creates new ones.
@dataclass(slots=True, eq=False)
class PCoordinate:
    name: str
    sign: Sign
    position: Position

    def __repr__(self):
        return self.key

    def __hash__(self):
        return self.key.__hash__()

    def __eq__(self, other):
        return repr(self) == repr(other)

    def __lt__(self, other):
        return str(self) < str(other)

    @property
    def pkey(self):
        return PKey(self.name, self.sign)

    @property
    def key(self):
        return f'{self.pkey}@{self.position}'


class ConfigSpacePoint:
    """One CS point (the book's classical state): a full assignment of a
    PCoordinate to every particle, plus the single complex weight of that
    point."""

    def __init__(self, step: int, coords: Union[dict, Iterable[PCoordinate]], weight,
                 predecessors: set[Self] = None, successors: set[Self] = None):
        if not isinstance(coords, dict):
            coords = {c.name: c for c in coords}
        self.step = step
        self.coords: dict[str, PCoordinate] = {name: coords[name] for name in sorted(coords)}
        self.weight: Complex = Complex(qn.qify(weight))
        self.predecessors = set(predecessors) if predecessors is not None else set()
        self.successors = set(successors) if successors is not None else set()
        # amplitude contributed by each predecessor CS point; after merging,
        # weight == sum(contributions.values()) — the weight-evolution trace
        self.contributions: dict[Self, Complex] = {}
        # the split component each particle took in the step that created
        # this CS point (None = passed through untouched); display data for
        # the per-particle bands of the weight-evolution graph
        self.particles: dict[str, Optional[Complex]] = {}
        # True when interference cancelled this CS point's weight to zero: it
        # was dropped from the live set but stays in the all-points history
        # so the weight-evolution graph/table can show the cancellation
        self.cancelled = False

    @property
    def key(self):
        return '|'.join(str(coord) for coord in self.coords.values())

    @property
    def probability(self):
        return probability(self.weight)

    def __repr__(self):
        return f'{self.key}:{wstr(self.weight)}'

    def __hash__(self):
        return self.key.__hash__()


class ConfigSpace:
    __slots__ = ('index', 'max_step')

    def __init__(self, initial_point: ConfigSpacePoint = None):
        self.index: dict[str, ConfigSpacePoint] = {}
        self.max_step = 0
        if initial_point is not None:
            self.index[initial_point.key] = initial_point
            self.max_step = initial_point.step

    def add_point(self, point: ConfigSpacePoint) -> ConfigSpacePoint:
        """Merge a successor into this space. CS points with identical
        coordinates interfere: their weights simply add. Returns the point now
        holding the combined weight."""
        self.max_step = max(self.max_step, point.step)
        existing = self.index.get(point.key)
        if existing is None:
            self.index[point.key] = point
            return point
        original_weight =  existing.weight
        existing.weight = existing.weight + point.weight
        log.debug(f'      MERGE {point.key}: '
                  f'{wstr(original_weight, precision=2)} + {wstr(point.weight, precision=2)} -> {wstr(existing.weight, precision=2)}')
        existing.predecessors |= point.predecessors
        for pred, contrib in point.contributions.items():
            if pred in existing.contributions:
                existing.contributions[pred] = existing.contributions[pred] + contrib
            else:
                existing.contributions[pred] = contrib
        for pname, component in point.particles.items():
            if existing.particles.get(pname) is None:
                existing.particles[pname] = component
        for pred in point.predecessors:
            pred.successors.discard(point)
            pred.successors.add(existing)
        return existing

    def remove(self, point: ConfigSpacePoint):
        del self.index[point.key]
        for pred in point.predecessors:
            pred.successors.discard(point)

    def record(self, point: ConfigSpacePoint):
        """Store a point under a step-qualified key, without merging — for the
        all-points history that feeds the network graph."""
        self.max_step = max(self.max_step, point.step)
        self.index[f'{point.step}#{point.key}'] = point


def _weight_is_zero(w) -> bool:
    """Zero test for a merged CS-point weight that has already been through
    qn.simplify, cheap in Symbolic mode: structural zero, then a fast
    numeric probe that proves NON-zero for almost every point; only
    near-zero candidates pay for the exact confirmation (qn.zerop, which
    runs sympy.simplify again)."""
    if qn.CalcMode.default() == 'Float':
        return qn.zerop(w)
    v = w.v if qn.isq(w) else w
    if v == 0:
        return True
    try:
        if abs(complex(v.evalf(15))) > 1e-9:
            return False
    except (TypeError, ValueError):
        pass
    return qn.zerop(w)


class ConfigSpaceRunner:
    def __init__(self, sim=None):
        self.sim = sim
        # Branch factors are the gates' precomputed constants (cos²θ, ...):
        # the same few objects recur for every CS point, so their zero-checks
        # (sympy.simplify each, in Symbolic mode) are cached by identity.
        self._factor_zero_cache = {}

    def _factor_is_zero(self, factor) -> bool:
        key = id(factor)
        if key not in self._factor_zero_cache:
            self._factor_zero_cache[key] = qn.zerop(factor)
        return self._factor_zero_cache[key]

    def __repr__(self):
        return f'{self.sim.gates.keys()}'

    def control_present(self, cs_point: ConfigSpacePoint, gname: str) -> bool:
        """Whether some particle of this CS point occupies gname's control
        input (see the per-CS-point positional note in particle_factors)."""
        control_port = GatePort(gname, 'control')
        return any(c.position.endpoint == control_port
                   for c in cs_point.coords.values())

    def stage_control_info(self, Q: ConfigSpace, stage_gates) -> dict:
        """For each stage gate whose control input is occupied: where the
        occupant came from and the merged probability |Σ weights|² of the
        CS points that put it there — display data for the per-CS-point
        CONTROL log line."""
        info = {}
        for gname in stage_gates:
            control_port = GatePort(gname, 'control')
            amp, source = None, None
            for cs_point in Q.index.values():
                for coord in cs_point.coords.values():
                    if coord.position.endpoint == control_port:
                        amp = cs_point.weight if amp is None else amp + cs_point.weight
                        source = coord.position.origin or coord.name
            if amp is not None:
                info[gname] = (source, qn.to_float(probability(amp)))
        return info

    def link_dest(self, origin: GatePort) -> GatePort:
        """Where a particle leaving on *origin* lands next: the linked input
        port, or (if unlinked) resting at the gate's own output."""
        dest_str = self.sim.links.get(str(origin))
        if dest_str is None:
            return GatePort(origin.gate, origin.port)
        parts = dest_str.split(SEP)
        return GatePort(*parts) if len(parts) == 2 else GatePort(parts[0], None)

    def particle_factors(self, cs_point: ConfigSpacePoint, pname: str,
                         stage_gates: Dict[str, FredkinGate]) -> list[tuple[PCoordinate, Optional[Complex]]]:
        """Alternatives for one particle of one CS point in the current
        stage, as (new coordinate, weight component) pairs. A component of
        None means the weight is unchanged (passthrough)."""
        coord = cs_point.coords[pname]
        endpoint = coord.position.endpoint
        if endpoint is None or endpoint == NOWHERE or endpoint.gate not in stage_gates:
            # finished, or still en route to a later stage: carried through unchanged
            return [(coord, None)]
        gate = stage_gates[endpoint.gate]
        if gate.report_type() == 'DelayGate' or endpoint.port in (None, 'control'):
            # control wires (and delay gates) pass the particle straight through
            origin = GatePort(gate.name, endpoint.port)
            dest = self.link_dest(origin)
            new_coord = PCoordinate(pname, coord.sign, Position(origin=origin, endpoint=dest))
            return [(new_coord, None)]
        # switch wire: the four-way split of §4.2.3. Control presence is
        # positional PER CS POINT — some *other* particle of this CS point
        # sits on this gate's control input — regardless of that particle's
        # sign. Within one CS point occupancy is boolean; the amplitude side
        # of "how present" the control is lives entirely in the CS-point
        # weights. A computed control input that comes out zero still behaves
        # as absent, because zero-amplitude occupancies never reach here:
        # zero components are skipped below, and CS points whose weights
        # cancel are dropped before the next stage runs — so no surviving CS
        # point has a particle on that control. A superposed control is a mix
        # of CS points with and without the occupancy, each routed
        # accordingly, and the outputs interfere downstream. (An aggregate
        # amplitude test would be wrong under entanglement: CS points sharing
        # this occupancy but differing elsewhere may sum to zero at the port
        # while each is genuinely controlled.)
        control_present = self.control_present(cs_point, gate.name)
        alternatives = []
        for out_port, out_sign, factor in gate.switch_factors(endpoint.port, coord.sign,
                                                              control_present):
            if self._factor_is_zero(factor):
                continue  # a zero-weight branch can never contribute
            origin = GatePort(gate.name, out_port)
            dest = self.link_dest(origin)
            alternatives.append(
                (PCoordinate(pname, out_sign, Position(origin=origin, endpoint=dest)), factor))
        return alternatives

    @staticmethod
    def cs_point_str(cs_point: ConfigSpacePoint, stage_gates=None) -> str:
        """Log display for a CS point: its weight plus only the coordinates
        that matter this stage — particles feeding a stage gate, or already
        moved from their origin. (The full key is unambiguous but drowns the
        reader in not-yet-moving particles.)"""
        def relevant(coord):
            if coord.position.origin is not None:
                return True
            endpoint = coord.position.endpoint
            return (stage_gates is not None and endpoint is not None
                    and endpoint.gate in stage_gates)
        coords = ([c for c in cs_point.coords.values() if relevant(c)]
                  or list(cs_point.coords.values()))
        return f'{"|".join(str(c) for c in coords)}:{wstr(cs_point.weight)}'

    def run(self, initial_point: ConfigSpacePoint) -> tuple[ConfigSpace, ConfigSpace]:
        """Advance the quantish state through every stage.

        For each stage, every CS point in Q expands to the cartesian product
        of its particles' alternatives; each successor's weight is the
        parent's weight times the product of the chosen components.
        Successors with identical coordinates merge by adding weights
        (interference), and CS points whose weights cancel to zero are
        dropped.
        """
        sim = self.sim
        Q = ConfigSpace(initial_point)
        all_points = ConfigSpace()
        all_points.record(initial_point)
        for step, stage in enumerate(sim.run_stages):
            stage_gates = {gname: sim.gates[gname] for gname in stage}
            log.debug(f'BEGIN STEP {step}: {", ".join(str(g) for g in stage_gates.values())}')
            control_info = self.stage_control_info(Q, stage_gates)
            Q_next = ConfigSpace()
            for cs_point in Q.index.values():
                # particles ordered by their gate's position in the stage
                # (run_stages order), so the cartesian product enumerates
                # successors gate by gate, each gate's four components in
                # the book's order c2a, c2b, c3a, c3b
                def stage_rank(pname):
                    endpoint = cs_point.coords[pname].position.endpoint
                    gate = endpoint.gate if endpoint is not None else None
                    return (stage.index(gate) if gate in stage_gates else len(stage),
                            pname)
                per_particle = [self.particle_factors(cs_point, pname, stage_gates)
                                for pname in sorted(cs_point.coords, key=stage_rank)]
                branches = [(successor_tuple,
                             cs_point.weight * qn.prod(x[1] or 1 for x in successor_tuple))
                            for successor_tuple in itertools.product(*per_particle)]
                controlled = ', '.join(
                    f'{control_info[g][0]}->{g} Pr {control_info[g][1]:.2f}'
                    for g in stage_gates if self.control_present(cs_point, g))
                log.debug(f'   {self.cs_point_str(cs_point, stage_gates)} '
                          f'-> {len(branches)} successor{"" if len(branches) == 1 else "s"}'
                          f'{" CONTROL: " + controlled if controlled else ""}')
                for successor_tuple, weight in branches:
                    # one line per branch, in creation order (per gate,
                    # components c2a, c2b, c3a, c3b): each moved particle
                    # with its destination and component, then the weight
                    # arithmetic spelled out — BEFORE add_point, so a MERGE
                    # line prints directly beneath the branch that caused it
                    if log.isEnabledFor(logging.DEBUG):
                        moved = [(coord, component) for coord, component in successor_tuple
                                 if component is not None]
                        arrivals = ' | '.join(
                            f'{coord.pkey}@{coord.position.origin} {wstr(component)}'
                            for coord, component in moved)
                        calc = ' × '.join([wstr(cs_point.weight)]
                                          + [wstr(component) for _, component in moved])
                        log.debug(f'      {arrivals}; weight: {calc} = {wstr(weight)}')
                    successor = ConfigSpacePoint(step + 1, [coord for coord, _ in successor_tuple],
                                                 weight, predecessors={cs_point})
                    successor.contributions = {cs_point: successor.weight}
                    successor.particles = {coord.name: component
                                           for coord, component in successor_tuple}
                    merged = Q_next.add_point(successor)
                    cs_point.successors.add(merged)
            # interference may have canceled a CS point's weight to zero
            for point in list(Q_next.index.values()):
                point.weight = qn.simplify(point.weight)
                if qn.zerop(point.weight):
                    log.debug(f'   dropping zero-weight point {point.key}')
                    point.cancelled = True
                    # all_points.record(point)
                    Q_next.remove(point)
            # the step's final output, last thing before the total so the
            # trace reads top-to-bottom into the result
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f'   step {step} result: {len(Q_next.index)} CS point(s)')
                for point in sorted(Q_next.index.values(),
                                    key=sim.cs_point_sort_key):
                    log.debug(f'      {point.key}: {wstr(point.weight)}')
            self.check_total_probability(Q_next, step)
            for point in Q_next.index.values():
                all_points.record(point)
            Q = Q_next
            log.debug(f'END STEP {step}: {len(Q.index)} CS point(s)')
            log.debug(' ')
        log.debug('finished')
        return Q, all_points

    def check_total_probability(self, space: ConfigSpace, step: int):
        """The one invariant that must hold: sum over CS points of |weight|² == 1."""
        total = qn.to_float(sum(p.probability for p in space.index.values()))
        log.debug(f'   total probability after step {step}: {total:.6f}')
        if abs(total - 1) > 1e-6:
            log.warning(f'   TOTAL PROBABILITY AFTER STEP {step} IS {total}, EXPECTED 1')