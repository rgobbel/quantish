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
from addict import Dict

from quantish.config_space import WIRES
from quantish.gate import FredkinGate, DelayGate
from quantish.particle import Particle
from quantish.qnumber import CalcMode, qify, probability
from quantish.simulation import Simulation
from quantish.util import QLogger, max_width, flat_list, SEP
from quantish.visualizations import diagram
# from quantish.dotdict import DotDict

log = logging.getLogger('quantish')

def set_config():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', required=True, help="REQUIRED Path to YAML configuration file")
    parser.add_argument('--configs-dir', default='models', help='Directory for model files')
    parser.add_argument('--use-defaults', action=BooleanOptionalAction, default=True, help='Load default values from defaults.yaml before individual model files')
    parser.add_argument('-s', '--simulate', action=BooleanOptionalAction, default=True, help='Run simulation')
    parser.add_argument('-l', '--log', default=None, type=str, help='Log file')
    parser.add_argument('--loglevel', choices=['debug', 'info', 'warning', 'error'], help='Default is info', default='info')
    parser.add_argument('--preserve-log', action='store_true', help='Preserve existing log file')
    parser.add_argument('--dup-log-to-console', action=BooleanOptionalAction,
                        default=True, help='Log to console as well as file')
    parser.add_argument('-d', '--diagram', type=str, help="Create a Mermaid diagram of the gate network on the named file with default extension '.mmd'")
    parser.add_argument('--no-diagram', action='store_true', default=SUPPRESS, help='Do not create a diagram')
    parser.add_argument('--diagram-dir', type=str, default='mermaid', help='Directory for Mermaid diagrams')
    parser.add_argument('--svg-diagram', action=BooleanOptionalAction, default=True, help='Create an SVG version of the diagram. Requires mmdc command-line Mermaid renderer')
    parser.add_argument('--pdf-diagram', action=BooleanOptionalAction, default=False, help='Create a PDF version of the diagram. Requires mmdc command-line Mermaid renderer')
    parser.add_argument('--diagram-when', choices=['before', 'after', 'both'], default='after', help='When to create a diagram, before or after simulation')
    parser.add_argument('--swap-threshold', type=float, default=SUPPRESS, help='Probability threshold for considering a control input "present"')
    parser.add_argument('--forward-threshold', type=float, default=SUPPRESS, help='Probability threshold for forwarding output')
    # parser.add_argument('--presence-threshold', type=float, default=SUPPRESS, help='Probability threshold for considering a particle "present"')
    parser.add_argument('--normalize-input', action='store_true', help='Normalize weights before measuring')
    parser.add_argument('--normalize-output', action='store_true', help='Normalize weights before forwarding')
    parser.add_argument('--symbolic', action='store_true', default=SUPPRESS, help='Force symbolic math')
    parser.add_argument('--numeric', action='store_true', default=SUPPRESS, help='Force numeric math')
    parser.add_argument('--merge-before-measure', action='store_true', help='Merge input particles before measuring')
    parser.add_argument('--merge-before-forward', action='store_true', help='Merge output particles before forwarding')
    parser.add_argument('--always-forward-switch-weights', action='store_true', help='Always forward switch weights regardless of output')
    parser.add_argument('--always-forward-control-weights', action='store_true', help='Always forward control weights regardless of output')
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
    # quantish.dotdict.DEBUG = True
    if args.use_defaults:
        with open(Path(config_dir, 'defaults.yaml'), 'r') as f:
            config_dict = yaml.safe_load(f)
    else:
        config_dict = {}
    with open(config_path, 'r') as f:
        user_config = yaml.safe_load(f)
    for k, v in user_config.items():
        if isinstance(v, dict):
            for vk, vv in v.items():
                if k not in config_dict.keys():
                    config_dict[k] = {}
                config_dict[k][vk] = vv
        else:
            config_dict[k] = v
    config = Dict(config_dict)
    config.config_path = args.config
    if args.loglevel is not None:
        loglevel = args.loglevel.upper()
    elif 'loglevel' in config:
        loglevel = config.loglevel.upper()
    else:
        loglevel = logging.INFO
    if args.log is not None:
        log_path = Path(args.log).with_suffix('.log')
        if not args.preserve_log:
            log_path.unlink(missing_ok=True)
        logging.basicConfig(filename=log_path, format='%(levelname)s:  %(message)s', level=loglevel)
        if args.dup_log_to_console:
            logging.getLogger('quantish').addHandler(QLogger())
    else:
        logging.basicConfig(format='%(message)s', level=loglevel, handlers=[QLogger()])
    log = logging.getLogger('quantish')
    if args.preserve_log: log.info('')
    if 'symbolic' in args:
        config.symbolic = args.symbolic
    if 'numeric' in args:
        config.symbolic = not args.numeric
    if args.sample:
        config.sample = True
        config.n_samples = args.n_samples
    symbolic = config.get('symbolic')
    CalcMode.mode = 'Symbolic' if symbolic else 'Float'
    log.info(f'QUANTISH PHYSICS SIMULATION STARTING: {config.title} at {time.asctime()}')
    if 'probability_threshold' not in config or config.probability_threshold is None:
        config.probability_threshold = Dict()
        # config.probability_threshold.forwarding = random.random
        # config.probability_threshold.swap = random.random
        # config.probability_threshold.selector = random.random
    if 'forward_threshold' in args: config.probability_threshold.fowarding = args.forward_threshold
    if 'swap_threshold' in args: config.probability_threshold.swap = args.swap_threshold
    # if 'presence_threshold' in args: config.probability_threshold.presence = args.presence_threshold
    if args.normalize_input: config.normalize_weights.input = True
    if args.normalize_output in args: config.normalize_weights.output = True
    if args.merge_before_measure: config.merge_option.before_measure = True
    if args.merge_before_forward: config.merge_option.before_forwarding = True
    if args.add_with_signs: config.merge_option.add_with_signs = True
    if args.measure_discrepancy: config.measure_discrepancy = True
    elif 'measure_discrepancy' not in config.keys(): config.measure_discrepancy  = False
    if args.always_forward_switch_weights: config.always_forward.switch_weights = True
    if args.always_forward_control_weights: config.always_forward.control_weights = True
    log.info(f"{'SYMBOLIC' if symbolic else 'FLOATING POINT'} MODE")
    return args, config

