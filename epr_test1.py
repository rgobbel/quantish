from collections import defaultdict

from quantish.gate import FredkinGate
from quantish.particle import Particle
from quantish.simulation import Simulation
import quantish.qnumber as qn
from quantish.util import SEP, angstr
from quantish.config_space import WIRES
import math as m
from itertools import accumulate
from tqdm import tqdm

G1_ANGLE = qn.qify('pi/6')
G2_ANGLE = qn.qify('pi/6') #G1_ANGLE
G3_ANGLE = 0
G4_ANGLE = G3_ANGLE
# G5_ANGLE = qn.qify('rad(20)')
# G6_ANGLE = G5_ANGLE
# G5_ANGLE = 0
# G6_ANGLE = qn.qify('rad(30)')
G5_ANGLE = qn.qify('pi/5')
# G5_ANGLE = qn.qify('rad(0)')
G6_ANGLE = qn.qify('pi/4')

W_ONE = qn.qify(1)

N_ITER = 1000
# N_CYCLES = 20

config = {
    'title': 'EPR Test',
    'variables': {},
    'merge': {
        'combine_signs': True,
        'before_measure': True,
        'before_forwarding': True
    },
    'probability_threshold': {
        'control': 0,
        'forwarding': 0,
        'selector': -1
    },
    'normalize_weights': {
        'output': True
    },
    'particles': {
        'p1': {'weight': W_ONE, 'sign': 1},
        'p2': {'weight': W_ONE, 'sign': 1},
        'p3': {'weight': W_ONE, 'sign': 1}
    },
    'gates': {
        'g1': {'angle': G1_ANGLE},
        'g2': {'angle': G2_ANGLE},
        'g3': {'angle': G3_ANGLE},
        'g4': {'angle': G4_ANGLE},
        'g5': {'angle': G5_ANGLE},
        'g6': {'angle': G6_ANGLE}
    },
    'links': {
        'p1': 'g1.upper',
        'p2': 'g2.upper',
        'p3': 'g3.upper',
        'g1.upper': 'g3.control',
        'g1.lower': 'g5.lower',
        'g2.upper': 'g4.control',
        'g2.lower': 'g6.lower',
        'g3.control': 'g5.upper',
        'g3.upper': 'g4.upper',
        'g3.lower': 'g4.lower',
        'g4.control': 'g6.upper'
    },
    'phases': []
}

def run1(histogram):
    discrepancy_count = 0
    coupled_count = 0
    for i in range(N_ITER):
        sim = Simulation(config)
        # sim.selector = None
        # if i == 0:
        #     print(f'{sim.gates["g5"]=}, {sim.gates["g6"]=}')
        result = {}
        run_result = sim.run()
        # for obname in sim.order:
        #     if obname in sim.gates.keys():
        #         g = sim.gates[obname]
        #         g.set_weights()
        # for obname in sim.order:
        #     if obname in sim.gates.keys():
        #         g = sim.gates[obname]
        #         g.set_inputs()
        #         g.set_outputs()
        for g in sim.gates.values():
            for wire in WIRES:
                out_pos = f'{g.name}{SEP}{wire}'
                if g.outputs[wire]:
                    result[out_pos] = g.outputs[wire]
                else:
                    result[out_pos] = None
        coupled = sim.gates['g4'].outputs['upper'] is not None
        if coupled:
            coupled_count += 1
            assert sim.gates['g4'].outputs['lower'] is None
            g5up = sim.gates['g5'].outputs['upper'] is not None
            g6up = sim.gates['g6'].outputs['upper'] is not None
            if g5up != g6up:
                discrepancy_count += 1
        # result = sim.propagate_weights()
        for k, v in result.items():
            if v is not None:
                histogram[k] += 1
            # print(f'{k}: {v}')
        if i < N_ITER - 1:
            del sim
    return sim, coupled_count, discrepancy_count

def main():
    # g1 = FredkinGate('g1', qn.qify(G1_ANGLE))
    # g3 = FredkinGate('g3', qn.qify(G3_ANGLE))
    # g5 = FredkinGate('g5', qn.qify(G5_ANGLE))
    #
    # p1 = Particle('p1', 1, 1)
    # p3 = Particle('p3', 1, 1)

    histogram = defaultdict(int)

    # sim = Simulation(config)
    # for obname in sim.order:
    #     if obname in sim.particles.keys():
    #         p = sim.particles[obname]
    #         print(p)

    sim = None

    results = []

    # a5s = [0] + list(accumulate([5] * 17))
    # a6s = [0] + list(accumulate([5] * 17))
    #
    # a5result = []
    # a5pred = []
    # a5divergence = []
    # for a5 in tqdm(a5s):
    #     config['gates']['g5']['angle'] = qn.qify(f'rad({a5})')
    #     a6result = []
    #     a6pred = []
    #     a6div = []
    #     for a6 in tqdm(a6s):
    #         config['gates']['g6']['angle'] = qn.qify(f'rad({a6})')

    sim, coupled_count, discrepancy_count = run1(histogram)
    #         d_rate = discrepancy_count/N_ITER
    #         a6result.append(d_rate)
    #         d_pred = m.sin(m.radians(a6) - m.radians(a5))**2
    #         a6pred.append(d_pred)
    #         d_div = d_rate - d_pred
    #         a6div.append(d_div)
    #     a5result.append(a6result)
    #     a5pred.append(a6pred)
    #     a5divergence.append(a6div)
    #
    # for a6r in a5result:
    #     a6s = ', '.join([f'{x:.2f}' for x in a6r])
    #     print(a6s)
    # print('')
    # for a6p in a5pred:
    #     a6s = ', '.join([f'{x:.2f}' for x in a6p])
    #     print(a6s)
    # print('')
    # for a6d in a5divergence:
    #     a6s = ', '.join([f'{x:.2f}' for x in a6d])
    #     print(a6s)
    # print('')

    gate_names = ['g1', 'g2', 'g3', 'g4', 'g5', 'g6']
    for name in gate_names:
        print(sim.gates[name])
    print('')

    for gate in gate_names:
        for wire in WIRES:
            pos = f'{gate}{SEP}{wire}'
            if pos in histogram.keys():
                print(f'{pos}: {histogram[pos]/N_ITER}')
        print('')
    print(f'G1_ANGLE={angstr(G1_ANGLE, 1)}, G2_ANGLE={angstr(G2_ANGLE, 1)}')
    print(f'G3_ANGLE={angstr(G3_ANGLE, 1)}, G4_ANGLE={angstr(G4_ANGLE, 1)}')
    predicted_discrepancy = (G6_ANGLE - G5_ANGLE).sin**2
    actual_discrepancy = discrepancy_count/N_ITER
    divergence = predicted_discrepancy - actual_discrepancy
    angle_diff = G6_ANGLE-G5_ANGLE
    print(f'G5_ANGLE={angstr(G5_ANGLE, 1)}, G6_ANGLE={angstr(G6_ANGLE, 1)}, difference={angstr(angle_diff, 1)}')
    print(f'{coupled_count=}, rate={coupled_count/N_ITER:.3f}, {discrepancy_count=}, {predicted_discrepancy=:.3f}, {actual_discrepancy=:.3f}, {divergence=:.3f}')
    print(f'{sim.selector=}, {sim.control_threshold=}, {sim.forwarding_threshold=}, {sim.presence_threshold=}')
    # for k, v in histogram.items():
    #     print(f'{k}: {v}')

if __name__ == '__main__':
    main()