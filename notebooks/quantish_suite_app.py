"""Quantish suite — every app on one page, in one kernel: the
Weight-split Explorer, the double-slit demo, the quantish app, the
network builder, and the decoherence lab as the sections of a single
notebook, so what one app produces the next one takes — a model built
in the builder opens in the quantish app and the lab; a gate clicked
in a run opens in the explorer.

Each section is one of the standalone notebooks embedded (App.embed)
in a cell of its own, so an interaction reruns that app alone; the
hand-offs between them ride mo.state. Which section shows is the
section row's choice (quantish.apps.suite_nav, also the page's URL
fragment #sec-lab), applied by CSS (css/suite.css): a switch touches
no cell, and any link to a section opens it.

Run with:  marimo run notebooks/quantish_suite_app.py
(css/quantish_suite_app.css is the two apps' stylesheets and
css/suite.css joined; tools/build_wasm_app.sh writes it, or: cat
css/quantish_app.css css/double_slit_app.css css/suite.css >
css/quantish_suite_app.css)
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Quantish Physics", css_file="css/quantish_suite_app.css")


@app.cell(hide_code=True)
async def initialization():
    import sys
    from pathlib import Path

    import marimo as mo

    # Under Pyodide (the WASM export) the quantish package and its
    # dependencies are installed from the bundled wheels, the model
    # library and the five notebooks fetched into the page's virtual
    # filesystem (the embedded notebooks' own install cells then find
    # everything in place).
    if sys.platform == 'emscripten':
        import importlib
        micropip = importlib.import_module('micropip')
        _base = str(mo.notebook_location())
        await micropip.install([
            f'{_base}/public/wheels/addict-2.4.0-py3-none-any.whl',
            f'{_base}/public/wheels/quantish-0.1.0-py3-none-any.whl',
        ], deps=False)
        await micropip.install(['sympy', 'scipy', 'networkx',
                                'pyyaml', 'anywidget'])
        import json as _json

        from pyodide.http import pyfetch
        _resp = await pyfetch(f'{_base}/public/models.json')
        for _rel, _text in _json.loads(await _resp.string()).items():
            _p = Path('/wasm-data/models') / _rel
            _p.parent.mkdir(parents=True, exist_ok=True)
            _p.write_text(_text)
        _nbdir = Path('/wasm-data/notebooks')
        _nbdir.mkdir(parents=True, exist_ok=True)
        for _name in ('weight_split_app', 'double_slit_app', 'quantish_app',
                      'network_builder_app', 'decoherence_app'):
            _resp = await pyfetch(f'{_base}/public/notebooks/{_name}.py')
            (_nbdir / f'{_name}.py').write_text(await _resp.string())
        _txdir = Path('/wasm-data/text')
        _txdir.mkdir(parents=True, exist_ok=True)
        for _name in ('home', 'explorer', 'double-slit', 'figures', 'builder', 'lab', 'qubits'):
            _resp = await pyfetch(f'{_base}/public/text/{_name}.md')
            (_txdir / f'{_name}.md').write_text(await _resp.string())
        _root = Path('/wasm-data')
    else:
        _root = Path(__file__).resolve().parents[1]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    from quantish.apps import common as _common
    _common.EMBEDDED = True   # the notebooks below run as sections of this one

    from notebooks.decoherence_app import app as dl_app
    from notebooks.double_slit_app import app as ds_app
    from notebooks.network_builder_app import app as nb_app
    from notebooks.quantish_app import app as qa_app
    from notebooks.weight_split_app import app as ws_app
    from quantish.apps.common import WASM_MODE, build_stamp, prose, stamp_html
    from quantish.apps.suite_nav import SectionNav

    # Under WASM an embedded app's runtime serves widget code as
    # virtual files the page cannot fetch (marimo 0.24: the embedded
    # runner asks for shared-memory virtual files); with virtual files
    # off it inlines the code as data URLs, as the page's own kernel
    # does — so the canvases and diagrams render
    if WASM_MODE:
        for _a in (nb_app, qa_app, ws_app, dl_app, ds_app):
            _a._get_kernel_runner()._runtime_context.virtual_files_supported = False

    def embedded_def(result, name):
        """One of an embedded notebook's globals, None when unset."""
        try:
            return result.defs[name]
        except (KeyError, AttributeError):
            return None

    def section(name, content):
        """An app's output as the section the URL fragment #sec-<name>
        shows (css/suite.css)."""
        return mo.Html(f'<div class="suite-sec suite-sec-{name}">{mo.as_html(content).text}</div>')

    return (
        build_stamp,
        dl_app,
        ds_app,
        embedded_def,
        mo,
        nb_app,
        prose,
        qa_app,
        section,
        SectionNav,
        stamp_html,
        ws_app,
    )


@app.cell(hide_code=True)
def _(SectionNav, mo):
    # the section row; `suite_nav.value['current']` is the section shown
    suite_nav = mo.ui.anywidget(SectionNav(sections=[
        ['home', 'Home'], ['explorer', 'Weight-split Explorer'],
        ['double-slit', 'Double-slit experiment'], ['quantish', 'Book figures'],
        ['builder', 'Network builder'], ['lab', 'Decoherence lab']]))
    suite_nav  # noqa: B018 — the cell's output
    return (suite_nav,)


@app.cell(hide_code=True)
def _(mo):
    # what passes between the sections: the model the builder last
    # sent, and the gate the quantish app last picked for the explorer
    suite_slot_get, suite_slot_set = mo.state(None)
    suite_seed_get, suite_seed_set = mo.state(None)
    return suite_seed_get, suite_seed_set, suite_slot_get, suite_slot_set


# the sections, in the order of the section row (marimo's outline
# panel lists their headings in cell order)
@app.cell(hide_code=True)
async def _(build_stamp, mo, prose, section, stamp_html):
    section('home', mo.vstack([mo.md(await prose('home')), stamp_html(await build_stamp())]))


@app.cell(hide_code=True)
async def _(section, suite_seed_get, ws_app):
    # the explorer, opening on the picked gate
    ws = await ws_app.embed(defs={'ws_seed_in': suite_seed_get()})
    section('explorer', ws.output)


@app.cell(hide_code=True)
async def _(ds_app, section):
    ds = await ds_app.embed()
    section('double-slit', ds.output)



@app.cell(hide_code=True)
async def _(embedded_def, qa_app, section, suite_seed_get, suite_seed_set, suite_slot_get):
    # the quantish app, opening on the sent model; a gate it picks
    # goes out through the seed state
    qa = await qa_app.embed(defs={'qa_suite': True, 'qa_model_in': suite_slot_get()})
    _seed = embedded_def(qa, 'qa_seed')
    if _seed is not None and _seed != suite_seed_get():
        suite_seed_set(_seed)
    section('quantish', qa.output)


@app.cell(hide_code=True)
async def _(embedded_def, nb_app, section, suite_slot_get, suite_slot_set):
    # the builder; a model it sends goes out through the slot state
    nb = await nb_app.embed(defs={'nb_suite': True})
    _sent = embedded_def(nb, 'nb_sent')
    if _sent is not None and _sent != suite_slot_get():
        suite_slot_set(_sent)
    section('builder', nb.output)


@app.cell(hide_code=True)
async def _(dl_app, section, suite_slot_get):
    # the lab, opening slot A on the sent model
    dl = await dl_app.embed(defs={'dl_model_in': suite_slot_get()})
    section('lab', dl.output)

if __name__ == "__main__":
    app.run()
