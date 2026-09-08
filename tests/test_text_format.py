"""The shared text-format subset every non-TikZ surface renders:
$...$ math as unicode (subscripts, superscripts, greek, symbols), and
bare digits after letters auto-subscripting. Plain text must pass
through untouched — the reasonable default is no markup at all."""
from quantish.util import fmt_label, math_to_unicode, subscript_digits


class TestMathToUnicode:
    def test_subscripts(self):
        assert math_to_unicode('$Q_1$ and $Q_{12}$') == 'Q₁ and Q₁₂'
        assert math_to_unicode('$w_{2a}$') == 'w₂ₐ'

    def test_superscripts(self):
        assert math_to_unicode('$x^2$') == 'x²'
        assert math_to_unicode('$y^{10}$') == 'y¹⁰'
        assert math_to_unicode('$e^{i}$') == 'eⁱ'

    def test_greek_and_symbols(self):
        assert math_to_unicode(r'$\theta_1 = \pi/6$') == 'θ₁ = π/6'
        assert math_to_unicode(r'$\Delta\varphi \le 2\pi$') == 'Δφ ≤ 2π'
        assert math_to_unicode(r'$\angle +45$') == '∠ +45'
        assert math_to_unicode(r'$a \ne b$') == 'a ≠ b'

    def test_unknown_command_left_alone(self):
        assert math_to_unicode(r'$\frobnicate$') == r'\frobnicate'

    def test_plain_text_untouched(self):
        assert math_to_unicode('no math here_at all') \
            == 'no math here_at all'
        assert math_to_unicode('price: $5') == 'price: $5'


class TestFmtLabel:
    def test_auto_subscript(self):
        assert fmt_label('g1') == 'g₁'
        assert fmt_label('w2a') == 'w₂a'
        assert fmt_label('theta12') == 'theta₁₂'

    def test_math_plus_auto(self):
        assert fmt_label(r'$\theta_1$ at g5') == 'θ₁ at g₅'

    def test_stable_under_reapplication(self):
        once = fmt_label('$w_{2a}$ g1')
        assert fmt_label(once) == once

    def test_non_string_input(self):
        assert fmt_label(42) == '42'


class TestSubscriptDigits:
    def test_underscore_forms(self):
        assert subscript_digits('g_p') == 'gₚ'
        assert subscript_digits('g_φ') == 'gᵩ'
        assert subscript_digits('measure_1') == 'measure₁'


def test_mathrm_and_text_unwrap():
    # \mathrm{...} / \text{...} are upright text on every surface
    # here, so only their content survives — inside a subscript too
    from quantish.util import math_runs, math_to_unicode
    assert math_to_unicode(r'$g_{\mathrm{split}}$') == 'gₛₚₗᵢₜ'
    assert math_runs(r'$g_{\mathrm{split}}$') == [('g', 0), ('split', -1)]
    assert math_to_unicode(r'$\text{S}_1$') == 'S₁'


def test_short_labels_show_pass_through_gates_bare():
    """Delay gates, phase plates and control-only gates are single-wire
    pass-throughs: the configuration label names them with no port
    letter ('+S2', not '+S2c') — that they route through a control
    port is an implementation detail."""
    from pathlib import Path

    import yaml
    from addict import Dict as Addict

    from quantish.display import pass_through_names, short_label
    from quantish.qnumber import CalcMode
    from quantish.simulation import Simulation

    models = Path(__file__).resolve().parents[1] / 'models' / 'extras'
    with open(models / 'double_slit_recorder.yaml') as f:
        cfg = yaml.safe_load(f)
    cfg['loglevel'] = 'warning'
    CalcMode.default('Float')
    sim = Simulation(Addict(cfg))
    space, _ = sim.run()
    assert {'S1', 'S2', 'S', 'D', 'φ'} <= pass_through_names(sim)
    labels = [short_label(sim, p) for p in space.index.values()]
    assert labels, 'no final points'
    for label in labels:
        for tok in label.split():
            assert not tok.endswith('Sc') and not tok.endswith('Dc'), label
    # a real Fredkin gate keeps its port letter
    assert any('g_obs' in tok and tok[-1] in 'ul'
               for label in labels for tok in label.split()), labels


def test_port_boxes_show_particle_signs():
    """After a run, a gate output port's box lines name the particle
    signs there, sign first, with their probabilities; a particle of
    one sign takes a single line with the phase."""
    from pathlib import Path

    import yaml
    from addict import Dict as Addict

    from quantish.config_space import GatePort
    from quantish.display import port_summary, pos_sign_lines
    from quantish.qnumber import CalcMode
    from quantish.simulation import Simulation

    models = Path(__file__).resolve().parents[1] / 'models'
    with open(models / 'gr2026' / 'fig4.04.yaml') as f:
        cfg = yaml.safe_load(f)
    cfg['loglevel'] = 'warning'
    CalcMode.default('Float')
    sim = Simulation(Addict(cfg))
    sim.run()
    gate = sim.run_order[0]
    lines = {port: pos_sign_lines(sim, f'{gate}.{port}')
             for port in ('upper', 'lower')}
    assert any(lines.values()), lines
    for block in filter(None, lines.values()):
        for ln in block.split('\n'):
            assert ln[0] in '+−Σ', ln
    seen = ' '.join(filter(None, lines.values()))
    assert '+p1' in seen and '−p1' in seen      # the four-way split
    summary = port_summary(sim, 1, GatePort(gate, 'upper'))
    assert summary is None or summary.lstrip()[0] in '+−'


def test_mermaid_after_run_shows_signs(tmp_path):
    """The after-run Mermaid diagram writes particle signs, sign first,
    in its port blocks (and renders at all — the path has no other
    test)."""
    import re
    from pathlib import Path

    import yaml
    from addict import Dict as Addict

    from quantish import mermaid_diagram
    from quantish.qnumber import CalcMode
    from quantish.simulation import Simulation

    models = Path(__file__).resolve().parents[1] / 'models'
    with open(models / 'defaults.yaml') as f:
        cfg = yaml.safe_load(f)
    with open(models / 'gr2026' / 'fig4.10.yaml') as f:
        cfg.update(yaml.safe_load(f))
    cfg['loglevel'] = 'warning'
    CalcMode.default('Float')
    sim = Simulation(Addict(cfg))
    sim.run()
    out = tmp_path / 'fig4.10.mmd'
    mermaid_diagram.diagram(sim, out, True)
    txt = out.read_text()
    assert '+p1 1.00' in txt                 # the entry annotation
    assert re.search(r'[+−]p1 0\.\d\d', txt)   # a per-sign port line
    assert not re.search(r'\bp\d[+-]', txt)   # no trailing-sign spelling
