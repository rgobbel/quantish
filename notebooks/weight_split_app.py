"""Quantish Weight-split Explorer — what one quantish Fredkin gate does to a
weight: the four-way split at any measurement angle, for either sign,
as vectors and as numbers.

Run with:  marimo edit notebooks/weight_split_app.py   (or `marimo run` to serve)
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", css_file="css/double_slit_app.css")


@app.cell(hide_code=True)
async def initialization():
    import sys
    from pathlib import Path

    import marimo as mo

    # Under Pyodide (the WASM export) the quantish package and its
    # dependencies are installed from the bundled wheels; see the
    # quantish app's initialization for the full story.
    if sys.platform == 'emscripten':
        # dynamic import: a literal `import micropip` makes server-side
        # marimo install a mock micropip meta-path finder whose globals
        # die with the notebook session, breaking all later imports
        import importlib
        micropip = importlib.import_module('micropip')
        _base = str(mo.notebook_location())
        await micropip.install([
            f'{_base}/public/wheels/addict-2.4.0-py3-none-any.whl',
            f'{_base}/public/wheels/quantish-0.1.0-py3-none-any.whl',
        ], deps=False)
        await micropip.install(['sympy', 'scipy', 'networkx',
                                'pyyaml', 'anywidget'])

    _repo = Path(__file__).resolve().parents[1]
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    from quantish.apps.common import build_stamp, init_engine, stamp_html
    from quantish.apps.explorer import (
        EXPLANATION,
        chart_selection,
        explorer_controls,
        explorer_view,
    )

    init_engine()
    return (
        EXPLANATION,
        build_stamp,
        chart_selection,
        explorer_controls,
        explorer_view,
        mo,
        stamp_html,
    )


@app.cell(hide_code=True)
def _(EXPLANATION, mo):
    mo.md('# Weight-split Explorer\n\n'
          '<span style="font-size:0.85em">An interactive tool showing what '
          'happens to weights going through a quantish Fredkin gate</span>\n' + EXPLANATION)


@app.cell(hide_code=True)
async def _(build_stamp, stamp_html):
    # which build is this? (the site build writes public/version.json
    # beside the page; a development copy says so instead)
    stamp_html(await build_stamp())


@app.cell(hide_code=True)
def _(explorer_controls, mo):
    ws_controls = explorer_controls()
    # the chart's mouse selection, persisted across parameter changes
    # (the chart is rebuilt on every slider move and reseeded from here)
    ws_sel_get, ws_sel_set = mo.state(())
    mo.hstack(list(ws_controls.elements.values()), wrap=True)
    return ws_controls, ws_sel_get, ws_sel_set


@app.cell(hide_code=True)
def _(explorer_view, ws_controls, ws_sel_get):
    ws_native, ws_view = explorer_view(ws_controls.value, ws_sel_get())
    ws_view  # noqa: B018 — the cell's output
    return (ws_native,)


@app.cell(hide_code=True)
def _(chart_selection, ws_native, ws_sel_get, ws_sel_set):
    # a cell that sets state is never rerun by that state, so the
    # selection's keeper lives apart from the chart
    _sel = chart_selection(ws_native, ws_sel_get())
    if _sel is not None:
        ws_sel_set(_sel)


if __name__ == "__main__":
    app.run()
