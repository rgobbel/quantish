"""Particles, post-refactor: a particle is a named thing with a sign and an
initial weight. During simulation, weights belong to configuration-space
points (see config_space.py) — a Particle only supplies the initial
conditions parsed from the model YAML, and labels for diagrams.
"""
from collections import namedtuple

from quantish.qnumber import Complex, probability, qify, zerop
from quantish.util import Sign

# the separator of a two-sign weight spec: 'plus; minus'
SIGN_SEP = ';'


def sign_components(spec, sign=Sign.plus, env: dict | None = None) -> dict:
    """A weight spec as {sign: Complex}. A plain spec ('1', '0.7@30°', a
    variable) is one component with the given sign. A two-sign spec
    'a; b' — the plus component, then the minus, either possibly empty
    (zero) — puts the particle in a superposition of its two signs on
    one wire, the shape a gate's output has; it carries its own signs,
    so `sign` must be None or plus (a declared minus contradicts it).
    """
    if isinstance(spec, str) and SIGN_SEP in spec:
        halves = spec.split(SIGN_SEP)
        if len(halves) != 2:
            raise ValueError(f"weight {spec!r}: a two-sign weight is "
                             f"'plus{SIGN_SEP} minus', two components")
        if sign is not None and Sign(sign) != Sign.plus:
            raise ValueError(f"weight {spec!r} carries both signs, so "
                             f"sign must not be declared as {Sign(sign)!r}")
        return {s: Complex(qify(h.strip() or 0, env))
                for s, h in zip((Sign.plus, Sign.minus), halves)}
    return {Sign(Sign.plus if sign is None else sign): Complex(qify(spec, env))}

CompositeKey = namedtuple('CompositeKey', ['name', 'sign'])

class PKey(CompositeKey):
    __slots__ = ()
    def __repr__(self):
        # sign first ('+p1'), the convention of every particle display:
        # the sign is a coordinate, not a modifier of the name
        return f'{self.sign}{self.name}'


class Particle:
    """`components` is the particle's initial weight per sign
    ({Sign: Complex}, see sign_components); `weight` and `sign` read
    the one nonzero component of an ordinary particle. A particle
    with both components nonzero is `superposed`: its sign is then a
    coordinate that differs between its initial configuration-space
    points, and `sign`/`weight` read the plus component (displays that
    need one line per particle check `superposed` first)."""

    def __init__(self, name: str, weight=1, sign=Sign.plus, precision: int = 2,
                 components: dict | None = None):
        assert len(name) > 0
        self.name = name
        if components is None:
            components = {Sign(sign): Complex(weight)}
        self.components = {Sign(s): Complex(w) for s, w in components.items()}
        # weights per destination, when the particle's link carries them:
        # one {Sign: Complex} per arm (the loader fills this in); the
        # components are then a plain factor on every arm
        self.arms = None
        self.precision = precision

    @property
    def live(self) -> dict:
        """The nonzero components, in sign order (plus first)."""
        return {s: w for s, w in sorted(self.components.items(), reverse=True)
                if not zerop(w)}

    @property
    def signs(self) -> set:
        """The signs the particle starts with somewhere (either sign of
        a two-sign weight, or of any weighted arm)."""
        if self.arms is None:
            return set(self.live)
        return {s for arm in self.arms for s, w in arm.items()
                if not zerop(w) and self.live}

    @property
    def superposed(self) -> bool:
        return len(self.signs) > 1

    @property
    def absent(self) -> bool:
        return not self.signs

    @property
    def sign(self) -> Sign:
        return next(iter(self.live), Sign.plus)

    @property
    def weight(self) -> Complex:
        return self.components.get(self.sign, Complex(0))

    def __repr__(self):
        return f'{"±" if self.superposed else self.sign}{self.name}'

    @property
    def pkey(self):
        return PKey(name=self.name, sign=self.sign)

    @property
    def probability(self):
        return probability(self.weight)

