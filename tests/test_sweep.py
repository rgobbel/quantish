"""Model-declared sweeps (quantish/sweep.py): the eraser's declaration
reproduces the complementary-fringe law, exactly in Symbolic mode; a
model without a sweep declares none; a bad declaration is rejected."""
import math
from pathlib import Path

import pytest
import yaml
from addict import Dict as Addict

from quantish.qnumber import CalcMode, to_float
from quantish.simulation import Simulation
from quantish.sweep import run_sweep, sweep_spec, sweep_values

MODELS = Path(__file__).resolve().parents[1] / 'models'


def load(rel: str, **overrides) -> Simulation:
    with open(MODELS / f'{rel}.yaml') as f:
        cfg = yaml.safe_load(f)
    cfg['loglevel'] = 'warning'
    cfg.update(overrides)
    return Simulation(Addict(cfg))


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def test_eraser_sweep_matches_the_law():
    sim = load('decoherence/double_slit_eraser')
    spec = sweep_spec(sim)
    assert spec['variable'] == 'phi' and spec['points'] == 41
    assert spec['group_by'] == {'particle': 'p2', 'coordinate': 'sign'}
    res = run_sweep(sim, spec, values=sweep_values(spec, 9))
    assert list(res['series']) == ['+', '−']
    for x, plus, minus, total in zip(res['x'], res['series']['+'],
                                     res['series']['−'], res['total']):
        phi = to_float(x)
        assert abs(to_float(plus) - 0.5 * math.cos(phi / 2) ** 2) < 1e-9
        assert abs(to_float(minus) - 0.5 * math.sin(phi / 2) ** 2) < 1e-9
        assert abs(to_float(total) - 0.5) < 1e-9
    assert abs(to_float(res['x'][-1]) - 2 * math.pi) < 1e-12


def test_symbolic_sweep_stays_exact():
    import sympy
    CalcMode.default('Symbolic')
    sim = load('decoherence/double_slit_eraser')
    spec = sweep_spec(sim)
    values = sweep_values(spec, 5)          # 0, π/2, π, 3π/2, 2π
    assert [v.v for v in values] == [0, sympy.pi / 2, sympy.pi,
                                     3 * sympy.pi / 2, 2 * sympy.pi]
    res = run_sweep(sim, spec, values=values)
    plus = [sympy.nsimplify(v.v) for v in res['series']['+']]
    assert plus == [sympy.Rational(1, 2), sympy.Rational(1, 4), 0,
                    sympy.Rational(1, 4), sympy.Rational(1, 2)]


def test_ungrouped_sweep_and_no_sweep():
    sim = load('extras/double_slit')
    spec = sweep_spec(sim)
    assert 'group_by' not in spec
    res = run_sweep(sim, spec, values=sweep_values(spec, 5))
    assert list(res['series']) == ['S']
    assert [round(to_float(v), 9) for v in res['series']['S']] == \
        [1.0, 0.5, 0.0, 0.5, 1.0]
    assert sweep_spec(load('gr2026/fig4.13')) is None


def test_bad_declarations_are_rejected():
    base = {'variable': 'phi', 'to': '2*pi',
            'observe': {'particle': 'p1', 'at': 'S'}}
    with pytest.raises(ValueError, match='variable'):
        sweep_spec(load('extras/double_slit',
                        sweep={**base, 'variable': 'nope'}))
    with pytest.raises(ValueError, match='particle'):
        sweep_spec(load('extras/double_slit',
                        sweep={**base, 'observe': {'particle': 'p9', 'at': 'S'}}))
    with pytest.raises(ValueError, match='gate'):
        sweep_spec(load('extras/double_slit',
                        sweep={**base, 'observe': {'particle': 'p1', 'at': 'Q'}}))
    with pytest.raises(ValueError, match='coordinate'):
        sweep_spec(load('decoherence/double_slit_eraser',
                        sweep={**base, 'group_by': {'particle': 'p2',
                                                    'coordinate': 'hue'}}))
    with pytest.raises(ValueError):
        sweep_values({'from': 0, 'to': 1, 'points': 1})


def test_check_sweep_validates_a_sweep_made_in_an_app():
    from quantish.screen import ScreenSpec
    from quantish.simulation import Simulation
    from quantish.sweep import check_sweep
    sim = Simulation(ScreenSpec.load('extras/double_slit_recorder').config_with({}))
    spec = check_sweep(sim, {'variable': 'phi', 'to': '2*pi',
                             'observe': {'particle': 'p1', 'at': 'S'},
                             'group_by': {'particle': 'p2'}})
    assert spec['from'] == 0 and spec['points'] == 41 and spec['group_by']['coordinate'] == 'sign'
    for bad, msg in ((dict(spec, variable='nope'), 'not one of the model'),
                     (dict(spec, observe={'particle': 'px', 'at': 'S'}), 'does not declare'),
                     (dict(spec, observe={'particle': 'p1', 'at': 'nowhere'}), 'not a gate'),
                     (dict(spec, group_by={'particle': 'p2', 'coordinate': 'color'}), 'coordinate')):
        with pytest.raises(ValueError, match=msg):
            check_sweep(sim, bad)


def test_run_sweep_honors_switched_off_gates_and_particles():
    from quantish.screen import ScreenSpec
    from quantish.simulation import Simulation
    from quantish.sweep import run_sweep, sweep_spec, sweep_values
    sim = Simulation(ScreenSpec.load('extras/double_slit_recorder').config_with({}))
    spec = sweep_spec(sim)
    values = sweep_values(spec, 5)
    flat = run_sweep(sim, spec, values)                       # the record: no fringes
    assert max(map(to_float, flat['total'])) - min(map(to_float, flat['total'])) < 1e-9
    fringes = run_sweep(sim, spec, values, inert=('g_obs',))  # the recorder off
    assert max(map(to_float, fringes['total'])) > 0.99
    gone = run_sweep(sim, spec, values, absent=('p2',))       # the recorder's particle off
    assert max(map(to_float, gone['total'])) > 0.99
    assert all(v == 0 for v in map(to_float, run_sweep(sim, spec, values, absent=('p1',))['total']))
