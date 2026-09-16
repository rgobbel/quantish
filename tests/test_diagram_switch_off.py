"""A switched-off gate in the circuit drawing: grayed, crossed out, and
its wires drawn straight through it (the gate is a plain wire for the
run), with the dotted switch X gone."""
from pathlib import Path

import yaml
from addict import Dict as Addict

from quantish.diagram_layout import DISABLED_X, WIRE_COLOR, dead_sources, diagram_geometry
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation

MODELS = Path(__file__).resolve().parents[1] / 'models'


def _sim():
    CalcMode.default('Float')
    cfg = yaml.safe_load((MODELS / 'gr2026' / 'fig4.17.yaml').read_text())
    cfg['loglevel'] = 'warning'
    return Simulation(Addict(cfg))


def _marks(g, color):
    return [m for m in g['marks'] if m['stroke'] == color]


def test_pass_through_lines_for_a_switched_off_gate():
    sim = _sim()
    fed = set(sim.links.values())

    def wired_wires(g):
        return [w for w in ('control', 'upper', 'lower')
                if f'{g}.{w}' in fed and f'{g}.{w}' in sim.links]

    # a gate with at least one wire fed in and linked onward
    gate = next(g for g in sim.fredkin_gates if wired_wires(g))
    on = diagram_geometry(sim)
    off = diagram_geometry(sim, disabled=(gate,))
    assert not _marks(on, WIRE_COLOR)
    thru = _marks(off, WIRE_COLOR)
    # one horizontal line per wire that is fed at the input and linked
    # onward at the output, frame edge to frame edge, distinct rows
    wired = wired_wires(gate)
    assert 1 <= len(wired) <= 3
    assert len(thru) == len(wired)
    assert all(m['y'] == m['y2'] for m in thru)
    assert len({m['y'] for m in thru}) == len(wired)
    xs = {(m['x'], m['x2']) for m in thru}
    assert len(xs) == 1
    left, right = xs.pop()
    assert right > left
    # the bold X spans the same frame and is drawn after the wires
    xmarks = _marks(off, DISABLED_X)
    assert xmarks and all(m['x'] == left and m['x2'] == right for m in xmarks)
    assert off['marks'].index(xmarks[0]) > off['marks'].index(thru[-1])
    # the dotted straight-and-crossed switch lines are gone for that gate
    assert any(d[0]['route'].startswith(f'{gate}~x') for d in on['dots'])
    assert not any(d[0]['route'].startswith(f'{gate}~x') for d in off['dots'])


def test_a_switched_off_particle_wire_is_dotted():
    sim = _sim()
    particle = next(iter(sim.particles))
    on = diagram_geometry(sim)
    off = diagram_geometry(sim, absent=(particle,))
    assert not any(seg[0].get('dotted') for seg in on['wires'])
    dotted = [seg for seg in off['wires'] if seg[0].get('dotted')]
    # the particle's own wire and everything downstream of it: in the
    # EPR circuit that is more than one wire
    dead = dead_sources(sim.links, (particle,))
    expected = sum(1 for src in sim.links if src.removesuffix('|2') in dead)
    assert expected > 1
    assert len(dotted) == expected
    assert all(p.get('dotted') for seg in dotted for p in seg)
    assert len(off['wires']) == len(on['wires'])


def test_dead_sources_follow_the_wires():
    # p1 -> g1.upper: both of g1's switch outputs die, and so does the
    # control output of every gate they feed; p2 on g2.upper stays
    # live, so g2's switch outputs carry weight
    links = {'p1': 'g1.upper', 'g1.lower': 'g2.control', 'g1.upper': 'g3.control',
             'p2': 'g2.upper', 'g2.upper': 'g4.lower', 'g2.control': 'g5.control'}
    assert dead_sources(links, ('p1',)) == {
        'p1', 'g1.upper', 'g1.lower', 'g2.control', 'g3.control', 'g5.control'}
    # a live particle on the other switch port keeps the outputs live;
    # both switch inputs dead kills them
    assert dead_sources(links, ('p1', 'p2')) >= {'g2.upper', 'g2.lower'}
    assert dead_sources(links, ()) == set()
