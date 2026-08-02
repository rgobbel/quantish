"""
circuit_diagram.py — TikZ topology renderer for Quantish circuits.

Ported from quantish_gld/circuits_diagram.py; the layout, routing, TikZ
emission, and compile pipeline are kept close to the original so future
improvements can be merged in either direction. The quantish_gld Circuit
input type is replaced by DiagramSpec, built from a multiworld Simulation
by spec_from_simulation().

Pipeline:
    Simulation → DiagramSpec → .tex (this module) → pdflatex → PDF → PIL.Image

Cached PNGs live in ~/.cache/quantish/diagrams/, keyed by a hash of the
circuit's topology and angles. Cache hits skip the LaTeX compile entirely.

Public API:
    spec_from_simulation(sim, fig=...) -> DiagramSpec
    render_diagram(spec, dpi=150) -> PIL.Image | None
    render_diagram_to_file(spec, out_path) -> bool   (.pdf/.svg/.png by extension)
    render_from_simulation(sim, out_path) -> bool    (one-call convenience)
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from multiworld.util import SEP, WIRES


# --------------------------------------------------------------------------
# Input shim: the structure the renderer reads, built from a Simulation.
# --------------------------------------------------------------------------

@dataclass
class ParsedShim:
    """The subset of quantish_gld's ParsedYaml that the renderer consumes."""
    gates: dict                 # name -> {'angle': display-string}
    delay_gates: list           # names
    particles: dict             # name -> anything; insertion order = layout order
    links: dict                 # source -> dest ('gate.port' or bare names)
    stage_gates: list           # list of lists of gate names (row grouping)
    stage_names: list           # labels parallel to stage_gates


@dataclass
class DiagramSpec:
    """Renderer input: topology dict in the quantish_gld Circuit shape."""
    fig: str
    title: str
    topology: dict              # {'parsed': ParsedShim, 'topo': {...}, 'engine_steps': [...]}


def spec_from_simulation(sim, fig: str = None) -> DiagramSpec:
    """Build a DiagramSpec from a multiworld Simulation.

    Columns (engine steps) are the topological generations of the simplified
    link graph — gates with no dependency between them share a column. Row
    grouping and stage labels come from sim.diagram_groups.
    """
    config = sim.config
    links = dict(sim.links)
    delay_names = list(sim.delay_gates.keys())
    gates = {gname: {'angle': str(config.gates[gname].angle)}
             for gname in sim.fredkin_gates.keys()}
    particles = {pname: {} for pname in sim.particles.keys()}

    # Wire naming mirrors quantish_gld's resolve_topology: every wire is named
    # for the port that emits onto it; a linked destination shares that name.
    gate_inputs = {g: {port: f'{g}_{port}_in' for port in WIRES} for g in gates}
    gate_outputs = {g: {port: f'{g}_{port}_out' for port in WIRES} for g in gates}
    delay_in = {d: f'{d}_in' for d in delay_names}
    delay_out = {d: f'{d}_out' for d in delay_names}

    def out_wire(src: str) -> str | None:
        if SEP in src:
            g, port = src.split(SEP, 1)
            return gate_outputs[g][port]
        if src in delay_out:
            return delay_out[src]
        return None

    def set_in_wire(dst: str, wire: str) -> None:
        if SEP in dst:
            g, port = dst.split(SEP, 1)
            gate_inputs[g][port] = wire
        elif dst in delay_in:
            delay_in[dst] = wire

    def in_wire(dst: str) -> str:
        if SEP in dst:
            g, port = dst.split(SEP, 1)
            return gate_inputs[g][port]
        return delay_in.get(dst, dst)

    particle_starts = {}
    for src, dst in links.items():
        if src in particles:
            particle_starts[src] = (in_wire(dst), int(sim.particles[src].sign))
            continue
        wire = out_wire(src)
        if wire is not None:
            set_in_wire(dst, wire)

    # Particle links stay in `links` for routing; the renderer draws them
    # from the particle circle to the destination port.
    # Groups (from diagram_groups) mark gates with similar function; each
    # group spans one or more columns. Independent gates in a group stack
    # vertically in one column; a gate that depends on another gate of the
    # same group goes in a later sub-column, side by side, so links never
    # have to run backwards. The group box (drawn in emit_tex) spans
    # whatever columns the group's gates occupy.
    stage_names = list(sim.diagram_groups.keys())
    stage_gates = [list(group) for group in sim.diagram_groups.values()]
    gate_deps = {}
    for gname in list(gates) + delay_names:
        if gname in sim.simplified_links:
            gate_deps[gname] = {p for p in sim.simplified_links.predecessors(gname)
                                if p in gates or p in delay_names}
        else:
            gate_deps[gname] = set()
    engine_steps = []
    fired = set()
    for group in stage_gates:
        remaining = list(group)
        while remaining:
            ready = [g for g in remaining if not (gate_deps.get(g, set()) - fired)]
            if not ready:
                # a gate depends on something in a *later* group; don't stall
                ready = list(remaining)
            engine_steps.append(ready)
            fired.update(ready)
            remaining = [g for g in remaining if g not in ready]

    return DiagramSpec(
        fig=fig or sim.title,
        title=sim.title,
        topology={
            'parsed': ParsedShim(gates=gates, delay_gates=delay_names,
                                 particles=particles, links=links,
                                 stage_gates=stage_gates, stage_names=stage_names),
            'topo': {
                'gate_inputs': gate_inputs,
                'gate_outputs': gate_outputs,
                'delay_in': delay_in,
                'delay_out': delay_out,
                'particle_starts': particle_starts,
            },
            'engine_steps': engine_steps,
        },
    )


# Alias so the renderer code below (ported verbatim where possible) reads
# the same as the quantish_gld original.
Circuit = DiagramSpec


# --------------------------------------------------------------------------
# Layout: pixels-on-paper coordinates derived from the parsed YAML.
# --------------------------------------------------------------------------

# All distances are in TikZ "cm" units. 1 cm ≈ 28pt.
GATE_WIDTH        = 4.2     # outer frame width
GATE_HEIGHT       = 2.4     # outer frame height
STAGE_WIDTH       = 6.0     # horizontal distance between stage column origins
GATE_VSPACE       = 1.0     # vertical gap between gates in the same stage
DELAY_HEIGHT      = 0.7
DELAY_VSPACE      = 0.5
PARTICLE_OFFSET_X = -1.8    # particle column relative to stage 1's gate left edge
# The control port is a single centered box (the control wire just passes
# through). Its half-width determines where the left/right edges sit
# relative to the gate's horizontal center.
CONTROL_HALF_W = 0.7

# Port-row y-offsets, measured from the gate's *top* (north anchor):
PORT_DY = {
    'control': -0.95,
    'upper':   -1.45,
    'lower':   -1.95,
}

# X-offsets (relative to a gate's north-west) of the *outer* edge of the
# input/output port boxes — where external wires should terminate.
PORT_IN_DX  = 0.15
PORT_OUT_DX = GATE_WIDTH - 0.15

# Group-box geometry (shared by emit_tex and the wire router so wires keep
# clear of the drawn borders): padding around the member gates, the header
# band that holds the group title, and the clearance wires must keep from
# any box border.
GROUP_PAD    = 0.28
GROUP_HEADER = 0.5
BOX_CLEAR    = 0.3



