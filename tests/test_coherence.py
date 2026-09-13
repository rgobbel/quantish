"""quantish/coherence.py: the which-way coherence per stage is the
fringe visibility the screen would show if the paths were merged right
after that stage. Checked against the family's laws — a recorder's
sin²θ, the chain's running product, the eraser's complementary ±1, and
the eraser chain's V± closed forms — and against the screen itself."""
import math

import pytest

from quantish.coherence import path_coherence, signed_visibility
from quantish.qnumber import CalcMode
from quantish.screen import (
    _CACHE,
    ScreenSpec,
    register,
    screen_curves,
    screen_models,
    visibility,
)
from quantish.simulation import Simulation

TOL = 1e-9


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def radians(**degrees):
    return {k: math.radians(v) for k, v in degrees.items()}


def run(model, variables, erase_after=None):
    """The model run at its own phase; with erase_after, g_erase moved
    out of the sort stage into its own stage after that declared stage
    (delayed choice: the numbers do not depend on where it sits)."""
    spec = ScreenSpec.load(model)
    cfg = spec.config_with(variables)
    if erase_after is not None:
        stages = {}
        for name, gates in dict(cfg['run_stages']).items():
            stages[name] = [g for g in gates if g != 'g_erase']
            if name == erase_after:
                stages['erase'] = ['g_erase']
        cfg['run_stages'] = stages
    sim = Simulation(cfg)
    sim.run()
    return spec, sim


def table(model, variables, erase_after=None):
    spec, sim = run(model, variables, erase_after)
    rows = path_coherence(sim, spec.observe[0], spec.group_by, upto_gate=spec.plate)
    return spec, {r.name: r for r in rows}, rows


def v_plus(theta_deg):
    s, c = math.sin(math.radians(theta_deg)) ** 2, math.cos(math.radians(theta_deg)) ** 2
    return (2 * s * s + c * math.cos(math.radians(2 * theta_deg))) / (2 * s * s + c)


def v_minus(theta_deg):
    s = math.sin(math.radians(theta_deg)) ** 2
    return (2 * s - math.cos(math.radians(2 * theta_deg))) / (2 * s + 1)


def test_rows_run_from_the_start_to_the_plate():
    _, by_name, rows = table('decoherence/double_slit_tunable', radians(theta_pre=30))
    # the declared `decoherence` stage runs as two steps (g_pre, then the
    # bypass it feeds): both rows carry its name, the gates tell them apart
    assert [r.name for r in rows] == ['initial', 'split', 'decoherence', 'decoherence',
                                      'observe', 'slits', 'phase']
    assert [r.gates for r in rows[2:4]] == [['g_pre'], ['bypass']]
    assert rows[0].whole is None and rows[0].switched == []
    assert rows[-1].gates == ['φ']
    assert by_name['split'].switched == ['p1'] and rows[2].switched == ['p2']
    assert by_name['observe'].switched == ['p2']      # the record is written here


@pytest.mark.parametrize('deg', [0, 30, 45, 60, 90])
def test_a_partial_recorder_leaves_sin_squared(deg):
    _, by_name, rows = table('decoherence/double_slit_tunable', radians(theta_pre=deg))
    for r in rows[1:4]:      # split, and the pre-gate's two steps
        assert abs(signed_visibility(r.whole) - 1) < TOL
    for name in ('observe', 'slits', 'phase'):
        assert abs(signed_visibility(by_name[name].whole)
                   - math.sin(math.radians(deg)) ** 2) < TOL
    assert all(r.groups == {} for r in rows)         # no sort declared


def test_the_chain_is_a_running_product():
    _, by_name, _ = table('decoherence/double_slit_decoherence_chain',
                          radians(theta_pre_1=30, theta_pre_2=45, theta_pre_3=60))
    assert abs(signed_visibility(by_name['observe_1'].whole) - 0.25) < TOL
    assert abs(signed_visibility(by_name['observe_2'].whole) - 0.125) < TOL
    assert abs(signed_visibility(by_name['observe_3'].whole) - 0.09375) < TOL
    assert abs(signed_visibility(by_name['phase'].whole) - 0.09375) < TOL
    assert by_name['observe_2'].switched == ['r2']


