import logging
import random
import re
from collections import defaultdict, deque
from dataclasses import dataclass
import itertools
from typing import Self, Optional, Dict, List, Tuple, Final, Set
from copy import deepcopy, copy
from multiworld.qnumber import Complex, probability

import networkx as nx
from addict import Addict
import numpy as np
import math as m

from multiworld.particle import Particle, PKey
from multiworld.util import (SEP, enough, SWITCH_WIRES, flat_list, wstr, OTHER,
                             Sign, SIGNS, WIRES, default_wires, show_points, NOSIGN)
import multiworld.qnumber as qn

log = logging.getLogger('multiworld')

# a Wire is specific input or output on a specific gate
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
FINISHED: Final[GatePort] = GatePort('FINISHED')

def stage_step_encode(stage: int, step:int):
    return stage * 10 + step

def stage_step_step(group_step:int):
    return group_step % 10

def stage_step_stage(group_stage:int):
    return group_stage // 10

# positions are connections between gates
# for simplicity's sake, we use only the output to refer to positions
@dataclass(slots=True)
class Position:
    # origin and endpoint are positions, either a gate,wire pair or None
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

ABSENT: Final[Position] = Position(None, None)
LOST: Final[Position] = Position()
LIMBO: Final[Position] = Position(NOWHERE, NOWHERE)

# the number of dimensions in configuration space is 2x the number of particles, one
# for particle position, one for particle sign. A configuration space point is a value
# of weights for all position/sign combinations in the system.
# PCoordinate is, for a particle, a position and a sign, at a specific step in running
@dataclass(slots=True)
class PCoordinate:
    name: str
    sign: Sign
    position: Position
    _stepped: bool
    def __init__(self, name:str, sign:Sign, position:Position, stepped=False):
        self.name = name
        self.sign = sign
        self.position = position
        self._stepped = stepped
    def __repr__(self):
        return self.key
    def __hash__(self):
        return self.__repr__().__hash__()
    def __eq__(self, other):
        return self.__repr__() == other.__repr__()
    def __lt__(self, other):
        return str(self) < str(other)

    @property
    def pkey(self):
        return PKey(self.name, self.sign)

    @pkey.setter
    def pkey(self, value):
        if isinstance(value, PKey):
            self.name = value.name
            self.sign = value.sign
        elif isinstance(value, tuple):
            self.name = value[0]
            self.sign = value[1]
        elif isinstance(value, str):
            self.name = value[:-1]
            self.sign = SIGNS[value[-1]]
        else:
            raise ValueError(f'no way to make a PKey from {value}')

    @property
    def endkey(self):
        return f'{self.pkey}@{self.position.endpoint}'

    @property
    def key(self):
        return f'{self.pkey}@{self.position}'
        # if self._stepped:
        #     return f'{self.step}/{self.pkey}@{self.position}'
        # else:
        #     return f'{self.pkey}@{self.position}'

    # @property
    # def unstepped_key(self):
    #     return f'{self.pkey}@{self.position}'

    @property
    def stepped(self):
        return self._stepped
    @stepped.setter
    def stepped(self, value):
        self._stepped = value


# a PCoordValue is a PCoordinate plus a specific particle
# particle name and sign must match the coordinate
@dataclass(slots=True)
class PCoordValue:
    # __slots__ = ('pcoord', 'particle', '_stepped')
    pcoord: PCoordinate # step, sign, name, position
    particle: Particle
    _stepped: bool = True
    consumed: bool = False
    def __post_init__(self):
        if not isinstance(self.pcoord, PCoordinate):
            raise ValueError(f'pcoord is a {type(self.pcoord)}, not a PCoordinate: {self.pcoord}')
        if not isinstance(self.particle, Particle):
            raise ValueError(f'particle is a {type(self.particle)}, not a Particle: {self.particle}')
        # if str(self.particle.pkey) != str(self.pcoord.pkey):
        #     raise ValueError(f'PCoordValue, mismatched pkeys: {self.pcoord=}, {self.particle.pkey=}')
    def __repr__(self):
        return f'{self.pcoord}:{wstr(self.particle.weight, precision=2)}({self.particle.probability:.2f})'
    def __hash__(self):
        return tuple((self.pcoord.__hash__(), self.particle.weight.__hash__())).__hash__()
    def copy(self):
        new_pcoord = PCoordinate(name=self.particle.name, sign=self.particle.sign, position=self.pcoord.position)
        new_particle = Particle(self.particle.name, self.particle.weight, self.particle.sign,
                                self.particle.precision, active_gates=self.particle.active_gates,
                                trace=self.particle.trace + [f'COPY({self.pcoord}->{new_pcoord}'])
        return PCoordValue(pcoord=new_pcoord, particle=new_particle, _stepped=self._stepped)

    @property
    def sign(self):
        return self.particle.sign

    @sign.setter
    def sign(self, value):
        self.particle.sign = value
        self.pcoord.sign = value

    # @property
    # def unstepped_key(self):
    #     return f'{self.pcoord.unstepped_key}:{wstr(self.particle.weight, precision=2)}({self.particle.probability:.2f})'

    @property
    def key(self):
        return f'{self.pcoord.key}:{wstr(self.particle.weight, precision=2)}({self.particle.probability:.2f})'

    @property
    def stepped(self):
        return self._stepped
    @stepped.setter
    def stepped(self, value):
        self.pcoord.stepped = value
        self._stepped = value

    def __add__(self, other):
        self.particle.weight += other.particle.weight
        return self

# a complete ConfigSpace coordinate
class CSCoordinate:
    def __init__(self, coords:Tuple[PCoordinate]):
        __slots__ = ('coords',)
        self.coords = sorted(coords, key=lambda x: x.pkey)

    def __repr__(self):
        return self.key
        # pstrs = [f'{self.pcvals[k].sign}:{self.axis_coords[k].name}'
        #            for k in self.axis_coords.keys()]
        # return f'({",".join(pstrs)})'

    @property
    def key(self):
        return f'{"|".join([f'{ac.key}' for ac in self.coords])}'

