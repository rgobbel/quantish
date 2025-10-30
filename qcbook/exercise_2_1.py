## Programming Quantum Computers
##   by Eric Johnston, Nic Harrigan and Mercedes Gimeno-Segovia
##   O'Reilly Media
##
## More samples like this can be found at http://oreilly-qc.github.io

## This sample generates a single random bit.

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile #, execute, IBMQ, BasicAer
from qiskit_aer import AerSimulator
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import Pauli, SparsePauliOp
import numpy as np
import math
## Uncomment the next line to see diagrams when running in a notebook
#%matplotlib inline

## Example 2-1: Random bit
# Set up the program
reg = QuantumRegister(1, name='reg')
reg_c = ClassicalRegister(1, name='regc')
qc = QuantumCircuit(reg, reg_c)

qc.reset(reg)          # write the value 0
qc.h(reg)              # put it into a superposition of 0 and 1
qc.measure(reg, reg_c) # read the result as a digital bit
print(qc.draw())

params = np.vstack([
    np.linspace(-np.pi, np.pi, 100),
    np.linspace(-4 * np.pi, 4 * np.pi, 100)
]).T


observables = [
    [SparsePauliOp(["XX", "IY"], [0.5, 0.5])],
    [Pauli("XX")],
    [Pauli("IY")]
]

# backend = AerSimulator.get_backend('statevector_simulator')
sim = AerSimulator()
estimator = StatevectorEstimator()
job = estimator.run([(qc, observables, params,)])

# tqc = transpile(qc, sim)
# job = sim.run(tqc)
# job = execute(qc, backend)
result = job.result()

counts = result.get_counts(qc)
print('counts:',counts)

outputstate = result.get_statevector(qc, decimals=3)
print(outputstate)
qc.draw()        # draw the circuit