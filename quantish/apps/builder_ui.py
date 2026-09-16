"""The network builder's library side: what the builder notebook
calls instead of holding itself. A model loaded into the builder is a
plain dict (`new_model`, `loaded_model`); the canvas's live
translation into a runnable config is `derive_config`; the run, the
sweep run, and the final-points table take the derived config and the
switch-off choices. Widgets stay in the notebook (marimo tracks a
widget only as a cell global); this module builds the values and
views the cells bind and show.
"""
from __future__ import annotations

from pathlib import PurePath

import marimo as mo
import yaml
from addict import Dict as Addict

from quantish.apps.common import switched_off
from quantish.apps.sweep_ui import sweep_chart, sweep_run
from quantish.builder import (
    angle_degrees,
    coherence_warnings,
    config_extras,
    config_to_graph,
    extract_sections,
    graph_to_config,
    section_body,
    validate_graph,
    variables_block,
    variables_env,
)
from quantish.display import (
    cs_point_sort_key,
    html_table,
    particle_names,
    particle_tokens,
    sym_or_float,
)
from quantish.qnumber import CalcMode
from quantish.screen import model_label
from quantish.screen import model_title as yaml_title
from quantish.simulation import Simulation
from quantish.sweep import check_sweep
from quantish.util import angle_label

# the calculation-mode picker's labels for the model's tri-state
# `symbolic` (None leaves the mode out of the YAML)
MODE_LABELS = {None: '-', False: 'Float', True: 'Symbolic'}
MODE_VALUES = {v: k for k, v in MODE_LABELS.items()}
# the run's config on top of the derived model
RUN_SETTINGS = {'string_precision': 2, 'max_symbolic_len': 40,
                'loglevel': 'warning'}
EMPTY_GRAPH = {'gates': {}, 'particles': {}, 'links': []}


def tri_mode(config) -> bool | None:
    """The model's calculation mode as the builder's tri-state:
    `calculation_mode` is a case-independent string; None when the
    YAML leaves it unset (the legacy boolean `symbolic` still read on
    upload of old files)."""
    mode = config.get('calculation_mode')
    if mode is not None:
        return str(mode).lower() == 'symbolic'
    if 'symbolic' in config:
        return bool(config['symbolic'])
    return None


def new_model() -> dict:
    """An empty model, as the builder holds a loaded one."""
    return {'graph': {'gates': {}, 'particles': {}, 'links': []},
            'notes': [], 'title': 'my_network', 'file': 'my_network',
            'caption': '', 'variables': {}, 'variables_text': '',
            'symbolic': None, 'angle_unit': None, 'model_notes': '',
            'extras': {}, 'extras_text': {}, 'source': 'a new empty model'}


def loaded_model(text: str, source: str) -> dict:
    """A model file's text as the builder holds it: the canvas graph
    and the loader's notes, the header fields, the variables section
    as written (comments kept — the parsed dict is the fallback for
    files with none), and the sections the builder does not edit (a
    sweep, epr_stats, …), parsed for the config and raw for the saved
    file. Raises on a file the builder cannot read."""
    config = yaml.safe_load(text)
    graph, notes = config_to_graph(config)
    sections = extract_sections(text)
    return {'graph': graph, 'notes': notes,
            'title': config.get('title') or 'my_network',
            'file': PurePath(source).stem,
            'caption': config.get('caption') or '',
            'variables': config.get('variables') or {},
            'variables_text': section_body(sections.get('variables', '')),
            'symbolic': tri_mode(config),
            'angle_unit': config.get('angle_unit'),
            'model_notes': config.get('notes') or '',
            'extras': config_extras(config),
            'extras_text': sections,
            'source': source}


def loaded_report(loaded: dict | None):
    """What the header shows about the last load: the source and the
    loader's notes; None before any load."""
    if not loaded or not loaded.get('source'):
        return None
    msg = ('<span style="font-size: 0.9em">loaded '
           f"**{loaded['source']}**</span>")
    if loaded['notes']:
        msg += '\n' + '\n'.join(f'- {n}' for n in loaded['notes'])
    return mo.md(msg)