# @dataclass
class ConfigSpacePoint:
    # __slots__ = ('step', 'pcvals', 'predecessors', 'successors', '_stepped', 'source_gates')
    # pcvals: Dict[PCoordinate, Particle]
    def __init__(self, step:int, coords:Tuple[PCoordinate],
                 weight: Complex,
                 predecessors:Set[Self]=None, successors:Set[Self]=None,
                 source_gates=None, disallow_excess_weight=False):
        self.coords = coords
        self.weight = weight
        self.step = step
        self._stepped = True
        self.disallow_excess_weight = disallow_excess_weight
        if predecessors is None: predecessors = set()
        self.predecessors = predecessors
        if successors is None: successors = set()
        self.successors = successors
        if source_gates is None: source_gates = set()
        self.source_gates = source_gates

    # def __iter__(self):
    #     return self.pcvals.values().__iter__()

    def same(self, other):
        return self.coords == other.coords

    def copy(self):
        new_pcvs = [deepcopy(x) for x in self.pcvals.values()]
        return self.__class__(self.step, new_pcvs, self.predecessors, self.successors)

    @property
    def key(self):
        return f'{"|".join([str(coord) for coord in self.coords])}'

    @property
    def endkey(self):
        return f'{"|".join([v.pcoord.endkey
                           for v in sorted(self.pcvals.values(), key=lambda x: x.particle.pkey)])}'

    @property
    def probability(self):
        return probability(self.weight)

    def __repr__(self):
        return self.key

    def __hash__(self):
        return self.key.__hash__()

    @property
    def stepped(self):
        return self._stepped
    @stepped.setter
    def stepped(self, value):
        self._stepped = value
        for pcv in self.pcvals.values():
            pcv.stepped = value

    @property
    def weight(self):
        return self.weight

    @property
    def particles(self):
        return {p.particle.name: p.particle for p in self.pcvals.values()}

    def add(self, other:Self):
        if self.key != other.key:
            raise ValueError(f'keys do not match: self={self.key}, other={other.key}')
        else:
            for predecessor in other.predecessors:
                predecessor.successors.add(self)
            self.predecessors |= other.predecessors
            # for k in self.pcvals.keys():
            #     other_pcv = other.pcvals[k]
            #     if active_destinations and other_pcv.pcoord.position.origin not in active_destinations:
            #         log.debug(
            #             f'not adding {other} to {self} because '
            #             f'pcv origin {other_pcv.pcoord.position.origin} not in active_destinations'
            #             f' ({", ".join([str(dest) for dest in active_destinations])})')
            #         return
            for k in self.pcvals.keys():
                cur_pcv = self.pcvals[k]
                other_pcv = other.pcvals[k]
                if other_pcv.pcoord.position.origin is None or other_pcv.pcoord.position.origin.gate not in active_gates:
                    log.debug(
                        f'not adding {other_pcv} to {cur_pcv} because '
                        f'pcv origin not in {active_gates}')
                    continue
                else:
                    log.debug(f'CONFIGSPACEPOINT.ADD: ({cur_pcv}) + ({other_pcv})')
                    cur_part = cur_pcv.particle
                    other_part = other_pcv.particle
                    new_weight = cur_part.weight + other_part.weight
                    if abs(new_weight) > 1:
                        log.warning(f'CONFIG_SPACE.ADD WEIGHTS ADD TO MORE THAN 1: {cur_pcv=}, {other_pcv=}')
                        if self.disallow_excess_weight: continue
                    # assert cur_pcv.particle.probability + other_pcv.particle.probability <= 1
                    self.pcvals[k].particle = Particle(
                        name=cur_part.name, sign=cur_part.sign, weight=new_weight,
                        active_gates=cur_part.active_gates.union(other_part.active_gates),
                        trace=[cur_part.trace + other_part.trace] + [f'ADD({cur_pcv} + {other_pcv})']
                    )

    @weight.setter
    def weight(self, value):
        self._weight = value


class ConfigSpace:
    __slots__ = ('index', 'discards', '_stepped', 'max_step')
    def __init__(self, initial_point:ConfigSpacePoint=None):
        self._stepped = False
        self.max_step = 0
        self.index = {}
        self.discards = defaultdict(list)
        # self.unstepped_index = {}
        if initial_point is not None:
            self.index[initial_point.key] = initial_point
            # self.unstepped_index[initial_point.key] = initial_point

    # def __iter__(self):
    #     return self.index.values().__iter__()

    def add(self, other:Self):
        for other_key, other_value in other.index.items():
            if other_key in self.index.keys():
                self.index[other_key].add(other_value)

    def add_point_rg(self, point:ConfigSpacePoint, active_gates):
        log.debug(f'CONFIG_SPACE.ADD_POINT: {point}, {active_gates=}')
        self.max_step = max(point.step, self.max_step)
        if point.key not in self.index.keys(): # same point?
            self.index[point.key] = point
        else:
            shared_key = point.key
            existing = self.index[shared_key]
            new_weights = []
            for p_ex, p_new in zip(existing.pcvals.values(), point.pcvals.values()):
                if p_ex.pcoord.position.origin is None:
                    log.info(f'      {p_ex} at origin, passing through without adding')
                    new_weights.append(p_ex.particle.weight)
                elif p_ex.pcoord.position.origin.gate not in active_gates:
                    log.info(f'      {p_ex} origin gate {p_ex.pcoord.position.origin.gate} not in {active_gates}, passing through without adding')
                    new_weights.append(p_ex.particle.weight)
                else:
                    new_weight = p_ex.particle.weight + p_new.particle.weight
                    if abs(new_weight) > 1:
                        log.error(f'CONFIG_SPACE.ADD_POINT WEIGHTS SUM > 1: {p_ex=}, {p_new=}')
                        # if self.disallow_excess_weights: continue
                    log.debug(f'CONFIGSPACE.ADD_POINT: ({existing}) + ({point})')
                    # check for all new weights nonzero
                    if p_new.pcoord.position.origin.port in SWITCH_WIRES: # TODO WTF
                        p_ex.particle.weight = new_weight

    def add_point_gld(self, point:ConfigSpacePoint, active_particles):
        log.debug(f'CONFIG_SPACE.ADD_POINT: {point}, {active_particles=}')
        self.max_step = max(point.step, self.max_step)
        if point.key not in self.index.keys(): # same point?
            self.index[point.key] = point
        else:
            shared_key = point.key
            existing = self.index[shared_key]
            new_weights = []
            for p_ex, p_new in zip(existing.pcvals.values(), point.pcvals.values()):
                if p_ex.pcoord.position.origin is None:
                    log.info(f'      {p_ex} at origin, passing through without adding')
                    new_weights.append(p_ex.particle.weight)
                elif p_ex.pcoord.position.origin.port == 'control':
                        log.info(f'      {p_ex} at control port, passing through without adding')
                        new_weights.append(p_ex.particle.weight)
                elif p_ex.particle.name not in active_particles:
                    log.info(f'      {p_ex.particle.name} not in {active_particles}, passing through without adding')
                    new_weights.append(p_ex.particle.weight)
                else:
                    new_weight = p_ex.particle.weight + p_new.particle.weight
                    if abs(new_weight) > 1:
                        log.error(f'CONFIG_SPACE.ADD_POINT WEIGHTS SUM > 1: {p_ex=}, {p_new=}')
                        # if self.disallow_excess_weights: continue
                    log.debug(f'CONFIGSPACE.ADD_POINT: ({existing}) + ({point})')
                    # check for all new weights nonzero
                    if p_new.pcoord.position.origin.port in SWITCH_WIRES: # TODO WTF
                        p_ex.particle.weight = new_weight

    def gate_inputs(self, gate):
        return [self.index[key] for key in self.index.keys() if re.match(rf'^.+>{gate}\..*$', key)]

    def stage_inputs(self, stage_gates, stage=None):
        stage_points = set()
        stage_pat = f'({"|".join(stage_gates)})'
        candidates = [point for point in
                      [self.index[key] for key in self.index.keys()
                       if re.match(rf'^.+>{stage_pat}\..*$', key)]]
        for point in candidates:
            if point.step == stage:
                stage_points.add(point)
            else:
                pass
            added = False
            for pcv in point.pcvals.values():
                if added: continue
                elif pcv.pcoord.position.origin is None and point.stage == stage:
                    if pcv.pcoord.position.endpoint.gate in stage_gates:
                        stage_points.add(point)
                        added = True
                        continue
                elif pcv.pcoord.position.endpoint and pcv.pcoord.position.endpoint.gate in stage_gates:
                    stage_points.add(point)
        # stage_pat = f'({"|".join(stage_gates)})'
        # stage_points = [point for point in
        #                 [self.index[key] for key in self.index.keys()
        #                  if re.match(rf'^.+>{stage_pat}\..*$', key)]]
        return stage_points

    @property
    def stepped(self):
        return self._stepped
    @stepped.setter
    def stepped(self, value):
        self._stepped = value
        for point in self.index.values():
            point.stepped = value

    # def update_unstepped_index(self):
    #     self.unstepped_index = Addict({p.key: p for p in self.index.values()})

