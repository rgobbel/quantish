"""A screen for any model that declares one.

A double-slit-style model says what its screen is in its `sweep`
section: the phase variable that sweeps across the screen (a phase
plate's phase, the pixel's path-length difference), the particle and
detector to observe, and optionally a particle whose final sign or
position sorts the hits. This module turns such a model into screen
curves and per-pixel intensities, with every other model variable
settable by name — the decoherence lab's engine side, and a general
form of double_slit.py's fixed conditions.

    spec = ScreenSpec.load('double_slit_eraser_chain')
    xs, curves = screen_curves(spec, {'theta_pre_2': math.radians(30)},
                               n_points=81, fringes=3, via='fit')
    # curves: {'+': [...], '−': [...]}  (the sorted groups) or {'all': [...]}

The three-run reconstruction (`via='fit'`, see double_slit.fringe_
coefficients) is valid when the swept variable enters the circuit
through exactly one phase plate and nothing else, so that every path
crosses it at most once; `spec.fit_ok` says whether it does, and
screen_curves falls back to one engine run per pixel otherwise.
"""
from __future__ import annotations

import copy
import functools
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from addict import Dict as Addict

from quantish.sweep import group_label

# the model library: the frozen copy under WASM, else the repo's
MODELS_ROOTS = (Path('/wasm-data/models'),
                Path(__file__).resolve().parent.parent / 'models')
COLLECTIONS = ('gr2026', 'gr2006', 'extras', 'decoherence')
VIA = ('pixels', 'fit')
DEFAULT_RANGE = (0.0, 180.0)   # degrees, for an angle no gate ranges
_CACHE: dict[str, dict] = {}


def models_root() -> Path:
    for root in MODELS_ROOTS:
        if root.is_dir():
            return root
    raise FileNotFoundError('no models directory')


def model_path(model_id: str) -> Path:
    """`collection/name` -> file; a bare name is looked up in every
    collection (the decoherence collection first, then extras)."""
    root = models_root()
    if '/' in model_id:
        p = root / f'{model_id}.yaml'
        if p.is_file():
            return p
        raise FileNotFoundError(f'models/{model_id}.yaml not found')
    for coll in ('decoherence', 'extras') + COLLECTIONS:
        p = root / coll / f'{model_id}.yaml'
        if p.is_file():
            return p
    raise FileNotFoundError(f'no models/*/{model_id}.yaml')


def register(model_id: str, config: dict) -> None:
    """Make a model known under an id without a file — an upload. The id
    should not collide with a library id (prefix it, say 'upload:')."""
    _CACHE[model_id] = copy.deepcopy(config)


def reload() -> None:
    """Forget every library model file read so far (uploads stay) and
    every simulation and pixel computed from them, so files edited on
    disk are read afresh on their next use — the apps' reload button."""
    for key in [k for k in _CACHE if not k.startswith('upload:')]:
        del _CACHE[key]
    _sim.cache_clear()
    _pixel.cache_clear()


def model_config(model_id: str) -> dict:
    """The model, parsed once (or registered) and deep-copied per use."""
    if model_id not in _CACHE:
        _CACHE[model_id] = yaml.safe_load(model_path(model_id).read_text())
    return copy.deepcopy(_CACHE[model_id])


def model_title(source) -> str:
    """A model file's title, or '' when it has none or cannot be read.
    `source` is a Path, or a library/upload id."""
    try:
        if isinstance(source, Path):
            cfg = yaml.safe_load(source.read_text()) or {}
        else:
            cfg = model_config(source)
    except Exception:  # noqa: BLE001 — an unreadable file simply has no title
        return ''
    return str(cfg.get('title') or '') if isinstance(cfg, dict) else ''


def model_label(stem: str, title: str = '') -> str:
    """How every app's model picker names a model: the file name (the
    identifier a user can find on disk and in the docs) followed by its
    title — 'fig4.17 — EPR experiment'."""
    return f'{stem} — {title}' if title else stem


def library() -> list[str]:
    """Every library model id, collection by collection, plus the
    registered uploads."""
    root = models_root()
    ids = []
    for coll in COLLECTIONS:
        d = root / coll
        if d.is_dir():
            ids += [f'{coll}/{p.stem}' for p in sorted(d.glob('*.yaml'))
                    if not p.name.startswith(('.', '#'))]
    ids += [k for k in _CACHE if k.startswith('upload:')]
    return ids


