import csv
import logging
import math as m
import random
import subprocess
import time
from argparse import ArgumentParser, BooleanOptionalAction, SUPPRESS, ArgumentDefaultsHelpFormatter
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import numpy as np
import networkx as nx
import sympy as sym
import yaml
from tqdm import tqdm
from addict import Addict

from multiworld.config_space import ConfigSpacePoint, ConfigSpace #, PCoordValue,
from multiworld.gate import FredkinGate #, DelayGate
from multiworld.particle import Particle
import multiworld.qnumber as qn
from multiworld.qnumber import CalcMode, qify
from multiworld.simulation import Simulation
from multiworld.util import QLogger, max_width, flat_list, SEP, WIRES, enough, Sign, default_wires, zerop, show_points
from multiworld.spacewalk import run_paths
from multiworld.visualizations import diagram, network_graph

log = None

def write_points_to_csv(name, particle_names, points:list):
    with open(f'{name}.csv', 'w') as out_csv:
        fieldnames = ['step']
        for p in particle_names:
            fieldnames += [f'{p}.sign', f'{p}.position']
        fieldnames += ['weight', 'probability']
        writer = csv.writer(out_csv, delimiter=',')
        writer.writerow(fieldnames)
        for v in points:
            writer.writerow(
                [v.step] + flat_list([[coord.sign, coord.position] for coord in v.coords] + [v.weight, v.probability]))


