import logging
import numbers as n
import sympy as sym
from sympy import re, im, Rational, deg, rad, Eq, Piecewise
from functools import reduce
from operator import mul
import math as m
import cmath as cm
import scipy.special as sci
import re as rex
from typing import Any, Callable, TypeIs, cast

log = logging.getLogger('quantish')

class Mode(__import__('enum').StrEnum):
    """The calculation mode as a proper type: qn.Mode.Symbolic reads
    like a symbol, autocompletes, and typos fail immediately — while
    each member IS its string, so configs, logs, and == 'Float'
    comparisons all keep working."""
    Float = 'Float'
    Symbolic = 'Symbolic'


CALC_MODE = Mode.Float
PI = m.pi
I = 1j
E = m.e
ZERO_THRESHOLD = 0.0

def set_calc_mode(new_mode: str) -> str:
    global I, PI, E, CALC_MODE, ZERO_THRESHOLD
    canon = {'float': Mode.Float, 'symbolic': Mode.Symbolic}.get(
        str(new_mode).lower())
    if canon is None:
        raise ValueError(f'unknown calculation mode {new_mode!r} — '
                         'use Mode.Float or Mode.Symbolic')
    CALC_MODE = canon
    if CALC_MODE == 'Float':
        I = 1j
        PI = m.pi
        E = m.e
        ZERO_THRESHOLD = float_zero_threshold
    else:
        I = sym.I
        PI = sym.pi
        E = sym.E
        ZERO_THRESHOLD = 0
    return CALC_MODE


class CalcModeMeta(type):
    """Metaclass so `CalcMode.mode` is a real settable property at the class level.

    Reading `CalcMode.mode` returns the current global mode; assigning to
    `CalcMode.mode = 'Symbolic'` updates CALC_MODE and the transcendental globals,
    keeping behavior consistent with `CalcMode.default('Symbolic')`.
    """
    @property
    def mode(cls):
        return CALC_MODE

    @mode.setter
    def mode(cls, new_mode):
        set_calc_mode(new_mode)

    def __setattr__(cls, name, value):
        # `CalcMode.default = 'Symbolic'` and `CalcMode.mode = ...`
        # both read as mode switches and must act as one — replacing
        # the classmethod with a string would break every later
        # constructor. Anything invalid fails loudly in set_calc_mode.
        if name in ('default', 'mode'):
            set_calc_mode(value)
            return
        super().__setattr__(name, value)


class CalcMode(metaclass=CalcModeMeta):
    @classmethod
    def default(cls, new_mode: str | None = None):
        if new_mode is None or new_mode == '':
            return CALC_MODE
        return set_calc_mode(new_mode)


def realtype(x) -> TypeIs[int | float]:
    if isq(x):
        x = x.v
    if type(x) in (int, float):
        return True
    return False

def floatable(x):
    try:
        _ = float(x)
        return True
    except TypeError:
        return False
    except ValueError:
        return False

def iscplx(x) -> TypeIs[complex]:
    return type(x) is complex

def isnative(x) -> TypeIs[int | float | complex]:
    return type(x) in (int, float, complex)

def isq(x) -> TypeIs['Complex']:
    return isinstance(x, Complex)

def issym(x) -> TypeIs[sym.Basic]:
    return rex.match('sympy', type(x).__module__) is not None

otherv = lambda x: x.v if isq(x) else x

def _rounded(v, n):
    """round() for either backend. sympy's own Expr.round trims the
    PRECISION to the digit count (Float(1.25).round(1) is a 2-digit
    Float printing '1.2' but worth 1.19921875); rounding through a
    Python float keeps the full-precision rounded value."""
    if issym(v):
        return (sym.Integer(round(float(v))) if n is None
                else sym.Float(round(float(v), n)))
    return round(v, n) if n is not None else round(v)



def to_float(x) -> float:
    try:
        result = float(x)
    except TypeError:
        if sym.im(x) == 0:
            result = complex(x).real
        else:
            raise
    return result


# sympy's sympify overloads only declare the strict= keyword; rational= is
# accepted at runtime but rejected by the type stubs, hence this typed alias.
_sympify = cast(Callable[..., sym.Expr], sym.sympify)

def to_native(x):
    """A Python-native value for x, which might be complex or might be
    real: float when possible, complex otherwise."""
    try:
        result = float(x)
    except TypeError:
        result = complex(x)
    return result

