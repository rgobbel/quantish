"""The double-slit demo's textbook relations."""
import math
import unittest

import quantish.qnumber as qn
from quantish.qnumber import CalcMode
from quantish.double_slit import pixel_probability, screen_curve


class TestDoubleSlit(unittest.TestCase):
    def setUp(self):
        CalcMode.default('Float')

    def curves(self, fringes=3, n=81):
        return {mode: screen_curve(n, fringes, mode)[1]
                for mode in ('both', 'slit1', 'slit2', 'observed')}

    def test_single_slit_is_flat(self):
        c = self.curves()
        for mode in ('slit1', 'slit2'):
            self.assertAlmostEqual(min(c[mode]), max(c[mode]), places=12)

    def test_both_slits_interfere(self):
        c = self.curves()
        self.assertAlmostEqual(min(c['both']), 0.0, places=9)   # dark fringes
        # bright fringes reach 4x the single-slit intensity
        self.assertAlmostEqual(max(c['both']), 4 * c['slit1'][0], places=9)
        # central bright fringe at the screen center (equal path lengths)
        mid = len(c['both']) // 2
        self.assertAlmostEqual(c['both'][mid], max(c['both']), places=9)

    def test_pixel_follows_the_cos_law(self):
        # remerge + sign sorter: P(S) = (1 + cos phi)/2, exact per engine run
        for degrees in (0, 60, 90, 120, 180):
            phi = math.radians(degrees)
            self.assertAlmostEqual(pixel_probability(phi),
                                   (1 + math.cos(phi)) / 2, places=12)

    def test_observation_restores_classical_sum(self):
        c = self.curves()
        for obs, s1, s2 in zip(c['observed'], c['slit1'], c['slit2']):
            self.assertAlmostEqual(obs, s1 + s2, places=12)


if __name__ == '__main__':
    unittest.main()


def test_symbolic_phase_plate_runs():
    """A non-zero phase-plate phase in Symbolic mode: the rotated
    weights' |w|² must stay Real and sum to 1 (regression — the
    invariant check used to choke on a Complex-typed probability)."""
    from pathlib import Path

    import yaml
    from addict import Dict as Addict
    from quantish.qnumber import CalcMode, Real
    from quantish.simulation import Simulation
    models = Path(__file__).resolve().parents[1] / 'models'
    with open(models / 'defaults.yaml') as f:
        cfg = yaml.safe_load(f)
    with open(models / 'extras' / 'double_slit.yaml') as f:
        cfg.update(yaml.safe_load(f))
    cfg['variables']['phi'] = 'pi/3'
    cfg['loglevel'] = 'warning'
    cfg['calculation_mode'] = 'Symbolic'
    CalcMode.default('Symbolic')
    try:
        sim = Simulation(Addict(cfg))
        space, _ = sim.run()
        probs = [p.probability for p in space.index.values()]
        assert all(isinstance(p, Real) for p in probs)
        assert abs(sum(float(p) for p in probs) - 1) < 1e-9
    finally:
        CalcMode.default('Float')


def test_conditions_come_from_their_model_files():
    """Each app condition is one of the extras/double_slit*.yaml files
    with only the angles and phi set on top — so the files are the
    source of truth and each also loads and runs on its own."""
    from pathlib import Path

    import yaml
    from addict import Addict
    from quantish.double_slit import MODEL_FILES, MODES, slit_config
    from quantish.simulation import Simulation

    models = Path(__file__).resolve().parents[1] / 'models' / 'extras'
    assert set(MODEL_FILES) == set(MODES)
    for mode, name in MODEL_FILES.items():
        with open(models / f'{name}.yaml') as f:
            cfg = yaml.safe_load(f)
        app = slit_config(mode)
        assert app['title'] == cfg['title']
        for key in ('run_stages', 'gates', 'particles', 'delay_gates',
                    'links'):
            got = (dict(app[key]) if isinstance(cfg[key], dict)
                   else list(app[key]))
            assert got == cfg[key], (name, key)
        assert set(app['variables']) == set(cfg['variables']), name
        cfg['loglevel'] = 'warning'
        space, _ = Simulation(Addict(cfg)).run()
        total = sum(float(p.probability) for p in space.index.values())
        assert abs(total - 1) < 1e-9, name


def test_tunable_recorder_visibility():
    """The tunable recorder: fringe visibility sin²(θ_pre). Per pixel,
    I = sin²θ_pre · cos²(φ/2) + ½ cos²θ_pre — the recorder condition at
    θ_pre = 0, both-slits-open at 90°, half visibility at 45°."""
    from quantish.double_slit import pixel_probability
    for deg in (0, 30, 45, 60, 90):
        t = math.radians(deg)
        for phi in (0.0, math.pi / 3, math.pi / 2, math.pi):
            got = pixel_probability(phi, 'tunable', theta_pre=t)
            want = (math.sin(t) ** 2 * math.cos(phi / 2) ** 2
                    + 0.5 * math.cos(t) ** 2)
            assert abs(got - want) < 1e-9, (deg, phi, got, want)
    assert abs(pixel_probability(math.pi, 'tunable', theta_pre=0.0)
               - pixel_probability(math.pi, 'observed')) < 1e-12
    assert abs(pixel_probability(math.pi / 3, 'tunable',
                                 theta_pre=math.pi / 2)
               - pixel_probability(math.pi / 3, 'both')) < 1e-12
