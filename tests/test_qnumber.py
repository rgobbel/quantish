"""qnumber is the numeric substrate of everything else, so it gets its
own bulletproofing: construction and parsing, both calculation modes,
mode switching (including the natural-but-wrong spellings), arithmetic,
displays, and the zero tests."""
import cmath
import copy
import math

import pytest
import sympy as sym

import quantish.qnumber as qn
from quantish.qnumber import CalcMode, Complex, Real, qify


@pytest.fixture(params=['Float', 'Symbolic'])
def mode(request):
    """Run a test under each calculation mode, restoring the previous
    mode (and its derived globals) afterwards."""
    prev = CalcMode.default()
    qn.set_calc_mode(request.param)
    yield request.param
    qn.set_calc_mode(prev)


def close(a, b, tol=1e-12):
    return cmath.isclose(complex(a), complex(b), abs_tol=tol)


# ---------------------------------------------------------------- modes

class TestModeControl:
    def test_default_get_and_set(self, mode):
        assert CalcMode.default() == mode
        assert CalcMode.mode == mode

    def test_empty_arg_reads_without_switching(self, mode):
        assert CalcMode.default(None) == mode
        assert CalcMode.default('') == mode

    def test_case_insensitive(self):
        prev = CalcMode.default()
        try:
            assert qn.set_calc_mode('symbolic') == 'Symbolic'
            assert qn.set_calc_mode('FLOAT') == 'Float'
        finally:
            qn.set_calc_mode(prev)

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match='Symbollic'):
            qn.set_calc_mode('Symbollic')
        with pytest.raises(ValueError):
            CalcMode.mode = 3.14

    def test_module_attribute_assignment_switches(self):
        # qn.CalcMode = 'Symbolic' reads as a mode switch; it must not
        # replace the class (the "'str' has no attribute 'default'" bug)
        prev = CalcMode.default()
        try:
            qn.CalcMode = 'Symbolic'
            assert isinstance(qn.CalcMode, type)
            assert CalcMode.default() == 'Symbolic'
            assert str(qify(0)) == '0'
        finally:
            qn.set_calc_mode(prev)

    def test_classmethod_assignment_switches(self):
        prev = CalcMode.default()
        try:
            CalcMode.default = 'Float'
            assert callable(CalcMode.default)
            assert CalcMode.default() == 'Float'
            CalcMode.mode = 'Symbolic'
            assert CalcMode.mode == 'Symbolic'
        finally:
            qn.set_calc_mode(prev)

    def test_mode_enum(self):
        # the Symbol-style spelling: Mode.Symbolic instead of a string
        prev = CalcMode.default()
        try:
            assert qn.set_calc_mode(qn.Mode.Symbolic) == 'Symbolic'
            assert CalcMode.default() is qn.Mode.Symbolic
            assert CalcMode.default() == 'Symbolic'   # still a str
            qn.CalcMode = qn.Mode.Float
            assert CalcMode.mode is qn.Mode.Float
            with pytest.raises(AttributeError):
                _ = qn.Mode.Symbollic
        finally:
            qn.set_calc_mode(prev)

    def test_switch_updates_derived_globals(self):
        # the constants are mode-adaptive objects: nothing is rebound
        # on a switch, the same object presents the matching backend
        prev = CalcMode.default()
        try:
            qn.set_calc_mode('Float')
            assert qn.ZERO_THRESHOLD == qn.float_zero_threshold
            assert isinstance(qn.I.v, complex)
            qn.set_calc_mode('Symbolic')
            assert qn.ZERO_THRESHOLD == 0
            assert qn.I.v is sym.I
        finally:
            qn.set_calc_mode(prev)


# ------------------------------------------------------------- parsing