@dataclass
class Layout:
    """Final coordinates for every node + computed routing helpers."""
    gate_xy:        dict[str, tuple[float, float]] = field(default_factory=dict)   # top-left
    delay_xy:       dict[str, tuple[float, float]] = field(default_factory=dict)
    particle_xy:    dict[str, tuple[float, float]] = field(default_factory=dict)   # center
    bounds:         tuple[float, float, float, float] = (0, 0, 0, 0)               # x_min,y_min,x_max,y_max
    col_of:         dict[str, int] = field(default_factory=dict)                   # gate/delay → engine-step column
    stage_label_x:  list[tuple[float, float, str]] = field(default_factory=list)   # (x_left, x_right, label) per execution stage
    stage_label_y:  float = 0.0

def total_height(circuit: Circuit):
    parsed = circuit.topology['parsed']
    max_height = 0
    for stage in parsed.stage_gates:
        cur_height = 0
        for gate in stage:
            if gate in parsed.gates.keys():
                cur_height += GATE_HEIGHT + GATE_VSPACE
            cur_height -= GATE_VSPACE
        if len(parsed.delay_gates) >= 0:
            cur_height += DELAY_VSPACE
            for gate in stage:
                if gate in parsed.delay_gates:
                    cur_height += DELAY_HEIGHT + DELAY_VSPACE
            cur_height -= DELAY_VSPACE
        max_height = max(max_height, cur_height)
    return max_height

def compute_layout(circuit: Circuit) -> Layout:
    """Lay out gates by engine-step (one column per parallel-firing group).

    Stages from the YAML are *grouping* primitives: their gates may span
    several engine steps when there are intra-stage dependencies (e.g. fig
    4.16's 'couple' stage has g3 and g4 in separate engine steps because g4
    depends on g3). Stage labels span the columns their gates occupy.
    """
    parsed = circuit.topology['parsed']
    topo = circuit.topology['topo']
    engine_steps = circuit.topology['engine_steps']
    delays = set(parsed.delay_gates)
    L = Layout()

    # Pass 1: column = engine-step index. Each gate goes in the column corresponding to its execution stage.
    for col, names in enumerate(engine_steps):
        for name in names:
            L.col_of[name] = col

    # Pass 2: vertical position. Each gate sits at the y assigned to its
    # execution stage row, *consistent across all columns*. So a column with only
    # the row-0 gate puts that gate at the same y as a fully-populated
    # column's row-0 gate, and the ports line up across columns.
    max_rows = max((len(s) for s in parsed.stage_gates), default=0) or 1
    # Compute the y for each row index. Rows 0..max_rows-1 stack top-to-bottom
    # centered around y=0. Use the gate height + vspacing as the row stride.
    row_stride = GATE_HEIGHT + GATE_VSPACE
    delay_stride = DELAY_HEIGHT + DELAY_VSPACE
    row_ys0 = []
    # total_h = max_rows * GATE_HEIGHT + (max_rows - 1) * GATE_VSPACE
    total_h = total_height(circuit)
    top = total_h / 2.0
    for r in range(max_rows):
        row_ys0.append(top - r * row_stride)

    for col, names in enumerate(engine_steps):
        x = col * STAGE_WIDTH
        row_ys = stage_ys(parsed, names, top, row_stride, delay_stride)
        for row_y, name in zip(row_ys, names):
            iy = stage_row(parsed, name)
            y0 = row_ys0[iy] if iy < len(row_ys0) else row_ys0[-1]
            h = height(parsed, name)
            if name in delays:
                L.delay_xy[name] = (x + GATE_WIDTH/2, row_y - h / 2)
            else:
                L.gate_xy[name] = (x, row_y)

    # Pass 3: particles. Place them top-to-bottom in execution order, spread evenly
    # across the *full* vertical extent of the diagram (topmost-gate-top to
    # bottommost-gate-bottom across all columns). With more vertical room
    # particles cascade more cleanly and circles can't visually overlap.
    n_particles = len(parsed.particles)
    if n_particles > 0:
        if L.gate_xy:
            top_y = max(y for _, y in L.gate_xy.values())
            bottom_y = min(y - GATE_HEIGHT for _, y in L.gate_xy.values())
        else:
            top_y, bottom_y = 1.5, -1.5
        if n_particles == 1:
            ys = [(top_y + bottom_y) / 2]
        else:
            step = (top_y - bottom_y) / (n_particles - 1)
            # Ensure a minimum gap of 1.0 cm so circles never overlap.
            min_gap = 1.0
            if step < min_gap:
                center = (top_y + bottom_y) / 2
                step = min_gap
                ys = [center + (n_particles - 1) / 2 * step - i * step for i in range(n_particles)]
            else:
                ys = [top_y - i * step for i in range(n_particles)]
        # Insertion order of parsed.particles is the execution order.
        for i, pname in enumerate(parsed.particles):
            L.particle_xy[pname] = (PARTICLE_OFFSET_X, ys[i])

    # Stage labels: one per execution stage, spanning the columns its gates occupy.
    if parsed.stage_names:
        col_xs = []
        for s_idx, stage in enumerate(parsed.stage_gates):
            cols = sorted({L.col_of[n] for n in stage if n in L.col_of})
            if not cols:
                continue
            x_left = cols[0] * STAGE_WIDTH
            x_right = cols[-1] * STAGE_WIDTH + GATE_WIDTH
            col_xs.append((x_left, x_right, parsed.stage_names[s_idx]))
        L.stage_label_x = col_xs
        # y above the topmost gate.
        if L.gate_xy:
            topmost = max(y for _, y in L.gate_xy.values())
            L.stage_label_y = topmost + 0.7

    # Bounding box.
    xs = [PARTICLE_OFFSET_X - 0.5]
    ys = [0.0]
    for x, y in L.gate_xy.values():
        xs.extend([x, x + GATE_WIDTH]); ys.extend([y, y - GATE_HEIGHT])
    for x, y in L.delay_xy.values():
        xs.extend([x, x + CONTROL_HALF_W]); ys.extend([y - DELAY_HEIGHT, y + DELAY_HEIGHT])
    for x, y in L.particle_xy.values():
        xs.extend([x - 0.4, x + 0.4]); ys.extend([y - 0.4, y + 0.4])
    # Reserve room above for the stage label band.
    ys.append(L.stage_label_y + 0.5)
    if xs:
        L.bounds = (min(xs), min(ys), max(xs), max(ys))
    return L

