"""The qubit-circuit panel: a run compiled to a qubit circuit
(quantish.qubit_circuit) — the qubits per particle, the drawn circuit,
its statevector checked against the engine's final configuration-space
points, and the Qiskit source to take away. Its explanation is
notebooks/text/qubits.md, passed in by the notebook (prose('qubits'))."""
from __future__ import annotations

import re

import marimo as mo

from quantish.qubit_circuit import compile_qubits

__all__ = ['qubit_panel']


def qubit_panel(sim, intro: str = ''):
    """The panel for a Simulation that has run."""
    try:
        circuit = compile_qubits(sim)
    except NotImplementedError as exc:
        return mo.md(f'{intro}\n\n_Not compiled: {exc}._')
    names = circuit.qubit_names
    rows = ['| Particle | Sign qubit | Position qubit | Flag qubits |', '|---|---|---|---|']
    for name, pq in circuit.particles.items():
        flags = ', '.join(f'q{f}' for f in pq.flags) or '—'
        rows.append(f'| {name} | q{pq.sign} ({names[pq.sign]}) | q{pq.x} ({names[pq.x]}) | {flags} |')
    title = str(getattr(sim, 'title', '') or '')
    stem = re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_').lower() or 'circuit'
    source = circuit.to_qiskit_source(title)
    parts = [mo.md(intro)] if intro else []
    parts += [
        mo.md(f'**{circuit.n_qubits} qubits, {len(circuit.ops)} operations.**\n\n'
              + '\n'.join(rows)),
        mo.md(f'```text\n{circuit.draw()}\n```'),
        mo.md(_check(circuit, sim)),
        mo.accordion({'Qiskit source': mo.vstack([
            mo.download(data=source.encode(), filename=f'{stem}_qiskit.py',
                        label='Download the Python file'),
            mo.md(f'```python\n{source}\n```'),
        ])}),
    ]
    return mo.vstack(parts)


def _check(circuit, sim) -> str:
    """The circuit's statevector against the engine's run, as a line."""
    space = getattr(sim, 'result_space', None)
    if space is None:
        return ''
    try:
        got = circuit.final_points()
        engine = {p.key: complex(p.weight) for p in space.index.values()}
    except (TypeError, ValueError) as exc:
        return f'_Statevector check skipped (symbolic weights): {exc}_'
    worst = max([abs(got.get(k, 0) - engine.get(k, 0)) for k in set(got) | set(engine)] or [0.0])
    verdict = 'matching' if worst < 1e-9 else 'differing from'
    return (f'Simulated as a statevector: {len(got)} final configuration-space '
            f'point(s), {verdict} the engine\'s run (largest weight difference {worst:.1e}).')