def qify(x, env: dict | None = None) -> 'Complex':
    """Parse x into a Q number. `env` is an optional {name: value} table
    of model variables usable in string expressions ('(q5 + q6) - theta2');
    values may be Q numbers or sympy expressions. An expression that still
    contains unknown names raises — every quantity must be concrete."""
    if isq(x): return x
    elif iscplx(x): return Complex(x)
    local_env = ({name: (val.v if isq(val) else val)
                  for name, val in env.items()} if env else None)
    xval = _sympify(x, rational=True, locals=local_env)
    free = getattr(xval, 'free_symbols', None)
    if free:
        unknown = ', '.join(sorted(str(sy) for sy in free))
        known = (f" (known variables: {', '.join(sorted(env))})"
                 if env else '')
        raise ValueError(f'unknown name(s) {unknown} in {x!r}{known}')
    try:
        _ = float(xval)
        return Real(xval)
    except TypeError:
        return Complex(xval)


# The constants and functions advertised for model expressions; a model
# variable with one of these names would silently change the meaning of
# every expression using the builtin. (Other sympy bindings — eye, beta,
# ... — are fair game: sympify's locals take precedence, so the model's
# meaning wins consistently.)
RESERVED_NAMES = frozenset({
    'pi', 'E', 'I', 'oo', 'zoo', 'nan',
    'rad', 'deg', 'sqrt', 'exp', 'log',
    'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2',
})


def reserved_name(name: str) -> bool:
    """True when `name` is one of the builtins usable in expressions."""
    return name in RESERVED_NAMES




def exact(x) -> 'Real':
    """Parse/wrap x into the exact representation, independent of the
    global CalcMode. Canonical stored values use this; conversion into
    the active mode happens at the edges via to_mode()."""
    if isq(x):
        x = x.v
    if isinstance(x, float):
        # sympify's rational=True only applies to strings; route authored
        # decimals through repr so 0.5 becomes Rational(1,2), not Float.
        x = repr(x)
    val = _sympify(x, rational=True)
    if not isinstance(val, sym.Expr):
        # sympify can "successfully" parse junk like 'not-a-number' into a
        # boolean expression; only genuine numeric expressions get through.
        raise ValueError(f'{x!r} is not a numeric expression')
    if floatable(val):
        return Real(val, 'Symbolic')
    # Non-real input only arises from caller misuse (exact() values are
    # angle-like); preserve the historical Complex fallback.
    return cast(Real, Complex(val, 'Symbolic'))

def softmax(vec):
    if CalcMode.default() == 'Float':
        if isq(vec[0]):
            xvec = [x.v for x in vec]
        elif iscplx(vec[0]):
            xvec = [abs(x) for x in vec]
        elif realtype(vec[0]):
            xvec = vec
        else:
            if type(vec[0]) in (sym.Integer, sym.Float):
                xvec = [float(x) for x in vec]
            else:
                xvec = [abs(complex(x)) for x in vec]
        sm = sci.softmax(xvec)
    else:
        svec = [sym.sympify(val) for val in (x.v if isq(x) else x for x in vec)]
        if sym.im(svec[0]) != 0:
            svec = [abs(x) for x in svec]
        exp_vec = [sym.exp(x) for x in svec]
        sum_exp_vec = sum(exp_vec)
        sm = [expo / sum_exp_vec for expo in exp_vec]
    if isq(vec[0]): fn = type(vec[0])
    elif realtype(vec[0]): fn = Real
    elif iscplx(vec[0]): fn = Complex
    elif isinstance(vec[0], sym.Integer) or isinstance(vec[0], sym.Float): fn = Real
    else: fn = Complex
    return [fn(x) for x in sm]


ANumber = int | float | complex | sym.Mul | sym.Integer | sym.Float | sym.Expr

