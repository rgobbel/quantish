"""The double-slit demo's presentation side: its conditions, the
panel titles, and each condition's circuit diagram geometry.
"""
from __future__ import annotations

from quantish.diagram_layout import diagram_geometry
from quantish.double_slit import slit_sim

__all__ = ['DIAGRAM_WIDTH', 'MAIN_MODES', 'MODES', 'PANEL_TITLES', 'diagram_geom']

# the four conditions of the main grid, plus the tunable recorder and
# the eraser in their own sections; the panel machinery covers all six
MAIN_MODES = ('both', 'slit2', 'slit1', 'observed')   # the grid
MODES = MAIN_MODES + ('tunable', 'eraser')
PANEL_TITLES = {'both': 'both slits open',
                'slit2': 'left slit blocked',
                'slit1': 'right slit blocked',
                'observed': 'recorder on right slit (both open)',
                'tunable': 'recorder with tunable decoherence',
                'eraser': 'recorder with quantum eraser'}
DIAGRAM_WIDTH = {mode: 900 if mode in ('slit1', 'both', 'slit2') else 1050
                 for mode in MODES}


def diagram_geom(mode: str, angles: dict, labels: dict) -> dict:
    """A condition's circuit diagram geometry at `angles` (radians),
    the gates labeled per `labels` (Sn = slit n, Bn = a block in its
    place): the grid rows size their own frames, and open with the
    whole circuit in view (fit) rather than at natural scale."""
    geom = diagram_geometry(
        slit_sim(mode, **angles), has_run=False,
        angle_overrides={'g_obs': '0°', 'φ': 'φ(x)', **labels})
    geom.update({'frame_w': DIAGRAM_WIDTH[mode], 'frame_h': 330, 'fit': True})
    return geom
