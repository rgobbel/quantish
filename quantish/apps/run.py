"""The quantish app's model and run: the gate-angle state seeded from
a model, the slider and entry widgets tied to that state, and the
Simulation built from the model, the edited variables, the set angles,
and the switch-off boxes.

The angle state is one dict, {gate: {'deg': float, 'expr': str|None}}:
'expr' keeps a symbolic spec (the model's or a typed one) alongside
its degree equivalent, so the model's variables stay live in the
gate and a sweep can rebind them. The notebook holds it in one
`mo.state` and passes the getter and setter here.
"""
from __future__ import annotations

import math

import marimo as mo

import quantish.qnumber as qn
from quantish.apps.common import load_config, switched_off
from quantish.qnumber import CalcMode
from quantish.simulation import Simulation

__all__ = [
    'DEGREE_MARKS', 'angle_entries', 'angle_sliders', 'build_sim', 'centered',
    'gate_angle', 'model_angles', 'shown_angle', 'spec_expr', 'typed_angle',
]

DEGREE_MARKS = ('°', 'º', '˚')


def centered(deg: float) -> float:
    """An angle in (−180, 180]."""
    d = deg % 360.0
    return d - 360.0 if d > 180.0 else d


def spec_expr(spec) -> str | None:
    """A gate's angle spec as the expression worth carrying verbatim:
    only a genuinely symbolic string; numeric and degree-marked specs
    are represented by their degrees (which came through the
    Simulation, so angle_unit and degree marks are already applied)."""
    if not isinstance(spec, str):
        return None
    s = spec.strip()
    if s and s[-1] in DEGREE_MARKS:
        return None
    try:
        float(s)
        return None
    except ValueError:
        return s


def model_angles(model_path, model_vars: dict) -> dict:
    """The angle state's seed from a model and the edited variables:
    {'gates': the Fredkin gates in run order, 'angles': {gate: {'deg',
    'expr'}} (degrees centered and rounded to the half degree),
    'env': the model's variables (typed expressions use them by name),
    'problem': why the variables were rejected, or None, 'particles',
    'plates': the phase plates in run order — the switch-off row}."""
    config = load_config(model_path)[0]
    config.variables.update(model_vars)
    problem = None
    try:
        base_sim = Simulation(config)
    except Exception as exc:  # noqa: BLE001 — bad variable definitions
        problem = f'variables rejected — {exc}'
        base_sim = Simulation(load_config(model_path)[0])
    return {
        'gates': [g for g in base_sim.run_order if g in base_sim.fredkin_gates],
        'angles': {g: {'deg': round(centered(float(gate.theta.degrees)) * 2) / 2,
                       'expr': spec_expr(config.gates[g].angle)}
                   for g, gate in base_sim.fredkin_gates.items()},
        'env': dict(base_sim.qvars),
        'problem': problem,
        'particles': list(base_sim.particles),
        'plates': [g for g in base_sim.run_order if g in base_sim.phase_plates],
    }


def gate_angle(cur: dict, mode: str, env: dict):
    """One gate's angle spec for the loader from its state entry. A
    symbolic expression stays a STRING: the loader qifies it against
    the model's variables, so names like theta1 stay live and a sweep's
    variable rebinding still has something to rebind (qifying here
    would freeze the current value into the gate). Otherwise degrees:
    a degree-marked spec in Symbolic mode, exact (30.0° → pi/6), a
    float in radians in Float mode."""
    if cur['expr']:
        qn.qify(cur['expr'], env)  # validate early, clear error
        return cur['expr']
    if mode == 'Symbolic':
        return f"{cur['deg']}°"
    return math.radians(cur['deg'])


def build_sim(model_path, model_vars: dict, mode: str, angles: dict,
              off_values: dict, env: dict) -> Simulation:
    """The Simulation as the app has it set: the model over the
    defaults, the edited variables, every gate at its state's angle,
    the switched-off gates inert and the switched-off particles
    absent. Sets the calculation mode. Construction is cheap and
    needs no run."""
    CalcMode.default(mode)
    config = load_config(model_path)[0]
    config.variables.update(model_vars)
    for g, cur in angles.items():
        config.gates[g].angle = gate_angle(cur, mode, env)
    inert, absent = switched_off(off_values)
    return Simulation(config, inert=inert, absent=absent)


def angle_sliders(angles_get, angles_set, gate_names, off_values: dict) -> mo.ui.dictionary:
    """A slider per gate at the state's degrees (0–180 shown), a move
    setting the state to that number and clearing any expression; a
    switched-off gate's slider is disabled. The caller binds the
    dictionary to a global, in a cell of its own: marimo never reruns
    the cell that invoked a state setter, so the sliders and the
    entries must live in separate cells."""
    def slider_cb(g):
        def cb(v):
            angles_set({**angles_get(), g: {'deg': float(v), 'expr': None}})
        return cb

    return mo.ui.dictionary({
        g: mo.ui.slider(
            -180, 180, step=0.5,
            value=max(0.0, min(180.0, round(angles_get()[g]['deg'] * 2) / 2)),
            show_value=True, full_width=True,
            disabled=not off_values.get(f'g:{g}', True),
            on_change=slider_cb(g))
        for g in gate_names})


def typed_angle(raw: str, units: str, env: dict) -> tuple[float, str | None] | None:
    """A typed angle as (degrees, the expression to keep or None), or
    None to keep the previous value: empty, or unparseable. A bare
    number is in `units` unless it carries a degree mark, which IS the
    unit; anything else is a symbolic radian expression, which may use
    the model's variables."""
    txt = (raw or '').strip()
    marked = txt.endswith(DEGREE_MARKS)
    txt = txt.rstrip(''.join(DEGREE_MARKS)).strip()
    if not txt:
        return None
    try:
        num = float(txt)
        return (num if marked or units == 'degrees' else math.degrees(num)), None
    except ValueError:
        pass
    try:
        rad = float(qn.qify(txt, env))
        return math.degrees(rad), txt
    except Exception:  # noqa: BLE001 — unparseable: keep the previous value
        return None


def shown_angle(cur: dict, mode: str, units: str) -> str:
    """The entry's text for a state entry, following the math mode:
    Symbolic shows the model's own symbolic spec while it is untouched
    (a slider or typed number clears it) and the simplest exact form
    of the set angle otherwise; Float shows a number in `units`."""
    if mode == 'Symbolic':
        if cur['expr']:
            return cur['expr']
        return qn.angle_expr(cur['deg'])
    if units == 'degrees':
        return f"{cur['deg']:.1f}º"
    return f"{math.radians(cur['deg']):.4f}"


def angle_entries(angles_get, angles_set, gate_names, off_values: dict,
                  mode: str, units: str, env: dict) -> mo.ui.dictionary:
    """A text entry per gate showing the state's angle (shown_angle),
    an edit setting the state (typed_angle); a switched-off gate's
    entry is disabled. Bound by the caller, in its own cell (see
    angle_sliders)."""
    def text_cb(g):
        def cb(raw):
            parsed = typed_angle(raw, units, env)
            if parsed is not None:
                deg, expr = parsed
                angles_set({**angles_get(), g: {'deg': deg, 'expr': expr}})
        return cb

    return mo.ui.dictionary({
        g: mo.ui.text(value=shown_angle(angles_get()[g], mode, units),
                      on_change=text_cb(g),
                      disabled=not off_values.get(f'g:{g}', True))
        for g in gate_names})