def run_simulation(args, config):
    epr_stats = args.epr_stats or config.get('epr_stats')
    sim = Simulation(config)
    q1 = None
    q2 = None
    dpath = None
    has_run = False
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

    if not sim.sample:
        experiment_results = sim.run()
        has_run = True
    else:
        ## Initial setup
        fig411 = sim.title == 'Figure 4.11'
        log.info(f'Running {sim.n_samples} trials')
        log.info('')
        log.info('PARTICLES:')
        for particle in sim.particles.values():
            log.info(f'   {particle}')
        log.info('GATES:')
        for gate in sim.gates.values():
            if callable(gate.swap_threshold):
                swapstr = f'(call){gate.swap_threshold():.2f}'
            else:
                swapstr = f'{gate.swap_threshold:.2f}'
            if callable(gate.forwarding_threshold):
                fwdstr = f'(call){gate.forwarding_threshold():.2f}'
            else:
                fwdstr = f'{gate.forwarding_threshold:.2f}'
            log.info(f'   {gate} (threshold: swap={swapstr}, fwd={fwdstr})')
        histogram = defaultdict(int)
        stats = defaultdict(float)
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
        if epr_stats:
            epr_histogram = defaultdict(int)
            epr_histogram['coupled-equal'] = 0
            epr_histogram['coupled-unequal'] = 0
            epr_histogram['uncoupled-equal'] = 0
            epr_histogram['uncoupled-unequal'] = 0

            epr_histogram['coupled-both-upper'] = 0
            epr_histogram['coupled-both-lower'] = 0
            epr_histogram['coupled-upper-lower'] = 0
            epr_histogram['coupled-lower-upper'] = 0
            epr_histogram['uncoupled-both-upper'] = 0
            epr_histogram['uncoupled-both-lower'] = 0
            epr_histogram['uncoupled-upper-lower'] = 0
            epr_histogram['uncoupled-lower-upper'] = 0
        if config.config_path == 'fig416plus':
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

        save_level = log.level
        log.setLevel(logging.WARNING)

        # if config.measure_discrepancy:
        #     angle_choices = ['qa', 'qb', 'qc']
        #     # angle_choices = ['qa', 'qc']
        #     for gate in sim.gates:
        #         for wire in WIRES:
        #             histogram[f'{gate}.{wire}'] = 0
        #     for angle in angle_choices:
        #         for wire in WIRES:
        #             histogram[f'{angle}.{wire}'] = 0

        ## Now run all trials
        with tqdm(range(sim.n_samples)) as tq:
            for i in tq:
                experiment_results = {} # new result each time
                if config.measure_discrepancy or epr_stats:
                    angle_choices = ['qa', 'qb', 'qc']
                    # angle_choices = ['qa', 'qc']
                    random.shuffle(angle_choices) # this should produce an even distribution for all combinations
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
                    config.gates.g5.angle = config.variables[q1]
                    config.gates.g6.angle = config.variables[q2]
                    del sim
                    sim = Simulation(config)
                    assert sim.gates.g5.theta == qify(config.variables[q1])
                    assert sim.gates.g6.theta == qify(config.variables[q2])
                else:
                    del sim
                    sim = Simulation(config)
                experiment_results = sim.run()
                # for stage in sim.run_stages.values():
                #     stage.run()
                g1 = sim.gates.get('g1')
                g2 = sim.gates.get('g2')
                g3 = sim.gates.get('g3')
                g4 = sim.gates.get('g4')
                g5 = sim.gates.get('g5')
                g6 = sim.gates.get('g6')
                if not config.measure_discrepancy and (g4 and g5 and g6):
                    if g4.output_wire == 'upper':
                        histogram['coupled_count'] += 1
                        if len(stats) < 2:
                            stats['g1_sin_sq'] = g1.theta.sin**2
                            stats['g1_cos_sq'] = g1.theta.cos**2
                            stats['g2_sin_sq'] = g2.theta.sin**2
                            stats['g2_cos_sq'] = g2.theta.cos**2
                            stats['g5_sin_sq'] = g5.theta.sin**2
                            stats['g5_cos_sq'] = g5.theta.cos**2
                            stats['g6_sin_sq'] = g6.theta.sin**2
                            stats['g6_cos_sq'] = g6.theta.cos**2
                            stats['g1_g5_sin_sq'] = (g5.theta - g1.theta).sin ** 2
                            stats['g2_g6_sin_sq'] = (g6.theta - g2.theta).sin ** 2
                            stats['g1_g5_cos_sq'] = (g5.theta - g1.theta).cos ** 2
                            stats['g2_g6_cos_sq'] = (g6.theta - g2.theta).cos ** 2
                            stats['g5_g6_sin_sq'] = (g5.theta - g6.theta).sin ** 2
                            stats['g5_g6_cos_sq'] = (g5.theta - g6.theta).cos ** 2
                            stats['g1_g5_cos_sq_prod'] = ((g1.theta - g5.theta).cos * (g2.theta - g6.theta).cos) ** 2
                            stats['g1g5_g2g6_sin_sum'] = 1 - ((g1.theta - g5.theta).cos ** 2 - (g2.theta - g6.theta).cos ** 2)
                            stats['g1g5_g2g6_diff_cos_sq'] = (abs(g5.theta - g1.theta) - abs(g6.theta - g2.theta)).cos ** 2
                            stats['g2g1_g6g5_cos_sq'] = (abs(g2.theta - g1.theta) - abs(g6.theta - g5.theta)).cos ** 2
                        if g5.output_wire != g6.output_wire:
                            histogram['discrepancy_count'] += 1
                        stats['discrepancy_rate'] = histogram['discrepancy_count'] / histogram['coupled_count']
                        tq.set_postfix(discrepancy_rate=stats['discrepancy_rate'])
                if config.measure_discrepancy:
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
                if config.config_path == 'fig49':
                    if experiment_results.get('g2.upper') and experiment_results.get('g3.upper'):
                        histogram['both_upper'] += 1
                    if experiment_results.get('g2.lower') and experiment_results.get('g3.lower'):
                        histogram['both_lower'] += 1
                    if not (experiment_results.get('g2.upper') or experiment_results.get('g3.upper')):
                        histogram['neither_upper'] += 1
                    if not (experiment_results.get('g2.lower') or experiment_results.get('g3.lower')):
                        histogram['neither_lower'] += 1
                    if not(experiment_results.get('g2.upper') or experiment_results.get('g3.upper')):
                        histogram['neither_upper'] += 1
                    if experiment_results.get('g2.upper') and not experiment_results.get('g3.upper'):
                        histogram['g2_upper_not_g3_upper'] += 1
                    if experiment_results.get('g3.upper') and not not experiment_results.get('g2.upper'):
                        histogram['g3_upper_not_g2_upper'] += 1
                    if experiment_results.get('g2.lower') and not experiment_results.get('g3.lower'):
                        histogram['g2_lower_not_g3_lower'] += 1
                    if experiment_results.get('g3.lower') and not experiment_results.get('g2.lower'):
                        histogram['g3_lower_not_g2_lower'] += 1
                # if config.config_path == 'fig416plus' and experiment_results.get('g4.upper'):
                #     log.info('coupled')
                if config.config_path == 'fig416plus' and i == 0:
                    g1uw = Particle.merge(flat_list(sim.gates.g1.port_weights('upper')))
                    g1lw = Particle.merge(flat_list(sim.gates.g1.port_weights('lower')))
                    g2uw = Particle.merge(flat_list(sim.gates.g2.port_weights('upper')))
                    g2lw = Particle.merge(flat_list(sim.gates.g2.port_weights('lower')))
                    g1up_phase = (g1uw and g1uw.weight.phase) or qify('0+0j')
                    g2up_phase = (g2uw and g2uw.weight.phase) or qify('0+0j')
                    log.info(f'upper combined phase: {(g1up_phase + g2up_phase).degrees:.2f}, probabilities: {g1uw.probability:.2f}, {g2uw.probability:.2f}')
                    g1lo_phase = g1lw and g1lw.weight.phase
                    g2lo_phase = g2lw and g2lw.weight.phase
                    if g1lo_phase and g2lo_phase:
                        log.info(f'lower combined phase: {(g1lo_phase + g2lo_phase).degrees:.2f}, probabilities: {g1lw.probability:.2f}, {g2lw.probability:.2f}')
                    else:
                        log.info(f'{g1lw=}, {g2lw=}')
                    fig417a['p1'] = sim.gates.g1.measure(sim.particles.p1)
                for k, v in experiment_results.items():
                    if v:
                        global_result[k] = v
                        histogram[k] += 1
                if config.measure_discrepancy or epr_stats:
                    ag1 = {'control': g1.results['control'], 'swapping': g1.swapping, 'upper': g1.results['upper'], 'lower': g1.results['lower']}
                    ag2 = {'control': g2.results['control'], 'swapping': g2.swapping, 'upper': g2.results['upper'], 'lower': g2.results['lower']}
                    ag3 = {'control': g3.results['control'], 'swapping': g3.swapping, 'upper': g3.results['upper'], 'lower': g3.results['lower']}
                    ag4 = {'control': g4.results['control'], 'swapping': g4.swapping, 'upper': g4.results['upper'], 'lower': g4.results['lower']}
                    ag5 = {'control': g5.results['control'], 'swapping': g5.swapping, 'upper': g5.results['upper'], 'lower': g5.results['lower']}
                    ag6 = {'control': g6.results['control'], 'swapping': g6.swapping, 'upper': g6.results['upper'], 'lower': g6.results['lower']}
                    coupled = g4.output_wire == 'upper' # and (g4.results['upper'] is not None)

                    # Discrepancy occurs when particles end up on different wires (one upper, one lower)
                    if coupled:
                        coupled_count += 1
                        if not w1aw3:
                            g5up = sim.gates.g5.outputs['upper'] or []
                            g6up = sim.gates.g6.inputs['upper'] or []
                            w1aw3 = (g5up + g6up) or []
                            w1aw3m = Particle.merge(w1aw3)
                        if not w2aw3:
                            g5lo = sim.gates.g5.outputs['lower'] or []
                            g6up = sim.gates.g6.inputs['upper'] or []
                            w2aw3 = (g5lo + g6up) or []
                            w2aw3m = Particle.merge(w2aw3)
                        if not w1aw4:
                            g5up = sim.gates.g5.outputs['upper'] or []
                            g6lo = sim.gates.g6.inputs['upper'] or []
                            w1aw4 = (g5up + g6lo) or []
                            w1aw4m = Particle.merge(w1aw4)
                        if not w2aw3:
                            g5lo = sim.gates.g5.outputs['lower'] or []
                            g6lo = sim.gates.g6.inputs['upper'] or []
                            w2aw3 = (g5lo + g6lo) or []
                            w2aw3m = Particle.merge(w2aw3)

                        if not w1aw3a:
                            g5up = sim.gates.g5.outputs['upper'] or []
                            g6up = sim.gates.g6.outputs['upper'] or []
                            w1aw3a = (g5up + g6up) or []
                            w1aw3am = Particle.merge(w1aw3a)
                        if not w2aw3a:
                            g5lo = sim.gates.g5.outputs['lower'] or []
                            g6up = sim.gates.g6.outputs['upper'] or []
                            w2aw3a = (g5lo + g6up) or []
                            w2aw3am = Particle.merge(w2aw3a)
                        if not w1aw4a:
                            g5up = sim.gates.g5.outputs['upper'] or []
                            g6lo = sim.gates.g6.outputs['lower'] or []
                            w1aw4a = (g5up + g6lo) or []
                            w1aw4am = Particle.merge(w1aw4a)
                        if not w2aw4a:
                            g5lo = sim.gates.g5.outputs['lower'] or []
                            g6lo = sim.gates.g6.outputs['lower'] or []
                            w2aw4a = (g5lo + g6lo) or []
                            w2aw4am = Particle.merge(w2aw4a)

                        if (not w1w3) and g5.output_wire == 'upper' and g6.output_wire == 'upper':
                            g5up = sim.gates.g1.weights['upper'] or []
                            g6up = sim.gates.g2.weights['upper'] or []
                            w1w3 = g5up + g6up
                            w1w3m = Particle.merge(w1w3)
                        if (not w2w4) and g5.output_wire == 'lower' and g6.output_wire == 'lower':
                            g5lo = sim.gates.g1.weights['lower'] or []
                            g6lo = sim.gates.g2.weights['lower'] or []
                            w2w4 = g5lo + g6lo
                            w2w4m = Particle.merge(w2w4)
                        if (not w1w4) and g5.output_wire == 'upper' and g6.output_wire == 'lower':
                            g5up = sim.gates.g1.weights['upper'] or []
                            g6lo = sim.gates.g2.weights['lower'] or []
                            w1w4 = g5up + g6lo
                            w1w4m = Particle.merge(w1w4)
                        if (not w2w3) and g5.output_wire == 'lower' and g6.output_wire == 'upper':
                            g5lo = sim.gates.g1.weights['lower'] or []
                            g6up = sim.gates.g2.weights['upper'] or []
                            w1w4 = g5lo + g6up
                            w1w4m = Particle.merge(w1w4)

                        for gate, var in zip([sim.gates.g5, sim.gates.g6], [q1, q2]):
                            for angle in ['qa', 'qb', 'qc']:
                                if var == angle:
                                    if gate.output_wire == 'upper':
                                        histogram[f'{angle}.upper_coupled'] += 1
                                    else:
                                        histogram[f'{angle}.lower_coupled'] += 1
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
                    else:
                        for gate, var in zip([sim.gates.g5, sim.gates.g6], [q1, q2]):
                            for angle in ['qa', 'qb', 'qc']:
                                if var == angle:
                                    if gate.output_wire == 'upper':
                                        histogram[f'{angle}.upper_uncoupled'] += 1
                                    else:
                                        histogram[f'{angle}.lower_uncoupled'] += 1
                if epr_stats:
                    if coupled:
                        # if g4_up and g4_up[0].probability > 0:
                        if g5.output_wire == 'upper' and g6.output_wire == 'upper':
                            epr_histogram['coupled-both-upper'] += 1
                        elif g5.output_wire == 'lower' and g6.output_wire == 'lower':
                            epr_histogram['coupled-both-lower'] += 1
                        elif g5.output_wire == 'upper' and g6.output_wire == 'lower':
                            epr_histogram['coupled-upper-lower'] += 1
                        elif g5.output_wire == 'lower' and g6.output_wire == 'upper':
                            epr_histogram['coupled-lower-upper'] += 1
                    #     if experiment_results.get('g5.upper') and experiment_results.get('g6.upper'):
                    #         if np.isclose(float(experiment_results['g5.upper'][0].probability),
                    #                       float(experiment_results['g6.upper'][0].probability)):
                    #             epr_histogram['coupled-equal'] += 1
                    #         else:
                    #             epr_histogram['coupled-unequal'] += 1
                    #     elif experiment_results.get('g5.lower') and experiment_results.get('g6.lower'):
                    #         epr_histogram['coupled-both-lower'] += 1
                    #         if np.isclose(float(experiment_results['g5.lower'][0].probability),
                    #                       float(experiment_results['g6.lower'][0].probability)):
                    #             epr_histogram['coupled-equal'] += 1
                    #         else:
                    #             epr_histogram['coupled-unequal'] += 1
                    #     else:
                    #         epr_histogram['coupled-unequal'] += 1
                    else:
                        if g5.output_wire == 'upper' and g6.output_wire == 'upper':
                            epr_histogram['uncoupled-both-upper'] += 1
                        elif g5.output_wire == 'lower' and g6.output_wire == 'lower':
                            epr_histogram['uncoupled-both-lower'] += 1
                        elif g5.output_wire == 'upper' and g6.output_wire == 'lower':
                            epr_histogram['uncoupled-upper-lower'] += 1
                        elif g5.output_wire == 'lower' and g6.output_wire == 'upper':
                            epr_histogram['uncoupled-lower-upper'] += 1
                        # if experiment_results.get('g5.upper') and experiment_results.get('g6.upper'):
                        #     epr_histogram['uncoupled-both-upper'] += 1
                            # if np.isclose(float(experiment_results['g5.upper'][0].probability),
                            #               float(experiment_results['g6.upper'][0].probability)):
                            #     epr_histogram['uncoupled-equal'] += 1
                            # else:
                            #     epr_histogram['uncoupled-unequal'] += 1
                        # elif experiment_results.get('g5.lower') and experiment_results.get('g6.lower'):
                        #     epr_histogram['uncoupled-both-lower'] += 1
                            # if np.isclose(float(experiment_results['g5.lower'][0].probability),
                            #               float(experiment_results['g6.lower'][0].probability)):
                            #     epr_histogram['uncoupled-equal'] += 1
                            # else:
                            #     epr_histogram['uncoupled-unequal'] += 1
                        # else:
                        #     epr_histogram['uncoupled-unequal'] += 1
                if fig411:
                    if g1.output_wire == 'upper':
                        if g2.output_wire == 'upper':
                            histogram['411-test-g2.upper'] += 1
                        else:
                            histogram['411-test-g2.lower'] += 1
                        if histogram["g1.upper"] != 0:
                            stats['prediction_match'] = 1 - float(abs((histogram["411-test-g2.upper"]/histogram["g1.upper"]) - ((g2.theta - g1.theta).cos ** 2)))
                            tq.set_postfix(prediction_match=f'{stats['prediction_match']:.3%}')

