"""What every app needs: the model library, a model over the defaults,
the variables editor's text, the picker and switch-off memories, the
build stamp, and the small markdown wrappers.

`import marimo as mo` is deliberate here: this is the marimo layer of
the package, one step above the engine, and widget-building functions
(`switch_off_boxes`) return elements the calling cell binds to a global
— marimo only tracks an element that is a cell global, so nothing here
keeps one.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import marimo as mo
import yaml
from addict import Dict as Addict

from quantish.qnumber import CalcMode
from quantish.screen import MODELS_ROOTS, model_label, model_title

__all__ = [
    'CONSTANTS', 'MODELS_TOP', 'REPO_DIR', 'WASM_MODE', 'build_stamp', 'collections',
    'editor_ui', 'in_div', 'init_engine', 'load_config', 'md_cell',
    'model_files', 'model_label', 'model_title', 'parse_vars',
    'merge_defaults', 'prose', 'remember_in', 'settable', 'stamp_html', 'switch_off_boxes',
    'switched_off', 'vars_text',
]

WASM_MODE = sys.platform == 'emscripten'
# True while the notebooks run embedded in the suite (the suite sets it
# before embedding them): the editor-only sections stay hidden there,
# whatever the runtime reports for an embedded app
EMBEDDED = False
REPO_DIR = Path(__file__).resolve().parents[2]
# the model library: the copy materialized into the page's virtual
# filesystem under WASM (by the notebook's install cell), else the repo's
MODELS_TOP = MODELS_ROOTS[0] if WASM_MODE else REPO_DIR / 'models'
# files under models/ that are not models
NOT_MODELS = ('defaults.yaml', 'schema.yaml')


def _constants(top: Path = MODELS_TOP) -> frozenset[str]:
    try:
        with open(top / 'defaults.yaml') as f:
            return frozenset((yaml.safe_load(f) or {}).get('variables') or {})
    except OSError:
        return frozenset()


# the defaults' standard variable names (zero, one, eye): constants
# every model can use, merged underneath its own variables by
# load_config — never candidates for a slider, an edit, or a sweep
CONSTANTS = _constants()


def settable(names) -> list[str]:
    """The variables a user may change or sweep: `names` (a model's
    variables, say a Simulation's qvars) with the constants left out."""
    return [n for n in names if n not in CONSTANTS]


def init_engine(mode: str = 'Float') -> None:
    """Every app's engine setup: the calculation mode and quiet logs."""
    CalcMode.default(mode)
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('quantish').setLevel(logging.WARNING)


def editor_ui(wasm_editor: bool | None = None) -> bool:
    """True whenever the surrounding UI is the marimo editor — a local
    `marimo edit`, or a WASM edit-mode export, which the notebook's
    install cell detects from the page (under WASM `mo.app_meta().mode`
    reports 'edit' for both export modes). Editor-only sections key
    off this."""
    if EMBEDDED:
        return False
    if WASM_MODE:
        return bool(wasm_editor)
    return mo.app_meta().mode == 'edit'


def collections(top: Path = MODELS_TOP) -> list[str]:
    """The library's collections: the subdirectories of models/, HIDEME
    and dotted names left out."""
    if not top.is_dir():
        return []
    return sorted(d.name for d in top.iterdir()
                  if d.is_dir() and d.name != 'HIDEME'
                  and not d.name.startswith('.'))


def model_files(top: Path = MODELS_TOP) -> dict[str, Path]:
    """Every model file in the library, 'collection/name.yaml' -> path,
    sorted; the defaults, the schema, and editor droppings left out."""
    if not top.is_dir():
        return {}
    return {str(p.relative_to(top)): p
            for p in sorted(top.rglob('*.yaml'))
            if p.name not in NOT_MODELS
            and not p.name.startswith(('.', '#'))}


def merge_defaults(model: dict, top: Path = MODELS_TOP) -> Addict:
    """A model (parsed) over the defaults. Variables merge deeply, so
    the defaults' standard names (zero, one, eye) stay available
    underneath the model's own; the log level is pinned to warning for
    the apps."""
    with open(top / 'defaults.yaml') as f:
        cfg = yaml.safe_load(f) or {}
    default_vars = dict(cfg.get('variables') or {})
    cfg.update(model)
    if default_vars:
        cfg['variables'] = {**default_vars,
                            **(model.get('variables') or {})}
    cfg['loglevel'] = 'warning'
    return Addict(cfg)


def load_config(path, top: Path = MODELS_TOP) -> tuple[Addict, dict]:
    """A model file over the defaults: (the merged config, the model as
    written) — see merge_defaults."""
    with open(path) as f:
        model = yaml.safe_load(f) or {}
    return merge_defaults(model, top), model


def vars_text(vs) -> str:
    """A variables mapping as the editors' `name: expression` lines
    (strings quoted, so `pi/4` survives a YAML round trip)."""
    return '\n'.join(
        f"{k}: '{v}'" if isinstance(v, str) else f'{k}: {v}'
        for k, v in (vs or {}).items())


def parse_vars(text: str) -> tuple[dict, str | None]:
    """The variables editor's text as a mapping, or ({}, why not): a
    parse problem is shown under the editor and the model's own
    definitions stand meanwhile."""
    text = (text or '').strip()
    if not text:
        return {}, None
    try:
        v = yaml.safe_load(text)
        if v is None:
            return {}, None
        if not isinstance(v, dict):
            raise TypeError('expected name: expression lines')
        return {str(k): val for k, val in v.items()}, None
    except Exception as exc:  # noqa: BLE001 — show, don't crash
        return {}, f'variables not parseable — {exc}'


def remember_in(memory: dict, key, cast=None):
    """An `on_change` callback that keeps a widget's value in a plain
    dict under `key`, so a rebuilt widget can open on it — the apps'
    picker and checkbox memories across model reloads. `cast` (say
    `bool`) normalizes the value first."""
    def cb(value):
        memory[key] = cast(value) if cast is not None else value
    return cb


def switch_off_boxes(memory: dict, gates, particles,
                     gate_label=str, particle_label=str) -> mo.ui.dictionary:
    """The run-time switch-off checkboxes, one per gate ('g:name') and
    particle ('p:name'), True = on; each remembers itself in `memory`
    so a model reload, which rebuilds them, keeps the choices. A gate
    off runs inert (a plain wire), a particle off is absent (a null
    input) — `Simulation(cfg, inert=…, absent=…)`. `gate_label` and
    `particle_label` turn a name into its box's label ('' for a bare
    box beside a name the caller draws itself). The caller binds the
    dictionary to a global and lays its `.elements` out."""
    return mo.ui.dictionary({
        key: mo.ui.checkbox(value=memory.get(key, True), label=label,
                            on_change=remember_in(memory, key, bool))
        for key, label in ([(f'g:{n}', gate_label(n)) for n in gates]
                           + [(f'p:{n}', particle_label(n)) for n in particles])})


def switched_off(values: dict) -> tuple[list, list]:
    """The switch-off boxes' value as (the gates off, the particles
    off) — `Simulation(cfg, inert=…, absent=…)`'s arguments."""
    inert = [k[2:] for k, v in values.items() if k.startswith('g:') and not v]
    absent = [k[2:] for k, v in values.items() if k.startswith('p:') and not v]
    return inert, absent


def md_cell(text: str) -> str:
    """html_table's cell renderer: markdown/math cells go through the
    markdown renderer (its arithmatex spans are typeset in the
    browser); plain cells pass straight through."""
    if any(ch in text for ch in '$`*_<'):
        return mo.md(text).text
    return text


def in_div(cls: str, md) -> mo.Html:
    """Markdown (an `mo.md`, or its source) wrapped in a div carrying a
    CSS class from the app's stylesheet — the class rides inside the
    content, which is what marimo's accordion actually renders."""
    html = md.text if hasattr(md, 'text') else mo.md(md).text
    return mo.Html(f'<div class="{cls}">{html}</div>')


async def build_stamp() -> str:
    """Which build is this? The site build (tools/build_wasm_app.sh)
    writes public/version.json beside each page: 'build <commit> ·
    <time>'; an unstamped site gives ''; a development copy says so."""
    if not WASM_MODE:
        return 'development copy'
    try:
        import json

        from pyodide.http import pyfetch  # type: ignore[import-not-found]
        v = json.loads(await (await pyfetch(
            f'{mo.notebook_location()}/public/version.json')).string())
        return f"build {v['build']} · {v['built_at']}"
    except Exception:  # noqa: BLE001 — an unstamped site shows nothing
        return ''


async def prose(name: str) -> str:
    """A section's text — its title, the blurb under it, and its
    introduction — from notebooks/text/<name>.md: plain Markdown files,
    editable without touching code. Under WASM the site build copies
    them to public/text/, fetched once into /wasm-data/text/ (the suite
    fetches all of them up front)."""
    if not WASM_MODE:
        return (REPO_DIR / 'notebooks' / 'text' / f'{name}.md').read_text()
    cached = Path('/wasm-data/text') / f'{name}.md'
    if not cached.exists():
        from pyodide.http import pyfetch  # type: ignore[import-not-found]
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(await (await pyfetch(
            f'{mo.notebook_location()}/public/text/{name}.md')).string())
    return cached.read_text()


def stamp_html(stamp: str):
    """The build stamp as the small gray line under an app's title, or
    None for none."""
    return (mo.md(f'<span style="font-size: 0.8em; color: #444">{stamp}</span>')
            if stamp else None)
