import logging
import random
from collections import defaultdict
from addict import Dict

from quantish.particle import Particle
from quantish.util import SEP, enough, sstr
# from quantish.dotdict import DotDict
# from argparse import Namespace

log = logging.getLogger('quantish')

class Coordinate:
    def __init__(self, position, particles=None):
        self.position = position
        self.particles = particles

SWITCH_WIRES = ('upper', 'lower')
WIRES = ('control',) + SWITCH_WIRES
OTHER = Dict({'upper': 'lower', 'lower': 'upper'})
STRAIGHT = Dict({w: w for w in SWITCH_WIRES})
SWAPPED = Dict({w: OTHER[w] for w in SWITCH_WIRES})

def default_wires():
    return Dict({wire: [] for wire in WIRES})

def default_switches():
    return Dict({wire: [] for wire in SWITCH_WIRES})

class RunStage:
    def __init__(self, name, gates=None, config_space=None, predecessor=None):
        self.name = name
        if gates is None:
            gates = []
        self.gates = gates
        self.config_space = config_space
        # self.selector = random.random()
        # for gate in self.gates:
        #     if gate.selector is None:
        #         gate.selector = self.selector

        self._result = None

    def __repr__(self):
        return f'{self.name}: {self.gates}'

    def run(self):
        log.info(f'RUN STAGE: {self.name}, gates={self.gates}')
        for gate in self.gates:
            gate.setup_inputs()
            gate.setup_weights()
            gate.setup_outputs()
        # for gate in self.gates:
        #     gate_result = gate.results
        #     for wire in WIRES:
        #         if gate_result[wire]:
        #             pluses = Particle.merge([x for x in gate_result[wire] if x.sign > 0])
        #             if pluses:
        #                 key = f'+{pluses.name}'
        #                 # if gate.name not in self.config_space.coordinates[key].keys():
        #                 #     self.config_space[]
        #                 self.config_space.coordinates[key][gate.name][wire]  = [pluses]
        #             minuses = Particle.merge([x for x in gate_result[wire] if x.sign < 0])
        #             if minuses:
        #                 key = f'-{minuses.name}'
        #                 if gate.name not in self.config_space.coordinates[key].keys():
        #                     self.config_space.coordinates[key][gate.name] = default_wires()
        #                 self.config_space.coordinates[key][gate.name][wire] = [minuses]
        for gate in self.gates:
            if gate.swap_threshold is not None:
                if callable(gate.swap_threshold):
                    swapstr = f'swap(call)={gate.swap_threshold():.2f}'
                else: swapstr = f'swap={gate.swap_threshold:.2f}'
            else: swapstr = None

            if gate.forwarding_threshold is not None:
                if callable(gate.forwarding_threshold): fwdstr = f'fwd(call)={gate.forwarding_threshold():.2f}'
                else: fwdstr = f'fwd={gate.forwarding_threshold:.2f}'
            else: fwdstr = None

            if swapstr or fwdstr: parmstr = f' (threshold: {", ".join([swapstr, fwdstr])})'
            else: parmstr = ''

            log.info(f'GATE {gate}{parmstr}')
            log.info(f'   INPUTS:')
            for k, v in gate.inputs.items():
                if isinstance(v, list) and len(v) > 1:
                    vm = f'{Particle.merge(v)}: {v}'
                else:
                    vm = f'{v}'
                log.info(f'      {k}: {vm}')
            swapstr = 'UNSWAPPED' if not gate.swapping else 'SWAPPED'
            log.info(f'   {swapstr} WEIGHTS:')
            for k, v in gate.weights.items():
                if isinstance(v, list) and len(v) > 1:
                    vm = f'{Particle.merge(v)}: {v}'
                else:
                    vm = f'{v}'
                log.info(f'      {k}: {vm}')
            log.info(f'   OUTPUTS:')
            for k, v in gate.outputs.items():
                if isinstance(v, list) and len(v) > 1:
                    vm = f'{Particle.merge(v)}: {v}'
                else:
                    vm = f'{v}'
                log.info(f'      {k}: {vm}')
            log.info(f'   RESULTS:')
            for k, v in gate.results.items():
                if isinstance(v, list) and len(v) > 1:
                    vm = f'{Particle.merge(v)}: {v}'
                else:
                    vm = f'{v}'
                pos = f'{gate.name}{SEP}{k}'
                if pos in gate.sim.links.keys():
                    dest = gate.sim.links[pos]
                    dest_str = f' -> {dest}'
                else:
                    dest_str = ''
                log.info(f'      {k}: {vm}{dest_str}')
            log.info('')
        log.info('')


