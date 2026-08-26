"""The builder round-trips model-level metadata: angle_unit, notes,
calculation mode, and degree-marked angle specs all survive
config -> graph -> config -> YAML -> config unchanged."""
import yaml

from quantish.builder import (angle_degrees, config_to_graph,
                              config_to_yaml, graph_to_config,
                              validate_graph)

CONFIG = {
    'title': 'Round trip',
    'notes': 'first line\nsecond: line',
    'calculation_mode': 'float',
    'angle_unit': 'degrees',
    'run_stages': {'s1': ['g1'], 's2': ['g2']},
    'particles': {'p1': {'sign': 1, 'weight': 1}},
    'gates': {'g1': {'angle': 30}, 'g2': {'angle': '45°'}},
    'links': {'p1': 'g1.upper', 'g1.upper': 'g2.upper'},
}


def test_metadata_round_trip():
    graph, notes = config_to_graph(CONFIG)
    assert notes == []
    out = graph_to_config(
        graph, CONFIG['title'], notes=CONFIG['notes'],
        symbolic=False, angle_unit=CONFIG['angle_unit'])
    back = yaml.safe_load(config_to_yaml(out))
    for key in ('title', 'notes', 'calculation_mode', 'angle_unit'):
        assert back[key] == CONFIG[key], key
    # specs verbatim: the plain number and the degree-marked string
    assert back['gates']['g1']['angle'] == 30
    assert back['gates']['g2']['angle'] == '45°'


def test_angle_degrees_reads_unit():
    assert angle_degrees(30, unit='degrees') == 30.0
    assert abs(angle_degrees(30, unit='radians')
               - 1718.8733853924696) < 1e-9
    assert angle_degrees('45°', unit='radians') == 45.0


def test_validate_graph_respects_unit():
    graph, _ = config_to_graph(CONFIG)
    assert validate_graph(graph, angle_unit='degrees') == []
    # read as radians, 30 is more than a full turn — the tripwire fires
    assert any('full turn' in p
               for p in validate_graph(graph, angle_unit='radians'))
