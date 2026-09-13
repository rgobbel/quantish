"""A model that declares no run_stages runs anyway, in wiring order —
one stage per topological layer — flagged for the apps to notice."""
import logging

from addict import Dict as Addict

from quantish.builder import config_to_graph
from quantish.model_schema import validate_model
from quantish.qnumber import CalcMode
from quantish.screen import ScreenSpec
from quantish.simulation import Simulation


def test_missing_run_stages_are_derived_from_the_wiring(caplog):
    CalcMode.default('Float')
    cfg = ScreenSpec.load('extras/double_slit').config_with({})
    declared = Simulation(cfg)
    declared.run()
    del cfg['run_stages']
    validate_model(dict(cfg))                       # the schema allows it
    with caplog.at_level(logging.WARNING, logger='quantish'):
        derived = Simulation(Addict(cfg))
    assert derived.run_stages_derived and not declared.run_stages_derived
    assert any('declares no run_stages' in r.message for r in caplog.records)
    assert list(derived.declared_run_stages) == [f'stage_{i}' for i in
                                                 range(1, len(derived.declared_run_stages) + 1)]
    assert sorted(g for gs in derived.declared_run_stages.values() for g in gs) == sorted(declared.gates)
    derived.run()
    a = {p.key: complex(p.weight) for p in declared.result_space.index.values()}
    b = {p.key: complex(p.weight) for p in derived.result_space.index.values()}
    assert a.keys() == b.keys() and all(abs(a[k] - b[k]) < 1e-12 for k in a)
    # the builder loads it too, and says what it did
    graph, notes = config_to_graph(Addict({**dict(cfg), 'loglevel': 'error'}))
    assert graph['stage_order'] and any('no run_stages declared' in n for n in notes)
