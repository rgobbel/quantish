import logging
import random

from particle import Particle
from quantish.util import SEP

log = logging.getLogger('quantish')

class Coordinate:
    def __init__(self, wire, particles):
        self.wire = wire
        self.particles = particles

SWITCH_WIRES = ('upper', 'lower')
WIRES = ('control',) + SWITCH_WIRES
OTHER = {'upper': 'lower', 'lower': 'upper'}
STRAIGHT = {w: w for w in SWITCH_WIRES}
SWAPPED = {w: OTHER[w] for w in SWITCH_WIRES}

def default_wires():
    return {wire: [] for wire in WIRES}

def default_switches():
    return {wire: [] for wire in SWITCH_WIRES}

class RunStage:
    def __init__(self, name, gates=None):
        self.name = name
        if gates is None:
            gates = []
        self.gates = gates
        self.selector = random.random()
        for gate in self.gates:
            gate.selector = self.selector

    def __repr__(self):
        return f'{self.name}: {self.gates}'

    def run(self):
        log.info(f'RUN STAGE: {self.name}, selector={self.selector}')
        for gate in self.gates:
            log.info(f'GATE {gate}')
            gate.set_input()
            log.info(f'   INPUTS:')
            for k, v in gate.input.items():
                if isinstance(v, list) and len(v) > 1:
                    vm = f'{Particle.merge(v)}: {v}'
                else:
                    vm = f'{v}'
                log.info(f'      {k}: {vm}')
            gate.set_weights()
            log.info(f'   WEIGHTS:')
            for k, v in gate.weights.items():
                if isinstance(v, list) and len(v) > 1:
                    vm = f'{Particle.merge(v)}: {v}'
                else:
                    vm = f'{v}'
                log.info(f'      {k}: {vm}')
            gate.set_output()
            log.info(f'   OUTPUTS:')
            for k, v in gate.output.items():
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

class GateState:
    def __init__(self, gate, predecessor=None, successors=None):
        self.predecessor = predecessor
        self.successors = successors
        self.gate = gate
        self.input = {'control': None, 'inputs': None, 'outputs': None}
        self.weights = {'control': None, 'inputs': None, 'outputs': None}
        self.output = {'control': None, 'inputs': None, 'outputs': None}
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

