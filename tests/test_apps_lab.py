"""quantish/apps/lab.py: a decoherence-lab slot built, driven, and
read out without a notebook."""
import pytest

from quantish.apps import lab
from quantish.qnumber import CalcMode
from quantish.screen import library


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield


@pytest.fixture(scope='module')
def eraser_id():
    ids = [m for m in library() if 'eraser' in m and 'chain' not in m]
    assert ids, list(library())
    return ids[0]


def test_slot_lifecycle(eraser_id):
    hits = {'seq': 0, 'hits': {}}
    assert lab.make_slot('A', '', None, hits) is None
    editor = lab.make_screen_editor(eraser_id)
    over = lab.screen_override(editor)
    assert over['plate'] and over['observe']['particle']
    state = lab.make_slot('A', eraser_id, editor, hits)
    assert hits['hits']['A'] == [] and state['panel'] is not None
    sliders, details = lab.make_controls(state)
    assert set(sliders.elements) == set(state['spec'].variables)
    variables = lab.update_slot(state, sliders, 21, 3, 'fit', hits)
    assert set(variables) == set(state['spec'].variables)
    assert state['grain'] == 21 and len(state['panel'].curves['x']) == 21
    assert 'visibility' in state['readout'].html
    assert '<svg' in state['strips'].html and 'stage' in state['stages'].html
    assert state['graph'].model
    # every particle off: the views say so, the screen is flat
    for p in state['particle_names']:
        state['ptoggles'].elements[p]._value = False
    lab.update_slot(state, sliders, 21, 3, 'fit', hits)
    assert 'nothing enters' in state['readout'].html
    assert set(state['panel'].curves['y']) == {0.0}
    hits['hits']['A'].append((0.1, 0.2))
    lab.refresh_panel(state, hits)
    assert state['panel'].data['hits'] == [[0.1, 0.2]]


def test_readout_and_pretty(eraser_id):
    from quantish.screen import ScreenSpec
    spec = ScreenSpec.load(eraser_id)
    text = lab.readout_text(spec, {'all': [0.0, 1.0, 0.0]}, inert=('g_x',))
    assert 'visibility: <b>1.0000</b>' in text and 'gates off: g_x' in text
    assert lab.readout_text(spec, {'all': [0.0, 0.0]}).count('—') >= 2
    for var in spec.variables:
        assert '(°)' in lab.pretty(spec, var) and ' ' not in lab.pretty(spec, var)
