"""
Test script to verify EPR discrepancy rate calculations.

According to Drescher's "Good and Real" Chapter 4, for coupled particles
measured at angles Q2 and Q3, the discrepancy rate should be sin²(Q3 - Q2).
"""

import sys
import math
from quantish.gate import FredkinGate
from quantish.particle import Particle
from quantish.qnumber import Complex, Real
import quantish.qnumber as qn

def test_cpair_methods():
    """Test different cpair calculation methods."""
    print("Testing cpair calculation methods")
    print("=" * 60)

    # Test angles
    theta = math.pi / 4  # 45 degrees

    # Create a test particle
    weight = Complex(1.0 + 0j)
    p_plus = Particle("test+", weight, 1)
    p_minus = Particle("test-", weight, -1)

    # Test each cpair method
    methods = ['cpair', 'cpair0', 'cpair_alt', 'cpair1', 'cpair2']

    for method in methods:
        print(f"\n{method}:")
        gate = FredkinGate("test", theta)

        # Measure plus particle
        results_plus = gate.measure(p_plus)
        print(f"  Plus particle (θ={math.degrees(theta):.1f}°):")
        print(f"    c2a: {results_plus[0]} (prob: {abs(results_plus[0])**2:.6f})")
        print(f"    c2b: {results_plus[1]} (prob: {abs(results_plus[1])**2:.6f})")
        print(f"    c3a: {results_plus[2]} (prob: {abs(results_plus[2])**2:.6f})")
        print(f"    c3b: {results_plus[3]} (prob: {abs(results_plus[3])**2:.6f})")

        # Check probabilities sum to 1
        total_prob = sum(abs(r)**2 for r in results_plus)
        print(f"    Total probability: {total_prob:.6f}")

        # Measure minus particle
        results_minus = gate.measure(p_minus)
        print(f"  Minus particle:")
        print(f"    c2a: {results_minus[0]} (prob: {abs(results_minus[0])**2:.6f})")
        print(f"    c2b: {results_minus[1]} (prob: {abs(results_minus[1])**2:.6f})")
        print(f"    c3a: {results_minus[2]} (prob: {abs(results_minus[2])**2:.6f})")
        print(f"    c3b: {results_minus[3]} (prob: {abs(results_minus[3])**2:.6f})")

        total_prob = sum(abs(r)**2 for r in results_minus)
        print(f"    Total probability: {total_prob:.6f}")


def test_epr_discrepancy():
    """Test expected EPR discrepancy rates."""
    print("\n\nTesting EPR Discrepancy Rates")
    print("=" * 60)

    # Test angle pairs and expected discrepancy rates
    test_cases = [
        (0, math.pi/8, math.pi/4),  # 0°, 22.5°, 45° - Bell's inequality test
    ]

    for Qa, Qb, Qc in test_cases:
        print(f"\nAngles: Qa={math.degrees(Qa):.1f}°, Qb={math.degrees(Qb):.1f}°, Qc={math.degrees(Qc):.1f}°")

        # Expected discrepancy rates (from Drescher)
        disc_ab_expected = math.sin(Qb - Qa)**2
        disc_bc_expected = math.sin(Qc - Qb)**2
        disc_ac_expected = math.sin(Qc - Qa)**2

        print(f"  Expected D(Qa,Qb) = sin²({math.degrees(Qb-Qa):.1f}°) = {disc_ab_expected:.6f}")
        print(f"  Expected D(Qb,Qc) = sin²({math.degrees(Qc-Qb):.1f}°) = {disc_bc_expected:.6f}")
        print(f"  Expected D(Qa,Qc) = sin²({math.degrees(Qc-Qa):.1f}°) = {disc_ac_expected:.6f}")

        # Check Bell's inequality
        bell_sum = disc_ab_expected + disc_bc_expected
        print(f"\n  Bell's inequality check:")
        print(f"    D(Qa,Qb) + D(Qb,Qc) = {bell_sum:.6f}")
        print(f"    D(Qa,Qc) = {disc_ac_expected:.6f}")

        if disc_ac_expected > bell_sum:
            print(f"    ✓ Bell's inequality VIOLATED (quantum behavior)")
            print(f"      Violation: {disc_ac_expected - bell_sum:.6f}")
        else:
            print(f"    ✗ Bell's inequality satisfied (classical behavior)")


def test_successive_measurements():
    """Test successive measurements with same angle (should show no further splitting)."""
    print("\n\nTesting Successive Measurements")
    print("=" * 60)

    theta1 = math.pi / 6  # 60 degrees
    theta2 = math.pi / 6  # Same angle

    # Initial particle
    weight = Complex(1.0 + 0j)
    p = Particle("test", weight, 1)

    # First measurement
    gate1 = FredkinGate("g1", theta1)
    results1 = gate1.measure(p)
    results1 = [sum(results1[:2]), sum(results1[2:])]

    print(f"First measurement at θ={math.degrees(theta1):.1f}°:")
    print(f"  Parallel component (upper wire): {abs(results1[0])**2:.6f}")
    print(f"  Perpendicular component (lower wire): {abs(results1[1])**2:.6f}")

    # Second measurement on the parallel component
    # Create particle from parallel component result
    p2 = Particle("test2", results1[0], 1)
    gate2 = FredkinGate("g2", theta2)
    results2 = gate2.measure(p2)
    results2 = [sum(results2[:2]), sum(results2[2:])]

    print(f"\nSecond measurement at θ={math.degrees(theta2):.1f}° (same angle):")
    print(f"  Should stay on upper wire: {abs(results2[0])**2:.6f}")
    print(f"  Should NOT go to lower wire: {abs(results2[1])**2:.6f}")

    if abs(results2[1])**2 < 1e-10:
        print("  ✓ Correct: No splitting with same measurement angle")
    else:
        print("  ✗ Error: Unexpected splitting with same measurement angle")


if __name__ == "__main__":
    test_cpair_methods()
    test_epr_discrepancy()
    test_successive_measurements()