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
    variable_notes: dict = field(default_factory=dict)  # name -> a line under its slider
    synthetic: dict = field(default_factory=dict)   # variable -> the gate it was made for
    override: tuple = ()            # a sweep defined in the app, frozen (see load)
    fit_ok: bool = True
    config: dict = field(default_factory=dict, repr=False)

    @property
    def has_screen(self) -> bool:
        return self.plate is not None

    @classmethod
    def load(cls, model_id: str, sweep: dict | None = None) -> ScreenSpec:
        """The model as the lab sees it. `sweep` (an app's own screen
        definition) replaces the model's sweep section: {'plate': the
        phase plate to sweep or None for no screen, 'observe':
        {'particle', 'at'}, 'group_by': {'particle', 'coordinate'} or
        None}."""
        cfg = model_config(model_id)
        if '/' not in model_id and not model_id.startswith('upload:'):
            model_id = str(model_path(model_id).relative_to(models_root()).with_suffix(''))
        plates = {k: str(v) for k, v in (cfg.get('phase_plates') or {}).items()}
        # every gate gets a slider: a gate whose angle is a literal (the
        # recorders' `angle: 0`) is given a variable of its own, named
        # for the gate, set to that literal in degrees — the model's
        # own variables and expressions over them are left alone; a
        # phase plate likewise, for its phase (a swept plate's is taken
        # back out of the sliders below)
        synthetic = {}
        declared = set(cfg.get('variables') or {})
        literal = [g for g, gspec in (cfg.get('gates') or {}).items()
                   if not any(_mentions(str(gspec.get('angle', '')), v) for v in declared)]
        literal_plates = [p for p, pspec in plates.items()
                          if not any(_mentions(pspec, v) for v in declared)]
        if literal or literal_plates:
            from quantish.simulation import Simulation
            sim = Simulation(Addict({**copy.deepcopy(cfg), 'loglevel': 'error'}))
            for g in literal:
                name = f'theta_{g}'
                deg = float(sim.gates[g].theta.degrees)
                cfg.setdefault('variables', {})[name] = f'{deg:.10g}°'
                cfg['gates'][g]['angle'] = name
                synthetic[name] = g
            for p in literal_plates:
                name = f'phi_{p}'
                deg = float(sim.gates[p].phase.degrees)
                cfg.setdefault('variables', {})[name] = f'{deg:.10g}°'
                cfg['phase_plates'][p] = name
                plates[p] = name
                synthetic[name] = p
        override = ()
        if sweep is not None:
            # the app's definition: the plate names the variable
            override = _freeze(sweep)
            plate = sweep.get('plate')
            cfg['sweep'] = ({'variable': plates[plate].strip(), 'from': 0, 'to': '2*pi',
                             'observe': dict(sweep.get('observe') or {}),
                             **({'group_by': dict(sweep['group_by'])}
                                if sweep.get('group_by') else {})}
                            if plate in plates else None)
        sweep = cfg.get('sweep') or {}
        var = sweep.get('variable')
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
        synthetic = {k: v for k, v in synthetic.items() if k in variables}
        return cls(name=model_id, title=str(cfg.get('title', model_id)),
                   caption=str(cfg.get('caption', '')), notes=str(cfg.get('notes', '')),
                   phase_var=var if screened else None,
                   plate=carriers[0] if screened else None,
                   observe=(observe['particle'], observe['at']) if screened else None,
                   group_by=((grp['particle'], grp.get('coordinate', 'sign'))
                             if screened and grp else None),
                   variables=variables,
                   variable_notes={k: str(v) for k, v in (cfg.get('variable_notes') or {}).items()},
                   synthetic=synthetic, override=override, fit_ok=fit_ok, config=cfg)

    @property
    def plates(self) -> list[str]:
        return list(self.config.get('phase_plates') or {})

    @property
    def gate_names(self) -> list[str]:
        """Every gate a particle can end at: gates, delays, plates."""
        return (list(self.config.get('gates') or {}) + list(self.config.get('delay_gates') or [])
                + self.plates)

    def screen_definition(self) -> dict:
        """The screen as {'plate', 'observe', 'group_by'} — the app's
        editable form, from the model's sweep or the override."""
        return {'plate': self.plate,
                'observe': ({'particle': self.observe[0], 'at': self.observe[1]}
                            if self.observe else {}),
                'group_by': ({'particle': self.group_by[0], 'coordinate': self.group_by[1]}
                             if self.group_by else None)}

    def angle_ranges(self) -> dict[str, tuple[float, float]]:
        """variable -> (low, high) in degrees: the gates' angle_range
        hints for the gates the variable sets (their intersection when
        several), DEFAULT_RANGE otherwise."""
        out = {k: DEFAULT_RANGE for k in self.variables}
        # a plate's phase runs the full turn
        for var in (self.config.get('phase_plates') or {}).values():
            if str(var).strip() in out:
                out[str(var).strip()] = (0.0, 360.0)
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
        gates whose angle is exactly a variable name; phase plates
        likewise, by their phase — the swept plate's is not settable)."""
        out = {}
        for g, spec in (self.config.get('gates') or {}).items():
            angle = str(spec.get('angle', '')).strip()
            if angle in self.variables:
                out[g] = angle
        for p, spec in (self.config.get('phase_plates') or {}).items():
            if str(spec).strip() in self.variables:      # a plate's settable phase
                out[p] = str(spec).strip()
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

    def simulation(self, variables: dict, inert: tuple = (), absent: tuple = ()):
        """A loaded, unrun Simulation with the variables set — for a
        circuit diagram, say — and, with `inert`, those gates switched
        off (wires: every particle passes straight through), with
        `absent`, those particles left out (null inputs)."""
        from quantish.simulation import Simulation
        return Simulation(self.config_with(variables), inert=tuple(inert),
                          absent=tuple(absent))


