"""quantish/apps/builder_ui.py: the builder's library side — a loaded
model, the canvas's translation, the run, sweep, and table — driven
without a notebook."""
from pathlib import Path

import marimo as mo
import pytest

from quantish.apps import builder_ui
from quantish.apps.common import model_files
from quantish.qnumber import CalcMode

MODELS = Path(__file__).resolve().parents[1] / 'models'
PATHS = model_files(MODELS)


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def load(key):
    return builder_ui.loaded_model(PATHS[key].read_text(), key)


def derive(loaded, **over):
    kw = dict(title=loaded['title'], caption=loaded['caption'],
              model_vars=loaded['variables'],
              mode_label=builder_ui.MODE_LABELS[loaded['symbolic']],
              unit_label=loaded['angle_unit'] or '-', notes=loaded['model_notes'],
              extras=loaded['extras'], sweep_cfg=loaded['extras'].get('sweep'))
    kw.update(over)
    return builder_ui.derive_config(loaded['graph'], **kw)


def test_tri_mode():
    assert builder_ui.tri_mode({'calculation_mode': 'Symbolic'}) is True
    assert builder_ui.tri_mode({'calculation_mode': 'float'}) is False
    assert builder_ui.tri_mode({'symbolic': True}) is True
    assert builder_ui.tri_mode({}) is None
    for k, v in builder_ui.MODE_LABELS.items():
        assert builder_ui.MODE_VALUES[v] is k


def test_new_and_loaded_model():
    fresh = builder_ui.new_model()
    assert builder_ui.canvas_counts(fresh['graph']) == (0, 0)
    assert builder_ui.loaded_report(fresh).text
    assert builder_ui.loaded_report(None) is None
    m = load('gr2026/fig4.17.yaml')
    assert m['file'] == 'fig4.17' and m['title']
    assert builder_ui.canvas_counts(m['graph'])[0] > 0
    assert 'variables' in m['extras_text'] or m['variables_text'] == ''
    with pytest.raises(Exception):
        builder_ui.loaded_model('gates: [', 'bad.yaml')


def test_model_options_one_collection():
    opts = builder_ui.model_options(PATHS, 'gr2026')
    assert all(k.startswith('gr2026/') for k in opts.values())
    assert 'gr2026/fig4.17.yaml' in opts.values()
    assert builder_ui.model_options(PATHS, None) == {}


def test_derive_run_and_table():
    m = load('gr2026/fig4.17.yaml')
    cfg, problems = derive(m)
    assert problems == [] and cfg['run_stages']
    labels = builder_ui.angle_labels(m['graph'], m['variables'], '-')
    assert labels and not any(v.startswith('⚠') for v in labels.values())
    gates, particles = builder_ui.run_order(m['graph'])
    assert set(gates) <= set(m['graph']['gates']) and particles
    status = builder_ui.status_view(m['graph'], problems, cfg)
    assert 'runnable. Stages' in status.text
    off = {**{f'g:{g}': True for g in gates}, **{f'p:{p}': True for p in particles}}
    sim, report = builder_ui.run_network(cfg, off)
    assert sim is not None and 'total probability 1.000000' in report.text
    table = builder_ui.final_points_html(sim)
    assert table.count('<tr') > 1
    assert builder_ui.run_network(None, off) == (None, None)
    # a particle off is absent from the run and named in the report
    off2 = {**off, f'p:{particles[0]}': False}
    sim2, report2 = builder_ui.run_network(cfg, off2)
    assert particles[0] in sim2.absent and 'particles off' in report2.text
    sections = builder_ui.raw_sections(m['extras_text'], m['variables'], 'a: 1')
    assert 'sweep' not in sections and ('variables' in sections) == bool(m['variables'])


def test_problems_and_all_off():
    m = load('gr2026/fig4.17.yaml')
    cfg, problems = derive(m, all_particles_off=True)
    assert cfg is None and any('switched off' in p for p in problems)
    view = builder_ui.status_view(m['graph'], problems, None)
    assert 'not-runnable' in view.text
    empty = builder_ui.new_model()
    cfg, problems = derive(empty)
    assert cfg is None and problems


def test_sweep_declared_and_run():
    m = load('decoherence/double_slit_tunable.yaml')
    cfg, problems = derive(m)
    assert problems == [] and cfg.get('sweep')
    bad = dict(cfg['sweep'], variable='no_such_variable')
    cfg2, problems2 = derive(m, sweep_cfg=bad)
    assert cfg2 is None and problems2[0].startswith('sweep:')
    gates, particles = builder_ui.run_order(m['graph'])
    off = {**{f'g:{g}': True for g in gates}, **{f'p:{p}': True for p in particles}}
    small = dict(cfg['sweep'], points=3)
    view = builder_ui.run_sweep(cfg, small, off, degrees=False)
    assert '3 points' in view.text
    assert builder_ui.run_sweep(None, small, off, False).text == mo.md('').text
