# Model files

Each YAML file here describes one circuit: particles, Fredkin gates, and the
links between them. Run one with

```bash
python -m quantish.main -c gr2026/fig4.17
```

(paths are relative to this directory; `defaults.yaml` is loaded first).

## Why three directories?

The 2026 revised draft of *Good and Real* chapter 4 renumbers several figures
relative to the 2006 published edition. Most readers will have one version or
the other, so rather than maintain a single set with a translation table, each
edition gets a complete, self-contained set — pick the directory matching your
copy of the book and the file names line up with its figure numbers.

- **`gr2006/`** — figures as numbered in the 2006 published edition.
- **`gr2026/`** — figures as numbered in the 2026 revised draft.
- **`extras/`** — everything beyond the book's circuits as printed: the
  variants of book circuits
  (`fig4.13_full`, `fig4.15x`, `fig4.16x`, `fig4.16_delay`, named by
  their 2026 figure numbers), the double-slit apparatus behind the
  double-slit app (`double_slit`), diagnostic circuits (`noop_*`,
  `zero_*`, `one_angle_plus_zero`, `split_*`), and figure 12 of AI Memo
  1026a (`AIM_Figure12`), the 1988 paper the chapter grew from.

## Figure mapping (2006 ↔ 2026)

Figures 4.2–4.8 are numbered identically in both editions. After that the
2026 draft inserts a new figure 4.9 (fig. 4.7's circuit with differing
angles), shifting the observation/interference sequence by one:

| circuit | 2006 | 2026 |
|---|---|---|
| U1: the classical Fredkin gate (a state moves through configuration space) | 4.2 | 4.2 |
| U2: p2 and p3 observe a superposed p1 (noninterfering branches) | 4.3 | 4.3 |
| four-way split | 4.4 | 4.4 |
| same angle twice / config view | 4.5, 4.6 | 4.5, 4.6 |
| self-inverting gate | 4.7 | 4.7 |
| succession of differing angles | 4.8 | 4.8 |
| 4.7's circuit with differing angles | — | 4.9 |
| p2 and p3 observe p1's position | 4.9 | 4.10 |
| repeated trials, cumulative records | 4.10 | 4.11 *(illustration, no model)* |
| an observation distinguishes outcomes | 4.11 | 4.12 |
| paths remerge and interfere | 4.12 | 4.13 |
| one path diverted, no interference | 4.13 | 4.14 |
| observation circumvents interference | 4.14 | 4.15 |
| erasure re-establishes interference | 4.15 | 4.16 |
| EPR experiment (g1–g6) | 4.16 | — *(the 2026 draft extends it with g7/g8 into its 4.17)* |
| EPR with second measurement (g1–g8) | — *(no 2006 figure)* | 4.17 |
| EPR config-space view | 4.17 | 4.18 *(same circuit as the EPR figure)* |

The two edition directories hold only the book's circuits as printed (the
EPR fidelity note below aside). Variants live in `extras/` under their 2026
figure numbers: `x` alters wiring or angles, `_full` connects wires the
figure leaves out, `_delay` adds delay gates that keep the particles in
step.

Note on fidelity: the EPR models in **both** directories use the corrected
circuit from the 2026 draft (`p2` enters `g2.lower`). The 2006 printing of
its EPR circuit — figure 4.16 there, which preps `g2` at Q1+π/2 — contained
a wiring error, acknowledged in the revised draft, so a faithful
transcription of the printed 2006 circuit would not reproduce the quantum
statistics the text derives.