class ConfigSpaceRunner:
    def __init__(self, sim=None):
        self.sim = sim

    def __repr__(self):
        # return f'{self.name}: {self.gates}'
        return f'{self.sim.gates.keys()}'


    # def forward_gate_results(self, gate, links, outputs):
    #     gate_name = gate.name
    #     control_dest = links.get(f'{gate_name}{SEP}control')
    #     controls = gate.weights['control']
    #     if control_dest:
    #         dest_gate, dest_port = control_dest.split(SEP)
    #     else:
    #         dest_gate, dest_port = None, None
    #     if controls:
    #         dest_pos = Position(GatePort(gate_name, 'control'), GatePort(dest_gate, dest_port))
    #         for p in controls:
    #             # if not enough(abs(p.weight), qn.ZERO_THRESHOLD):
    #             #     log.info(f'   particle {p} does not pass threshold, not forwarding')
    #             #     self.sim.discards[p.pkey] += [p]
    #             #     continue
    #             next_particle = Particle(name=p.name, weight=p.weight, sign=p.sign,
    #                                      precision=p.precision, active_gates=p.active_gates,
    #                                      trace=p.trace + [f'FORWARD->{dest_pos}'])
    #             pcoord = PCoordinate(pkey=next_particle.pkey, position=dest_pos)
    #             result_value = PCoordValue(pcoord, next_particle)
    #             outputs[gate_name]['control'] = [result_value]
    #     if gate.report_type() == 'DelayGate': return
    #     for port in SWITCH_WIRES:
    #         source = f'{gate_name}{SEP}{port}'
    #         if links.get(source):
    #             dest = links[source]
    #             dest_gate, dest_port = dest.split(SEP)
    #         else:
    #             dest_gate, dest_port = None, None
    #         if gate.weights[port]:
    #                 for p in gate.weights[port]:
    #                     # if not enough(abs(p.weight), qn.ZERO_THRESHOLD):
    #                     #     log.info(f'   point {p} does not pass threshold, not forwarding')
    #                     #     self.sim.discards[p.pkey] += [p]
    #                     #     continue
    #                     dest_pos = Position(origin=GatePort(gate_name, port),
    #                                         endpoint=GatePort(dest_gate, dest_port))
    #                     next_particle = Particle(name=p.name, weight=p.weight, sign=p.sign,
    #                                              next_step=self.sim.gate_step.get(dest_gate, 0),
    #                                              precision=p.precision, active_gates=p.active_gates,
    #                                              trace=p.trace + [f'FORWARD->{dest_pos}'])
    #                     pcoord = PCoordinate(pkey=next_particle.pkey, position=dest_pos)
    #                     result_value = PCoordValue(pcoord, next_particle)
    #                     outputs[gate_name][port] += [result_value]

    def forward_gate_results(self, gate):
        links = self.sim.links
        discard = False
        outputs = []
        control_dest = links.get(f'{gate.name}{SEP}control')
        controls = gate.weights['control']
        if control_dest:
            dest_gate, dest_port = control_dest.split(SEP)
        else:
            dest_gate, dest_port = gate.name, 'control'
        if controls:
            dest_pos = Position(origin=GatePort(gate.name, 'control'),
                                endpoint=GatePort(dest_gate, dest_port))
            for p in controls:
                if not discard:
                    if not enough(abs(p.weight), qn.ZERO_THRESHOLD):
                        log.info(f'   particle {p} does not pass threshold, not forwarding')
                        continue
                    # next_particle = Particle(name=p.name, weight=p.weight, sign=p.sign,
                    #                          precision=p.precision, active_gates=p.active_gates,
                    #                          trace=p.trace + [f'FORWARD->{dest_pos}'])#,
                    #                          # family_tree=p.family_tree)
                    pcoord = PCoordinate(name=p.name, sign=p.sign, position=dest_pos)
                    result_value = PCoordValue(pcoord, p)
                    outputs.append(result_value)
        if gate.report_type() == 'DelayGate': return outputs
        for port in SWITCH_WIRES:
            source = f'{gate.name}{SEP}{port}'
            if links.get(source):
                dest = links[source]
                dest_gate, dest_port = dest.split(SEP)
            else:
                dest_gate, dest_port = gate.name, f'{port}'
            if gate.weights[port]:
                    for p in gate.weights[port]:
                        if not enough(abs(p.weight), qn.ZERO_THRESHOLD):
                            log.info(f'   point {p} does not pass threshold, not forwarding')
                            continue
                        dest_pos = Position(origin=GatePort(gate.name, port),
                                            endpoint=GatePort(dest_gate, dest_port))
                        # next_particle = Particle(name=p.name, weight=p.weight, sign=p.sign,
                        #                          next_step=self.sim.gate_step.get(dest_gate, 0),
                        #                          precision=p.precision, active_gates=p.active_gates,
                        #                          trace=p.trace + [f'FORWARD->{dest_pos}'],
                        #                          family_tree=p.family_tree)
                        # pcoord = PCoordinate(name=next_particle.name, sign=next_particle.sign, position=dest_pos)
                        pcoord = PCoordinate(name=p.name, sign=p.sign, position=dest_pos)
                        result_value = PCoordValue(pcoord, p)
                        outputs.append(result_value)
        return outputs

    # def forward_results(self, gates, links):
    #     assign_outs = []
    #     for gate in gates:
    #         control_dest = links.get(f'{gate.name}{SEP}control')
    #         controls = gate.weights['control']
    #         if control_dest:
    #             dest_gate, dest_port = control_dest.split(SEP)
    #         else:
    #             dest_gate, dest_port = None, None
    #         if controls:
    #             dest_pos = Position(GatePort(gate.name, 'control'), GatePort(dest_gate, dest_port))
    #             for p in controls:
    #                 next_particle = Particle(name=p.name, weight=p.weight, sign=p.sign,
    #                                          precision=p.precision, active_gates=p.active_gates)
    #                 pcoord = PCoordinate(pkey=next_particle.pkey, position=dest_pos)
    #                 result_value = PCoordValue(pcoord, next_particle)
    #                 assign_outs.append(result_value)
    #         if gate.report_type() == 'DelayGate': continue
    #         for port in SWITCH_WIRES:
    #             source = f'{gate.name}{SEP}{port}'
    #             if links.get(source):
    #                 dest = links[source]
    #                 dest_gate, dest_port = dest.split(SEP)
    #             else:
    #                 dest_gate, dest_port = None, None
    #             if gate.weights[port]:
    #                     for p in gate.weights[port]:
    #                         next_particle = Particle(name=p.name, weight=p.weight, sign=p.sign,
    #                                                  precision=p.precision, active_gates=p.active_gates)
    #                         dest_pos = Position(origin=GatePort(gate.name, port),
    #                                             endpoint=GatePort(dest_gate, dest_port))
    #                         pcoord = PCoordinate(pkey=next_particle.pkey, position=dest_pos)
    #                         result_value = PCoordValue(pcoord, next_particle)
    #                         assign_outs.append(result_value)
    #     return assign_outs

    # def run_gates(self, initial_point:ConfigSpacePoint):
    #     sim = self.sim
    #     space = ConfigSpace(initial_point)
    #     for step, current_stage in enumerate(sim.stages):
    #         gate = sim.gates[current_stage.gate]
    #         # stage_outputs = defaultdict(list)
    #         log.info(f'begin step {step}, gate {gate}')
    #         step_inputs = [x for x in space.index.values() if x.step == step]
    #         gate_inputs = [x for x in step_inputs
    #                        if np.any([pcv.pcoord.position.endpoint.gate == current_stage.gate
    #                                   for pcv in x.pcvals.values()])]
    #         deferred = list(set(step_inputs).difference(set(gate_inputs)))
    #         if len(deferred) > 0:
    #             log.info('deferred:')
    #         for def_point in deferred:
    #             log.info(f'   {def_point}')
    #             stpoint = ConfigSpacePoint(step + 1, list(def_point.pcvals.values()), predecessors={def_point})
    #             # stage_outputs[stpoint.key] += [stpoint]
    #             space.add_point(stpoint, {}, {})
    #         log.info(f'   {len(gate_inputs)} input{"s" if len(gate_inputs) > 1 else ""}')
    #         for input_point in gate_inputs:
    #             active_destinations = set()
    #             split_wires = set()
    #             log.info(f'      processing {input_point}')
    #             by_destination = defaultdict(list)
    #             by_coord = defaultdict(list)
    #             by_particle = defaultdict(list)
    #             gate.reset()
    #             for pcv in input_point.pcvals.values():
    #                 destination = pcv.pcoord.position.endpoint
    #                 dest_gate = destination.gate
    #                 dest_port = destination.port
    #                 if destination.gate != current_stage.gate:
    #                     by_destination[destination] += [pcv.copy()]
    #                     by_particle[pcv.particle.name] += [pcv.copy()]
    #                 else:
    #                     if destination.port in SWITCH_WIRES:
    #                         split_wires.add(destination)
    #                         split_wires.add(GatePort(dest_gate, OTHER[dest_port]))
    #                     gate.inputs[destination.port].append(pcv.particle)
    #                     # pcv.particle.active_gates.add(gate.name)
    #                     active_destinations.add(destination)
    #                     sim.step_particles[step].add(pcv.particle.name)
    #             gate.set_weights()
    #             outputs = self.forward_gate_results(step, gate, sim.links)
    #             log.info(f'      {len(outputs)} outputs')
    #             for pcv in outputs:
    #                 by_destination[pcv.pcoord.position.endpoint] += [pcv]
    #                 by_particle[pcv.particle.name] += [pcv.copy()]
    #             successor_tuples = list(itertools.product(*[by_particle[x] for x in sorted(by_particle.keys())]))
    #             log.info(f'      {len(successor_tuples)} successor tuples')
    #             log.info('')
    #             for st in successor_tuples:
    #                 # stcoord = CSCoordinate(tuple(pcv.pcoord for pcv in st))
    #                 stpoint = ConfigSpacePoint(step + 1, st, predecessors={input_point})
    #                 input_point.successors.add(stpoint)
    #                 # stage_outputs[stpoint.key] += [stpoint]
    #                 by_coord[stpoint.key] += [stpoint]
    #                 log.info(f'      adding {stpoint} to config space')
    #                 space.add_point(stpoint, split_wires, active_destinations)
    #             log.info(' ')
    #         log.info(f'finished step {step}')
    #         log.info(' ')
    #     if log.getEffectiveLevel() == logging.DEBUG:
    #         log.debug(f'final space contents:')
    #         pad_len = [0] * len(list(space.index.values())[0].pcvals.values())
    #         for point in space.index.values():
    #             positions = [p.pcoord.position.origin for p in point.pcvals.values()]
    #             particles = [p.particle for p in point.pcvals.values()]
    #             logstr = [f'{particle.ps(short=True)}@{pos}' for particle, pos in zip(particles, positions)]
    #             for i, s in enumerate(logstr):
    #                 pad_len[i] = max(pad_len[i], len(s))
    #         for point in space.index.values():
    #             positions = [p.pcoord.position.origin for p in point.pcvals.values()]
    #             particles = [p.particle for p in point.pcvals.values()]
    #             logstr = '  |  '.join([f'{f"{particle.ps(short=True)}@{pos}":<{pad_len[i]}}' for i, (particle, pos) in enumerate(zip(particles, positions))])
    #             log.info(f'   {point.step}: {logstr}')
    #     return space
    #
    # def run_stages(self, initial_point:ConfigSpacePoint):
    #     sim = self.sim
    #     space = ConfigSpace(initial_point)
    #     stage_input_points = [initial_point]
    #     for step, current_stage in enumerate(sim.run_stages):
    #         log.info(f'begin step {step}, gates {current_stage}:')
    #         other_pcvs = set()
    #         next_stage_points = []
    #         for in_point in stage_input_points:
    #             gate_output_pcvs = defaultdict(list)
    #             for pcv in in_point.pcvals.values():
    #                 if pcv.pcoord.position.endpoint.gate not in current_stage:
    #                     other_pcvs.add(pcv)
    #             for gate_name in current_stage:
    #                 gate = sim.gates[gate_name]
    #                 gate.reset()
    #                 for pcv in in_point.pcvals.values():
    #                     destination = pcv.pcoord.position.endpoint
    #                     pcv_gate = pcv.pcoord.position.endpoint.gate
    #                     if pcv_gate == gate_name:
    #                         gate.inputs[destination.port] += [pcv.particle]
    #                 gate.set_weights()
    #                 gate_output_pcvs[gate_name] += self.forward_gate_results(gate, sim.links)
    #             stage_output_pcvs = list(gate_output_pcvs.values())
    #             by_particle = defaultdict(list)
    #             for pcv_list in gate_output_pcvs.values():
    #                 for pcv in pcv_list:
    #                     by_particle[pcv.particle.name] += [pcv]
    #             for pcv in other_pcvs:
    #                 by_particle[pcv.particle.name] += [pcv]
    #             successor_tuples = list(itertools.product(*by_particle.values()))
    #             successor_points = []
    #             for st in successor_tuples:
    #                 successor_points.append(ConfigSpacePoint(step+1, st))
    #             for point in successor_points:
    #                 space.add_point(point, current_stage)
    #             next_stage_points += successor_points
    #         log.info(f'finished step {step}')
    #         log.debug('next_stage_points:')
    #         show_points(next_stage_points, '   ', logging.DEBUG)
    #         stage_input_points = next_stage_points
    #         log.info(' ')
    #         step += 1
    #     log.info('all done')
    #     return space

    def run_gld1(self, initial_point:ConfigSpacePoint):
        sim = self.sim
        particle_names = sorted(list(sim.particles.keys()))
        all_points = [initial_point]
        # result_space = ConfigSpace(initial_point)
        Q = {initial_point.key: initial_point} #ConfigSpace(initial_point)
        stages = sim.run_stages
        # stages = [[x] for x in sim.run_order]
        ## For each time-step t
        for time_t, stage_gates in enumerate(stages):
            # begin loop for one time step
            log.info(f'BEGIN STEP {time_t}, {", ".join([str(sim.gates[g]) for g in stage_gates])}')
            # log.info(f'begin step {time_t}, {sim.gates[stage_gates]}')
            ## - initialize successor quantish state Q' to the empty list
            Q_prime = {} #ConfigSpace()
            log.info(f'   begin loop over {len(Q)} points c in Q')
            log.debug(f'   values in Q:')
            for val in Q.values():
                log.debug(f'      {val}')
            log.debug(' ')
            ## for each nonzero-weighted configuration-space point c in Q with associated weight z
            for c in Q.values():
                something_to_do = False
                skip_this_one = False
                # check for weight > 1 for any particle (a bug)
                if np.any([abs(x.particle.weight) > 1 for x in c.pcvals.values()]):
                    losers = []
                    for pcv in c.pcvals.values():
                        if abs(pcv.particle.weight) > 1:
                            losers.append(str(pcv.particle.pkey))
                    log.error(f'BEGINNING OF Q VALUE LOOP, {", ".join(losers)} WEIGHT > 1: {c}')
                    if self.sim.disallow_excess_weights: continue
                # begin loop over points in Q
                # only do nonzero-weight points
                if np.any([abs(p.particle.weight) == 0 for p in c.pcvals.values()]):
                    if self.sim.skip_zeros:
                        losers = []
                        for pcv in c.pcvals.values():
                            if abs(pcv.particle.weight) == 0:
                                losers.append(str(pcv.particle.pkey))
                        log.warning(f'       SKIPPING {c} BECAUSE {", ".join(losers)} WEIGHT IS ZERO')
                        continue
                    elif self.sim.disappear_zeros:
                        losers = []
                        for pcv in c.pcvals.values():
                            if abs(pcv.particle.weight) == 0:
                                losers.append(str(pcv.particle.pkey))
                        log.warning(f'       REMOVING{", ".join(losers)} FROM {c} BECAUSE WEIGHT IS ZERO')
                        continue

                # construct c'
                cprime_components = []
                stage_particles = set() # particles that will be processed in this time step. Some will just be passed along, the equivalent of a Delay Gate in the book.
                for pname in sorted(particle_names):
                    pcv = c.pcvals[pname] # name, weight, position, sign for one particle
                    if abs(pcv.particle.weight) == 0 and self.sim.disappear_zeros:
                        log.warning(f'COMPLETELY IGNORING {pcv.particle}')
                        continue
                    p = pcv.particle.copy()
                    p_z = deepcopy(p.weight)
                    if abs(p_z) > 1: # again, check for invalid weights. Is this needed?
                        log.error(f'IN C_PRIME SETUP LOOP, {p} WEIGHT > 1')
                        if self.sim.disallow_excess_weights: skip_this_one = True
                    p_pos = pcv.pcoord.position.endpoint
                    if p_pos is None or p_pos == NOWHERE: # this one is done
                        cprime_components.append(pcv)
                    elif p_pos.gate not in stage_gates: # nothing happening this time step
                        cprime_components.append(pcv) # just pass it on
                    else:
                        something_to_do = True
                        stage_particles.add(pname)
                        # construct particle value with undetermined sign and position (configuration space dimensions)
                        next_pcv = PCoordValue(
                            pcoord=PCoordinate(name=p.name, sign=NOSIGN, position=Position(origin=p_pos, endpoint=NOWHERE)),
                                               particle=Particle(p.name, weight=p_z, sign=NOSIGN, trace=p.trace))
                        cprime_components.append(next_pcv)
                if skip_this_one or not something_to_do: continue
                c_prime = ConfigSpacePoint(time_t+1, cprime_components, predecessors=c.predecessors, successors=c.successors) # c' has weight but no position or sign
                C = [c_prime]
                # we now have list C, with one element, c'

                log.info(f'      begin loop over stage particles ({", ".join(sorted(stage_particles))}), input from {c}')
                ## for each particle p (pname) to which c assigns sign s and wire-position w
                for pname in sorted(stage_particles):
                    pcv = c.pcvals[pname] # pcv has position (endpoint) and sign
                    wire_pos_w = pcv.pcoord.position.endpoint # wire-position w
                    sign_s = pcv.particle.sign # sign s

                    D = [] ## initialize list D to the empty list

                    log.info(f'         begin loop over {len(C)} points d in C for particle {pcv.particle}@{wire_pos_w}')

                    ## for each configuration-space point d in list C
                    for i_d, d in enumerate(C):
                        log.debug(f'            {i_d} : {d}')
                        if wire_pos_w is None: # CAN THIS HAPPEN?
                            new_d = deepcopy(d)
                            new_d.predecessors = {d}
                            d.successors.add(new_d)
                            D.append(new_d)
                        elif wire_pos_w.gate not in stage_gates: # nothing happening with this particle now
                            new_d = deepcopy(d)
                            D.append(new_d)
                        ## if w is a control wire input
                        elif wire_pos_w.port == 'control':
                            new_d = ConfigSpacePoint(
                                    step=d.step,
                                    initial_values=[deepcopy(pcv) for pcv in d.pcvals.values()],
                                    predecessors={d}
                                )
                            d.successors.add(new_d)
                            dest_str = sim.links.get(str(wire_pos_w))
                            if dest_str is not None:
                                dest = GatePort(*dest_str.split(SEP))
                            else:
                                dest = NOWHERE
                            ## set d's p-positon coordinate to the control wire output
                            new_d.pcvals[pname].pcoord.position.endpoint = dest
                            ## set d's p-sign to s
                            new_d.pcvals[pname].sign = sign_s
                            new_d.pcvals[pname].particle.trace += [f'control{sign_s}:{dest}']
                            ## append d to D (for some reason Gary put this at the beginning, but whatever)
                            log.debug(f'            CONTROL PASSTHROUGH {d.pcvals[pname]} -> {new_d.pcvals[pname]}')
                            D.append(new_d)
                        else: # input to a switch wire, do a 4-way split
                            new_ds = []
                            for _ in range(4):
                                dnew = ConfigSpacePoint(
                                    step=d.step,
                                    initial_values=[deepcopy(pcv) for pcv in d.pcvals.values()],
                                    predecessors={d}
                                )
                                d.successors.add(dnew)
                                new_ds.append(dnew)
                            control_present = False
                            # check if one of the other particles is at the control wire
                            for pcv_pname, pcv in c.pcvals.items():
                                if pcv_pname == pname:
                                    continue
                                pcv_dest = pcv.pcoord.position.endpoint # looking for something that lands on control
                                if pcv_dest is None: # not this one, keep going
                                    continue
                                if pcv_dest.gate == wire_pos_w.gate and pcv_dest.port == 'control': # found a control input
                                    control_present = True

                            if len(pname) != 0:
                                log.info(f'            LOOPING SPLIT of {d.pcvals[pname]}')
                                new_sign = [sign_s, sign_s.negative, sign_s, sign_s.negative]
                                xforms = [
                                    ['cos2_theta', 'sin2_theta'],
                                    ['cos_sin_theta', 'mcos_sin_theta'],
                                    ['sin2_theta', 'cos2_theta'],
                                    ['mcos_sin_theta', 'cos_sin_theta'],
                                ]
                                for i in range(4):
                                    if i < 2:
                                        origin = wire_pos_w
                                        dest_str = sim.links.get(str(wire_pos_w))
                                    else:
                                        origin = GatePort(wire_pos_w.gate, OTHER[wire_pos_w.port])
                                        dest_str = sim.links.get(str(GatePort(wire_pos_w.gate, OTHER[wire_pos_w.port])))
                                    new_ds[i].pcvals[pname].pcoord.position.origin = origin
                                    if dest_str is not None:
                                        dest = GatePort(*dest_str.split(SEP))
                                    else:
                                        w_gate = wire_pos_w.gate
                                        if i < 2:
                                            w_port = wire_pos_w.port
                                        else:
                                            w_port = OTHER[wire_pos_w.port]
                                        dest = GatePort(w_gate, f'{w_port}')
                                        # dest = NOWHERE
                                    new_ds[i].pcvals[pname].pcoord.position.endpoint = dest
                                    new_ds[i].pcvals[pname].sign = new_sign[i]
                                    i_xform = lambda cp, s: int((not cp) ^ (s == Sign.plus))
                                    i_x = i_xform(control_present, sign_s)
                                    weight = d.pcvals[pname].particle.weight * getattr(sim.gates[wire_pos_w.gate], xforms[i][i_x])
                                    if abs(weight) > 1:
                                        log.error(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
                                        if self.sim.disallow_excess_weights: skip_this_one = True
                                    elif abs(weight) == 0 and sim.disappear_zeros:
                                        continue
                                    else:
                                        new_ds[i].pcvals[pname].particle.weight = weight
                                        new_ds[i].pcvals[pname].particle.trace += [f'd{i + 1}{new_sign[i]}:{dest}']

                            # for i in range(4):
                            #     assert new_ds2[i].pcvals[pname].particle.weight == new_ds[i].pcvals[pname].particle.weight

                            # D[pname] += new_ds
                            if not skip_this_one:
                                D += new_ds
                            # for dnew in new_ds: ### NO NO NO!!!
                            #     D.append(dnew)
                        log.info(f'            finished {i_d+1} of {len(C)}')
                    ## end loop over configuration-space points d in successor list C
                    log.info(f'         end loop over points d in C, {len(D)=}, outputs:')
                    for p_d in D:
                        log.debug(f'            {p_d}')
                    ## set C to D
                    C = D
                ## end loop over particles p
                log.info(f'      end loop over particles')
                log.info(' ')

                self.merge_results(C, Q_prime, stage_particles, particle_names, all_points)

            ## end loop over configuration-space points c in Q
            log.info(f'   end loop over points c in Q')

            # result_space.index.update(Q_prime.index)
            ## set Q to Q'
            Q = Q_prime
            log.info(f'END PROCESSING OF TIME STEP {time_t}, now Q = Q_prime')
            log.info(' ')

        ## end loop over t

        log.info('')
        log.info('finished')
        result_space = ConfigSpace()
        for point in Q.values():
            result_space.add_point_gld(point, [])
        result_space.max_step = len(stages)
        return result_space

    def run_gld(self, initial_point:ConfigSpacePoint):
        sim = self.sim
        particle_names = sorted(list(sim.particles.keys()))
        all_points = ConfigSpace(initial_point)
        # result_space = ConfigSpace(initial_point)
        Q = ConfigSpace(initial_point)
        stages = sim.run_stages
        # stages = [[x] for x in sim.run_order]
        ## For each time-step t
        for time_t, stage_gates in enumerate(stages):
            # begin loop for one time step
            log.info(f'BEGIN STEP {time_t}, {", ".join([str(sim.gates[g]) for g in stage_gates])}')
            # log.info(f'begin step {time_t}, {sim.gates[stage_gates]}')
            ## - initialize successor quantish state Q' to the empty list
            Q_prime = ConfigSpace()
            log.info(f'   begin loop over {len(Q.index)} points c in Q')
            log.debug(f'   values in Q:')
            for val in Q.index.values():
                log.debug(f'      {val}')
            log.debug(' ')
            ## for each nonzero-weighted configuration-space point c in Q with associated weight z
            for c in Q.index.values():
                something_to_do = False
                skip_this_one = False
                # check for weight > 1 for any particle (a bug)
                if np.any([abs(x.particle.weight) > 1 for x in c.pcvals.values()]):
                    losers = []
                    for pcv in c.pcvals.values():
                        if abs(pcv.particle.weight) > 1:
                            losers.append(str(pcv.particle.pkey))
                    log.error(f'BEGINNING OF Q VALUE LOOP, {", ".join(losers)} WEIGHT > 1: {c}')
                    if self.sim.disallow_excess_weights: continue
                # begin loop over points in Q
                # only do nonzero-weight points
                if np.any([abs(p.particle.weight) == 0 for p in c.pcvals.values()]):
                    if self.sim.skip_zeros:
                        losers = []
                        for pcv in c.pcvals.values():
                            if abs(pcv.particle.weight) == 0:
                                losers.append(str(pcv.particle.pkey))
                        log.warning(f'       SKIPPING {c} BECAUSE {", ".join(losers)} WEIGHT IS ZERO')
                        continue
                    elif self.sim.disappear_zeros:
                        losers = []
                        for pcv in c.pcvals.values():
                            if abs(pcv.particle.weight) == 0:
                                losers.append(str(pcv.particle.pkey))
                        log.warning(f'       REMOVING{", ".join(losers)} FROM {c} BECAUSE WEIGHT IS ZERO')
                        continue

                # construct c'
                cprime_components = []
                stage_particles = set() # particles that will be processed in this time step. Some will just be passed along, the equivalent of a Delay Gate in the book.
                for pname in sorted(particle_names):
                    pcv = c.pcvals[pname] # name, weight, position, sign for one particle
                    if abs(pcv.particle.weight) == 0 and self.sim.disappear_zeros:
                        log.warning(f'COMPLETELY IGNORING {pcv.particle}')
                        continue
                    p = pcv.particle.copy()
                    p_z = deepcopy(p.weight)
                    if abs(p_z) > 1: # again, check for invalid weights. Is this needed?
                        log.error(f'IN C_PRIME SETUP LOOP, {p} WEIGHT > 1')
                        if self.sim.disallow_excess_weights: skip_this_one = True
                    p_pos = pcv.pcoord.position.endpoint
                    if p_pos is None or p_pos == NOWHERE: # this one is done
                        cprime_components.append(pcv)
                    elif p_pos.gate not in stage_gates: # nothing happening this time step
                        cprime_components.append(pcv) # just pass it on
                    else:
                        something_to_do = True
                        stage_particles.add(pname)
                        # construct particle value with undetermined sign and position (configuration space dimensions)
                        next_pcv = PCoordValue(
                            pcoord=PCoordinate(name=p.name, sign=NOSIGN, position=Position(origin=p_pos, endpoint=NOWHERE)),
                                               particle=Particle(p.name, weight=p_z, sign=NOSIGN, trace=p.trace))
                        cprime_components.append(next_pcv)
                # if skip_this_one or not something_to_do:
                #     continue
                c_prime = ConfigSpacePoint(time_t+1, cprime_components, predecessors=c.predecessors, successors=c.successors) # c' has weight but no position or sign
                C = [c_prime]
                # we now have list C, with one element, c'

                log.info(f'      begin loop over stage particles ({", ".join(sorted(stage_particles))}), input from {c}')
                ## for each particle p (pname) to which c assigns sign s and wire-position w
                for pname in sorted(stage_particles):
                    pcv = c.pcvals[pname] # pcv has position (endpoint) and sign
                    wire_pos_w = pcv.pcoord.position.endpoint # wire-position w
                    sign_s = pcv.particle.sign # sign s

                    D = [] ## initialize list D to the empty list

                    log.info(f'         begin loop over {len(C)} points d in C for particle {pcv.particle}@{wire_pos_w}')

                    ## for each configuration-space point d in list C
                    for i_d, d in enumerate(C):
                        log.debug(f'            {i_d} : {d}')
                        if wire_pos_w is None: # CAN THIS HAPPEN?
                            new_d = deepcopy(d)
                            new_d.predecessors = {c}
                            c.successors.add(new_d)
                            D.append(new_d)
                        elif wire_pos_w.gate not in stage_gates: # nothing happening with this particle now
                            new_d = deepcopy(d)
                            D.append(new_d)
                        ## if w is a control wire input
                        elif wire_pos_w.port == 'control':
                            new_d = ConfigSpacePoint(
                                    step=d.step,
                                    initial_values=[deepcopy(pcv) for pcv in d.pcvals.values()],
                                    predecessors={c}
                                )
                            dest_str = sim.links.get(str(wire_pos_w))
                            if dest_str is not None:
                                dest = GatePort(*dest_str.split(SEP))
                            else:
                                dest = NOWHERE
                            for spname in stage_particles:
                                new_d.pcvals[spname].sign = c.pcvals[spname].sign
                            ## set d's p-positon coordinate to the control wire output
                            new_d.pcvals[pname].pcoord.position.endpoint = dest
                            ## set d's p-sign to s
                            new_d.pcvals[pname].particle.trace += [f'control{sign_s}:{dest}']
                            ## append d to D (for some reason Gary put this at the beginning, but whatever)
                            log.debug(f'            CONTROL PASSTHROUGH {d.pcvals[pname]} -> {new_d.pcvals[pname]}')
                            # new_d.predecessors = {c}
                            c.successors.add(new_d)
                            # all_points.add_point(new_d, stage_particles)
                            D.append(new_d)
                        else: # input to a switch wire, do a 4-way split
                            new_ds = []
                            for _ in range(4):
                                dnew = ConfigSpacePoint(
                                    step=d.step,
                                    initial_values=[deepcopy(pcv) for pcv in d.pcvals.values()],
                                    predecessors={c}
                                )
                                new_ds.append(dnew)
                            control_present = False
                            # check if one of the other particles is at the control wire
                            for pcv_pname, pcv in c.pcvals.items():
                                if pcv_pname == pname:
                                    continue
                                pcv_dest = pcv.pcoord.position.endpoint # looking for something that lands on control
                                if pcv_dest is None: # not this one, keep going
                                    continue
                                if pcv_dest.gate == wire_pos_w.gate and pcv_dest.port == 'control': # found a control input
                                    control_present = True

                            new_sign = [sign_s, sign_s.negative, sign_s, sign_s.negative]
                            xforms = [
                                ['cos2_theta', 'sin2_theta'],
                                ['cos_sin_theta', 'mcos_sin_theta'],
                                ['sin2_theta', 'cos2_theta'],
                                ['mcos_sin_theta', 'cos_sin_theta'],
                            ]
                            for i in range(4):
                                if i < 2:
                                    origin = wire_pos_w
                                    dest_str = sim.links.get(str(wire_pos_w))
                                else:
                                    origin = GatePort(wire_pos_w.gate, OTHER[wire_pos_w.port])
                                    dest_str = sim.links.get(str(GatePort(wire_pos_w.gate, OTHER[wire_pos_w.port])))
                                new_ds[i].pcvals[pname].pcoord.position.origin = origin
                                if dest_str is not None:
                                    dest = GatePort(*dest_str.split(SEP))
                                else:
                                    w_gate = wire_pos_w.gate
                                    if i < 2:
                                        w_port = wire_pos_w.port
                                    else:
                                        w_port = OTHER[wire_pos_w.port]
                                    dest = GatePort(w_gate, f'{w_port}')
                                    # dest = NOWHERE
                                new_ds[i].pcvals[pname].pcoord.position.endpoint = dest
                                new_ds[i].pcvals[pname].sign = new_sign[i]
                                i_xform = lambda cp, s: int((not cp) ^ (s == Sign.plus))
                                i_x = i_xform(control_present, sign_s)
                                weight = d.pcvals[pname].particle.weight * getattr(sim.gates[wire_pos_w.gate], xforms[i][i_x])
                                if abs(weight) > 1:
                                    log.error(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
                                    if self.sim.disallow_excess_weights: skip_this_one = True
                                elif abs(weight) == 0 and sim.disappear_zeros:
                                    continue
                                else:
                                    new_ds[i].pcvals[pname].particle.weight = weight
                                    new_ds[i].pcvals[pname].particle.trace += [f'd{i + 1}{new_sign[i]}:{dest}']

                            # for i in range(4):
                            #     assert new_ds2[i].pcvals[pname].particle.weight == new_ds[i].pcvals[pname].particle.weight

                            # D[pname] += new_ds
                            if not skip_this_one:
                                for new_d in new_ds:
                                    d.successors.add(new_d)
                                    # all_points.add_point(new_d, stage_particles)
                                D += new_ds
                            # for dnew in new_ds: ### NO NO NO!!!
                            #     D.append(dnew)
                        log.info(f'            finished {i_d+1} of {len(C)}')
                    ## end loop over configuration-space points d in successor list C
                    log.info(f'         end loop over points d in C, {len(D)=}, outputs:')
                    for p_d in D:
                        log.debug(f'            {p_d}')
                    ## set C to D
                    C = D
                ## end loop over particles p
                log.info(f'      end loop over particles')
                log.info(' ')

                self.merge_results_gld(C, Q_prime, stage_particles, particle_names)

            ## end loop over configuration-space points c in Q
            log.info(f'   end loop over points c in Q')

            # result_space.index.update(Q_prime.index)
            ## set Q to Q'
            for p in Q_prime.index.values():
                all_points.add_point_gld(p, stage_particles)
            Q = Q_prime
            log.info(f'END PROCESSING OF TIME STEP {time_t}, now Q = Q_prime')
            log.info(' ')

        ## end loop over t

        log.info('')
        log.info('finished')
        # result_space = ConfigSpace()
        # for point in Q.values():
        #     result_space.add_point(point, [])
        # result_space.max_step = len(stages)
        Q.max_step = len(stages)
        return Q, all_points

    def merge_results_rg(self, C:list[ConfigSpacePoint], Q_prime:ConfigSpace, stage_particles:list[str], particle_names:list[str]):
        log.info(f'      BEGIN MERGE of {len(C)} points d in C into Q_prime')
        for i_d, d in enumerate(C):
            Q_prime.add_point_gld(d, active_particles=stage_particles)

    def merge_results_gld(self, C, Q_prime, stage_particles, particle_names):
        ## We've now assembled a list C of c's successor configuration-space points,
        ## each with all coordinates now specified.
        log.info(f'      BEGIN MERGE of {len(C)} points d in C into Q_prime')
        ## for each configuration-point d in C
        for i_d, d in enumerate(C):
            ## if a point e with identical coordinates is already in Q', increment e's weight by d's weight.
            if d.key in Q_prime.index.keys():
                delete = False
                existing_e = Q_prime.index[d.key]
                p_prev = None
                p_new = None
                if log.getEffectiveLevel() == logging.DEBUG:
                    p_prev = str(existing_e)
                    p_new = str(d)
                # if not d.same(existing):
                for pname in particle_names:
                    if d.pcvals[pname].pcoord.position.origin is not None and d.pcvals[pname].pcoord.position.origin.port == 'control':
                        log.warning(
                            f'       SKIPPING {d.pcvals[pname]} BECAUSE {pname} IS AT A CONTROL WIRE')
                        continue
                    if pname in stage_particles:
                        new_weight = existing_e.pcvals[pname].particle.weight + d.pcvals[pname].particle.weight
                        if abs(new_weight) > 1:  # error message, but do it anyway
                            log.error(
                                f'IN MERGE, NEW WEIGHT IS > 1: {new_weight}, {existing_e.pcvals[pname]} + {d.pcvals[pname]}')
                            if self.sim.disallow_excess_weights:
                                continue
                        if log.getEffectiveLevel() == logging.DEBUG:
                            log.debug(
                                f'         found {d.key}: {d.pcvals[pname].particle.pkey} {qn.to_native(existing_e.pcvals[pname].particle.weight):.2f} + {qn.to_native(d.pcvals[pname].particle.weight):.2f} -> {qn.to_native(new_weight):.2f} ({d})')
                        new_particle = Particle(
                            name=pname,
                            weight=new_weight,
                            sign=existing_e.pcvals[pname].particle.sign
                        )
                        existing_e.pcvals[pname].particle = new_particle
                    else:
                        log.warning(
                            f'       SKIPPING {existing_e.pcvals[pname]} + {d.pcvals[pname]} BECAUSE {pname} not in ({", ".join(stage_particles)})')
                existing_e.predecessors.add(d)
                existing_e.successors |= d.successors
                for predecessor in existing_e.predecessors:
                    predecessor.successors.add(d)
            elif self.sim.skip_zeros and np.any([abs(p.weight) == 0 for p in d.particles.values()]):
                losers = []
                for pcv in d.pcvals.values():
                    if abs(pcv.particle.weight) == 0:
                        losers.append(str(pcv.particle.pkey))
                log.warning(f'       SKIPPING {d} BECAUSE IN INPUT VALUE {", ".join(losers)} WEIGHT IS ZERO')
            else:
                log.debug(f'         adding {d}')
                Q_prime.index[d.key] = d
        if self.sim.delete_zeros:
            keys = list(Q_prime.index.keys())
            for key in keys:
                delete = False
                cs_point = Q_prime.index[key]
                for p in cs_point.particles.values():
                    if abs(p.weight) == 0:
                        delete = True
                        log.info(f'DELETING {cs_point} BECAUSE {p.pkey} WEIGHT IS ZERO')
                        del Q_prime.index[key]
                if delete:
                    continue
        log.info('      FINISHED MERGE C into Q_prime')
        log.info(' ')
        ## end merge into Q'

    def run_rg(self, initial_point:ConfigSpacePoint):
        sim = self.sim
        space = ConfigSpace(initial_point)
        stage_inputs = {initial_point}
        for step, stage in enumerate(sim.run_stages):
            log.info(f'starting step {step} ({", ".join(stage)})')
            stage_gates = {gname: sim.gates[gname] for gname in stage}
            stage_successors = []
            for j, in_point in enumerate(stage_inputs):
                log.debug(f'IN_POINT {j}: {in_point}')
                deferred = []
                gate_results = {gname: [] for gname in stage}
                for gate in stage_gates.values():
                    gate.reset()
                for pcv in in_point.pcvals.values():
                    destination = pcv.pcoord.position.endpoint
                    if destination.gate in stage:
                        stage_gates[destination.gate].inputs[destination.port] += [pcv.particle]
                    else:
                        deferred.append([pcv, 'DEFERRED'])
                for gate in stage_gates.values():
                    gate.set_weights()
                    log.info(f'   processing gate {gate}')
                    gate_results[gate.name] = self.forward_gate_results(gate)
                by_particle = defaultdict(list)
                for gname, goutput in gate_results.items():
                    for pcv in goutput:
                        by_particle[pcv.particle.name] += [[pcv, gname]]
                for pcv, gname in deferred:
                    by_particle[pcv.particle.name] += [[pcv, gname]]
                successor_tuples = list(itertools.product(*[by_particle[k] for k in sorted(by_particle.keys())]))
                for st in successor_tuples:
                    out_point = ConfigSpacePoint(step + 1, (x[0] for x in st), source_gates=[x[1] for x in st if x != 'DEFERRED'], predecessors={in_point})
                    in_point.successors.add(out_point)
                    stage_successors.append(out_point)
                    space.add_point_rg(out_point, active_gates=[x[1] for x in st if x[1] != 'DEFERRED'])
                log.debug(f'FINISHED WITH {j}: {in_point}')
                log.debug(' ')

            log.debug('stage_successors:')
            show_points(stage_successors, '   ', logging.DEBUG)
            # for point in stage_successors:

            log.info(f'end processing step {step} ({", ".join(stage)}), {len(stage_successors)} outputs')
            stage_inputs = set(stage_successors)
            log.info(' ')

        log.info(' ')
        log.info('returning because nothing more to do')
        return space, space
