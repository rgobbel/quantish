"""Loose mode (Simulation(cfg, loose=True), the `loose` config key, the
CLI's --loose): the model is whatever the particles can reach. Gates
no particle reaches, particles with no link, and everything that named
them are dropped; run_stages the model leaves out are derived from the
topology. The connected part runs exactly as the strict model does."""
import math
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from addict import Dict as Addict

from quantish.qnumber import CalcMode
from quantish.simulation import Simulation, loose_config

MODELS = Path(__file__).resolve().parents[1] / 'models'
TOL = 1e-9


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def load(model: str, **variables) -> Addict:
    with open(MODELS / 'defaults.yaml') as f:
        cfg = yaml.safe_load(f)
    with open(MODELS / f'{model}.yaml') as f:
        cfg.update(yaml.safe_load(f))
    cfg['loglevel'] = 'warning'
    for name, deg in variables.items():
        cfg['variables'][name] = f'{deg}°'
    return Addict(cfg)


def outcomes(sim: Simulation) -> dict:
    """{sorted coordinate text: probability} of the final configuration
    space, for comparing two runs particle by particle."""
    out = {}
    for point in sim.result_space.index.values():
        key = tuple(sorted(str(c) for c in point.coords.values()))
        out[key] = out.get(key, 0.0) + float(point.probability)
    return out


def same_outcomes(a: dict, b: dict):
    assert a.keys() == b.keys()
    for key, prob in a.items():
        assert abs(prob - b[key]) < TOL, key


def with_orphans(cfg: Addict) -> Addict:
    """A copy with loose ends: a particle linked into an undeclared gate,
    a gate nothing feeds and the gate it feeds, each with labels and
    display strings."""
    cfg = deepcopy(cfg)
    cfg.particles.p_lost = Addict({'weight': 1, 'sign': 1})
    cfg.gates.g_unfed = Addict({'angle': '30°'})
    cfg.gates.g_orphan = Addict({'angle': '30°'})
    cfg.links.p_lost = 'g_missing.control'
    cfg.links['g_unfed.upper'] = 'g_orphan.control'
    cfg.display_strings = Addict({**dict(cfg.get('display_strings') or {}),
                                  'g_orphan': '$g_o$', 'p_lost': '$p_?$'})
    cfg.wire_labels = Addict({**dict(cfg.get('wire_labels') or {}),
                              'p_lost': 'w_lost', '>g_unfed.lower': 'w_null'})
    return cfg


def test_strict_mode_still_refuses_loose_ends():
    cfg = with_orphans(load('gr2026/fig4.13'))
    with pytest.raises(ValueError):
        Simulation(cfg)
    with pytest.raises(ValueError, match='run_stages'):
        bare = load('gr2026/fig4.13')
        del bare['run_stages']
        Simulation(bare)


def test_orphans_are_dropped_and_the_rest_runs_unchanged():
    base = load('gr2026/fig4.13')
    strict = Simulation(base)
    strict.run()
    loose = Simulation(with_orphans(base), loose=True)
    assert loose.dropped == {
        'particles': ['p_lost'], 'gates': ['g_orphan', 'g_unfed'],
        'links': ['p_lost: g_missing.control', 'g_unfed.upper: g_orphan.control']}
    assert set(loose.gates) == set(strict.gates)
    assert set(loose.particles) == set(strict.particles)
    assert loose.run_stages == strict.run_stages
    assert 'g_orphan' not in loose.config.display_strings
    assert 'p_lost' not in loose.config.get('wire_labels', {})
    loose.run()
    same_outcomes(outcomes(loose), outcomes(strict))


def test_the_config_key_switches_loose_mode_on():
    cfg = with_orphans(load('gr2026/fig4.13'))
    cfg.loose = True
    sim = Simulation(cfg)
    assert sim.loose and sim.dropped['gates'] == ['g_orphan', 'g_unfed']
    assert sim.config.loose is True    # the pruned config remembers


def test_the_original_config_is_untouched():
    cfg = with_orphans(load('gr2026/fig4.13'))
    before = deepcopy(dict(cfg))
    pruned, dropped = loose_config(cfg)
    assert dict(cfg) == before
    assert 'g_orphan' not in pruned.gates and 'g_orphan' in cfg.gates
    assert dropped['particles'] == ['p_lost']


@pytest.mark.parametrize('model', ['gr2026/fig4.13', 'gr2026/fig4.17',
                                   'decoherence/double_slit_eraser_chain'])
def test_stages_derive_from_the_topology_when_missing(model):
    base = load(model)
    strict = Simulation(base)
    strict.run()
    cfg = deepcopy(base)
    del cfg['run_stages']
    loose = Simulation(cfg, loose=True)
    assert all(name.startswith('auto_') for name in loose.declared_run_stages)
    assert sorted(g for stage in loose.run_stages for g in stage) \
        == sorted(g for stage in strict.run_stages for g in stage)
    loose.run()
    same_outcomes(outcomes(loose), outcomes(strict))


