"""
Proposed fix for handling superposed control particles in simulation.py

Key insight: When control is superposed, each switch-wire output particle
needs to be SPLIT into two particles:
1. One going to the "swap" destination (weighted by control's parallel component)
2. One going to the "no-swap" destination (weighted by control's perpendicular component)

This avoids having to process the entire gate twice.
"""

# Add this helper function near the top of simulation.py
from quantish.qnumber import Complex, probability, to_float

def split_by_control(particle, control_parallel_weight, control_perp_weight, swap_dest, noswap_dest):
    """
    Split a switch-wire output particle into swap and no-swap branches based on control superposition.

    Args:
        particle: The output particle from measuring a switch wire
        control_parallel_weight: Complex weight of control's measurement-parallel component
        control_perp_weight: Complex weight of control's measurement-perpendicular component
        swap_dest: Destination if swap occurs
        noswap_dest: Destination if no swap occurs

    Returns:
        List of (destination, weighted_particle) tuples
    """
    results = []

    # Swap branch: multiply particle weight by control's parallel component
    if to_float(probability(control_parallel_weight)) > 0:
        swap_weight = Complex(particle.weight * control_parallel_weight)
        swap_particle = Particle(
            f'{particle.name}[swap]',
            swap_weight,
            particle.sign,
            precision=particle.precision
        )
        results.append((swap_dest, swap_particle))

    # No-swap branch: multiply particle weight by control's perpendicular component
    if to_float(probability(control_perp_weight)) > 0:
        noswap_weight = Complex(particle.weight * control_perp_weight)
        noswap_particle = Particle(
            f'{particle.name}[noswap]',
            noswap_weight,
            particle.sign,
            precision=particle.precision
        )
        results.append((noswap_dest, noswap_particle))

    return results


# Modify the gate processing section around lines 121-204
# Here's the replacement logic:

def process_gate_with_superposed_control(gate, inputs, destinations, ...):
    """
    Process a gate that may have superposed control.
    """

    # Step 1: Measure control particle to determine superposition
    control_parallel_total = Complex(0)
    control_perp_total = Complex(0)
    control_is_superposed = False

    if inputs['control']:
        merged_control = Particle.merge(inputs['control'])

        # Measure control against gate angle
        ctrl_components = gate.measure(merged_control)
        # Returns [par_a, par_b, perp_a, perp_b]

        # Sum parallel components (these contribute to "control present" branch)
        control_parallel_total = Complex(ctrl_components[0] + ctrl_components[1])

        # Sum perpendicular components (these contribute to "control absent" branch)
        control_perp_total = Complex(ctrl_components[2] + ctrl_components[3])

        # Check if both branches have significant weight
        parallel_prob = to_float(probability(control_parallel_total))
        perp_prob = to_float(probability(control_perp_total))

        control_is_superposed = (parallel_prob > control_threshold and
                                perp_prob > control_threshold)

        log.info(f'   Control: parallel_prob={parallel_prob:.3f}, perp_prob={perp_prob:.3f}, superposed={control_is_superposed}')

    # Step 2: Measure switch-wire particles (existing code works fine)
    out_dict = defaultdict(list)
    for input_wire in SWITCH_WIRES:
        for p_in in inputs[input_wire]:
            if to_float(p_in.probability) > 0:
                measurement_results = gate.measure(p_in)
                # ... existing code to create output particles in out_dict ...
                # (This part doesn't change)

    # Step 3: Route outputs based on control state
    outputs = default_switches()

    if control_is_superposed:
        # Route each particle to BOTH swap and no-swap destinations with appropriate weights
        log.info('   CONTROL SUPERPOSED - creating swap and no-swap branches')

        for input_wire in SWITCH_WIRES:
            swap_dest = OTHER[input_wire]
            noswap_dest = input_wire

            # Collect all particles from this input wire
            wire_particles = (out_dict[f'{input_wire}_c2a'] + out_dict[f'{input_wire}_c2b'] +
                            out_dict[f'{input_wire}_c3a'] + out_dict[f'{input_wire}_c3b'])

            for particle in wire_particles:
                # Split this particle into swap and no-swap branches
                branches = split_by_control(
                    particle,
                    control_parallel_total,
                    control_perp_total,
                    swap_dest,
                    noswap_dest
                )

                for dest_wire, weighted_particle in branches:
                    outputs[dest_wire].append(weighted_particle)

    else:
        # Original binary logic for non-superposed control
        swap = merged_control is not None and enough(merged_control.probability, control_threshold)

        if swap:
            log.info('   SWAPPING UPPER<->LOWER')

        for input_wire in SWITCH_WIRES:
            output_wire = OTHER[input_wire] if swap else input_wire
            outputs[output_wire] = (out_dict[f'{input_wire}_c2a'] + out_dict[f'{input_wire}_c2b'] +
                                   out_dict[f'{input_wire}_c3a'] + out_dict[f'{input_wire}_c3b'])

    # Step 4: Forward outputs to next stage (existing code continues...)
    # The rest of the code remains the same

    return outputs


# NOTE: This is pseudocode showing the logic. The actual implementation
# needs to be integrated carefully into the existing simulation.py structure.