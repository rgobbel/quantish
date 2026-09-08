"""Weight-evolution graph of a simulation: stages × gate output ports.

Each column is a run stage; each node is one switch output port of one
gate of that stage holding a particle (a delay gate's or phase plate's
control wire likewise), the initial column being a single node of
every particle's entry weight. A node has one cell per particle (hue =
particle identity): a particle at that gate shows its MAGNITUDE at its
port — the square root of the summed probabilities of its mutually
orthogonal plus- and minus-signed components there, at the node's port
for the switch particle, at the control port for the control particle
— dark = 0, light = 1; a particle at no port of that gate is fine black
diagonal stripes on white. When the gate's control was occupied, the
other cells carry a border in the controlling particle's hue. Labels
name particles at ports without signs: the graph speaks in magnitudes.
Arrows are the wires: one per particle, from the node where it last
was to the node it reaches next, spanning the columns it spent in
flight. Gates themselves are implicit: the focus is stages and their
results.
"""
import colorsys
import logging
import math as m
from collections import defaultdict
from pathlib import Path

from quantish.config_space import ConfigSpace, GatePort
from quantish.display import cs_point_sort_key, strip_markdown
from quantish.simulation import Simulation
from quantish.qnumber import probability, to_float
import quantish.qnumber as qn

log = logging.getLogger('quantish')

HUES = [0.00, 0.33, 0.62, 0.78, 0.09, 0.50]  # red green blue purple orange cyan
LEVEL_FLOOR = 0.1  # display level of a zero magnitude (1.0 = the figure's max)


