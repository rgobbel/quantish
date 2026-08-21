# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quantish Physics is a simulation of "quantish" physics from Chapter 4 of *Good and Real: Demystifying Paradoxes from Physics to Ethics* (Gary L. Drescher, 2006). The system simulates quantum-like behavior using Fredkin gates, particles with complex-valued weights, and EPR-style experiments.

### Terminology

Follow the book's terms. A **configuration-space point** (`ConfigSpacePoint` and `cs_point` in code — the book calls it a *classical state*) is a full assignment of a position and sign to every particle, with one complex weight. Write the term out in prose and displays; the abbreviation "CS point" is reserved for variable names (`cs_point`) and very informal communication. The **quantum state** (the full quantish world) is the weighted superposition of configuration-space points. Avoid the bare word "world" for either. The squared magnitudes of the configuration-space points' weights always sum to 1 (the `check_total_probability` invariant), and a configuration-space point's |weight|² is its probability of being the successor to its immediate predecessor. The four split values a gate applies to a switch-wire particle are its **components** — c2a, c2b, c3a, c3b in the book's order (cos²θ, i·sinθcosθ, sin²θ, −i·sinθcosθ); per-particle displays label them by particle, not "factor".

## Development Commands

### Running the Simulation

The main entry point is `quantish/main.py`. Run simulations using:

```bash
python -m quantish.main -c <model_name>   # e.g. -c gr2026/fig4.17
```

Model files live in the `models/` directory, split by book edition: `gr2006/` (2006 published figure numbers), `gr2026/` (2026 revised-draft numbers), and `extras/` (circuits with no book figure). See `models/README.md` for the figure mapping (e.g., `gr2026/fig4.17.yaml` is the EPR experiment).

### Key Command-Line Options

- `-c/--config`: YAML configuration file (required)
- `--simulate/--no-simulate`: Run simulation (default: True)
- `-d/--diagram`: Generate Mermaid diagram of gate network
- `--symbolic/--numeric`: Force symbolic or numeric math mode
- `--sample --n-samples N`: Run N random samples and collect statistics
- `--epr-stats`: Collect EPR-specific statistics for EPR experiments
- `-l/--log`: Write logs to file
- `--loglevel`: Set log level (debug/info/warning/error)

### Testing

Run tests using:

```bash
uv run pytest
```

Run a single test file:

```bash
uv run pytest tests/test_wiring.py
```

pytest (with pytest-subtests) is in the dev dependency group; `uv sync`
installs it.

### Configuration

Configuration is split between:
- `models/defaults.yaml`: Default settings (loaded by default with `--use-defaults`)
- Individual model files: Specific experiment configurations

## Architecture

### Core Components

1. **Simulation** (`quantish/simulation.py`)
   - Main simulation engine that propagates particle weights through a gate network
   - Executes gates stage by stage per the model's required `run_stages`
   - Manages particles, gates, and the overall state

