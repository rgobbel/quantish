"""The quantish app's Detailed Results: the tables over a finished
run — the weight-evolution table (the graph's tabular twin), the
final configuration-space points, the marginal probabilities, and the
gate traffic by step — each in its own accordion under one outer one,
so a reader can open the section and then just the tables they care
about.
"""
from __future__ import annotations

import marimo as mo

import quantish.qnumber as qn
from quantish.apps.common import md_cell
from quantish.config_space import GatePort
from quantish.display import (
    coord_sort_key,
    cs_point_sort_key,
    gate_io,
    html_table,
    math_prob,
    math_weight,
    md_table,
    particle_names,
    particle_tokens,
    phase_deg,
)

__all__ = ['detailed_results', 'evolution_table', 'final_points', 'gate_io_table', 'marginals']


def evolution_table(sim):
    # Tabular twin of the weight-evolution graph: per stage, one row per
    # parent→child branch — the input configuration-space point and its weight, the
    # per-particle components the gate applied (cos²θ, ±i·sinθcosθ, sin²θ),
    # the branch amplitude, and the output configuration-space point's total weight. Where
    # branch w ≠ point w, interfering branches merged into that configuration-space point.
    pnames = particle_names(sim)

    def label(p):
        # one cell per particle (particle-name order), each the
        # abbreviated position; the header names the particle
        return [f'`{tok}`' for _, tok in particle_tokens(sim, p)]

    # the product sign, in a math serif so it doesn't read as a
    # gateway glyph, with the explanation on hover
    _prod = ('<span title="the product of this branch&#39;s '
             'per-particle components, shown as one multiplier: a '
             'merged configuration-space point stores only its '
             'first branch&#39;s per-particle components" '
             'style="font-family: STIXTwoMath, STIXGeneral, '
             '\'Cambria Math\', \'Times New Roman\', serif">'
             '∏</span>')

    def particle_cell(w, parent, contrib):
        # A merged configuration-space point stores only its FIRST branch's per-particle
        # components; for other branches show just the branch's overall
        # multiplier ∏ (recovered as branch w / input w).
        facts = {name: f for name, f in w.particles.items() if f is not None}
        try:
            expected = complex(parent.weight)
            for f in facts.values():
                expected *= complex(f)
            stored_ok = abs(expected - complex(contrib)) < 1e-9
        except (TypeError, ValueError):
            stored_ok = True  # symbolic with free symbols: trust the stored components
        if stored_ok:
            return '<br>'.join(f'{name}: {math_weight(f)}'
                               for name, f in facts.items()) or '—'
        try:
            return (f'{_prod}: '
                    f'{math_weight(complex(contrib) / complex(parent.weight))}')
        except (TypeError, ValueError, ZeroDivisionError):
            return f'{_prod}: ?'

    def controlled_gates(cs_point, stage):
        # per-configuration-space point positional check, as in the engine
        return [g for g in stage
                if any(c.position.endpoint == GatePort(g, 'control')
                       for c in cs_point.coords.values())]

    def control_header(stage, parents):
        # per-gate control occupancy: source port and merged Pr, the
        # same summary the debug log's CONTROL suffix shows
        parts = []
        for g in stage:
            amp, source = None, None
            for w in parents:
                for c in w.coords.values():
                    if c.position.endpoint == GatePort(g, 'control'):
                        amp = w.weight if amp is None else amp + w.weight
                        source = c.position.origin or c.name
            if amp is not None:
                pr = qn.to_float(qn.probability(amp))
                parts.append(f'`{source}` → {g}, Pr {pr:.2f}')
        return 'control: ' + (', '.join(parts) if parts else '∅')

    by_step = {}
    for pt in sim.all_points.index.values():
        by_step.setdefault(pt.step, []).append(pt)
    sections = {}
    for step in sorted(by_step):
        points = sorted(by_step[step], key=lambda p: cs_point_sort_key(sim, p))
        if step == 0:
            sections['Step 0 — initial configuration-space point'] = mo.md(html_table(
                [('configuration-space point', pnames), ('weight $w$', None)],
                [label(w) + [math_weight(w.weight)] for w in points], md_cell))
            continue
        stage = sim.run_stages[step - 1]
        parents = by_step.get(step - 1, [])
        rows = []
        n = len(pnames)
        for w in points:
            out_label = label(w)
            if w.canceled:
                out_label = out_label[:-1] + [out_label[-1] + ' _(canceled)_']
            branches = sorted(w.contributions.items(),
                              key=lambda kv: cs_point_sort_key(sim, kv[0]))
            if len(branches) == 1:
                parent, contrib = branches[0]
                rows.append(label(parent) + [
                             ', '.join(controlled_gates(parent, stage)) or '∅',
                             math_weight(parent.weight),
                             particle_cell(w, parent, contrib),
                             math_weight(contrib)] + out_label + [
                             math_weight(w.weight)])
                continue
            # a merged output: its weight belongs to the SUM of the
            # branches, not to each branch — blank the output columns
            # on branch rows and close the group with a merged row
            # showing the addition
            for parent, contrib in branches:
                rows.append(label(parent) + [
                             ', '.join(controlled_gates(parent, stage)) or '∅',
                             math_weight(parent.weight),
                             particle_cell(w, parent, contrib),
                             math_weight(contrib), ('', n), ''])
            rows.append([('**merged**', n), '', '', '',
                         ' '.join(math_weight(c) for _, c in branches)]
                        + out_label + [math_weight(w.weight)])
        total = qn.to_float(sum(w.probability for w in points
                                if not w.canceled))
        # md_table needs a blank line before it; its output starts
        # with one newline, so add the other after the header text
        sections[f'Step {step} — {", ".join(stage)}'] = mo.md(
            control_header(stage, parents) + '\n\n' +
            html_table([('input configuration-space point', pnames),
                        ('control', None), ('$w_{in}$', None),
                        ('particles', None), ('branch $w$', None),
                        ('output configuration-space point', pnames),
                        ('$w_{out}$', None)], rows, md_cell) +
            f'\n\ntotal probability after step: {total:.6f}')
    return mo.accordion({'### Weight evolution table (configuration-space points)':
                         mo.accordion(sections, multiple=True, lazy=True)})


