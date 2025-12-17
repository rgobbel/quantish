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
    def __init__(self, gates=None):
        if gates is None:
            gates = []
        self.gates = gates

    def run(self):
        for gate in self.gates:
            gate.set_input()
            gate.set_weights()
            gate.set_output()

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