def group_boxes(parsed, L: Layout) -> list[dict]:
    """Geometry of every group adornment, shared by the TikZ emitter and the
    wire router. Returns one dict per group with member coordinates:
    x1/x2 (left/right), y_top (border incl. header), y_bot, label, and
    multi (True when a box is actually drawn, False for a bare label)."""
    result = []
    for group, label in zip(parsed.stage_gates, parsed.stage_names):
        member_boxes = []
        for name in group:
            if name in L.gate_xy:
                x, y = L.gate_xy[name]
                member_boxes.append((x, y, x + GATE_WIDTH, y - GATE_HEIGHT))
            elif name in L.delay_xy:
                cx, cy = L.delay_xy[name]
                member_boxes.append((cx - CONTROL_HALF_W, cy + DELAY_HEIGHT / 2,
                                     cx + CONTROL_HALF_W, cy - DELAY_HEIGHT / 2))
        if not member_boxes:
            continue
        x1 = min(b[0] for b in member_boxes)
        y_gate_top = max(b[1] for b in member_boxes)
        x2 = max(b[2] for b in member_boxes)
        y_bot = min(b[3] for b in member_boxes)
        multi = len(member_boxes) > 1
        result.append({
            'x1': x1 - GROUP_PAD if multi else x1,
            'x2': x2 + GROUP_PAD if multi else x2,
            'y_top': (y_gate_top + GROUP_PAD + GROUP_HEADER) if multi else (y_gate_top + 0.45),
            'y_bot': (y_bot - GROUP_PAD) if multi else y_bot,
            'y_gate_top': y_gate_top,
            'label': label,
            'multi': multi,
        })
    return result


def stage_row(parsed, name: str) -> int:
    """Return the row index of `name` within its execution stage (0 if not found)."""
    for stage in parsed.stage_gates:
        for i, n in enumerate(stage):
            if n == name:
                return i
    return 0

def stage_ys(parsed, stage_gates, top,  gate_stride, delay_stride) -> list[float]:
    ys = [top]
    for name in stage_gates:
        if name in parsed.delay_gates:
            ys.append(ys[-1] - delay_stride)
        else:
            ys.append(ys[-1] - gate_stride)
    if stage_gates[-1] in parsed.delay_gates:
        ys[-1] -= DELAY_VSPACE
    else:
        ys[-1] -= GATE_VSPACE
    return ys

def height(parsed, name: str) -> float:
    return DELAY_HEIGHT if name in parsed.delay_gates else GATE_HEIGHT

def vspace(parsed, name: str) -> float:
    return DELAY_VSPACE if name in parsed.delay_gates else GATE_VSPACE

def vspace_for_stack(parsed, names: list[str]) -> float:
    if len(names) <= 1:
        return 0
    return sum(vspace(parsed, n) for n in names[:-1])


# --------------------------------------------------------------------------
# Wire endpoint resolution
# --------------------------------------------------------------------------

def port_xy(L: Layout, gate_name: str, port: str, side: str) -> tuple[float, float]:
    """Coordinates of a port on a Fredkin gate or a delay's in/out point.

    For Fredkin gates, the returned point is the *outer* edge of the port box
    where external wires terminate. The control port is a single centered
    box (the wire passes through), so the in-side is its left edge and the
    out-side is its right edge — both at the gate's horizontal center ±
    CONTROL_HALF_W. Switch ports (upper/lower) have separate in/out columns
    at the gate's left/right edges.
    """
    if gate_name in L.delay_xy:
        cx, cy = L.delay_xy[gate_name]
        return (cx - CONTROL_HALF_W, cy) if side == 'in' else (cx + CONTROL_HALF_W, cy)
    x, y = L.gate_xy[gate_name]
    dy = PORT_DY[port]
    if port == 'control':
        cx = x + GATE_WIDTH / 2
        edge_x = cx - CONTROL_HALF_W if side == 'in' else cx + CONTROL_HALF_W
    else:
        edge_x = x + PORT_IN_DX if side == 'in' else x + PORT_OUT_DX
    return (edge_x, y + dy)

def wire_endpoint(circuit: Circuit, L: Layout, wire_name: str, side: str) -> tuple[float, float] | None:
    """Find the (x, y) where a wire enters or exits its node."""
    topo = circuit.topology['topo']
    if side == 'in':
        # Search gate inputs and delay inputs.
        for gname, ports in topo['gate_inputs'].items():
            for port, w in ports.items():
                if w == wire_name:
                    return port_xy(L, gname, port, 'in')
        for dname, w in topo['delay_in'].items():
            if w == wire_name:
                return port_xy(L, dname, '_delay', 'in')
    else:  # out
        for gname, ports in topo['gate_outputs'].items():
            for port, w in ports.items():
                if w == wire_name:
                    return port_xy(L, gname, port, 'out')
        for dname, w in topo['delay_out'].items():
            if w == wire_name:
                return port_xy(L, dname, '_delay', 'out')
    return None


def wire_endpoint_y(circuit: Circuit, L: Layout, wire_name: str, side: str) -> float:
    end = wire_endpoint(circuit, L, wire_name, side)
    return end[1] if end else 0.0


# --------------------------------------------------------------------------
# Wire routing — picks vertical channels in each inter-stage gap.
# --------------------------------------------------------------------------

@dataclass
class Route:
    """A single wire's polyline path: list of (x, y) waypoints."""
    points: list[tuple[float, float]] = field(default_factory=list)


