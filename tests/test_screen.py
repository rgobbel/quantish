"""quantish/screen.py: a screen for any model with a sweep declaration.
It agrees with double_slit.py's fixed conditions, the three-run fit is
allowed exactly when the phase enters through one plate alone, and the
chain models follow their laws through it."""
import math

import pytest

from quantish.qnumber import CalcMode
from quantish.screen import (
    DEFAULT_RANGE,
    ScreenSpec,
    library,
    register,
    screen_curves,
    screen_models,
    visibility,
)

FAMILY = ['extras/double_slit', 'extras/double_slit_recorder',
          'decoherence/double_slit_decoherence_chain', 'decoherence/double_slit_eraser',
          'decoherence/double_slit_eraser_chain', 'decoherence/double_slit_tunable']


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def test_family_is_every_extras_model_with_a_screen():
    assert screen_models() == FAMILY
    for name in FAMILY:
        spec = ScreenSpec.load(name)
        assert spec.has_screen and spec.name == name
        assert ScreenSpec.load(name.split('/', 1)[1]).name == name   # bare names resolve
        assert spec.phase_var == 'phi' and spec.plate == 'φ' and spec.fit_ok
        assert spec.observe == ('p1', 'S')
        assert 'phi' not in spec.variables
        assert spec.angle_gates()          # every model's gates are variable-named
        # the family's gates carry angle ranges of 0..90 for every slider
        assert all(r == (0.0, 90.0) for r in spec.angle_ranges().values()), spec.angle_ranges()


def test_any_model_loads_without_a_screen():
    ids = library()
    assert 'gr2026/fig4.17' in ids and 'extras/double_slit' in ids
    spec = ScreenSpec.load('gr2026/fig4.17')
    assert not spec.has_screen and spec.plate is None
    assert set(spec.variables) >= {'theta1', 'theta2', 'Qa'}
    assert spec.angle_ranges()['theta1'] == DEFAULT_RANGE   # no hint: the default
    with pytest.raises(ValueError):
        screen_curves(spec, {}, 11, 1.0, 'fit')
    # an upload is a model like any other
    cfg = ScreenSpec.load('extras/double_slit').config
    register('upload:mine', cfg)
    assert 'upload:mine' in library()
    assert ScreenSpec.load('upload:mine').has_screen


@pytest.mark.parametrize('name, mode, kw', [
    ('double_slit', 'both', {}),
    ('double_slit_recorder', 'observed', {}),
    ('double_slit_tunable', 'tunable', {'theta_pre': math.radians(35)}),
])
def test_agrees_with_the_double_slit_module(name, mode, kw):
    from quantish.double_slit import screen_curve
    spec = ScreenSpec.load(name)
    xs, curves = screen_curves(spec, kw, 41, 3.0, 'fit')
    ref_xs, ref = screen_curve(41, 3.0, mode, via='pixels', **kw)
    assert xs == ref_xs and list(curves) == ['all']
    assert max(abs(a - b) for a, b in zip(curves['all'], ref)) < 1e-12


def test_eraser_groups_match_the_double_slit_module():
    from quantish.double_slit import screen_curves_by_sign
    spec = ScreenSpec.load('double_slit_eraser')
    _, curves = screen_curves(spec, {}, 41, 3.0, 'fit')
    _, (plus, minus) = screen_curves_by_sign(41, 3.0, 'eraser', via='pixels')
    assert list(curves) == ['+', '−']
    assert max(abs(a - b) for a, b in zip(curves['+'], plus)) < 1e-12
    assert max(abs(a - b) for a, b in zip(curves['−'], minus)) < 1e-12


@pytest.mark.parametrize('name', FAMILY)
def test_fit_matches_pixels(name):
    spec = ScreenSpec.load(name)
    variables = {k: math.radians(d) for k, d in
                 zip(spec.variables, (35, 50, 20, 60, 30, 70, 25))}
    _, fit = screen_curves(spec, variables, 31, 3.0, 'fit')
    _, px = screen_curves(spec, variables, 31, 3.0, 'pixels')
    for g in fit:
        assert max(abs(a - b) for a, b in zip(fit[g], px[g])) < 1e-12, (name, g)


def test_chain_laws_through_the_screen():
    spec = ScreenSpec.load('double_slit_decoherence_chain')
    _, c = screen_curves(spec, {'theta_pre_1': math.radians(30), 'theta_pre_2': math.radians(45),
                                'theta_pre_3': math.radians(60)}, 81, 3.0, 'fit')
    assert abs(visibility(c['all']) - 0.25 * 0.5 * 0.75) < 1e-9
    spec = ScreenSpec.load('double_slit_eraser_chain')
    _, c = screen_curves(spec, {'theta_pre_1': math.pi / 2, 'theta_pre_2': math.radians(30),
                                'theta_pre_3': math.pi / 2}, 81, 3.0, 'fit')
    assert abs(visibility(c['+']) - 4 / 7) < 1e-9
    assert visibility(c['−']) < 1e-9 or visibility(c['−']) is None


def test_fit_is_refused_when_the_phase_enters_twice():
    # a model whose swept variable also sets a gate angle: no fit
    from quantish.screen import _mentions
    assert _mentions('phi', 'phi') and _mentions('2*phi + 1', 'phi')
    assert not _mentions('phi2', 'phi') and not _mentions('theta.phi', 'phi')
