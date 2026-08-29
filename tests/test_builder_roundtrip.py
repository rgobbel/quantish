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


def test_display_string_round_trip():
    # one top-level dict names every kind of object, delays included
    cfg = dict(CONFIG)
    cfg['run_stages'] = {'s1': ['g1'], 's2': ['g2', 'd1']}
    cfg['links'] = {'p1': 'g1.upper', 'g1.upper': 'g2.upper',
                    'g1.control': 'd1'}
    cfg['delay_gates'] = ['d1']
    cfg['display_strings'] = {'g1': '$g_{split}$', 'p1': '$p_1$',
                              'd1': '$delay_1$'}
    graph, notes = config_to_graph(cfg)
    assert notes == []
    assert graph['gates']['g1']['display_string'] == '$g_{split}$'
    assert graph['gates']['d1']['display_string'] == '$delay_1$'
    assert graph['particles']['p1']['display_string'] == '$p_1$'
    out = graph_to_config(graph, cfg['title'],
                          angle_unit=cfg['angle_unit'])
    back = yaml.safe_load(config_to_yaml(out))
    assert back['display_strings'] == cfg['display_strings']
    assert 'display_string' not in back['gates']['g1']
    assert 'display_string' not in back['particles']['p1']


def test_phase_plate_round_trip():
    cfg = dict(CONFIG)
    cfg['run_stages'] = {'s1': ['g1'], 'plate': ['pp'], 's2': ['g2']}
    cfg['links'] = {'p1': 'g1.upper', 'g1.upper': 'pp',
                    'pp': 'g2.upper'}
    cfg['phase_plates'] = {'pp': '30°'}
    graph, notes = config_to_graph(cfg)
    assert notes == []
    assert graph['gates']['pp'] == {
        **graph['gates']['pp'], 'kind': 'phase', 'phase': '30°'}
    out = graph_to_config(graph, cfg['title'],
                          angle_unit=cfg['angle_unit'])
    back = yaml.safe_load(config_to_yaml(out))
    assert back['phase_plates'] == {'pp': '30°'}
    assert 'pp' not in back['gates']
    # read as radians, 30 is more than a full turn — the tripwire fires
    assert any('full turn' in p
               for p in validate_graph(graph, angle_unit='radians'))


def test_validate_graph_checks_particle_weights():
    graph, _ = config_to_graph(CONFIG)
    graph['particles']['p1']['weight'] = '0.5+0.87j'
    assert validate_graph(graph, angle_unit='degrees') == []
    graph['particles']['p1']['weight'] = 'bogus_name'
    problems = validate_graph(graph, angle_unit='degrees')
    assert any('p1' in pr and 'weight' in pr for pr in problems)


def test_branching_particle_round_trip():
    cfg = dict(CONFIG)
    cfg['run_stages'] = {'s1': ['g1', 'g2']}
    cfg['links'] = {'p1': ['g1.upper', 'g2.upper', 0.25]}
    graph, notes = config_to_graph(cfg)
    assert notes == []
    assert [l for l in graph['links'] if l[0] == 'p1'] == \
        [['p1', 'g1.upper'], ['p1', 'g2.upper']]
    assert graph['branches'] == {'p1': 0.25}
    assert validate_graph(graph, angle_unit='degrees') == []
    out = graph_to_config(graph, cfg['title'], angle_unit=cfg['angle_unit'])
    back = yaml.safe_load(config_to_yaml(out))
    assert back['links']['p1'] == ['g1.upper', 'g2.upper', 0.25]
    # three arms is one too many
    graph['links'].append(['p1', 'g1.lower'])
    assert any('two ways at most' in pr
               for pr in validate_graph(graph, angle_unit='degrees'))