class Complex(n.Number):
    def __new__(cls, value: 'ANumber | Complex | str' = 0, mode: str | None = None):
        instance = super().__new__(cls)
        if mode is None:
            mode = CalcMode.default()
        instance.__init__(value=value, mode=mode)
        return instance

    def __init__(self, value: 'ANumber | Complex | str' = 0, mode: str | None = None):
        # Extract the underlying value FIRST: in the Real.__new__ identity-return
        # path, value may be self, and zeroing self._value before this would
        # destroy the very value we are about to read.
        if isq(value):
            value = value.v
        self._value: ANumber = 0
        super().__init__()
        if mode is None:
            mode = CalcMode.default()
        if mode == 'Symbolic':
            if not issym(value):
                self._value = sym.sympify(value)
            else:
                self._value = value
        else:
            complex_value = complex(value)
            if type(self) is Complex or complex_value.imag != 0:
                self._value = complex_value
            else:
                n_value = complex_value.real
                if round(n_value) == n_value:
                    n_value = int(n_value)
                self._value = n_value


    def newme(self, x):
        return self.__class__(x)

    def __hash__(self):
        return self._value.__hash__()

    def __getnewargs__(self):
        # copy/pickle support: Real.__new__ requires its value argument, so
        # deepcopy would otherwise fail with "missing 1 required positional
        # argument" (e.g. copying a config whose gate angles are Reals).
        return (self._value,)


    @property
    def v(self):
        return self._value

    @property
    def mm(self):
        if isnative(self._value): return 'Float'
        else: return 'Symbolic'





    def rotate(self, theta):
        """This value rotated by theta radians: self · e^(iθ).
        (The pre-cleanup version computed e^(iθ·self) — a bug.)"""
        return self * (qify(theta) * I).exp

    def same(self, other):
        result = type(self) is type(other)
        return result

    def to_mode(self, mode=None):
        """Return an equivalent number in the given (default: current) mode."""
        if mode is None:
            mode = CalcMode.default()
        if self.mm == mode:
            return self
        return self.__class__(self._value, mode)

    @property
    def is_exact(self):
        """True when the representation is exact (no floating-point content) —
        i.e. its str() form is faithful and worth displaying as-is."""
        if isnative(self._value):
            return isinstance(self._value, int)
        return not self._value.has(sym.Float)

    @property
    def simplified(self):
        """Best-effort simplification; identity for native-backend values."""
        if isnative(self._value):
            return self
        return self.newme(sym.simplify(self._value))

    @property
    def is_bare_numeric(self):
        """True for plain numbers ('45', '1/2', 'sqrt(2)') — input a GUI
        may legitimately reinterpret through a deg/rad toggle. Values
        containing pi, free symbols, or function calls (acos(4/5)) are
        already radians by convention."""
        if isnative(self._value):
            return True
        v = self._value
        return not (v.has(sym.pi) or v.free_symbols or v.atoms(sym.Function))


    def __repr__(self):
        return f'Complex({self._value}, {self.mm})'

    def __str__(self):
        return f'{self._value}'

    def __format__(self, format_spec):
        try:
            return self._value.__format__(format_spec)
        except RecursionError:
            return str(self._value)

    def display(self, precision: int = 2) -> str:
        """Compact display: fixed-precision 're+imj' for float-backed
        values, the exact expression for symbolic ones — so Symbolic-mode
        logs and reprs stay float-free."""
        v = self._value
        if isnative(v):
            c = complex(v)
            return f'{c.real:.{precision}f}{c.imag:+.{precision}f}j'
        return str(v)

    def __complex__(self):
        return complex(self._value)

    def __bool__(self):
        """True if self != 0. Called for bool(self)."""
        return bool(self._value)

    @property
    def real(self):
        if isnative(self._value):
            val = self._value.real
        else:
            val = re(self._value).as_real_imag()[0]
        return Real(val, self.mm)

    @property
    def imag(self):
        if isnative(self._value): val = self._value.imag
        else: val = im(self._value).as_real_imag()[0]
        return Real(val, self.mm)

    @property
    def phase(self):
        if isnative(self._value): val = cm.phase(self._value)
        else:
            try:
                val = sym.arg(self._value)
                if val is sym.nan:
                    val = 0
            except ZeroDivisionError:
                val = 0
        return Real(val, self.mm)

    def __add__(self, other):
        return self.newme(self._value + otherv(other))

    def __radd__(self, other):
        return self.newme(otherv(other) + self._value)

    def __neg__(self):
        return self.newme(-self._value)

    def __pos__(self):
        return self.newme(+self._value)

    def __sub__(self, other):
        """self - other"""
        return self.newme(self._value + -otherv(other))

    def __rsub__(self, other):
        """other - self"""
        return self.newme(-self._value + otherv(other))

    def __mul__(self, other):
        """self * other"""
        return self.newme(self._value * otherv(other))

    def __rmul__(self, other):
        """self * other"""
        return self.newme(otherv(other) * self._value)

    def __truediv__(self, other):
        """self / other: Should promote to float when necessary."""
        return self.newme(self._value / otherv(other))

    def __rtruediv__(self, other):
        """other / self"""
        return self.newme(otherv(other) / self._value)

    def __pow__(self, exponent):
        """self ** exponent; should promote to float or complex when necessary."""
        return self.newme(self._value ** otherv(exponent))

    def __rpow__(self, base):
        """base ** self"""
        return self.newme(otherv(base) ** self._value)

    def __abs__(self):
        """Returns the Real distance from 0. Called for abs(self)."""
        return Real(abs(self._value))

    def __round__(self, n=None):
        # round the underlying values: rounding the Real properties
        # would re-enter this method and lose the digits argument
        if bool(self.imag == 0):
            return Real(_rounded(self.real.v, n))
        i = sym.I if issym(self._value) else 1j
        return Complex(_rounded(self.real.v, n)
                       + _rounded(self.imag.v, n) * i)

    def conjugate(self):
        """(x+y*i).conjugate() returns (x-y*i)."""
        return self.newme(self._value.conjugate())

    def __eq__(self, other) -> Any:
        # Returns a sympy Eq (not a bool) for symbolic values, so the
        # override is typed Any rather than bool.
        ov = otherv(other)
        if issym(self._value):
            return Eq(self._value, ov)
        else:
            return self._value == ov

    @property
    def cos(self):
        if iscplx(self._value): val = cm.cos(self._value)
        elif realtype(self._value): val = m.cos(self._value)
        else: val = sym.cos(self._value)
        return self.__class__(val)

    @property
    def sin(self):
        if iscplx(self._value): val = cm.sin(self._value)
        elif realtype(self._value): val = m.sin(self._value)
        else: val = sym.sin(self._value)
        return self.__class__(val)

    @property
    def exp(self):
        if iscplx(self._value):
            return Complex(cm.exp(self._value))
        elif realtype(self._value):
            return Real(m.exp(self._value))
        else:
            val = sym.exp(self._value)
            if floatable(val):
                return Real(val)
            else:
                return Complex(val)

    def sympify(self):
        return sym.sympify(self._value)

