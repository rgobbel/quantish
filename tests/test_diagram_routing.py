"""Wire-routing invariants over every model in the library.

The router (tikz_diagram.route_wires) is heuristic, so these tests pin
what a reader would call a wrong drawing rather than exact geometry:
no wire runs across a labeled null-input/output stub, no wire's
vertical passes through the END of another wire's horizontal (which
reads as a T-junction fusing the two), and a branching particle's two
arms leave it along one shared channel (the fork). Crossings through
the interior of another wire are allowed: they are sometimes
unavoidable and always read as crossings."""
from pathlib import Path

import pytest
import yaml
from addict import Dict as Addict

import quantish.tikz_diagram as tk
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation
from quantish.util import BRANCH_MARK, base_name

MODELS = Path(__file__).parent.parent / 'models'
MODEL_FILES = sorted(p for p in MODELS.rglob('*.yaml')
                     if p.name not in ('defaults.yaml', 'schema.yaml'))
_T_TOL = 0.12      # the router's own T-junction tolerance
_EPS = 0.02


def _routed(path):
    CalcMode.default('Float')
    cfg = yaml.safe_load(path.read_text())
    sim = Simulation(Addict(cfg | {'loglevel': 'error'}))
    circuit = tk.spec_from_simulation(sim)
    L = tk.compute_layout(circuit)
    routes = tk.route_wires(circuit, L)
    links = list(circuit.topology['parsed'].links.items())
    # route_wires yields the links' routes in its own (sorted) order and
    # appends the labeled stubs; recover each route's link by endpoints
    stubs = list(tk.labeled_stubs(circuit, L))
    wires = routes[:len(routes) - len(stubs)]
    return sim, circuit, L, wires, stubs


def _segments(points):
    """(horizontal, vertical) segment lists of a polyline."""
    hs, vs = [], []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if abs(y1 - y2) < 1e-9:
            hs.append((y1, min(x1, x2), max(x1, x2)))
        elif abs(x1 - x2) < 1e-9:
            vs.append((x1, min(y1, y2), max(y1, y2)))
    return hs, vs


def _source_of(route, circuit, L):
    """The link source a route was drawn for, matched by its start."""
    parsed = circuit.topology['parsed']
    particles = set(parsed.particles)
    delays = set(parsed.delay_gates)
    x0, y0 = route.points[0]
    for src in parsed.links:
        sxy = tk.src_xy(L, src, particles, delays)
        if sxy and abs(sxy[0] - x0) < 1e-6 and abs(sxy[1] - y0) < 1e-6:
            dxy, _ = tk.dst_xy_col(circuit, L, parsed.links[src], delays)
            if dxy and abs(dxy[0] - route.points[-1][0]) < 1e-6 \
                    and abs(dxy[1] - route.points[-1][1]) < 1e-6:
                return src
    return None


@pytest.mark.parametrize('path', MODEL_FILES,
                         ids=[str(p.relative_to(MODELS)) for p in MODEL_FILES])
def test_no_wire_crosses_a_labeled_stub(path):
    _, _, _, wires, stubs = _routed(path)
    for points, label, _, _ in stubs:
        (ax, ay), (bx, _) = points[0], points[-1]
        lo, hi = min(ax, bx), max(ax, bx)
        for w in wires:
            for x, y1, y2 in _segments(w.points)[1]:
                assert not (lo + _EPS < x < hi - _EPS
                            and y1 + _EPS < ay < y2 - _EPS), \
                    f'a wire vertical at x={x:.2f} crosses the {label} stub'


@pytest.mark.parametrize('path', MODEL_FILES,
                         ids=[str(p.relative_to(MODELS)) for p in MODEL_FILES])
def test_no_t_junction_on_another_wires_end(path):
    _, circuit, L, wires, _ = _routed(path)
    owners = [_source_of(w, circuit, L) for w in wires]
    for i, w in enumerate(wires):
        for x, y1, y2 in _segments(w.points)[1]:
            for j, other in enumerate(wires):
                if i == j:
                    continue
                oi, oj = owners[i], owners[j]
                if oi and oj and '.' not in oi and '.' not in oj \
                        and base_name(oi) == base_name(oj):
                    continue   # sibling arms: their corners ARE the fork
                for y, xa, xb in _segments(other.points)[0]:
                    if y1 + _EPS < y < y2 - _EPS:
                        assert abs(x - xa) >= _T_TOL and abs(x - xb) >= _T_TOL, \
                            (f'wire {oi} vertical at x={x:.2f} passes through '
                             f'the end of wire {oj} at y={y:.2f}')


@pytest.mark.parametrize('path', MODEL_FILES,
                         ids=[str(p.relative_to(MODELS)) for p in MODEL_FILES])
def test_branching_arms_share_one_channel(path):
    sim, circuit, L, wires, _ = _routed(path)
    if not sim.branch_specs:
        pytest.skip('no branching particle')
    owners = [_source_of(w, circuit, L) for w in wires]
    for pname in sim.branch_specs:
        arms = [w for w, o in zip(wires, owners)
                if o in (pname, f'{pname}{BRANCH_MARK}')]
        assert len(arms) == 2, f'{pname}: expected two routed arms'
        firsts = [_segments(a.points)[1][0][0] for a in arms
                  if _segments(a.points)[1]]
        assert len(firsts) == 2 and abs(firsts[0] - firsts[1]) < 1e-6, \
            f'{pname}: the arms leave along different channels {firsts}'
