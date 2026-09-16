"""Quantish suite — every app on one page, in one kernel: the
Weight-split Explorer, the double-slit demo, the quantish app, the
network builder, and the decoherence lab as the tabs of a single
notebook, so what one app produces the next one takes — a model built
in the builder opens in the quantish app and the lab; a gate clicked
in a run opens in the explorer.

Each page is one of the standalone notebooks embedded (App.embed):
the notebooks stay the sources, this file only arranges them and
passes the hand-offs between them as definitions.

Run with:  marimo run notebooks/quantish_suite_app.py
(css/quantish_suite_app.css is the two apps' stylesheets joined;
tools/build_wasm_app.sh writes it, or: cat css/quantish_app.css
css/double_slit_app.css > css/quantish_suite_app.css)
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", css_file="css/quantish_suite_app.css")


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
        _root = Path('/wasm-data')
    else:
        _root = Path(__file__).resolve().parents[1]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    from quantish.apps import common as _common
    _common.EMBEDDED = True   # the notebooks below run as pages of this one

    from notebooks.decoherence_app import app as dl_app
    from notebooks.double_slit_app import app as ds_app
    from notebooks.network_builder_app import app as nb_app
    from notebooks.quantish_app import app as qa_app
    from notebooks.weight_split_app import app as ws_app
    from quantish.apps.common import WASM_MODE, build_stamp, remember_in, stamp_html
    return (
        WASM_MODE,
        build_stamp,
        dl_app,
        ds_app,
        mo,
        nb_app,
        qa_app,
        remember_in,
        stamp_html,
        ws_app,
    )


@app.cell(hide_code=True)
async def _(build_stamp, stamp_html):
    # which build is this? (the site build writes public/version.json
    # beside the page; a development copy says so instead)
    stamp_html(await build_stamp())


@app.cell(hide_code=True)
def _():
    # the tab last chosen, so the tab strip — rebuilt whenever an app
    # reacts — opens where it was (a plain dict, as the apps' pickers
    # remember themselves)
    suite_memory = {'tab': 'Home'}
    return (suite_memory,)


@app.cell(hide_code=True)
def _(mo):
    suite_home = mo.md("""
    # Quantish Physics

    Simulations of the "quantish" universe from Chapter 4 of *Good and Real*
    (Gary L. Drescher), as one application. The tabs:

    - **Weight-split Explorer** — what one quantish Fredkin gate does to a
      weight: the four-way split at any measurement angle, for either sign.
    - **Double-slit experiment** — the classic experiment in the quantish
      framework: fire particles and watch the fringes build up.
    - **Quantish app** — the chapter's figures as live circuits: run one and
      follow the weights through the gates. After a run, click a gate's frame
      to open its split in the explorer.
    - **Network builder** — build a circuit from scratch or from any model,
      run it, and *send* it: the quantish app and the decoherence lab open it.
    - **Decoherence lab** — the double-slit family side by side, angles as
      sliders, screens and virtual screens.

    Every tab keeps its state while you visit the others.
    """)
    return (suite_home,)


@app.cell(hide_code=True)
async def _(
    WASM_MODE,
    dl_app,
    ds_app,
    mo,
    nb_app,
    qa_app,
    remember_in,
    suite_home,
    suite_memory,
    ws_app,
):
    # The apps, embedded in this kernel, and the hand-offs between them
    # as definitions: the builder's last sent model goes to the quantish
    # app and the lab, the quantish app's picked gate to the explorer.
    # Any interaction in an embedded app reruns this cell; an app whose
    # inputs did not change comes back from its cache.
    def _def(result, name):
        try:
            return result.defs[name]
        except (KeyError, AttributeError):
            return None

    # Under WASM an embedded app's runtime serves widget code as
    # virtual files the page cannot fetch (marimo 0.24: the embedded
    # runner asks for shared-memory virtual files); with virtual files
    # off it inlines the code as data URLs, as the page's own kernel
    # does — so the canvases and diagrams render
    if WASM_MODE:
        for _a in (nb_app, qa_app, ws_app, dl_app, ds_app):
            _a._get_kernel_runner()._runtime_context.virtual_files_supported = False

    nb = await nb_app.embed(defs={'nb_suite': True})
    _slot = _def(nb, 'nb_sent')
    qa = await qa_app.embed(defs={'qa_suite': True, 'qa_model_in': _slot})
    _seed = _def(qa, 'qa_seed')
    ws = await ws_app.embed(defs={'ws_seed_in': _seed})
    dl = await dl_app.embed(defs={'dl_model_in': _slot})
    ds = await ds_app.embed()
    _tabs = {
        'Home': suite_home,
        'Weight-split Explorer': ws.output,
        'Double-slit experiment': ds.output,
        'Quantish app': qa.output,
        'Network builder': nb.output,
        'Decoherence lab': dl.output,
    }
    mo.ui.tabs(_tabs, value=suite_memory.get('tab') if suite_memory.get('tab') in _tabs
               else 'Home', on_change=remember_in(suite_memory, 'tab'))


if __name__ == "__main__":
    app.run()
