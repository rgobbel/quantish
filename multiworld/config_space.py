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
                             Sign, SIGNS, WIRES, default_wires, show_points, NOSIGN, zerop)
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
# of complex weight for a specific position/sign combination for all dimensions.
# PCoordinate is, for a particle, a position and a sign, at a specific step in running
@dataclass(slots=True)
class PCoordinate:
    name: str
    sign: Sign
    position: Position
    label: str
    _stepped: bool
    def __init__(self, name:str, sign:Sign, position:Position, label: str='', stepped=False):
        self.name = name
        self.sign = sign
        self.position = position
        self.label = label
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


# a PCoordValue is a PCoordinate plus a weight
# particle name and sign must match the coordinate
@dataclass(slots=True)
class PCoordValue:
    # __slots__ = ('pcoord', 'particle', '_stepped')
    pcoord: PCoordinate # step, sign, name, position
    weight: Complex
    _stepped: bool = True
    consumed: bool = False
    def __post_init__(self):
        if not isinstance(self.pcoord, PCoordinate):
            raise ValueError(f'pcoord is a {type(self.pcoord)}, not a PCoordinate: {self.pcoord}')
        if not isinstance(self.weight, Complex):
            raise ValueError(f'weight is a {type(self.weight)}, not a Complex value: {self.weight}')
        # if str(self.particle.pkey) != str(self.pcoord.pkey):
        #     raise ValueError(f'PCoordValue, mismatched pkeys: {self.pcoord=}, {self.particle.pkey=}')

    def __repr__(self):
        return f'{self.pcoord}:{wstr(self.weight, precision=2)}({probability(self.weight):.2f})'

    def __hash__(self):
        return tuple((self.pcoord.__hash__(), self.weight.__hash__())).__hash__()

    def copy(self):
        new_pcoord = PCoordinate(name=self.pcoord.name, sign=self.pcoord.sign, position=self.pcoord.position)
        # new_particle = Particle(self.particle.name, self.particle.weight, self.particle.sign,
        #                         self.particle.precision, active_gates=self.particle.active_gates,
        #                         trace=self.particle.trace + [f'COPY({self.pcoord}->{new_pcoord}'])
        return PCoordValue(pcoord=new_pcoord, weight=self.weight, _stepped=self._stepped)

    @property
    def sign(self):
        return self.pcoord.sign

    @sign.setter
    def sign(self, value):
        self.pcoord.sign = value

    # @property
    # def unstepped_key(self):
    #     return f'{self.pcoord.unstepped_key}:{wstr(self.particle.weight, precision=2)}({self.particle.probability:.2f})'

    @property
    def key(self):
        return f'{self.pcoord.key}:{wstr(self.weight, precision=2)}({probability(self.weight):.2f})'

    @property
    def stepped(self):
        return self._stepped
    @stepped.setter
    def stepped(self, value):
        self.pcoord.stepped = value
        self._stepped = value

    def __add__(self, other):
        self.weight += other.weight
        return self

# a complete ConfigSpace coordinate
class CSCoordinate:
    def __init__(self, coords:dict[str, PCoordinate]):
        __slots__ = ('coords',)
        self.coords = coords

    def __repr__(self):
        return self.key
        # pstrs = [f'{self.pcvals[k].sign}:{self.axis_coords[k].name}'
        #            for k in self.axis_coords.keys()]
        # return f'({",".join(pstrs)})'

    @property
    def key(self):
        return f'{"|".join([f'{ac.key}' for ac in self.coords.values()])}'

