"""quantish/apps/explorer.py and FredkinGate.components: the
Weight-split Explorer's split, controls, and view without a notebook."""
import cmath
import html
import math

import pytest

import quantish.qnumber as qn
from quantish.apps import explorer
from quantish.gate import FredkinGate
from quantish.qnumber import CalcMode
from quantish.util import Sign


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


@pytest.mark.parametrize('mode', ['Float', 'Symbolic'])
@pytest.mark.parametrize('theta', [0, 30, 45, -60, 90])
@pytest.mark.parametrize('plus', [True, False])
def test_components_agree_with_the_gate_and_sum_to_w(mode, theta, plus):
    CalcMode.default(mode)
    w = 0.8 * cmath.exp(0.4j)
    parts = explorer.split_components(theta, w, plus)
    t = math.radians(theta)
    c, s = math.cos(t), math.sin(t)
    straight = [w * c * c, 1j * w * s * c]
    cross = [w * s * s, -1j * w * s * c]
    want = straight + cross if plus else cross[:1] + [-straight[1]] + straight[:1] + [-cross[1]]
    got = [parts[k] for k in ('c2a', 'c2b', 'c3a', 'c3b')]
    assert got == pytest.approx(want, abs=1e-9)
    assert sum(got) == pytest.approx(w, abs=1e-9)
    assert parts['c2'] + parts['c3'] == pytest.approx(w, abs=1e-9)
    # the engine's own split uses the same four values for a plus sign
    gate = FredkinGate('g', qn.qify(t))
    engine = [complex(qn.Complex(w) * v) for _, _, v in
              gate.switch_components('upper', Sign.plus, True)]
    assert engine == pytest.approx(straight + cross, abs=1e-9)


def test_polar_weight():
    assert explorer.polar_weight(1.0, 0) == pytest.approx(1)
    assert explorer.polar_weight(0.5, 90) == pytest.approx(0.5j)


def test_controls_default_and_seeded():
    ctl = explorer.explorer_controls()
    v = ctl.value
    assert v['theta'] == 30 and v['sign'] is True and v['wmag'] == 1.0 and v['wphase'] == 0
    assert list(v['components']) == explorer.COMPONENTS
    seeded = explorer.explorer_controls(
        {'theta_deg': 33.3, 'plus_sign': False, 'wmag': 0.707, 'wphase_deg': 200})
    v = seeded.value
    assert v['theta'] == 35 and v['sign'] is False
    assert v['wmag'] == pytest.approx(0.7) and v['wphase'] == 180


def test_view_and_selection():
    ctl = explorer.explorer_controls()
    values = {**ctl.value, 'components': ['c2', 'c3a']}
    native, view = explorer.explorer_view(values, selected=('c3a', 'c2b'))
    assert native.widget.data['order'] == ['c2', 'c3a']
    assert native.widget.selected == ['c3a']          # c2b is not shown
    text = html.unescape(view.text)
    assert 'c_{3a} &=' in text and 'c_{2b}' not in text.split('begin{align*}')[1]
    assert explorer.chart_selection(native, ('c3a',)) is None
    native.widget.selected = ['c2']
    assert explorer.chart_selection(native, ('c3a',)) == ('c2',)
