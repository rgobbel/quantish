class Coordinate:
    def __init__(self, wire, particles):
        self.wire = wire
        self.particles = particles

WIRES = ('control', 'upper', 'lower')
SWITCH_WIRES = ('upper', 'lower')

def default_wires():
    return {wire: [] for wire in WIRES}

class GateState:
    def __init__(self, key, gate, control=None, upper=None, lower=None, predecessor=None):
        self.predecessor = predecessor
        self.key = key
        self.gate = gate
        self.control = control
        self.upper = upper
        self.lower=lower

    def __repr__(self):
        return f'{self.gate.name}(c:{self.control}, u:{self.upper}, l:{self.lower}'