class TestQify:
    def test_numbers(self, mode):
        assert isinstance(qify(0), Real)
        assert isinstance(qify(2), Real)
        assert isinstance(qify(0.5), Real)
        assert isinstance(qify(1 + 2j), Complex)
        assert close(qify(0.5), 0.5)
        assert close(qify(1 + 2j), 1 + 2j)

    def test_strings(self, mode):
        assert close(qify('2'), 2)
        assert close(qify('1/2'), 0.5)
        assert close(qify('pi/6'), math.pi / 6)
        assert close(qify('rad(30)'), math.radians(30))
        assert close(qify('sqrt(2)/2'), math.sqrt(2) / 2)
        assert close(qify('acos(4/5)'), math.acos(0.8))
        assert close(qify('0.5+0.87j'), 0.5 + 0.87j)
        assert close(qify('I'), 1j)

    def test_q_passthrough_is_identity(self, mode):
        x = qify('pi/6')
        assert qify(x) is x

    def test_env_variables(self, mode):
        env = {'q5': qify(0), 'q6': qify('pi/4'), 'theta2': qify('pi/8')}
        assert close(qify('(q5 + q6) - theta2', env), math.pi / 8)

    def test_unknown_name_raises_with_hint(self, mode):
        with pytest.raises(ValueError, match='unknown name'):
            qify('nonsense')
        with pytest.raises(ValueError, match='known variables'):
            qify('q5 + oops', {'q5': qify(1)})

    def test_symbolic_mode_is_exact(self):
        prev = CalcMode.default()
        try:
            qn.set_calc_mode('Symbolic')
            assert qify('pi/6').v == sym.pi / 6
            assert 'pi' in str(qify('rad(30)'))
        finally:
            qn.set_calc_mode(prev)


class TestExact:
    def test_exact_parses_symbolically(self):
        x = qn.exact('1/2')
        assert x.v == sym.Rational(1, 2)
        assert x.is_exact
        assert qn.exact('pi/6').v == sym.pi / 6

    def test_exact_rejects_junk(self):
        with pytest.raises(ValueError):
            qn.exact('not-a-number')

    def test_is_bare_numeric(self):
        assert qn.exact('45').is_bare_numeric
        assert qn.exact('1/2').is_bare_numeric
        assert not qn.exact('pi/6').is_bare_numeric
        assert not qn.exact('acos(4/5)').is_bare_numeric


# ---------------------------------------------------------- predicates

class TestPredicates:
    def test_type_predicates(self, mode):
        assert qn.isq(qify(1)) and qn.isq(qify(1j))
        assert not qn.isq(1) and not qn.isq('1')
        assert qn.iscplx(1j) and not qn.iscplx(1) and not qn.iscplx(qify(1j))
        assert qn.realtype(1) and qn.realtype(1.5)
        assert not qn.realtype(1j)
        assert qn.issym(sym.pi) and not qn.issym(1.0)
        assert qn.isnative(1) and qn.isnative(1j) and not qn.isnative(qify(1))

    def test_to_float_and_to_native(self, mode):
        assert qn.to_float(sym.pi / 6) == pytest.approx(math.pi / 6)
        assert qn.to_native(1.5) == 1.5
        assert qn.to_native(sym.I) == 1j


# ---------------------------------------------------------- arithmetic

