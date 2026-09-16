"""quantish/apps/sweep_ui.py: the shared sweep editor's declaration,
run, and result formatting, exercised without a notebook."""
from pathlib import Path

import pytest

from quantish.apps import common, sweep_ui
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation
from quantish.apps.common import load_config

MODELS = Path(__file__).resolve().parents[1] / 'models'


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


@pytest.fixture
def tunable():
    cfg, _ = load_config(MODELS / 'decoherence' / 'double_slit_tunable.yaml', MODELS)
    return Simulation(cfg)


def test_editor_spec_shapes():
    base = {'variable': 'phi', 'from': '0', 'to': '2*pi', 'points': 5,
            'particle': 'p1', 'at': 'S', 'sort': sweep_ui.UNSORTED, 'coordinate': 'sign'}
    assert sweep_ui.editor_spec(base) == {
        'variable': 'phi', 'from': '0', 'to': '2*pi', 'points': 5,
        'observe': {'particle': 'p1', 'at': 'S'}}
    sorted_ = sweep_ui.editor_spec({**base, 'sort': 'p2', 'coordinate': 'both'})
    assert sorted_['group_by'] == {'particle': 'p2', 'coordinate': 'both'}
    assert sweep_ui.editor_spec({**base, 'on': False}) is None
    assert sweep_ui.editor_spec({**base, 'variable': None}) is None


def test_controls_seed_from_declaration_then_memory(tunable):
    decl = sweep_ui.declared_sweep(tunable)
    assert decl['variable'] and decl['observe']['particle']
    ed = sweep_ui.sweep_controls(tunable.qvars, tunable.particles, tunable.gates, decl)
    v = ed.value
    assert v['variable'] == decl['variable']
    assert v['at'] == decl['observe']['at']
    assert 'on' not in v
    memory = {'points': 7, 'on': False}
    ed = sweep_ui.sweep_controls(tunable.qvars, tunable.particles, tunable.gates, decl,
                                 memory=memory, declare_box=True)
    assert ed.value['points'] == 7 and ed.value['on'] is False
    # a remembered value the options no longer have falls back to the first
    ed = sweep_ui.sweep_controls(tunable.qvars, tunable.particles, tunable.gates, decl,
                                 memory={'variable': 'gone'})
    assert ed.value['variable'] == common.settable(tunable.qvars)[0]


def test_constants_are_no_sweep_candidates(tunable):
    assert {'zero', 'one', 'eye'} <= common.CONSTANTS <= set(tunable.qvars)
    ed = sweep_ui.sweep_controls(tunable.qvars, tunable.particles, tunable.gates)
    options = ed.elements['variable'].options
    assert not common.CONSTANTS & set(options)
    assert set(options) == set(common.settable(tunable.qvars))
    # a model with only the constants has nothing to sweep
    ed = sweep_ui.sweep_controls(common.CONSTANTS, tunable.particles, tunable.gates)
    assert ed.value['variable'] is None


def test_checked_spec_reports_problems(tunable):
    decl = sweep_ui.declared_sweep(tunable)
    values = {'variable': decl['variable'], 'from': '0', 'to': 'pi', 'points': 3,
              'particle': decl['observe']['particle'], 'at': decl['observe']['at'],
              'sort': sweep_ui.UNSORTED, 'coordinate': 'sign'}
    spec, problem = sweep_ui.checked_spec(tunable, values)
    assert problem is None and spec['points'] == 3
    _, problem = sweep_ui.checked_spec(tunable, {**values, 'at': 'no_such_gate'})
    assert problem
    _, problem = sweep_ui.checked_spec(tunable, {**values, 'variable': None})
    assert 'no variables' in problem


def test_run_series_and_table(tunable):
    spec = sweep_ui.declared_sweep(tunable)
    res = sweep_ui.sweep_run(tunable, spec, points=3)
    xs, names, series = sweep_ui.sweep_series(res, spec, degrees=True)
    assert len(xs) == 3 and xs[0] == pytest.approx(0)
    assert all(len(s['y']) == 3 for s in series)
    xr, _, _ = sweep_ui.sweep_series(res, spec, degrees=False)
    assert xr[-1] == pytest.approx(xs[-1] * 3.141592653589793 / 180)
    table = sweep_ui.sweep_table(res, spec)
    assert table.count('\n') >= 4 and spec['variable'] in table.strip().splitlines()[0]
    if spec.get('group_by'):
        assert series[-1]['name'] == 'total'
        assert 'total' in table.splitlines()[0]
        for i in range(3):
            assert sum(s['y'][i] for s in series[:-1]) == pytest.approx(series[-1]['y'][i])
    chart = sweep_ui.sweep_chart(res, spec)
    assert chart.value is not None or chart is not None