@dataclass
class ConfigSpacePoint:
    __slots__ = ('step', '_coords', '_weight', 'predecessors', 'successors', '_stepped', 'source_gates', 'disallow_excess_weight')
    # pcvals: Dict[PCoordinate, Particle]
    def __init__(self, step:int, coords:dict[str, PCoordinate],
                 weight: Complex=Complex(0),
                 predecessors:Set[Self]=None, successors:Set[Self]=None,
                 source_gates=None, disallow_excess_weight=False):
        self._coords = coords
        self._weight = weight
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
        return self._coords == other.coords

    def copy(self):
        new_coords = {k: PCoordinate(v.name, v.sign, copy(v.position)) for k, v in self.coords.items()}
        return self.__class__(self.step, new_coords, self.weight, copy(self.predecessors), copy(self.successors))

    @property
    def key(self):
        return f'{"|".join([str(coord) for coord in self._coords.values()])}'

    # @property
    # def endkey(self):
    #     return f'{"|".join([v.pcoord.endkey
    #                        for v in sorted(self.pcvals.values(), key=lambda x: x.particle.pkey)])}'

    @property
    def probability(self):
        return probability(self._weight)

    def __repr__(self):
        return f'{self.key}:{self._weight}'

    def __hash__(self):
        return self.key.__hash__()

    # @property
    # def stepped(self):
    #     return self._stepped
    # @stepped.setter
    # def stepped(self, value):
    #     self._stepped = value
    #     # for pcv in self.pcvals.values():
    #     #     pcv.stepped = value

    @property
    def weight(self):
        return self._weight
    @weight.setter
    def weight(self, value):
        self._weight = value

    @property
    def coords(self):
        return self._coords
    @coords.setter
    def coords(self, value):
        self._coords = value

    # @property
    # def particles(self):
    #     return {pkey.name: pkey for pkey, ppos in self.coords.items()}

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
            new_weight = self.weight + other.weight
            if abs(new_weight) > 1:
                log.warning(f'CONFIG_SPACE.ADD WEIGHTS ADD TO MORE THAN 1: {self=}, {other=}')
                if self.disallow_excess_weight: return
            self.weight = new_weight
            # assert cur_pcv.particle.probability + other_pcv.particle.probability <= 1
            # for k in self.pcvals.keys():
            #     cur_pcv = self.pcvals[k]
            #     other_pcv = other.pcvals[k]
            #     if other_pcv.pcoord.position.origin is None or other_pcv.pcoord.position.origin.gate not in active_gates:
            #         log.debug(
            #             f'not adding {other_pcv} to {cur_pcv} because '
            #             f'pcv origin not in {active_gates}')
            #         continue
            #     else:
            #         log.debug(f'CONFIGSPACEPOINT.ADD: ({self}) + ({other})')
            #         cur_part = cur_pcv.particle
            #         other_part = other_pcv.particle
            #         self.pcvals[k].particle = Particle(
            #             name=cur_part.name, sign=cur_part.sign, weight=new_weight,
            #             active_gates=cur_part.active_gates.union(other_part.active_gates),
            #             trace=[cur_part.trace + other_part.trace] + [f'ADD({cur_pcv} + {other_pcv})']
            #         )


