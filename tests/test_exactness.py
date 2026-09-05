"""Symbolic mode keeps every quantity exact until display.

The teaching-tool contract: with clean symbolic inputs, no value is
ever converted to a float inside the calculation — only displays,
logs, the probability invariant check and Monte Carlo sampling
convert, and each of those converts once, at the end. A decimal that
arrives as a Python float (a YAML literal, a slider) is an exact
Rational, not a sympy Float."""
from pathlib import Path

import pytest
import sympy as sym
import yaml
from addict import Addict

import quantish.qnumber as qn
from quantish.epr import run_pair, sweep_angles
from quantish.simulation import Simulation

MODELS = Path(__file__).resolve().parents[1] / 'models'


@pytest.fixture
def symbolic():
    qn.CalcMode.default('Symbolic')
    yield
    qn.CalcMode.default('Float')


def _config(name, **overrides):
    with open(MODELS / 'defaults.yaml') as f:
        cfg = yaml.safe_load(f)
    with open(MODELS / f'{name}.yaml') as f:
        cfg.update(yaml.safe_load(f))
    cfg['loglevel'] = 'warning'
    cfg['calculation_mode'] = 'Symbolic'
    cfg.update(overrides)
    return cfg


def _has_float(x):
    return getattr(x, 'v', x).has(sym.Float)


def test_python_floats_become_rationals(symbolic):
    assert qn.qify(0.5).v == sym.Rational(1, 2)
    assert qn.qify(0.1).v == sym.Rational(1, 10)
    assert qn.qify(0.25).v == sym.Rational(1, 4)
    assert not _has_float(qn.qify(0.5))
    assert not qn.inexact(qn.qify(0.5))
    # a long machine decimal is exact but not meaningfully symbolic
    assert qn.inexact(qn.qify(0.5235987755982988))
    assert qn.inexact(qn.Real(sym.Float(0.5)))


def test_degree_unit_angles_stay_exact(symbolic):
    cfg = _config('gr2026/fig4.04')
    cfg['angle_unit'] = 'degrees'
    for g in cfg['gates'].values():
        g['angle'] = 30
    sim = Simulation(Addict(cfg))
    theta = sim.fredkin_gates['g1'].theta.v
    assert sym.simplify(theta - sym.pi / 6) == 0
    assert sim.inexact_inputs() == []
    space, _ = sim.run()
    for p in space.index.values():
        assert not _has_float(p.weight)
        assert not _has_float(p.probability)


def test_branch_probability_literal_is_exact(symbolic):
    cfg = _config('gr2026/fig4.03')      # p1: [g1.control, g2.control, 0.5]
    sim = Simulation(Addict(cfg))
    for amps in sim.branch_amps.values():
        assert all(not _has_float(a) for a in amps)
    assert sim.inexact_inputs() == []


def test_epr_cell_is_exact(symbolic):
    sim = Simulation(Addict(_config('gr2026/fig4.17')))
    sim.run()
    angles = sweep_angles(sim)
    a, b = list(angles.values())[:2]
    cell = run_pair(sim, a, b)
    for key in ('exact', 'analytical', 'classical'):
        assert not _has_float(cell[key]), key
    # the exact rate equals the analytical prediction sin²(θ1−θ2)
    assert sym.simplify(qn.qify(cell['exact']).v
                        - qn.qify(cell['analytical']).v) == 0


def test_inexact_inputs_are_reported(symbolic):
    cfg = _config('gr2026/fig4.04')
    for g in cfg['gates'].values():
        g['angle'] = 0.5235987755982988        # math.radians(30)
    sim = Simulation(Addict(cfg))
    assert sim.inexact_inputs() == ['g1 angle']
