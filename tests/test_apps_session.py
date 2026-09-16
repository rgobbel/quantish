"""quantish/apps/session.py: a model and a gate's split as values that
pass between the apps."""
from pathlib import Path

import pytest

from quantish.apps import builder_ui, explorer, session
from quantish.apps.common import load_config, model_files
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation
from quantish.util import Sign

MODELS = Path(__file__).resolve().parents[1] / 'models'
PATHS = model_files(MODELS)


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def ran(key):
    cfg, _ = load_config(PATHS[key], MODELS)
    sim = Simulation(cfg)
    sim.run()
    return sim


def test_model_slot_round_trip(tmp_path):
    loaded = builder_ui.loaded_model(PATHS['gr2026/fig4.17.yaml'].read_text(), 'fig4.17')
    cfg, problems = builder_ui.derive_config(
        loaded['graph'], title=loaded['title'], caption=loaded['caption'],
        model_vars=loaded['variables'], mode_label='-', unit_label='-',
        notes=loaded['model_notes'], extras=loaded['extras'],
        sweep_cfg=loaded['extras'].get('sweep'))
    assert problems == []
    slot = session.ModelSlot.from_builder(
        cfg, builder_ui.raw_sections(loaded['extras_text'], loaded['variables'],
                                     loaded['variables_text']), file='sent')
    assert slot.title == loaded['title'] and slot.model_id == 'uploads/sent'
    # over the defaults it runs like the original
    (tmp_path / 'defaults.yaml').write_text((MODELS / 'defaults.yaml').read_text())
    sim = Simulation(slot.to_config(tmp_path))
    sim.run()
    total = sum(float(p.probability) for p in sim.result_space.index.values())
    assert total == pytest.approx(1.0)
    assert len(sim.result_space.index) == len(ran('gr2026/fig4.17.yaml').result_space.index)
    # saved into the shared collection and known to the lab's catalog
    path = slot.save(tmp_path)
    assert path == tmp_path / 'uploads' / 'sent.yaml' and path.read_text() == slot.yaml_text
    from quantish import screen
    assert 'uploads/sent' in screen.library()
    again = session.ModelSlot.from_file(path)
    assert again.model == slot.model and again.file == 'sent'


def test_seed_from_run_matches_the_gate():
    sim = ran('gr2026/fig4.04.yaml')
    gate = next(iter(sim.fredkin_gates))
    weights = session.incoming_weights(sim, gate)
    assert weights and all(k[1] in (Sign.plus, Sign.minus) for k in weights)
    seed = session.ExplorerSeed.from_run(sim, gate)
    assert seed is not None and seed.gate == gate and seed.model == sim.title
    assert seed.theta_deg == pytest.approx(float(sim.fredkin_gates[gate].theta.degrees))
    w = weights[(seed.particle, Sign.plus if seed.plus_sign else Sign.minus)]
    assert seed.weight == pytest.approx(w, abs=1e-9)
    # the explorer's split of the seed sums back to the arriving weight
    parts = explorer.split_components(seed.theta_deg, seed.weight, seed.plus_sign)
    assert parts['c2'] + parts['c3'] == pytest.approx(w, abs=1e-9)
    assert (seed.particle, 1 if seed.plus_sign else -1) in seed.arrivals
    # a particle nothing arrives from, or a non-gate, gives nothing
    assert session.ExplorerSeed.from_run(sim, 'no_such_gate') is None
    assert 'entering' in seed.describe() and seed.as_controls()['theta_deg'] == seed.theta_deg


def test_seed_query_round_trip():
    seed = session.ExplorerSeed(theta_deg=-30, wmag=0.5, wphase_deg=90, plus_sign=False,
                                gate='g2', particle='p1', model='Fig')
    q = seed.to_query()
    back = session.ExplorerSeed.from_query(q)
    assert back.as_controls() == seed.as_controls()
    assert (back.gate, back.particle, back.model) == ('g2', 'p1', 'Fig')
    assert session.ExplorerSeed.from_query({}) is None
    assert session.ExplorerSeed.from_query(None) is None
    assert session.ExplorerSeed.from_query({'theta': 'x'}) is None
    url = session.explorer_url(seed)
    assert url.startswith('../weight_split_app/?theta=-30') and 'sign=-' in url
    # the explorer's controls open on the seed's grid values
    ctl = explorer.explorer_controls(back.as_controls())
    assert ctl.value['theta'] == -30 and ctl.value['sign'] is False
    assert ctl.value['wmag'] == pytest.approx(0.5) and ctl.value['wphase'] == 90
