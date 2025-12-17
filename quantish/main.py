import math
import random
import subprocess
from argparse import ArgumentParser, BooleanOptionalAction, SUPPRESS, ArgumentDefaultsHelpFormatter
import logging
from collections import defaultdict, OrderedDict
from pathlib import Path
import time
import sympy as sym
import math as m
from tqdm import tqdm

import numpy as np
import yaml
from quantish.simulation import Simulation
from quantish.visualizations import diagram
from quantish.qnumber import CalcMode
from quantish.util import QLogger, max_width, flat_list, SEP
from quantish.config_space import WIRES
from quantish.sink import SinkEncoder
from quantish.particle import Particle
from quantish.gate import FredkinGate
import json

def main():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', required=True, help="Path to YAML configuration file")
    parser.add_argument('--configs-dir', default='models', help='Directory for model files')
    parser.add_argument('--use-common', action=BooleanOptionalAction, default=True, help='Load default values from common.yaml before individual model files')
    parser.add_argument('-s', '--simulate', action=BooleanOptionalAction, default=True, help='Run simulation')
    parser.add_argument('-l', '--log', default=None, type=str, help='Log file')
    parser.add_argument('--loglevel', choices=['debug', 'info', 'warning', 'error'])
    parser.add_argument('--preserve-log', action='store_true', help='Preserve existing log file. Default is to wipe it out and start over')
    parser.add_argument('-d', '--diagram', type=str, help="Create a Mermaid diagram of the gate network on the named file with default extension '.mmd'")
    parser.add_argument('--no-diagram', action='store_true', default=SUPPRESS, help='Do not create a diagram')
    parser.add_argument('--diagram-dir', type=str, default='mermaid', help='Directory for Mermaid diagrams')
    parser.add_argument('--svg-diagram', action=BooleanOptionalAction, default=True, help='Create an SVG version of the diagram')
    parser.add_argument('--diagram-when', choices=['before', 'after', 'both'], default='after', help='When to create a diagram, before or after simulation')
    parser.add_argument('--control-threshold', type=float, default=SUPPRESS, help='Probability threshold for considering a control input "present"')
    parser.add_argument('--forward-threshold', type=float, default=SUPPRESS, help='Probability threshold for forwarding output')
    parser.add_argument('--presence-threshold', type=float, default=SUPPRESS, help='Probability threshold for considering a particle "present"')
    parser.add_argument('--normalize-input', action='store_true', help='Normalize weights before measuring')
    parser.add_argument('--normalize-output', action='store_true', help='Normalize weights after measuring')
    parser.add_argument('--symbolic', action='store_true', default=SUPPRESS, help='Force symbolic math')
    parser.add_argument('--numeric', action='store_true', default=SUPPRESS, help='Force numeric math')
    parser.add_argument('--merge-before-measure', action='store_true', help='Merge input particles before measuring')
    parser.add_argument('--merge-before-forward', action='store_true', help='Merge output particles before forwarding')
    parser.add_argument('--add-with-signs', action='store_true', help='Multiply weight values by particle sign when adding particles')
    parser.add_argument('--combine-signs', action=BooleanOptionalAction, default=True, help='Merge plus and minus-signed particles')
    parser.add_argument('--combine-names', action=BooleanOptionalAction, default=True, help='Merge particles with different names')
    parser.add_argument('--sample', action='store_true', help='Take gate output as distributions, run with one random sample')
    parser.add_argument('--n-samples', type=int, default=1, help='Run this many sample executions, collect statistics on results')
    parser.add_argument('--epr-stats', action='store_true', help='Run statistics on EPR experiment model (book figure 4.16)')
    parser.add_argument('--measure-discrepancy', action='store_true', help='Measure discrepancy ')
    parser.add_argument('--full-stats', action='store_true', help='Include particle names and probabilities in results')
    args = parser.parse_args()
    config_path = Path(args.configs_dir, args.config).with_suffix('.yaml')
    config_dir = args.configs_dir
    if args.use_common:
        with open(Path(config_dir, 'common.yaml'), 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    with open(config_path, 'r') as f:
        config.update(yaml.safe_load(f))
    config['config_path'] = args.config
    if args.loglevel is not None:
        loglevel = args.loglevel.upper()
    elif 'loglevel' in config.keys():
        loglevel = config['loglevel'].upper()
    else:
        loglevel = logging.INFO
    if args.log is not None:
        log_path = Path(args.log).with_suffix('.log')
        if not args.preserve_log:
            log_path.unlink(missing_ok=True)
        logging.basicConfig(filename=log_path, format='%(levelname)s:  %(message)s', level=loglevel)
    else:
        logging.basicConfig(format='%(message)s', level=loglevel, handlers=[QLogger()])
    log = logging.getLogger('quantish')
    if args.preserve_log: log.info('')
    if 'symbolic' in args:
        config['symbolic'] = args.symbolic
    if 'numeric' in args:
        config['symbolic'] = not args.numeric
    if args.sample:
        config['sample'] = True
        config['n_samples'] = args.n_samples
    symbolic = config.get('symbolic')
    CalcMode.mode = 'Symbolic' if symbolic else 'Float'
    log.info(f'QUANTISH PHYSICS SIMULATION STARTING: {config["title"]} at {time.asctime()}')
    if 'forward_threshold' in args:
        config['probability_threshold']['fowarding'] = args.forward_threshold
    if 'control_threshold' in args:
        config['probability_threshold']['control'] = args.control_threshold
    if 'presence_threshold' in args:
        config['probability_threshold']['presence'] = args.presence_threshold
    if args.normalize_input:
        config['normalize_weights']['input'] = True
    if args.normalize_output in args:
        config['normalize_weights']['output'] = True
    if args.merge_before_measure:
        config['merge']['before_measure'] = True
    if args.merge_before_forward:
        config['merge']['before_forwarding'] = True
    if args.measure_discrepancy:
        config['measure_discrepancy'] = True
    elif 'measure_discrepancy' not in config.keys():
        config['measure_discrepancy']  = False
    log.info(f"{'SYMBOLIC' if symbolic else 'FLOATING POINT'} MODE")
    q1 = None
    q2 = None
    dpath = None
    has_run = False
    sim = Simulation(config)
    if 'no_diagram' not in args:
        if args.diagram is None:
            dpath = Path(args.diagram_dir, args.config).with_suffix('.mmd')
        else:
            dpath = Path(args.diagram_dir, args.diagram, ).with_suffix('.mmd')
        if 'diagram_when' in args:
            if args.diagram_when in ('before', 'both'):
                before_path = dpath.with_stem(dpath.stem+'_before').with_suffix('.mmd')
                diagram(sim, before_path, False)
                if args.svg_diagram:
                    svg_path = Path(before_path).with_suffix('.svg')
                    subprocess.run(['mmdc', '-i', before_path, '-o', svg_path])
    if args.simulate:
        if not sim.sample:
            experiment_results = sim.propagate_weights()
            has_run = True
        else:
            print('PARTICLES:')
            for particle in sim.particles.values():
                print(f'   {particle}')
            print('GATES:')
            for gate in sim.gates.values():
                print(f'   {gate}')
            histogram = defaultdict(int)
            angle_counts = defaultdict(int)
            pair_counts = defaultdict(int)
            coupled_pair_counts = defaultdict(int)
            for k in ('ab', 'bc', 'ac'):
                pair_counts[k] = 0
                coupled_pair_counts[k] = 0
            discrepancy_count = 0
            disc_ab = 0
            disc_bc = 0
            disc_ac = 0
            up5not6 = 0
            up6not5 = 0
            lo5not6 = 0
            lo6not5 = 0
            coupled_count = 0
            if args.epr_stats:
                epr_histogram = defaultdict(int)
                epr_histogram['coupled-equal'] = 0
                epr_histogram['coupled-unequal'] = 0
                epr_histogram['uncoupled-equal'] = 0
                epr_histogram['uncoupled-unequal'] = 0
            if config['config_path'] == 'fig416plus':
                fig417a = {}
                fig417b = {}
                fig417c = {}
            # gate_names = [g for g in sim.gates.keys()]
            global_result = {}
            for i in tqdm(range(sim.n_samples)):
                # del sim
                # sim = Simulation(config)
                experiment_results = {}
                if config['measure_discrepancy']:
                    angle_choices = ['qa', 'qb', 'qc']
                    # angle_choices = ['qa', 'qc']
                    random.shuffle(angle_choices)
                    q1, q2 = angle_choices[:2]
                    assert q1 != q2
                    # q1, q2 = random.sample(angle_choices, k=2)
                    # q1 = 'qb'
                    # q2 = 'qc'
                    # q2 = random.sample(angle_choices, k=1)[0]
                    # assert q1 != q2
                    # q1 = random.choice(angle_choices)
                    # angle_choices.remove(q1)
                    # q2 = random.choice(angle_choices)
                    # random.shuffle(angle_choices)
                    # q1 = angle_choices.pop()
                    # q2 = angle_choices.pop()
                    angle_counts[q1] += 1
                    angle_counts[q2] += 1
                    pair = None
                    if q1 == 'qa':
                        if q2 == 'qb':
                            pair = 'ab'
                        else:
                            pair = 'ac'
                    elif q1 == 'qb':
                        if q2 == 'qc':
                            pair = 'bc'
                        else:
                            pair = 'ab'
                    elif q1 == 'qc':
                        if q2 == 'qa':
                            pair = 'ac'
                        else:
                            pair = 'bc'
                    pair_counts[pair] += 1
                    config['gates']['g5']['angle'] = config['variables'][q1]
                    config['gates']['g6']['angle'] = config['variables'][q2]
                    del sim
                    sim = Simulation(config)
                for stage in sim.run_stages.values():
                    # val = random.random()
                    # sim.selector = lambda: random.random()
                    stage.run()
                for g in sim.gates.values():
                    if type(g) is FredkinGate:
                        g_result = g.results
                        for wire in WIRES:
                            out_pos = f'{g.name}{SEP}{wire}'
                            if g_result[wire]:
                                experiment_results[out_pos] = g_result[wire]
                            else:
                                experiment_results[out_pos] = None
                    # for gname in ('g5', 'g6'):
                    #     sim.gates[gname] = FredkinGate(gname, config['gates'][gname]['angle'])
                    # del sim
                    # sim = Simulation(config)
                    # experiment_results, _, _ = sim.propagate_weights()
                # for obname in sim.order:
                #     if obname in sim.gates.keys():
                #         g = sim.gates[obname]
                #         g.reset()
                    # experiment_results = sim.propagate_weights()
                    has_run = True
                if config['config_path'] == 'fig49':
                    if experiment_results.get('g2.upper') and experiment_results.get('g3.upper'):
                        histogram['both_upper'] += 1
                    if experiment_results.get('g2.lower') and experiment_results.get('g3.lower'):
                        histogram['both_lower'] += 1
                    if experiment_results.get('g2.upper') is None and experiment_results.get('g3.upper') is None:
                        histogram['neither_upper'] += 1
                    if experiment_results.get('g2.lower') is None and experiment_results.get('g3.lower') is None:
                        histogram['neither_lower'] += 1
                    if experiment_results.get('g2.upper') is None and experiment_results.get('g3.upper') is None:
                        histogram['neither_upper'] += 1
                    if experiment_results.get('g2.upper') and experiment_results.get('g3.upper') is None:
                        histogram['g2_upper_not_g3_upper'] += 1
                    if experiment_results.get('g2.upper') is None and experiment_results.get('g3.upper'):
                        histogram['g3_upper_not_g2_upper'] += 1
                    if experiment_results.get('g2.lower') and experiment_results.get('g3.lower') is None:
                        histogram['g2_lower_not_g3_lower'] += 1
                    if experiment_results.get('g2.lower') is None and experiment_results.get('g3.lower'):
                        histogram['g3_lower_not_g2_lower'] += 1
                # if config['config_path'] == 'fig416plus' and experiment_results.get('g4.upper'):
                #     print('coupled')
                if config['config_path'] == 'fig416plus' and i == 0:
                    g1uw = Particle.merge(flat_list(sim.gates['g1'].port_weights('upper')))
                    g1lw = Particle.merge(flat_list(sim.gates['g1'].port_weights('lower')))
                    g2uw = Particle.merge(flat_list(sim.gates['g2'].port_weights('upper')))
                    g2lw = Particle.merge(flat_list(sim.gates['g2'].port_weights('lower')))
                    g1up_phase = g1uw.weight.phase
                    g2up_phase = g2uw.weight.phase
                    print(f'upper combined phase: {(g1up_phase + g2up_phase).degrees:.2f}, probabilities: {g1uw.probability:.2f}, {g2uw.probability:.2f}')
                    g1lo_phase = g1lw.weight.phase
                    g2lo_phase = g2lw.weight.phase
                    print(f'lower combined phase: {(g1lo_phase + g2lo_phase).degrees:.2f}, probabilities: {g1lw.probability:.2f}, {g2lw.probability:.2f}')
                    fig417a['p1'] = sim.gates['g1'].measure(sim.particles['p1'])
                # q1 = 'qa'
                # q2 = 'qb'
                # config['gates']['g5']['angle'] = config['variables'][q1]
                # config['gates']['g6']['angle'] = config['variables'][q2]
                # experiment_results, experiment_input = sim.run_experiment()
                for k, v in experiment_results.items():
                    if v:
                        global_result[k] = v
                        histogram[k] += 1
                if config['measure_discrepancy']:
                    g1 = sim.gates['g1']
                    g2 = sim.gates['g2']
                    g3 = sim.gates['g3']
                    g4 = sim.gates['g4']
                    g5 = sim.gates['g5']
                    g6 = sim.gates['g6']
                    ag1 = {'control': g1.results['control'], 'swapping': g1.swapping, 'upper': g1.results['upper'], 'lower': g1.results['lower']}
                    ag2 = {'control': g2.results['control'], 'swapping': g2.swapping, 'upper': g2.results['upper'], 'lower': g2.results['lower']}
                    ag3 = {'control': g3.results['control'], 'swapping': g3.swapping, 'upper': g3.results['upper'], 'lower': g3.results['lower']}
                    ag4 = {'control': g4.results['control'], 'swapping': g4.swapping, 'upper': g4.results['upper'], 'lower': g4.results['lower']}
                    ag5 = {'control': g5.results['control'], 'swapping': g5.swapping, 'upper': g5.results['upper'], 'lower': g5.results['lower']}
                    ag6 = {'control': g6.results['control'], 'swapping': g6.swapping, 'upper': g6.results['upper'], 'lower': g6.results['lower']}
                    # if (g3.control is None and g1.results['upper'] is not None) or \
                    #         (g3.control is not None and g1.results['upper'] is None):
                    #     print(f'{g3.control=}, {g1.results["upper"]=}')
                    # if (g4.control is None and g2.results['upper'] is not None) or \
                    #         (g4.control is not None and g2.results['upper'] is None):
                    #     print(f'{g4.control=}, {g2.results["upper"]=}')
                    # assert (g4.control == g4.input['control']) and (g4.input['control'] == g4.results['control'])
                    # assert not (experiment_results.get('g4.upper') and experiment_results.get('g4.lower')), 'g4 both'
                    coupled = (g4.output_wire == 'upper') and (g4.results['upper'] is not None)
                    # Discrepancy occurs when particles end up on different wires (one upper, one lower)
                    if coupled:
                        # if g1.output_wire != g2.output_wire:
                        #     raise RuntimeError(f'coupled, but {g1.output_wire=} and {g2.output_wire=}')
                        coupled_count += 1
                        coupled_pair_counts[pair] += 1
                        g5m = g6m = None
                        discrepancy = False
                        g5up = experiment_results.get('g5.upper')
                        g6up = experiment_results.get('g6.upper')
                        g5lo = experiment_results.get('g5.lower')
                        g6lo = experiment_results.get('g6.lower')
                        discrepancy = g5.output_wire != g6.output_wire
                        # if g5up and g6up:
                        #     g5m = Particle.merge(flat_list(g5up))
                        #     g6m = Particle.merge(flat_list(g6up))
                        #     if not g5m.equiv(g6m):
                        #         discrepancy = True
                        #     # discrepancy = not Particle.merge(flat_list(g5up)).equiv(
                        #     #     Particle.merge(flat_list(g6up)))
                        # if g5lo and g6lo:
                        #     g5m = Particle.merge(flat_list(g5lo))
                        #     g6m = Particle.merge(flat_list(g6lo))
                        #     if not g5m.equiv(g6m):
                        #         discrepancy = True
                            # discrepancy = not Particle.merge(flat_list(g5lo)).equiv(
                            #     Particle.merge(flat_list(g6lo)))
                        # elif g5up and not g6up:
                        #     up5not6 += 1
                        #     discrepancy = True
                        # elif g6up and not g5up:
                        #     up6not5 += 1
                        #     discrepancy = True
                        # elif g5lo and not g6lo:
                        #     lo5not6 += 1
                        #     discrepancy = True
                        # elif g6lo and not g6lo:
                        #     lo6not5 += 1
                        #     discrepancy = True
                        # else:
                        #     discrepancy = False
                        # if i < 10:  # Debug first 10 samples
                        #     print(f"Sample {i}: q1={q1}, q2={q2}, coupled={coupled is not None}, g5_upper={g5_on_upper}, g6_upper={g6_on_upper}, discrepancy={discrepancy}")
                        # assert not (experiment_results.get('g5.upper') is None and experiment_results.get('g6.upper') is None), 'both upper None'
                        # assert not (experiment_results.get('g5.lower') is None and experiment_results.get('g6.lower') is None), 'both lower None'
                        # if (experiment_results.get('g5.upper') and experiment_results.get('g5.lower')):
                        #     raise RuntimeError('impossible')
                        # assert not (experiment_results.get('g5.upper') and experiment_results.get('g5.lower')), 'g5 both'
                        # assert not (experiment_results.get('g6.upper') and experiment_results.get('g6.lower')), 'g6 both'
                        if discrepancy:
                            discrepancy_count += 1
                            if q1 == 'qa':
                                if q2 == 'qb':
                                    disc_ab += 1
                                else:
                                    disc_ac += 1
                            elif q1 == 'qb':
                                if q2 == 'qa':
                                    disc_ab += 1
                                else:
                                    disc_bc += 1
                            elif q1 == 'qc':
                                if q2 == 'qb':
                                    disc_bc += 1
                                else:
                                    disc_ac += 1
                            else:
                                raise RuntimeError(f'invalid value: {q1=}')
                if args.epr_stats:
                    g4_up = experiment_results.get('g4.upper')
                    if g4_up: coupled_count += 1
                    # print(g4_up)
                    if g4_up and g4_up[0].probability > 0:
                        if experiment_results.get('g5.upper') and experiment_results.get('g6.upper'):
                            if np.isclose(float(experiment_results['g5.upper'][0].probability),
                                          float(experiment_results['g6.upper'][0].probability)):
                                epr_histogram['coupled-equal'] += 1
                            else:
                                epr_histogram['coupled-unequal'] += 1
                        elif experiment_results.get('g5.lower') and experiment_results.get('g6.lower'):
                            if np.isclose(float(experiment_results['g5.lower'][0].probability),
                                          float(experiment_results['g6.lower'][0].probability)):
                                epr_histogram['coupled-equal'] += 1
                            else:
                                epr_histogram['coupled-unequal'] += 1
                        else:
                            epr_histogram['coupled-unequal'] += 1
                    else:
                        if experiment_results.get('g5.upper') and experiment_results.get('g6.upper'):
                            if np.isclose(float(experiment_results['g5.upper'][0].probability),
                                          float(experiment_results['g6.upper'][0].probability)):
                                epr_histogram['uncoupled-equal'] += 1
                            else:
                                epr_histogram['uncoupled-unequal'] += 1
                        elif experiment_results.get('g5.lower') and experiment_results.get('g6.lower'):
                            if np.isclose(float(experiment_results['g5.lower'][0].probability),
                                          float(experiment_results['g6.lower'][0].probability)):
                                epr_histogram['uncoupled-equal'] += 1
                            else:
                                epr_histogram['uncoupled-unequal'] += 1
                        else:
                            epr_histogram['uncoupled-unequal'] += 1
            switch_vals = {'control': 0, 'upper': 1, 'lower': 2}
            def switch_order(s):
                if '.' not in s: return s
                # gate, switch = s.split('.')
                splits = s.split('.')
                if len(splits) != 2:
                    raise RuntimeError('oops')
                else:
                    gate, switch = splits
                return gate + str(switch_vals[switch])
            hist_keys = sorted(histogram.keys(), key=lambda x: switch_order(x))
            hist_key_width = max_width(hist_keys)
            count_width = max_width(histogram.values())
            # count_width = len(str(max(histogram.values())))
            # print('LAST ITERATION INput:')
            # state_keys = sorted(experiment_inputs.keys(), key=lambda x: switch_order(x))
            # state_key_width = max_width(state_keys)
            # for k in state_keys:
            #     f_key = f'%-{state_key_width+1}s'
            #     kstr = f_key % k
            #     print(f'   {kstr}: {experiment_inputs[k]}')
            # print('')
            print('FINAL OUTPUTS:')
            result_keys = sorted(experiment_results.keys(), key=lambda x: switch_order(x))
            result_key_width = max_width(result_keys)
            for k in result_keys:
                # if len(experiment_results[k]) > 1:
                #     raise RuntimeError(f'invalid result value: {experiment_results[k]}')
                f_key = f'%-{result_key_width+1}s'
                kstr = f_key % k
                print(f'   {kstr}: {experiment_results[k]}')
            print('')
            print('RESULT COUNTS:')
            for k in hist_keys:
                count = histogram[k]
                # rstr = f' {global_result[k].ps(short=True)}' if k in global_result.keys() and global_result[k] else ''
                if k in global_result.keys() and global_result[k]:
                    # rstr = f' {global_result[k].ps(short=True)}'
                    rstr = f' {global_result[k]}'
                    f_key = f'%-{hist_key_width+1}s'
                    kstr = f_key % k
                    f_count = f'%{count_width+1}d'
                    count_str = f_count % count
                    print(f'   {kstr}: {count_str} ({(count/sim.n_samples):>6.1%}) {rstr}')
            if config['measure_discrepancy']:
                if coupled_count == 0:
                    print('COUPLED COUNT 0!')
                    coupled_count = 1
                if discrepancy_count == 0:
                    print('DISCREPANCY COUNT 0!')
                    discrepancy_count = 1
                print(f'coupled count = {coupled_count}, discrepancy_count = {discrepancy_count}, {disc_ab=}, {disc_bc=}, {disc_ac=}, rate={discrepancy_count/coupled_count:.2f}, rate2={discrepancy_count/sim.n_samples:.2f}')
                print(f'{coupled_pair_counts["ab"]=}, {coupled_pair_counts["bc"]=}, {coupled_pair_counts["bc"]=}')
                v_qa, v_qb, v_qc = (sym.N(sym.deg(sym.sympify(config['variables'][x]))) for x in ['qa', 'qb', 'qc'])
                pred_ac = m.sin(m.radians(v_qc) - m.radians(v_qa))**2
                pred_ab = m.sin(m.radians(v_qb) - m.radians(v_qa))**2
                pred_bc = m.sin(m.radians(v_qc) - m.radians(v_qb))**2
                print(f'qa = {v_qa:.1f}, qb = {v_qb:.1f}, qc = {v_qc:.1f}')
                print(f'counts: qa:{angle_counts["qa"]}, qb:{angle_counts["qb"]}, qc:{angle_counts["qc"]}')
                pcab = pair_counts['ab']
                pcbc = pair_counts['bc']
                pcac = pair_counts['ac']
                pss = ', '.join([f'{pk}: {pair_counts[pk]}' for pk in pair_counts.keys()])
                print(f'pairs: {pss}')
                # print(f'pairs: ab:{pair_counts["ab"]}, bc:{pair_counts["bc"]}, ac:{pair_counts["ac"]}, ba:{pair_counts["ba"]}, bc:{pair_counts["cb"]}, ac:{pair_counts["ca"]}')
                try:
                    print(f'predicted ab={pred_ab:.3f}, bc={pred_bc:.3f}, ac={pred_ac:.3f}, ab+bc={pred_ab+pred_bc:.3f}')
                except ZeroDivisionError:
                    pass
                try:
                    print(f'actual0: ab={disc_ab/sim.n_samples:.3f}, bc={disc_bc/sim.n_samples:.3f}, ac={disc_ac/sim.n_samples:.3f}, ab+bc={(disc_ab+disc_bc)/sim.n_samples:.3f}')
                except ZeroDivisionError:
                    pass
                try:
                    print(f'actual    ab={disc_ab/pcab:.3f}, bc={disc_bc/pcbc:.3f}, ac={disc_ac/pcac:.3f}, ab+bc={disc_ab/pcab+disc_bc/pcbc:.3f}')
                except ZeroDivisionError:
                    pass
                try:
                    print(f'actual2    ab={disc_ab/discrepancy_count:.3f}, bc={disc_bc/discrepancy_count:.3f}, ac={disc_ac/discrepancy_count:.3f}, ab+bc={(disc_ab+disc_bc)/discrepancy_count:.3f}')
                except ZeroDivisionError:
                    pass
                try:
                    print(f'actual3    ab={disc_ab/coupled_count:.3f}, bc={disc_bc/coupled_count:.3f}, ac={disc_ac/coupled_count:.3f}, ab+bc={(disc_ab+disc_bc)/coupled_count:.3f}')
                except ZeroDivisionError:
                    pass
                try:
                    print(f'actual4    ab={disc_ab/coupled_pair_counts['ab']:.3f}, '
                          f'bc={disc_bc/coupled_pair_counts['bc']:.3f}, '
                          f'ac={disc_ac/coupled_pair_counts['ac']:.3f}, '
                          f'ab+bc='
                          f'{(disc_ab+disc_bc)/(coupled_pair_counts['ab'] + coupled_pair_counts['bc']):.3f}')
                except ZeroDivisionError:
                    pass
                print(f'{up5not6=}, {up6not5=}, {lo5not6=}, {lo6not5=}')
            if args.epr_stats:
                print('\nEPR COUNTS:')
                # epr_key_width = len(max(epr_histogram.keys(), key=lambda x: len(str(x))))
                epr_key_width = max_width(epr_histogram.keys())
                epr_count_width = max_width(epr_histogram.values())
                for k in epr_histogram.keys():
                    f_key = f'%-{epr_key_width + 1}s'
                    kstr = f_key % k
                    f_count = f'%{epr_count_width + 1}d'
                    count_str = f_count % epr_histogram[k]
                    print(f'   {kstr}: {count_str}')

    if 'no_diagram' not in args:
        if args.diagram_when in ('after', 'both'):
            after_path = dpath.with_stem(dpath.stem+'_after').with_suffix('.mmd')
            diagram(sim, after_path, has_run)
            if args.svg_diagram:
                svg_path = Path(after_path).with_suffix('.svg')
                subprocess.run(['mmdc', '-i', after_path, '-o', svg_path])

if __name__ == '__main__':
    main()