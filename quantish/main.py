import logging
import math as m
import random
import subprocess
import time
from argparse import ArgumentParser, BooleanOptionalAction, SUPPRESS, ArgumentDefaultsHelpFormatter
from collections import defaultdict
from pathlib import Path

import numpy as np
import sympy as sym
import yaml
from tqdm import tqdm

from quantish.config_space import WIRES
from quantish.gate import FredkinGate, DelayGate
from quantish.particle import Particle
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation
from quantish.util import QLogger, max_width, flat_list, SEP
from quantish.visualizations import diagram

def main():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', required=True, help="REQUIRED Path to YAML configuration file")
    parser.add_argument('--configs-dir', default='models', help='Directory for model files')
    parser.add_argument('--use-common', action=BooleanOptionalAction, default=True, help='Load default values from common.yaml before individual model files')
    parser.add_argument('-s', '--simulate', action=BooleanOptionalAction, default=True, help='Run simulation')
    parser.add_argument('-l', '--log', default=None, type=str, help='Log file')
    parser.add_argument('--loglevel', choices=['debug', 'info', 'warning', 'error'], help='Default is info if not sampling, warning if sampling')
    parser.add_argument('--preserve-log', action='store_true', help='Preserve existing log file')
    parser.add_argument('-d', '--diagram', type=str, help="Create a Mermaid diagram of the gate network on the named file with default extension '.mmd'")
    parser.add_argument('--no-diagram', action='store_true', default=SUPPRESS, help='Do not create a diagram')
    parser.add_argument('--diagram-dir', type=str, default='mermaid', help='Directory for Mermaid diagrams')
    parser.add_argument('--svg-diagram', action=BooleanOptionalAction, default=True, help='Create an SVG version of the diagram. Requires mmdc command-line Mermaid renderer')
    parser.add_argument('--diagram-when', choices=['before', 'after', 'both'], default='after', help='When to create a diagram, before or after simulation')
    parser.add_argument('--control-threshold', type=float, default=SUPPRESS, help='Probability threshold for considering a control input "present"')
    parser.add_argument('--forward-threshold', type=float, default=SUPPRESS, help='Probability threshold for forwarding output')
    parser.add_argument('--presence-threshold', type=float, default=SUPPRESS, help='Probability threshold for considering a particle "present"')
    parser.add_argument('--normalize-input', action='store_true', help='Normalize weights before measuring')
    parser.add_argument('--normalize-output', action='store_true', help='Normalize weights before forwarding')
    parser.add_argument('--symbolic', action='store_true', default=SUPPRESS, help='Force symbolic math')
    parser.add_argument('--numeric', action='store_true', default=SUPPRESS, help='Force numeric math')
    parser.add_argument('--merge-before-measure', action='store_true', help='Merge input particles before measuring')
    parser.add_argument('--merge-before-forward', action='store_true', help='Merge output particles before forwarding')
    parser.add_argument('--add-with-signs', action='store_true', help='Multiply weight values by particle sign when adding particles')
    parser.add_argument('--combine-signs', action=BooleanOptionalAction, default=True, help='Merge plus and minus-signed particles')
    parser.add_argument('--combine-names', action=BooleanOptionalAction, default=True, help='Merge particles with different names')
    parser.add_argument('--sample', action='store_true', help='Run multiple trials and collect a histogram of results')
    parser.add_argument('--n-samples', type=int, default=1, help='Run this many sampling trials')
    parser.add_argument('--epr-stats', action='store_true', help='Run statistics on EPR experiment model (book figure 4.16)')
    parser.add_argument('--measure-discrepancy', action='store_true', help='Measure discrepancy for EPR experiment. Assumes a network consistent with book figure 4.16')
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
        if config.get('sample'):
            loglevel = logging.WARN
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
    if 'forward_threshold' in args: config['probability_threshold']['fowarding'] = args.forward_threshold
    if 'control_threshold' in args: config['probability_threshold']['control'] = args.control_threshold
    if 'presence_threshold' in args: config['probability_threshold']['presence'] = args.presence_threshold
    if args.normalize_input: config['normalize_weights']['input'] = True
    if args.normalize_output in args: config['normalize_weights']['output'] = True
    if args.merge_before_measure: config['merge']['before_measure'] = True
    if args.merge_before_forward: config['merge']['before_forwarding'] = True
    if args.measure_discrepancy: config['measure_discrepancy'] = True
    elif 'measure_discrepancy' not in config.keys(): config['measure_discrepancy']  = False
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
            experiment_results = sim.run()
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
            disc_ba = 0
            disc_cb = 0
            disc_ca = 0
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
            global_result = {}
            w1w3 = None
            w1w4 = None
            w2w3 = None
            w2w4 = None
            w1w3m = None
            w1w4m = None
            w2w3m = None
            w2w4m = None

            w1aw3 = None
            w1aw4 = None
            w2aw3 = None
            w2aw4 = None
            w1aw3m = None
            w1aw4m = None
            w2aw3m = None
            w2aw4m = None

            w1aw3a = None
            w1aw4a = None
            w2aw3a = None
            w2aw4a = None
            w1aw3am = None
            w1aw4am = None
            w2aw3am = None
            w2aw4am = None

            for i in tqdm(range(sim.n_samples)):
                experiment_results = {}
                if config['measure_discrepancy']:
                    angle_choices = ['qa', 'qb', 'qc']
                    # angle_choices = ['qa', 'qc']
                    random.shuffle(angle_choices)
                    q1, q2 = angle_choices[:2]
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
                            pair = 'ba'
                    elif q1 == 'qc':
                        if q2 == 'qa':
                            pair = 'ca'
                        else:
                            pair = 'cb'
                    pair_counts[pair] += 1
                    config['gates']['g5']['angle'] = config['variables'][q1]
                    config['gates']['g6']['angle'] = config['variables'][q2]
                    del sim
                    sim = Simulation(config)
                else:
                    del sim
                    sim = Simulation(config)
                for stage in sim.run_stages.values():
                    stage.run()
                if config['measure_discrepancy']:
                    for gate, var in zip([sim.gates['g5'], sim.gates['g6']], [q1, q2]):
                        for angle in ['qa', 'qb', 'qc']:
                            if var == angle:
                                if gate.output_wire == 'upper':
                                    histogram[f'{angle}.upper'] += 1
                                else:
                                    histogram[f'{angle}.lower'] += 1
                for g in sim.gates.values():
                    if type(g) is FredkinGate:
                        g_result = g.results
                        for wire in WIRES:
                            out_pos = f'{g.name}{SEP}{wire}'
                            if g_result[wire]:
                                experiment_results[out_pos] = g_result[wire]
                            else:
                                experiment_results[out_pos] = None
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
                    g1lo_phase = g1lw and g1lw.weight.phase
                    g2lo_phase = g2lw and g2lw.weight.phase
                    if g1lo_phase and g2lo_phase:
                        print(f'lower combined phase: {(g1lo_phase + g2lo_phase).degrees:.2f}, probabilities: {g1lw.probability:.2f}, {g2lw.probability:.2f}')
                    else:
                        print(f'{g1lw=}, {g2lw=}')
                    fig417a['p1'] = sim.gates['g1'].measure(sim.particles['p1'])
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
                    coupled = g4.output_wire == 'upper' # and (g4.results['upper'] is not None)

                    # Discrepancy occurs when particles end up on different wires (one upper, one lower)
                    if coupled:
                        if not w1aw3:
                            g5up = sim.gates['g5'].output['upper'] or []
                            g6up = sim.gates['g6'].input['upper'] or []
                            w1aw3 = (g5up + g6up) or []
                            w1aw3m = Particle.merge(w1aw3)
                        if not w2aw3:
                            g5lo = sim.gates['g5'].output['lower'] or []
                            g6up = sim.gates['g6'].input['upper'] or []
                            w2aw3 = (g5lo + g6up) or []
                            w2aw3m = Particle.merge(w2aw3)
                        if not w1aw4:
                            g5up = sim.gates['g5'].output['upper'] or []
                            g6lo = sim.gates['g6'].input['upper'] or []
                            w1aw4 = (g5up + g6lo) or []
                            w1aw4m = Particle.merge(w1aw4)
                        if not w2aw3:
                            g5lo = sim.gates['g5'].output['lower'] or []
                            g6lo = sim.gates['g6'].input['upper'] or []
                            w2aw3 = (g5lo + g6lo) or []
                            w2aw3m = Particle.merge(w2aw3)

                        if not w1aw3a:
                            g5up = sim.gates['g5'].output['upper'] or []
                            g6up = sim.gates['g6'].output['upper'] or []
                            w1aw3a = (g5up + g6up) or []
                            w1aw3am = Particle.merge(w1aw3a)
                        if not w2aw3a:
                            g5lo = sim.gates['g5'].output['lower'] or []
                            g6up = sim.gates['g6'].output['upper'] or []
                            w2aw3a = (g5lo + g6up) or []
                            w2aw3am = Particle.merge(w2aw3a)
                        if not w1aw4a:
                            g5up = sim.gates['g5'].output['upper'] or []
                            g6lo = sim.gates['g6'].output['lower'] or []
                            w1aw4a = (g5up + g6lo) or []
                            w1aw4am = Particle.merge(w1aw4a)
                        if not w2aw4a:
                            g5lo = sim.gates['g5'].output['lower'] or []
                            g6lo = sim.gates['g6'].output['lower'] or []
                            w2aw4a = (g5lo + g6lo) or []
                            w2aw4am = Particle.merge(w2aw4a)

                        if w1w3 is None and g5.output_wire == 'upper' and g6.output_wire == 'upper':
                            g5up = sim.gates['g1'].weights['upper'] or []
                            g6up = sim.gates['g2'].weights['upper'] or []
                            w1w3 = g5up + g6up
                            w1w3m = Particle.merge(w1w3)
                        if w2w4 is None and g5.output_wire == 'lower' and g6.output_wire == 'lower':
                            g5lo = sim.gates['g1'].weights['lower'] or []
                            g6lo = sim.gates['g2'].weights['lower'] or []
                            w2w4 = g5lo + g6lo
                            w2w4m = Particle.merge(w2w4)
                        if w1w4 is None and g5.output_wire == 'upper' and g6.output_wire == 'lower':
                            g5up = sim.gates['g1'].weights['upper'] or []
                            g6lo = sim.gates['g2'].weights['lower'] or []
                            w1w4 = g5up + g6lo
                            w1w4m = Particle.merge(w1w4)
                        if w2w3 is None and g5.output_wire == 'lower' and g6.output_wire == 'upper':
                            g5lo = sim.gates['g1'].weights['lower'] or []
                            g6up = sim.gates['g2'].weights['upper'] or []
                            w1w4 = g5lo + g6up
                            w1w4m = Particle.merge(w1w4)

                        for gate, var in zip([sim.gates['g5'], sim.gates['g6']], [q1, q2]):
                            for angle in ['qa', 'qb', 'qc']:
                                if var == angle:
                                    if gate.output_wire == 'upper':
                                        histogram[f'{angle}.upper_coupled'] += 1
                                    else:
                                        histogram[f'{angle}.lower_coupled'] += 1
                        coupled_count += 1
                        coupled_pair_counts[pair] += 1
                        discrepancy = g5.output_wire != g6.output_wire
                        if discrepancy:
                            discrepancy_count += 1
                            if q1 == 'qa':
                                if q2 == 'qb':
                                    disc_ab += 1
                                else:
                                    disc_ac += 1
                            elif q1 == 'qb':
                                if q2 == 'qa':
                                    disc_ba += 1
                                else:
                                    disc_bc += 1
                            elif q1 == 'qc':
                                if q2 == 'qb':
                                    disc_cb += 1
                                else:
                                    disc_ca += 1
                            else:
                                raise RuntimeError(f'invalid value: {q1=}')
                if args.epr_stats:
                    g4_up = experiment_results.get('g4.upper')
                    if g4_up: coupled_count += 1
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
            switch_vals = {'control': 0, 'upper': 1, 'lower': 2, 'upper_coupled': 3, 'lower_coupled': 4}
            def switch_order(s):
                if '.' not in s: return s
                gate, switch = s.split('.')
                return gate + str(switch_vals[switch])
            hist_keys = sorted(histogram.keys(), key=lambda x: switch_order(x))
            hist_key_width = max_width(hist_keys)
            count_width = max_width(histogram.values())
            print('FINAL OUTPUTS:')
            print('   FREDKIN GATES:')
            result_keys = sorted(experiment_results.keys(), key=lambda x: switch_order(x))
            result_key_width = max_width(result_keys)
            for k in result_keys:
                if experiment_results[k] is None:
                    v = 'None'
                else:
                    v = Particle.merge(experiment_results[k])
                print(f'      {k:{result_key_width+1}s}: {v}')
            print('')
            print('DELAY GATES:')
            for k, v in sim.gates.items():
                if type(v) is DelayGate:
                    if v.state is None:
                        vstr = 'None'
                    else:
                        vstr = f'{Particle.merge(v.state)}'
                    print(f'    {k}: {vstr} {v}')
            print('')
            print('RESULT COUNTS:')
            for k in hist_keys:
                count = histogram[k]
                if k in global_result.keys() and global_result[k]:
                    print(f'   {k:{hist_key_width}s}: {count:{count_width}d} ({(count/sim.n_samples):>6.1%}) {Particle.merge(global_result[k])}')
            if config['measure_discrepancy']:
                if coupled_count == 0:
                    print('COUPLED COUNT 0!')
                    coupled_count = 1
                if discrepancy_count == 0:
                    print('DISCREPANCY COUNT 0!')
                    discrepancy_count = 1
                acounts = defaultdict(int)
                print('')

                print('Figure 4.17:')
                print('   a:')
                print(f'      w1,w3 = {w1w3m} {w1w3}')
                print(f'      w1,w4 = {w1w4m} {w1w4}')
                print(f'      w2,w3 = {w2w3m} {w2w3}')
                print(f'      w2,w4 = {w2w4m} {w2w4}')
                print('')

                print('   b:')
                print(f'      w1a,w3 = {w1aw3m} {w1aw3}')
                print(f'      w1a,w4 = {w1aw4m} {w1aw4}')
                print(f'      w2a,w3 = {w2aw3m} {w2aw3}')
                print(f'      w2a,w4 = {w2aw4m} {w2aw4}')
                print('')

                print('   c:')
                print(f'      w1a,w3a = {w1aw3am} {w1aw3a}')
                print(f'      w1a,w4a = {w1aw4am} {w1aw4a}')
                print(f'      w2a,w3a = {w2aw3am} {w2aw3a}')
                print(f'      w2a,w4a = {w2aw4am} {w2aw4a}')
                print('')

                print('uncoupled lower/angle total:')
                for angle in ['qa', 'qb', 'qc']:
                    upstr = f'{angle}.upper'
                    lostr = f'{angle}.lower'
                    upcount = histogram[upstr]
                    locount = histogram[lostr]
                    atotal = upcount + locount
                    acounts[angle] = locount/atotal
                    print(f'{angle}: {locount}/{atotal}={(locount/atotal):.3f}')
                print('')
                print('coupled lower/angle total:')
                c_acounts = defaultdict(int)
                for angle in ['qa', 'qb', 'qc']:
                    upstr = f'{angle}.upper_coupled'
                    lostr = f'{angle}.lower_coupled'
                    upcount = histogram[upstr]
                    locount = histogram[lostr]
                    atotal = upcount + locount
                    c_acounts[angle] = locount / atotal
                    print(f'{angle}: {locount}/{atotal}={(locount / atotal):.3f}')
                print('')

                print(f'uncoupled qb-qa={acounts["qb"]-acounts["qa"]:.3f}, qc-qb={acounts["qc"]-acounts["qb"]:.3f}, qc-qa={acounts["qc"]-acounts["qa"]:.3f}')
                print(f'coupled qb-qa={c_acounts["qb"]-c_acounts["qa"]:.3f}, qc-qb={c_acounts["qc"]-c_acounts["qb"]:.3f}, qc-qa={c_acounts["qc"]-c_acounts["qa"]:.3f}')
                print(f'coupled count = {coupled_count} ({coupled_count/sim.n_samples:.2%}), discrepancy_count = {discrepancy_count} ({discrepancy_count/coupled_count:.2%}), {disc_ab=}, {disc_bc=}, {disc_ac=}, {disc_ba=}, {disc_cb=}, {disc_ca=}')
                print(f'disc/coupled={discrepancy_count/coupled_count:.2f}, disc/samples={discrepancy_count/sim.n_samples:.2f}')
                print(f'coupled_pair_counts: ab={coupled_pair_counts["ab"]}, bc={coupled_pair_counts["bc"]}, ac={coupled_pair_counts["ac"]}, ba={coupled_pair_counts["ba"]}, cb={coupled_pair_counts["cb"]}, ca={coupled_pair_counts["ca"]}')
                v_qa, v_qb, v_qc = (sym.N(sym.deg(sym.sympify(config['variables'][x]))) for x in ['qa', 'qb', 'qc'])
                print(f'{v_qa=:.3f}, {v_qb=:.3f}, {v_qc=:.3f}')
                pred_ac = m.sin(m.radians(v_qc) - m.radians(v_qa))**2
                pred_ab = m.sin(m.radians(v_qb) - m.radians(v_qa))**2
                pred_bc = m.sin(m.radians(v_qc) - m.radians(v_qb))**2
                pred_ab_bc = pred_ab + pred_bc
                print(f'qa = {v_qa:.1f}º, qb = {v_qb:.1f}º, qc = {v_qc:.1f}º')
                print(f'angles: qa:{angle_counts["qa"]}, qb:{angle_counts["qb"]}, qc:{angle_counts["qc"]}')
                pcab = pair_counts['ab']
                pcbc = pair_counts['bc']
                pcac = pair_counts['ac']
                pcba = pair_counts['ba']
                pccb = pair_counts['cb']
                pcca = pair_counts['ca']
                cpcab = coupled_pair_counts['ab']
                cpcbc = coupled_pair_counts['bc']
                cpcac = coupled_pair_counts['ac']
                cpcba = coupled_pair_counts['ba']
                cpccb = coupled_pair_counts['cb']
                cpcca = coupled_pair_counts['ca']
                pss = ', '.join([f'{pk}: {pair_counts[pk]}' for pk in pair_counts.keys()])
                print(f'pairs: {pss}')
                print('')

                # print(f'pairs: ab:{pair_counts["ab"]}, bc:{pair_counts["bc"]}, ac:{pair_counts["ac"]}, ba:{pair_counts["ba"]}, bc:{pair_counts["cb"]}, ac:{pair_counts["ca"]}')

                measures = ['coupled pair counts', 'n_samples', 'pair counts', 'discrepancy count', 'coupled count']
                pad_len = max([len(s) for s in measures])

                discs = [disc_ab, disc_bc, disc_ac, disc_ab+disc_bc, disc_ba, disc_cb, disc_ba+disc_cb]

                rate_calc = lambda term, divisor: term/divisor

                try:
                    m_type = 'predicted'
                    hit = '*' if pred_ac > pred_ab+pred_bc else ''
                    print(f'{m_type: >{pad_len}}: ab={pred_ab:.3f},          bc={pred_bc:.3f},          ac={pred_ac:.3f},          ab+bc={pred_ab_bc:.3f}{hit}')
                    print('')
                except ZeroDivisionError:
                    pass

                # discrepancy rates / coupled pair counts
                try:
                    rate_ab = disc_ab/cpcab
                    rate_bc = disc_bc/cpcbc
                    rate_ab_bc = (disc_ab + disc_bc) / (cpcab + cpcbc)
                    rate_ac = disc_ac/cpcac
                    rate_ba = disc_ba/cpcba
                    rate_cb = disc_cb/cpccb
                    rate_ba_cb = (disc_ba+disc_cb) / (cpcba + cpccb)
                    rate_ca = disc_ca/cpcca
                    avg_ab = (disc_ab + disc_ba) / (cpcab + cpcba)
                    avg_bc = (disc_bc + disc_cb) / (cpcbc + cpccb)
                    avg_ac = (disc_ac + disc_ca) / (cpcac + cpcca)
                    avg_ab_bc = (disc_ab + disc_ba + disc_bc + disc_cb) / (cpcab + cpcba + cpcbc + cpccb)
                    m_type = 'coupled pair counts'
                    hit = '*' if rate_ac > rate_ab_bc else ''
                    print(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
                    hit = '*' if rate_ca > rate_ba_cb else ''
                    print(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
                    print(f'{"avg":>{pad_len}}: ba={avg_ab:.3f} ({pred_ab-avg_ab:> 6.3f}), cb={avg_bc:.3f} ({pred_bc-avg_bc:> 6.3f}), ca={avg_ac:.3f} ({pred_ac-avg_ac:> 6.3f}), ba+cb={avg_ab_bc:.3f} ({pred_ab_bc-avg_ab_bc:> 6.3f}){hit}')
                    print('')
                except ZeroDivisionError:
                    pass

                # discrepancy rates / total number of trials, both coupled and uncoupled
                try:
                    divisor = sim.n_samples
                    rate_ab = disc_ab/divisor
                    rate_bc = disc_bc/divisor
                    rate_ab_bc = (disc_ab + disc_bc) / divisor
                    rate_ac = disc_ac/divisor
                    rate_ba = disc_ba/divisor
                    rate_cb = disc_cb/divisor
                    rate_ba_cb = (disc_ba+disc_cb) / divisor
                    rate_ca = disc_ca/divisor
                    m_type = 'n_samples'
                    hit = '*' if rate_ac > rate_ab_bc else ''
                    print(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
                    hit = '*' if rate_ca > rate_ba_cb else ''
                    print(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
                    print('')
                except ZeroDivisionError:
                    pass

                # discrepancy rates / pair counts, both coupled and uncoupled
                # try:
                #     rate_ab = disc_ab/pcab
                #     rate_bc = disc_bc/pcbc
                #     rate_ab_bc = (disc_ab + disc_bc) / (pcab+pcbc)
                #     rate_ac = disc_ac/pcac
                #     rate_ba = disc_ba/pcba
                #     rate_cb = disc_cb/pccb
                #     rate_ba_cb = (disc_ba+disc_cb) / (pcba+pccb)
                #     rate_ca = disc_ca/pcca
                #     m_type = 'pair counts'
                #     print(f'{m_type: >{pad_len}}: ab={rate_ab:.3f}, bc={rate_bc:.3f}, ac={rate_ac:.3f}, ab+bc={rate_ab_bc:.3f}')
                #     print(f'{" ":>{pad_len}}: ba={rate_ba:.3f}, cb={rate_cb:.3f}, ca={rate_ca:.3f}, ba+cb={rate_ba_cb:.3f}')
                # except ZeroDivisionError:
                #     pass

                # individual discrepancy rates / total number of discrepancies
                try:
                    divisor = discrepancy_count
                    rate_ab = disc_ab/divisor
                    rate_bc = disc_bc/divisor
                    rate_ab_bc = (disc_ab + disc_bc) / divisor
                    rate_ac = disc_ac/divisor
                    rate_ba = disc_ba/divisor
                    rate_cb = disc_cb/divisor
                    rate_ba_cb = (disc_ba+disc_cb) / divisor
                    rate_ca = disc_ca/divisor
                    m_type = 'discrepancy count'
                    hit = '*' if rate_ac > rate_ab_bc else ''
                    print(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
                    hit = '*' if rate_ca > rate_ba_cb else ''
                    print(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
                    print('')
                except ZeroDivisionError:
                    pass

                # discrepancy rate / total number of coupled trials
                try:
                    divisor = coupled_count
                    rate_ab = disc_ab/divisor
                    rate_bc = disc_bc/divisor
                    rate_ab_bc = (disc_ab + disc_bc) / divisor
                    rate_ac = disc_ac/divisor
                    rate_ba = disc_ba/divisor
                    rate_cb = disc_cb/divisor
                    rate_ba_cb = (disc_ba+disc_cb) / divisor
                    rate_ca = disc_ca/divisor
                    m_type = 'coupled count'
                    hit = '*' if rate_ac > rate_ab_bc else ''
                    print(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
                    hit = '*' if rate_ca > rate_ba_cb else ''
                    print(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
                    print('')
                except ZeroDivisionError:
                    pass

            if args.epr_stats:
                print('\nEPR COUNTS:')
                epr_key_width = max_width(epr_histogram.keys())
                epr_count_width = max_width(epr_histogram.values())
                for k in epr_histogram.keys():
                    print(f'   {k:{epr_key_width+1}s}: {epr_histogram[k]:{epr_count_width + 1}d}')

    if 'no_diagram' not in args:
        if args.diagram_when in ('after', 'both'):
            after_path = dpath.with_stem(dpath.stem+'_after').with_suffix('.mmd')
            diagram(sim, after_path, has_run)
            if args.svg_diagram:
                svg_path = Path(after_path).with_suffix('.svg')
                subprocess.run(['mmdc', '-i', after_path, '-o', svg_path])

if __name__ == '__main__':
    main()