2. **FredkinGate** (`quantish/gate.py`)
   - A measurement angle plus the four precomputed split components
   - Three wires: control, upper, lower
   - `switch_components()` yields the four-way split for a switch-wire
     particle — component values fixed by the angle, destinations swapped
     by control presence or a minus sign
   - Optional `phase` (an extension beyond the book's gates): every
     traversing particle's weight is rotated by e^(iφ) — switch-wire
     particles via the components, control pass-throughs via
     `phase_factor` in the runner. An angle-0 gate with a phase, entered
     through its control wire, is a pure phase plate (the double-slit
     demo's path-length difference)

3. **Particle** (`quantish/particle.py`)
   - A particle: name, complex-valued initial weight, sign (+1 or -1)
   - `PKey` is the hashable (name, sign) identity used in coordinates

4. **QNumber System** (`quantish/qnumber.py`)
   - Unified number representation supporting both symbolic (SymPy) and numeric (float/complex) modes
   - The `CalcMode.mode` global variable controls whether to use 'Symbolic' or 'Float'
   - Complex and Real wrap SymPy or native Python types (angles are
     plain Reals in radians, un-normalized; `Real.degrees` converts)
   - Used throughout the codebase for all mathematical operations

5. **Configuration Space** (`quantish/config_space.py`)
   - `GatePort`/`Position`/`PCoordinate`: where each particle is
   - `ConfigSpacePoint` and the `ConfigSpace` store (merge-on-add =
     interference)
   - `ConfigSpaceRunner`: the engine — per stage, each configuration-space
     point expands to the cartesian product of its particles' splits

6. **Display helpers** (`quantish/display.py`)
   - Presentation over a finished Simulation: port value blocks (Mermaid),
     the gate-traffic table (app), and the canonical display sort keys

### Data Flow

1. **Initialization**: Load YAML config → validate wiring → build
   Particles and FredkinGates → schedule stages from the model's
   `run_stages` (checked against the link topology)
2. **Propagation**: stage by stage, every configuration-space point
   expands to the cartesian product of its particles' alternatives
   (pass-through, or the four-way switch split); successors with
   identical coordinates merge by adding weights (interference), and
   points whose weights cancel are dropped
3. **Sampling Mode** (optional): Monte Carlo draws from the final
   superposition (terminal) or stage-by-stage world-lines (path)
4. **Output**: final configuration-space points, statistics, and optional
   TikZ/Mermaid/weight-evolution diagrams

### YAML Configuration Structure

Model files define:
- `title`: Experiment name
- `caption` (optional): a one-line description, typically the book
  figure's caption — shown as a box in the Mermaid diagram, under the
  title in the app, and in the model-load log
- `run_stages`: named execution stages (every linked gate must appear)
- `diagram_groups` (optional): display grouping when it differs from
  `run_stages`
- `variables`: Symbolic constants (angles, weights) using YAML anchors
- `particles`: Initial particles with weight and sign
- `gates`: Fredkin gates with rotation angles (and optionally a `phase`)
- `links`: Connectivity graph (particle/gate outputs → gate inputs)

Configuration options (usually in defaults.yaml):
- `symbolic`: true/false for math mode
- `string_precision`: decimal places in displays
- `max_symbolic_len`: Symbolic-mode expressions longer than this display
  as floats (display.sym_or_float)
- `sample` / `n_samples`: enable sampling mode
- `epr_stats`: collect EPR statistics (the fig4.17 models set it)

### Important Patterns

1. **Math Mode**: The system can operate in symbolic (exact) or numeric (float) mode. Set via `CalcMode.mode` at startup based on config.

2. **Positions**: a particle's position is a `Position(origin, endpoint)` pair of gate ports, displayed like `g1.upper_out>g3.control_in`; `SEP` ('.') separates gate and port in link strings

3. **Gate Wiring**: Gates have three wires (control, upper, lower). Control determines whether upper/lower outputs are straight or swapped; a delay gate is used via its control wire only and passes particles through unchanged.

4. **Interference**: configuration-space points with identical coordinates merge by adding weights; points whose weights cancel to zero are dropped (and marked `cancelled`).

## File Organization

- `quantish/`: Main package (renamed from `multiworld/`; the original
  2025 `quantish/` package is archived in `HIDEME/`)
  - `main.py`: Entry point and CLI
  - `simulation.py`: Simulation engine
  - `gate.py`: Fredkin gate implementation
  - `particle.py`: Particle representation
  - `qnumber.py`, `angle.py`: Unified number system
  - `config_space.py`: configuration-space points and the stage engine
  - `display.py`: presentation helpers over a finished Simulation
  - `epr.py`: EPR experiment sweeps and statistics
  - `montecarlo.py`: Monte Carlo sampling mode
  - `mermaid_diagram.py`, `network_graph.py`, `tikz_diagram.py`: Diagrams
  - `double_slit.py`: the double-slit demo's engine side
  - `util.py`: shared constants (SEP, wires, Sign) and small helpers
- `models/`: YAML configuration files for experiments
  - `defaults.yaml`: Default configuration
  - `gr2006/`, `gr2026/`, `extras/`: per-edition book figures and non-book circuits (see `models/README.md`)
- `tests/`: Unit tests (golden states, wiring validation, EPR, Monte
  Carlo, variables, double slit)
- `notebooks/`: the marimo apps (`quantish_app.py`, `double_slit_app.py`)
- `HIDEME/`: Historical/experimental code and archived dead code (ignore)

## Notes for Development

- When modifying gate behavior, test with both symbolic and numeric modes
- EPR experiments (gr2026/fig4.17.yaml) are particularly sensitive to angle settings
- The simulation supports sampling mode for statistical analysis of quantum-like behavior
- Mermaid diagrams can be generated before/after simulation to visualize gate networks
- Log output is controlled by `--loglevel` and provides detailed execution traces in debug mode