def route_wires(circuit: Circuit, L: Layout) -> list[Route]:
    """Compute polyline paths for every link.

    Algorithm:
      1. Compute each gate/delay's bounding box (the visual obstacle).
      2. For each link, try a "minimal" route:
           - Straight horizontal if sy == dy and the path from sx to dx
             is unobstructed.
           - Two-step (out, vertical, in) at a channel x in some gap, if
             at the chosen y values both horizontals are unobstructed.
      3. If neither minimal route works, detour through a *local* lane just
         above or below the blocking gate(s), staying close to the action.
      4. Channel-x and lane-y are allocated to avoid colliding with other
         wires already routed. We track 'used' (x, y_range) intervals per
         gap, and 'used' (y, x_range) intervals per lane.
    """
    parsed = circuit.topology['parsed']
    routes: list[Route] = []
    particles = set(parsed.particles)
    delays = set(parsed.delay_gates)
    n_cols = len(circuit.topology['engine_steps'])
    boxes_geom = group_boxes(parsed, L)

    # Build the obstacle list: name → (x_left, y_top, x_right, y_bottom).
    # Tests can exclude the source/destination gates from the check (since a
    # wire at a port y is *visually* outside its own gate's body).
    obstacles: dict[str, tuple[float, float, float, float]] = {}
    for name, (x, y) in L.gate_xy.items():
        obstacles[name] = (x, y, x + GATE_WIDTH, y - GATE_HEIGHT)
    for name, (cx, cy) in L.delay_xy.items():
        obstacles[name] = (cx + GATE_WIDTH/2 - CONTROL_HALF_W, cy + DELAY_HEIGHT / 2,
                           cx + GATE_WIDTH/2 + CONTROL_HALF_W, cy - DELAY_HEIGHT / 2)

    def hit_horizontal(y: float, x1: float, x2: float,
                       exclude: set[str] = frozenset(),
                       ignore_pad: float = 0.05) -> bool:
        """Does the open horizontal segment at y from x1 to x2 cross any gate
        not listed in `exclude`?"""
        lo, hi = min(x1, x2), max(x1, x2)
        for name, (ox1, oy1, ox2, oy2) in obstacles.items():
            if name in exclude:
                continue
            if not (oy2 - ignore_pad < y < oy1 + ignore_pad):
                continue
            if ox2 < lo + ignore_pad or ox1 > hi - ignore_pad:
                continue
            return True
        return False

    def hit_vertical(x: float, y1: float, y2: float,
                     exclude: set[str] = frozenset(),
                     ignore_pad: float = 0.05) -> bool:
        lo, hi = min(y1, y2), max(y1, y2)
        for name, (ox1, oy1, ox2, oy2) in obstacles.items():
            if name in exclude:
                continue
            if not (ox1 - ignore_pad < x < ox2 + ignore_pad):
                continue
            if oy1 < lo + ignore_pad or oy2 > hi - ignore_pad:
                continue
            return True
        return False

    def endpoint_gate(s: str) -> str | None:
        """Gate name of a link endpoint (or None for particles/bare names)."""
        if '.' in s:
            return s.split('.', 1)[0]
        if s in delays:
            return s
        return None

    # Channels must clear not just the gates but the group-box borders
    # (which protrude GROUP_PAD beyond the gates), with BOX_CLEAR to spare.
    _GAP_MARGIN = GROUP_PAD + BOX_CLEAR

    def gap_x_range(gap: int) -> tuple[float, float]:
        if gap < 0:
            # Particle corridor: start past the right edge of the particle
            # circles (centers at PARTICLE_OFFSET_X, radius ~0.4) with extra
            # clearance so a vertical channel doesn't graze a particle, and
            # end clear of the first column's group-box border.
            return (PARTICLE_OFFSET_X + 0.55, -_GAP_MARGIN)
        gate_right = gap * STAGE_WIDTH + GATE_WIDTH
        next_left = (gap + 1) * STAGE_WIDTH
        return (gate_right + _GAP_MARGIN, next_left - _GAP_MARGIN)

    # Track per-gap channel (vertical-segment) allocations: list of
    # (x, y_low, y_high). When picking a new channel, we prefer one that
    # doesn't overlap any existing wire's vertical segment.
    gap_channels_used: dict[int, list[tuple[float, float, float]]] = {}

    # Track horizontal segments globally: list of (y, x_lo, x_hi). Used to
    # avoid placing a new horizontal at the same y on top of an existing one
    # over the same x-range. Two horizontals at the same y but disjoint x
    # are fine (they look like two separate strokes on the same baseline).
    horizontal_segments: list[tuple[float, float, float]] = []

    def add_horizontal(y: float, x_lo: float, x_hi: float) -> None:
        if x_hi > x_lo + 0.02:
            horizontal_segments.append((y, min(x_lo, x_hi), max(x_lo, x_hi)))

    def horizontal_blocked(y: float, x_lo: float, x_hi: float) -> tuple[float, float] | None:
        """If a horizontal at y overlapping [x_lo, x_hi] is already in use,
        return the (x_lo, x_hi) of the conflicting segment."""
        lo, hi = min(x_lo, x_hi), max(x_lo, x_hi)
        for sy, sx_lo, sx_hi in horizontal_segments:
            if abs(sy - y) > 0.15:
                continue
            if sx_hi < lo + 0.05 or sx_lo > hi - 0.05:
                continue
            return (sx_lo, sx_hi)
        return None

    # Minimum visual separation between two channels in the same gap.
    _CHANNEL_MIN_GAP = 0.30

    def alloc_channel(gap: int, y_low: float, y_high: float,
                      stub_y: float | None = None,
                      stub_to: float | None = None,
                      spread: bool = False) -> float:
        """Pick a channel x in `gap` whose vertical span doesn't overlap any
        already-allocated channel whose y-span overlaps ours.

        Optionally `stub_y` + `stub_to` describe an out-from-channel horizontal
        stub at y=stub_y running from cx to stub_to. We avoid choosing a cx
        that places the stub on top of an existing horizontal segment.

        When `spread=True`, also keep _CHANNEL_MIN_GAP distance from *every*
        already-allocated x in this gap, regardless of y overlap. This is
        used in the particle corridor so successive particle wires fan out
        in a cascade rather than stacking on the leftmost slot.

        Strategy:
          1. Build the set of x's whose verticals would conflict (overlapping
             y-ranges).
          2. Sample candidates densely across the gap; for each, also check
             that any required stub horizontal isn't shadowed by an existing
             one. Accept the first that passes.
          3. As a last resort, accept whatever's furthest from vertical conflicts.
        """
        x_lo, x_hi = gap_x_range(gap)
        used = gap_channels_used.setdefault(gap, [])
        conflicts = [
            ux for ux, uy_lo, uy_hi in used
            if not (y_high < uy_lo - 0.05 or y_low > uy_hi + 0.05)
        ]
        # When spreading, every prior x acts as a soft-conflict for proximity.
        proximity_xs = [ux for ux, _, _ in used] if spread else conflicts

        n = 32
        candidates = [x_lo + (x_hi - x_lo) * (i + 0.5) / n for i in range(n)]
        # In spread mode candidates are walked left-to-right, so the
        # first-routed wires (nearest destinations, routed first by the
        # flexibility sort) take the leftmost slots. Later wires — the ones
        # headed farthest right — get larger x's, so their long horizontal
        # runs start to the right of every earlier-routed vertical and
        # never cross one.

        def stub_ok(cx: float) -> bool:
            if stub_y is None or stub_to is None:
                return True
            blk = horizontal_blocked(stub_y, cx, stub_to)
            return blk is None

        for cx in candidates:
            if not all(abs(cx - cf) >= _CHANNEL_MIN_GAP for cf in proximity_xs):
                continue
            if not stub_ok(cx):
                continue
            used.append((cx, y_low, y_high))
            return cx
        # Relaxation 1: drop the stub-clearance constraint, keep min-gap.
        for cx in candidates:
            if all(abs(cx - cf) >= _CHANNEL_MIN_GAP for cf in proximity_xs):
                used.append((cx, y_low, y_high))
                return cx
        # Relaxation 2: drop spread, keep y-conflict avoidance.
        if spread:
            for cx in candidates:
                if all(abs(cx - cf) >= _CHANNEL_MIN_GAP for cf in conflicts):
                    used.append((cx, y_low, y_high))
                    return cx
        # Last-resort: max distance from conflicts.
        best = max(candidates, key=lambda cx: min((abs(cx - cf) for cf in conflicts), default=10))
        used.append((best, y_low, y_high))
        return best

    # Track per-lane usage. The below-base clears group-box bottoms, which
    # protrude GROUP_PAD beyond the lowest gate.
    lane_above_base = L.bounds[3] + 0.4
    lane_below_base = L.bounds[1] - 0.4 - GROUP_PAD
    lanes_above: list[tuple[float, float, float]] = []   # (y, x_lo, x_hi)
    lanes_below: list[tuple[float, float, float]] = []

    # Vertical spacing between successive lane rows when they have to stack.
    _LANE_STEP = 0.55

    def alloc_lane(prefer_below: bool, x_lo: float, x_hi: float) -> float:
        used = lanes_below if prefer_below else lanes_above
        for ly, lx_lo, lx_hi in used:
            if x_hi < lx_lo - 0.1 or x_lo > lx_hi + 0.1:
                # Disjoint in x: we can share this lane.
                used.append((ly, min(x_lo, lx_lo), max(x_hi, lx_hi)))
                return ly
        # Need a new lane row.
        offset = _LANE_STEP * len(used)
        ly = (lane_below_base - offset) if prefer_below else (lane_above_base + offset)
        used.append((ly, x_lo, x_hi))
        return ly

    # Sort links by routing flexibility: short adjacent links first (fewer
    # routing alternatives), then longer skips. Within each tier, preserve
    # execution order. This ensures constrained wires claim their gap-0 channels
    # before flexible ones grab the same x-band for their endpoint stubs.
    def flexibility_key(link):
        src, dst = link
        s_xy = src_xy(circuit, L, src, particles, delays)
        d_xy, d_col = dst_xy_col(circuit, L, dst, delays)
        s_col = col_of_src(L, src, particles, delays)
        if s_xy is None or d_xy is None or s_col is None or d_col is None:
            return 999
        return d_col - s_col   # smaller = more constrained

    sorted_links = sorted(parsed.links.items(), key=flexibility_key)

    for src, dst in sorted_links:
        s_xy = src_xy(circuit, L, src, particles, delays)
        d_xy, d_col = dst_xy_col(circuit, L, dst, delays)
        if s_xy is None or d_xy is None:
            continue
        s_col = col_of_src(L, src, particles, delays)
        sx, sy = s_xy; dx, dy = d_xy

        # Exclude source and destination gates from obstacle checks for this
        # wire (a port-edge wire is "outside" its own gate visually).
        skip_set = {g for g in (endpoint_gate(src), endpoint_gate(dst)) if g}

        # ---- Try straight horizontal. ----
        if (abs(sy - dy) < 0.05 and dx > sx
                and not hit_horizontal(sy, sx + 0.01, dx - 0.01, exclude=skip_set)
                and horizontal_blocked(sy, sx, dx) is None):
            routes.append(Route([(sx, sy), (dx, dy)]))
            add_horizontal(sy, sx, dx)
            continue

        # ---- Try a two-step route (out, vertical channel, in). ----
        # Need a gap where: src right edge ≤ gap_x ≤ dst left edge, and
        # both horizontals at sy and dy don't hit any gate, and the vertical
        # at the chosen cx doesn't hit any gate.
        two_step = None
        # Candidate gap is the gap whose x-range contains an x in (sx, dx).
        # Try every gap from src_col to d_col-1.
        candidate_gaps = []
        if s_col is not None and d_col is not None:
            start = max(-1, s_col)
            for g in range(start, d_col):
                candidate_gaps.append(g)
        for gap in candidate_gaps:
            x_lo, x_hi = gap_x_range(gap)
            if x_lo > dx - 0.2 or x_hi < sx + 0.2:
                continue
            # Confirm horizontal at sy from sx to channel-region start
            # and at dy from channel-region end to dx are unobstructed.
            if hit_horizontal(sy, sx + 0.02, x_lo + 0.05, exclude=skip_set):
                continue
            if hit_horizontal(dy, x_hi - 0.05, dx - 0.02, exclude=skip_set):
                continue
            # Pick a channel x. Try multiple candidate x's within this gap,
            # not just the first that alloc_channel returns; we need each
            # corner stub to clear gates AND already-routed horizontals.
            y_lo, y_hi = min(sy, dy), max(sy, dy)
            picked_cx = None
            tried = []
            for _attempt in range(8):
                # In the particle corridor (gap == -1), spread successive
                # particle wires so they cascade rather than stack on the
                # leftmost slot.
                cx = alloc_channel(gap, y_lo, y_hi, stub_y=dy, stub_to=dx,
                                   spread=(gap == -1))
                tried.append(cx)
                # Validate against gates and horizontal stubs.
                bad = (hit_horizontal(sy, sx + 0.02, cx, exclude=skip_set)
                       or hit_horizontal(dy, cx, dx - 0.02, exclude=skip_set)
                       or hit_vertical(cx, y_lo + 0.02, y_hi - 0.02, exclude=skip_set)
                       or horizontal_blocked(sy, sx, cx) is not None
                       or horizontal_blocked(dy, cx, dx) is not None)
                if not bad:
                    picked_cx = cx
                    break
                # Pop the failed allocation so the next attempt sees fresh state,
                # but treat it as a forbidden x by re-recording with infinite span
                # (forces alloc_channel to pick something else).
                gap_channels_used[gap].pop()
                # Instead of permanently blocking, just record the conflict and
                # ask alloc_channel to try the *next* candidate. We do this by
                # adding a fake conflict at the just-tried cx.
                gap_channels_used[gap].append((cx, -1e9, 1e9))
            # Clean up fake conflicts we added.
            for tcx in tried:
                if picked_cx is None or tcx != picked_cx:
                    # Remove the corresponding fake entry (last matching).
                    for i in range(len(gap_channels_used[gap]) - 1, -1, -1):
                        if (abs(gap_channels_used[gap][i][0] - tcx) < 1e-6
                                and gap_channels_used[gap][i][1] == -1e9):
                            gap_channels_used[gap].pop(i)
                            break
            if picked_cx is None:
                continue
            two_step = [(sx, sy), (picked_cx, sy), (picked_cx, dy), (dx, dy)]
            break

        if two_step is not None:
            routes.append(Route(two_step))
            # Record both stubs as occupied horizontals.
            add_horizontal(sy, sx, two_step[1][0])
            add_horizontal(dy, two_step[2][0], dx)
            continue

        # ---- Detour through a *local* lane. ----
        # Pick a lane y first (a y-coord just above/below blockers between
        # source and destination), then allocate channels at the proper x's
        # using the actual y-spans the wire will occupy. This way the
        # collision check sees the real span, not a placeholder.
        src_gap = max(-1, s_col if s_col is not None else 0)
        dst_gap = max(-1, (d_col - 1) if d_col is not None else 0)
        # Approximate the channels' x's so we can find blockers between them.
        approx_cx_lo, approx_cx_hi = gap_x_range(src_gap)
        approx_dx_lo, approx_dx_hi = gap_x_range(dst_gap)
        x_span_lo = min(approx_cx_lo, approx_dx_lo)
        x_span_hi = max(approx_cx_hi, approx_dx_hi)

        blockers = []
        for name, (ox1, oy1, ox2, oy2) in obstacles.items():
            if name in skip_set:
                continue
            if ox2 < x_span_lo - 0.1 or ox1 > x_span_hi + 0.1:
                continue
            blockers.append((ox1, oy1, ox2, oy2))

        candidate_ys = []
        # Several y-offsets so multiple wires that all need to detour around
        # the same blocker can stack instead of all landing on one line.
        for ox1, oy1, ox2, oy2 in blockers:
            for k in range(3):
                candidate_ys.append(oy1 + 0.35 + k * _LANE_STEP)   # progressively above
                candidate_ys.append(oy2 - 0.35 - k * _LANE_STEP)   # progressively below
        # Also: row-gap y values (between adjacent gate rows) — useful when
        # the detour is just hopping a small obstacle and a global lane
        # would force a huge u-turn.
        all_gate_ys = []
        for x, y in L.gate_xy.values():
            all_gate_ys.append(('top', y))
            all_gate_ys.append(('bot', y - GATE_HEIGHT))
        # Offset by half the inter-gate gap so a lane between two gate rows
        # sits centered rather than hugging the nearer frame.
        for ttype, gy in all_gate_ys:
            if ttype == 'top':
                candidate_ys.append(gy + GATE_VSPACE / 2)
            else:
                candidate_ys.append(gy - GATE_VSPACE / 2)
        # Lanes hugging group-box borders, at a respectful distance.
        for gb in boxes_geom:
            candidate_ys.append(gb['y_top'] + BOX_CLEAR + 0.05)
            candidate_ys.append(gb['y_bot'] - BOX_CLEAR - 0.05)
        candidate_ys.append(lane_above_base)
        candidate_ys.append(lane_below_base)

        def clear_of_boxes(ly: float) -> bool:
            """Reject lane ys that run along a group-box border (or through
            its title band) anywhere in this wire's x-span."""
            for gb in boxes_geom:
                if gb['x2'] < x_span_lo - 0.05 or gb['x1'] > x_span_hi + 0.05:
                    continue
                if abs(ly - gb['y_top']) < BOX_CLEAR or abs(ly - gb['y_bot']) < BOX_CLEAR:
                    return False
                if gb['multi'] and gb['y_top'] > ly > gb['y_top'] - GROUP_HEADER:
                    return False
            return True

        # A candidate ly is valid if (a) no gate blocks the horizontal at ly
        # over the wire's x-span and (b) no already-routed wire's lane
        # segment within _LANE_STEP of ly overlaps the x-span. The
        # _LANE_STEP tolerance keeps two near-but-not-identical lane-y
        # candidates (e.g. one at -1.55, another at -1.60 from a different
        # candidate-source) from being rendered as visibly-overlapping lines.
        def lane_y_free(ly: float) -> bool:
            for uy, ux_lo, ux_hi in lanes_above + lanes_below:
                if abs(uy - ly) >= _LANE_STEP - 0.02:
                    continue
                if ux_hi < x_span_lo - 0.05 or ux_lo > x_span_hi + 0.05:
                    continue
                return False
            # Also check generic horizontal segments tracked at this y.
            return horizontal_blocked(ly, x_span_lo, x_span_hi) is None

        valid = []
        for ly in candidate_ys:
            if hit_horizontal(ly, x_span_lo - 0.05, x_span_hi + 0.05, exclude=skip_set):
                continue
            if not lane_y_free(ly):
                continue
            if not clear_of_boxes(ly):
                continue
            valid.append(ly)

        if not valid:
            # Fall back to a fresh lane (alloc_lane bumps to a new y if needed).
            prefer_below = (sy + dy) / 2 < 0
            lane_y = alloc_lane(prefer_below, x_span_lo, x_span_hi)
        else:
            target = (sy + dy) / 2
            valid.sort(key=lambda y: abs(y - target))
            lane_y = valid[0]
            below = lane_y < min(sy, dy)
            (lanes_below if below else lanes_above).append((lane_y, x_span_lo, x_span_hi))

        # Now allocate channels with the *actual* y-spans the wire will use.
        # Pass the destination-side stub info so the channel x avoids
        # shadowing an existing horizontal at y=dy. In the particle corridor
        # use spread mode so successive particle wires cascade leftward.
        cx = alloc_channel(src_gap, min(sy, lane_y), max(sy, lane_y),
                           stub_y=sy, stub_to=sx,
                           spread=(src_gap == -1))
        d_cx = alloc_channel(dst_gap, min(dy, lane_y), max(dy, lane_y),
                             stub_y=dy, stub_to=dx,
                             spread=(dst_gap == -1))
        routes.append(Route([
            (sx, sy),
            (cx, sy),
            (cx, lane_y),
            (d_cx, lane_y),
            (d_cx, dy),
            (dx, dy),
        ]))
        # Record all three horizontal segments of the route.
        add_horizontal(sy, sx, cx)
        add_horizontal(lane_y, cx, d_cx)
        add_horizontal(dy, d_cx, dx)
    return routes

