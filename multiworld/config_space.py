import logging
import random
import re
from collections import defaultdict, namedtuple, deque
from dataclasses import dataclass
import itertools
from enum import Enum, auto
from typing import Self, Optional, Dict, List, Tuple, Final, Set
from copy import deepcopy
from addict import Addict
import networkx as nx
import numpy as np

from multiworld.particle import Particle, PKey
from multiworld.util import SEP, enough, sstr, Sign, SWITCH_WIRES, WIRES, default_wires, ZERO_THRESHOLD, flat_list, wstr
from multiworld.qnumber import Complex
import multiworld.qnumber as qn
from multiworld.sink import Sink

log = logging.getLogger('multiworld')

# a Wire is specific input or output on a specific gate
@dataclass(slots=True)
class Wire:
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

NOWHERE: Final[Wire] = Wire(None, None)

# positions are connections between gates
# for simplicity's sake, we use only the output to refer to positions
@dataclass(slots=True)
class Position:
    # origin and endpoint are positions, either a gate,wire pair or None
    origin: Optional[Wire] = None
    endpoint: Optional[Wire] = None
    # def __post_init__(self):
    #     if self.origin is None and self.endpoint is None:
    #         raise ValueError(f"Can't have both origin and endpoint None")
    def __repr__(self):
        if self.origin is None and self.endpoint is None:
            return 'LOST'
        elif self.origin is NOWHERE and self.endpoint is NOWHERE:
            return 'LIMBO'
        elif self.origin is None:
            return f'ORIGIN>{self.endpoint}'
        elif self.endpoint is None:
            return f'{self.origin}>SINK'
        elif self.endpoint == NOWHERE:
            return f'{self.origin}'
        else:
            return f'{self.origin}>{self.endpoint}'

LOST: Final[Position] = Position()
LIMBO: Final[Position] = Position(NOWHERE, NOWHERE)

# the number of dimensions in configuration space is 2x the number of particles, one
# for particle position, one for particle sign. A configuration space point is a value
# of weights for all position/sign combinations in the system.
# PCoordinate is, for a particle, a position and a sign, at a specific step in running
@dataclass(slots=True)
class PCoordinate:
    step: int
    pkey: PKey # name and sign
    position: Position
    def __repr__(self):
        return self.key
    def __hash__(self):
        return self.__repr__().__hash__()
    def __eq__(self, other):
        return self.__repr__() == other.__repr__()
    def __lt__(self, other):
        return str(self) < str(other)
    @property
    def key(self):
        return f'{self.step}/{self.pkey}@{self.position}'

# a PCoordValue is a PCoordinate plus a specific particle (for name and weight)
# particle name and sign must match the coordinate
@dataclass(slots=True)
class PCoordValue:
    pcoord: PCoordinate # step, sign, name, position
    particle: Particle
    def __post_init__(self):
        if not isinstance(self.pcoord, PCoordinate):
            raise ValueError(f'pcoord is a {type(self.pcoord)}, not a PCoordinate: {self.pcoord}')
        if not isinstance(self.particle, Particle):
            raise ValueError(f'particle is a {type(self.particle)}, not a Particle: {self.particle}')
        if str(self.particle.pkey) != str(self.pcoord.pkey):
            raise ValueError(f'PCoordValue, mismatched pkeys: {self.pcoord=}, {self.particle.pkey=}')
    def __repr__(self):
        return f'{self.pcoord}:{wstr(self.particle.weight, precision=2)}({self.particle.probability:.2f})'
    def __hash__(self):
        return tuple((self.pcoord.__hash__(), self.particle.weight.__hash__())).__hash__()
    def copy(self):
        new_pcoord = PCoordinate(step=self.pcoord.step, pkey=self.pcoord.pkey, position=self.pcoord.position)
        new_particle = Particle(self.particle.name, self.particle.weight, self.particle.sign,
                                self.particle.next_step, self.particle.precision)
        return PCoordValue(pcoord=new_pcoord, particle=new_particle)

