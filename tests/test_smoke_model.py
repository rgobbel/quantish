"""tests/fixtures/smoke.yaml is the display stress-test fixture: a unicode gate
name, a phase plate, a delay gate sharing its stage with a full gate,
mixed degree-marked angles. It must run, validate, and lay out without
the regressions it was built to catch."""
from pathlib import Path

import yaml
from addict import Dict as Addict

from quantish.diagram_layout import (DELAY_FILL, GATE_FILL,
                                     STAGE_FILL, diagram_geometry)
from quantish.model_schema import validate_model
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation

SMOKE = Path(__file__).parent / 'fixtures' / 'smoke.yaml'


def _sim():
    CalcMode.default('Float')
    sim = Simulation(Addict(yaml.safe_load(SMOKE.read_text())))
    sim.run()
    return sim


def test_smoke_validates_and_runs():
    config = yaml.safe_load(SMOKE.read_text())
    assert validate_model(config) == []
    sim = _sim()
    total = sum(float(p.probability)
                for p in sim.result_space.index.values())
    assert abs(total - 1) < 1e-9


def test_smoke_layout():
    g = diagram_geometry(_sim(), has_run=True)
    # a unicode gate name keeps its subscript (φ1 → φ₁)
    texts = [ln for tx in g['texts'] for ln in tx['lines']]
    assert any('φ₁' in ln for ln in texts)
    assert not any('φ1' in ln for ln in texts)
    # the delay box tucks in just below its column's gates instead of
    # a KY-stretched row away (the chasm the fixture caught). Both d₁
    # and the φ₁ plate use DELAY_FILL; d₁ is the one whose column also
    # holds a gate frame.
    gaps = []
    for delay in (b for b in g['boxes'] if b['fill'] == DELAY_FILL):
        cx = (delay['x'] + delay['x2']) / 2
        mates = [b for b in g['boxes'] if b['fill'] == GATE_FILL
                 and b['x'] < cx < b['x2']]
        if mates:
            gaps.append(min(b['y'] for b in mates) - delay['y2'])
    assert gaps, 'no delay shares a column with a gate frame'
    assert all(0 < gap < 1.0 for gap in gaps), \
        f'delay-to-gate gaps {[f"{g:.2f}" for g in gaps]}'
    # the plate's compass needle stays inside its box
    plates = [b for b in g['boxes'] if b['fill'] == DELAY_FILL]
    for seg in g['wires']:
        if len(seg) == 2 and seg[0].get('route', '').endswith('~c'):
            xs = [p['x'] for p in seg]
            for b in plates:
                if b['x'] < sum(xs) / 2 < b['x2']:
                    poked = seg[0]['route']
                    assert all(b['x'] <= x <= b['x2'] for x in xs), \
                        f'needle {poked} pokes out of its plate box'
    # the wires reaching the tucked-in delay drop and rise OUTSIDE the
    # stage box, never running vertically through it
    d1 = next(b for b in g['boxes'] if b['fill'] == DELAY_FILL
              and any(m['fill'] == GATE_FILL
                      and m['x'] < (b['x'] + b['x2']) / 2 < m['x2']
                      for m in g['boxes']))
    dcx = (d1['x'] + d1['x2']) / 2
    stage = next(b for b in g['boxes'] if b['fill'] == STAGE_FILL
                 and b['x'] < dcx < b['x2']
                 and b['y'] < (d1['y'] + d1['y2']) / 2 < b['y2'])
    for seg in g['wires']:
        for a, b in zip(seg, seg[1:]):
            vertical = (abs(a['x'] - b['x']) < 1e-6
                        and abs(a['y'] - b['y']) > 0.1)
            if not vertical:
                continue
            ylo, yhi = sorted((a['y'], b['y']))
            if yhi > stage['y'] and ylo < stage['y2']:
                assert not (stage['x'] + 0.05 < a['x']
                            < stage['x2'] - 0.05), \
                    f"vertical wire run at x={a['x']:.2f} crosses " \
                    f"the stage box interior"
