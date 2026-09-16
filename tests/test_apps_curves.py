"""quantish/apps/curves.py: screen curves pushed into a panel at the
right grain, the lab's grouped curves, and the demo's per-condition
curves."""
from types import SimpleNamespace

import pytest

from quantish.apps import curves
from quantish.qnumber import CalcMode


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield


def test_push_curves_rebuilds_only_on_a_new_grain():
    panel = SimpleNamespace(curves=None, data=None)
    xs, ys = [0, 1, 2], [0.1, 0.2, 0.3]
    grain = curves.push_curves(panel, xs, ys, grain=None, title='t', width=10, hits=[(1, 2)])
    assert grain == 3
    assert panel.curves == {'x': xs, 'y': ys}
    assert panel.data == {'title': 't', 'curve': panel.curves, 'width': 10, 'hits': [[1, 2]]}
    panel.data = 'untouched'
    grain = curves.push_curves(panel, xs, [0.3, 0.2, 0.1], [('+p', ys)],
                               grain=grain, title='t', width=10, hits=[])
    assert grain == 3 and panel.data == 'untouched'
    assert panel.curves['parts'] == [{'name': '+p', 'y': ys}]
    grain = curves.push_curves(panel, xs + [3], ys + [0.4], grain=grain,
                               title='t', width=10, hits=[])
    assert grain == 4 and panel.data['hits'] == []


def test_grouped_curves():
    total, parts = curves.grouped_curves({'all': [1, 2]}, 'p2')
    assert total == [1, 2] and parts is None
    total, parts = curves.grouped_curves({'+': [1, 2], '−': [3, 4]}, 'p2')
    assert total == [4, 6]
    assert parts == [('+p2', [1, 2]), ('−p2', [3, 4])]
    _, parts = curves.grouped_curves({'g1.upper': [1]}, 'p2')
    assert parts == [('g1.upper', [1])]


def test_double_slit_curves_cover_every_condition():
    main = ('both', 'slit2', 'slit1', 'observed')
    settings = {'n': 9, 'fringes': 3, 'main_angles': {},
                'theta_pre': 0.3, 'theta_erase': 0.5}
    xs, cs, parts = curves.double_slit_curves(settings, main)
    assert set(cs) == set(main) | {'tunable', 'eraser'}
    assert all(len(c) == len(xs) == 9 for c in cs.values())
    plus, minus = (ys for _, ys in parts['eraser'])
    for a, b, t in zip(plus, minus, cs['eraser']):
        assert a + b == pytest.approx(t)
