"""The builder round-trips model-level metadata: angle_unit, notes,
calculation mode, and degree-marked angle specs all survive
config -> graph -> config -> YAML -> config unchanged."""
import yaml

from quantish.builder import (
    angle_degrees,
    config_to_graph,
    config_to_yaml,
    graph_to_config,
    loose_ends,
    validate_graph,
)

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
    # the model names the plate bare; the canvas wires its control port
    assert ['g1.upper', 'pp.control'] in graph['links']
    assert ['pp.control', 'g2.upper'] in graph['links']
    assert not any('phase plate' in p
                   for p in validate_graph(graph, angle_unit='degrees'))
    out = graph_to_config(graph, cfg['title'],
                          angle_unit=cfg['angle_unit'])
    back = yaml.safe_load(config_to_yaml(out))
    assert back['phase_plates'] == {'pp': '30°'}
    assert 'pp' not in back['gates']
    assert back['links'] == {'p1': 'g1.upper', 'g1.upper': 'pp',
                             'pp': 'g2.upper'}
    # the explicit port form still reads, and comes back bare
    cfg2 = dict(cfg)
    cfg2['links'] = {'p1': 'g1.upper', 'g1.upper': 'pp.control',
                     'pp.control': 'g2.upper'}
    graph2, _ = config_to_graph(cfg2)
    assert graph2['links'] == graph['links']
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


def test_unhandled_sections_survive_a_save():
    """Nothing is lost when a model is saved from the builder: sections
    it does not edit (a sweep declaration, epr_stats, …) ride through
    config -> graph -> config -> YAML -> config verbatim."""
    from pathlib import Path

    from quantish.builder import config_extras
    models = Path(__file__).resolve().parents[1] / 'models' / 'decoherence'
    with open(models / 'double_slit_eraser.yaml') as f:
        cfg = yaml.safe_load(f)
    cfg['epr_stats'] = False
    cfg['loglevel'] = 'warning'
    extras = config_extras(cfg)
    assert set(extras) == {'sweep', 'epr_stats', 'loglevel'}
    graph, _ = config_to_graph(cfg)
    out = graph_to_config(graph, cfg['title'], caption=cfg['caption'],
                          variables=cfg['variables'], notes=cfg['notes'],
                          extras=extras)
    back = yaml.safe_load(config_to_yaml(out))
    assert back['sweep'] == cfg['sweep']
    assert back['epr_stats'] is False and back['loglevel'] == 'warning'
    # and the handled sections are still the builder's own
    assert back['links'] == cfg['links'] and back['gates'] == cfg['gates']
    # extras never override a handled key
    out2 = graph_to_config(graph, 'T', extras={'title': 'X', 'sweep': {}})
    assert out2['title'] == 'T' and out2['sweep'] == {}


def test_unhandled_sections_keep_their_comments():
    """With the loaded file's text at hand, an unhandled section is
    written back verbatim — its comments included."""
    from pathlib import Path

    from quantish.builder import config_extras, extract_sections
    path = (Path(__file__).resolve().parents[1] / 'models' / 'decoherence'
            / 'double_slit_eraser.yaml')
    text = path.read_text()
    cfg = yaml.safe_load(text)
    sections = extract_sections(text)
    assert list(sections)[:3] == ['title', 'caption', 'notes']
    assert sections['sweep'].startswith('# the screen: P(p1 at S)')
    assert sections['sweep'].rstrip().endswith('coordinate: sign}')
    graph, _ = config_to_graph(cfg)
    out = graph_to_config(graph, cfg['title'], variables=cfg['variables'],
                          extras=config_extras(cfg))
    txt = config_to_yaml(out, raw_sections=sections)
    assert sections['sweep'] in txt
    assert yaml.safe_load(txt)['sweep'] == cfg['sweep']
    # a section the text lacks still comes out, dumped from its value
    out['epr_stats'] = True
    assert '\nepr_stats: true\n' in config_to_yaml(out, raw_sections=sections)