def _mentions(text: str, var: str) -> bool:
    return re.search(rf'(?<![\w.]){re.escape(var)}(?![\w])', str(text)) is not None


def _key(spec: ScreenSpec, variables: dict, inert: tuple = ()) -> tuple:
    """The cache key: the settable variables — less those that only set
    the angles of inert gates, which cannot matter to the run."""
    if inert:
        used_elsewhere = {v for g, v in spec.angle_gates().items() if g not in inert}
        idle = {v for g, v in spec.angle_gates().items() if g in inert} - used_elsewhere
    else:
        idle = set()
    return tuple(sorted((k, float(v)) for k, v in variables.items()
                        if k in spec.variables and k not in idle))


def _freeze(d) -> tuple:
    """A sweep definition as a hashable tuple (cache keys)."""
    if isinstance(d, dict):
        return tuple((k, _freeze(v)) for k, v in sorted(d.items()))
    return d


def _thaw(t):
    if isinstance(t, tuple):
        return {k: _thaw(v) for k, v in t}
    return t


@functools.lru_cache(maxsize=256)
def _sim(name: str, key: tuple, inert: tuple = (), absent: tuple = (), override: tuple = ()):
    from quantish.simulation import Simulation
    spec = ScreenSpec.load(name, sweep=_thaw(override) if override else None)
    return spec, Simulation(spec.config_with(dict(key)), inert=tuple(inert),
                            absent=tuple(absent))


@functools.lru_cache(maxsize=1 << 16)
def _pixel(name: str, key: tuple, phi: float, inert: tuple = (), absent: tuple = (),
           override: tuple = ()) -> tuple:
    """((group, probability), ...) that the observed particle ends at
    the detector, sorted by the group particle's coordinate, for one
    phase — one engine run (the loaded Simulation is reused, only the
    plate's phase changes). `inert` names gates switched off, `absent`
    particles left out: an absent observed particle makes no hits, an
    absent sort particle leaves the hits unsorted ('all')."""
    spec, sim = _sim(name, key, inert, absent, override)
    sim.phase_plates[spec.plate].set_phase(phi)
    sim.run()
    particle, detector = spec.observe
    strings = dict(sim.config.get('display_strings') or {})
    by_group: dict[str, float] = {}
    for point in sim.result_space.index.values():
        coord = point.coords.get(particle)
        origin = coord.position.origin if coord is not None else None
        if origin is None or origin.gate != detector:
            continue
        sort = point.coords.get(spec.group_by[0]) if spec.group_by else None
        label = 'all' if sort is None else group_label(sort, spec.group_by[1], strings)
        by_group[label] = by_group.get(label, 0.0) + float(point.probability)
    return tuple(sorted(by_group.items(), key=lambda kv: (kv[0].lstrip('+−'), kv[0])))