class NetworkGraph:
    def __init__(self, result_space: ConfigSpace, sim: Simulation, diagram_path: Path=None,
                 show=True):
        """With diagram_path: render the weight-evolution graph and save it
        as a PDF next to diagram_path (requires vl-convert). Without: just
        hold the inputs — call chart() to render."""
        self.result_space = result_space
        self.sim = sim
        if diagram_path is not None:
            import vl_convert

            from quantish.svg_export import network_graph_svg
            out_path = diagram_path.with_stem(diagram_path.stem + '_graph').with_suffix('.pdf')
            pdf = vl_convert.svg_to_pdf(network_graph_svg(self.build_model()))
            out_path.write_bytes(pdf)
            log.info(f'Weight-evolution graph written to {out_path}')

    # ---------- value scale ----------

    @staticmethod
    def magnitude(value):
        """Raw magnitude of a value; to_float only here, at the color edge.
        Display levels come from to_level in build_model: raw magnitudes
        are scaled by the figure's maximum into LEVEL_FLOOR…1 — linear,
        with a floor so the smallest magnitudes stay distinguishable
        from black."""
        return max(0.0, to_float(abs(value)))

    @staticmethod
    def cell_color(mag, hue):
        # dark = 0, light = 1. Value and saturation both ramp so the ends
        # read far apart: near 0 a deep saturated shade, near 1 a light
        # tint just dark enough to distinguish from white.
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0 - 0.82 * mag, 0.25 + 0.75 * mag)
        return f'#{round(255 * r):02x}{round(255 * g):02x}{round(255 * b):02x}'

    @staticmethod
    def border_color(hue):
        r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.75)
        return f'#{round(255 * r):02x}{round(255 * g):02x}{round(255 * b):02x}'

    # ---------- the render model ----------

    def build_model(self):
        """Pure data for the renderer: columns, nodes, cells, stripes,
        control borders, arrows, and labels.

        Randy's layout (2026-09-08). Columns are the run stages (a stage
        of delay gates only contributes no column). A NODE is one switch
        output port of one gate of the stage holding a particle — the
        plus and minus components of that particle at that port travel
        together to the next point of the graph, so they are one node;
        a delay gate or phase plate, entered through its control wire,
        is one node too. The initial column is a single node of every
        particle's entry weight. A node has one cell per particle:
        a particle at that gate shows its MAGNITUDE at its port (the
        node's port for the switch particle, the control port for the
        control particle — real, non-negative, the square root of the
        summed probabilities of its mutually orthogonal components
        there), a particle at no port of that gate is striped. When the
        gate's control was occupied, the other cells carry a border in
        the controlling particle's hue. Labels carry no signs: the
        graph speaks in magnitudes. Arrows are the wires: one per
        particle, from the node where it last was to the node it
        reaches next, spanning the columns it spent in flight."""
        sim = self.sim

        layers = defaultdict(list)
        for p in self.result_space.index.values():
            if p.cancelled or qn.zerop(p.weight):
                continue
            layers[p.step].append(p)
        steps = sorted(layers.keys())
        for step in steps:
            layers[step].sort(key=lambda p: cs_point_sort_key(sim, p))

        # delay gates (and phase plates) are drawn like the gates they are
        # subclassed from — a particle passes through their control wire
        delays = set(sim.delay_gates.keys()) | set(sim.pass_through_gates)
        plain_delays = {g for g in delays
                        if sim.gates[g].report_type() != 'PhasePlate'}

        def stage_gates_at(step):
            i = steps.index(step)
            return sim.run_stages[i - 1] if 0 < i <= len(sim.run_stages) else []

        def stage_tick(i):
            gates = sim.run_stages[i] if i < len(sim.run_stages) else []
            for name, members in (sim.declared_run_stages or {}).items():
                if gates and set(gates) <= set(members):
                    return name
            return ', '.join(gates)

        def stage_of(i):
            return sim.run_stages[i] if i < len(sim.run_stages) else []

        # a stage of plain delays only — nothing happens — has no column
        suppressed = {steps[i + 1] for i in range(len(steps) - 1)
                      if stage_of(i) and all(g in plain_delays for g in stage_of(i))}
        visible_steps = [st for st in steps if st not in suppressed]
        col_labels = ['initial'] + [stage_tick(i) for i in range(len(steps) - 1)
                                    if steps[i + 1] not in suppressed]

        particles = sorted({n for step in steps for p in layers[step]
                            for n in p.coords})
        n_particles = len(particles)

        # ---- magnitudes: per step, particle, port -> sqrt(Σ probability)
        prob_at = {}
        for step in steps:
            sums = defaultdict(float)
            for pt in layers[step]:
                pr = to_float(probability(pt.weight))
                for n, c in pt.coords.items():
                    if c.position.origin is not None:
                        sums[(n, c.position.origin)] += pr
            prob_at[step] = sums

        def magnitude_at(step, pname, port):
            return m.sqrt(prob_at[step].get((pname, port), 0.0))

        def prob_of(step, pname, port):
            return prob_at[step].get((pname, port), 0.0)

        # ---- nodes: (column, gate, port) -> the points there, per particle
        # port. A switch port is a node; a delay/plate's control wire is
        # a node; a Fredkin gate's control port is not a node of its own —
        # the control particle appears as a cell in that gate's switch
        # nodes (its border cue on the others).
        Node = dict   # keys: col, gate, port, points, at (pname -> port), label
        columns = [[] for _ in col_labels]
        node_of_point = defaultdict(list)   # (col, point) -> [node, ...]

        initial = Node(col=0, gate=None, port='ORIGIN', points=list(layers[steps[0]]),
                       at={n: 'ORIGIN' for n in particles},
                       label=' '.join(f'{n}@ORIGIN' for n in particles))
        columns[0].append(initial)
        for p in layers[steps[0]]:
            node_of_point[(0, p)].append(initial)

        for ci, step in enumerate(visible_steps[1:], start=1):
            gates = list(stage_gates_at(step))
            for g in gates:
                ports = (['control'] if g in delays else ['upper', 'lower'])
                for port in ports:
                    gp = GatePort(g, port)
                    pts = [pt for pt in layers[step]
                           if any(c.position.origin == gp for c in pt.coords.values())]
                    if not pts:
                        continue
                    at = {}
                    for pt in pts:
                        for n, c in pt.coords.items():
                            o = c.position.origin
                            if o is not None and o.gate == g:
                                at.setdefault(n, set()).add(o)
                    node = Node(col=ci, gate=g, port=port, points=pts,
                                at={n: sorted(os_, key=repr) for n, os_ in at.items()},
                                label=' '.join(f'{n}@{o}' for n in sorted(at)
                                               for o in sorted(at[n], key=repr)))
                    columns[ci].append(node)
                    for pt in pts:
                        node_of_point[(ci, pt)].append(node)

        layer_max = max(len(col) for col in columns)
        band_h = min(0.22, 0.82 / n_particles)
        node_h = band_h * n_particles

        pos, node_id = {}, {}
        for ci, col in enumerate(columns):
            n = len(col)
            for i, node in enumerate(col):
                pos[id(node)] = (float(ci), (n - 1) / 2.0 - i)
                node_id[id(node)] = f'{ci}.{i}'

        def cell_rect(node, pname):
            x, y = pos[id(node)]
            i = particles.index(pname)
            y1 = y + node_h / 2 - i * band_h
            return x, y1 - band_h, y1

        def cell_mid(node, pname):
            _, y0, y1 = cell_rect(node, pname)
            return (y0 + y1) / 2

        # ---- cells
        cells, stripes, arrows, labels = [], [], [], []
        vmax = 1.0
        for ci, col in enumerate(columns):
            for node in col:
                for n in particles:
                    if n in node['at']:
                        ports = node['at'][n]
                        if ci == 0:
                            pass
                        else:
                            vmax = max(vmax, max(magnitude_at(visible_steps[ci], n, o)
                                                 for o in ports))

        def to_level(raw):
            return LEVEL_FLOOR + (1.0 - LEVEL_FLOOR) * raw / vmax

        for ci, col in enumerate(columns):
            step = visible_steps[ci]
            for node in col:
                g = node['gate']
                controller = None
                if g is not None and g not in delays:
                    for n, ports in node['at'].items():
                        if any(o.port == 'control' for o in ports):
                            controller = n
                for i, n in enumerate(particles):
                    xc, y0, y1 = cell_rect(node, n)
                    hue = HUES[i % len(HUES)]
                    stroke, sw = '#000000', 0.4
                    if controller is not None and n != controller:
                        stroke, sw = self.border_color(
                            HUES[particles.index(controller) % len(HUES)]), 1.0
                    base = dict(x=xc, y0=y0, y1=y1, particle=n,
                                node=node_id[id(node)],
                                cs_point=node['label'], stroke=stroke, sw=sw)
                    if n not in node['at']:
                        cells.append(dict(base, fill='#ffffff', value='—',
                                          port='', pr=''))
                        stripes.append((xc, y0, y1, sw))
                        continue
                    if ci == 0:
                        entry = next((pt.particles.get(n) for pt in node['points']
                                      if pt.particles.get(n) is not None), 1.0)
                        mag, pr, port = self.magnitude(entry), self.magnitude(entry) ** 2, 'ORIGIN'
                    else:
                        ports = node['at'][n]
                        pr = sum(prob_of(step, n, o) for o in ports)
                        mag = m.sqrt(pr)
                        port = ', '.join(str(o) for o in ports)
                    cells.append(dict(base, fill=self.cell_color(to_level(mag), hue),
                                      value=f'{mag:.4f}', pr=f'{pr:.4f}', port=port))
                    if ci == 0:
                        labels.append(dict(x=xc, y=(y0 + y1) / 2, text=n))

        # ---- arrows: wires. For each node and each particle at it, the
        # nodes where that particle last was (walking each point's
        # contributions back through the stages it spent in flight).
        col_of_step = {st: ci for ci, st in enumerate(visible_steps)}

        def acted(pt, n):
            if pt.step == steps[0]:
                return True
            o = pt.coords[n].position.origin
            return o is not None and o.gate in stage_gates_at(pt.step) \
                and pt.step in col_of_step

        def last_nodes(pt, n, _depth=0):
            """Nodes where particle n last was on the way to point pt
            (pt's own column excluded)."""
            found = []
            for parent in pt.contributions:
                if n not in parent.coords:
                    continue
                if acted(parent, n):
                    ci = col_of_step[parent.step]
                    for node in node_of_point[(ci, parent)]:
                        if n in node['at']:
                            found.append(node)
                else:
                    found.extend(last_nodes(parent, n))
            return found

        drawn = set()
        for ci, col in enumerate(columns[1:], start=1):
            for node in col:
                for n in node['at']:
                    for pt in node['points']:
                        for src in last_nodes(pt, n):
                            key = (node_id[id(src)], node_id[id(node)], n)
                            if key in drawn:
                                continue
                            drawn.add(key)
                            sx, _ = pos[id(src)]
                            dx, _ = pos[id(node)]
                            arrows.append(dict(x=sx, y=cell_mid(src, n),
                                               x2=dx, y2=cell_mid(node, n),
                                               src=node_id[id(src)],
                                               dst=node_id[id(node)]))

        return dict(col_labels=col_labels, layer_max=layer_max,
                    n_columns=len(col_labels), band_h=band_h,
                    cells=cells, stripes=stripes,
                    arrows=arrows, labels=labels,
                    # chart titles are plain text: peel the caption's
                    # Markdown markers rather than show them literally
                    title=f'{sim.title}{" - " if sim.caption else ""}'
                          f'{strip_markdown(sim.caption)}')