def model_options(model_paths: dict, collection: str | None) -> dict:
    """The model picker's `label: key` options for one collection."""
    return {model_label(k.split('/', 1)[1].removesuffix('.yaml'),
                        yaml_title(model_paths[k])): k
            for k in sorted(model_paths) if k.split('/')[0] == collection}


def canvas_counts(graph) -> tuple[int, int]:
    """(gates, particles) on the canvas."""
    return len(graph.get('gates') or {}), len(graph.get('particles') or {})


def run_order(graph) -> tuple[list[str], list[str]]:
    """The switch-off rows' order: gates in run order (the stages the
    translation derives, any it cannot place after, by name; delay
    gates have nothing to switch off), then the particles."""
    try:
        staged = [g for stage in graph_to_config(graph, 'x')
                  .get('run_stages', {}).values() for g in stage]
    except Exception:  # noqa: BLE001 — a wiring loop: no order to speak of
        staged = []
    gates = [n for n, g in (graph.get('gates') or {}).items()
             if g.get('kind') != 'delay']
    gates.sort(key=lambda n: (staged.index(n) if n in staged else len(staged), n))
    return gates, list(graph.get('particles') or {})


def derive_config(graph, *, title: str, caption: str, model_vars: dict,
                  mode_label: str, unit_label: str, notes: str,
                  extras: dict, sweep_cfg, all_particles_off: bool = False
                  ) -> tuple[dict | None, list[str]]:
    """The live translation of the canvas: (config, []) when it can
    run — caption, notes, variables, calculation mode, angle unit, the
    loaded model's other sections, and the declared sweep included —
    or (None, the problems keeping it from running)."""
    unit = None if unit_label == '-' else unit_label
    problems = validate_graph(graph, variables=model_vars,
                              angle_unit=unit or 'radians')
    if all_particles_off:
        problems.append('every particle is switched off — nothing would enter')
    if problems:
        return None, problems
    try:
        config = graph_to_config(
            graph, title, caption=caption.strip() or None,
            variables=model_vars or None, symbolic=MODE_VALUES[mode_label],
            angle_unit=unit, notes=notes.strip() or None,
            extras={**{k: v for k, v in extras.items() if k != 'sweep'},
                    **({'sweep': sweep_cfg} if sweep_cfg else {})})
    except ValueError as exc:  # a wiring loop
        return None, [str(exc)]
    if sweep_cfg:
        # the sweep must name the model's own variable, particle, and gate
        try:
            check_sweep(Simulation(Addict({'loglevel': 'warning', **config})),
                        sweep_cfg)
        except Exception as exc:  # noqa: BLE001 — the engine's own wording
            return None, [f'sweep: {exc}']
    return config, []


def angle_labels(graph, model_vars: dict, unit_label: str) -> dict[str, str]:
    """The canvas's display label per gate ('pi/6 (30.0°)'); a spec the
    engine cannot parse shows flagged, the specifics being in the
    problems list."""
    env, _ = variables_env(model_vars)
    unit = 'radians' if unit_label == '-' else unit_label
    out = {}
    for name, gd in (graph.get('gates') or {}).items():
        if gd.get('kind') == 'delay':
            continue
        spec = gd.get('phase' if gd.get('kind') == 'phase' else 'angle', 0)
        try:
            out[name] = angle_label(spec, angle_degrees(spec, env, unit), '°',
                                    variables=model_vars)
        except Exception:  # noqa: BLE001 — reported via problems
            out[name] = f'⚠ {spec}'
    return out


def raw_sections(extras_text: dict, model_vars: dict, variables_text: str) -> dict:
    """What the save writes verbatim: the loaded file's unhandled
    sections (the sweep is regenerated) and, when the editor holds
    variables, its text — comments included."""
    out = {k: v for k, v in extras_text.items() if k != 'sweep'}
    if model_vars and variables_text.strip():
        out['variables'] = variables_block(variables_text)
    return out