def pixel(spec: ScreenSpec, variables: dict, phi: float, inert: tuple = (),
          absent: tuple = ()) -> dict[str, float]:
    inert, absent = tuple(inert), tuple(absent)
    return dict(_pixel(spec.name, _key(spec, variables, inert), float(phi), inert, absent,
                       spec.override))


def screen_positions(n_points: int) -> list[float]:
    return [-1.0 + 2.0 * i / (n_points - 1) for i in range(n_points)]


def screen_curves(spec: ScreenSpec, variables: dict, n_points: int = 81,
                  fringes: float = 3.0, via: str = 'fit', inert: tuple = (),
                  absent: tuple = ()) -> tuple[list[float], dict[str, list[float]]]:
    """(positions, {group: intensities}) across the screen: the phase
    sweeps `fringes` periods over x in [-1, 1]. via='fit' uses the
    three-run reconstruction when the model allows it (spec.fit_ok),
    one engine run per pixel otherwise. `inert` names gates switched
    off for the run (wires), `absent` particles left out of it."""
    if via not in VIA:
        raise ValueError(f'via must be one of {VIA}, not {via!r}')
    xs = screen_positions(n_points)
    inert, absent = tuple(inert), tuple(absent)
    groups = list(_groups(spec, absent))
    if via == 'fit' and spec.fit_ok:
        at = [pixel(spec, variables, phi, inert, absent) for phi in (0.0, math.pi / 2, math.pi)]
        curves = {}
        for g in groups:
            p0, p1, p2 = (at[k].get(g, 0.0) for k in range(3))
            a, b, c = (p0 + p2) / 2, (p0 - p2) / 2, p1 - (p0 + p2) / 2
            curves[g] = [a + b * math.cos(fringes * math.pi * x)
                         + c * math.sin(fringes * math.pi * x) for x in xs]
        return xs, curves
    per_x = [pixel(spec, variables, fringes * math.pi * x, inert, absent) for x in xs]
    return xs, {g: [p.get(g, 0.0) for p in per_x] for g in groups}


def _groups(spec: ScreenSpec, absent: tuple = ()) -> tuple[str, ...]:
    # the sort needs its particle: without it the hits are one group
    if spec.group_by and spec.group_by[0] in absent:
        return ('all',)
    return spec.group_names()


def _fit_curves(spec: ScreenSpec, variables: dict, xs: list[float], fringes: float,
                inert: tuple, symmetric: bool, absent: tuple = ()) -> dict[str, list[float]]:
    """The three-run reconstruction a + b cos φ + c sin φ; with
    `symmetric` (c known to be 0) two runs, at φ = 0 and π."""
    phis = (0.0, math.pi) if symmetric else (0.0, math.pi / 2, math.pi)
    at = [pixel(spec, variables, phi, inert, absent) for phi in phis]
    curves = {}
    for g in _groups(spec, absent):
        p0, p2 = at[0].get(g, 0.0), at[-1].get(g, 0.0)
        a, b = (p0 + p2) / 2, (p0 - p2) / 2
        c = 0.0 if symmetric else at[1].get(g, 0.0) - a
        curves[g] = [a + b * math.cos(fringes * math.pi * x)
                     + c * math.sin(fringes * math.pi * x) for x in xs]
    return curves


