Every quantish circuit is also a quantum circuit that can be built from qubits. Each particle gets two of them, a sign qubit that holds the particle's sign, $\vert0\rangle$ for plus, $\vert1\rangle$ for minus, and a position qubit that holds which of a gate's two switch wires the particle is on.

A Fredkin gate with no control particle present becomes three standard operations on those two qubits, applied in order. First, the sign qubit is rotated by the measurement angle $\theta$ (an $R_x$ rotation by $2\theta$). Second, a CNOT (controlled NOT) from the sign qubit to the position qubit: where the sign qubit reads minus, the position flips; where it reads plus, the position stays. Third, the rotation is undone. Together these say what the book's split rule says: the gate measures the sign in a basis turned by $\theta$, and the position wire records the answer, straight for the parallel component and crossed for the perpendicular one. The four split components $\cos^2\theta$,
$i \cdot \sin\theta\cos\theta$, $\sin^2\theta$, and $-i \cdot \sin\theta\cos\theta$ are the entries of the matrix this product works out to.

A control particle present flips the position qubit once more, conditioned on the control particle's own position qubit. That is the only operation that acts on two particles at once, so it is the only place where one particle becomes entangled with another.

Three smaller pieces. A phase plate multiplies by a phase, conditioned on the particle's position. A particle that starts on two wires is a rotation ($R_y$) of its position qubit. A pass along a control wire is no operation at all: the particle moves on unchanged.

One bookkeeping detail: a position qubit can only tell two wires apart. When two of a particle's possible paths would land on the same qubit value, the compiler adds a flag qubit to keep them distinct.

The circuit below is compiled from the network on the canvas, switched-off gates and all. After a Run, its statevector is simulated here and compared with the engine's final configuration-space points. The Qiskit source builds the same circuit for a real Qiskit session, since Qiskit does not run in the browser.