### Now report stats
        log.setLevel(save_level)
        switch_vals = {'control': 0, 'upper': 1, 'lower': 2,
                       'upper_coupled': 3, 'lower_coupled': 4,
                       'upper_uncoupled': 5, 'lower_uncoupled': 6}
        def switch_order(s):
            if '.' not in s: return s
            gate, switch = s.split('.')
            return gate + str(switch_vals[switch])
        hist_keys = sorted(histogram.keys(), key=lambda x: switch_order(x))
        hist_key_width = max_width(hist_keys)
        count_width = max_width(histogram.values())
        log.info('FINAL OUTPUTS:')
        log.info('   FREDKIN GATES:')
        result_keys = sorted(experiment_results.keys(), key=lambda x: switch_order(x))
        result_key_width = max_width(result_keys)
        for k in result_keys:
            if not experiment_results[k]:
                v = 'None'
            else:
                v = Particle.merge(experiment_results[k])
            log.info(f'      {k:{result_key_width+1}s}: {v}')
        log.info('')
        # log.info('DELAY GATES:')
        # for k, v in sim.gates.items():
        #     if type(v) is DelayGate:
        #         if v.state is None:
        #             vstr = 'None'
        #         else:
        #             vstr = f'{Particle.merge(v.state)}'
        #         log.info(f'    {k}: {vstr} {v}')
        log.info('GATE RATIOS (UPPER / LOWER)')
        log.info('   WEIGHTS:')
        for gname, gate in sim.gates.items():
            p_upper = Particle.merge(gate.weights['upper']).probability
            p_lower = Particle.merge(gate.weights['lower']).probability
            p_total = p_upper + p_lower
            if p_total != 0:
                log.info(f'      {gate}: {p_upper/p_total:.2%} / {p_lower/p_total:.2%} (total = {p_total:.3f})')
            else:
                log.info(f'      {gate}: NO WEIGHTS!')
        log.info('')
        log.info('   OUTPUTS')
        for gname, gate in sim.gates.items():
            p_upper = Particle.merge(gate.outputs['upper']).probability
            p_lower = Particle.merge(gate.outputs['lower']).probability
            p_total = p_upper + p_lower
            if p_total != 0:
                log.info(f'      {gate}: {p_upper/p_total:.2%} / {p_lower/p_total:.2%} (total = {p_total:.3f})')
            else:
                log.info(f'      {gate}: NO OUTPUTS!')
        log.info('')
        log.info('   RESULTS')
        for gname, gate in sim.gates.items():
            p_upper = Particle.merge(gate.results['upper']).probability
            p_lower = Particle.merge(gate.results['lower']).probability
            p_total = p_upper + p_lower
            if p_total != 0:
                log.info(f'      {gate}: {p_upper/p_total:.2%} / {p_lower/p_total:.2%} (total = {p_total:.3f})')
            else:
                log.info(f'      {gate}: NO RESULTS!')
        log.info('')
        log.info('RESULT COUNTS:')
        for k in hist_keys:
            count = histogram[k]
            if k in global_result.keys() and global_result[k]:
                log.info(f'   {k:{hist_key_width}s}: {count:{count_width}d} ({(count/sim.n_samples):>6.1%}) {Particle.merge(global_result[k])}')
        log.info('')
        log.info('GATE WEIGHT SQUARED MAGNITUDE RATIOS:')
        for gname in sim.gates.keys():
            upper_pos = f'{gname}{SEP}upper'
            lower_pos = f'{gname}{SEP}lower'
            if upper_pos not in global_result.keys():
                upper = 0
            else:
                upper = Particle.merge(global_result[f'{gname}.upper']).probability
            if lower_pos not in global_result.keys():
                lower = 0
            else:
                lower = Particle.merge(global_result[f'{gname}.lower']).probability
            total = upper + lower
            if total == 0:
                log.info(f'   {gname}: NO RESULTS')
            else:
                log.info(f'   {gname}.upper: {upper / total:.2f}')
                log.info(f'   {gname}.lower: {lower / total:.2f}')
        if config.measure_discrepancy:
            if coupled_count == 0:
                log.info('COUPLED COUNT 0!')
                coupled_count = 1
            if discrepancy_count == 0:
                log.info('DISCREPANCY COUNT 0!')
                discrepancy_count = 1
            acounts = defaultdict(int)
            log.info('')

            log.info('Figure 4.17:')
            log.info('   a:')
            log.info(f'      w1,w3 = {w1w3m} {w1w3}')
            log.info(f'      w1,w4 = {w1w4m} {w1w4}')
            log.info(f'      w2,w3 = {w2w3m} {w2w3}')
            log.info(f'      w2,w4 = {w2w4m} {w2w4}')
            log.info('')

            log.info('   b:')
            log.info(f'      w1a,w3 = {w1aw3m} {w1aw3}')
            log.info(f'      w1a,w4 = {w1aw4m} {w1aw4}')
            log.info(f'      w2a,w3 = {w2aw3m} {w2aw3}')
            log.info(f'      w2a,w4 = {w2aw4m} {w2aw4}')
            log.info('')

            log.info('   c:')
            log.info(f'      w1a,w3a = {w1aw3am} {w1aw3a}')
            log.info(f'      w1a,w4a = {w1aw4am} {w1aw4a}')
            log.info(f'      w2a,w3a = {w2aw3am} {w2aw3a}')
            log.info(f'      w2a,w4a = {w2aw4am} {w2aw4a}')
            log.info('')

            g1a = sim.gates.g1.theta
            g2a = sim.gates.g2.theta

            log.info(f'angle delta g1({g1a.degrees:.1f}º) & g2({g2a.degrees:.1f}º) / unfiltered lower/total ratio:')
            for angle in ['qa', 'qb', 'qc']:
                upstr = f'{angle}.upper'
                lostr = f'{angle}.lower'
                upcount = histogram[upstr]
                locount = histogram[lostr]
                atotal = upcount + locount
                try:
                    acounts[angle] = locount/atotal
                except ZeroDivisionError:
                    acounts[angle] = m.inf
                aval = qify(config.variables[angle])
                g1_angle_diff = g1a - aval
                g2_angle_diff = g2a - aval
                log.info(f'{angle}({aval.degrees:.1f}º)({g1_angle_diff.degrees:.1f}º,{g2_angle_diff.degrees:.1f}º): {locount}/{atotal}={acounts[angle]:.3f} ({g1_angle_diff.sin**2:.3f}, {g2_angle_diff.sin**2:.3f})')
            log.info('')

            log.info(f'angle delta g1({g1a.degrees:.1f}º) & g2({g2a.degrees:.1f}º) / coupled/uncoupled lower/total ratio:')
            c_acounts = defaultdict(int)
            unc_acounts = defaultdict(int)
            for angle in ['qa', 'qb', 'qc']:
                upstr = f'{angle}.upper_coupled'
                lostr = f'{angle}.lower_coupled'
                upcount = histogram[upstr]
                locount = histogram[lostr]
                atotal = upcount + locount
                if atotal > 0:
                    c_acounts[angle] = locount / atotal
                un_upstr = f'{angle}.upper_uncoupled'
                un_lostr = f'{angle}.lower_uncoupled'
                un_upcount = histogram[un_upstr]
                un_locount = histogram[un_lostr]
                un_atotal = un_upcount + un_locount
                if un_atotal > 0:
                    unc_acounts[angle] = un_locount / un_atotal
                aval = qify(config.variables[angle])
                g1_angle_diff = g1a - aval
                g2_angle_diff = g2a - aval
                if atotal > 0:
                    log.info(f'coupled   {angle}({aval.degrees:.1f}º)({g1_angle_diff.degrees:.1f}º,{g2_angle_diff.degrees:.1f}º): {locount}/{atotal}={(locount/atotal):.3f} ({g1_angle_diff.sin**2:.3f}, {g2_angle_diff.sin**2:.3f})')
                else:
                    log.info('coupled count == 0')
                if un_atotal > 0:
                    log.info(
                        f'uncoupled {angle}({aval.degrees:.1f}º)({g1_angle_diff.degrees:.1f}º,{g2_angle_diff.degrees:.1f}º): {un_locount}/{un_atotal}={(un_locount / un_atotal):.3f} ({g1_angle_diff.sin ** 2:.3f}, {g2_angle_diff.sin ** 2:.3f})')
                else:
                    log.info('uncoupled count == 0')
            log.info('')

            log.info(f'uncoupled qb-qa={acounts["qb"]-acounts["qa"]:.3f}, qc-qb={acounts["qc"]-acounts["qb"]:.3f}, qc-qa={acounts["qc"]-acounts["qa"]:.3f}')
            log.info(f'coupled qb-qa={c_acounts["qb"]-c_acounts["qa"]:.3f}, qc-qb={c_acounts["qc"]-c_acounts["qb"]:.3f}, qc-qa={c_acounts["qc"]-c_acounts["qa"]:.3f}')
            log.info(f'coupled count = {coupled_count} ({coupled_count/sim.n_samples:.2%}), discrepancy_count = {discrepancy_count} ({discrepancy_count/coupled_count:.2%}), {disc_ab=}, {disc_bc=}, {disc_ac=}, {disc_ba=}, {disc_cb=}, {disc_ca=}')
            log.info(f'disc/coupled={discrepancy_count/coupled_count:.2f}, disc/samples={discrepancy_count/sim.n_samples:.2f}')
            log.info(f'coupled_pair_counts: ab={coupled_pair_counts["ab"]}, bc={coupled_pair_counts["bc"]}, ac={coupled_pair_counts["ac"]}, ba={coupled_pair_counts["ba"]}, cb={coupled_pair_counts["cb"]}, ca={coupled_pair_counts["ca"]}')
            deg_qa, deg_qb, deg_qc = [qify(config.variables[x]).degrees for x in ['qa', 'qb', 'qc']]
            rad_qa, rad_qb, rad_qc = [qify(config.variables[x]) for x in ['qa', 'qb', 'qc']]

            deg_ab = abs(deg_qa - deg_qb)
            deg_bc = abs(deg_qb - deg_qc)
            deg_ac = abs(deg_qa - deg_qc)

            log.info(f'{deg_qa=:.3f}, {deg_qb=:.3f}, {deg_qc=:.3f}')

            pred_ab = (rad_qa - rad_qb).sin**2
            pred_ac = (rad_qa - rad_qc).sin**2
            pred_bc = (rad_qb - rad_qc).sin**2
            pred_ab_bc = pred_ab + pred_bc

            p_g1_upper = g1.theta.cos**2
            p_g1_lower = g1.theta.sin**2
            p_g2_upper = g2.theta.cos**2
            p_g2_lower = g2.theta.sin**2
            p_g5_upper = g5.theta.cos**2 * p_g1_upper
            p_g5_lower = g5.theta.sin**2
            p_g6_upper = g6.theta.cos**2 * p_g2_upper
            p_g6_lower = g6.theta.sin**2
            p_g5_g6_upper = p_g5_upper * p_g6_upper
            p_g5_g6_lower = p_g5_lower * p_g6_lower
            p_g5_g6_same = p_g5_g6_upper + p_g5_g6_lower
            p_g5_g6_diff = 1 - p_g5_g6_same

            p_qa_upper = rad_qa.cos**2
            p_qa_lower = 1 - p_qa_upper
            p_qb_upper = rad_qb.cos**2
            p_qb_lower = 1 - p_qb_upper
            p_qc_upper = rad_qc.cos**2
            p_qc_lower = 1 - p_qc_upper

            avg_qa_upper = p_qa_upper * ((p_g1_upper + p_g2_upper) / 2)
            avg_qb_upper = p_qb_upper * ((p_g1_upper + p_g2_upper) / 2)
            avg_qc_upper = p_qc_upper * ((p_g1_upper + p_g2_upper) / 2)

            joint_ab = 1 - ((p_qa_upper * p_qb_upper) + (p_qa_lower * p_qb_lower))
            joint_bc = 1 - ((p_qb_upper * p_qc_upper) + (p_qb_lower * p_qc_lower))
            joint_ac = 1 - ((p_qa_upper * p_qc_upper) + (p_qa_lower * p_qc_lower))
            joint_ab_bc = joint_ab + joint_bc

            # joint_ab = abs(p_qa - p_qb)
            # joint_bc = abs(p_qb - p_qc)
            # joint_ac = abs(p_qa - p_qc)
            # joint_ab_bc = joint_ab + joint_bc

            log.info(f'qa = {deg_qa:.1f}º, qb = {deg_qb:.1f}º, qc = {deg_qc:.1f}º')
            log.info(f'angles: qa:{angle_counts["qa"]}, qb:{angle_counts["qb"]}, qc:{angle_counts["qc"]}')
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
            pss = ', '.join([f'{pk}: {pair_counts[pk]}' for pk in ['ab', 'bc', 'ac', 'ba', 'cb', 'ca']]) #pair_counts.keys()])
            log.info(f'pairs: {pss}')
            log.info('')

            # log.info(f'pairs: ab:{pair_counts["ab"]}, bc:{pair_counts["bc"]}, ac:{pair_counts["ac"]}, ba:{pair_counts["ba"]}, bc:{pair_counts["cb"]}, ac:{pair_counts["ca"]}')

            measures = ['coupled pair counts', 'n_samples', 'pair counts', 'discrepancy count', 'coupled count']
            pad_len = max([len(s) for s in measures])

            discs = [disc_ab, disc_bc, disc_ac, disc_ab+disc_bc, disc_ba, disc_cb, disc_ba+disc_cb]

            rate_calc = lambda term, divisor: term/divisor

            # log.info(f'ab={abs(v_qa - v_qb):.1f}º ({m.sin(m.radians(v_qa) - m.radians(v_qb))**2:.3f})')
            # log.info(f'bc={abs(v_qb - v_qc):.1f}º ({m.sin(m.radians(v_qb) - m.radians(v_qc))**2:.3f})')
            # log.info(f'ac={abs(v_qa - v_qc):.1f}º ({m.sin(m.radians(v_qa) - m.radians(v_qc))**2:.3f})')

            spc = ''
            log.info(f'{spc:>{pad_len}}{" "*2}{deg_ab:.1f}º{" "*14}{deg_bc:.1f}º{" "*14}{deg_ac:.1f}º{" "*14}{deg_ab+deg_bc:.1f}º')
            try:
                m_type = 'predicted, angles'
                hit = '*' if pred_ac > pred_ab+pred_bc else ''
                log.info(f'{m_type: >{pad_len}}: ab={pred_ab:.3f},          bc={pred_bc:.3f},          ac={pred_ac:.3f},          ab+bc={pred_ab_bc:.3f}{hit}')
            except ZeroDivisionError:
                pass

            try:
                m_type = '           joint'
                hit = '*' if joint_ac > joint_ab_bc else ''
                log.info(f'{m_type: >{pad_len}}: ab={joint_ab:.3f},          bc={joint_bc:.3f},          ac={joint_ac:.3f},          ab+bc={joint_ab_bc:.3f}{hit}')
                log.info('')
            except ZeroDivisionError:
                pass

            # discrepancy rates / coupled pair counts
            try:
                rate_ab = disc_ab/cpcab
                rate_bc = disc_bc/cpcbc
                rate_ab_bc = rate_ab + rate_bc
                rate_ac = disc_ac/cpcac
                rate_ba = disc_ba/cpcba
                rate_cb = disc_cb/cpccb
                rate_ba_cb = rate_ba + rate_cb
                rate_ca = disc_ca/cpcca
                avg_ab = (disc_ab + disc_ba) / (cpcab + cpcba)
                avg_bc = (disc_bc + disc_cb) / (cpcbc + cpccb)
                avg_ac = (disc_ac + disc_ca) / (cpcac + cpcca)
                avg_ab_bc = (rate_ab_bc + rate_ba_cb) / 2
                m_type = 'coupled pair counts'
                hit = '*' if rate_ac > rate_ab_bc else ''
                log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
                hit = '*' if rate_ca > rate_ba_cb else ''
                log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
                log.info(f'{"avg":>{pad_len}}: ab={avg_ab:.3f} ({pred_ab-avg_ab:> 6.3f}), bc={avg_bc:.3f} ({pred_bc-avg_bc:> 6.3f}), ac={avg_ac:.3f} ({pred_ac-avg_ac:> 6.3f}), ab+bc={avg_ab_bc:.3f} ({pred_ab_bc-avg_ab_bc:> 6.3f}){hit}')
                log.info('')
            except ZeroDivisionError:
                pass

            # discrepancy rates / total number of trials, both coupled and uncoupled
            try:
                divisor = sim.n_samples
                rate_ab = disc_ab/divisor
                rate_bc = disc_bc/divisor
                rate_ab_bc = rate_ab + rate_bc
                rate_ac = disc_ac/divisor
                rate_ba = disc_ba/divisor
                rate_cb = disc_cb/divisor
                rate_ba_cb = (disc_ba+disc_cb) / divisor
                rate_ca = disc_ca/divisor
                m_type = 'n_samples'
                hit = '*' if rate_ac > rate_ab_bc else ''
                log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
                hit = '*' if rate_ca > rate_ba_cb else ''
                log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
                log.info('')
            except ZeroDivisionError:
                pass

            # discrepancy rates / pair counts, both coupled and uncoupled
            try:
                rate_ab = disc_ab/pcab
                rate_bc = disc_bc/pcbc
                rate_ab_bc = rate_ab + rate_bc
                rate_ac = disc_ac/pcac
                rate_ba = disc_ba/pcba
                rate_cb = disc_cb/pccb
                rate_ba_cb = rate_ba + rate_cb
                rate_ca = disc_ca/pcca
                m_type = 'pair counts'
                log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}')
                log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}')
                log.info('')
            except ZeroDivisionError:
                pass

            # individual discrepancy rates / total number of discrepancies
            try:
                divisor = discrepancy_count
                rate_ab = disc_ab/divisor
                rate_bc = disc_bc/divisor
                rate_ab_bc = rate_ab + rate_bc
                rate_ac = disc_ac/divisor
                rate_ba = disc_ba/divisor
                rate_cb = disc_cb/divisor
                rate_ba_cb = rate_ba + rate_cb
                rate_ca = disc_ca/divisor
                m_type = 'discrepancy count'
                hit = '*' if rate_ac > rate_ab_bc else ''
                log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
                hit = '*' if rate_ca > rate_ba_cb else ''
                log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
                log.info('')
            except ZeroDivisionError:
                pass

            # discrepancy rate / total number of coupled trials
            try:
                divisor = coupled_count
                rate_ab = disc_ab/divisor
                rate_bc = disc_bc/divisor
                rate_ab_bc = rate_ab + rate_bc
                rate_ac = disc_ac/divisor
                rate_ba = disc_ba/divisor
                rate_cb = disc_cb/divisor
                rate_ba_cb = rate_ba + rate_cb
                rate_ca = disc_ca/divisor
                m_type = 'coupled count'
                hit = '*' if rate_ac > rate_ab_bc else ''
                log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
                hit = '*' if rate_ca > rate_ba_cb else ''
                log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
                log.info('')
            except ZeroDivisionError:
                pass

        if epr_stats:
            log.info('\nEPR COUNTS:')
            epr_key_width = max_width(epr_histogram.keys())
            epr_count_width = max_width(epr_histogram.values())
            for k in epr_histogram.keys():
                log.info(f'   {k:{epr_key_width+1}s}: {epr_histogram[k]:{epr_count_width + 1}d}')
            log.info('')

        log.info('')
        log.info('FULL HISTOGRAM VALUES:')
        for k in hist_keys:
            log.info(f'   {k}: {histogram[k]}')

        if len(stats) > 0:
            stats_key_width = max_width(stats.keys())
            log.info('')
            log.info('STATISTICS:')
            for k in stats.keys():
                log.info(f'   {k:{stats_key_width+1}s}: {stats[k]:.3f}')
            log.info('')

        if fig411:
            log.info('')
            log.info('FOR FIGURE 4.11:')
            log.info(f'   {abs(g1.theta.degrees - g2.theta.degrees)=}')
            log.info(f'   {histogram["411-test-g2.upper"]/histogram["g1.upper"]=}')
            log.info(f'   {((g2.theta - g1.theta).cos ** 2)=}')
            log.info(f'   prediction_match={1 - abs(((g2.theta - g1.theta).cos ** 2) - histogram["411-test-g2.upper"]/histogram["g1.upper"]):.3%}')
            log.info('')
    if 'no_diagram' not in args:
        if args.diagram_when in ('after', 'both'):
            after_path = dpath.with_stem(dpath.stem+'_after').with_suffix('.mmd')
            log.info(f'Generating Mermaid diagram on {after_path}')
            diagram(sim, after_path, has_run)
            if args.svg_diagram:
                svg_path = Path(after_path).with_suffix('.svg')
                log.info(f'Saving SVG version of diagram to {svg_path}')
                subprocess.run(['mmdc', '-i', after_path, '-o', svg_path])
            if args.pdf_diagram:
                pdf_path = Path(after_path).with_suffix('.pdf')
                log.info(f'Saving PDF version of diagram to {pdf_path}')
                subprocess.run(['mmdc', '-i', after_path, '-o', pdf_path])

def main():
    args, config = set_config()
    if args.simulate:
        run_simulation(args, config)


if __name__ == '__main__':
    main()