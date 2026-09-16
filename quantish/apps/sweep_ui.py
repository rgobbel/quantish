"""The sweep editor the quantish app and the network builder share:
which variable to sweep, over what range and how many points, which
particle's arrival at which gate to record, and an optional sort —
the widgets (built here, bound to a global by the cell), the editor's
values as a sweep declaration, the run, and a result as a line chart
and a values table. Engine in `quantish.sweep`.
"""
from __future__ import annotations

import math

import marimo as mo

import quantish.qnumber as qn
from quantish.apps.common import remember_in, settable
from quantish.builder_widget import LinePlotWidget
from quantish.display import md_table, sym_or_float
from quantish.sweep import check_sweep, run_sweep, sweep_spec, sweep_values

__all__ = [
    'COORDINATES', 'PALETTE', 'UNSORTED', 'checked_spec', 'declared_sweep',
    'editor_rows', 'editor_spec', 'sweep_chart', 'sweep_controls',
    'sweep_run', 'sweep_series', 'sweep_table',
]

UNSORTED = '(unsorted)'
COORDINATES = ('sign', 'position', 'both')
PALETTE = ['#4c78a8', '#f58518', '#54a24b', '#e45756', '#72b7b2',
           '#b279a2', '#ff9da6', '#9d755d']
TOTAL_COLOR = '#333'


def declared_sweep(sim) -> dict:
    """The loaded model's own sweep section, or {} — a broken
    declaration also starts the editor from its defaults."""
    try:
        return dict(sweep_spec(sim) or {})
    except ValueError:
        return {}


def sweep_controls(variables, particles, gates, decl=None, memory=None,
                   declare_box=False) -> mo.ui.dictionary:
    """The editor's widgets, seeded from a sweep declaration `decl`
    (a model's sweep section) and, over that, from `memory` — a plain
    dict the widgets keep their values in, so a rebuild (the builder
    remakes them whenever the variables or the canvas change) opens
    where the user left them. The defaults' constants (zero, one, eye)
    are no candidates. `declare_box` adds the builder's 'declare a
    sweep' checkbox ('on'). The caller binds the dictionary to a
    global."""
    decl = dict(decl or {})
    obs, grp = dict(decl.get('observe') or {}), dict(decl.get('group_by') or {})
    memory = memory if memory is not None else {}
    variables, particles, gates = settable(variables), list(particles), list(gates)

    def seed(key, default):
        return memory.get(key, default)

    def pick(key, options, default, label):
        value = seed(key, default)
        return mo.ui.dropdown(
            options=options,
            value=value if value in options else (options[0] if options else None),
            label=label, on_change=remember_in(memory, key))

    def text(key, default, label):
        return mo.ui.text(value=str(seed(key, default)), label=label,
                          on_change=remember_in(memory, key))

    elements = {}
    if declare_box:
        elements['on'] = mo.ui.checkbox(value=bool(seed('on', bool(decl))),
                                        label='declare a sweep',
                                        on_change=remember_in(memory, 'on'))
    elements.update({
        'variable': pick('variable', variables, decl.get('variable'), 'variable'),
        'from': text('from', decl.get('from', 0), 'from'),
        'to': text('to', decl.get('to', '2*pi'), 'to'),
        'points': mo.ui.number(2, 401, value=int(seed('points', decl.get('points', 41))),
                               label='points', on_change=remember_in(memory, 'points')),
        'particle': pick('particle', particles, obs.get('particle'), 'record: particle'),
        # the last gate, where a screen usually sits, when the model says nothing
        'at': pick('at', gates, obs.get('at') or (gates[-1] if gates else None),
                   'arriving at'),
        'sort': pick('sort', [UNSORTED, *particles], grp.get('particle', UNSORTED),
                     'sort by'),
        'coordinate': pick('coordinate', list(COORDINATES),
                           grp.get('coordinate', 'sign'), 'coordinate'),
    })
    return mo.ui.dictionary(elements)