# a complete ConfigSpace coordinate
class CSCoordinate:
    def __init__(self, coords:Tuple[PCoordinate]):
        __slots__ = ('coords',)
        self.coords = sorted(coords, key=lambda x: x.pkey)

    def __repr__(self):
        pstrs = [f'{self.pcvals[k].sign}:{self.axis_coords[k].name}'
                   for k in self.axis_coords.keys()]
        return f'({",".join(pstrs)})'

    @property
    def key(self):
        return f'{"|".join([f'{ac}' for ac in self.pcoords])}'

@dataclass
class ConfigSpacePoint:
    __slots__ = ('step', 'pcvals', 'predecessors', 'successors')
    pcvals: Dict[PCoordinate, Particle]
    def __init__(self, step, initial_values:List[PCoordValue],
                 predecessors:Set[Self]=None, successors:Set[Self]=None):
        self.step = step
        self.pcvals = {x.pcoord.key: x for x in sorted(initial_values, key=lambda x: x.particle.pkey)}
        if predecessors is None: predecessors = set()
        self.predecessors = predecessors
        if successors is None: successors = set()
        self.successors = successors

    @property
    def key(self):
        return f'{self.step}/{"|".join([str(k) for k, v in sorted(self.pcvals.items(), key=lambda x: x[1].particle.pkey)])}'

    def __hash__(self):
        return self.key.__hash__()

    @property
    def weights(self):
        return [p.particle.weight for p in self.pcvals.values()]

    @property
    def weight(self):
        return sum([p.particle.weight for p in self.pcvals.values()])

    @property
    def particles(self):
        return [p.particle for p in self.pcvals.values()]

    def add(self, other:Self, active_gates:set):
        if self.key != other.key:
            raise ValueError(f'keys do not match: self={self.key}, other={other.key}')
        else:
            self.predecessors.add(other)
            other.successors.add(self)
            for k in self.pcvals.keys():
                cur_pcv = self.pcvals[k]
                other_pcv = other.pcvals[k]
                if cur_pcv.pcoord.position.origin not in active_gates:
                    continue
                cur_part = cur_pcv.particle
                other_part = other_pcv.particle
                cur_step = cur_part.next_step
                other_step = other_part.next_step
                if other_pcv.pcoord.step != self.step:
                    log.info(f'{self.step=}, {cur_step=}, {other_step=}, not adding')
                    log.info(f'{self=}, {cur_pcv=}, {other_pcv=}')
                    continue
                # if cur_step == 0 or cur_step < self.step:
                #     log.info(f'{self.step=}, {cur_step=}, {other_step=}, not adding')
                #     log.info(f'{self=}, {cur_pcv=}, {other_pcv=}')
                #     continue
                self.pcvals[k].particle = Particle(name=cur_part.name, sign=cur_part.sign,
                                                   weight=cur_part.weight+other_part.weight,
                                                   next_step=cur_part.next_step)

class ConfigSpace:
    __slots__ = ('index',)
    def __init__(self, initial_point:ConfigSpacePoint):
        self.index = Addict({initial_point.key: initial_point})

    def add(self, other:Self):
        for other_key, other_value in other.index.items():
            if other_key in self.index.keys():
                self.index[other_key].add(other_value)

    def add_point(self, point:ConfigSpacePoint):
        if point.key in self.index.keys():
            self.index[point.key].add(point)
        else:
            self.index[point.key] = point

    def gate_inputs(self, gate):
        return [self.index[key] for key in self.index.keys() if re.match(rf'.+:{gate}.\w+', key)]

    def add_coordinate(self, coord:CSCoordinate):
        if coord.pkey not in self.index.keys():
            self.index[coord.pkey] = coord
        else:
            self.index[coord.pkey].add(coord)

    def add_coordinates(self, coords):
        for coord in coords:
            self.add_coordinate(coord)


