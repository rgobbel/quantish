"""Presentation helpers over a finished Simulation.

Everything here formats or orders results for humans: the Mermaid
diagram's port value blocks, the notebook's gate-traffic table, and the
canonical display ordering the notebook and the network graph share.
Each function takes the Simulation as its first argument; nothing in
this module affects a run.
"""
import cmath
import logging
import math
from collections import defaultdict

import quantish.qnumber as qn
from quantish.config_space import GatePort
from quantish.util import SEP

log = logging.getLogger('quantish')

# display ordering of a gate's ports: the switch wires the book's
# figures read top-down, then the pass-through control
PORT_DISPLAY_ORDER = {'upper': 0, 'lower': 1, 'control': 2}


def coord_sort_key(sim, coord):
    """Canonical display order for one particle coordinate: gate (in
    logical evaluation order), then port (upper, lower, control), then
    particle name, then sign (+ before −). Yields e.g.
    p3+@g4.upper, p3+@g4.lower, p1+@g7.upper, p1-@g7.upper, ..."""
    where = coord.position.origin or coord.position.endpoint
    gate = where.gate if where is not None else None
    port = where.port if where is not None else None
    return (sim.gate_step.get(gate, len(sim.run_stages) + 1),
            sim.run_order.index(gate) if gate in sim.run_order
            else len(sim.run_order),
            PORT_DISPLAY_ORDER.get(port, len(PORT_DISPLAY_ORDER)),
            coord.name,
            -int(coord.sign))


def cs_point_sort_key(sim, point):
    """Canonical display order for a whole configuration-space point: compare configuration-space points by
    their coordinates taken in coord_sort_key order, so rows group by
    gate, then port (upper first), then sign (+ first)."""
    return tuple(sorted(coord_sort_key(sim, c) for c in point.coords.values()))


def port_summary(sim, step, port, end='origin'):
    """Formatted per-particle summary of the amplitudes at `port` over
    the configuration-space points at `step`, one line per particle:

        p1+: 0.56, p1-: 0.19 | Σ: 0.75 ∠+30º

    The per-sign values are marginal probabilities (Σ|w|²). Σ is the
    aggregate: the two signed component amplitudes summed as complex
    numbers, shown as squared magnitude and phase — the port's
    wire-weight view. end='origin' summarizes what exited the port,
    end='endpoint' what is arriving at it. None when nothing matches
    (or symbolic weights with free symbols)."""
    if sim.all_points is None:
        return None
    probs = defaultdict(lambda: defaultdict(float))   # pname -> sign -> Σ|w|²
    amps = defaultdict(complex)                       # pname -> Σ of configuration-space point weights
    try:
        for point in sim.all_points.index.values():
            if point.step != step or point.cancelled:
                continue
            for pname, coord in point.coords.items():
                where = (coord.position.origin if end == 'origin'
                         else coord.position.endpoint)
                if where == port:
                    probs[pname][str(coord.sign)] += float(point.probability)
                    amps[pname] += complex(point.weight)
    except (TypeError, ValueError):
        return None  # symbolic weights with free symbols
    if not probs:
        return None
    lines = []
    for pname in sorted(probs.keys()):
        sign_parts = ', '.join(
            f'{pname}{sign}: {prob:.{sim.precision}f}'
            for sign, prob in sorted(probs[pname].items(), reverse=True))
        agg = amps[pname]
        phase_deg = math.degrees(cmath.phase(agg)) if abs(agg) > 1e-12 else 0.0
        lines.append(f'{sign_parts}\nΣ: {abs(agg) ** 2:.{sim.precision}f} '
                     f'∠{phase_deg:+.0f}º')
    return '\n'.join(lines)


def gate_io(sim):
    """Per-step gate traffic: a list of rows {step, gate, port, input,
    output} for every gate port that saw a particle — inputs are what
    was arriving at the port in the previous step's configuration-space points (coordinate
    endpoints), outputs what exited it when the gate fired (coordinate
    origins), both in port_summary format."""
    rows = []
    if sim.all_points is None:
        return rows
    for i, stage in enumerate(sim.run_stages):
        step = i + 1
        for gname in stage:
            for wire in ('control', 'upper', 'lower'):
                port = GatePort(gname, wire)
                arriving = port_summary(sim, step - 1, port, end='endpoint')
                leaving = port_summary(sim, step, port, end='origin')
                if arriving is None and leaving is None:
                    continue
                rows.append({'step': step, 'gate': gname, 'port': wire,
                             'input': arriving or '—',
                             'output': leaving or '—'})
    return rows


def port_particle_amps(sim, step, port, end='origin'):
    """Per-particle summed amplitude (qnumber Complex) at `port` over
    the configuration-space points at `step`. end='origin' sums what exited the
    port, end='endpoint' what is arriving at it. Empty dict when
    nothing matches."""
    amps = {}
    if sim.all_points is None:
        return amps
    for point in sim.all_points.index.values():
        if point.step != step or point.cancelled:
            continue
        for pname, coord in point.coords.items():
            where = (coord.position.origin if end == 'origin'
                     else coord.position.endpoint)
            if where == port:
                amps[pname] = (amps[pname] + point.weight
                               if pname in amps else point.weight)
    return amps


def amp_value_str(sim, pname, amp):
    """Display block for one particle's summed amplitude at a port:

        p1 +0.75,+0.43i
        Pr: 0.75 (0.56+0.19) ∠+30º

    Line 1: the amplitude as a signed (real, imaginary) pair, the
    imaginary part suffixed i. Line 2: the combined probability, its
    decomposition into real- and imaginary-part contributions, and
    the phase in degrees. (In this circuit family the real part is
    the plus-sign component and the imaginary part the minus-sign
    component.)"""
    prec = sim.precision
    re_v = qn.to_float(amp.real)
    im_v = qn.to_float(amp.imag)
    pr = qn.to_float(qn.probability(amp))
    pr_re = qn.to_float(qn.probability(amp.real))
    pr_im = qn.to_float(qn.probability(amp.imag))
    deg = qn.to_float(amp.phase.degrees)
    return (f'{pname} {re_v:+.{prec}f},{im_v:+.{prec}f}i\n'
            f'Pr: {pr:.{prec}f} ({pr_re:.{prec}f}+{pr_im:.{prec}f}) ∠{deg:+.0f}º')


def pos_value_str(sim, pos):
    """Display string for a gate output port after a run: one
    amp_value_str block per particle present. Returns None when
    nothing exited there."""
    parts = pos.split(SEP)
    if len(parts) != 2:
        return None
    gname, gport = parts
    step = sim.gate_step.get(gname)
    if step is None:
        return None
    amps = port_particle_amps(sim, step, GatePort(gname, gport))
    if not amps:
        return None
    return '\n'.join(amp_value_str(sim, p, amps[p]) for p in sorted(amps))
