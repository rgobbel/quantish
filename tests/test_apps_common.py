"""quantish/apps/common.py and display.py's weight formatting: the
pieces the marimo notebooks share, exercised without a notebook."""
from pathlib import Path

import pytest

import quantish.qnumber as qn
from quantish.apps import common
from quantish.display import (
    latex_weight,
    math_prob,
    math_weight,
    md_table,
    phase_deg,
)
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation

MODELS = Path(__file__).resolve().parents[1] / 'models'


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def test_library_layout():
    colls = common.collections(MODELS)
    assert {'gr2006', 'gr2026', 'extras', 'decoherence'} <= set(colls)
    assert 'HIDEME' not in colls
    files = common.model_files(MODELS)
    assert 'gr2026/fig4.17.yaml' in files
    assert not any(k.endswith(('defaults.yaml', 'schema.yaml')) for k in files)
    assert list(files) == sorted(files)
    # a missing library is empty, not an error (the builder's None case)
    assert common.collections(MODELS / 'nope') == []
    assert common.model_files(MODELS / 'nope') == {}


def test_load_config_merges_defaults_under_the_model():
    cfg, raw = common.load_config(MODELS / 'gr2026' / 'fig4.04.yaml', MODELS)
    assert raw['title'] == cfg.title
    # the defaults' standard variables stay available underneath
    assert {'zero', 'one'} <= set(cfg.variables)
    for k, v in (raw.get('variables') or {}).items():
        assert cfg.variables[k] == v
    assert cfg.loglevel == 'warning'
    # and the merged config runs
    sim = Simulation(cfg)
    sim.run()
    total = sum(float(pt.probability) for pt in sim.result_space.index.values())
    assert abs(total - 1) < 1e-9


def test_vars_text_round_trip():
    vs = {'theta': 'pi/4', 'n': 3, 'w': 0.5}
    text = common.vars_text(vs)
    assert text.splitlines() == ["theta: 'pi/4'", 'n: 3', 'w: 0.5']
    parsed, err = common.parse_vars(text)
    assert err is None and parsed == vs
    assert common.vars_text(None) == ''
    assert common.parse_vars('   ') == ({}, None)
    parsed, err = common.parse_vars('- a list')
    assert parsed == {} and err and 'not parseable' in err


def test_remember_in_and_switch_off_boxes():
    memory = {}
    common.remember_in(memory, 'k', bool)(0)
    assert memory == {'k': False}
    memory = {'g:g2': False}
    boxes = common.switch_off_boxes(memory, ['g1', 'g2'], ['p1'])
    assert list(boxes.elements) == ['g:g1', 'g:g2', 'p:p1']
    assert boxes.elements['g:g2'].value is False
    assert boxes.elements['g:g1'].value is True


def test_weight_formatting_float():
    assert latex_weight(0.5 + 0.25j) == '0.500+0.250i'
    assert latex_weight(0) == '0.000+0.000i'
    assert latex_weight(-1e-15 - 0.5j, prec=2) == '0.00-0.50i'
    assert math_weight(1) == '$1.000+0.000i$'
    assert math_prob(0.5625) == '$0.5625$'
    assert phase_deg(1j) == pytest.approx(90.0)
    assert phase_deg(-1) == pytest.approx(180.0)


def test_weight_formatting_symbolic():
    CalcMode.default('Symbolic')
    w = qn.qify('sqrt(2)/2')
    assert latex_weight(w) == qn.latex(w)
    assert math_weight(w).startswith('$') and ' ' not in math_weight(w)[:2]
    assert math_prob(qn.qify('9/16')) == '$\\frac{9}{16}$'
    # too long for the exact form: the numeric pair
    assert latex_weight(w, max_len=1) == '0.707+0.000i'


def test_md_table_escapes_pipes():
    t = md_table(['a', 'b'], [['x|y', 1]])
    assert t.startswith('\n| a | b |\n|---|---|\n')
    assert r'x\|y' in t