def src_xy(circuit: Circuit, L: Layout, src: str, particles: set, delays: set):
    if '.' in src:
        gname, port = src.split('.', 1)
        return port_xy(L, gname, port, 'out')
    if src in particles:
        cx, cy = L.particle_xy[src]
        return (cx + 0.4, cy)
    if src in delays:
        return port_xy(L, src, '_delay', 'out')
    return None

def dst_xy_col(circuit: Circuit, L: Layout, dst: str, delays: set):
    if '.' in dst:
        gname, port = dst.split('.', 1)
        return port_xy(L, gname, port, 'in'), L.col_of.get(gname)
    if dst in delays:
        return port_xy(L, dst, '_delay', 'in'), L.col_of.get(dst)
    return None, None

def col_of_src(L: Layout, src: str, particles: set, delays: set) -> int | None:
    if '.' in src:
        return L.col_of.get(src.split('.', 1)[0])
    if src in delays:
        return L.col_of.get(src)
    if src in particles:
        return -1   # virtual particle column
    return None


# --------------------------------------------------------------------------
# TikZ emission
# --------------------------------------------------------------------------

TEX_PREAMBLE = r"""\documentclass[border=8pt,tikz]{standalone}
\usepackage{tikz}
\usepackage{amsmath}
\usepackage{array}
\usepackage[T1]{fontenc}
\usetikzlibrary{positioning,shapes.geometric,calc,arrows.meta,fit}
\begin{document}
\begin{tikzpicture}[
    font=\sffamily\small,
    > = {Stealth[length=4pt,width=4pt]},
    fgate/.style = {
        draw=black!60, rounded corners=2pt, line width=0.4pt,
        inner sep=0pt, fill=white,
        font=\sffamily\small,
    },
    fport/.style = {
        draw=black!50, rounded corners=1pt, line width=0.3pt,
        inner sep=0pt, minimum width=14mm, minimum height=4mm,
        fill=blue!4,
        font=\sffamily\footnotesize,
    },
    particle/.style = {
        draw=black!60, line width=0.4pt,
        circle, fill=blue!8, inner sep=1pt,
        minimum size=8mm,
        font=\sffamily\small,
    },
    delay/.style = {
        draw=black!60, line width=0.4pt,
        rectangle, rounded corners=2pt, fill=black!8,
        minimum width=14mm, minimum height=7mm,
        font=\sffamily\footnotesize,
        inner sep=2pt,
    },
    stagelbl/.style = {
        font=\sffamily\itshape\footnotesize,
        text=black!50,
    },
    groupbox/.style = {
        draw=black!30, rounded corners=4pt, line width=0.5pt,
    },
    wire/.style = {
        ->, line width=0.6pt, color=black!80,
        rounded corners=1pt,
    },
]
"""
TEX_GATE_DEF = r"""
%% Fredkin gate macro: \fgate{name}{title}{angle}{x}{y}.
%%
%% Visual model:
%%
%%   +-- name : angle ------------------------+
%%   |                                        |
%%   |              [ control ]               |   ← single passthrough box
%%   |                                        |
%%   |  [uin] \ . . . . . . / [uout]         |
%%   |          X     (dotted X = 4-way split)
%%   |  [lin] / . . . . . . \ [lout]         |
%%   |                                        |
%%   +----------------------------------------+
%%
%% Switch ports are split (in / out) since the gate's switch logic does
%% something interesting between them. The control wire just passes through,
%% so it's a single box centered horizontally.
%%
%% External wires use these named coordinates:
%%   #1-cin  / #1-cout : left and right sides of the control box
%%   #1-uin  / #1-uout : input/output upper switch ports
%%   #1-lin  / #1-lout : input/output lower switch ports
%%
%% Layout (relative to the outer-frame north-west = (0,0)):
%%   width  ≈ 4.2 cm  (frame)
%%   height ≈ 2.4 cm
%%   port box width ≈ 1.4 cm, height ≈ 0.4 cm
\newcommand{\fgate}[5]{%
    %% Outer frame
    \node[fgate, anchor=north west,
          minimum width=4.2cm, minimum height=2.4cm]
          (#1-box) at (#4,#5) {};
    %% Title
    \node[anchor=north, inner sep=0pt, yshift=-2pt]
          at ($(#1-box.north)$)
          {\textbf{#2}\;{\scriptsize\color{black!60}#3}};
    %% Single control port (centered horizontally).
    \node[fport, anchor=center] (#1-control)
          at ($(#1-box.north)+(0,-0.95)$) {control};
    %% Aliases so the router can target the same box via cin/cout names.
    \coordinate (#1-cin)  at ($(#1-control.west)$);
    \coordinate (#1-cout) at ($(#1-control.east)$);
    %% Input/output switch ports.
    \node[fport, anchor=center] (#1-uin)  at ($(#1-box.north west)+(0.85,-1.45)$) {upper};
    \node[fport, anchor=center] (#1-uout) at ($(#1-box.north east)+(-0.85,-1.45)$) {upper};
    \node[fport, anchor=center] (#1-lin)  at ($(#1-box.north west)+(0.85,-1.95)$) {lower};
    \node[fport, anchor=center] (#1-lout) at ($(#1-box.north east)+(-0.85,-1.95)$) {lower};
    %% Internal switch wires: dotted X (4-way split), each input → both outputs.
    \draw[line width=0.4pt, color=black!50, densely dotted]
        (#1-uin.east) -- (#1-uout.west);
    \draw[line width=0.4pt, color=black!50, densely dotted]
        (#1-lin.east) -- (#1-lout.west);
    \draw[line width=0.4pt, color=black!50, densely dotted]
        (#1-uin.east) -- (#1-uout.west|-#1-lout.west);
    \draw[line width=0.4pt, color=black!50, densely dotted]
        (#1-lin.east) -- (#1-uout.west);
}
"""
_TEX_POSTAMBLE = r"""
\end{tikzpicture}
\end{document}
"""