class TestArithmetic:
    def test_ring_operations(self, mode):
        a, b = qify('1/2'), qify('1/3')
        assert close(a + b, 5 / 6)
        assert close(a - b, 1 / 6)
        assert close(a * b, 1 / 6)
        assert close(a / b, 1.5)
        assert close(a ** 2, 0.25)
        assert close(-a, -0.5)
        assert close(+a, 0.5)
        for x in (a + b, a * b, -a):
            assert qn.isq(x)

    def test_reflected_operations(self, mode):
        a = qify(2)
        assert close(1 + a, 3)
        assert close(1 - a, -1)
        assert close(3 * a, 6)
        assert close(1 / a, 0.5)
        assert close(2 ** a, 4)

    def test_abs_round_conjugate(self, mode):
        w = qify('0.6+0.8j')
        assert close(abs(w), 1)
        assert isinstance(abs(w), Real)
        assert close(w.conjugate(), 0.6 - 0.8j)
        assert close(round(qify(1.25), 1), 1.2)

    def test_real_imag_phase(self, mode):
        w = qify('1+1j') if mode == 'Float' else qify('1 + I')
        assert close(w.real, 1)
        assert close(w.imag, 1)
        assert close(w.phase, math.pi / 4)

    def test_euler_identity(self, mode):
        # e^(iπ) = −1, the canonical exactness check
        e_ipi = (qify('pi') * qify('I')).exp
        assert close(e_ipi, -1)
        if mode == 'Symbolic':
            assert e_ipi.v == -1

    def test_rotate(self, mode):
        # the pre-cleanup rotate computed e^(iθ·self); regression-guard
        # the fixed semantics self·e^(iθ)
        assert close(qify(1).rotate(math.pi / 2), 1j)
        assert close(qify(2).rotate(math.pi), -2)

    def test_trig(self, mode):
        th = qify('pi/6')
        assert close(th.cos, math.cos(math.pi / 6))
        assert close(th.sin, 0.5)
        assert close(th.cos ** 2 + th.sin ** 2, 1)

    def test_probability(self, mode):
        assert close(qn.probability(qify('0.6+0.8j')), 1)
        assert close(qn.probability(qify('sqrt(2)/2')), 0.5)

    def test_prod(self, mode):
        assert close(qn.prod([qify(2), qify(3), qify(4)]), 24)
        assert close(qn.prod([]), 0)


# ------------------------------------------------------ angles, modes

class TestRealExtras:
    def test_degrees_radians_round_trip(self, mode):
        th = qify('rad(30)')
        assert isinstance(th, Real)
        assert close(th.degrees, 30)
        assert close(th.degrees.radians, math.radians(30))
        if mode == 'Symbolic':
            assert th.degrees.v == 30

    def test_real_of_real_is_identity(self, mode):
        x = Real(1.5)
        assert Real(x) is x

    def test_real_nonreal_falls_back_to_complex(self, mode):
        w = Real(1 + 2j if mode == 'Float' else sym.I)
        assert type(w) is Complex

    def test_mm_and_to_mode(self):
        prev = CalcMode.default()
        try:
            qn.set_calc_mode('Float')
            x = qify('pi/6')
            assert x.mm == 'Float'
            s = x.to_mode('Symbolic')
            assert s.mm == 'Symbolic'
            assert close(s, x, tol=1e-15)
            assert x.to_mode('Float') is x
        finally:
            qn.set_calc_mode(prev)

    def test_float_conversion(self, mode):
        assert float(qify('1/2')) == 0.5
        assert complex(qify('I')) == 1j


# ----------------------------------------------------------- displays

class TestDisplay:
    def test_float_display_precision(self):
        prev = CalcMode.default()
        try:
            qn.set_calc_mode('Float')
            assert qify('0.5+0.87j').display(2) == '0.50+0.87j'
            assert qify(1).display(1) == '1.0+0.0j'
        finally:
            qn.set_calc_mode(prev)

    def test_symbolic_display_is_float_free(self):
        prev = CalcMode.default()
        try:
            qn.set_calc_mode('Symbolic')
            assert qify('pi/6').display() == 'pi/6'
            assert '.' not in qify('sqrt(2)/2').display()
        finally:
            qn.set_calc_mode(prev)

    def test_str_and_format(self, mode):
        assert str(qify(2)) == '2'
        assert f'{qify(0.5):.1f}' == '0.5'


# -------------------------------------------------------- zero testing

class TestZerop:
    def test_float_threshold(self):
        prev = CalcMode.default()
        try:
            qn.set_calc_mode('Float')
            assert qn.zerop(qify(0))
            assert qn.zerop(qify(1e-16))
            assert not qn.zerop(qify(1e-10))
        finally:
            qn.set_calc_mode(prev)

    def test_symbolic_is_exact(self):
        prev = CalcMode.default()
        try:
            qn.set_calc_mode('Symbolic')
            assert qn.zerop(qify(0))
            assert qn.zerop(sym.sqrt(2) ** 2 - 2)
            assert not qn.zerop(qify('1/10**30'))
            # a free symbol can't be proven zero
            assert not qn.zerop(sym.Symbol('x'))
        finally:
            qn.set_calc_mode(prev)

    def test_cancellation(self, mode):
        a = qify('sqrt(2)/2')
        assert qn.zerop((a * a + a * a) - qify(1))