def screen_models() -> list[str]:
    """The library models with a screen (a sweep on a phase plate), by
    id — the double-slit family in extras and decoherence."""
    return [mid for mid in library() if ScreenSpec.load(mid).has_screen]


@dataclass
class ScreenSpec:
    """A model as the lab sees it: its settable variables and, when the
    model declares one, its screen (read from the sweep section)."""
    name: str                       # model id: 'extras/double_slit', 'upload:x'
    title: str
    caption: str
    notes: str
    phase_var: str | None           # the swept variable (a plate's phase)
    plate: str | None               # the phase plate carrying it
    observe: tuple[str, str] | None     # (particle, detector gate)
    group_by: tuple[str, str] | None    # (particle, 'sign'|'position'|'both')
    variables: dict = field(default_factory=dict)   # name -> spec, phase_var excluded
    fit_ok: bool = True
    config: dict = field(default_factory=dict, repr=False)

    @property
    def has_screen(self) -> bool:
        return self.plate is not None

    @classmethod
    def load(cls, model_id: str) -> ScreenSpec:
        cfg = model_config(model_id)
        if '/' not in model_id and not model_id.startswith('upload:'):
            model_id = str(model_path(model_id).relative_to(models_root()).with_suffix(''))
        sweep = cfg.get('sweep') or {}
        var = sweep.get('variable')
        plates = {k: str(v) for k, v in (cfg.get('phase_plates') or {}).items()}
        carriers = [k for k, spec in plates.items() if var and _mentions(spec, var)]
        screened = (var is not None and len(carriers) == 1
                    and plates[carriers[0]].strip() == var and 'observe' in sweep)
        fit_ok = False
        if screened:
            # the fit needs the phase to enter nowhere else: no gate
            # angle, no other plate, no other variable mentions it
            elsewhere = ([str(g.get('angle', '')) + ' ' + str(g.get('phase', ''))
                          for g in (cfg.get('gates') or {}).values()]
                         + [str(v) for k, v in (cfg.get('variables') or {}).items() if k != var])
            fit_ok = not any(_mentions(text, var) for text in elsewhere)
        observe = sweep.get('observe') or {}
        grp = sweep.get('group_by')
        variables = {k: v for k, v in (cfg.get('variables') or {}).items()
                     if not (screened and k == var)}
        return cls(name=model_id, title=str(cfg.get('title', model_id)),
                   caption=str(cfg.get('caption', '')), notes=str(cfg.get('notes', '')),
                   phase_var=var if screened else None,
                   plate=carriers[0] if screened else None,
                   observe=(observe['particle'], observe['at']) if screened else None,
                   group_by=((grp['particle'], grp.get('coordinate', 'sign'))
                             if screened and grp else None),
                   variables=variables, fit_ok=fit_ok, config=cfg)

    def angle_ranges(self) -> dict[str, tuple[float, float]]:
        """variable -> (low, high) in degrees: the gates' angle_range
        hints for the gates the variable sets (their intersection when
        several), DEFAULT_RANGE otherwise."""
        out = {k: DEFAULT_RANGE for k in self.variables}
        for spec in (self.config.get('gates') or {}).values():
            var = str(spec.get('angle', '')).strip()
            rng = spec.get('angle_range')
            if var in out and rng:
                lo, hi = out[var]
                out[var] = (max(lo, float(rng[0])), min(hi, float(rng[1])))
        return out

    def default_degrees(self) -> dict[str, float]:
        """Every settable variable's default, in degrees (the lab treats
        every variable as an angle), evaluated with the model's own
        variables as the environment."""
        from quantish.simulation import Simulation
        sim = Simulation(self.config_with({}))
        return {k: float(sim.qvars[k].degrees) for k in self.variables}

    def angle_gates(self) -> dict[str, str]:
        """gate name -> the settable variable that is its angle (only
        gates whose angle is exactly a variable name)."""
        out = {}
        for g, spec in (self.config.get('gates') or {}).items():
            angle = str(spec.get('angle', '')).strip()
            if angle in self.variables:
                out[g] = angle
        return out

    def group_names(self) -> tuple[str, ...]:
        if not self.has_screen:
            raise ValueError(f'{self.name} declares no screen')
        if self.group_by is None:
            return ('all',)
        if self.group_by[1] == 'sign':
            return ('+', '−')
        # positions and both: discovered from a run
        _, curves = screen_curves(self, {}, n_points=3, fringes=1.0, via='pixels')
        return tuple(curves)

    def config_with(self, variables: dict) -> Addict:
        """The model's config with the given variables set (radians;
        names the model does not declare are ignored)."""
        cfg = copy.deepcopy(self.config)
        cfg['loglevel'] = 'error'
        for k, v in variables.items():
            if k in self.variables:
                cfg['variables'][k] = v
        return Addict(cfg)

    def simulation(self, variables: dict):
        """A loaded, unrun Simulation with the variables set — for a
        circuit diagram, say."""
        from quantish.simulation import Simulation
        return Simulation(self.config_with(variables))