def test_extract_sections_edge_cases():
    from quantish.builder import extract_sections
    text = """# file header
title: T

# about the list
items:
  - a   # inline
  # inner comment

  - b

# trailing comment for k2

k2: {x: 1}
k3: v
"""
    s = extract_sections(text)
    assert list(s) == ['title', 'items', 'k2', 'k3']
    assert s['title'] == '# file header\ntitle: T'
    assert s['items'] == ('# about the list\nitems:\n  - a   # inline\n'
                          '  # inner comment\n\n  - b')
    assert s['k2'] == '# trailing comment for k2\n\nk2: {x: 1}'
    assert s['k3'] == 'k3: v'


def test_variables_editor_comments_survive_a_save():
    """Comments a user writes in the builder's variables editor come out
    in the saved file, and a file's variable comments arrive in the
    editor: section_body / variables_block round-trip them."""
    from quantish.builder import section_body, variables_block
    text = """# leading comment (belongs to the key, not the body)
variables:
  # the measurement angles
  theta1: pi/8   # radians
  theta2: '30°'

  phi: 0
"""
    body = section_body(text.rstrip())
    assert body == ("# the measurement angles\ntheta1: pi/8   # radians\n"
                    "theta2: '30°'\n\nphi: 0")
    assert yaml.safe_load(body) == {'theta1': 'pi/8', 'theta2': '30°',
                                    'phi': 0}
    edited = body + "\n# added in the editor\ntheta3: 1  # new"
    cfg = dict(CONFIG)
    cfg['variables'] = yaml.safe_load(edited)
    graph, _ = config_to_graph(cfg)
    out = graph_to_config(graph, cfg['title'], variables=cfg['variables'])
    txt = config_to_yaml(out, raw_sections={'variables': variables_block(edited)})
    assert '  # added in the editor\n  theta3: 1  # new' in txt
    assert '  theta1: pi/8   # radians' in txt
    assert yaml.safe_load(txt)['variables'] == cfg['variables']
    # without the editor text the section is regenerated as before
    assert '# added' not in config_to_yaml(out)


def test_loose_mode_tolerates_loose_ends_and_rides_into_the_yaml():
    # an orphan gate and an unlinked particle: strict problems, loose fine
    graph = {
        'gates': {'g1': {'angle': '30°'}, 'g_orphan': {'angle': '10°'}},
        'particles': {'p1': {'sign': 1, 'weight': 1}, 'p_lost': {'sign': 1, 'weight': 1}},
        'links': [['p1', 'g1.upper']],
    }
    strict = validate_graph(graph)
    assert strict == ['particle p_lost is not connected to anything',
                      'gate g_orphan has no inputs']
    assert loose_ends(graph) == strict
    assert validate_graph(graph, loose=True) == []
    config = graph_to_config(graph, 'Loose', loose=True)
    assert config['loose'] is True
    assert 'g_orphan' in config['gates'] and 'p_lost' in config['particles']
    text = config_to_yaml(config)
    assert 'loose: true' in text
    back = yaml.safe_load(text)
    assert back['loose'] is True
    # the engine loads it loosely, dropping exactly the loose ends
    from addict import Dict as Addict

    from quantish.simulation import Simulation
    sim = Simulation(Addict({'loglevel': 'warning', **back}))
    assert sim.loose and sim.dropped['gates'] == ['g_orphan']
    assert sim.dropped['particles'] == ['p_lost']
    # and the builder opens it with every declared element on the canvas
    graph2, _notes = config_to_graph(back)
    assert set(graph2['gates']) == {'g1', 'g_orphan'}
    assert set(graph2['particles']) == {'p1', 'p_lost'}
    assert graph2['gates']['g_orphan']['angle'] == '10°'
    # strict mode still refuses the same file
    strict_cfg = {k: v for k, v in back.items() if k != 'loose'}
    import pytest
    with pytest.raises(ValueError):
        config_to_graph(strict_cfg)