def final_points(sim):
    # Worlds sorted canonically: gate (in evaluation order), then port
    # (upper before lower), then sign (+ before −); the configuration
    # label's coordinates are reordered to match.
    # weights and probabilities at one fixed precision (three
    # decimals); the phase is an angle, which gets at most two
    rows = [[f'`{tok}`' for _, tok in particle_tokens(sim, p)] + [
        math_weight(p.weight, prec=3),
        math_prob(p.probability, prec=3),
        f'${phase_deg(p.weight):.2f}º$',
    ] for p in sorted(sim.result_space.index.values(),
                      key=lambda p: cs_point_sort_key(sim, p))]
    return mo.accordion({'### Final configuration-space points\n': mo.md(html_table(
        [('configuration', particle_names(sim)), ('weight $w$', None),
         (r'$\lvert w\rvert^2$', None), ('phase', None)], rows, md_cell))})


def marginals(sim):
    # Marginal in the statistics sense: each row sums |w|² over every
    # final configuration-space point containing that coordinate — the chance of finding that
    # particle, with that sign, at that port, regardless of where the
    # other particles ended up. Rows follow gate evaluation order (upper
    # before lower, + before −), so a port's +/− pair sits together and
    # sums to the port's total output probability.
    acc = {}
    for p in sim.result_space.index.values():
        prob = float(p.probability)
        for coord in p.coords.values():
            entry = acc.setdefault(f'{coord.pkey}@{coord.position.origin}',
                                   [coord, 0.0])
            entry[1] += prob
    rows = [(f'`{key}`', f'{entry[1]:.4f}')
            for key, entry in sorted(acc.items(),
                                     key=lambda kv: coord_sort_key(sim, kv[1][0]))]
    return mo.accordion({
        '### Marginal probabilities (one coordinate at a time)':
            mo.md(r'Each row sums $\lvert w\rvert^2$ over every final configuration-space point '
                  'in which that particle, with that sign, sits at that '
                  'port — its probability there *regardless of where the '
                  'other particles ended up* (the marginal over the rest '
                  "of the configuration). The $+$/$-$ rows at one port "
                  "together give the port's total output probability.\n" +
                  md_table(['coordinate', 'probability'], rows))
    })


def gate_io_table(sim):
    # Per-step gate traffic: what arrived at each port (previous step's
    # coordinate endpoints) and what left it (that step's origins), with
    # per-sign probabilities and the aggregate Σ (|Σ|² and phase).
    rows = [(row['step'], row['gate'], row['port'],
             row['input'].replace('\n', '<br>'),
             row['output'].replace('\n', '<br>'))
            for row in gate_io(sim)]
    return mo.accordion({
        '### Gate inputs and outputs by step':
            mo.md(md_table(['step', 'gate', 'port', 'input', 'output'], rows))
    })


def detailed_results(sim):
    """The whole section for a finished run."""
    return mo.accordion({'## Detailed Results\n\n<span style="font-size:0.85em">'
                         'Numerical simulation results</span>': mo.vstack([
        evolution_table(sim), final_points(sim), marginals(sim), gate_io_table(sim)])})
