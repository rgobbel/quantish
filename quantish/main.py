from argparse import ArgumentParser, BooleanOptionalAction
import logging
from collections import defaultdict
from pathlib import Path
import time

import numpy as np
import yaml
from quantish.simulation_v2 import Simulation
from quantish.visualizations import diagram
from quantish.qnumber import CalcMode
from quantish.util import QLogger
from quantish.sink import SinkEncoder
from quantish.particle import Particle
import json

def main():
    parser = ArgumentParser()
    parser.add_argument('-c', '--config', required=True, help="Path to YAML configuration file")
    parser.add_argument('-s', '--simulate', action=BooleanOptionalAction, default=True, help='Run simulation')
    parser.add_argument('-d', '--diagram', type=str, help="Create a Mermaid diagram of the gate network on the named file, extension '.mmd'")
    parser.add_argument('--diagram-when', choices=['before', 'after', 'both'], default='after', help='When to create a diagram, before or after simulation')
    parser.add_argument('-l', '--log', type=str, help='Log file')
    parser.add_argument('--loglevel', choices=['debug', 'info', 'warning', 'error'], default='info')
    parser.add_argument('--control-threshold', type=float, help='Probability threshold for considering a control input "present"')
    parser.add_argument('--preserve-log', action='store_true', help='Preserve existing log file. Default is to wipe it out and start over')
    parser.add_argument('--forward-threshold', type=float, help='Probability threshold for forwarding outputs')
    parser.add_argument('--normalize-inputs', action=BooleanOptionalAction, help='Normalize weights before measuring')
    parser.add_argument('--normalize-outputs', action=BooleanOptionalAction, help='Normalize weights after measuring')
    parser.add_argument('--symbolic', action='store_true', help='Force symbolic math')
    parser.add_argument('--numeric', action='store_true', help='Force numeric math')
    parser.add_argument('--winner-take-all', '-wta', action=BooleanOptionalAction, default=True, help='Only process highest probability control')
    parser.add_argument('--add-with-signs', action=BooleanOptionalAction, default=True, help='Multiply weight values by particle sign when adding particles')
    parser.add_argument('--use-common', action=BooleanOptionalAction, default=True, help='Use values from common.yaml instead of individual model files')
    parser.add_argument('--sample', action='store_true', help='Take gate outputs as distributions, run with one random sample')
    parser.add_argument('--n-samples', type=int, default=100, help='Run this many sample executions, collect statistics on results')
    parser.add_argument('--epr-stats', action='store_true', help='Run statistics on EPR experiment model')
    parser.add_argument('--full-stats', action='store_true', help='Include particle names and probabilities in results')
    args = parser.parse_args()
    loglevel = args.loglevel.upper()
    if args.log is not None:
        log_path = Path(args.log).with_suffix('.log')
        if not args.preserve_log:
            log_path.unlink(missing_ok=True)
        logging.basicConfig(filename=log_path, format='%(levelname)s:  %(message)s', level=loglevel)
    else:
        logging.basicConfig(format='%(message)s', level=loglevel, handlers=[QLogger()])
    log = logging.getLogger('quantish')
    if args.preserve_log: log.info('')
    config_path = Path(args.config).with_suffix('.yaml')
    config_dir = config_path.parent
    if args.use_common:
        with open(Path(config_dir, 'common.yaml'), 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    config['sample'] = args.sample
    config['n_samples'] = args.n_samples
    with open(config_path, 'r') as f:
        config.update(yaml.safe_load(f))
    if args.symbolic:
        config['symbolic'] = True
    if args.numeric:
        config['symbolic'] = False
    symbolic = config.get('symbolic')
    CalcMode.mode = 'Symbolic' if symbolic else 'Float'
    log.info(f'QUANTISH PHYSICS SIMULATION STARTING: {config["title"]} at {time.asctime()}')
    if args.forward_threshold is not None:
        config['probability_threshold']['fowarding'] = args.forward_threshold
    if args.control_threshold is not None:
        config['probability_threshold']['control'] = args.normalize_inputs
    if args.normalize_inputs is not None:
        config['normalize_weights']['input'] = args.control_threshold
    if args.normalize_outputs is not None:
        config['normalize_weights']['output'] = args.normalize_outputs
    log.info(f"{'SYMBOLIC' if symbolic else 'FLOATING POINT'} MODE")
    if config.get('sample'):
        stats = []
        thresholds = []
        histogram = defaultdict(int)
        histogram['coupled-equal'] = 0
        histogram['coupled-unequal'] = 0
        histogram['uncoupled-equal'] = 0
        histogram['uncoupled-unequal'] = 0
        for i in range(config.get('n_samples')):
            sim = Simulation(config)
            sinks, _ = sim.run()
            run_result = {}
            thresholds.append(sim.control_threshold)
            for sname, sval in sinks.items():
                merged = Particle.merge(sval.values.values())
                if merged is not None: # and merged.probability > 0.5:
                    s_part = f'{"+" if merged.sign == 1 else "-"}{merged.name.split('>')[0]}'
                    run_result[sval.name] = [s_part, f'{merged.probability:.2f}']
            by_gates = defaultdict(dict)
            wires = ['control', 'upper', 'lower']
            winners = {}
            gate_names = [g for g in sim.gates.keys()]
            for gate_name in gate_names:
                probs = {wire: 0.0 for wire in wires}
                for wire in wires:
                    gwire = f'{gate_name}.{wire}'
                    if gwire in sim.sinks.keys():
                        sink = sim.sinks[gwire]
                        probs[wire] = sink.summary_probability()
                        if args.full_stats:
                            merged = Particle.merge(sink.values.values())
                            s_part = f'{"+" if merged.sign == 1 else "-"}{merged.name.split('>')[0]}'
                            run_result[gwire] = [s_part, f'{merged.probability:.2f}']
                    else:
                        probs[wire] = 0.0
                by_gates[gate_name] = {'control': probs['control'], 'upper': probs['upper'], 'lower': probs['lower']}
            if args.epr_stats:
                if by_gates['g4']['upper'] == 1.0 and by_gates['g4']['lower'] == 0.0:
                    if np.isclose(by_gates['g5']['upper'], by_gates['g6']['upper']) and \
                        np.isclose(by_gates['g5']['lower'], by_gates['g6']['lower']):
                        histogram['coupled-equal'] += 1
                    else:
                        histogram['coupled-unequal'] += 1
                else:
                    if np.isclose(by_gates['g5']['upper'], by_gates['g6']['upper']) and \
                        np.isclose(by_gates['g5']['lower'], by_gates['g6']['lower']):
                        histogram['uncoupled-equal'] += 1
                    else:
                        histogram['uncoupled-unequal'] += 1
                for gate_name, values in by_gates.items():
                    if values['upper'] > values['lower']:
                        histogram[f'{gate_name}.upper'] += 1
                        winners[gate_name] = 'upper'
                    else:
                        histogram[f'{gate_name}.lower'] += 1
                        winners[gate_name] = 'lower'
                hist_keys = histogram.keys()
                for k in hist_keys:
                    log.info(f'{k}: {histogram[k]}')
            if args.full_stats:
                stats.append(run_result)
            del sim
        stats.append(histogram)
            # svals = {sname: s.vlist() for sname, s in sinks.items()}
            # jsinks = []
            # for sink in sinks.values():
            #     jsinks.append(json.dumps(sink, cls=SinkEncoder))
        # for run_result in stats:
        #     for k, (v, threshold,) in run_result.items():
        #         histogram[f'{k}-{v}'] += 1
        with open ('stats.json', 'w') as f:
            json.dump(stats, f, sort_keys=True, indent=True)
        # print()
        # print(stats)
    else:
        sim = Simulation(config)
        if args.diagram is not None:
            dpath = Path(args.diagram).with_suffix('.mmd')
        else:
            dpath = Path(args.config).with_suffix('.mmd')
        has_run = False
        if args.diagram_when in ('before', 'both'):
            before_path = dpath.with_stem(dpath.stem+'_before').with_suffix('.mmd')
            diagram(sim, before_path, False)
        if args.simulate:
            sim.run()
            has_run = True
        if args.diagram_when in ('after', 'both'):
            after_path = dpath.with_stem(dpath.stem+'_after').with_suffix('.mmd')
            diagram(sim, after_path, has_run)

if __name__ == '__main__':
    main()