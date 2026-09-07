"""Model-declared sweeps: rerun a circuit across a range of one of its
variables and record the probability that a particle ends at a gate,
optionally split by another particle's final coordinate.

Some circuits only tell their story across a range: the double slit's
fringes are the pixel phase φ swept over a period, and the quantum
eraser's complementary fringes appear only when the result is sorted
by the recorder particle's sign as well. A model declares its sweep in
a `sweep` section (see models/schema.yaml):

    sweep:
      title: screen intensity, sorted by the eraser's outcome
      variable: phi              # a name from `variables`
      from: 0                    # default 0
      to: 2*pi
      points: 41                 # default 41
      observe: {particle: p1, at: S}
      group_by: {particle: p2, coordinate: sign}   # optional

Each point rebinds the variable and runs the circuit — the model's own
gate expressions say how the variable enters, so the model stays the
single source of truth (the run_pair convention in epr.py). The swept
values are exact fractions of the range in Symbolic mode (0..2π in 40
steps is k·π/20), floats in Float mode; the recorded probabilities are
qnumber values either way, converted only for display.
"""
import logging
from copy import deepcopy

from quantish.qnumber import qify

log = logging.getLogger('quantish')

DEFAULT_POINTS = 41
COORDINATES = ('sign', 'position', 'both')
SIGN_MARKS = {1: '+', -1: '−'}


def sweep_spec(sim) -> dict | None:
    """The model's sweep declaration with defaults filled in, validated
    against the loaded model; None when the model declares none."""
    raw = sim.config.get('sweep')
    if not raw:
        return None
    spec = {k: v for k, v in dict(raw).items()}
    var = spec.get('variable')
    if var not in sim.qvars:
        raise ValueError(f"sweep variable '{var}' is not one of the model's "
                         f"variables ({', '.join(sim.qvars) or 'none'})")
    spec.setdefault('from', 0)
    spec.setdefault('points', DEFAULT_POINTS)
    obs = dict(spec.get('observe') or {})
    if obs.get('particle') not in sim.particles:
        raise ValueError(f"sweep observes particle '{obs.get('particle')}', "
                         f"which the model does not declare")
    if obs.get('at') not in sim.gates:
        raise ValueError(f"sweep observes arrival at '{obs.get('at')}', "
                         f"which is not a gate of the model")
    spec['observe'] = obs
    grp = spec.get('group_by')
    if grp:
        grp = dict(grp)
        if grp.get('particle') not in sim.particles:
            raise ValueError(f"sweep groups by particle '{grp.get('particle')}'"
                             f", which the model does not declare")
        grp.setdefault('coordinate', 'sign')
        if grp['coordinate'] not in COORDINATES:
            raise ValueError(f"sweep group_by coordinate must be one of "
                             f"{COORDINATES}, not '{grp['coordinate']}'")
        spec['group_by'] = grp
    return spec


def sweep_values(spec: dict, points: int | None = None) -> list:
    """The swept variable's values, `points` of them from `from` to `to`
    inclusive: lo + (hi − lo)·k/(n−1), the fraction qified as a spec
    string so Symbolic mode keeps it a Rational."""
    n = int(points or spec['points'])
    if n < 2:
        raise ValueError('a sweep needs at least 2 points')
    lo, hi = qify(spec['from']), qify(spec['to'])
    span = hi - lo
    return [lo + span * qify(f'{k}/{n - 1}') for k in range(n)]


def group_label(coord, coordinate: str, display_strings=None) -> str:
    """The label of a particle's final coordinate: its sign ('+'/'−'),
    the gate it ended at, or both ('+E1')."""
    if coordinate == 'sign':
        return SIGN_MARKS[int(coord.sign)]
    origin = coord.position.origin
    gate = origin.gate if origin is not None else '?'
    gate = (display_strings or {}).get(gate, gate)
    if coordinate == 'position':
        return gate
    return f'{SIGN_MARKS[int(coord.sign)]}{gate}'


def run_sweep(sim, spec: dict | None = None, values=None) -> dict:
    """Run the sweep: {'spec', 'x': the swept values, 'series': {label:
    probabilities aligned with x}, 'total': their sum per x}. Without a
    group_by there is a single series named for the observed arrival.
    Probabilities are qnumber values (exact in Symbolic mode)."""
    from quantish.simulation import Simulation
    spec = spec if spec is not None else sweep_spec(sim)
    if spec is None:
        raise ValueError('the model declares no sweep')
    values = list(values if values is not None else sweep_values(spec))
    obs, grp = spec['observe'], spec.get('group_by')
    display_strings = dict(sim.config.get('display_strings') or {})
    zero = qify(0)
    series: dict[str, list] = {}
    total = [zero] * len(values)
    saved_level = log.level
    log.setLevel(logging.WARNING)   # each run re-logs the whole setup
    try:
        for i, x in enumerate(values):
            cfg = deepcopy(sim.config)
            cfg.variables[spec['variable']] = x
            space, _ = Simulation(cfg).run()
            for point in space.index.values():
                origin = point.coords[obs['particle']].position.origin
                if origin is None or origin.gate != obs['at']:
                    continue
                label = (group_label(point.coords[grp['particle']],
                                     grp['coordinate'], display_strings)
                         if grp else obs['at'])
                if label not in series:
                    series[label] = [zero] * len(values)
                series[label][i] = series[label][i] + point.probability
                total[i] = total[i] + point.probability
    finally:
        log.setLevel(saved_level)
    order = sorted(series, key=lambda lab: (lab.lstrip('+−'), lab))
    return {'spec': spec, 'x': values,
            'series': {lab: series[lab] for lab in order}, 'total': total}


def log_sweep(result: dict, csv_path: str | None = None) -> None:
    """Log the sweep as a table (values as floats), optionally writing
    it as CSV too."""
    import csv

    from quantish.qnumber import to_float
    spec = result['spec']
    labels = list(result['series'])
    headers = [spec['variable'], *labels] + (['total'] if spec.get('group_by')
                                             else [])
    rows = []
    for i, x in enumerate(result['x']):
        row = [to_float(x)] + [to_float(result['series'][lab][i])
                               for lab in labels]
        if spec.get('group_by'):
            row.append(to_float(result['total'][i]))
        rows.append(row)
    log.info(' ')
    title = spec.get('title') or (f"P({spec['observe']['particle']} at "
                                  f"{spec['observe']['at']})")
    log.info(f'SWEEP: {title} — {spec["variable"]} over {len(rows)} points')
    widths = [max(len(h), 9) for h in headers]
    log.info('   ' + '  '.join(h.rjust(w) for h, w in zip(headers, widths)))
    for row in rows:
        log.info('   ' + '  '.join(f'{v:{w}.4f}' for v, w in zip(row, widths)))
    if csv_path:
        with open(csv_path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(rows)
        log.info(f'sweep written to {csv_path}')
