"""Inert gates (wires) and the virtual screens built on them: the
screen a model would show if its paths were merged right after each
stage, the environment frozen there. Checked against the family's laws
and against one-run-per-pixel screens."""
import math

import pytest

from quantish.qnumber import CalcMode
from quantish.screen import (
    ScreenSpec,
    _pixel,
    pixel,
    screen_curves,
    stage_screens,
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


def signed(ys):
    """(P(φ=0) − P(φ=π)) / sum from a one-fringe curve: x = 0 is φ = 0,
    x = ±1 is φ = ±π."""
    hi, lo = ys[len(ys) // 2], ys[0]
    return None if hi + lo < 1e-12 else (hi - lo) / (hi + lo)


def test_an_inert_gate_is_a_wire():
    spec = ScreenSpec.load('extras/double_slit_recorder')
    sim = spec.simulation({}, inert=('g_obs',))
    assert sim.inert == ['g_obs'] and sim.gates['g_obs'].inert
    sim.run()
    # the recorder never records: p2 stays where it entered, every
    # point keeps p1's coherence — the plain double slit's screen
    for pt in sim.result_space.index.values():
        assert pt.coords['p2'].position.origin.gate == 'g_obs'
        assert pt.coords['p2'].position.origin.port == 'upper'
    _, curves = screen_curves(spec, {}, 41, 1.0, inert=('g_obs',))
    assert abs(signed(curves['all']) - 1) < TOL
    _, curves = screen_curves(spec, {}, 41, 1.0)
    assert abs(signed(curves['all'])) < TOL      # the record kills them
    with pytest.raises(ValueError):
        Simulation(spec.config_with({}), inert=('nope',))


def test_inert_gates_angles_leave_the_cache_key():
    spec = ScreenSpec.load('decoherence/double_slit_decoherence_chain')
    inert = ('g_obs_3', 'g_pre_3', 'bypass_3')
    _pixel.cache_clear()
    pixel(spec, radians(theta_pre_3=20), 0.0, inert)
    before = _pixel.cache_info().hits
    pixel(spec, radians(theta_pre_3=70), 0.0, inert)      # only the inert gate's angle moved
    assert _pixel.cache_info().hits == before + 1
    pixel(spec, radians(theta_pre_2=70), 0.0, inert)      # a live gate's angle: a new run
    assert _pixel.cache_info().hits == before + 1


def test_virtual_screens_end_at_the_models_own():
    spec = ScreenSpec.load('decoherence/double_slit_decoherence_chain')
    v = radians(theta_pre_1=30, theta_pre_2=45, theta_pre_3=60)
    _, screens = stage_screens(spec, v, 41, 1.0)
    assert [s['name'] for s in screens] == ['split', 'decoherence', 'observe_1',
                                            'observe_2', 'observe_3', 'actual screen']
    for s, expected in zip(screens, (1, 1, 0.25, 0.125, 0.09375, 0.09375)):
        assert abs(signed(s['curves']['all']) - expected) < TOL, s['name']
    assert screens[1]['curves'] is screens[0]['curves']    # nothing recorded: reused
    _, final = screen_curves(spec, v, 41, 1.0)
    assert all(abs(a - b) < TOL for a, b in zip(final['all'], screens[-1]['curves']['all']))


def test_eraser_chain_shows_the_record_and_then_the_erasure():
    spec = ScreenSpec.load('decoherence/double_slit_eraser_chain')
    _, screens = stage_screens(spec, radians(theta_pre_2=30), 41, 1.0)
    names = [s['name'] for s in screens]
    # the file stages the eraser after the merge: the model's own screen
    # is the last strip, and it is where the erasure shows
    assert names == ['split', 'decoherence', 'observe_2', 'actual screen']
    assert 'g_erase' in screens[-1]['gates']
    split, record, screen = screens[0], screens[2], screens[-1]
    assert abs(signed(split['curves']['+']) - 1) < TOL and max(split['curves']['−']) < TOL
    assert abs(signed(record['curves']['+']) - 0.1) < TOL
    assert abs(signed(record['curves']['−']) - 0.5) < TOL
    assert abs(signed(screen['curves']['+']) - 4 / 7) < TOL
    assert abs(signed(screen['curves']['−'])) < TOL
    # the whole screen never changes after the record
    for s in (record, screen):
        total = [a + b for a, b in zip(s['curves']['+'], s['curves']['−'])]
        assert abs(visibility(total) - 0.25) < TOL


def test_eraser_subsets_are_complementary_only_after_the_eraser():
    spec = ScreenSpec.load('decoherence/double_slit_eraser')
    _, screens = stage_screens(spec, radians(theta_erase=45), 41, 1.0)
    assert [s['name'] for s in screens] == ['split', 'observe', 'actual screen']
    observe, screen = screens[1], screens[2]
    assert abs(signed(observe['curves']['+'])) < TOL and max(observe['curves']['−']) < TOL
    assert abs(signed(screen['curves']['+']) - 1) < TOL
    assert abs(signed(screen['curves']['−']) + 1) < TOL


@pytest.mark.parametrize('model, v', [
    ('decoherence/double_slit_eraser', radians(theta_erase=30, theta_split=30)),
    ('decoherence/double_slit_tunable', radians(theta_pre=40, theta_merge=60, theta_sort=20)),
])
def test_the_fit_agrees_with_one_run_per_pixel(model, v):
    spec = ScreenSpec.load(model)
    _, fitted = stage_screens(spec, v, 21, 1.0)
    _, exact = stage_screens(spec, v, 21, 1.0, via='pixels')
    assert [s['name'] for s in fitted] == [s['name'] for s in exact]
    for a, b in zip(fitted, exact):
        for g in a['curves']:
            assert all(abs(p - q) < 1e-9 for p, q in zip(a['curves'][g], b['curves'][g])), a['name']


def test_gates_switched_off_throughout_the_virtual_screens():
    # the lab's toggles: with the middle recorder's pre-gate off, r2 never
    # splits and the chain is two recorders — in every strip, the actual
    # screen included
    spec = ScreenSpec.load('decoherence/double_slit_decoherence_chain')
    v = radians(theta_pre_1=30, theta_pre_2=45, theta_pre_3=60)
    _, screens = stage_screens(spec, v, 41, 1.0, inert=('g_pre_2',))
    assert [s['name'] for s in screens] == ['split', 'decoherence', 'observe_1',
                                            'observe_2', 'observe_3', 'actual screen']
    # g_pre_2 off: r2 stays on its record arm and g_obs_2 records completely
    assert abs(signed(screens[3]['curves']['all'])) < TOL
    _, direct = screen_curves(spec, v, 41, 1.0, inert=('g_pre_2',))
    assert all(abs(a - b) < TOL for a, b in zip(direct['all'], screens[-1]['curves']['all']))
    # g_obs_2 off instead: the middle recorder never records, V = sin²θ₁·sin²θ₃
    _, screens = stage_screens(spec, v, 41, 1.0, inert=('g_obs_2',))
    assert abs(signed(screens[-1]['curves']['all']) - 0.25 * 0.75) < TOL


def test_an_absent_particle_is_a_null_input():
    # the recorder's particle left out: nothing records, the plain double
    # slit's fringes, total probability untouched (a null input, not a
    # zero weight on the state)
    spec = ScreenSpec.load('decoherence/double_slit_tunable')
    sim = spec.simulation({}, absent=('p2',))
    assert sim.absent == ['p2'] and 'p2' in sim.particles      # declared, drawn, never entering
    sim.run()
    assert all('p2' not in pt.coords for pt in sim.result_space.index.values())
    assert abs(sum(float(pt.probability) for pt in sim.result_space.index.values()) - 1) < TOL
    _, curves = screen_curves(spec, {}, 41, 1.0, absent=('p2',))
    assert abs(signed(curves['all']) - 1) < TOL
    with pytest.raises(ValueError, match='absent names no declared particle'):
        spec.simulation({}, absent=('nobody',))


def test_absent_particles_through_the_screen_and_the_strips():
    spec = ScreenSpec.load('decoherence/double_slit_eraser_chain')
    # the sort particle left out: one unsorted group, the chain of the
    # other two recorders
    v = radians(theta_pre_1=30, theta_pre_2=30, theta_pre_3=60)
    _, curves = screen_curves(spec, v, 41, 1.0, absent=('r2',))
    assert list(curves) == ['all'] and abs(visibility(curves['all']) - 0.25 * 0.75) < TOL
    _, screens = stage_screens(spec, v, 41, 1.0, absent=('r2',))
    assert screens[-1]['name'] == 'actual screen' and list(screens[-1]['curves']) == ['all']
    # the screen particle left out: no hits, no strips
    _, curves = screen_curves(spec, v, 41, 1.0, absent=('p1',))
    assert all(y == 0 for ys in curves.values() for y in ys)
    assert stage_screens(spec, v, 41, 1.0, absent=('p1',))[1] == []


def test_the_diagram_crosses_out_what_is_off():
    from quantish.diagram_layout import DISABLED_FILL, diagram_geometry
    spec = ScreenSpec.load('decoherence/double_slit_tunable')
    geom = diagram_geometry(spec.simulation({}), disabled=('g_obs',), absent=('p2',))
    assert len(geom['marks']) == 4            # two lines per X, a gate and a particle
    assert sum(b['fill'] == DISABLED_FILL for b in geom['boxes']) >= 6   # frame, ports, blob
    assert diagram_geometry(spec.simulation({}))['marks'] == []


def test_every_particle_absent_still_runs():
    from quantish.qnumber import prod
    assert float(prod([])) == 0 and float(prod(x for x in ())) == 0   # empty generators too
    spec = ScreenSpec.load('decoherence/double_slit_decoherence_chain')
    sim = spec.simulation({}, absent=('p1', 'r1', 'r2', 'r3'))
    sim.run()          # nothing enters: no crash, and nothing comes out
    assert len(sim.result_space.index) == 0


def test_a_plate_off_the_sweep_gets_a_phase_slider_and_a_toggle():
    from quantish.screen import _CACHE, register
    cfg = dict(ScreenSpec.load('extras/double_slit').config)
    del cfg['sweep']                       # no screen: the plate's phase is settable
    cfg['phase_plates'] = {'φ': '30°'}     # a literal phase
    register('upload:plated', cfg)
    try:
        spec = ScreenSpec.load('upload:plated')
        assert not spec.has_screen and spec.synthetic.get('phi_φ') == 'φ'
        assert spec.angle_gates()['φ'] == 'phi_φ' and spec.angle_ranges()['phi_φ'] == (0.0, 360.0)
        assert abs(spec.default_degrees()['phi_φ'] - 30) < 1e-9
        sim = spec.simulation({'phi_φ': math.radians(90)}, inert=('φ',))
        assert abs(float(sim.gates['φ'].phase.degrees) - 90) < 1e-9 and sim.gates['φ'].inert
    finally:
        _CACHE.pop('upload:plated', None)
    # the screened models keep their swept plate out of the sliders
    screened = ScreenSpec.load('extras/double_slit')
    assert 'phi' not in screened.variables and 'φ' not in screened.angle_gates()
