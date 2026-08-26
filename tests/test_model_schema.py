"""Every model YAML validates against models/schema.yaml, and the
schema actually rejects malformed configs (it isn't vacuously true)."""
from pathlib import Path

import pytest
import yaml

from quantish.model_schema import validate_defaults, validate_model

MODELS_TOP = Path(__file__).parent.parent / 'models'
MODEL_FILES = sorted(
    p for p in MODELS_TOP.rglob('*.yaml')
    if p.name not in ('defaults.yaml', 'schema.yaml')
    and not p.name.startswith('.'))


@pytest.mark.parametrize('path', MODEL_FILES,
                         ids=[str(p.relative_to(MODELS_TOP))
                              for p in MODEL_FILES])
def test_model_validates(path):
    with open(path) as f:
        config = yaml.safe_load(f)
    assert validate_model(config) == []


def test_defaults_validate():
    with open(MODELS_TOP / 'defaults.yaml') as f:
        config = yaml.safe_load(f)
    assert validate_defaults(config) == []


def test_schema_rejects_bad_configs():
    good = {'title': 't', 'run_stages': {'s1': ['g1']},
            'particles': {'p1': {'sign': 1, 'weight': '1+0j'}},
            'gates': {'g1': {'angle': 'rad(30)'}},
            'links': {'p1': 'g1.upper'}}
    assert validate_model(good) == []
    for breakage in (
            lambda c: c.pop('title'),
            lambda c: c.update(unknown_option=True),
            lambda c: c['particles']['p1'].pop('sign'),
            lambda c: c['particles']['p1'].update(colour='red'),
            lambda c: c['gates']['g1'].pop('angle'),
            lambda c: c['run_stages'].update(s2='g1'),  # not a list
            lambda c: c.update(symbolic='yes')):        # not a bool
        bad = {k: (dict(v) if isinstance(v, dict) else v)
               for k, v in good.items()}
        bad['particles'] = {'p1': dict(good['particles']['p1'])}
        bad['gates'] = {'g1': dict(good['gates']['g1'])}
        bad['run_stages'] = dict(good['run_stages'])
        breakage(bad)
        assert validate_model(bad) != [], breakage


def test_angle_unit_degrees():
    """A plain-number gate angle reads in angle_unit; expression specs
    are never converted."""
    import math

    from addict import Addict

    from quantish.qnumber import CalcMode
    from quantish.simulation import Simulation

    CalcMode.default('Float')
    base = {'title': 't', 'run_stages': {'s1': ['g1']},
            'particles': {'p1': {'sign': 1, 'weight': '1+0j'}},
            'links': {'p1': 'g1.upper'}}
    deg = Simulation(Addict({**base, 'angle_unit': 'degrees',
                             'gates': {'g1': {'angle': 30}}}))
    rad = Simulation(Addict({**base,
                             'gates': {'g1': {'angle': 'rad(30)'}}}))
    assert math.isclose(float(deg.fredkin_gates['g1'].theta),
                        float(rad.fredkin_gates['g1'].theta))
    # an expression spec is untouched even under degrees
    expr = Simulation(Addict({**base, 'angle_unit': 'degrees',
                              'gates': {'g1': {'angle': 'pi/6'}}}))
    assert math.isclose(float(expr.fredkin_gates['g1'].theta),
                        math.pi / 6)
    assert validate_model({**base, 'angle_unit': 'degrees',
                           'gates': {'g1': {'angle': 30}}}) == []
    assert validate_model({**base, 'angle_unit': 'turns',
                           'gates': {'g1': {'angle': 30}}}) != []
    assert validate_model({**base, 'calculation_mode': 'Float',
                           'notes': 'free text',
                           'gates': {'g1': {'angle': 30}}}) == []


def test_degree_marked_angle_spec():
    """A '30°' angle string reads as degrees regardless of angle_unit."""
    import math

    from addict import Addict

    from quantish.qnumber import CalcMode
    from quantish.simulation import Simulation

    CalcMode.default('Float')
    base = {'title': 't', 'run_stages': {'s1': ['g1']},
            'particles': {'p1': {'sign': 1, 'weight': 1}},
            'links': {'p1': 'g1.upper'}}
    marked = Simulation(Addict({**base,
                                'gates': {'g1': {'angle': '30°'}}}))
    assert math.isclose(float(marked.fredkin_gates['g1'].theta),
                        math.radians(30))
