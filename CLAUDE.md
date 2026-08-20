# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quantish Physics is a simulation of "quantish" physics from Chapter 4 of *Good and Real: Demystifying Paradoxes from Physics to Ethics* (Gary L. Drescher, 2006). The system simulates quantum-like behavior using Fredkin gates, particles with complex-valued weights, and EPR-style experiments.

### Terminology

Follow the book's terms. A **CS point** (configuration-space point, `ConfigSpacePoint`, `cs_point` in code — the book calls it a *classical state*) is a full assignment of a position and sign to every particle, with one complex weight. The **quantum state** (the full quantish world) is the weighted superposition of CS points. Avoid the bare word "world" for either. The squared magnitudes of the CS points' weights always sum to 1 (the `check_total_probability` invariant), and a CS point's |weight|² is its probability of being the successor to its immediate predecessor. The four split values a gate applies to a switch-wire particle are its **components** — c2a, c2b, c3a, c3b in the book's order (cos²θ, i·sinθcosθ, sin²θ, −i·sinθcosθ); per-particle displays label them by particle, not "factor".

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
python -m pytest tests/
```

Run a single test file:

```bash
python -m pytest tests/test_gate.py
```

Note: pytest is not currently in dependencies - may need to be added if running tests.

### Configuration

Configuration is split between:
- `models/common.yaml`: Default settings (loaded by default with `--use-common`)
- Individual model files: Specific experiment configurations

## Architecture

### Core Components

1. **Simulation** (`quantish/simulation.py`)
   - Main simulation engine that propagates particle weights through a gate network
   - Executes gates stage by stage per the model's required `run_stages`
   - Manages particles, gates, and the overall state

2. **FredkinGate** (`quantish/gate.py`)
   - Implements quantum Fredkin gates with rotation angles
   - Three input wires: control, upper, lower
   - Performs complex rotations on particle weights using trigonometric scaling
   - Multiple `cpair` calculation methods available (cpair, cpair_alt, cpair0, cpair1, cpair2)
   - The `alternative_measure` config option selects which method to use

3. **Particle** (`quantish/particle.py`)
   - Represents quantum-like particles with:
     - Complex-valued weights
     - Sign (+1 or -1)
     - Name and unique ID
   - Supports merging particles via addition
   - Tracks probability (magnitude squared of weight)

4. **QNumber System** (`quantish/qnumber.py`)
   - Unified number representation supporting both symbolic (SymPy) and numeric (float/complex) modes
   - The `CalcMode.mode` global variable controls whether to use 'Symbolic' or 'Float'
   - Complex, Real, and Angle classes wrap SymPy or native Python types
   - Used throughout the codebase for all mathematical operations

5. **Sink** (`quantish/sink.py`)
   - Collects output particles from gates
   - Can merge particles based on configuration (combine_signs, combine_names)
   - Filters particles by presence_threshold

6. **Configuration Space** (`quantish/config_space.py`)
   - Defines wire types: control, upper, lower
   - GateState tracks gate inputs/outputs during simulation

### Data Flow

1. **Initialization**: Load YAML config → create Particles and FredkinGates → establish Links between particles/gates
2. **Topological Sort**: Determine execution order of gates based on particle flow
3. **Propagation**: For each gate in order:
   - Gather input particles on control/upper/lower wires
   - Apply gate transformation (cpair rotation)
   - Forward output particles to next gates or sinks
4. **Sampling Mode** (optional): Run multiple iterations, randomly sampling from probability distributions
5. **Output**: Final particle states, statistics, and optional Mermaid diagrams

### YAML Configuration Structure

Model files define:
- `title`: Experiment name
- `phases`: Logical grouping of gates
- `variables`: Symbolic constants (angles, weights) using YAML anchors
- `particles`: Initial particles with weight and sign
- `gates`: Fredkin gates with rotation angles
- `links`: Connectivity graph (particle/gate outputs → gate inputs)

Configuration options (usually in common.yaml):
- `symbolic`: true/false for math mode
- `merge`: Control particle merging behavior
- `normalize_weights`: Normalize before/after measurement
- `probability_threshold`: Thresholds for control/forwarding/presence
- `sample`: Enable sampling mode

### Important Patterns

1. **Math Mode**: The system can operate in symbolic (exact) or numeric (float) mode. Set via `CalcMode.mode` at startup based on config.

2. **Particle Names**: Track lineage through transformations using '>' separator (e.g., "p1>g1.upper>g3.control")

3. **Gate Wiring**: Gates have three wires (control, upper, lower). Control determines whether upper/lower outputs are straight or swapped.

4. **Probability Thresholds**: Multiple thresholds control behavior:
   - `control`: Whether superposed control particle is "present"
   - `forwarding`: Drop particles below this probability
   - `presence`: Don't add particles to sinks below this

5. **Merging**: Particles can be merged before measurement or forwarding based on sign and/or name

## File Organization

- `quantish/`: Main package (renamed from `multiworld/`; the original
  2025 `quantish/` package is archived in `HIDEME/`)
  - `main.py`: Entry point and CLI
  - `simulation.py`: Simulation engine
  - `gate.py`: Fredkin gate implementation
  - `particle.py`: Particle representation
  - `qnumber.py`, `calc_mode.py`, `angle.py`: Unified number system
  - `config_space.py`: CS points, gate state, wire definitions
  - `epr.py`: EPR experiment sweeps and statistics
  - `montecarlo.py`: Monte Carlo sampling mode
  - `mermaid_diagram.py`, `network_graph.py`, `tikz_diagram.py`: Diagrams
  - `double_slit.py`, `marimo_helpers.py`: Notebook support
  - `util.py`: Utilities (logging, parsing, etc.)
- `models/`: YAML configuration files for experiments
  - `defaults.yaml`: Default configuration
  - `gr2006/`, `gr2026/`, `extras/`: per-edition book figures and non-book circuits (see `models/README.md`)
- `tests/`: Unit tests
- `notebooks/`: Jupyter/exploratory notebooks
- `HIDEME/`: Historical/experimental code (ignore)

## Notes for Development

- When modifying gate behavior, test with both symbolic and numeric modes
- EPR experiments (gr2026/fig4.17.yaml) are particularly sensitive to angle settings
- The simulation supports sampling mode for statistical analysis of quantum-like behavior
- Mermaid diagrams can be generated before/after simulation to visualize gate networks
- Log output is controlled by `--loglevel` and provides detailed execution traces in debug mode