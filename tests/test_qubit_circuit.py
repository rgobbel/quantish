"""The qubit compiler (quantish/qubit_circuit.py) reproduces the engine:
for every model, the statevector of the compiled circuit decodes to the
same final configuration-space points with the same weights."""
from pathlib import Path

import pytest
import yaml
from addict import Dict as Addict

from quantish.qnumber import CalcMode
from quantish.qubit_circuit import compile_qubits
from quantish.simulation import Simulation

MODELS = Path(__file__).resolve().parents[1] / 'models'
MODEL_FILES = sorted(p for p in MODELS.rglob('*.yaml')
                     if p.name not in ('defaults.yaml', 'schema.yaml')
                     and 'uploads' not in p.parts and not p.name.startswith('.'))
TOL = 1e-9


def load(path: Path) -> Simulation:
    with open(MODELS / 'defaults.yaml') as f:
        cfg = yaml.safe_load(f)
    with open(path) as f:
        cfg.update(yaml.safe_load(f))
    cfg['loglevel'] = 'warning'
    return Simulation(Addict(cfg))


@pytest.fixture(autouse=True)
def float_mode():
    CalcMode.default('Float')
    yield
    CalcMode.default('Float')


@pytest.mark.parametrize('path', MODEL_FILES,
                         ids=[str(p.relative_to(MODELS)) for p in MODEL_FILES])
def test_compiled_circuit_matches_engine(path):
    sim = load(path)
    space, _ = sim.run()
    expected = {p.key: complex(p.weight) for p in space.index.values()}
    circuit = compile_qubits(sim)
    got = circuit.final_points()
    assert set(got) == set(expected), (sorted(set(got) ^ set(expected)))
    for key, weight in expected.items():
        assert abs(got[key] - weight) < TOL, (key, got[key], weight)
    assert abs(sum(abs(w) ** 2 for w in got.values()) - 1) < 1e-6


def test_gate_identity_matches_switch_components():
    # the single-particle circuit of one gate, both signs, both inputs,
    # with and without a control — the 4x4 of Rx(-2θ)·CNOT·Rx(2θ) (plus
    # X on x for a control) against gate.switch_components
    import math

    import numpy as np

    from quantish.gate import FredkinGate
    from quantish.qnumber import qify
    from quantish.qubit_circuit import Op, QubitCircuit
    from quantish.util import Sign
    for deg in (0, 17, 30, 45, 90):
        theta = math.radians(deg)
        gate = FredkinGate('g', qify(theta))
        for control in (False, True):
            qc = QubitCircuit(sim=None)
            s, x = qc.new_qubit('s'), qc.new_qubit('x')
            ops = [Op('rx', s, (), 2 * theta), Op('x', x, ((s, 1),)), Op('rx', s, (), -2 * theta)]
            if control:
                ops.append(Op('x', x))
            for x_in, port in enumerate(('upper', 'lower')):
                for s_in, sign in enumerate((Sign.plus, Sign.minus)):
                    psi = np.zeros(4, dtype=complex); psi[2 * x_in + s_in] = 1
                    for op in ops:
                        psi = qc.apply(psi, op)
                    expected = np.zeros(4, dtype=complex)
                    for dest, out_sign, c in gate.switch_components(port, sign, control):
                        x_out = ('upper', 'lower').index(dest)
                        s_out = 0 if out_sign == Sign.plus else 1
                        expected[2 * x_out + s_out] += complex(c.v)
                    assert np.allclose(psi, expected, atol=1e-12), (deg, control, port, sign)


def test_qiskit_export_agrees():
    qiskit = pytest.importorskip('qiskit', reason='qiskit not installed')
    Statevector = qiskit.quantum_info.Statevector
    for rel in ('gr2026/fig4.13', 'gr2026/fig4.17', 'decoherence/double_slit_eraser'):
        sim = load(MODELS / f'{rel}.yaml')
        circuit = compile_qubits(sim)
        ours = circuit.simulate()
        theirs = Statevector(circuit.to_qiskit()).data * circuit.weight
        import numpy as np
        assert np.allclose(ours, theirs, atol=1e-9), rel
