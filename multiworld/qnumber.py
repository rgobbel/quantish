import logging
import numbers as n
import sympy as sym
from sympy import re, im, Rational, deg, rad, Eq, Piecewise
import math as m
import cmath as cm
import re as rex
import scipy.special as sci

log = logging.getLogger('multiworld')

CALC_MODE = 'Float'

def _set_calc_mode(new_mode: str) -> str:
    global I, PI, CALC_MODE
    CALC_MODE = new_mode
    if CALC_MODE == 'Float':
        I = 1j
        PI = m.pi
    else:
        I = sym.I
        PI = sym.pi
    return CALC_MODE


class _CalcModeMeta(type):
    """Metaclass so `CalcMode.mode` is a real settable property at the class level.

    Reading `CalcMode.mode` returns the current global mode; assigning to
    `CalcMode.mode = 'Symbolic'` updates CALC_MODE and the I / PI globals,
    keeping behavior consistent with `CalcMode.default('Symbolic')`.
    """
    @property
    def mode(cls):
        return CALC_MODE

    @mode.setter
    def mode(cls, new_mode):
        _set_calc_mode(new_mode)


class CalcMode(metaclass=_CalcModeMeta):
    @classmethod
    def default(cls, new_mode: str = None):
        if new_mode is None or new_mode == '':
            return CALC_MODE
        return _set_calc_mode(new_mode)


# realtype = lambda x: type(x) in (int, float)
def realtype(x):
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

iscplx = lambda x: type(x) is complex
isnative = lambda x: type(x) in (int, float, complex)
def isq(x):
    return isinstance(x, Complex)

issym = lambda x: rex.match('sympy', type(x).__module__) is not None
otherv = lambda x: x.v if isq(x) else x

DEBUG = False

Modes = ['Symbolic', 'Float']

def to_float(x):
    try:
        result = float(x)
    except TypeError:
        if sym.im(x) == 0:
            result = complex(x).real
        else:
            raise
    return result

def to_native(x):
    try:
        result = float(x)
    except TypeError:
        result = complex(x)
    return result

def qify(x):
    if isq(x): return x
    elif iscplx(x): return Complex(x)
    xval = sym.sympify(x)
    try:
        _ = float(xval)
        return Real(xval)
    except TypeError:
        return Complex(xval)

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

class partialproperty:
    """Combine the functionality of property() and partialmethod()"""
    def __init__(self, getter, *args, **kwargs):
        self.getter = getter
        self.args = args
        self.kwargs = kwargs

    def __set_name__(self, owner, name):
        self._name = name
        self._owner = owner

    def __get__(self, obj, objtype=None):
        return self.getter(obj, *self.args, **self.kwargs)

ANumber = int | float | complex | sym.Mul | sym.Integer | sym.Float | sym.Expr

class Complex(n.Number):
    def __new__(cls, value=0, mode:str=None):
        instance = super().__new__(cls)
        if mode is None:
            mode = CalcMode.default()
        instance.__init__(value=value, mode=mode)
        return instance

    def __init__(self, value, mode:str=None):
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

    # @classmethod
    def rotate(self, theta):
        return self.newme(self._value * (I * qify(theta))).exp

    def newme(self, x):
        return self.__class__(x)

    def __hash__(self):
        return self._value.__hash__()

    def same(self, other):
        result = type(self) is type(other)
        return result

    @property
    def v(self):
        return self._value

    @property
    def mm(self):
        if isnative(self._value): return 'Float'
        else: return 'Symbolic'

    def __repr__(self):
        return f'Complex({self._value}, {self.mm})'

    def __str__(self):
        return f'{self._value}'

    def __format__(self, format_spec):
        try:
            return self._value.__format__(format_spec)
        except RecursionError:
            return str(self._value)

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

    def conjugate(self):
        """(x+y*i).conjugate() returns (x-y*i)."""
        return self.newme(self._value.conjugate())

    def __eq__(self, other):
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

# Complex.register(complex)

# noinspection PyAbstractClass
class Real(Complex):
    def __new__(cls, value, mode:str=None):
        if isinstance(value, cls):
            return value
        if not floatable(value):
            return Complex(value, mode)
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
        if issym(self._value): val = self._value.round()
        else: val = round(self._value, ndigits)
        return Real(val)

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

ZERO = Real(0)

def runtest(x, y):
    try:
        return x % y
    except TypeError as e:
        log.error(e)

def PI_fn(mode=None):
    global PI
    if mode is None:
        mode = CALC_MODE
    if mode == 'Float':
        return Real(m.pi, mode)
    else:
        return Real(sym.pi, mode)

def I_fn(mode=None):
    global I
    if mode is None:
        mode = CALC_MODE
    if mode == 'Float':
        return Complex(1j, mode)
    else:
        return Complex(sym.I, mode)

float_zero_threshold = 1e-15

def zero_threshold_fn(mode=None):
    global ZERO_THRESHOLD
    if mode is None:
        mode = CALC_MODE
    if mode == 'Float':
        return float_zero_threshold
    else:
        return qify(0)

PI = PI_fn()
I = I_fn()
ZERO_THRESHOLD = zero_threshold_fn()

def enough(x, threshold):
    if not x: return False
    flx = to_float(x)
    tx = to_float(threshold)
    return flx >= tx

def zerop(x):
    return not enough(abs(x), ZERO_THRESHOLD)
