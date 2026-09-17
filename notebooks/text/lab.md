# Decoherence lab

The double-slit family side by side, every angle a slider, with screens and virtual screens.

A workbench for putting two quantish circuits side by side. Load a
model into each slot — any model in the library, or a model file of
your own — and its angles become sliders, its own notes explain it,
and its circuit diagram follows the sliders. A model that declares a
screen (a `sweep` on a phase plate: which phase sweeps across the
pixels, which particle at which detector makes a hit, and, where a
recorder is read out, which particle's sign sorts the hits) also
gets a fired-particle screen with its exact intensity curve — and any model can be given one, or a different one, from the slot's controls: choose the phase plate to sweep, the particle and gate that make a hit, and the sort — and the *virtual screens*: one film strip per stage showing what the screen would be if the two paths were merged right there — whole and per sorted subset — so a which-way record is seen being written, and erased, as the fringes die and return. A table gives the same progression as fringe visibilities, and every slot carries the weight-evolution graphic of its particles across the stages.

The library holds, by collection:

- the **decoherence** collection: the double-slit family with a
  screen — which-way recorders complete and partial, the quantum
  eraser, and chains of recorders with and without an eraser; the plain double slit is the one the [Double-slit experiment](#sec-double-slit) fires particles through;
- the book's figures (**gr2026**, **gr2006**) and the **extras**,
  most of which have no screen but load all the same, with their
  diagrams and angle sliders;
- any model file of your own, added with the button below.

Every gate has a slider, and beside each slider a checkbox: uncheck it and the gate is switched off — a plain wire that every particle passes straight through. Every particle has a checkbox too: unchecked, it never enters — a null input, its wires empty — so a circuit can be taken apart piece by piece without rewiring it. A switched-off slider grays out, and the diagram grays and crosses out whatever is off.

Every landing point on a screen is drawn from exact weights computed
by the quantish engine.
