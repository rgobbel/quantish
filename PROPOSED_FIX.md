# Proposed Fix for Superposed Control Particles

## Problem
When a control particle is in superposition (complex weight with both real and imaginary components nonzero), the current code treats it as simply "present" or "not present" based on probability threshold. This is incorrect - a superposed control should create BOTH swap and no-swap branches.

## Solution Overview
Measure the control particle against the gate's angle to get:
- Measurement-parallel components (control "present" - causes swap)
- Measurement-perpendicular components (control "absent" - no swap)

Then weight the switch-wire outputs accordingly.

## Code Changes to simulation.py

Replace lines 121-167 with the following:

```python
                ## Set up control input and determine if we need to handle superposition
                control_parallel = []  # Components for "control present" (swap) branch
                control_perpendicular = []  # Components for "control absent" (no-swap) branch
                control_is_superposed = False

                if inputs['control']:
                    merged_control = Particle.merge(inputs['control'])

                    # Measure control particle to get parallel/perpendicular components
                    control_measurement = gate.measure(merged_control)
                    # control_measurement = [par_a, par_b, perp_a, perp_b]

                    # Parallel components (c2a, c2b) represent "control present"
                    par_a_weight = control_measurement[0]
                    par_b_weight = control_measurement[1]
                    parallel_prob = probability(par_a_weight) + probability(par_b_weight)

                    # Perpendicular components (c3a, c3b) represent "control absent"
                    perp_a_weight = control_measurement[2]
                    perp_b_weight = control_measurement[3]
                    perpendicular_prob = probability(perp_a_weight) + probability(perp_b_weight)

                    # Check if control is truly superposed (both parallel and perpendicular components exist)
                    control_is_superposed = (enough(parallel_prob, self.control_threshold) and
                                            enough(perpendicular_prob, self.control_threshold))

                    if control_is_superposed:
                        # Create particles for both branches
                        # Parallel branch (control present)
                        if to_float(probability(par_a_weight)) > 0:
                            control_parallel.append(Particle(f'{merged_control.name}>present_a',
                                                            par_a_weight, merged_control.sign,
                                                            precision=self.precision))
                        if to_float(probability(par_b_weight)) > 0:
                            control_parallel.append(Particle(f'{merged_control.name}>present_b',
                                                            par_b_weight, -merged_control.sign,
                                                            precision=self.precision))

                        # Perpendicular branch (control absent)
                        if to_float(probability(perp_a_weight)) > 0:
                            control_perpendicular.append(Particle(f'{merged_control.name}>absent_a',
                                                                 perp_a_weight, merged_control.sign,
                                                                 precision=self.precision))
                        if to_float(probability(perp_b_weight)) > 0:
                            control_perpendicular.append(Particle(f'{merged_control.name}>absent_b',
                                                                 perp_b_weight, -merged_control.sign,
                                                                 precision=self.precision))
                    else:
                        # Not superposed - use binary logic
                        swap = enough(merged_control.probability, self.control_threshold)

                    # Forward control to next stage
                    if destinations['control'] is not None:
                        self.state_dict[destinations['control']] += inputs['control']
                        self.sinks[gate_positions['control']] = Sink(
                            gate_positions['control'],
                            merged_control.pid,
                            presence_threshold=self.presence_threshold,
                            initial_values=inputs['control'], precision=self.precision,
                            combine_signs=combine_signs,
                            combine_names=combine_names)
                else:
                    merged_control = None
                    swap = False
                    control_is_superposed = False

                if normalize_inputs:
                    for wire in SWITCH_WIRES:
                        if inputs[wire]: norm_input_particles(inputs[wire])
                if merge_before_measure:
                    log.info('MERGING INPUTS')
                    for wire in SWITCH_WIRES:
                        inputs[wire] = merge_inputs(inputs[wire])

                ## Log inputs and set up variables for output.
                log.info(f'   INPUTS:')
                if control_is_superposed:
                    log.info(f'      merged control= {merged_control} SUPERPOSED')
                    log.info(f'         parallel (present): prob={parallel_prob:.3f}')
                    log.info(f'         perpendicular (absent): prob={perpendicular_prob:.3f}')
                else:
                    presence_str = 'PRESENT' if (not control_is_superposed and swap) else 'NOT PRESENT'
                    log.info(f'      merged control= {merged_control} {presence_str}')
                for wire in SWITCH_WIRES:
                    log.info(f'      {wire}=   {astr(inputs[wire])}')
```

Then modify the measurement section (lines 168-195) to handle both swap and no-swap branches when control is superposed. This requires processing the switch particles twice - once for each branch.

Actually, this is getting complex. Let me think of a simpler approach...

## Simpler Alternative

Instead of modifying the measurement loop, modify how outputs are routed (lines 199-201). When control is superposed:

1. Keep existing measurement code (it already creates all 4 components)
2. But when routing to output wires, weight the particles by control components:
   - For swap branch: multiply by parallel component weights
   - For no-swap branch: multiply by perpendicular component weights

This way both branches get created with correct weights.

Would this approach work better?