# Quantish Physics

A simulation of "quantish" physics, as described in Chapter 4 of *Good and
Real: Demystifying Paradoxes from Physics to Ethics* (Gary L. Drescher, MIT
Press, 2006). The quantish universe is a toy analogue of quantum mechanics:
particles with complex-valued weights flow through a network of Fredkin
gates, splitting into weighted superpositions of classical states (here
called **configuration-space points**), interfering,
recombining, and — in the chapter's culmination — violating Bell's
inequality from entirely local machinery.

Every figure from the chapter is included as a runnable model, in both the
2006 published numbering (`models/gr2006/`) and the numbering of the 2026
revised draft (`models/gr2026/`); `models/README.md` has the mapping.

## Setup

Requires Python 3.13+. With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
git clone https://github.com/rgobbel/quantish.git
cd quantish
uv sync
```

Or with pip: `pip install -e .` in a fresh virtual environment.

### External tools for the circuit diagrams

The TikZ circuit diagrams (shown in both apps and available from the
CLI) are rendered with `pdflatex` and converted with `pdf2svg`. Without
them the apps still run, but the diagram panels show a "render
unavailable" note instead. The LaTeX install must include TikZ/PGF and
the `standalone` document class:

- Debian/Ubuntu (including Jetson boards):
  `sudo apt install texlive-latex-base texlive-latex-extra
  texlive-fonts-recommended texlive-fonts-extra pdf2svg`
  (a verified-working set; `texlive-latex-base` + `pdf2svg` alone is
  not enough)
- macOS: MacTeX, or BasicTeX plus `sudo tlmgr install standalone`;
  then `brew install pdf2svg`

Also optional:

- ImageMagick (`magick`) — PNG export of TikZ diagrams from the CLI
- `mmdc` (mermaid-cli) — rendering Mermaid diagrams to SVG/PDF from the CLI

## The interactive app

```bash
uv run marimo run notebooks/quantish_app.py
```

A [marimo](https://marimo.io) notebook app: pick a model and gate angles,
run it, and explore the results — circuit diagrams (TikZ and Mermaid), a
graph of every configuration-space point's evolution through the network,
a step-by-step weight-evolution table, final configuration-space points
with exact weights, per-particle
marginal probabilities, Monte Carlo sampling, an interactive weight-split
explorer, and (for the EPR models) the full Bell/CHSH sweep.

There is also a small double-slit demonstration:

```bash
uv run marimo run notebooks/double_slit_app.py
```

## The command line

```bash
uv run quantish -c fig4.17            # the EPR experiment (gr2026 numbering)
uv run quantish -c fig4.13 --symbolic # exact symbolic weights
uv run quantish -c fig4.16 --config-sub gr2006   # the 2006 model set
```

Useful options (see `--help` for the full list):

- `--symbolic` / `--numeric` — exact SymPy math vs. floating point
- `--diagram-when both` — Mermaid diagrams before and after the run
- `--tikz-diagram pdf|svg|png` — render the TikZ circuit diagram
- `--sample --n-samples N` — Monte Carlo sampling of outcomes
- `--epr-stats` — the Bell/CHSH sweep on an EPR model
- `--set NAME=EXPR` — override a model variable, e.g. `--set theta2=pi/8`
- `--loglevel debug` — a detailed trace of every gate firing and
  configuration-space point split, with checkable weight arithmetic

## Models

A model is a YAML file: particles with initial weights, Fredkin gates with
rotation angles, links wiring outputs to inputs, and explicit `run_stages`.
`models/defaults.yaml` supplies shared settings, `models/extras/` holds
circuits with no book figure, and `models/README.md` documents the
2006/2026 figure correspondence.

## Tests

```bash
uv run pytest
```

The suite includes golden-state tests: exact final configuration-space point
amplitudes for the book models, verified in both numeric and symbolic modes.
