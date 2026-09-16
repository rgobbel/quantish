"""What passes between the apps: a model as a value (`ModelSlot` — the
builder's result, which the quantish app and the decoherence lab open
as they open any model file) and a gate's split as a value
(`ExplorerSeed` — one gate out of a run, with the weight arriving on its
switch wires, which the Weight-split Explorer opens on). Each app
standing alone hands these over through what the pages share — the
models directory (locally: the repo's gitignored models/uploads/; a
rescan finds it) and the explorer page's query string; in one kernel
(the suite) they ride a shared state instead.
"""
from __future__ import annotations

import cmath
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlencode

import yaml

from quantish import screen
from quantish.apps.common import MODELS_TOP, merge_defaults
from quantish.builder import config_to_yaml
from quantish.display import phase_deg
from quantish.util import Sign

UPLOADS = 'uploads'   # the collection the apps share at runtime


@dataclass
class ModelSlot:
    """A model as a value: its YAML text (comments and all), the file
    stem it is saved under, and its title."""
    yaml_text: str
    file: str = 'my_network'
    title: str = ''

    @classmethod
    def from_builder(cls, config: dict, raw_sections: dict | None = None,
                     file: str = 'my_network') -> ModelSlot:
        """The builder's derived config (and the sections it keeps
        verbatim) as a slot."""
        return cls(config_to_yaml(config, raw_sections=raw_sections), file,
                   str(config.get('title') or file))

    @classmethod
    def from_file(cls, path: Path) -> ModelSlot:
        text = Path(path).read_text()
        return cls(text, Path(path).stem, screen.model_title(Path(path)))

    @property
    def model(self) -> dict:
        return yaml.safe_load(self.yaml_text) or {}

    @property
    def model_id(self) -> str:
        """The id the lab's catalog gives the saved copy."""
        return f'{UPLOADS}/{self.file}'

    def to_config(self, top: Path = MODELS_TOP):
        """The model over the defaults, as `Simulation` takes it."""
        return merge_defaults(self.model, top)

    def save(self, top: Path = MODELS_TOP) -> Path:
        """Write the model into the shared `uploads` collection (the
        page's virtual filesystem under WASM, models/uploads/ from the
        repo) and register it with the lab's catalog; the path."""
        d = top / UPLOADS
        d.mkdir(parents=True, exist_ok=True)
        path = d / f'{self.file}.yaml'
        path.write_text(self.yaml_text)
        screen.register(self.model_id, self.model)
        return path


def incoming_weights(sim, gate: str) -> dict[tuple[str, Sign], complex]:
    """What arrives on `gate`'s switch wires in the run: per (particle,
    sign), the sum of the weights of the configuration-space points, at
    the step before the gate's stage, whose coordinate for that particle
    ends at the gate's upper or lower port. A marginal amplitude — the
    weight the gate would split if that particle's coordinate factored
    out of the superposition; exact when it does."""
    out: dict = {}
    if sim.all_points is None or gate not in sim.gate_step:
        return out
    before = sim.gate_step[gate] - 1
    for point in sim.all_points.index.values():
        if point.step != before or point.canceled:
            continue
        for pname, coord in point.coords.items():
            end = coord.position.endpoint
            if end is not None and end.gate == gate and end.port in ('upper', 'lower'):
                key = (pname, coord.sign)
                out[key] = out.get(key, 0) + complex(point.weight)
    return out


@dataclass
class ExplorerSeed:
    """One gate's split as the explorer opens on it: the gate's angle,
    the arriving weight (magnitude and phase) and its sign, and where it
    came from."""
    theta_deg: float
    wmag: float = 1.0
    wphase_deg: float = 0.0
    plus_sign: bool = True
    gate: str = ''
    particle: str = ''
    model: str = ''
    # every (particle, sign) arriving at the gate, for a chooser
    arrivals: list = field(default_factory=list)

    @property
    def weight(self) -> complex:
        return self.wmag * cmath.exp(1j * math.radians(self.wphase_deg))

    @classmethod
    def from_run(cls, sim, gate: str, particle: str | None = None,
                 sign: Sign | None = None) -> ExplorerSeed | None:
        """The seed for `gate` out of a finished run: its angle and, of
        the weights arriving on its switch wires, the chosen particle's
        (and sign's), else the first by name. None when the gate is not
        a Fredkin gate of the run or nothing arrives on its switch
        wires (a control-only pass-through)."""
        if gate not in sim.fredkin_gates:
            return None
        weights = incoming_weights(sim, gate)
        if not weights:
            return None
        keys = sorted(weights, key=lambda k: (k[0], -int(k[1])))
        pick = next((k for k in keys
                     if (particle is None or k[0] == particle)
                     and (sign is None or k[1] == sign)), keys[0])
        w = weights[pick]
        return cls(theta_deg=float(sim.fredkin_gates[gate].theta.degrees),
                   wmag=abs(w), wphase_deg=phase_deg(w),
                   plus_sign=pick[1] == Sign.plus, gate=gate, particle=pick[0],
                   model=str(getattr(sim, 'title', '') or ''),
                   arrivals=[(k[0], int(k[1])) for k in keys])

    def as_controls(self) -> dict:
        """The seed as `explorer_controls(seed)` takes it."""
        return {'theta_deg': self.theta_deg, 'plus_sign': self.plus_sign,
                'wmag': self.wmag, 'wphase_deg': self.wphase_deg}

    def to_query(self) -> dict[str, str]:
        """The seed as the explorer page's query string carries it."""
        q = {'theta': f'{self.theta_deg:g}', 'wmag': f'{self.wmag:g}',
             'wphase': f'{self.wphase_deg:g}', 'sign': '+' if self.plus_sign else '-'}
        for k in ('gate', 'particle', 'model'):
            if getattr(self, k):
                q[k] = getattr(self, k)
        return q

    @classmethod
    def from_query(cls, params) -> ExplorerSeed | None:
        """A seed from a page's query parameters (anything with .get),
        or None when they carry no angle."""
        theta = params.get('theta') if params is not None else None
        if theta in (None, ''):
            return None
        try:
            return cls(theta_deg=float(theta),
                       wmag=float(params.get('wmag') or 1.0),
                       wphase_deg=float(params.get('wphase') or 0.0),
                       plus_sign=(params.get('sign') or '+') != '-',
                       gate=str(params.get('gate') or ''),
                       particle=str(params.get('particle') or ''),
                       model=str(params.get('model') or ''))
        except (TypeError, ValueError):
            return None

    def describe(self) -> str:
        """One line: where the seed came from and what it carries."""
        where = (f'{self.particle} ({"+" if self.plus_sign else "−"}) entering '
                 f'{self.gate}' + (f' in {self.model}' if self.model else ''))
        return (f'{where}: θ = {self.theta_deg:g}°, |w| = {self.wmag:.3f}, '
                f'φ(w) = {self.wphase_deg:.1f}°')

    def as_dict(self) -> dict:
        return asdict(self)


def explorer_url(seed: ExplorerSeed, base: str = '../weight_split_app/') -> str:
    """The explorer page opened on `seed` (the site's layout puts the
    apps side by side, so the default base is the explorer next door)."""
    return f'{base}?{urlencode(seed.to_query())}'