class ConfigSpaceRunner:
    def __init__(self, sim=None):
        self.sim = sim

    def __repr__(self):
        # return f'{self.name}: {self.gates}'
        return f'{self.name}'

    def forward_results(self, step, gates, links):
        assign_outs = []
        next_step = step + 1
        for gate in gates.values():
            control_dest = links.get(f'{gate.name}{SEP}control')
            controls = gate.weights['control']
            if control_dest:
                dest_gate, dest_port = control_dest.split(SEP)
            else:
                dest_gate, dest_port = None, None
            if controls:
                dest_pos = Position(Wire(gate.name, 'control'), Wire(dest_gate, dest_port))
                for p in controls:
                    p.next_step = self.sim.gate_step[dest_gate]
                    pcoord = PCoordinate(step=next_step, pkey=p.pkey, position=dest_pos)
                    result_value = PCoordValue(pcoord, p).copy()
                    assign_outs.append(result_value)
            if gate.report_type() == 'DelayGate': continue
            for port in SWITCH_WIRES:
                source = f'{gate.name}{SEP}{port}'
                if links.get(source):
                    dest = links[source]
                    dest_gate, dest_port = dest.split(SEP)
                else:
                    dest_gate, dest_port = None, None
                if gates[gate.name].weights[port]:
                        for p in gates[gate.name].weights[port]:
                            p.next_step = self.sim.gate_step[dest_gate]
                            dest_pos = Position(origin=Wire(gate.name, port),
                                                endpoint=Wire(dest_gate, dest_port))
                            pcoord = PCoordinate(step=next_step, pkey=p.pkey, position=dest_pos)
                            result_value = PCoordValue(pcoord, p).copy()
                            assign_outs.append(result_value)
        return assign_outs

    def run(self, initial_point:ConfigSpacePoint):
        sim = self.sim
        all_worlds = [initial_point]
        worlds = deque([[initial_point]])
        space = ConfigSpace(initial_point)
        step = initial_point.step
        while len(worlds) > 0:
            this_cycle_points = worlds.popleft()
            next_cycle_points = []
            next_step = step + 1
            log.info(f'begin step {step}')
            log.info(f'   input values:')
            for cs_point in this_cycle_points:
                log.info(f'      {cs_point}')
            log.info('')
            dest_gate_names = set()
            for cs_point in this_cycle_points:
                by_position = defaultdict(list)
                dest_gates = {}
                by_coord = {}
                by_dest_coords = defaultdict(list)
                by_particle = defaultdict(list)
                deferred = []

                for pcv in cs_point.pcvals.values():
                    log.debug(f'{pcv=}')
                    if pcv.particle.next_step != step:
                        log.info(f'   deferring {pcv} because {pcv.particle.next_step=} and {step=}')
                        deferred.append(pcv)
                    else:
                        ppos = pcv.pcoord.position.endpoint
                        if ppos.gate is not None:
                            dest_gate_name = ppos.gate
                            by_position[ppos].append(deepcopy(pcv))
                            by_dest_coords[(ppos, pcv.particle.sign)] += [deepcopy(pcv)]
                            dest_gate_names.add(dest_gate_name)

                if len(dest_gate_names) > 0:
                    log.info(f'   next point {cs_point.key}: {", ".join([str(p) for p in cs_point.particles])}')
                    log.info(f'      destination gates: {", ".join([str(sim.gates[g]) for g in dest_gate_names])}')
                    bpvals = sorted(flat_list(list(by_position.values())), key=lambda x: x.particle.pkey)
                    log.info(f'      input weights:')
                    for v in bpvals:
                        log.info(f'         {v}')

                    # reset all gate internal states
                    for gate_name in dest_gate_names:
                        gate = sim.gates[gate_name]
                        gate.reset()
                        dest_gates[gate_name] = gate

                    # set inputs for all current gates
                    for dest_pos, input_pcvs in by_position.items():
                        dest_gate_name = dest_pos.gate
                        if dest_gate_name:
                            dest_port = dest_pos.port
                            dest_gate = sim.gates[dest_gate_name]
                            dest_gate.inputs[dest_port] += [pcv.particle for pcv in input_pcvs]

                    # ensure all inputs have real values (not "undefined"), calculate weights
                    for gate in dest_gates.values():
                        gate.set_weights()

                    outputs = self.forward_results(step=step, gates=dest_gates, links=sim.links)

                # no destination gates
                else:
                    outputs = []

                if len(outputs) > 0:
                    outputs += deferred
                else:
                    if len(deferred) > 0:
                        log.info(f'   no output, but these were deferred:')
                        for pcv in deferred:
                            log.info(f'      {pcv}')

                for pcv in outputs:
                    if pcv.pcoord.position.endpoint == NOWHERE:
                        log.info(f'   {pcv} going nowhere, next_step set to 0')
                        pcv.particle.next_step = 0

                point_outputs = []
                if outputs:
                    for pcv in outputs:
                        by_particle[pcv.particle.name] += [pcv.copy()]
                        if pcv.pcoord in by_coord.keys():
                            by_coord[pcv.pcoord] += [pcv]
                        else:
                            by_coord[pcv.pcoord] = [pcv.copy()]
                    successor_tuples = list(itertools.product(*[by_particle[x] for x in sorted(by_particle.keys())]))
                    nonzero_successors = []
                    for st in successor_tuples:
                        if not np.all([enough(p.particle.probability, ZERO_THRESHOLD) for p in st]):
                            log.info(f'   discarding {st} because it includes a zero weight')
                        else:
                            nonzero_successors.append(st)
                    if len(nonzero_successors) > 0:
                        all_worlds.append(nonzero_successors)

                    for st in nonzero_successors:
                        stpoint = ConfigSpacePoint(next_step, st, predecessors={cs_point})
                        cs_point.successors.add(stpoint)
                        point_outputs.append(stpoint)
                    log.info(f'   finished processing {cs_point}')
                if len(point_outputs) > 0:
                    log.info(f'   unfiltered point outputs:')
                    for point in point_outputs:
                        log.info(f'      {point}')
                else:
                    log.info('   nothing for next cycle')
                log.info('')
                next_cycle_points += point_outputs
                # for point in point_outputs:
                #     point.predecessors.add(cs_point)
                # cs_point.successors |= {*point_outputs}
            # done generating successors for this cycle, now filter and merge

            # report raw outputs
            if len(next_cycle_points) > 0:
                log.info(f'   unfiltered cycle outputs')
                for point in next_cycle_points:
                    log.info(f'      {point}')
            else:
                log.info(f'   NO OUTPUTS')

            # merge points at the same position -> merged_points
            by_key = {}
            for point in next_cycle_points:
                if point.key in by_key.keys():
                    by_key[point.key].add(point, dest_gate_names)
                else:
                    by_key[point.key] = point
            merged_points = list(by_key.values())

            # merged_points -> nonzero_values
            # all nonzero values are added to config space, even if no further output
            nonzero_values = []
            if len(merged_points) > 0:
                log.info(f'   merged:')
                for point in merged_points:
                    if enough(abs(point.weight), ZERO_THRESHOLD):
                        log.info(f'      {point}')
                        nonzero_values.append(point)
                    else:
                        log.info(f'      discarding {point}, not passing {ZERO_THRESHOLD}')
            if len(nonzero_values) > 0:
                log.info(f'   nonzero values:')
                for point in nonzero_values:
                    log.info(f'      {point}')
                    space.add_point(point)

            # nonzero_values -> filtered_values
            filtered_values = []
            for point in nonzero_values:
                if np.all([pcv.pcoord.position.endpoint == NOWHERE or pcv.pcoord.position.origin is None for pcv in point.pcvals.values()]):
                    log.info(f'      ignoring {point}')
                    continue
                filtered_values.append(point)

            # filtered_values -> worlds
            for point in filtered_values:
                log.info(f'   {point}')
            if len(filtered_values) > 0:
                worlds.append(filtered_values)
                log.info(f'   added {len(filtered_values)} points for next step')

            log.info(f'end step {step}, queue length = {len(worlds)}')
            step = next_step
            log.info('')

        log.info('')
        log.info('returning because nothing more to do')
        return space, step