def test_unscheduled_gates_are_slotted_in_topological_order():
    base = load('decoherence/double_slit_decoherence_chain')
    strict = Simulation(base)
    strict.run()
    cfg = deepcopy(base)
    # forget the whole detect stage and one recorder gate
    del cfg.run_stages['detect']
    cfg.run_stages['observe_2'] = []
    loose = Simulation(cfg, loose=True)
    names = list(loose.declared_run_stages)
    assert 'observe_2' not in names and 'detect' not in names
    # g_obs_2 slots in ahead of the first stage that depends on it, the
    # detectors go at the end
    assert loose.declared_run_stages['auto_1'] == ['g_obs_2']
    assert names.index('auto_1') < names.index('observe_3')
    assert names[-1] == 'auto_2' and set(loose.declared_run_stages['auto_2']) == {'D', 'S'}
    # g_obs_2 must still fire before g_obs_3 (its control-chain successor)
    order = [g for stage in loose.run_stages for g in stage]
    assert order.index('g_obs_2') < order.index('g_obs_3')
    loose.run()
    same_outcomes(outcomes(loose), outcomes(strict))


def p_at(sim: Simulation, gate: str, particle: str = 'p1') -> float:
    total = 0.0
    for point in sim.result_space.index.values():
        origin = point.coords[particle].position.origin
        if origin is not None and origin.gate == gate:
            total += float(point.probability)
    return total


def pull_gate(cfg: Addict, gate: str) -> Addict:
    """The builder's move: delete one gate and every link at it."""
    cfg = deepcopy(cfg)
    del cfg.gates[gate]
    cfg.links = {src: dst for src, dst in cfg.links.items()
                 if src.split('.')[0] != gate and dst.split('.')[0] != gate}
    return cfg


def test_pulling_a_recorder_pre_gate_out_of_the_chain():
    # Without g_pre_2, r2 has nowhere to start and bypass_2 nothing to
    # catch, but g_obs_2 still sits on p1's control chain — with an
    # empty upper wire it records nothing, so the screen is the chain
    # with the middle recorder fully bypassed: V = sin²θ₁·sin²θ₃.
    angles = {'theta_pre_1': 30, 'theta_pre_2': 60, 'theta_pre_3': 70}
    cfg = pull_gate(load('decoherence/double_slit_decoherence_chain', **angles),
                    'g_pre_2')
    with pytest.raises(ValueError):
        Simulation(cfg)
    probe = Simulation(cfg, loose=True)
    assert probe.dropped['particles'] == ['r2']
    assert probe.dropped['gates'] == ['bypass_2']
    assert 'g_obs_2' in probe.gates and 'r2' not in probe.particles
    assert probe.declared_run_stages['decoherence'] == \
        ['g_pre_1', 'g_pre_3', 'bypass_1', 'bypass_3']

    def screen(phi):
        c = deepcopy(cfg)
        c.variables.phi = f'{phi}°'
        sim = Simulation(c, loose=True)
        sim.run()
        return p_at(sim, 'S')
    bright, dark = screen(0), screen(180)
    visibility = (bright - dark) / (bright + dark)
    expected = math.prod(math.sin(math.radians(a)) ** 2
                         for a in (angles['theta_pre_1'], angles['theta_pre_3']))
    assert abs(visibility - expected) < TOL


def test_an_empty_circuit_runs_no_stages():
    cfg = load('gr2026/fig4.13')
    cfg.links = {}
    sim = Simulation(cfg, loose=True)
    assert sim.run_stages == [] and not sim.particles
    assert sim.dropped['gates'] == sorted(set(cfg.gates) | set(cfg.get('delay_gates', [])))
    sim.run()
    assert len(sim.result_space.index) == 1


def test_a_sub_circuit_with_its_own_particle_is_kept():
    # reachability, not connectedness: a recorder that never meets p1 is
    # still a (spectator) part of the model and runs
    cfg = load('gr2026/fig4.13')
    cfg.particles.r = Addict({'weight': 1, 'sign': 1})
    cfg.gates.g_r = Addict({'angle': '30°'})
    cfg.links.r = 'g_r.upper'
    sim = Simulation(cfg, loose=True)
    assert sim.dropped == {'particles': [], 'gates': [], 'links': []}
    assert 'g_r' in sim.gates and 'r' in sim.particles
    assert sim.declared_run_stages['auto_1'] == ['g_r']
    sim.run()
    assert abs(sum(float(p.probability)
                   for p in sim.result_space.index.values()) - 1) < TOL


def test_branching_particle_with_one_dead_arm_goes_the_other_way():
    base = load('gr2026/fig4.13')
    strict = Simulation(base)
    strict.run()
    cfg = deepcopy(base)
    entry = cfg.links.p1
    cfg.links.p1 = [entry, 'g_missing.control', 0.25]
    sim = Simulation(cfg, loose=True)
    assert sim.dropped['links'] == [f"p1: ['{entry}', 'g_missing.control', 0.25]"]
    assert sim.links['p1'] == entry and not sim.branch_specs
    sim.run()
    same_outcomes(outcomes(sim), outcomes(strict))
