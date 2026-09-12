"""The decoherence chain (models/decoherence/double_slit_decoherence_chain.yaml):
three partial which-way recorders in series on the right-slit arm. The
fringe visibility is the product of the recorders' bypass fractions,
V = prod_i sin²(theta_pre_i), and the screen follows
P(S) = V·cos²(phi/2) + (1 − V)/2. All from exact weights (Float mode,
no sampling); the brief is docs/decoherence-chain-task.md."""
import math
from pathlib import Path

import pytest
import yaml
from addict import Dict as Addict

from quantish.qnumber import CalcMode
from quantish.simulation import Simulation

MODELS = Path(__file__).resolve().parents[1] / 'models'
MODEL = 'decoherence/double_slit_decoherence_chain'
TOL = 1e-9


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def run(angles_deg=(45, 45, 45), phi_deg=0.0) -> Simulation:
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


def p_at(sim: Simulation, gate: str, particle: str = 'p1') -> float:
    """Exact probability that `particle` ends at `gate`."""
    total = 0.0
    for point in sim.result_space.index.values():
        origin = point.coords[particle].position.origin
        if origin is not None and origin.gate == gate:
            total += float(point.probability)
    return total


def visibility(angles_deg) -> float:
    bright = p_at(run(angles_deg, 0.0), 'S')
    dark = p_at(run(angles_deg, 180.0), 'S')
    return (bright - dark) / (bright + dark)


def product_law(angles_deg) -> float:
    return math.prod(math.sin(math.radians(a)) ** 2 for a in angles_deg)


@pytest.mark.parametrize('angles, expected', [
    ((45, 45, 45), 0.125),        # three half-overlaps: 1/8
    ((90, 90, 90), 1.0),          # nothing recorded: figure 4.13
    ((0, 90, 90), 0.0),           # one complete record: figure 4.15
    ((30, 45, 60), 0.09375),      # 1/4 · 1/2 · 3/4
])
def test_visibility_is_the_product_of_overlaps(angles, expected):
    v = visibility(angles)
    assert abs(v - expected) < TOL, (angles, v)
    assert abs(v - product_law(angles)) < TOL


@pytest.mark.parametrize('angles', [(45, 45, 45), (30, 45, 60), (20, 70, 50)])
@pytest.mark.parametrize('phi_deg', [60.0, 120.0, 200.0])
def test_screen_follows_the_law(angles, phi_deg):
    v = product_law(angles)
    expected = v * math.cos(math.radians(phi_deg) / 2) ** 2 + (1 - v) / 2
    got = p_at(run(angles, phi_deg), 'S')
    assert abs(got - expected) < TOL, (angles, phi_deg, got, expected)
    # the screen and the dark detector share p1's weight
    assert abs(got + p_at(run(angles, phi_deg), 'D') - 1) < TOL


def test_order_of_recorders_does_not_matter():
    reference = visibility((30, 45, 60))
    for order in ((60, 30, 45), (45, 60, 30), (60, 45, 30)):
        assert abs(visibility(order) - reference) < TOL, order


def test_probability_conserved_at_every_stage():
    sim = run((30, 45, 60), 70.0)
    _, history = sim.result_space, sim.all_points
    by_step = {}
    for point in history.index.values():
        by_step[point.step] = by_step.get(point.step, 0.0) + float(point.probability)
    assert sorted(by_step) == list(range(len(sim.run_stages) + 1))
    for step, total in by_step.items():
        assert abs(total - 1) < 1e-9, (step, total)


def test_single_recorder_reduces_to_the_tunable_model():
    # with the other two recorders fully bypassed (90°), the chain is
    # the one-recorder model: V = sin²(theta_pre)
    for deg in (0, 30, 45, 60, 90):
        assert abs(visibility((deg, 90, 90)) - math.sin(math.radians(deg)) ** 2) < TOL