def stage_screens(spec: ScreenSpec, variables: dict, n_points: int = 81,
                  fringes: float = 3.0, via: str = 'fit', sim=None,
                  inert: tuple = (), absent: tuple = ()) -> tuple[list[float], list[dict]]:
    """The virtual screens: what the model's own screen would show if
    the paths were merged right after each stage. Each is the same run
    with the environment frozen at that stage — every later gate the
    observed particle does not traverse switched off (inert) — so the
    sort sees the recorder as it stands there. Delayed choice makes
    this honest: a gate acting on the environment alone gives the same
    screen wherever it is staged.

    (positions, [{'step', 'name', 'gates', 'switched', 'curves'}, ...])
    for the stages up to the plate in which some particle was split
    (the others would repeat the screen before them), and then, always,
    the model's own screen as 'actual screen' — which differs from the
    last virtual one only when a gate acts on the environment after the
    merge (an eraser staged late). `sim` is the model already run at its
    own phase, when the caller has one; `inert` names gates switched off
    throughout (the lab's gate toggles) — the freeze adds to them — and
    `absent` particles left out. Without the observed particle there is
    no screen: an empty list."""
    from quantish.coherence import REAL_TOL, path_coherence
    if via not in VIA:
        raise ValueError(f'via must be one of {VIA}, not {via!r}')
    if not spec.has_screen:
        raise ValueError(f'{spec.name} declares no screen')
    base, absent = tuple(inert), tuple(absent)
    xs = screen_positions(n_points)
    observe = spec.observe[0]
    if observe in absent:
        return xs, []
    if sim is None:
        sim = spec.simulation(variables, base, absent)
        sim.run()
    group_by = None if spec.group_by and spec.group_by[0] in absent else spec.group_by
    rows = path_coherence(sim, observe, group_by, upto_gate=spec.plate)
    acting = [r for r in rows if r.switched]
    # the gates that switch the observed particle are the tail (with the
    # plate); every other gate — a recorder it merely controls, the
    # recorder's own gates, an eraser — is the environment, frozen
    # after the stage
    switching = set()
    for pt in sim.all_points.index.values():
        pos = pt.coords[observe].position
        switching |= {p.gate for p in (pos.origin, pos.endpoint)
                      if p is not None and p.gate and p.port in ('upper', 'lower')}
    environment = [g for g in sim.gates if g not in switching and g != spec.plate]
    # the fringes carry no sine term when the coherences are all real
    # (the phase between the paths is 0 or π): then two runs fix a
    # screen, once the first virtual screen (three runs) shows the
    # tail adds no shift of its own
    real = all(z is None or abs(z.imag) < REAL_TOL
               for r in rows for z in (r.whole, *r.groups.values()))
    fit = via == 'fit' and spec.fit_ok
    out, symmetric, last_values = [], False, None

    def values(row):
        return [None if z is None else (round(z.real, 9), round(z.imag, 9))
                for z in (row.whole, *row.groups.values())]

    for r in acting:
        inert = base + tuple(g for g in environment
                             if sim.gate_step[g] > r.step and g not in base)
        if out and values(r) == last_values:
            # nothing the screen can see changed: the same screen again
            curves = out[-1]['curves']
        elif fit:
            curves = _fit_curves(spec, variables, xs, fringes, inert, symmetric, absent)
            if not symmetric and real:
                symmetric = all(abs(ys[len(ys) // 4] - ys[-1 - len(ys) // 4]) < 1e-9
                                for ys in curves.values())   # c = 0: symmetric about x = 0
        else:
            _, curves = screen_curves(spec, variables, n_points, fringes, via,
                                      inert=inert, absent=absent)
        last_values = values(r)
        out.append({'step': r.step, 'name': r.name, 'gates': r.gates,
                    'switched': r.switched, 'curves': curves})
    # the model's own screen closes the progression: it differs from the
    # last virtual strip only when a gate acts on the environment after
    # the merge (an eraser staged late), and it is always shown so the
    # list never changes shape as the sliders move
    _, final = screen_curves(spec, variables, n_points, fringes, via, inert=base, absent=absent)
    tail = [g for g in environment
            if not out or sim.gate_step[g] > out[-1]['step']]
    out.append({'step': len(sim.run_stages), 'name': 'actual screen',
                'gates': [g for g in tail if sim.gates[g].report_type() != 'DelayGate'],
                'switched': [], 'curves': final})
    return xs, out


def visibility(ys: list[float]) -> float | None:
    hi, lo = max(ys), min(ys)
    return None if hi + lo < 1e-12 else (hi - lo) / (hi + lo)
