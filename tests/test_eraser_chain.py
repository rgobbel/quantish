"""The decoherence chain with an eraser on its middle recorder
(models/decoherence/double_slit_eraser_chain.yaml): sorting the screen by
r2's sign recovers fringes of visibility

    V+ = (2 s² + c·cos 2θ) / (2 s² + c),   V− = (2 s − cos 2θ) / (2 s + 1)

with s = sin²θ, c = cos²θ, θ = theta_pre_2, times sin²θ₁·sin²θ₃ when
the other recorders are active; the whole screen keeps the chain's
product law. Exact weights only. Exchange: docs/chain-eraser-task.md."""
import math
from pathlib import Path

import pytest
import yaml
from addict import Dict as Addict

from quantish.qnumber import CalcMode
from quantish.simulation import Simulation

MODELS = Path(__file__).resolve().parents[1] / 'models'
MODEL = 'decoherence/double_slit_eraser_chain'
TOL = 1e-9


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def run(angles_deg, phi_deg) -> Simulation:
    with open(MODELS / 'defaults.yaml') as f:
        cfg = yaml.safe_load(f)
    with open(MODELS / f'{MODEL}.yaml') as f:
        cfg.update(yaml.safe_load(f))
    cfg['loglevel'] = 'warning'
    for i, deg in enumerate(angles_deg, start=1):
        cfg['variables'][f'theta_pre_{i}'] = f'{deg}°'
    cfg['variables']['phi'] = f'{phi_deg}°'
    sim = Simulation(Addict(cfg))
    sim.run()
    return sim


def screen_by_sign(sim: Simulation) -> dict:
    """{r2 sign: P(p1 at S and r2 has that sign)}, plus P(r2 sign) under
    the keys ('n', sign)."""
    out = {1: 0.0, -1: 0.0, ('n', 1): 0.0, ('n', -1): 0.0}
    for point in sim.result_space.index.values():
        sign = int(point.coords['r2'].sign)
        prob = float(point.probability)
        out[('n', sign)] += prob
        origin = point.coords['p1'].position.origin
        if origin is not None and origin.gate == 'S':
            out[sign] += prob
    return out


def visibilities(angles_deg):
    """(V+, V−, V whole), each (P₀ − P₁₈₀)/(P₀ + P₁₈₀); None for an empty subset."""
    bright, dark = screen_by_sign(run(angles_deg, 0.0)), screen_by_sign(run(angles_deg, 180.0))

    def vis(a, b):
        return None if a + b < 1e-12 else (a - b) / (a + b)
    return (vis(bright[1], dark[1]), vis(bright[-1], dark[-1]),
            vis(bright[1] + bright[-1], dark[1] + dark[-1]))


def closed_form(t2_deg, t1_deg=90, t3_deg=90):
    th = math.radians(t2_deg)
    s, c = math.sin(th) ** 2, math.cos(th) ** 2
    rest = math.sin(math.radians(t1_deg)) ** 2 * math.sin(math.radians(t3_deg)) ** 2
    v_plus = (2 * s * s + c * math.cos(2 * th)) / (2 * s * s + c)
    v_minus = (2 * s - math.cos(2 * th)) / (2 * s + 1)
    return v_plus * rest, v_minus * rest


@pytest.mark.parametrize('t2, v_plus, v_minus', [
    (0, 1.0, -1.0),           # the eraser model: complementary full fringes
    (30, 4 / 7, 0.0),
    (45, 0.5, 0.5),           # the eraser recovers nothing
    (60, 8 / 11, 4 / 5),
    (90, 1.0, None),          # nothing recorded; the minus subset is empty
])
def test_sorted_visibility_with_the_other_recorders_inert(t2, v_plus, v_minus):
    got_plus, got_minus, whole = visibilities((90, t2, 90))
    assert abs(got_plus - v_plus) < TOL, (t2, got_plus)
    if v_minus is None:
        assert got_minus is None
    else:
        assert abs(got_minus - v_minus) < TOL, (t2, got_minus)
    # the sort does not change the screen: the chain's law throughout
    assert abs(whole - math.sin(math.radians(t2)) ** 2) < TOL


@pytest.mark.parametrize('t2', [15, 30, 45, 60, 75])
def test_closed_forms(t2):
    got_plus, got_minus, _ = visibilities((90, t2, 90))
    v_plus, v_minus = closed_form(t2)
    assert abs(got_plus - v_plus) < TOL and abs(got_minus - v_minus) < TOL


@pytest.mark.parametrize('angles', [(30, 45, 60), (30, 20, 60), (45, 70, 30)])
def test_other_recorders_factor_out(angles):
    got_plus, got_minus, whole = visibilities(angles)
    v_plus, v_minus = closed_form(angles[1], angles[0], angles[2])
    assert abs(got_plus - v_plus) < TOL and abs(got_minus - v_minus) < TOL, angles
    product = math.prod(math.sin(math.radians(a)) ** 2 for a in angles)
    assert abs(whole - product) < TOL


def test_sign_split_is_independent_of_phi():
    for phi in (0.0, 90.0, 180.0):
        out = screen_by_sign(run((30, 45, 60), phi))
        assert abs(out[('n', 1)] - 0.5) < TOL and abs(out[('n', -1)] - 0.5) < TOL
