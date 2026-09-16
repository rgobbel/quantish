"""The quantish app's Monte Carlo sampling: the interpretations on
offer, the runtime projection from a calibration on the loaded
circuit, a sampling job — a plain dict a background thread (or, under
WASM, a synchronous loop) fills chunk by chunk — and its progress
and results views.
"""
from __future__ import annotations

import asyncio
import random
import threading
import time
from collections import Counter
from copy import deepcopy
from html import escape

import marimo as mo

from quantish.display import html_table, particle_names, particle_tokens
from quantish.epr import sample_hidden_variable
from quantish.montecarlo import (
    pilot_transitions,
    predicted_distribution,
    sample_pilot,
    sample_terminal,
)
from quantish.simulation import Simulation

__all__ = [
    'CHUNK', 'EPR_SAMPLER_LABELS', 'LONG_RUN_SECONDS', 'SAMPLER_LABELS',
    'SAMPLER_NAMES', 'new_job', 'picked_modes', 'progress_view',
    'projection', 'results_view', 'run_job', 'run_job_async', 'sampling_explanation',
    'sampling_seconds', 'trial_count',
]

# The sampling interpretations, labeled by what each assumes (see the
# explanation); the value is the engine's mode name. The EPR sweep also
# offers Bell's local hidden-variable example, which samples no wave: a
# shared hidden angle and two independent detector readings
# (epr.sample_hidden_variable)
SAMPLER_LABELS = {'terminal (Everett)': 'terminal',
                  'pilot wave (Bohm, nonlocal)': 'pilot'}
EPR_SAMPLER_LABELS = {**SAMPLER_LABELS,
                      "local hidden variable (Bell's example)": 'hidden'}
SAMPLER_NAMES = {v: k for k, v in EPR_SAMPLER_LABELS.items()}
SAMPLER_NOTES = {
    'terminal': 'Everett — one draw from the final superposition per trial',
    'pilot': 'Bohm — one wave-guided trajectory per trial, nonlocal'}
LONG_RUN_SECONDS = 30
CHUNK = 2000            # draws per chunk: the grain of progress and Cancel

EXPLANATION = r"""
The engine always computes the whole wave: every final
configuration-space point with its exact weight. Sampling asks what
a **single run** of the experiment looks like. Each trial makes one
random draw, whose rule is the interpretation; tallying many trials
gives observed frequencies that converge on the exact probabilities
as the trial count grows, with a spread of about $1/\sqrt{n}$ from
the finite count — the *sampling noise*. Two interpretations of the
same wave are offered here:

- **Terminal (Everett).** *One trial:* one final configuration-space
  point is drawn from the evolved superposition, with probability
  $\lvert w\rvert^2$ — "which branch am I in". Converges to the
  exact probabilities. The faithful simulation of a real experiment:
  interference stays intact until the observation at the end.
- **Pilot wave (Bohm, nonlocal).** *One trial:* one actual
  configuration starts at the initial configuration-space point
  and advances one stage at a time. At each stage its next point
  is drawn from transition probabilities fitted to the wave, so
  that over many trials the configurations are distributed as
  $\lvert w\rvert^2$ at every stage. Converges to the exact
  probabilities, the same as terminal. The difference is that a
  single trial has one definite configuration at every stage, and
  the transition probabilities at each stage depend on the whole
  wave — both branches — which is the model's nonlocality.
  (Discrete pilot-wave dynamics are not unique; this is the
  maximum-entropy coupling on the graph's edges, in the stochastic
  form of Bell 1984 / Vink 1993.)

A third model, Bell's local hidden-variable example, samples no
wave at all; it belongs to the EPR section below, where the
comparison is the point.
"""


def sampling_explanation() -> mo.Html:
    """The section's explanation; .tight-list (css/quantish_app.css):
    the list follows its lead-in."""
    return mo.Html('<div class="tight-list">' + mo.md(EXPLANATION).text + '</div>')


def picked_modes(boxes, labels: dict) -> list[str]:
    """The mode names whose checkboxes are ticked, in the labels'
    order — the order the results are shown in."""
    return [labels[k] for k, v in boxes.value.items() if v]


