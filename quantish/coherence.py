"""Which-way coherence, stage by stage: the fringe visibility a
double-slit circuit would show if its two paths were merged right after
each stage.

A recorder that learns which path the screen particle took kills the
fringes; a quantum eraser does not destroy that record but moves it into
the recorder's sign, so fringes come back only per sign-sorted subset.
The quantity behind both stories is the overlap of the environment's
states on the two paths, and this module reads it off the engine's
all-points history.

At a stage, split the configuration-space points by the observed
particle's position (its path: left arm or right arm). On each path the
environment (every other particle) has a conditional amplitude vector
e_path over its coordinates. The circuit's tail — merge, sort, detect —
acts on the observed particle alone, so what it sees of the environment
is the inner product ⟨e_L|e_R⟩, and the screen's fringes have

    visibility = 2 |⟨e_L|e_R⟩| / (‖e_L‖² + ‖e_R‖²)

(the ratio's phase is the fringe shift; in this family it is 0 or π, so
the real part is a *signed* visibility, negative for fringes shifted by
half a period — the eraser's complementary subsets). Restricting the
environment coordinates to a sort subset (the recorder's sign, say)
gives that subset's visibility.

One subtlety: the observed particle's own sign is not part of the
environment. The split gate gives the two paths opposite-phase minus
components (½ and ±i/2 at 45°), and matching the observed particle's
sign across the paths would cancel them. The environment never depends
on that sign — control wires act by presence — so the conditional
vectors are read at one fixed reference sign of the observed particle.

Rows stop at the stage holding the phase plate (`upto_gate`): after the
merge the observed particle's two positions are the detector arms, not
the paths, and the question no longer applies. Delayed choice is what
makes the per-stage reading honest: a gate that acts on the environment
alone gives the same numbers wherever the model stages it, so a model
that wants the erasing step in this table stages its eraser before the
merge.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import sympy as sym

from quantish.sweep import group_label

REAL_TOL = 1e-9     # an imaginary part below this is display noise


@dataclass
class StageCoherence:
    step: int
    name: str                   # the declared stage name, else its gates joined
    gates: list[str]
    switched: list[str]         # particles that took a split component this step
    whole: complex | None       # None: the observed particle is not on two paths
    groups: dict[str, complex | None] = field(default_factory=dict)


def path_coherence(sim, observe: str, group_by: tuple[str, str] | None = None,
                   upto_gate: str | None = None) -> list[StageCoherence]:
    """The coherence per stage of a run simulation (see the module
    docstring). `observe` is the screen particle; `group_by` is the
    sort — (particle, 'sign' | 'position' | 'both'), labeled like the
    sweep's series ('+', '−', a gate name, '+E1'); `upto_gate` ends the
    rows at the stage holding that gate (the phase plate)."""
    if sim.all_points is None:
        raise ValueError('run the simulation first')
    layers = defaultdict(list)
    for pt in sim.all_points.index.values():
        if not pt.canceled:
            layers[pt.step].append(pt)
    display_strings = dict(sim.config.get('display_strings') or {})
    rows = []
    for step in sorted(layers):
        pts = layers[step]
        gates = list(sim.run_stages[step - 1]) if step > 0 else []
        name = 'initial' if step == 0 else _stage_name(sim, gates)
        switched = sorted({n for pt in pts for n, c in pt.particles.items()
                           if c is not None}) if step > 0 else []
        groups = {}
        if group_by is not None:
            particle, coordinate = group_by
            subsets = defaultdict(list)
            for pt in pts:
                subsets[group_label(pt.coords[particle], coordinate, display_strings)].append(pt)
            for label in sorted(subsets, key=lambda lab: (lab.lstrip('+−'), lab)):
                groups[label] = _coherence(subsets[label], observe)
            if coordinate == 'sign':
                for label in ('+', '−'):
                    groups.setdefault(label, None)
        rows.append(StageCoherence(step=step, name=name, gates=gates, switched=switched,
                                   whole=_coherence(pts, observe), groups=groups))
        if upto_gate is not None and upto_gate in gates:
            break
    return rows


def signed_visibility(z: complex | None) -> float | None:
    """The real part of a coherence — the signed visibility — or None
    when the coherence is undefined or carries a fringe shift that is
    not 0 or π (then |z| and its phase are the honest reading)."""
    if z is None or abs(z.imag) > REAL_TOL:
        return None
    return z.real


def _coherence(points, observe: str) -> complex | None:
    """2⟨e_L|e_R⟩ / (‖e_L‖² + ‖e_R‖²) over the points, or None unless the
    observed particle sits on exactly two positions."""
    by_path = defaultdict(list)
    for pt in points:
        by_path[str(pt.coords[observe].position)].append(pt)
    if len(by_path) != 2:
        return None
    # one reference sign for the observed particle, present on both paths
    signs = [{int(pt.coords[observe].sign) for pt in pts} for pts in by_path.values()]
    common = signs[0] & signs[1]
    if not common:
        return None
    ref = max(common)           # +1 when it is there
    vectors = []
    for pts in by_path.values():
        vec = defaultdict(complex)
        for pt in pts:
            if int(pt.coords[observe].sign) != ref:
                continue
            key = tuple((n, int(c.sign), str(c.position))
                        for n, c in pt.coords.items() if n != observe)
            vec[key] += _to_complex(pt.weight)
        vectors.append(vec)
    left, right = vectors
    inner = sum(left[k].conjugate() * right.get(k, 0j) for k in left)
    norm = (sum(abs(v) ** 2 for v in left.values())
            + sum(abs(v) ** 2 for v in right.values()))
    return 2 * inner / norm if norm > 0 else None


def _stage_name(sim, gates: list[str]) -> str:
    """The declared stage the gates belong to (a declared stage the
    engine splits over several steps names each of them; the gates tell
    them apart), else the gates joined."""
    members = set(gates)
    for name, declared in (sim.declared_run_stages or {}).items():
        if members and members <= set(declared):
            return name
    return ', '.join(gates)


def _to_complex(w) -> complex:
    x = getattr(w, 'v', w)
    try:
        return complex(x)
    except TypeError:
        return complex(sym.N(x))
