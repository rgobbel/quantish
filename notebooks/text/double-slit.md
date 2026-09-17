# The double-slit experiment

A quantish implementation of the classic double-slit experiment. Fire a stream of particles at two slits,
observe as interference fringes build up, as well as what happens when one slit is blocked, or a recorder
is placed at one slit.

In the quantish universe of *Good and Real* (chapter 4), the two slits
are the two switch outputs of a splitting Fredkin gate. Blocking a slit is
diverting an output wire away (figures 4.13 and 4.14). The slits are idealized as
infinitely narrow, so there is no single-slit diffraction envelope. We simulate a delay by a gate that
rotates a particle's weight without altering its amplitude.

The whole apparatus simulates a [Mach-Zehnder Interferometer](https://en.wikipedia.org/wiki/Mach%E2%80%93Zehnder_interferometer).

Three conditions are simulated:

1. **Both slits open**: each particle traverses both slits in superposed
  worlds that interfere. Dark fringes appear where the worlds cancel
  (positions where either slit alone would deliver particles receive
  none), and bright fringes receive up to twice what the two
  single-slit curves sum to.
2. **One slit blocked**: there is only one world, so there is nothing to interfere with.
  We see a flat line at that slit's intensity.
3. **Recorder on one slit** (figures 4.10 and 4.15): both slits stay open,
  but on the right-hand slit we place a particle whose output destination
  indicates which slit (i.e., which switch wire) the main input particle
  went through. The two outputs now end
  in distinguishable configurations, so the engine's remerge rule
  forbids their interference: the fringes wash out and the screen
  shows exactly the classical sum, though nothing blocked either path.

Below each screen is a diagram of the actual gate network the
engine ran to produce it. Every
particle's landing point is drawn from exact world-amplitudes
computed by the quantish engine. These same circuits, with their angles as sliders and their virtual screens,
are in the [Decoherence lab](#sec-lab), along with some more elaborate interference
circuits that demonstrate cascaded and tunable interference, as well as a [quantum eraser](https://en.wikipedia.org/wiki/Quantum_eraser_experiment).