# noinspection PyAbstractClass
class Real(Complex):
    def __new__(cls, value: 'ANumber | Complex | str', mode: str | None = None) -> 'Real':
        if isinstance(value, cls):
            return value
        if not floatable(value):
            # Historical fallback for non-real input; presented as Real so
            # the common (real-valued) construction path types cleanly.
            return cast(Real, Complex(value, mode))
        instance =  super().__new__(cls, value, mode)
        return instance

    def __repr__(self):
        return f'Real({self._value}, mode={self.mm})'

    def __str__(self):
        return f'{self._value}'

    def as_integer_ratio(self):
        if realtype(self._value): val = self._value.as_integer_ratio()
        else:
            val = Rational(*float(self._value).as_integer_ratio())
        return self.__class__(val, self.mm)

    @property
    def degrees(self):
        if isinstance(self._value, float): val = m.degrees(self._value)
        else: val = deg(self._value)
        return Real(val, self.mm)

    @property
    def radians(self):
        if isinstance(self._value, float): val = m.radians(self._value)
        else: val = rad(self._value)
        return Real(val, self.mm)

    def __float__(self):
        return to_float(self._value)

    def __trunc__(self):
        if issym(self._value): val = sym.Integer(self._value)
        else: val = int(self._value)
        return Real(val)

    def __floor__(self):
        """Finds the greatest Integral <= self."""
        if issym(self._value): val = sym.floor(self._value)
        else: val = m.floor(self._value)
        return Real(val)

    def __ceil__(self):
        """Finds the least Integral >= self."""
        if issym(self._value): val = sym.ceiling(self._value)
        else: val = m.ceil(self._value)
        return Real(val)

    def __round__(self, ndigits=None):
        return Real(_rounded(self._value, ndigits))

    def __divmod__(self, other):
        ov = otherv(other)
        vdiv, vmod = divmod(self._value, ov)
        return Real(vdiv), Real(vmod)

    def __rdivmod__(self, other):
        ov = otherv(other)
        vdiv, vmod = divmod(ov, self._value)
        return Real(vdiv), Real(vmod)

    def __floordiv__(self, other):
        """self // other: The floor() of self/other."""
        return Real(self._value // otherv(other))

    def __rfloordiv__(self, other):
        """other // self: The floor() of other/self."""
        return Real(otherv(other) // self._value)

    def __mod__(self, other):
        """self % other"""
        return Real(self._value % otherv(other))

    def __rmod__(self, other):
        """other % self"""
        return Real(otherv(other) % self._value)

    def __lt__(self, other):
        return self._value < otherv(other)

    def __gt__(self, other):
        return self._value > otherv(other)

    # >= and <= are sometimes problematic in SymPy, thus this
    # complicated way of testing.
    def __ge__(self, other):
        if issym(self._value):
            ov = otherv(other)
            return Piecewise(
                (True, self._value > ov),
                (True, Eq(self._value, ov)),
                (False, True))
        else:
            return self._value >= otherv(other)

    def __le__(self, other):
        if issym(self._value):
            ov = otherv(other)
            return Piecewise(
                (True, self._value < ov),
                (True, Eq(self._value, ov)),
                (False, True))
        else:
            return self._value <= otherv(other)

def probability(w: Complex)-> Real:
    result = abs(w)**2
    return result

def prod(it):
    if not it:
        return Real(0)
    return reduce(mul, it)



ZERO = Real(0)

def PI_fn(mode=None):
    global PI
    if mode is None:
        mode = CALC_MODE
    if mode == 'Float':
        ret = Real(m.pi, mode)
    else:
        ret = Real(sym.pi, mode)
    PI = ret
    return ret

def I_fn(mode=None):
    global I
    if mode is None:
        mode = CALC_MODE
    if mode == 'Float':
        ret = Complex(1j, mode)
    else:
        ret = Complex(sym.I, mode)
    I = ret
    return ret

def E_fn(mode=None):
    global E
    if mode is None:
        mode = CALC_MODE
    if mode == 'Float':
        ret = Real(m.e, mode)
    else:
        ret = Real(sym.E, mode)
    E = ret
    return ret

float_zero_threshold = 1e-15

def zero_threshold_fn(mode=None):
    global ZERO_THRESHOLD
    if mode is None:
        mode = CALC_MODE
    if mode == 'Float':
        ret = float_zero_threshold
    else:
        ret = qify(0)
    ZERO_THRESHOLD = ret
    return ret

PI = PI_fn()
I = I_fn()
E = E_fn()
ZERO_THRESHOLD = zero_threshold_fn()

def enough(x, threshold):
    if not x: return False
    flx = to_float(x)
    tx = to_float(threshold)
    return flx >= tx

def zerop(x):
    """True iff x is treated as zero in the current calculation mode.

    Float mode: |x| < ZERO_THRESHOLD (the existing 1e-15 numeric tolerance).
    Symbolic mode: x simplifies to exactly 0 (no fuzzy threshold). Expressions
    that contain free symbols and don't reduce to a literal zero return False —
    we can't claim a symbolic weight is zero unless sympy can prove it.

    The answer is cached on Q-number instances (they are immutable by
    convention and created under the mode they are used in): the Symbolic
    test runs sympy.simplify, and the same few objects — e.g. a gate's
    four split components — get re-tested for every configuration-space
    point of every stage.
    """
    if isq(x):
        cached = getattr(x, '_zerop', None)
        if cached is None:
            cached = x._zerop = _zerop(x.v)
        return cached
    return _zerop(x)


def _zerop(x) -> bool:
    """The uncached mode-aware zero test on an unwrapped value."""
    if CalcMode.default() == 'Float':
        return not enough(abs(x), ZERO_THRESHOLD)
    if issym(x):
        return sym.simplify(x) == 0
    return x == 0


def simplify(w):
    """
    In Symbolic mode, run sympy.simplify on the wrapped value so that
    interference identities like cos(θ)² + sin(θ)² → 1 collapse before
    we test for zero or compare configs. No-op in Float mode.
    """
    if CalcMode.default() != 'Symbolic':
        return w
    if not isq(w):
        w = qify(w)
    simplified = sym.simplify(w.v)
    return w.__class__(simplified)


class _QNumberModule(__import__('types').ModuleType):
    """`qn.CalcMode = 'Symbolic'` reads as a mode switch and must act
    as one: a plain module-attribute assignment would silently replace
    the CalcMode class with a string and break every later constructor
    (the classic symptom: "'str' object has no attribute 'default'")."""

    def __setattr__(self, name, value):
        if name == 'CalcMode' and not isinstance(value, type):
            set_calc_mode(value)
            return
        super().__setattr__(name, value)


__import__('sys').modules[__name__].__class__ = _QNumberModule
