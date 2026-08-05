"""Configuration space for the quantish simulation.

The quantish state is a superposition of *worlds* (ConfigSpacePoints). Each
world assigns every particle a coordinate — a position and a sign — and
carries ONE complex weight for the whole world. Weights belong to worlds, not
to particles: interference happens between worlds, so when two worlds arrive
at identical coordinates their weights simply add.

The runner advances the state one stage at a time. Within a stage, each
particle in a world contributes a list of alternatives (a single pass-through,
or the four-way split of a switch wire); the successor worlds are the
cartesian product of those per-particle alternatives, each weighted by the
parent world's weight times the product of the chosen branch factors.
"""

import logging
import itertools
from dataclasses import dataclass
from typing import Final, Iterable, Optional, Self, Union

import multiworld.qnumber as qn
from multiworld.qnumber import Complex, probability
from multiworld.particle import PKey
from multiworld.util import SEP, Sign, wstr

log = logging.getLogger('multiworld')

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
    """One world: a full assignment of a PCoordinate to every particle, plus
    the single complex weight of that world."""

    def __init__(self, step: int, coords: Union[dict, Iterable[PCoordinate]], weight,
                 predecessors: set[Self] = None, successors: set[Self] = None):
        if not isinstance(coords, dict):
            coords = {c.name: c for c in coords}
        self.step = step
        self.coords: dict[str, PCoordinate] = {name: coords[name] for name in sorted(coords)}
        self.weight: Complex = Complex(qn.qify(weight))
        self.predecessors = set(predecessors) if predecessors is not None else set()
        self.successors = set(successors) if successors is not None else set()
        # amplitude contributed by each predecessor world; after merging,
        # weight == sum(contributions.values()) — the weight-evolution trace
        self.contributions: dict[Self, Complex] = {}
        # the branch factor each particle took in the step that created this
        # world (None = passed through untouched); display data for the
        # per-particle bands of the weight-evolution graph
        self.factors: dict[str, Optional[Complex]] = {}

    @property
    def key(self):
        return '|'.join(str(coord) for coord in self.coords.values())

    @property
    def probability(self):
        return probability(self.weight)

    def __repr__(self):
        return f'{self.key}:{wstr(self.weight, precision=2)}'

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
        """Merge a successor world into this space. Worlds with identical
        coordinates interfere: their weights simply add. Returns the point now
        holding the combined weight."""
        self.max_step = max(self.max_step, point.step)
        existing = self.index.get(point.key)
        if existing is None:
            self.index[point.key] = point
            return point
        if log.isEnabledFor(logging.DEBUG):
            # guarded: the f-string formats symbolic weights via evalf, an
            # expensive no-op when debug logging is off
            log.debug(f'      MERGE at {point.key}: '
                      f'{wstr(existing.weight, precision=2)} + {wstr(point.weight, precision=2)}')
        existing.weight = existing.weight + point.weight
        existing.predecessors |= point.predecessors
        for pred, contrib in point.contributions.items():
            if pred in existing.contributions:
                existing.contributions[pred] = existing.contributions[pred] + contrib
            else:
                existing.contributions[pred] = contrib
        for pname, factor in point.factors.items():
            if existing.factors.get(pname) is None:
                existing.factors[pname] = factor
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
    """Zero test for a merged world weight that has already been through
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
        # the same few objects recur for every world, so their zero-checks
        # (sympy.simplify each, in Symbolic mode) are cached by identity.
        self._factor_zero_cache = {}

    def _factor_is_zero(self, factor) -> bool:
        key = id(factor)
        if key not in self._factor_zero_cache:
            self._factor_zero_cache[key] = qn.zerop(factor)
        return self._factor_zero_cache[key]

    def __repr__(self):
        return f'{self.sim.gates.keys()}'

    def link_dest(self, origin: GatePort) -> GatePort:
        """Where a particle leaving on *origin* lands next: the linked input
        port, or (if unlinked) resting at the gate's own output."""
        dest_str = self.sim.links.get(str(origin))
        if dest_str is None:
            return GatePort(origin.gate, origin.port)
        parts = dest_str.split(SEP)
        return GatePort(*parts) if len(parts) == 2 else GatePort(parts[0], None)

    def particle_alternatives(self, world: ConfigSpacePoint, pname: str,
                              stage_gates: dict) -> list[tuple[PCoordinate, Optional[Complex]]]:
        """The alternatives for one particle of one world in the current stage,
        as (new coordinate, weight factor) pairs. A factor of None means the
        weight is unchanged (pass-through)."""
        coord = world.coords[pname]
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
        # positional — some *other* particle of this world sits on this gate's
        # control input — regardless of that particle's sign or the world's weight.
        control_port = GatePort(gate.name, 'control')
        control_present = any(
            other.position.endpoint == control_port
            for other_name, other in world.coords.items() if other_name != pname)
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

    def run(self, initial_point: ConfigSpacePoint) -> tuple[ConfigSpace, ConfigSpace]:
        """Advance the quantish state through every stage.

        For each stage, every world in Q expands to the cartesian product of
        its particles' alternatives; each successor world's weight is the
        parent's weight times the product of the chosen branch factors.
        Successors with identical coordinates merge by adding weights
        (interference), and worlds whose weights cancel to zero are dropped.
        """
        sim = self.sim
        Q = ConfigSpace(initial_point)
        all_points = ConfigSpace()
        all_points.record(initial_point)
        for step, stage in enumerate(sim.run_stages):
            stage_gates = {gname: sim.gates[gname] for gname in stage}
            log.debug(f'BEGIN STEP {step}: {", ".join(str(g) for g in stage_gates.values())}')
            Q_next = ConfigSpace()
            for world in Q.index.values():
                per_particle = [self.particle_alternatives(world, pname, stage_gates)
                                for pname in world.coords]
                successor_count = 0
                for combo in itertools.product(*per_particle):
                    weight = world.weight
                    for _, factor in combo:
                        if factor is not None:
                            weight = weight * factor
                    successor = ConfigSpacePoint(step + 1, [coord for coord, _ in combo],
                                                 weight, predecessors={world})
                    successor.contributions = {world: successor.weight}
                    successor.factors = {coord.name: factor for coord, factor in combo}
                    merged = Q_next.add_point(successor)
                    world.successors.add(merged)
                    successor_count += 1
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f'   {world} -> {successor_count} successor world(s)')
            # interference may have cancelled a world's weight to zero
            for point in list(Q_next.index.values()):
                point.weight = qn.simplify(point.weight)
                if _weight_is_zero(point.weight):
                    log.debug(f'   dropping cancelled world {point.key}')
                    Q_next.remove(point)
            self.check_total_probability(Q_next, step)
            for point in Q_next.index.values():
                all_points.record(point)
            Q = Q_next
            log.debug(f'END STEP {step}: {len(Q.index)} world(s)')
            log.debug(' ')
        log.debug('finished')
        return Q, all_points

    def check_total_probability(self, space: ConfigSpace, step: int):
        """The one invariant that must hold: sum over worlds of |weight|² == 1."""
        try:
            total = sum(float(p.probability) for p in space.index.values())
        except (TypeError, ValueError):
            return  # symbolic weights with free symbols: nothing to check numerically
        log.debug(f'   total probability after step {step}: {total:.6f}')
        if abs(total - 1) > 1e-6:
            log.warning(f'   TOTAL PROBABILITY AFTER STEP {step} IS {total}, EXPECTED 1')