def trial_count(text: str, slider_value) -> int:
    """The trials to run: the text entry when it parses — 1000000,
    1_000_000, 1,000,000, or 1e6 — else the slider."""
    try:
        return max(1, int(float((text or '').strip().replace(',', '').replace('_', ''))))
    except ValueError:
        return int(slider_value)


_calibration: dict = {}


def sampling_seconds(model_sim, modes, n_trials: int, cells: int = 1) -> float:
    """A projection of how long a sampling job will take, from a
    calibration on this circuit: a few hundred trials of each
    interpretation are timed once per loaded model (and one run of
    the circuit, for a sweep's per-cell rebuild), then scaled to
    n_trials × cells. Measured where it will run, so the browser
    build's slower Python is accounted for."""
    key = id(model_sim)
    if key not in _calibration:
        t0 = time.perf_counter()
        cfg = deepcopy(model_sim.config)
        cfg['loglevel'] = 'warning'
        probe = Simulation(cfg)
        probe.run()
        run_cost = time.perf_counter() - t0
        rng, k, per_trial = random.Random(0), 300, {}
        t0 = time.perf_counter()
        sample_terminal(probe.result_space, k, rng)
        per_trial['terminal'] = (time.perf_counter() - t0) / k
        t0 = time.perf_counter()
        guidance = pilot_transitions(probe.initial_points)
        fit_cost = time.perf_counter() - t0
        t0 = time.perf_counter()
        sample_pilot(probe.initial_points, k, rng, transitions=guidance)
        per_trial['pilot'] = (time.perf_counter() - t0) / k
        t0 = time.perf_counter()
        sample_hidden_variable(0.0, 1.0, k, rng)
        per_trial['hidden'] = (time.perf_counter() - t0) / k
        _calibration[key] = (run_cost, fit_cost, per_trial)
    run_cost, fit_cost, per_trial = _calibration[key]
    secs = (run_cost if cells > 1 else 0.0) * cells
    for m in modes:
        secs += cells * (n_trials * per_trial[m] + (fit_cost if m == 'pilot' else 0.0))
    return secs


def projection(secs: float, n_trials: int | None = None) -> mo.Html:
    """The predicted-runtime line: italic, and red bold past
    LONG_RUN_SECONDS so a long wait is announced before the Run
    button is pressed; with `n_trials`, the count the job will
    actually run, so a custom entry that did not parse (the slider
    stands in) is visible. (Html rather than markdown: marimo's
    markdown strips inline styles; explicit colors, since bare Html
    output would inherit marimo's muted gray.)"""
    if secs < 1:
        text = 'under a second'
    elif secs < 90:
        text = f'about {secs:.0f} s'
    else:
        text = f'about {secs / 60:.1f} min'
    if n_trials is not None:
        text += f' for {n_trials:,} trials'
    style = ('color: #ff1f1f; font-weight: 700' if secs > LONG_RUN_SECONDS
             else 'color: #000')
    return mo.Html(f'<em style="{style}">Predicted runtime: {text}</em>')


def new_job(sim, n_trials: int, modes) -> dict:
    """A sampling job, the plain dict run_job fills: the worker and
    the display share it, the display re-rendering on the tick counter
    the worker bumps."""
    return {'cancel': threading.Event(), 'done': False,
            'progress': 0, 'total': n_trials * len(modes),
            'n_trials': n_trials, 'modes': list(modes), 'sim': sim,
            'results': None, 'n_done': {}, 'error': None}


def _steps(job: dict, seed: int):
    """Run a job chunk by chunk, yielding each chunk's size — the grain
    of progress and Cancel — and leaving the tallies (each
    interpretation's, the predicted distribution beside them), or the
    error, in the job at the end."""
    sim, n = job['sim'], job['n_trials']
    try:
        rng = random.Random(seed)
        res = {'predicted': predicted_distribution(sim.result_space)}
        done = 0
        for m in job['modes']:
            tally = Counter()
            remaining = n
            # the pilot wave's guidance is fitted once per job
            guidance = pilot_transitions(sim.initial_points) if m == 'pilot' else None
            while remaining and not job['cancel'].is_set():
                k = min(CHUNK, remaining)
                if m == 'terminal':
                    tally += sample_terminal(sim.result_space, k, rng)
                else:
                    tally += sample_pilot(sim.initial_points, k, rng, transitions=guidance)
                remaining -= k
                done += k
                job['progress'] = done
                yield k
            res[m] = tally
            job['n_done'][m] = n - remaining
        job['results'] = res
    except Exception as exc:  # noqa: BLE001 — surface in the display
        job['error'] = repr(exc)
    finally:
        job['done'] = True


