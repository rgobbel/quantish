"""quantish/apps/run.py, results.py, sampling.py, epr_ui.py: the
quantish app's library side, driven without a notebook."""
from pathlib import Path

import marimo as mo
import pytest

from quantish.apps import epr_ui, results, run, sampling
from quantish.apps.common import model_files
from quantish.qnumber import CalcMode

MODELS = Path(__file__).resolve().parents[1] / 'models'
FIG44 = model_files(MODELS)['gr2026/fig4.17.yaml']   # any model does for the run side
FIG417 = model_files(MODELS)['gr2026/fig4.17.yaml']


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


def test_model_angles_and_build_sim():
    seed = run.model_angles(FIG44, {})
    assert seed['problem'] is None and seed['gates'] and seed['particles']
    assert set(seed['angles']) == set(seed['gates'])
    for cur in seed['angles'].values():
        assert -180 < cur['deg'] <= 180 and cur['deg'] * 2 == int(cur['deg'] * 2)
    bad = run.model_angles(FIG44, {'nonsense': 'sqrt('})
    assert bad['problem'] and bad['gates'] == seed['gates']
    off = {f'g:{g}': True for g in seed['gates']} | {f'p:{p}': True for p in seed['particles']}
    sim = run.build_sim(FIG44, {}, 'Float', seed['angles'], off, seed['env'])
    sim.run()
    assert abs(sum(float(p.probability) for p in sim.result_space.index.values()) - 1) < 1e-9
    g = seed['gates'][0]
    sim2 = run.build_sim(FIG44, {}, 'Float', seed['angles'], {**off, f'g:{g}': False}, seed['env'])
    assert g in sim2.inert
    # the angle spec per mode: an expression stays a string, degrees stay exact in Symbolic
    assert run.gate_angle({'deg': 30.0, 'expr': 'pi/6'}, 'Float', {}) == 'pi/6'
    assert run.gate_angle({'deg': 30.0, 'expr': None}, 'Symbolic', {}) == '30.0°'
    assert run.gate_angle({'deg': 90.0, 'expr': None}, 'Float', {}) == pytest.approx(1.5707963)


def test_typed_and_shown_angles():
    assert run.typed_angle('45', 'degrees', {}) == (45.0, None)
    assert run.typed_angle('45°', 'radians', {}) == (45.0, None)
    assert run.typed_angle('pi/4', 'degrees', {}) == (pytest.approx(45.0), 'pi/4')
    assert run.typed_angle('', 'degrees', {}) is None
    assert run.typed_angle('sqrt(', 'degrees', {}) is None
    assert run.shown_angle({'deg': 45.0, 'expr': None}, 'Float', 'degrees') == '45.0º'
    assert run.shown_angle({'deg': 45.0, 'expr': 'pi/4'}, 'Symbolic', 'degrees') == 'pi/4'
    assert run.shown_angle({'deg': 180.0, 'expr': None}, 'Float', 'radians') == '3.1416'


def test_angle_widgets_drive_the_state():
    seed = run.model_angles(FIG44, {})
    get, set_ = mo.state(seed['angles'])
    g = seed['gates'][0]
    off = {f'g:{g}': False}
    sliders = run.angle_sliders(get, set_, seed['gates'], off)
    entries = run.angle_entries(get, set_, seed['gates'], off, 'Float', 'degrees', seed['env'])
    assert set(sliders.elements) == set(entries.elements) == set(seed['gates'])
    assert all(w.elements[g]._component_args['disabled'] for w in (sliders, entries))
    sliders.elements[g]._on_change(12.5)
    assert get()[g] == {'deg': 12.5, 'expr': None}
    entries.elements[g]._on_change('pi/3')
    assert get()[g]['expr'] == 'pi/3' and get()[g]['deg'] == pytest.approx(60.0)


def test_detailed_results_render():
    seed = run.model_angles(FIG44, {})
    sim = run.build_sim(FIG44, {}, 'Float', seed['angles'], {}, seed['env'])
    sim.run()
    for fn in (results.evolution_table, results.final_points, results.marginals,
               results.gate_io_table, results.detailed_results):
        html = fn(sim).text
        assert '<' in html and len(html) > 100
    assert 'Step 1' in results.evolution_table(sim).text


def test_sampling_job_and_views():
    seed = run.model_angles(FIG44, {})
    sim = run.build_sim(FIG44, {}, 'Float', seed['angles'], {}, seed['env'])
    sim.run()
    boxes = mo.ui.dictionary({k: mo.ui.checkbox(value=k.startswith('pilot'))
                              for k in sampling.SAMPLER_LABELS})
    assert sampling.picked_modes(boxes, sampling.SAMPLER_LABELS) == ['pilot']
    assert sampling.trial_count(' 7 ', 100) == 7 and sampling.trial_count('x', 100) == 100
    assert sampling.trial_count('1e6', 100) == sampling.trial_count('1,000,000', 100) == 1_000_000
    secs = sampling.sampling_seconds(sim, ['terminal', 'pilot'], 1000)
    assert secs > 0 and 'Predicted runtime' in sampling.projection(secs).text
    assert 'ff1f1f' in sampling.projection(sampling.LONG_RUN_SECONDS + 1).text
    assert 'for 1,000,000 trials' in sampling.projection(2.0, 1_000_000).text
    job = sampling.new_job(sim, 3000, ['terminal', 'pilot'])
    ticks, bumps = [], []
    assert 'progress' in sampling.progress_view(job, mo.ui.button()).text
    sampling.run_job(job, 1, bumps.append, tick=ticks.append)
    assert job['done'] and job['error'] is None and not bumps
    assert sum(ticks) == 6000 and job['n_done'] == {'terminal': 3000, 'pilot': 3000}
    html = sampling.results_view(job).text
    assert 'terminal' in html and 'pilot' in html and 'total variation distance' in html
    job = sampling.new_job(sim, 500, ['terminal'])
    sampling.run_job(job, 1, bumps.append)
    assert job['done'] and bumps
    # the WASM worker: a coroutine yielding between chunks; a cancel
    # set from outside stops it at the next chunk with partial tallies
    import asyncio
    job = sampling.new_job(sim, 10000, ['terminal', 'pilot'])

    async def cancel_soon():
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        job['cancel'].set()

    async def both():
        await asyncio.gather(sampling.run_job_async(job, 1, bumps.append), cancel_soon())
    asyncio.run(both())
    assert job['done'] and job['error'] is None and job['cancel'].is_set()
    assert 0 < job['n_done']['terminal'] <= 10000
    assert 'canceled' in sampling.results_view(job).text


def test_epr_report():
    seed = run.model_angles(FIG417, {})
    sim = run.build_sim(FIG417, {}, 'Float', seed['angles'], {}, seed['env'])
    entries = epr_ui.epr_angle_entries({'qa': '0', 'qb': 'pi/8', 'qc': 'pi/4'})
    assert set(entries.value) == {'qa', 'qb', 'qc'}
    html = epr_ui.epr_report(sim, entries.value, 0, [], 'degrees', seed['env']).text
    assert 'Bell excess (exact)' in html and 'VIOLATED' in html and 'sampled' not in html
    html = epr_ui.epr_report(sim, {'qa': '0', 'qb': '22.5', 'qc': '45'}, 200,
                             ['hidden'], 'degrees', seed['env']).text
    assert 'sampled results: 200 trials' in html
    bad = epr_ui.epr_report(sim, {'qa': '0', 'qb': '0', 'qc': '45'}, 0, [], 'degrees', {}).text
    assert 'distinct' in bad
    assert float(epr_ui.parse_angle('45', 'degrees', {})) == pytest.approx(0.7853981)