class ConfigurationSpace:
    def __init__(self, particles, gates, wires, sim=None):
        self.particles = [p for p in particles if enough(p.weight, 0)]
        self.gates = gates
        self.wires = wires
        self.coordinates = defaultdict(list)
        self.sim = sim
        # self.dimensions = {f'{sign}{p.name}': None for sign in ('+', '-') for p in particles}
        for particle in particles:
            ppos = self.sim.links[particle.name]
            gname, wire = ppos.split(SEP)
            key = f'{sstr(particle.sign)}{particle.name}'
            self.coordinates[key][gname] = default_wires()
            self.coordinates[key][gname][wire] = [particle]

    def state(self):
        return {f'{sign}{p.name}': self.coordinates[f'{sign}{p.name}'] for sign in ('+', '-') for p in self.particles}

# Figure 4.12
# dimension coordinates below duplicated for plus and minus sign values
# p1:
#    g0.upper->g1.upper
#    g0.lower->0
#    g1.upper->g2.upper
#    g1.lower->g2.lower
#    g2.upper->g3.upper
#    g2.lower->g3.lower
#    g3.upper->0
#    g3.lower->0

# Figure 4.16
# p1:
#    0->g1.upper
#    g1.upper->g3.control
#    g1.lower->g5.lower
#    g3.control->g5.upper
#    g5.upper->0
#    g5.lower->0
# p2:
#    0->g2.upper
#    g2.upper->g4.control
#    g2.lower->g6.lower
#    g4.control->g6.upper
#    g6.upper->0
#    g6.lower->0
# p3:
#    0->g3.upper
#    g3.upper->g4.upper
#    g3.lower->g4.lower
#    g4.upper->0
#    g4.lower->0
#
# initial:
#    +p1@g1.upper
#    +p2@g2.upper
#
# next:
#    +p3@g3.upper, with:
#       +p1@g3.control
#       -p1@g3.control
#     OR:
#       +p1@d1
#       -p1@d1

# p1 possible positions:
#
#       0->g1.upper
#
#       g1.upper->g3.control
#       g1.lower->d1
#
#       d1->d5
#
#       d5->g5.lower
#
#       g5.upper->0
#       g5.lower->0
#
# p2 possible positions:
#
#       0->g2.upper
#
#       g2.upper->d2
#       g2.lower->d3
#
#       d2->g4.control
#
#       d3->d6
#
#       d5->g5.lower
#
#       g5.upper->0
#       g5.lower->0

# initial:
#   +p1@g1.upper, +p2@g2.upper
# transition 1:
#   +p1@g1.upper | g1.lower
#   -p1@g1.upper | g1.lower
#
#   +p2@g2.upper | g2.lower
#   -p2@g2.upper | g2.lower

class GateState:
    def __init__(self, gate, predecessor=None, successors=None):
        self.predecessor = predecessor
        self.successors = successors
        self.gate = gate
        self.input = Dict({'control': None, 'inputs': None, 'outputs': None})
        self.weights = Dict({'control': None, 'inputs': None, 'outputs': None})
        self.output = Dict({'control': None, 'inputs': None, 'outputs': None})
        self.output_wire = None

    def __repr__(self):
        return f'{self.gate.name}(i:{self.input}, w:{self.weights}, l:{self.output}'

class WorldState:
    def __init__(self, gates=None, predecessors=None, successors=None):
        if gates is None:
            gates = {}
        self.gates = gates
        self.predecessors = predecessors
        self.successors = successors