def status_view(graph, problems: list[str], config: dict | None):
    """The status line under the canvas: the counts and either why the
    network is not runnable (in red — the one message that says why
    Run is disabled) or its stages and any coherence warnings."""
    n_g, n_p = canvas_counts(graph)
    summary = f'{n_g} gate(s), {n_p} particle(s), {len(graph.get("links", []))} wire(s)'
    if problems:
        msg = summary + ' — **not runnable yet:**\n' + '\n'.join(f'- {p}' for p in problems)
        return mo.Html(f'<div class="not-runnable">{mo.md(msg).text}</div>')
    stages = ' | '.join(f"{name}: {', '.join(gs)}"
                        for name, gs in config['run_stages'].items())
    msg = f'{summary} — runnable. Stages: {stages}'
    warns = coherence_warnings(graph)
    if warns:
        msg += '\n' + '\n'.join(f'- ⚠ {w}' for w in warns)
    return mo.md(msg)


def run_config(config: dict) -> Addict:
    """The derived model as the engine takes it, with the calculation
    mode set as the model asks."""
    CalcMode.default('Symbolic' if str(config.get('calculation_mode')
                                       or '').lower() == 'symbolic' else 'Float')
    cfg = Addict({**RUN_SETTINGS, **config})
    cfg.config_path = 'builder'
    return cfg


def _off_note(inert, absent) -> str:
    return ''.join(f' — {what} off: {", ".join(names)}'
                   for what, names in (('gates', inert), ('particles', absent))
                   if names)


def run_network(config: dict | None, off_values: dict):
    """The Run: (Simulation, report) after a successful run, (None,
    why not) on failure, (None, None) with nothing to run. Switched-off
    gates go inert (wires), particles absent (null inputs)."""
    if not config:
        return None, None
    inert, absent = switched_off(off_values)
    cfg = run_config(config)
    try:
        s = Simulation(cfg, inert=inert, absent=absent)
        s.run()
    except Exception as exc:  # noqa: BLE001 — show, don't crash the app
        return None, mo.md(f'**run failed** — `{exc}`')
    total = sum(float(p.probability) for p in s.result_space.index.values())
    bad = s.inexact_inputs()
    note = ('' if not bad else
            '<br><span style="color: #b00020">⚠ Symbolic mode, but '
            + ', '.join(bad) + (' is' if len(bad) == 1 else ' are')
            + ' not exact (a floating-point or long decimal value), '
            'so these results carry floating point.</span>')
    return s, mo.md(
        f'Ran **{cfg.title}** — {len(s.run_stages)} stage(s), '
        f'{len(s.result_space.index)} final configuration-space '
        f'point(s), total probability {total:.6f}' + _off_note(inert, absent) + note)


def run_sweep(config: dict | None, sweep_cfg, off_values: dict, degrees: bool):
    """The declared sweep, run and plotted; the switched-off gates and
    particles apply to every point, as to a run of the network."""
    if config is None or sweep_cfg is None:
        return mo.md('')
    inert, absent = switched_off(off_values)
    try:
        with mo.status.spinner(title='running the sweep…'):
            res = sweep_run(Simulation(run_config(config)), sweep_cfg,
                            inert=inert, absent=absent)
    except Exception as exc:  # noqa: BLE001 — show, don't crash the app
        return mo.md(f'**sweep failed** — `{exc}`')
    return mo.vstack([mo.md(f"{len(res['x'])} points{_off_note(inert, absent)}"),
                      sweep_chart(res, sweep_cfg, degrees)], gap=0.3)


def final_points_html(sim) -> str:
    """The final configuration-space points: one column per particle
    under a 'configuration' heading that names each, the weight and
    probability at a fixed precision (exact forms in Symbolic mode
    when short)."""
    rows = []
    for p in sorted(sim.result_space.index.values(),
                    key=lambda p: cs_point_sort_key(sim, p)):
        w = complex(p.weight)
        rows.append([f'`{tok}`' for _, tok in particle_tokens(sim, p)]
                    + [sym_or_float(p.weight, f'{w.real:.3f}{w.imag:+.3f}i'),
                       sym_or_float(p.probability, f'{float(p.probability):.3f}')])
    return html_table(
        [('configuration', particle_names(sim)), ('weight', None),
         ('probability', None)], rows,
        lambda t: mo.md(t).text if any(ch in t for ch in '$`*') else t)