def run_job(job: dict, seed: int, bump, tick=None) -> None:
    """Run a job to completion or cancellation in a background thread.
    `bump` is the tick counter's setter, called every quarter second
    and at the end (the thread's way to re-render the display); with
    `tick` (a progress bar's update) each chunk reports there instead
    and the display renders once, at the end."""
    last_bump = 0.0
    for k in _steps(job, seed):
        if tick is not None:
            tick(k)
        elif time.monotonic() - last_bump > 0.25:
            last_bump = time.monotonic()
            bump(lambda v: v + 1)
    if tick is None:
        bump(lambda v: v + 1)  # final render, full results


async def run_job_async(job: dict, seed: int, bump) -> None:
    """The same run for the WASM build, where a thread is a coroutine on
    the page's event loop (mo.Thread awaits what its target returns):
    yielding after every chunk lets the page render the progress and
    deliver a Cancel press between chunks."""
    last_bump = 0.0
    for _ in _steps(job, seed):
        if time.monotonic() - last_bump > 0.25:
            last_bump = time.monotonic()
            bump(lambda v: v + 1)
        await asyncio.sleep(0)
    bump(lambda v: v + 1)


def progress_view(job: dict, cancel_button):
    """A running job: its bar, the count, and the Cancel button."""
    pct = 100 * job['progress'] / max(1, job['total'])
    return mo.hstack([
        mo.Html(f'<progress value="{job["progress"]}" max="{job["total"]}" '
                'style="width: 24em; max-width: 100%"></progress>'),
        mo.md(f'{pct:.0f}% — {job["progress"]:,} of {job["total"]:,} draws'),
        cancel_button,
    ], justify='start', gap=1, align='center', wrap=True)


def results_view(job: dict):
    """A finished (or canceled) job's tallies, one table per
    interpretation: the configuration-space points by predicted
    probability, count, observed and analytical frequency, and the
    total variation distance between the two."""
    if job['error'] is not None:
        return mo.md(f'**Monte Carlo failed** — `{job["error"]}`')
    results, sim = job['results'], job['sim']
    pred = results['predicted']
    # compact row labels: one abbreviated position per particle, the
    # form the final-points table uses, looked up from the terminal
    # points (raw keys are unreadably long for multi-particle models)
    pnames = particle_names(sim)
    tokens = {p.key: [tok for _, tok in particle_tokens(sim, p)]
              for p in sim.result_space.index.values()}
    sections = []
    if job['cancel'].is_set():
        sections.append('_canceled — partial tallies below_')
    for label, note in SAMPLER_NOTES.items():
        n_done = job['n_done'].get(label, 0)
        if label not in results or not n_done:
            continue
        tally = results[label]
        rows, tvd = [], 0.0
        for key in sorted(set(tally) | set(pred), key=lambda k: -pred.get(k, 0)):
            freq = tally.get(key, 0) / n_done
            tvd += abs(freq - pred.get(key, 0.0))
            bare = key.split(':')[0]
            toks = tokens.get(bare, [bare[:60].replace('|', ' ')] + [''] * (len(pnames) - 1))
            rows.append([f'<code>{escape(t)}</code>' for t in toks]
                        + [str(tally.get(key, 0)), f'{freq:.4f}', f'{pred.get(key, 0.0):.4f}'])
        # an HTML table (markdown tables cannot span columns): the
        # particle columns share the 'point' heading, the two
        # frequency columns share theirs
        table = html_table([('configuration-space point', pnames), ('count', None),
                            ('frequencies', ['observed', 'analytical'])], rows)
        sections.append(f'**{label}** — {note}; {n_done:,} trials, '
                        f'total variation distance {tvd / 2:.4f}\n\n' + table)
    return mo.md('\n\n'.join(sections))
