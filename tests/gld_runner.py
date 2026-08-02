"""Helper for the reference-parity tests: run a quantish_gld circuit through
that repo's OWN loader (circuits_yaml) and engine, printing the final state as
JSON. Executed as a subprocess under the gld repo's venv, because the loader
needs ruamel.yaml, which the quantish venv doesn't carry.

Usage:
    <gld_venv_python> gld_runner.py <gld_repo_dir> <circuit.yaml> ['<angle_override_json>']

angle_override_json maps gate name -> angle expression (string or number).

Output (single line of JSON):
    {"worlds": [[[particle, wire, sign], ...], ...], "weights": [[re, im], ...]}
"""
import json
import sys
from pathlib import Path


def main():
    gld_dir = sys.argv[1]
    circuit_path = sys.argv[2]
    angle_override = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}

    sys.path.insert(0, gld_dir)
    import qnumber as gqn
    gqn.set_calc_mode('Float')
    gqn.CalcMode.default('Float')
    from circuits_yaml import load_circuit
    from engine import simulate_circuit

    circuit = load_circuit(Path(circuit_path))
    label_for_gate = circuit.topology['parsed'].gate_slider_label
    label_value = {label_for_gate[g]: expr for g, expr in angle_override.items()}
    angles = [label_value.get(label, default)
              for label, default in zip(circuit.angle_names, circuit.angle_defaults)]
    initial_state, steps = circuit.builder(angles)
    history = simulate_circuit(initial_state, steps)

    worlds = []
    weights = []
    for wp in history[-1]:
        canon = sorted([pname, wire, int(sign)]
                       for pname, (wire, sign) in wp.config.items())
        worlds.append(canon)
        w = complex(wp.weight)
        weights.append([w.real, w.imag])
    print(json.dumps({'worlds': worlds, 'weights': weights}))


if __name__ == '__main__':
    main()