"""The double-slit demo's textbook relations."""
import math
import unittest

from quantish.double_slit import pixel_probability, screen_curve
from quantish.qnumber import CalcMode


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


def test_eraser_complementary_fringes():
    """The quantum eraser (extras/double_slit_eraser.yaml): a 45° gate
    after the recorder mixes p2's two which-way wires. Sorted by p2's
    sign the screen shows complementary fringes — P(S, p2+) = ½cos²(φ/2)
    and P(S, p2−) = ½sin²(φ/2) whichever detector p2 reached — while
    sorted by p2's detector alone, and in total, it is the recorder's
    flat ½."""
    import copy
    from collections import defaultdict
    from pathlib import Path

    import yaml
    from addict import Dict as Addict

    from quantish.qnumber import CalcMode
    from quantish.simulation import Simulation

    models = Path(__file__).resolve().parents[1] / 'models' / 'extras'
    with open(models / 'double_slit_eraser.yaml') as f:
        base = yaml.safe_load(f)
    base['loglevel'] = 'warning'
    CalcMode.default('Float')
    for phi in (0.0, math.pi / 3, math.pi / 2, math.pi, 1.5 * math.pi):
        cfg = copy.deepcopy(base)
        cfg['variables']['phi'] = phi
        space, _ = Simulation(Addict(cfg)).run()
        at_s = defaultdict(float)     # (p2 detector, p2 sign) -> P(p1 at S)
        for p in space.index.values():
            c1, c2 = p.coords['p1'], p.coords['p2']
            if c1.position.origin.gate != 'S':
                continue
            at_s[(c2.position.origin.gate, int(c2.sign))] += float(p.probability)
        assert set(at_s) <= {('E1', 1), ('E1', -1), ('E2', 1), ('E2', -1)}
        plus = sum(v for (_, s), v in at_s.items() if s > 0)
        minus = sum(v for (_, s), v in at_s.items() if s < 0)
        assert abs(plus - 0.5 * math.cos(phi / 2) ** 2) < 1e-9, (phi, plus)
        assert abs(minus - 0.5 * math.sin(phi / 2) ** 2) < 1e-9, (phi, minus)
        for det in ('E1', 'E2'):
            by_wire = at_s[(det, 1)] + at_s[(det, -1)]
            assert abs(by_wire - 0.25) < 1e-9, (phi, det, by_wire)
        assert abs(plus + minus - 0.5) < 1e-9
        # delayed choice: erasing after p1 has hit the screen changes
        # nothing — the final configuration-space points are identical
        late = copy.deepcopy(cfg)
        late['run_stages'] = {'split': ['g_split'], 'observe': ['g_obs'],
                              'slits': ['S1', 'S2'], 'phase': ['φ'],
                              'merge': ['g_merge'], 'sort': ['g_sort'],
                              'detect': ['S', 'D'], 'erase': ['g_erase'],
                              'read': ['E1', 'E2']}
        late_space, _ = Simulation(Addict(late)).run()
        early = {k: complex(p.weight.v) for k, p in space.index.items()}
        assert early == {k: complex(p.weight.v)
                         for k, p in late_space.index.items()}


def test_eraser_screen_split_by_sign():
    """The eraser condition of the app: the screen intensity split by
    p2's sign gives the complementary fringes ½cos²(φ/2) and ½sin²(φ/2)
    and the flat total; θ_erase = 0 is the recorder (all plus); grouped
    hit sampling tags each hit with a group drawn at its pixel's odds."""
    import random

    import pytest

    from quantish.double_slit import pixel_by_sign, sample_hits, screen_curves_by_sign
    for phi in (0.0, math.pi / 3, math.pi / 2, math.pi):
        plus, minus = pixel_by_sign(phi, 'eraser')
        assert abs(plus - 0.5 * math.cos(phi / 2) ** 2) < 1e-9
        assert abs(minus - 0.5 * math.sin(phi / 2) ** 2) < 1e-9
        assert pixel_by_sign(phi, 'eraser', theta_erase=0.0) == \
            pytest.approx((0.5, 0.0))
        assert pixel_by_sign(phi, 'both') == \
            pytest.approx((math.cos(phi / 2) ** 2, 0.0))
    xs, (plus, minus) = screen_curves_by_sign(41, 3.0, 'eraser')
    total = [a + b for a, b in zip(plus, minus)]
    assert all(abs(t - 0.5) < 1e-9 for t in total)
    hits = sample_hits(xs, total, 2000, random.Random(7), parts=(plus, minus))
    assert hits and all(len(h) == 3 and h[2] in (0, 1) for h in hits)
    # the screen center (φ = 0) is a plus-sign fringe and x = ±1/3
    # (φ = π) a minus-sign one; jitter lets a neighbor pixel's few
    # other-sign hits stray in, so the checks are statistical
    center = [h for h in hits if abs(h[0]) < 0.05]
    dark = [h for h in hits if abs(abs(h[0]) - 1 / 3) < 0.05]
    assert len(center) > 50 and len(dark) > 50
    assert sum(h[2] for h in center) / len(center) < 0.15
    assert sum(1 - h[2] for h in dark) / len(dark) < 0.15


def test_reused_simulation_matches_a_fresh_one():
    """The per-condition Simulation reused across pixels (the phase
    plate set in place per pixel) gives exactly what a freshly loaded
    Simulation gives — a run is repeatable and set_phase is complete."""
    from quantish.double_slit import pixel_by_sign, slit_sim
    for mode, kw in (('tunable', {'theta_pre': 0.7}),
                     ('eraser', {'theta_erase': 0.6}), ('both', {}),
                     ('slit1', {}), ('slit2', {}), ('observed', {})):
        for phi in (1.3, 0.2, 2.9, 1.3):     # revisits included
            fresh = slit_sim(mode, phi=phi, **kw)
            fresh.run()
            want = sum(float(p.probability)
                       for p in fresh.result_space.index.values()
                       if p.coords['p1'].position.origin.gate == 'S')
            got = sum(pixel_by_sign(phi, mode, **kw))
            assert abs(got - want) < 1e-12, (mode, phi, got, want)


def test_three_run_reconstruction_matches_every_pixel():
    """via='fit' (three engine runs, A + B cos φ + C sin φ) agrees with
    one engine run per pixel to rounding — at the ideal angles and at
    off-ideal ones the app's implementation-level sliders reach."""
    from quantish.double_slit import screen_curves_by_sign
    settings = [{},
                {'theta_s': math.radians(30), 'theta_merge': math.radians(50),
                 'theta_sort': math.radians(20), 'theta_pre': math.radians(35),
                 'theta_erase': math.radians(25)}]
    for kw in settings:
        for mode in ('both', 'slit1', 'slit2', 'observed', 'tunable',
                     'eraser'):
            xs, fit = screen_curves_by_sign(41, 3.0, mode, via='fit', **kw)
            _, px = screen_curves_by_sign(41, 3.0, mode, via='pixels', **kw)
            for series in range(2):
                for x, a, b in zip(xs, fit[series], px[series]):
                    assert abs(a - b) < 1e-12, (mode, kw, series, x, a, b)
