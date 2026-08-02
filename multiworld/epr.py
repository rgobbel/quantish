"""EPR outcome conventions, following quantish_gld/epr_bell.py.

The intrinsic discrepancy law for the fig 4.16/4.17 family, conditioned on
p3 exiting its coupling gate on the upper wire:

    one-stage (g5/g6 only):   sin²(Q5 + Q6)
    two-stage (adds g7/g8):   sin²((Q5 + Q6) − (Q7 + Q8))

The measurement outcome is NOT plain position for one-stage circuits: an
angle-0 gate routes a PLUS particle straight and a MINUS particle across
(it is a sign sorter, not the identity), so the one-stage outcome is
position⊕sign — what a final sorting stage would turn into pure position.
The second stage of fig 4.17 plays exactly that role, which is why plain
position is the outcome there.
"""


def is_two_stage(sim) -> bool:
    return 'g7' in sim.gates.keys() and 'g8' in sim.gates.keys()


def expected_discrepancy(sim):
    """The intrinsic sin²-law discrepancy for the sim's gate angles, or
    None when the circuit lacks the EPR structure (g5/g6)."""
    if 'g5' not in sim.gates.keys() or 'g6' not in sim.gates.keys():
        return None
    total = sim.gates['g5'].theta + sim.gates['g6'].theta
    if is_two_stage(sim):
        total = total - (sim.gates['g7'].theta + sim.gates['g8'].theta)
    return total.sin ** 2


def outcome(coord, two_stage: bool) -> str:
    """Measurement outcome for one particle's final coordinate: plain
    position ('upper'/'lower') after a second measurement stage,
    position⊕sign after one."""
    side = coord.position.origin.port
    if not two_stage and int(coord.sign) < 0:
        side = 'lower' if side == 'upper' else 'upper'
    return side


def classify(point, two_stage: bool) -> str:
    """'same' / 'diff' (p1's and p2's outcomes agree / disagree) for worlds
    where p3 exited on the upper wire, else 'uncoupled'."""
    coords = list(point.coords.values())
    if len(coords) < 3:
        return 'uncoupled'
    p1c, p2c, p3c = coords[:3]
    origin = p3c.position.origin
    if origin is None or origin.port != 'upper':
        return 'uncoupled'
    if outcome(p1c, two_stage) == outcome(p2c, two_stage):
        return 'same'
    return 'diff'