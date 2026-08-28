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