# ------------------------------------------------- object plumbing

class TestPlumbing:
    def test_equality_and_same(self, mode):
        assert bool(qify('pi/6') == qify('pi/6'))
        assert qify(1).same(qify(2))
        assert not qify(1).same(qify(1j))

    def test_hash_matches_value(self, mode):
        assert hash(qify(2)) == hash(qify(2).v)

    def test_deepcopy(self, mode):
        x = qify('rad(30)')
        y = copy.deepcopy(x)
        assert close(x, y)
        assert type(y) is type(x)

    def test_bool(self, mode):
        assert not bool(qify(0))
        assert bool(qify('1/10'))

    def test_mode_constants(self, mode):
        assert close(qn.PI, math.pi)
        assert close(qn.I, 1j)
        assert close(qn.E, math.e)
        assert (qn.ZERO_THRESHOLD == qn.float_zero_threshold
                if mode == 'Float' else close(qn.ZERO_THRESHOLD, 0))

    def test_constants_track_mode_through_imports(self):
        # even a from-imported binding follows a later mode switch
        from quantish.qnumber import PI
        prev = CalcMode.default()
        try:
            qn.set_calc_mode('Symbolic')
            assert PI.v is sym.pi
            assert (PI / 2).v == sym.pi / 2
            qn.set_calc_mode('Float')
            assert PI.v == math.pi
        finally:
            qn.set_calc_mode(prev)


class TestPIAlias:
    """qify('PI') is the same constant as qify('pi') in both modes —
    the module exports PI, so expressions may spell it either way."""

    def test_pi_alias_both_modes(self):
        import math
        for mode in ('Float', 'Symbolic'):
            qn.CalcMode.default(mode)
            assert float(qn.qify('PI')) == pytest.approx(math.pi)
            assert float(qn.qify('PI/2')) == pytest.approx(math.pi / 2)
        qn.CalcMode.default('Float')

    def test_model_variable_still_wins(self):
        qn.CalcMode.default('Float')
        assert float(qn.qify('x + PI', {'x': qn.Real(1)})) == \
            pytest.approx(1 + 3.141592653589793)


class TestDegreeMarks:
    """Postfix degree marks are part of the expression language:
    '30°' and '(q5+q6)°' parse everywhere qify is used — exactly, as
    pi fractions, in Symbolic mode."""

    def test_bare_and_compound(self, mode):
        assert float(qn.qify('30°')) == pytest.approx(math.radians(30))
        assert float(qn.qify('30° + 15°')) == \
            pytest.approx(math.radians(45))
        assert float(qn.qify('(q5 + q6)°',
                             {'q5': qn.Real(30), 'q6': qn.Real(15)})) \
            == pytest.approx(math.radians(45))

    def test_symbolic_is_exact(self):
        prev = qn.CalcMode.default()
        try:
            qn.CalcMode.default('Symbolic')
            assert qn.qify('30°').v == sym.pi / 6
            assert qn.qify('22.5°').v == sym.pi / 8
        finally:
            qn.CalcMode.default(prev)

    def test_variables_may_hold_degree_marks(self):
        # the load_variables path: a variable defined as '30°' resolves
        # and is usable in later expressions
        env = {'q30': qn.qify('30°')}
        assert float(qn.qify('q30 * 2', env)) == \
            pytest.approx(math.radians(60))


class TestConj:
    """conj(...) (and sympy's own conjugate) work in qify expressions —
    exact in Symbolic mode."""

    def test_conj_both_modes(self, mode):
        env = {'q45': qn.qify('sqrt(2)/2 + sqrt(2)*I/2')}
        got = complex(qn.qify('conj(q45)', env).v)
        want = complex(qn.qify('sqrt(2)/2 - sqrt(2)*I/2').v)
        assert abs(got - want) < 1e-12
        assert complex(qn.qify('conjugate(I)').v) == -1j

    def test_conj_is_reserved(self):
        assert qn.reserved_name('conj')
        assert qn.reserved_name('conjugate')
