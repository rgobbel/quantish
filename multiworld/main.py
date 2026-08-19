import csv
import logging
import subprocess
import time
from argparse import ArgumentParser, BooleanOptionalAction, SUPPRESS, ArgumentDefaultsHelpFormatter
from collections import defaultdict
from pathlib import Path

import yaml
from addict import Addict

import multiworld.qnumber as qn
from multiworld.qnumber import CalcMode
from multiworld.simulation import Simulation
from multiworld.util import QLogger, flat_list, zerop, show_points
from multiworld.mermaid_diagram import diagram
from multiworld.network_graph import NetworkGraph

log = None

def mmdc_cmd():
    """The mermaid-cli command, with our puppeteer config when present.

    Homebrew's mermaid-cli pins an exact headless-Chrome version that
    breaks on every upgrade; puppeteer-config.json points it at the
    installed Google Chrome instead.
    """
    cmd = ['mmdc']
    pconfig = Path(__file__).resolve().parents[1] / 'puppeteer-config.json'
    if pconfig.exists():
        cmd += ['-p', str(pconfig)]
    return cmd


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
                [v.step] + flat_list([[coord.sign, coord.position] for coord in v.coords.values()] + [v.weight, v.probability]))


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
    parser.add_argument('--tikz-diagram', type=str, default=None,
                        help='Render a TikZ circuit diagram to this file in the diagram dir '
                             '(.pdf/.svg/.png chosen by extension, default .pdf). Requires pdflatex.')
    parser.add_argument('--csv-output', default=None, type=str, help='CSV output file, default is no CSV output')
    parser.add_argument('--set', dest='set_vars', action='append', default=[],
                        metavar='NAME=EXPR',
                        help='Override a model variable, e.g. --set theta2=pi/8 '
                             '(repeatable). Affects gates whose angles reference '
                             'the variable BY NAME (angle: theta2), not YAML '
                             'aliases (angle: *theta2), which copy the value at '
                             'parse time.')
    parser.add_argument('--symbolic', action='store_true', default=SUPPRESS, help='Force symbolic math')
    parser.add_argument('--numeric', action='store_true', default=SUPPRESS, help='Force numeric math')
    parser.add_argument('--sample', action='store_true', help='Run multiple trials and collect a histogram of results')
    parser.add_argument('--n-samples', type=int, default=1, help='Run this many sampling trials')
    parser.add_argument('--mc-mode', choices=['terminal', 'path', 'both'], default='both',
                        help='Monte Carlo sampling mode (with --sample): terminal draws from the '
                             'final superposition, path walks one world-line per trial')
    parser.add_argument('--mc-seed', type=int, default=None, help='Monte Carlo RNG seed')
    parser.add_argument('--epr-stats', action='store_true', help='Run statistics on EPR experiment model (book figure 4.16)')
    parser.add_argument('--measure-discrepancy', action='store_true',
                        help='Measure discrepancy for EPR experiment. Assumes a network consistent with book figure 4.16')
    parser.add_argument('--full-stats', action='store_true', help='Include particle names and probabilities in results')
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
    for item in args.set_vars:
        name, sep, expr = item.partition('=')
        if not sep or not name.strip():
            raise SystemExit(f"--set expects NAME=EXPR, got '{item}'")
        config.variables[name.strip()] = expr.strip()
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
    if args.preserve_log: log.info(' ')
    if 'symbolic' in args:
        config.symbolic = args.symbolic
    if 'numeric' in args:
        config.symbolic = not args.numeric
    if args.sample:
        config.sample = True
        config.n_samples = args.n_samples
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
    dpath = None
    has_run = False
    save_ll = log.getEffectiveLevel()
    sim = Simulation(config)
    if args.tikz_diagram:
        from multiworld.tikz_diagram import render_from_simulation
        tikz_path = Path(args.diagram_dir, args.tikz_diagram)
        if not tikz_path.suffix:
            tikz_path = tikz_path.with_suffix('.pdf')
        log.info(f'Rendering TikZ circuit diagram to {tikz_path}')
        if not render_from_simulation(sim, tikz_path):
            log.warning(f'TikZ diagram render failed (see stderr)')
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
                    subprocess.run(mmdc_cmd() + ['-i', before_path, '-o', svg_path])
                if args.pdf_diagram:
                    pdf_path = Path(before_path).with_suffix('.pdf')
                    log.info(f'Saving PDF version of diagram to {pdf_path}')
                    subprocess.run(mmdc_cmd() + ['-i', before_path, '-o', pdf_path, '--pdfFit'])
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
            log.info(' ')
            nonzeros = final_points  # zero-weight worlds were already dropped by the runner
            # marginal probabilities: each config space point contributes its |weight|^2 to
            # every coordinate it assigns
            try:
                pkey_summary = defaultdict(float)
                pname_summary = defaultdict(float)
                gate_summary = defaultdict(lambda: defaultdict(float))
                for point in nonzeros:
                    prob = float(point.probability)
                    for pname, coord in point.coords.items():
                        origin = coord.position.origin
                        pkey_summary[f'{coord.pkey}@{origin}'] += prob
                        pname_summary[f'{pname}@{origin}'] += prob
                        if origin is not None and origin.gate is not None:
                            gate_summary[origin.gate][origin.port] += prob
                log.info(' ')
                log.info('gate summary (probability by output port):')
                for gate_name in sorted(gate_summary.keys()):
                    ports = gate_summary[gate_name]
                    portstr = ', '.join(f'{port}: {ports[port]:.4f}' for port in sorted(ports.keys()))
                    log.info(f'   {sim.gates[gate_name]}: {portstr}')
                log.info(' ')
                log.info('particle summary (probability by position):')
                for pname in sorted(pname_summary.keys()):
                    log.info(f'   {pname}: {pname_summary[pname]:.4f}')
                log.info(' ')
                log.info('pkey summary (probability by position and sign):')
                for pkey in sorted(pkey_summary.keys()):
                    log.info(f'   {pkey}: {pkey_summary[pkey]:.4f}')
            except (TypeError, ValueError):
                log.info('skipping numeric summaries (symbolic weights with free symbols)')

            if config.epr_stats:
                from multiworld.epr import expected_discrepancy, is_two_stage, outcome
                log.info(' ')
                two_stage = is_two_stage(sim)
                predicted = expected_discrepancy(sim)
                if predicted is not None:
                    log.info(f'predicted discrepancy rate is {float(predicted):.4f} '
                             f'(outcome = {"position" if two_stage else "position⊕sign"}, '
                             f'law sin²((Q5+Q6)−(Q7+Q8)))')
                # Tally BOTH g4 branches, not just the conventional coupled
                # one: with g2 = g1 (missing the +π/2) the coupling inverts
                # onto g4.lower, and showing one branch alone is unreadable.
                branches = {'upper': {'same': 0.0, 'diff': 0.0},
                            'lower': {'same': 0.0, 'diff': 0.0}}
                for point in nonzeros:
                    coords = list(point.coords.values())
                    couplers = [c for c in coords
                                if c.position.origin is not None
                                and c.position.origin.gate == 'g4']
                    if len(couplers) != 1:
                        continue
                    others = [c for c in coords if c is not couplers[0]]
                    kind = ('same' if outcome(others[0], two_stage)
                            == outcome(others[1], two_stage) else 'diff')
                    branch = branches[couplers[0].position.origin.port]
                    branch[kind] += float(point.probability)
                    log.info(f'   [p3@g4.{couplers[0].position.origin.port} '
                             f'{kind}] {point}')
                for port, probs in branches.items():
                    total = probs['same'] + probs['diff']
                    if total == 0:
                        continue
                    rate = probs['diff'] / total
                    log.info(f"p3@g4.{port}: same p={probs['same']:.4f} + "
                             f"diff p={probs['diff']:.4f} = {total:.4f}; "
                             f"discrepancy = {probs['diff']:.4f}/{total:.4f} "
                             f"= {rate:.4f}")
                rate_up = branches['upper']
                total_up = rate_up['same'] + rate_up['diff']
                if total_up > 0:
                    log.info(f"observed discrepancy rate = "
                             f"{rate_up['diff'] / total_up:.4f} "
                             f"(coupled = p3@g4.upper, the fig 4.17 "
                             f"convention with Q2 = Q1 + π/2)")
                    if predicted is not None:
                        lo = branches['lower']
                        total_lo = lo['same'] + lo['diff']
                        if (total_lo > 0
                                and abs(rate_up['diff'] / total_up - float(predicted)) > 0.01
                                and abs((1 - lo['diff'] / total_lo) - float(predicted)) <= 0.01):
                            log.warning(
                                'the LOWER branch anti-correlates at the '
                                'predicted rate — the coupling appears '
                                'INVERTED (is g2 missing its +π/2?)')
                else:
                    log.info('no coupled worlds at p3@g4.upper')

                # run_paths(sim.initial_point, final_points, sim.n_samples, sim)



            if config.sample and sim.n_samples > 0:
                from multiworld.montecarlo import run_monte_carlo
                run_monte_carlo(sim, sim.n_samples, mode=args.mc_mode, seed=args.mc_seed)
                from multiworld.epr import run_epr_experiment, supports_epr
                if supports_epr(sim):
                    run_epr_experiment(sim, sim.n_samples, seed=args.mc_seed)

            print(f'log level was {save_ll}, setting to {logging.WARN}')
            log.setLevel(logging.WARN)
            if args.network_graph:
                if dpath is None:  # diagrams disabled; still need a stem for the graph PDF
                    dpath = Path(args.diagram_dir, args.config).with_suffix('.mmd')
                NetworkGraph(all_points, sim, dpath, show=args.show_graph)

    if 'no_diagram' not in args:
        if args.diagram_when in ('after', 'both'):
            after_path = dpath.with_stem(dpath.stem+'_after').with_suffix('.mmd')
            log.info(f'Generating Mermaid diagram on {after_path}')
            diagram(sim, after_path, has_run)
            if args.svg_diagram:
                svg_path = Path(after_path).with_suffix('.svg')
                log.info(f'Saving SVG version of diagram to {svg_path}')
                subprocess.run(mmdc_cmd() + ['-i', after_path, '-o', svg_path])
            if args.pdf_diagram:
                pdf_path = Path(after_path).with_suffix('.pdf')
                log.info(f'Saving PDF version of diagram to {pdf_path}')
                subprocess.run(mmdc_cmd() + ['-i', after_path, '-o', pdf_path, '--pdfFit'])
    log.setLevel(save_ll)
    print(f'setting log level back to {save_ll}')

if __name__ == '__main__':
    main()