class ConfigSpace:
    __slots__ = ('index', 'discards', '_stepped', 'max_step', 'disallow_excess_weight')
    def __init__(self, initial_point:ConfigSpacePoint=None, disallow_excess_weight=False):
        self._stepped = False
        self.max_step = 0
        self.index = {}
        self.discards = defaultdict(list)
        self.disallow_excess_weight = disallow_excess_weight
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

    def add_point(self, point:ConfigSpacePoint, active_gates):
        log.debug(f'CONFIG_SPACE.ADD_POINT: {point}, {active_gates=}')
        self.max_step = max(point.step, self.max_step)
        if point.key not in self.index.keys(): # same point?
            self.index[point.key] = point
        else:
            shared_key = point.key
            existing = self.index[shared_key]
            new_weight = existing.weight + point.weight
            if abs(new_weight) > 1:
                log.error(f'CONFIG_SPACE.ADD_POINT WEIGHTS SUM > 1: {existing.weight=}, {point.weight=}')
                if self.disallow_excess_weight: return
            existing.weight = new_weight

    def add_point_gld(self, point:ConfigSpacePoint, active_particles):
        log.debug(f'CONFIG_SPACE.ADD_POINT: {point}, {active_particles=}')
        self.max_step = max(point.step, self.max_step)
        if point.key not in self.index.keys(): # same point?
            self.index[point.key] = point
        else:
            shared_key = point.key
            existing = self.index[shared_key]
            new_weight = point.weight + existing.weight
            if abs(new_weight) > 1:
                log.error(f'CONFIG_SPACE.ADD_POINT WEIGHTS SUM > 1: {existing=}, {point=}')
            existing.weight = new_weight
            # for p_ex, p_new in zip(existing.pcvals.values(), point.pcvals.values()):
            #     if p_ex.pcoord.position.origin is None:
            #         log.info(f'      {p_ex} at origin, passing through without adding')
            #         new_weights.append(p_ex.particle.weight)
            #     elif p_ex.pcoord.position.origin.port == 'control':
            #             log.info(f'      {p_ex} at control port, passing through without adding')
            #             new_weights.append(p_ex.particle.weight)
            #     elif p_ex.particle.name not in active_particles:
            #         log.info(f'      {p_ex.particle.name} not in {active_particles}, passing through without adding')
            #         new_weights.append(p_ex.particle.weight)
            #     else:
            #         new_weight = p_ex.particle.weight + p_new.particle.weight
            #         if abs(new_weight) > 1:
            #             log.error(f'CONFIG_SPACE.ADD_POINT WEIGHTS SUM > 1: {p_ex=}, {p_new=}')
            #             # if self.disallow_excess_weights: continue
            #         log.debug(f'CONFIGSPACE.ADD_POINT: ({existing}) + ({point})')
            #         # check for all new weights nonzero
            #         if p_new.pcoord.position.origin.port in SWITCH_WIRES: # TODO WTF
            #             p_ex.particle.weight = new_weight

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
                    # if zerop(p.weight):
                    #     log.info(f'   particle {p} does not pass threshold, not forwarding')
                    #     continue
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
                endpoint_str = links[source]
                endpoint = GatePort(*endpoint_str.split(SEP))
            else:
                endpoint = NOWHERE
            if gate.weights[port]:
                    for p in gate.weights[port]:
                        if zerop(p.weight):
                            log.info(f'   point {p} does not pass threshold, not forwarding')
                            continue
                        dest_pos = Position(origin=GatePort(gate.name, port),
                                            endpoint=endpoint)
                        # next_particle = Particle(name=p.name, weight=p.weight, sign=p.sign,
                        #                          next_step=self.sim.gate_step.get(dest_gate, 0),
                        #                          precision=p.precision, active_gates=p.active_gates,
                        #                          trace=p.trace + [f'FORWARD->{dest_pos}'],
                        #                          family_tree=p.family_tree)
                        # pcoord = PCoordinate(name=next_particle.name, sign=next_particle.sign, position=dest_pos)
                        pcoord = PCoordinate(name=p.pcoord.name, sign=p.pcoord.sign, position=dest_pos)
                        result_value = PCoordValue(pcoord, p.weight)
                        outputs.append(result_value)
        return outputs

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
            ## - initialize successor quantish state Q' to the empty list
            Q_prime = ConfigSpace()
            log.info(f'   begin loop over {len(Q.index)} points c in Q')
            log.debug(f'   values in Q:')
            for val in Q.index.values():
                log.debug(f'      {val}')
            log.debug(' ')
            ## for each nonzero-weighted configuration-space point c in Q with associated weight z
            stage_particles = set()  # particles that will be processed in this time step. Some will just be passed along, the equivalent of a Delay Gate in the book.
            for c in Q.index.values():
                something_to_do = False
                skip_this_one = False
                if zerop(c.weight):
                    log.warning(f'       SKIPPING {c} BECAUSE WEIGHT IS ZERO')
                    continue
                c_prime_coords = {}
                for pname, p_coord in c.coords.items():
                    if p_coord.position.endpoint.gate in stage_gates:
                        something_to_do = True
                        stage_particles.add(pname)
                        c_prime_coords[pname] = PCoordinate(pname, sign=NOSIGN, position=copy(LIMBO))
                    else:
                        c_prime_coords[pname] = c.coords[pname]
                c_prime = ConfigSpacePoint(time_t+1,
                                           coords=c_prime_coords,
                                           weight=c.weight, predecessors=copy(c.predecessors), successors=copy(c.successors)) # c' has weight but no position or sign for particles in this stage
                C = [c_prime]
                # we now have list C, with one element, c'

                log.info(f'      begin loop over stage particles ({", ".join(sorted(stage_particles))}), input from {c}')
                ## for each particle p (pname) to which c assigns sign s and wire-position w
                for pname in stage_particles:
                    pcoord = c.coords[pname] # pcv has position (endpoint) and sign
                    wire_pos_w = pcoord.position.endpoint # wire-position w
                    sign_s = pcoord.sign # sign s

                    D = [] ## initialize list D to the empty list

                    log.info(f'         begin loop over {len(C)} points d in C for particle {sign_s}{pname}@{wire_pos_w}')

                    ## for each configuration-space point d in list C
                    for i_d, d in enumerate(C):
                        log.debug(f'            {i_d} : {d}')
                        if wire_pos_w is None: # CAN THIS HAPPEN?
                            raise RuntimeError(f'Invalid position for predecessor point c: {wire_pos_w}')
                        elif wire_pos_w.gate not in stage_gates: # nothing happening with this particle now
                            continue
                            # new_d = d.copy()
                            # D.append(new_d)
                        ## if w is a control wire input
                        elif wire_pos_w.port == 'control':
                            new_d = ConfigSpacePoint(step=d.step, weight=c.weight, predecessors={d},
                                coords={k: PCoordinate(name=v.name, sign=v.sign, position=copy(v.position))
                                        for k, v in c.coords.items()})
                            dest_str = sim.links.get(str(wire_pos_w))
                            if dest_str is not None:
                                dest = GatePort(*dest_str.split(SEP))
                            else:
                                dest = NOWHERE
                            for spname in stage_particles:
                                new_d.coords[spname].sign = c.coords[spname].sign
                            ## set d's p-positon coordinate to the control wire output
                            log.debug(f'new_d.coords[pname].position.endpoint = {dest}')
                            new_d.coords[pname].position.endpoint = dest
                            ## set d's p-sign to s
                            ## append d to D (for some reason Gary put this at the beginning, but whatever)
                            log.debug(f'            CONTROL PASSTHROUGH {d.coords[pname]} -> {new_d.coords[pname]}')
                            c.successors.add(new_d)
                            D.append(new_d)
                        else: # input to a switch wire, do a 4-way split
                            new_ds = []
                            for _ in range(4):
                                dnew = ConfigSpacePoint(
                                    step=d.step,
                                    coords={k: PCoordinate(v.name, v.sign, copy(v.position)) for k, v in d.coords.items()},
                                    weight=Complex(0),
                                    predecessors={d}
                                )
                                new_ds.append(dnew)
                            control_present = False
                            # check if one of the other particles is at the control wire
                            for c_pname, pcoord in c.coords.items():
                                if c_pname == pname:
                                    continue
                                p_dest = pcoord.position.endpoint # looking for something that lands on control
                                if p_dest is None: # not this one, keep going
                                    continue
                                if p_dest.gate == wire_pos_w.gate and p_dest.port == 'control': # found a control input
                                    control_present = True

                            new_sign = [sign_s, -sign_s, sign_s, -sign_s]
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
                                new_ds[i].coords[pname].position.origin = origin
                                if dest_str is not None:
                                    dest = GatePort(*dest_str.split(SEP))
                                else:
                                    w_gate = wire_pos_w.gate
                                    if i < 2:
                                        w_port = wire_pos_w.port
                                    else:
                                        w_port = OTHER[wire_pos_w.port]
                                    dest = GatePort(w_gate, f'{w_port}')
                                new_ds[i].coords[pname].position.endpoint = dest
                                new_ds[i].coords[pname].sign = new_sign[i]
                                i_xform = lambda cp, s: int((not cp) ^ (s == Sign.plus))
                                i_x = i_xform(control_present, sign_s)
                                weight = d.weight * getattr(sim.gates[wire_pos_w.gate], xforms[i][i_x])
                                if abs(weight) > 1:
                                    log.error(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
                                    if self.sim.disallow_excess_weights: skip_this_one = True
                                elif zerop(weight) and sim.disappear_zeros:
                                    continue
                                else:
                                    new_ds[i].weight = weight

                            if not skip_this_one:
                                for new_d in new_ds:
                                    d.successors.add(new_d)
                                D += new_ds
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

            ## set Q to Q'
            for p in Q_prime.index.values():
                all_points.add_point_gld(p, stage_particles)
            Q = Q_prime
            log.info(f'END PROCESSING OF TIME STEP {time_t}, now Q = Q_prime')
            log.info(' ')

        ## end loop over t

        log.info('')
        log.info('finished')
        Q.max_step = len(stages)
        keys = list(Q.index.keys())
        for k in keys:
            if zerop(Q.index[k].weight):
                del Q.index[k]
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
                existing_e = Q_prime.index[d.key]
                new_weight = existing_e.weight + d.weight
                if abs(new_weight) > 1:  # error message, but do it anyway
                    log.error(
                        f'IN MERGE, NEW WEIGHT IS > 1: {new_weight}, {existing_e} + {d}')
                    if self.sim.disallow_excess_weights:
                        continue
                existing_e.weight = new_weight
                existing_e.predecessors.add(d)
                existing_e.successors |= d.successors
                for predecessor in existing_e.predecessors:
                    predecessor.successors.add(d)
                if self.sim.skip_zeros and zerop(new_weight):
                    log.warning(f'       SKIPPING {d} BECAUSE RESULTING WEIGHT IS ZERO')
                    continue
            elif self.sim.skip_zeros and zerop(d.weight):
                log.warning(f'       SKIPPING {d} BECAUSE RESULTING WEIGHT IS ZERO')
                continue
            else:
                log.debug(f'         adding {d}')
                Q_prime.index[d.key] = d
        if self.sim.delete_zeros:
            keys = list(Q_prime.index.keys())
            for key in keys:
                cs_point = Q_prime.index[key]
                if zerop(cs_point.weight):
                    del Q_prime.index[key]
        log.info('      FINISHED MERGE C into Q_prime')
        log.info(' ')
        ## end merge into Q'

    def run_rg(self, initial_point:ConfigSpacePoint):
        sim = self.sim
        space = ConfigSpace(initial_point)
        stage_inputs = {initial_point}
        for step, stage in enumerate(sim.run_stages):
            # collect results for all gates in this stage
            # NOTE: if placed into correct sequence, it's ok to turn a multi-gate
            #       stage into a series of single gates. The result should be the same.
            stage_result = ConfigSpace()
            log.info(f'starting step {step} ({", ".join(stage)})')
            stage_gates = {gname: sim.gates[gname] for gname in stage}
            stage_successors = []
            for j, in_point in enumerate(stage_inputs):
                # - each point generates up to 4 ** (number of particles) successor points
                # - particles at control ports simply forward to the next stage
                # - successor points with the same position and sign are added
                # - zero-weight results disappear
                log.debug(f'IN_POINT {j}: {in_point}')
                skip_this_one = False
                deferred = []
                gate_results = {gname: [] for gname in stage}
                for gate in stage_gates.values():
                    gate.reset()
                for pname, ppos in in_point.coords.items():  #.pcvals.values():
                    destination = ppos.position.endpoint
                    if destination == NOWHERE:
                        skip_this_one = True
                        continue
                    if destination.gate in stage_gates.keys():
                        stage_gates[destination.gate].inputs[destination.port] += [ppos]
                    # else:
                    #     deferred.append([ppos, 'DEFERRED'])
                if skip_this_one: continue
                for gate in stage_gates.values():
                    gate.set_weights(in_point.weight)
                    log.info(f'   processing gate {gate}')
                    gate_results[gate.name] = self.forward_gate_results(gate)
                by_particle = defaultdict(list)
                for gname, goutput in gate_results.items():
                    for pcv in goutput:
                        by_particle[pcv.pcoord.name] += [[pcv, gname]]
                # for coord, gname in deferred:
                #     by_particle[coord.name] += [[coord, gname]]
                successor_tuples = list(itertools.product(*[by_particle[k] for k in sorted(by_particle.keys())]))
                for st in successor_tuples:
                    out_point = ConfigSpacePoint(
                        step=step + 1,
                        coords={x[0].pcoord.name: x[0].pcoord for x in st},
                        weight=sum([x[0].weight for x in st]),
                        source_gates=[x[1] for x in st if x != 'DEFERRED'],
                        predecessors={in_point})
                    in_point.successors.add(out_point)
                    stage_successors.append(out_point)
                    stage_result.add_point(out_point, active_gates=[x[1] for x in st if x[1] != 'DEFERRED'])
                log.debug(f'FINISHED WITH {j}: {in_point}')
                log.debug(' ')

            log.debug('stage_successors:')
            show_points(stage_successors, '   ', logging.DEBUG)
            space = stage_result
            # for point in stage_successors:

            log.info(f'end processing step {step} ({", ".join(stage)}), {len(stage_successors)} outputs')
            stage_inputs = set(stage_successors)
            log.info(' ')

        log.info(' ')
        log.info('returning because nothing more to do')
        return space, space