@pytest.mark.parametrize('deg', [20, 30, 45, 60])
def test_eraser_chain_subsets_follow_v_plus_and_v_minus(deg):
    _, by_name, _ = table('decoherence/double_slit_eraser_chain',
                          radians(theta_pre_1=90, theta_pre_2=deg, theta_pre_3=90),
                          erase_after='observe_2')
    s = math.sin(math.radians(deg)) ** 2
    before, after = by_name['observe_2'], by_name['erase']
    assert after.switched == ['r2']
    for r in (before, after, by_name['phase']):
        assert abs(signed_visibility(r.whole) - s) < TOL      # the eraser changes no total
    assert abs(signed_visibility(after.groups['+']) - v_plus(deg)) < TOL
    assert abs(signed_visibility(after.groups['−']) - v_minus(deg)) < TOL
    assert abs(signed_visibility(by_name['phase'].groups['+']) - v_plus(deg)) < TOL
    # before the eraser the sort by r2's sign sees the pre-gate's own split
    # (at 45° the eraser recovers nothing, so there the two coincide)
    if deg != 45:
        assert signed_visibility(before.groups['+']) != pytest.approx(v_plus(deg))


def test_as_declared_the_eraser_sits_after_the_merge():
    # the file stages g_erase in `sort`, past the plate: no erase row, the
    # subsets show the unerased record, the whole is still sin²θ
    _, by_name, rows = table('decoherence/double_slit_eraser_chain',
                             radians(theta_pre_1=90, theta_pre_2=30, theta_pre_3=90))
    assert 'erase' not in by_name and rows[-1].name == 'phase'
    assert abs(signed_visibility(rows[-1].whole) - 0.25) < TOL
    assert abs(signed_visibility(rows[-1].groups['+']) - 0.1) < TOL
    assert abs(signed_visibility(rows[-1].groups['−']) - 0.5) < TOL


def test_eraser_gives_complementary_fringes_per_sign():
    _, by_name, _ = table('decoherence/double_slit_eraser', radians(theta_erase=45),
                          erase_after='observe')
    assert abs(signed_visibility(by_name['split'].whole) - 1) < TOL
    assert by_name['split'].groups['−'] is None          # p2 has no minus component yet
    assert abs(signed_visibility(by_name['observe'].whole)) < TOL   # a complete record
    after = by_name['erase']
    assert abs(signed_visibility(after.whole)) < TOL      # the whole stays flat
    assert abs(signed_visibility(after.groups['+']) - 1) < TOL
    assert abs(signed_visibility(after.groups['−']) + 1) < TOL
    # θ_erase = 0 is the plain recorder: nothing to sort
    _, by_name, _ = table('decoherence/double_slit_eraser', radians(theta_erase=0),
                          erase_after='observe')
    assert by_name['erase'].groups['−'] is None
    assert abs(signed_visibility(by_name['erase'].groups['+'])) < TOL


@pytest.mark.parametrize('model', screen_models())
def test_the_last_row_is_the_screen_visibility(model):
    spec, _, rows = table(model, {})
    for r in rows:
        for z in [r.whole, *r.groups.values()]:
            assert z is None or abs(z.imag) < TOL           # fringe shifts of 0 or π only
    xs, curves = screen_curves(spec, {}, n_points=41, fringes=1.0, via='pixels')
    total = [sum(curves[g][i] for g in curves) for i in range(len(xs))]
    assert abs(abs(signed_visibility(rows[-1].whole)) - visibility(total)) < 1e-6


def test_signed_visibility_reads_the_real_part():
    assert signed_visibility(None) is None
    assert signed_visibility(complex(-0.25, 0)) == -0.25
    assert signed_visibility(complex(0.5, 0.3)) is None


def test_variable_notes_ride_on_the_spec():
    assert ScreenSpec.load('decoherence/double_slit_eraser').variable_notes == {}
    cfg = dict(ScreenSpec.load('decoherence/double_slit_eraser').config)
    cfg['variable_notes'] = {'theta_erase': '0°: the plain recorder · 45°: full erasure'}
    register('upload:noted', cfg)
    try:
        spec = ScreenSpec.load('upload:noted')
        assert spec.variable_notes == {'theta_erase': '0°: the plain recorder · 45°: full erasure'}
        assert 'theta_erase' in spec.variables
    finally:
        _CACHE.pop('upload:noted', None)     # the library's exact listing is tested elsewhere