def _mentions(text: str, var: str) -> bool:
    return re.search(rf'(?<![\w.]){re.escape(var)}(?![\w])', str(text)) is not None


def _key(spec: ScreenSpec, variables: dict) -> tuple:
    return tuple(sorted((k, float(v)) for k, v in variables.items() if k in spec.variables))


@functools.lru_cache(maxsize=64)
def _sim(name: str, key: tuple):
    from quantish.simulation import Simulation
    spec = ScreenSpec.load(name)
    return spec, Simulation(spec.config_with(dict(key)))


@functools.lru_cache(maxsize=1 << 16)
def _pixel(name: str, key: tuple, phi: float) -> tuple:
    """((group, probability), ...) that the observed particle ends at
    the detector, sorted by the group particle's coordinate, for one
    phase — one engine run (the loaded Simulation is reused, only the
    plate's phase changes)."""
    spec, sim = _sim(name, key)
    sim.phase_plates[spec.plate].set_phase(phi)
    sim.run()
    particle, detector = spec.observe
    strings = dict(sim.config.get('display_strings') or {})
    by_group: dict[str, float] = {}
    for point in sim.result_space.index.values():
        origin = point.coords[particle].position.origin
        if origin is None or origin.gate != detector:
            continue
        if spec.group_by is None:
            label = 'all'
        else:
            label = group_label(point.coords[spec.group_by[0]], spec.group_by[1], strings)
        by_group[label] = by_group.get(label, 0.0) + float(point.probability)
    return tuple(sorted(by_group.items(), key=lambda kv: (kv[0].lstrip('+−'), kv[0])))


def pixel(spec: ScreenSpec, variables: dict, phi: float) -> dict[str, float]:
    return dict(_pixel(spec.name, _key(spec, variables), float(phi)))


def screen_positions(n_points: int) -> list[float]:
    return [-1.0 + 2.0 * i / (n_points - 1) for i in range(n_points)]


def screen_curves(spec: ScreenSpec, variables: dict, n_points: int = 81,
                  fringes: float = 3.0, via: str = 'fit'
                  ) -> tuple[list[float], dict[str, list[float]]]:
    """(positions, {group: intensities}) across the screen: the phase
    sweeps `fringes` periods over x in [-1, 1]. via='fit' uses the
    three-run reconstruction when the model allows it (spec.fit_ok),
    one engine run per pixel otherwise."""
    if via not in VIA:
        raise ValueError(f'via must be one of {VIA}, not {via!r}')
    xs = screen_positions(n_points)
    groups = list(spec.group_names())
    if via == 'fit' and spec.fit_ok:
        at = [pixel(spec, variables, phi) for phi in (0.0, math.pi / 2, math.pi)]
        curves = {}
        for g in groups:
            p0, p1, p2 = (at[k].get(g, 0.0) for k in range(3))
            a, b, c = (p0 + p2) / 2, (p0 - p2) / 2, p1 - (p0 + p2) / 2
            curves[g] = [a + b * math.cos(fringes * math.pi * x)
                         + c * math.sin(fringes * math.pi * x) for x in xs]
        return xs, curves
    per_x = [pixel(spec, variables, fringes * math.pi * x) for x in xs]
    return xs, {g: [p.get(g, 0.0) for p in per_x] for g in groups}


def visibility(ys: list[float]) -> float | None:
    hi, lo = max(ys), min(ys)
    return None if hi + lo < 1e-12 else (hi - lo) / (hi + lo)
