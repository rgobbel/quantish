# Quantish Physics

This site is intended as a companion to Chapter 4 of *Good and Real: Demystifying Paradoxes from Physics to
Ethics* (Gary L. Drescher, MIT Press, 2006), and an aid to understanding the Everett interpretation of quantum mechanics
through the toy universe that chapter builds.

*Quantish physics* is a toy universe with laws of physics that are analogous to real quantum mechanics under
Everett’s interpretation. The laws of quantish physics largely recapitulate Everett’s relative-state formulation of
quantum mechanics, but with Fredkin gates substituted for quantum waves. The examples show in the book are all presented
as
simulations that can run in a browser.

*Note: The first visit downloads the Python runtime, which can
take a minute or two. Later visits start much faster. Figures in the gr2026 collection follow the numbering of the 2026
revised draft of the book.*

## Quantish and quantum

A quantish particle travels along a wire and has a *sign*, plus or minus. Wires meet at *Fredkin gates*, with three
wires in,
three wires out, and a *measurement angle* θ.

A quantish gate is equivalent to a standard two-qubit operation in quantum computing. Given a particle with
sign qubit $s$ ($\vert0\rangle = \mathrm{plus}$, $\vert1\rangle = \mathrm{minus}$) a position qubit $x$, and a gate
at measurement angle $\theta$ with no control particle present, the result is

$$U (θ) = Rx (\mathrm{s},-2θ) · CNOT (s \rightarrow x)  · Rx (\mathrm{s},+2θ)$$

A particle on the control wire passes straight through and controls
whether the other two wires, the upper and the lower switch ports, cross or run straight. The angle acts on a particle
entering by
the upper or lower wire. This is where quantish parts from classical physics. The particle does not take one exit.
Its weight splits four ways, over the two exits and the two signs, into the
*components* $\mathrm{cos}^2\theta$, $i · \mathrm{sin}\theta · \mathrm{cos}\theta$, $\mathrm{sin}^2\theta$, and
$−i·\mathrm{sin}\theta · \mathrm{cos}\theta$. The squared magnitudes of the four components sum to one.

So the state of a quantish universe is never a single arrangement of its particles. It is a *superposition* of
*configuration-space points*, each a complete assignment of a position and a sign to every particle, each carrying one
complex weight. A gate turns each point into several. The squared magnitude of a point's weight is its probability,
and the probabilities always sum to one. One further rule completes the physics: two configuration-space points that
come to the same position in a network merge, with a result that is the vector sum of their weights. A point with weight
zero disappears. That is interference, and it is the only way anything is ever removed from a quantish universe.

Quantum mechanics has the same basic elements: a state that is a weighted superposition of classical states, unitary
evolution that splits and rotates the weights, probabilities as squared magnitudes, and interference where paths
reconverge. Quantish is just those elements, so that interference, the effect of an observation,
decoherence,
entanglement, and the EPR correlations that break Bell's inequality can all be followed step by step.

## The nature of an "observation" in Everett and quantish

The chapter's reading of quantum mechanics, and this site's, is Everett's: nothing ever collapses. An observation is one
more Fredkin gate. A recorder particle passes through a gate controlled by the particle being observed, and comes out on
one wire or the other according to where that particle went. The superposition now holds configuration-space points in which
the record reads "upper" and points in which it reads "lower", and no rule picks between them. Each classical-world instance of the
recorder sees one definite outcome. From within one classical world the outcome looks random, with the frequencies the
squared magnitudes predict.

Nothing forbids the versions from interfering. They simply no longer coincide, because after transiting the recorder 
they are not at the same coordinate in configuration space, so there is nothing for the merge rule to add. 
That is *decoherence*, and it is why observing which slit a particle used destroys the fringes without touching the 
particle. Undoing the record by transiting a gate that restores coordinate correspondence makes the points coincide
again, and the fringes return: that is the quantum eraser. If on the other hand we let the record spread to more 
particles, the fringes are gone permanently, not due to any law against interference but because the points that would 
have to merge never meet again, barring some mechanism that sends them through a set of gates that precisely undoes the
decoherence. The same machinery, run on two particles prepared together and measured apart, gives the EPR correlations, 
which no assignment of hidden local properties can reproduce.

## How the site is organized

Each section is built on the same quantish engine. They run in this order as a tutorial, from one gate to Bell's
theorem, and they work together: a circuit built in the network builder opens in the book's figures and in the
decoherence lab, and a gate clicked after a run of one of the book's figures can be opened in the explorer with its actual
incoming weight.

- [**Weight-split Explorer**](#sec-explorer) — one gate, one weight. Set the angle and the incoming weight and watch the
  four components as vectors and as numbers, with the two exits' sums. Everything else on the site is built from this
  split.
- [**Double-slit experiment**](#sec-double-slit) — a splitting gate and a merging gate make the two slits. You can fire
  particles in volleys and see the fringes build up, while at the same time seeing the effect of a blocked slit, or 
  what happens when a recorder is introduced into the circuit.
- [**Book figures**](#sec-quantish) — the chapter's figures as live circuits, from the first splits through observation,
  interference, erasure, and the EPR experiment. Run one and follow the weights through the gates, stage by stage, to
  the final probabilities; run it many times to see an experiment's statistics; sweep an angle; test Bell's and the CHSH
  inequalities against quantish and local hidden-variable predictions.
- [**Network builder**](#sec-builder) — build a circuit of your own, or change one of the chapter's on a canvas, run
  it, and send it to the other sections or download it as a YAML file.
- [**Decoherence lab**](#sec-lab) — the double-slit family side by side, with every angle a slider: the plain double
  slit, complete and partial which-way recorders, a quantum eraser, and chains of recorders.