def emit_tex(circuit: Circuit, L: Layout, routes: list[Route],
             angle_overrides: dict[str, object] | None = None) -> str:
    parsed = circuit.topology['parsed']
    out = [TEX_PREAMBLE, TEX_GATE_DEF]

    # Group adornments: multi-gate groups get a fitted box with the group
    # name at the top; single-gate groups get a plain label above the gate.
    # Geometry comes from group_boxes() so the router keeps wires clear of
    # exactly what gets drawn.
    for gb in group_boxes(parsed, L):
        cx = (gb['x1'] + gb['x2']) / 2
        if gb['multi']:
            out.append(rf"\draw[groupbox] ({gb['x1']:.2f},{gb['y_bot']:.2f}) "
                       rf"rectangle ({gb['x2']:.2f},{gb['y_top']:.2f});")
            out.append(rf"\node[stagelbl, anchor=north] at ({cx:.2f},{gb['y_top'] - 0.06:.2f}) "
                       rf"{{{tex_escape(gb['label'])}}};")
        else:
            out.append(rf"\node[stagelbl, anchor=south] at ({cx:.2f},{gb['y_gate_top'] + 0.12:.2f}) "
                       rf"{{{tex_escape(gb['label'])}}};")

    # Gates. Override the angle text with whatever the GUI is currently
    # using (the slider's value), falling back to the YAML's literal default.
    for gname, (x, y) in L.gate_xy.items():
        gdata = parsed.gates[gname]
        sub = subscript(gname)
        title = rf"$g_{{{sub}}}$" if sub else rf"$g$"
        if angle_overrides is not None and gname in angle_overrides:
            angle_text = format_angle(angle_overrides[gname])
        else:
            angle_text = format_angle(gdata.get('angle', 0))
        out.append(rf"\fgate{{{gname}}}{{{title}}}{{{angle_text}}}{{{x:.2f}}}{{{y:.2f}}}")

    # Delays.
    for dname, (cx, cy) in L.delay_xy.items():
        out.append(rf"\node[delay] ({dname}) at ({cx:.2f},{cy:.2f}) {{{tex_escape(dname)}}};")

    # Particles.
    for pname, (cx, cy) in L.particle_xy.items():
        sign_int = circuit.topology['topo']['particle_starts'][pname][1]
        sign_char = '+' if sign_int > 0 else '-'
        sub = subscript(pname)
        label = rf"${sign_char}{pname[:1]}_{{{sub}}}$" if sub else rf"${sign_char}{pname[:1]}$"
        out.append(rf"\node[particle] ({pname}) at ({cx:.2f},{cy:.2f}) {{{label}}};")

    # Wires.
    for r in routes:
        if len(r.points) < 2:
            continue
        coords = " -- ".join(f"({px:.2f},{py:.2f})" for px, py in r.points)
        out.append(rf"\draw[wire] {coords};")

    out.append(_TEX_POSTAMBLE)
    return "\n".join(out)

