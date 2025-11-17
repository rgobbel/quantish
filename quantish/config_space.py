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

class GateState:
    def __init__(self, key, gate, control=None, upper=None, lower=None, predecessor=None, successors=None):
        self.predecessor = predecessor
        self.successors = successors
        self.key = key
        self.gate = gate
        self.control = control
        self.upper = upper
        self.lower=lower

    def __repr__(self):
        return f'{self.gate.name}(c:{self.control}, u:{self.upper}, l:{self.lower}'
