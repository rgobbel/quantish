"""quantish/apps/double_slit_ui.py and the demo's curve helpers."""
import pytest

from quantish.apps import curves, double_slit_ui as ui
from quantish.qnumber import CalcMode


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield


def test_modes_and_titles():
    assert set(ui.MODES) == set(ui.PANEL_TITLES) == set(ui.DIAGRAM_WIDTH)
    assert ui.MODES[:4] == ui.MAIN_MODES


@pytest.mark.parametrize('mode', ui.MODES)
def test_diagram_geom_fits_its_frame(mode):
    g = ui.diagram_geom(mode, {}, {'g_split': '45°'})
    assert g['fit'] and g['frame_w'] == ui.DIAGRAM_WIDTH[mode] and g['frame_h'] == 330


def test_live_helpers_agree_with_the_per_pixel_curves():
    settings = {'n': 7, 'fringes': 2, 'main_angles': {}, 'theta_pre': 0.4, 'theta_erase': 0.2}
    xs, all_curves, parts = curves.double_slit_curves(settings, ui.MAIN_MODES)
    main = curves.main_curves(7, 2, {}, 'pixels', ui.MAIN_MODES)
    assert main == {m: all_curves[m] for m in ui.MAIN_MODES}
    assert curves.tunable_curve(7, 2, {}, 0.4) == all_curves['tunable']
    _, total, ps = curves.eraser_curves(7, 2, {}, 0.2)
    assert total == all_curves['eraser'] and ps == parts['eraser']
    fit = curves.main_curves(7, 2, {}, 'fit', ui.MAIN_MODES)
    for m in ui.MAIN_MODES:
        assert fit[m] == pytest.approx(main[m], abs=1e-9)