def subscript(name: str) -> str:
    """Extract the trailing digit(s) of a name like 'g3' or 'p2' for $g_3$.

    Returns an empty string if the name has no trailing digits (so a gate
    named 'g' renders as $g$ rather than $g_g$).
    """
    digits = ''
    for ch in reversed(name):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    return digits

def format_angle(angle) -> str:
    """Format the angle for the gate header."""
    s = str(angle)
    if not s or s == '0':
        return r'$0^{\circ}$'
    # The GUI renders degree values with a trailing '°'; pdflatex can't
    # take that character raw, so convert it to math-mode \circ.
    if s.endswith('°'):
        return f"${tex_math_clean(s[:-1])}^{{\\circ}}$"
    # Wrap pi-bearing strings in math mode.
    if any(c in s for c in 'pi*/+-^') or '\\' in s:
        return f"${tex_math_clean(s)}$"
    return tex_escape(s)

def tex_math_clean(s: str) -> str:
    return s.replace('pi', r'\pi').replace('*', r'\cdot ')

def tex_escape(s: str) -> str:
    return s.replace('_', r'\_').replace('&', r'\&').replace('%', r'\%').replace('#', r'\#').replace('$', r'\$')


# --------------------------------------------------------------------------
# Compile
# --------------------------------------------------------------------------

