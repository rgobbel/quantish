"""The results diagram's hover detail: a dangling output's stadium
blob (the value landing outside the gate) carries the same amplitude
and probability tip as the out-port box it extends."""
import yaml
from addict import Dict

from quantish.diagram_layout import diagram_geometry
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation


def test_stadium_blob_shares_the_port_tip():
    CalcMode.default('Float')
    with open('models/gr2026/fig4.04.yaml') as f:
        cfg = yaml.safe_load(f)
    cfg['loglevel'] = 'error'
    sim = Simulation(Dict(cfg))
    sim.run()
    geo = diagram_geometry(sim, has_run=True)
    tips = {(b['amp'], b['pr']) for b in geo['boxes'] if b.get('amp')}
    assert tips, 'the out-port boxes carry tips after a run'
    assert geo['stadiums'], 'figure 4.4 has dangling outputs'
    for blob in geo['stadiums']:
        assert (blob['amp'], blob['pr']) in tips