def editor_rows(editor: mo.ui.dictionary) -> list:
    """The editor laid out as its two rows: the range, then what to
    record."""
    e = editor.elements
    return [mo.hstack([e['variable'], e['from'], e['to'], e['points']],
                      justify='start', wrap=True, gap=1.5, align='end'),
            mo.hstack([e['particle'], e['at'], e['sort'], e['coordinate']],
                      justify='start', wrap=True, gap=1.5, align='end')]


def editor_spec(values: dict) -> dict | None:
    """The editor's values as the sweep as a model would declare it
    (unchecked against any model), or None when there is nothing to
    sweep: no variable, or the declare box unchecked."""
    if not values.get('on', True) or not values.get('variable'):
        return None
    spec = {'variable': values['variable'], 'from': values['from'],
            'to': values['to'], 'points': int(values['points']),
            'observe': {'particle': values['particle'], 'at': values['at']}}
    if values.get('sort') and values['sort'] != UNSORTED:
        spec['group_by'] = {'particle': values['sort'],
                            'coordinate': values['coordinate']}
    return spec


def checked_spec(sim, values: dict) -> tuple[dict | None, str | None]:
    """The editor's sweep validated against the loaded model: (the
    checked spec, None), or (None, why not)."""
    raw = editor_spec(values)
    if raw is None:
        return None, 'the model has no variables to sweep'
    try:
        return check_sweep(sim, raw), None
    except ValueError as exc:
        return None, str(exc)


def sweep_run(sim, spec: dict, points: int | None = None,
              inert=(), absent=()) -> dict:
    """The sweep run: one engine run per point over the range, the
    switched-off gates and particles applying to every point."""
    return run_sweep(sim, spec, values=sweep_values(spec, points),
                     inert=tuple(inert), absent=tuple(absent))


def sweep_series(res: dict, spec: dict, degrees: bool = True):
    """A sweep result as plot data: (xs as floats, in degrees or
    radians; the series' display names by label, sign first ('+p2');
    the series list for LinePlotWidget, the dashed total last when the
    result is sorted)."""
    xs = [math.degrees(qn.to_float(x)) if degrees else qn.to_float(x)
          for x in res['x']]
    grp = spec.get('group_by')
    names = {lab: f"{lab}{grp['particle']}" if grp else lab
             for lab in res['series']}
    series = [{'name': names[lab], 'x': xs,
               'y': [qn.to_float(v) for v in ys],
               'color': PALETTE[i % len(PALETTE)]}
              for i, (lab, ys) in enumerate(res['series'].items())]
    if grp:
        series.append({'name': 'total', 'x': xs,
                       'y': [qn.to_float(v) for v in res['total']],
                       'color': TOTAL_COLOR, 'dash': '6 4'})
    return xs, names, series


def sweep_chart(res: dict, spec: dict, degrees: bool = True,
                width: int = 900, height: int = 220):
    """The result's line chart, a bound LinePlotWidget."""
    xs, _, series = sweep_series(res, spec, degrees)
    obs = spec['observe']
    return mo.ui.anywidget(LinePlotWidget(data={
        'series': series, 'xdomain': [min(xs), max(xs)],
        'xlabel': f"{spec['variable']} ({'degrees' if degrees else 'radians'})",
        'ylabel': f"P({obs['particle']} at {obs['at']})",
        'width': width, 'height': height}))


def sweep_table(res: dict, spec: dict, degrees: bool = True) -> str:
    """The result's values as a Markdown table: the swept value, each
    series, and the total when sorted — exact in Symbolic mode where
    short."""
    xs, names, _ = sweep_series(res, spec, degrees)
    grp = spec.get('group_by')

    def cell(v):
        return sym_or_float(v, f'{qn.to_float(v):.4f}')

    headers = [spec['variable']] + [names[lab] for lab in res['series']] \
        + (['total'] if grp else [])
    rows = []
    for i, x in enumerate(xs):
        cells = [f'{x:.2f}'] + [cell(res['series'][lab][i]) for lab in res['series']]
        if grp:
            cells.append(cell(res['total'][i]))
        rows.append(cells)
    return md_table(headers, rows)