def compile_tex(tex_source: str, dpi: int) -> Image.Image | None:
    """Run pdflatex on the source, then convert PDF→PNG via ImageMagick.

    We use the `magick` CLI rather than the pdf2image Python package because
    pdf2image requires Poppler (pdftoppm), which conflicts with some Homebrew
    installs of pdf2svg on this system. ImageMagick handles the conversion
    via its embedded Ghostscript delegate.
    """
    if not shutil.which('pdflatex'):
        print("circuits_diagram: pdflatex not on PATH; skipping diagram", file=sys.stderr)
        return None
    if not shutil.which('magick'):
        print("circuits_diagram: ImageMagick (magick) not on PATH; skipping diagram", file=sys.stderr)
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tex_path = tmp_dir / 'diagram.tex'
        tex_path.write_text(tex_source, encoding='utf-8')
        try:
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                 '-output-directory', str(tmp_dir), str(tex_path)],
                capture_output=True, timeout=20,
            )
        except subprocess.TimeoutExpired:
            print("circuits_diagram: pdflatex timed out", file=sys.stderr)
            return None
        pdf_path = tmp_dir / 'diagram.pdf'
        if not pdf_path.exists():
            print("circuits_diagram: pdflatex failed", file=sys.stderr)
            print(result.stdout.decode('utf-8', errors='replace')[-2000:], file=sys.stderr)
            return None
        png_path = tmp_dir / 'diagram.png'
        try:
            subprocess.run(
                ['magick', '-density', str(dpi), str(pdf_path),
                 '-background', 'white', '-alpha', 'remove', str(png_path)],
                check=True, capture_output=True, timeout=20,
            )
        except subprocess.CalledProcessError as exc:
            print(f"circuits_diagram: magick failed: {exc.stderr.decode(errors='replace')[:500]}", file=sys.stderr)
            return None
        except subprocess.TimeoutExpired:
            print("circuits_diagram: magick timed out", file=sys.stderr)
            return None
        if not png_path.exists():
            return None
        return Image.open(png_path).copy()

# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------

CACHE_DIR = Path.home() / '.cache' / 'quantish' / 'diagrams'

def cache_key(circuit: Circuit,
              angle_overrides: dict[str, object] | None = None) -> str:
    """Stable cache key: a hash of the circuit's topology and angles, so any
    change to links, gates, stages, or angle overrides invalidates the cache."""
    parsed = circuit.topology['parsed']
    ident = repr((circuit.fig,
                  sorted(parsed.links.items()),
                  sorted((g, d.get('angle')) for g, d in parsed.gates.items()),
                  parsed.stage_gates,
                  sorted((angle_overrides or {}).items(), key=lambda kv: kv[0])))
    h = hashlib.sha1(ident.encode()).hexdigest()[:12]
    safe_fig = ''.join(c if (c.isalnum() or c in '-_') else '_' for c in circuit.fig)
    return f"{safe_fig}_{h}"


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def render_diagram(circuit: Circuit, dpi: int = 150,
                   angle_overrides: dict[str, object] | None = None) -> Image.Image | None:
    """Generate / fetch-from-cache the PIL Image for a circuit's topology.

    `angle_overrides` is an optional {gate_name: angle_value} dict that
    replaces what the gate header displays. Pass the GUI's current slider
    values here so the diagram reflects the user's parameter settings rather
    than the YAML's literal defaults. Topology (positions, wires) is unaffected.
    The cache key incorporates the override values so distinct settings get
    distinct cached PNGs.
    """
    if circuit.topology is None:
        return None

    cache_key_val = cache_key(circuit, angle_overrides)
    cached = CACHE_DIR / f"{cache_key_val}_{dpi}.png"
    if cached.exists():
        try:
            return Image.open(cached).copy()
        except Exception:
            cached.unlink(missing_ok=True)

    layout = compute_layout(circuit)
    routes = route_wires(circuit, layout)
    tex = emit_tex(circuit, layout, routes, angle_overrides=angle_overrides)
    img = compile_tex(tex, dpi=dpi)
    if img is None:
        return None

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img.save(cached)
    except Exception as exc:
        print(f"circuits_diagram: cache save failed: {exc}", file=sys.stderr)

    return img


def render_diagram_to_file(circuit: Circuit, out_path: Path | str,
                           angle_overrides: dict[str, object] | None = None,
                           dpi: int = 150) -> bool:
    """Render the circuit and write the result to `out_path`.

    File format is selected by the path's extension: `.pdf` and `.svg` are
    produced directly from the LaTeX compile (PDF is the native output;
    SVG goes via `pdf2svg`). Other extensions fall back to PIL.Image.save
    on the rasterized PNG (so .png/.jpg/.gif all work).

    Returns True on success, False on failure (with a message printed to
    stderr).
    """
    if circuit.topology is None:
        return False
    out_path = Path(out_path)
    suffix = out_path.suffix.lower()

    if suffix in ('.pdf', '.svg'):
        layout = compute_layout(circuit)
        routes = route_wires(circuit, layout)
        tex = emit_tex(circuit, layout, routes, angle_overrides=angle_overrides)
        return compile_tex_to_file(tex, out_path)

    img = render_diagram(circuit, dpi=dpi, angle_overrides=angle_overrides)
    if img is None:
        return False
    try:
        img.save(out_path)
    except Exception as exc:
        print(f"circuits_diagram: save to {out_path} failed: {exc}", file=sys.stderr)
        return False
    return True


def compile_tex_to_file(tex_source: str, out_path: Path) -> bool:
    """Compile TeX → PDF and write to `out_path`. If the path is .svg, run
    pdf2svg as a final step. Returns True on success.
    """
    if not shutil.which('pdflatex'):
        print("circuits_diagram: pdflatex not on PATH", file=sys.stderr)
        return False
    suffix = out_path.suffix.lower()
    if suffix == '.svg' and not shutil.which('pdf2svg'):
        print("circuits_diagram: pdf2svg not on PATH; install it to save SVG",
              file=sys.stderr)
        return False

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tex_path = tmp_dir / 'diagram.tex'
        tex_path.write_text(tex_source, encoding='utf-8')
        try:
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                 '-output-directory', str(tmp_dir), str(tex_path)],
                capture_output=True, timeout=20,
            )
        except subprocess.TimeoutExpired:
            print("circuits_diagram: pdflatex timed out", file=sys.stderr)
            return False
        pdf_path = tmp_dir / 'diagram.pdf'
        if not pdf_path.exists():
            print("circuits_diagram: pdflatex failed", file=sys.stderr)
            print(result.stdout.decode('utf-8', errors='replace')[-2000:], file=sys.stderr)
            return False

        if suffix == '.pdf':
            shutil.copyfile(pdf_path, out_path)
            return True

        # .svg
        try:
            subprocess.run(['pdf2svg', str(pdf_path), str(out_path)],
                           check=True, capture_output=True, timeout=20)
        except subprocess.CalledProcessError as exc:
            print(f"circuits_diagram: pdf2svg failed: "
                  f"{exc.stderr.decode(errors='replace')[:500]}", file=sys.stderr)
            return False
        return True


def render_from_simulation(sim, out_path: Path | str,
                           angle_overrides: dict[str, object] | None = None,
                           dpi: int = 150) -> bool:
    """One-call convenience: build the DiagramSpec from a Simulation and
    render it to out_path (.pdf/.svg/.png chosen by extension)."""
    spec = spec_from_simulation(sim)
    return render_diagram_to_file(spec, out_path,
                                  angle_overrides=angle_overrides, dpi=dpi)