def main():
    global log
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', required=True, help="REQUIRED Path to YAML configuration file")
    parser.add_argument('--configs-dir', default='models', help='Directory for model files')
    parser.add_argument('--use-defaults', action=BooleanOptionalAction, default=True,
                        help='Load default values from defaults.yaml before individual model files')
    parser.add_argument('-s', '--simulate', action=BooleanOptionalAction, default=True, help='Run simulation')
    parser.add_argument('-l', '--log', default=None, type=str, help='Log file')
    parser.add_argument('--loglevel', choices=['debug', 'info', 'warning', 'error'], help='Default is info')
    parser.add_argument('--preserve-log', action='store_true', help='Preserve existing log file')
    parser.add_argument('--dup-log-to-console', action=BooleanOptionalAction,
                        default=True, help='Log to console as well as file')
    parser.add_argument('-d', '--diagram', type=str,
                        help="Create a Mermaid diagram of the gate network on the named file with default extension '.mmd'")
    parser.add_argument('--no-diagram', action='store_true', default=SUPPRESS, help='Do not create a diagram')
    parser.add_argument('--diagram-dir', type=str, default='mermaid', help='Directory for Mermaid diagrams')
    parser.add_argument('--svg-diagram', action=BooleanOptionalAction, default=True,
                        help='Create an SVG version of the diagram. Requires mmdc command-line Mermaid renderer')
    parser.add_argument('--pdf-diagram', action=BooleanOptionalAction, default=False,
                        help='Create a PDF version of the diagram. Requires mmdc command-line Mermaid renderer')
    parser.add_argument('--network-graph', action=BooleanOptionalAction, default=True,
                        help='Plot paths through configuration space')
    parser.add_argument('--show-graph', action=BooleanOptionalAction, default=True, help='Display config space plot on screen')
    parser.add_argument('--pdf-graph', action=BooleanOptionalAction, default=True,
                        help='Create a PDF version of the config space plot')
    parser.add_argument('--diagram-when', choices=['before', 'after', 'both'], default='before',
                        help='When to create a diagram, before or after simulation')
    parser.add_argument('--csv-output', default=None, type=str, help='CSV output file, default is no CSV output')
    parser.add_argument('--symbolic', action='store_true', default=SUPPRESS, help='Force symbolic math')
    parser.add_argument('--numeric', action='store_true', default=SUPPRESS, help='Force numeric math')
    parser.add_argument('--sample', action='store_true', help='Run multiple trials and collect a histogram of results')
    parser.add_argument('--n-samples', type=int, default=1, help='Run this many sampling trials')
    parser.add_argument('--epr-stats', action='store_true', help='Run statistics on EPR experiment model (book figure 4.16)')
    parser.add_argument('--measure-discrepancy', action='store_true',
                        help='Measure discrepancy for EPR experiment. Assumes a network consistent with book figure 4.16')
    parser.add_argument('--full-stats', action='store_true', help='Include particle names and probabilities in results')
    parser.add_argument('--delete-zeros', action=BooleanOptionalAction, default=SUPPRESS, help='Delete points containing zero values')
    parser.add_argument('--disappear-zeros', action=BooleanOptionalAction, default=SUPPRESS, help='Zero-valued particles vanish altogether (dimension itself goes away)')
    parser.add_argument('--skip-zeros', action=BooleanOptionalAction, default=SUPPRESS, help='Skip over (but not delete) zero-value results')
    parser.add_argument('--disallow-excess-weights', action=BooleanOptionalAction, default=SUPPRESS, help='Skip over result weights that would sum to more than one')
    args = parser.parse_args()
    config_path = Path(args.configs_dir, args.config).with_suffix('.yaml')
    config_dir = args.configs_dir
    if args.use_defaults:
        with open(Path(config_dir, 'defaults.yaml'), 'r') as f:
            config_dict = yaml.safe_load(f)
    else:
        config_dict = {}
    with open(config_path, 'r') as f:
        config_dict.update(yaml.safe_load(f))
    config = Addict(config_dict)
    symbolic = config.symbolic or False
    CalcMode.default('Symbolic' if symbolic else 'Float')
    qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
    qn.I = qn.I_fn()
    qn.PI = qn.PI_fn()
    config.config_path = args.config
    if args.loglevel is not None:
        loglevel = args.loglevel.upper()
    elif 'loglevel' in config.keys():
        loglevel = config.loglevel.upper()
    else:
        loglevel = logging.INFO
    if args.log is not None:
        log_path = Path(args.log).with_suffix('.log')
        if not args.preserve_log:
            log_path.unlink(missing_ok=True)
        logging.basicConfig(filename=log_path, format='%(levelname)s:  %(message)s', level=loglevel)
        if args.dup_log_to_console:
            logging.getLogger('multiworld').addHandler(QLogger())
    else:
        logging.basicConfig(format=' %(message)s', level=loglevel, handlers=[QLogger()])
    log = logging.getLogger('multiworld')
    epr_stats = args.epr_stats or config.get('epr_stats')
    if args.preserve_log: log.info(' ')
    if 'symbolic' in args:
        config.symbolic = args.symbolic
    if 'numeric' in args:
        config.symbolic = not args.numeric
    if args.sample:
        config.sample = True
        config.n_samples = args.n_samples
    if 'delete_zeros' in args:
        config.delete_zeros = args.delete_zeros
    if 'skip_zeros' in args:
        config.skip_zeros = args.skip_zeros
    if 'disappear_zeros' in args:
        config.disappear_zeros = args.disappear_zeros
    if 'disallow_excess_weights' in args:
        config.disallow_excess_weights = args.disallow_excess_weights
    log.info(f'QUANTISH PHYSICS SIMULATION STARTING: {config["title"]} at {time.asctime()}')
    if args.measure_discrepancy: config.measure_discrepancy = True
    elif 'measure_discrepancy' not in config.keys(): config.measure_discrepancy  = False
    log.info(f"{'SYMBOLIC' if symbolic else 'FLOATING POINT'} MODE")
    if log.getEffectiveLevel() == logging.DEBUG:
        log.debug(f'ARGS:')
        for k, v in args.__dict__.items():
            if k[0] != '_':
                log.debug(f'   {k}: {v}')
        log.debug('')
        log.debug(f'CONFIG:')
        for k, v in config_dict.items():
            log.debug(f'   {k}: {v}')
    q1 = None
    q2 = None
    dpath = None
    has_run = False
    save_ll = log.getEffectiveLevel()
    sim = Simulation(config)
    if 'no_diagram' not in args:
        if args.diagram is None:
            dpath = Path(args.diagram_dir, args.config).with_suffix('.mmd')
        else:
            dpath = Path(args.diagram_dir, args.diagram, ).with_suffix('.mmd')
        if 'diagram_when' in args:
            if args.diagram_when in ('before', 'both'):
                before_path = dpath.with_stem(dpath.stem+'_before').with_suffix('.mmd')
                log.info(f'Generating Mermaid diagram on {before_path}')
                diagram(sim, before_path, False)
                if args.svg_diagram:
                    svg_path = Path(before_path).with_suffix('.svg')
                    log.info(f'Saving SVG version of diagram to {svg_path}')
                    subprocess.run(['mmdc', '-i', before_path, '-o', svg_path])
                if args.pdf_diagram:
                    pdf_path = Path(before_path).with_suffix('.pdf')
                    log.info(f'Saving PDF version of diagram to {pdf_path}')
                    subprocess.run(['mmdc', '-i', before_path, '-o', pdf_path, '--pdfFit'])
        log.info(' ')
    if args.simulate:
        result_space, all_points = sim.run()
        if args.csv_output is not None:
            with open(f'{args.csv_output}_results.csv', 'w') as result_csv:
                fieldnames = ['step']
                for p in sim.particles.values():
                    fieldnames += [f'{p.name}.sign', f'{p.name}.position']
                fieldnames += ['weight', 'probability']
                writer = csv.writer(result_csv, delimiter=',')
                writer.writerow(fieldnames)
                for v in result_space.index.values():
                    writer.writerow([v.step] + flat_list([[pcoord.pkey.sign, pcoord.position] for pcoord in v.coords.values()] + [v.weight, v.probability]))
            with open(f'{args.csv_output}_all.csv', 'w') as all_csv:
                fieldnames = ['step']
                for p in sim.particles.values():
                    fieldnames += [f'{p.name}.sign', f'{p.name}.position']
                fieldnames += ['weight', 'probability']
                writer = csv.writer(all_csv, delimiter=',')
                writer.writerow(fieldnames)
                for v in all_points.index.values():
                    writer.writerow([v.step] + flat_list([[pcoord.pkey.sign, pcoord.position] for pcoord in v.coords.values()] + [v.weight, v.probability]))

        steps = result_space.max_step
        has_run = True
        final_points = [v for v in result_space.index.values()
                        if v.step == steps
                        and not zerop(v.weight)]
        log.info(f'finished after {steps} steps, {len(result_space.index)} total points in final config space, {len(final_points)} points from last step')
        log.info(' ')
        if len(final_points) > 0:
            log.info('final results:')
            show_points(final_points, indent='   ')
            pad_len = [0] * len(final_points[0].coords.values())
            by_pname_gate_pos = defaultdict(list)
            by_pkey_gate_count = defaultdict(int)
            # for point in final_points:
            #     coords = list(point.coords.values())
            #     for c in coords:
            #         key = f'{c.name}@{c.position.origin}'
            #         pkey = f'{c.pkey}'
            #         if key in by_pname_gate_pos.keys():
            #             by_pkey_gate_count[pkey] += 1
            #             by_pname_gate_pos[key] = point
            #         else:
            #             by_pkey_gate_count[pkey] = 1
            #             by_pname_gate_pos[key] = point
            #     # positions = [c.position.origin for c in coords]
            #     logstr = [f'{coord.position}' for coord in point.coords.values()]
            #     for i, s in enumerate(logstr):
            #         pad_len[i] = max(pad_len[i], len(s))
            # by_particle = defaultdict(lambda: defaultdict(dict))
            # for k, v in by_pname_gate_pos.items():
            #     pkey = f'{v}'
            #     v.weight /= by_pkey_gate_count[pkey]
            #     pname = v.name
            #     gname = v.position.origin.gate
            #     port = v.position.origin.port
            #     by_particle[pname][gname][port] = v

            log.info(' ')
            # for point in final_points:
            #     coords = list(point.coords.values())
            #     logstr = '  |  '.join([f'{coord:<{pad_len[i]}}' for i, coord in enumerate(coords)])
            #     log.info(f'   {logstr}')
            # log.info(' ')
            log.info('all nonzero:')
            nonzeros = [point for point in final_points if not zerop(point.weight)]
            show_points(nonzeros)
            # for point in nonzeros:
            #     pcvals = list(point.pcvals.values())
            #     positions = [p.pcoord.position.origin for p in pcvals]
            #     particles = [p.particle for p in pcvals]
            #     logstr = '  |  '.join(
            #         [f'{f"{particle.ps(short=True)}@{pos}":<{pad_len[i]}}' for i, (particle, pos) in
            #          enumerate(zip(particles, positions))])
            #     log.info(f'   {logstr}')
            pkey_summary = {}
            pname_summary = {}
            gate_summary = {}
            summary_gate_count = {}
            for point in nonzeros:
                by_particle = defaultdict(list)
                by_pkey = defaultdict(list)
                by_gate_pos = {}
                for pcv in point.pcvals.values():
                    by_pkey[pcv.particle.pkey] += [pcv]
                    by_particle[pcv.particle.name] += [pcv]
                    origin = pcv.pcoord.position.origin
                    if pcv.pcoord.position.origin.gate not in by_gate_pos.keys():
                        by_gate_pos[origin.gate] = default_wires()
                    by_gate_pos[origin.gate][origin.port] += [pcv]
                for pkey, pcvs in by_pkey.items():
                    pkey_summary[pkey] = Particle.merge([pcv.particle for pcv in pcvs])
                for pname, pcvs in by_particle.items():
                    pname_summary[pname] = Particle.merge([pcv.particle for pcv in pcvs], combine_signs=True)
                for gname, vals in by_gate_pos.items():
                    gate_summary[gname] = default_wires()
                    for wire in WIRES:
                        gate_summary[gname][wire] = Particle.merge([v.particle for v in vals[wire]])
                    # summary_gate = pcv.pcoord.position.origin.gate
                    # summary_port = pcv.pcoord.position.origin.port
                    # if summary_gate in summary.keys():
                    #     merged = Particle.merge(summary[summary_gate][summary_port][pcv.particle.sign] + [pcv.particle])
                    #     summary[summary_gate][summary_port][pcv.particle.sign] = merged
                    #     summary_gate_count[summary_gate][summary_port][pcv.particle.sign] += 1
                    # else:
                    #     summary[summary_gate] = {w: {Sign.plus: [], Sign.minus: []} for w in WIRES}
                    #     summary[summary_gate][summary_port][pcv.particle.sign] = [pcv.particle]
                    #     summary_gate_count[summary_gate] = {w: {Sign.plus: 0, Sign.minus: 0} for w in WIRES}
                    #     summary_gate_count[summary_gate][summary_port][pcv.particle.sign] = 1
            # for k in gate_summary.keys():
            #     for kk, kv in summary[k].items():
            #         for sign in Sign:
            #             if kv[sign]:
            #                 summary[k][kk][sign][0].weight /= summary_gate_count[k][kk][sign]
            # for k in summary.keys():
            #     for kk, kv in summary[k].items():
            #         summary[k][kk] = Particle.merge(summary[k][kk][Sign.plus] + summary[k][kk][Sign.minus], combine_signs=True)
            #         if summary[k][kk]:
            #             summary[k][kk] = summary[k][kk][0]
            log.info(' ')
            log.info('gate summary:')
            for gate_name, v in sorted(gate_summary.items(), key=lambda x: x[0]):
                log.info(f'   {sim.gates[gate_name]}: upper: {v["upper"]}, lower: {v["lower"]}')
            log.info(' ')
            log.info('particle summary:')
            for pname in sorted(pname_summary.keys()):
                log.info(f'   {pname}: {pname_summary[pname]}')
            log.info(' ')
            log.info('pkey summary:')
            for pkey in sorted(pkey_summary.keys()):
                log.info(f'   {pkey}: {pkey_summary[pkey]}')

            if config.epr_stats:
                log.info(' ')
                log.info(f'predicted discrepancy rate is {(sim.gates['g5'].theta - sim.gates['g6'].theta).sin ** 2:.3f}')
                p3filtered = [p for p in nonzeros if list(p.pcvals.values())[2].pcoord.position.origin.port == 'upper']
                probs = {'same': 0.0, 'diff': 0.0}
                count_same = 0
                count_diff = 0
                log.info(f'coupled:')
                for point in p3filtered:
                    pcvals = list(point.pcvals.values())
                    p1v, p2v, p3v = pcvals
                    positions = [p.pcoord.position.origin for p in pcvals]
                    particles = [p.particle for p in pcvals]
                    logstr = '  |  '.join(
                        [f'{f"{particle.ps(short=True)}@{pos}":<{pad_len[i]}}' for i, (particle, pos) in
                         enumerate(zip(particles, positions))])
                    log.info(f'   {logstr}')
                    if p3v.pcoord.position.origin.port != 'upper':
                        continue
                    if p1v.pcoord.position.origin.port == p2v.pcoord.position.origin.port:
                        psame = p1v.particle.probability * p2v.particle.probability
                        count_same += 1
                        probs['same'] += psame
                    else:
                        pdiff = p1v.particle.probability * p2v.particle.probability
                        count_diff += 1
                        probs['diff'] += pdiff
                log.info(f'{count_same=}, {count_diff=}, {probs["same"]=:.4f}, {1 - probs["same"]=:.4f}, {probs["diff"]=:.4f}, {1 - probs["diff"]=:.4f}, {abs(probs["same"] - probs["diff"])=:.4f}, {1 - (abs(probs["same"] - probs["diff"]))=:.4f}')

                # run_paths(sim.initial_point, final_points, sim.n_samples, sim)



            print(f'log level was {save_ll}, setting to {logging.WARN}')
            log.setLevel(logging.WARN)
            if args.network_graph:
                network_graph(all_points, dpath, sim)
                # network_graph(result_space, dpath, sim)

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
                subprocess.run(['mmdc', '-i', after_path, '-o', pdf_path, '--pdfFit'])
    log.setLevel(save_ll)
    print(f'setting log level back to {save_ll}')

if __name__ == '__main__':
    main()