"""The quantish app's EPR / Bell section: the sweep-angle entries and
the report — the exact, analytical, and classical grids with their
verdicts, then one sampled grid per chosen interpretation. Engine in
`quantish.epr`.
"""
from __future__ import annotations

import math

import marimo as mo

import quantish.qnumber as qn
from quantish.apps.sampling import SAMPLER_NAMES
from quantish.display import md_table, sym_or_float
from quantish.epr import DEFAULT_VALUES, run_epr_experiment, verdict, verdict_slack

__all__ = ['epr_angle_entries', 'epr_report', 'parse_angle']


def epr_angle_entries(variables: dict) -> mo.ui.dictionary:
    """The sweep-angle entries, seeded from the model's qa/qb/qc
    variables (or the defaults 0, pi/8, pi/4). Same input forms as
    the gate-angle entries: a bare number in the selected units,
    anything else a symbolic radian expression. Bound by the caller."""
    vars_ = {str(k).lower(): str(v) for k, v in variables.items()}
    return mo.ui.dictionary({
        k: mo.ui.text(value=vars_.get(k, v), label=f'**{k}** =')
        for k, v in DEFAULT_VALUES.items()})


def parse_angle(raw: str, units: str, env: dict):
    """A sweep angle: a bare number is in `units`, kept as a spec string
    so Symbolic mode stays exact (22.5 → pi/8), never a float in
    radians; anything else a symbolic radian expression over the
    model's variables."""
    txt = (raw or '').strip().rstrip('º°').strip()
    try:
        float(txt)
        return qn.qify(txt if units == 'radians' else f'{txt}°')
    except ValueError:
        return qn.qify(txt, env)


def epr_report(sim_model, raw_angles: dict, n: int, modes, units: str, env: dict):
    """The EPR experiment at the entered angles: the exact laws first —
    quantish, analytical (one verdict: they agree), classical — then
    one sampled block per interpretation in the interpretations'
    fixed order, `n` trials per cell, each a grid and its verdicts.
    A markdown problem line when the angles are unparseable or not
    distinct."""
    try:
        values = {k: parse_angle(v, units, env) for k, v in raw_angles.items()}
    except Exception as exc:  # noqa: BLE001 — show, don't crash the app
        return mo.md(f'**unparseable sweep angle** — {exc}')
    if len({round(float(v) % math.pi, 9) for v in values.values()}) < 3:
        return mo.md('**sweep angles must be distinct (mod π)** — equal '
                     'angles make cells compare an angle with itself and '
                     'the inequalities degenerate')
    # one sweep per chosen interpretation (the exact, analytical and
    # classical grids are the same in each; the observed grid and its
    # verdict differ — that comparison is the demonstration)
    modes = list(modes) if n else []
    runs = {m: run_epr_experiment(sim_model, n_trials=n, seed=1, values=values, mode=m)
            for m in modes}
    # the exact grids come with any run; with no model ticked (or no
    # trials) one exact run supplies them
    res = runs[modes[0]] if modes else run_epr_experiment(sim_model, n_trials=0, values=values)
    labels = list(res['values'].keys())

    def grid_table(getter, grid, fmt='{:.4f}'):
        # exact rates show as such in Symbolic mode when short
        # (sin²(π/8) = 1/2 - √2/4); floats otherwise
        def cell(v):
            return sym_or_float(v, fmt.format(qn.to_float(v)))
        rows = [[f'**{l1}**'] + [cell(getter(grid[(l1, l2)])) for l2 in labels]
                for l1 in labels]
        return md_table([r'$\theta_1 \backslash \theta_2$'] + labels, rows)

    def verdicts(tag, r, bell_key, chsh_key, bell_slack, chsh_slack):
        # a sampled excess needs to clear sampling noise to count; the
        # words are epr.verdict's (VIOLATED / saturated / satisfied)
        def word(excess, slack):
            v = verdict(excess, slack)
            return f'**{v}**' if v == 'VIOLATED' else v
        bell, bell_at = r[bell_key]
        chsh, chsh_at = r[chsh_key]
        return (f'Bell excess ({tag}): **{bell:+.4f}** at {bell_at} — '
                f'{word(bell, bell_slack)}  \n'
                f'CHSH $|S|$ ({tag}): **{chsh:.4f}** at {chsh_at} — '
                f'{word(chsh - 2, chsh_slack)}')

    parts = ['sweep angles: ' + ', '.join(
        f'{k} = {math.degrees(float(v)):.1f}º' for k, v in values.items()),
             '**Exact quantish simulation** results',
             grid_table(lambda c: c['exact'], res['grid']),
             r'**Analytical law** $\sin^2(\theta_1-\theta_2)$',
             grid_table(lambda c: c['analytical'], res['grid']),
             verdicts('exact', res, 'bell_exact', 'chsh_exact', 1e-9, 1e-9),
             ('**Classical hidden-variable law** — the best a local '
              'model can do: it sits exactly on the bound'),
             grid_table(lambda c: c['classical'], res['grid']),
             verdicts('classical law', res, 'bell_classical', 'chsh_classical', 1e-9, 1e-9)]
    if modes:
        # a sampled excess must clear sampling noise (3σ) to count
        bell_slack, chsh_slack = verdict_slack(n)
        for m in [m for m in SAMPLER_NAMES if m in runs]:
            name = SAMPLER_NAMES[m]
            parts += [f'**{name[0].upper()}{name[1:]}** sampled results: {n:,} trials per cell',
                      grid_table(lambda c: c['sampled'], runs[m]['grid']),
                      verdicts('sampled', runs[m], 'bell', 'chsh', bell_slack, chsh_slack)]
    # .tight-paragraphs (css/quantish_app.css): headings, grids and
    # verdicts run as close as the section's prose
    return mo.Html('<div class="tight-paragraphs">' + mo.md('\n\n'.join(parts)).text + '</div>')
