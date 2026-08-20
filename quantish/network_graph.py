"""Configuration-space point evolution DAG of a simulation, rendered with Vega-Altair.

Each glyph is one configuration-space point: a stack of cells, one per particle
(hue = particle identity, brightness = magnitude, dark = 0, light = 1;
fine black diagonal stripes = nothing happened to it). Arrows show
successor relationships and respect particle identity: they leave only the
cells of particles that have been active, and land on the same particle's
cell in the successor.

Columns, left to right:
- initial: the configured entry weights, labeled per particle (the hue
  key); arrows leave the cells of the particles the first stage acts on;
- per stage, a result column — a switch particle's cell shows the
  magnitude of the component the gate applied, but only when the gate did
  something (split or controlled reroute; an angle-0 gate with no control
  is a no-op and stays striped); a particle that passed through a control
  shows the magnitude of the control input; when a stage gate's control
  was occupied, the switch-wire cells of the stage's control-wired gates
  carry a thicker border in the controller's hue;
- a state's history ends with one settled glyph in the column after its
  last action, showing the same cell values as that action — for
  surviving states that is the 'final' column; a state that dies out
  settles in the stage column right after the one that produced it, with
  nothing coming out of it.

configuration-space points appear in the canonical display order (gate, then port with
upper first, then sign with + first — sim.cs_point_sort_key). Cancelled
and zero-weight configuration-space points do not appear at all. Gates are implicit: the
focus is stages and their results.
"""
import colorsys
import logging
import math as m
from collections import defaultdict
from pathlib import Path

from quantish.config_space import ConfigSpace, ConfigSpacePoint, GatePort
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
            out_path = diagram_path.with_stem(diagram_path.stem + '_graph').with_suffix('.pdf')
            pdf = vl_convert.vegalite_to_pdf(self.chart().to_json())
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
        """Pure data for the renderer: columns, glyphs, cells, stripes,
        control borders, arrows, and labels."""
        sim = self.sim

        layers = defaultdict(list)
        for p in self.result_space.index.values():
            if p.cancelled or qn.zerop(p.weight):
                continue
            layers[p.step].append(p)
        steps = sorted(layers.keys())
        for step in steps:
            layers[step].sort(key=sim.cs_point_sort_key)

        control_wired = {str(dst).split('.')[0]
                         for dst in sim.links.values()
                         if str(dst).endswith('.control')}
        # delay/pass-through gates are no-ops kept only for the book's
        # synchronization: they disappear from this view (the circuit
        # diagrams still show them)
        delays = set(sim.delay_gates.keys()) | set(sim.pass_through_gates)

        def stage_gates_at(step):
            i = steps.index(step)
            return sim.run_stages[i - 1] if 0 < i <= len(sim.run_stages) else []

        def occupied_controls(w, gates):
            found = {}
            for g in gates:
                port = GatePort(g, 'control')
                for pname, c in w.coords.items():
                    if c.position.endpoint == port:
                        found[g] = pname
            return found

        def parent_weight_sum(w):
            weights = [parent.weight for parent in w.contributions]
            if not weights:
                return w.weight
            total = weights[0]
            for extra in weights[1:]:
                total = total + extra
            return total

        def gate_acted(w, pname):
            origin = w.coords[pname].position.origin
            if origin is None or origin.gate not in sim.gates \
                    or origin.gate in delays:
                return False
            if to_float(sim.gates[origin.gate].theta) != 0.0:
                return True
            control = GatePort(origin.gate, 'control')
            return any(c.position.endpoint == control
                       for parent in w.contributions
                       for c in parent.coords.values())

        def action_cells(w):
            """pname -> (kind, level, value) for the point's own action:
            entry weights for initial points, the stage's effect otherwise.
            kind is 'cell' or 'striped'; value is the complex behind the
            level, for tooltips."""
            out = {}
            for pname in sorted(w.coords.keys()):
                if w.step == steps[0]:
                    weight = w.particles.get(pname, 1.0)
                    weight = weight if weight is not None else 1.0
                    out[pname] = ('cell', self.magnitude(weight), complex(weight))
                    continue
                origin = w.coords[pname].position.origin
                if origin is not None and origin.port == 'control' \
                        and origin.gate in stage_gates_at(w.step) \
                        and origin.gate not in delays:
                    carried = parent_weight_sum(w)
                    out[pname] = ('cell', self.magnitude(carried), complex(carried))
                    continue
                component = w.particles.get(pname)
                if component is not None and gate_acted(w, pname):
                    out[pname] = ('cell', self.magnitude(component), complex(component))
                    continue
                out[pname] = ('striped', None, None)
            return out

        cells_of = {p: action_cells(p) for step in steps for p in layers[step]}

        # display level: scale raw magnitudes by the figure's own maximum,
        # linearly into LEVEL_FLOOR…1 (the floor keeps the smallest
        # magnitudes visibly off-black)
        vmax = max((lv for kinds in cells_of.values()
                    for kind, lv, _v in kinds.values()
                    if kind == 'cell' and lv is not None), default=1.0) or 1.0

        def to_level(raw):
            return LEVEL_FLOOR + (1.0 - LEVEL_FLOOR) * raw / vmax

        def is_active(w, pname):
            return w.step != steps[0] and cells_of[w][pname][0] == 'cell'

        # A pure carry has no active particles. A dead carry never acts
        # again; dead carries are suppressed and their last action settles
        # one column later instead.
        children = defaultdict(list)
        for step in steps:
            for p in layers[step]:
                for parent in p.contributions:
                    children[parent].append(p)

        dead = {}
        for step in reversed(steps):
            for p in layers[step]:
                pure = p.step != steps[0] and not any(
                    is_active(p, n) for n in p.coords)
                dead[p] = pure and all(dead.get(c, False) for c in children[p])

        def settles(p):
            return not dead.get(p, False) and \
                all(dead.get(c, False) for c in children[p])

        def stage_tick(i):
            gates = sim.run_stages[i] if i < len(sim.run_stages) else []
            for name, members in (sim.declared_run_stages or {}).items():
                if gates and set(gates) <= set(members):
                    return name
            return ', '.join(gates)

        # Columns: initial, one per stage, final — except that a stage of
        # only delay gates contributes no column at all. A glyph is
        # (point, mode) with mode 'initial', 'result' (action or waiting
        # carry), or 'settled' (the state at rest, same cells as its last
        # action).
        def stage_of(i):
            return sim.run_stages[i] if i < len(sim.run_stages) else []

        suppressed = {steps[i + 1] for i in range(len(steps) - 1)
                      if stage_of(i) and all(g in delays for g in stage_of(i))}
        visible_steps = [st for st in steps if st not in suppressed]

        col_labels = ['initial'] + [stage_tick(i) for i in range(len(steps) - 1)
                                    if steps[i + 1] not in suppressed] + ['final']
        col_glyphs = [[] for _ in col_labels]
        for ci, step in enumerate(visible_steps):
            for p in layers[step]:
                if dead.get(p, False):
                    continue
                col_glyphs[ci].append((p, 'initial' if ci == 0 else 'result'))
                if settles(p):
                    col_glyphs[ci + 1].append((p, 'settled'))
        for glyphs in col_glyphs:
            glyphs.sort(key=lambda g: sim.cs_point_sort_key(g[0]))

        # the final column is redundant when it repeats the last stage
        # column exactly (nothing died there); keep it only when it differs
        if {q for q, _ in col_glyphs[-1]} == {q for q, _ in col_glyphs[-2]}:
            col_glyphs.pop()
            col_labels.pop()

        def visible_parents(w):
            """Immediate predecessors, looking through suppressed
            delay-stage points."""
            out = []
            for parent in w.contributions:
                if parent.step in suppressed:
                    out.extend(visible_parents(parent))
                else:
                    out.append(parent)
            return out

        layer_max = max(len(g) for g in col_glyphs)
        n_particles = max(len(p.coords) for step in steps for p in layers[step])

        pos = {}
        for ci, glyphs in enumerate(col_glyphs):
            n = len(glyphs)
            for i, (p, mode) in enumerate(glyphs):
                pos[(ci, p)] = (float(ci), (n - 1) / 2.0 - i)

        # Geometry: rows are 1 apart; the renderer computes pixel
        # dimensions from these data units and sizes cells square.
        band_h = min(0.22, 0.82 / n_particles)
        node_h = band_h * n_particles

        def cell_rect(ci, p, pname):
            x, y = pos[(ci, p)]
            i = sorted(p.coords.keys()).index(pname)
            y1 = y + node_h / 2 - i * band_h
            return x, y1 - band_h, y1  # (x-center, y0, y1)

        point_str = {p: ' '.join(
            f'{n}@{c.position.endpoint}:{int(c.sign):+d}'
            for n, c in p.coords.items()) for step in steps for p in layers[step]}

        cells, stripes, arrows, labels = [], [], [], []

        def add_cells(ci, p, mode):
            pnames = sorted(p.coords.keys())
            # control borders belong to the action, not the settled copy
            control_edges = {}
            if mode == 'result':
                gates = [g for g in stage_gates_at(p.step)
                         if g in control_wired and g not in delays]
                controllers = {}
                for parent in p.contributions:
                    controllers.update(occupied_controls(parent, gates))
                if controllers:
                    controller = sorted(controllers.values())[0]
                    edge = self.border_color(HUES[pnames.index(controller) % len(HUES)])
                    for pname in pnames:
                        origin = p.coords[pname].position.origin
                        if origin is not None and origin.gate in gates \
                                and origin.port != 'control':
                            control_edges[pname] = edge
            pr = to_float(probability(p.weight))
            for i, pname in enumerate(pnames):
                kind, level, value = cells_of[p][pname]
                xc, y0, y1 = cell_rect(ci, p, pname)
                # a control-swapped cell's own border is the control cue:
                # thick, in the controlling particle's hue — otherwise the
                # ordinary thin black border
                stroke, sw = ((control_edges[pname], 1.0)
                              if pname in control_edges else ('#000000', 0.4))
                level = to_level(level) if kind == 'cell' else level
                base = dict(x=xc, y0=y0, y1=y1,
                            particle=pname,
                            cs_point=point_str[p],
                            stroke=stroke, sw=sw,
                            pr=f'{pr:.4f}')
                if kind == 'striped':
                    cells.append(dict(base, fill='#ffffff', value='—'))
                    stripes.append((xc, y0, y1, sw))
                else:
                    cells.append(dict(
                        base,
                        fill=self.cell_color(level, HUES[i % len(HUES)]),
                        value=f'{value.real:+.4f}{value.imag:+.4f}i'))
                if mode == 'initial':
                    sign = '+' if int(p.coords[pname].sign) >= 0 else '−'
                    labels.append(dict(x=xc, y=(y0 + y1) / 2,
                                       text=f'{pname}{sign}'))

        def add_arrow(x0, y0, x1, y1):
            arrows.append(dict(x=x0, y=y0, x2=x1, y2=y1))

        def cell_mid(ci, p, pname):
            xc, y0, y1 = cell_rect(ci, p, pname)
            return (y0 + y1) / 2

        for ci, glyphs in enumerate(col_glyphs):
            for p, mode in glyphs:
                add_cells(ci, p, mode)
                if mode == 'initial':
                    continue
                x, y = pos[(ci, p)]
                if mode == 'settled':
                    px, py = pos[(ci - 1, p)]
                    movers = [n for n in sorted(p.coords.keys())
                              if cells_of[p][n][0] == 'cell']
                    if p.step != steps[0] and movers:
                        for n in movers:
                            add_arrow(px, cell_mid(ci - 1, p, n),
                                      x, cell_mid(ci, p, n))
                    else:
                        add_arrow(px, py, x, y)
                    continue
                for parent in visible_parents(p):
                    if (ci - 1, parent) not in pos:
                        continue
                    px, py = pos[(ci - 1, parent)]
                    if parent.step == steps[0]:
                        # out of the initial column: from the entry cells of
                        # the particles the first stage acts on
                        movers = [n for n in sorted(parent.coords.keys())
                                  if n in p.coords and is_active(p, n)]
                    else:
                        movers = [n for n in sorted(parent.coords.keys())
                                  if n in p.coords and is_active(parent, n)]
                    if movers:
                        for n in movers:
                            add_arrow(px, cell_mid(ci - 1, parent, n),
                                      x, cell_mid(ci, p, n))
                    else:
                        add_arrow(px, py, x, y)

        return dict(col_labels=col_labels, layer_max=layer_max,
                    n_columns=len(col_labels), band_h=band_h,
                    cells=cells, stripes=stripes,
                    arrows=arrows, labels=labels,
                    title=f'{sim.title} — weight evolution')

    # ---------- the Altair renderer ----------

    def chart(self):
        import altair as alt
        import pandas as pd

        model = self.build_model()
        band_h = model['band_h']
        n_cols = model['n_columns']
        layer_max = model['layer_max']

        x_lo, x_hi = -0.75, n_cols - 1 + 0.6
        y_span = (layer_max + 1) / 2.0
        y_lo, y_hi = -y_span - 0.75, y_span + 0.4
        width = min(170 * n_cols, 1350)
        height = max(min(int(58 * (layer_max + 2)), 900), 220)
        px_x = width / (x_hi - x_lo)
        px_y = height / (y_hi - y_lo)
        cell_w = band_h * px_y / px_x  # square cells in pixels

        xscale = alt.Scale(domain=[x_lo, x_hi], nice=False, zero=False)
        yscale = alt.Scale(domain=[y_lo, y_hi], nice=False, zero=False)

        def X(field='x'):
            return alt.X(f'{field}:Q', axis=None, scale=xscale)

        def Y(field='y'):
            return alt.Y(f'{field}:Q', axis=None, scale=yscale)

        layer = []

        arrows = pd.DataFrame(model['arrows'])
        if len(arrows):
            # start lines at the source cell edge, stop at the destination
            # cell edge; arrowheads are small filled triangles built in
            # DATA units (sized in pixels at default zoom) so they scale
            # with the figure. Vega-Lite has no polygon mark, but every
            # arrow here points rightward, so each triangle is x-monotone
            # and renders exactly as an area band (y…y2 vs x) per head.
            arrows['x'] = arrows['x'] + cell_w / 2 + 0.02
            arrows['x2'] = arrows['x2'] - cell_w / 2 - 0.02
            head_rows = []
            head_len, head_half = 6.0, 2.4  # px at default zoom
            for aid, r in enumerate(arrows.itertuples(index=False)):
                dx, dy = (r.x2 - r.x) * px_x, (r.y2 - r.y) * px_y
                norm = m.hypot(dx, dy) or 1.0
                ux, uy = dx / norm, dy / norm
                tip = (r.x2, r.y2)
                bx = r.x2 - head_len * ux / px_x
                by = r.y2 - head_len * uy / px_y
                corners = [(bx - head_half * -uy / px_x, by - head_half * ux / px_y),
                           (bx + head_half * -uy / px_x, by + head_half * ux / px_y)]
                corners.sort()  # by x: leftmost first
                (lx, ly), (mx, my) = corners
                if (tip[0] - lx) < 1e-9:
                    continue  # degenerate (shouldn't happen: arrows point right)
                if abs(mx - lx) < 1e-9:
                    # symmetric base (near-horizontal arrow): two x-samples
                    head_rows += [dict(aid=aid, x=lx, y=min(ly, my), y2=max(ly, my)),
                                  dict(aid=aid, x=tip[0], y=tip[1], y2=tip[1])]
                else:
                    # slanted: sample the middle corner against the L->tip edge
                    t = (mx - lx) / (tip[0] - lx)
                    edge_y = ly + t * (tip[1] - ly)
                    head_rows += [dict(aid=aid, x=lx, y=ly, y2=ly),
                                  dict(aid=aid, x=mx, y=min(my, edge_y),
                                       y2=max(my, edge_y)),
                                  dict(aid=aid, x=tip[0], y=tip[1], y2=tip[1])]
            layer.append(alt.Chart(arrows).mark_rule(
                stroke='black', strokeWidth=1).encode(
                x=X(), y=Y(), x2='x2:Q', y2='y2:Q'))
            layer.append(alt.Chart(pd.DataFrame(head_rows)).mark_area(
                interpolate='linear', color='black', opacity=1).encode(
                x=X(), y=Y(), y2='y2:Q', detail='aid:N'))

        cells = pd.DataFrame(model['cells'])
        # every cell occupies the same full-size footprint: the border is
        # an underlay rect in the border color, and the fill is inset by
        # the border thickness in DATA units — so a control border is a
        # thicker border on the same box, and borders scale with zoom
        cells['x0'] = cells['x'] - cell_w / 2
        cells['x1'] = cells['x'] + cell_w / 2
        cells['bx'] = cells['sw'] / px_x   # border thickness, data units
        cells['by'] = cells['sw'] / px_y
        cells['fx0'] = cells['x0'] + cells['bx']
        cells['fx1'] = cells['x1'] - cells['bx']
        cells['fy0'] = cells['y0'] + cells['by']
        cells['fy1'] = cells['y1'] - cells['by']
        tooltip = [alt.Tooltip('cs_point:N', title='configuration-space point'),
                   alt.Tooltip('particle:N', title='particle'),
                   alt.Tooltip('value:N', title='value'),
                   alt.Tooltip('pr:N', title='Pr(point)')]
        layer.append(alt.Chart(cells).mark_rect().encode(
            x=X('x0'), x2='x1:Q', y=Y('y0'), y2='y1:Q',
            color=alt.Color('stroke:N', scale=None), tooltip=tooltip))
        layer.append(alt.Chart(cells).mark_rect().encode(
            x=X('fx0'), x2='fx1:Q', y=Y('fy0'), y2='fy1:Q',
            color=alt.Color('fill:N', scale=None), tooltip=tooltip))

        # fine black diagonal stripes for untouched cells, generated as data
        stripe_rows = []
        n_stripes = 5
        for xc, y0, y1, sw in model['stripes']:
            # stripes fill the cell exactly to the border's inner edge
            x0 = xc - cell_w / 2 + sw / px_x
            x1 = xc + cell_w / 2 - sw / px_x
            y0, y1 = y0 + sw / px_y, y1 - sw / px_y
            for k in range(1, 2 * n_stripes):
                c = -1 + k / n_stripes
                u0, u1 = max(0.0, -c), min(1.0, 1.0 - c)
                if u0 >= u1:
                    continue
                stripe_rows.append(dict(
                    x=x0 + u0 * (x1 - x0), y=y0 + (u0 + c) * (y1 - y0),
                    x2=x0 + u1 * (x1 - x0), y2=y0 + (u1 + c) * (y1 - y0)))
        if stripe_rows:
            layer.append(alt.Chart(pd.DataFrame(stripe_rows)).mark_rule(
                stroke='black', strokeWidth=0.4).encode(
                x=X(), y=Y(), x2='x2:Q', y2='y2:Q'))

        plabels = pd.DataFrame(model['labels'])
        if len(plabels):
            plabels['x'] = plabels['x'] - cell_w / 2 - 0.04
            layer.append(alt.Chart(plabels).mark_text(
                align='right', baseline='middle', fontSize=11,
                color='#404040').encode(
                x=X(), y=Y(), text='text:N'))

        stage_labels = pd.DataFrame([
            dict(x=float(i), y=y_lo + 0.35, text=label)
            for i, label in enumerate(model['col_labels'])])
        layer.append(alt.Chart(stage_labels).mark_text(
            fontSize=13, color='black').encode(
            x=X(), y=Y(), text='text:N'))

        return alt.layer(*layer).properties(
            width=width, height=height,
            title=model['title']).configure_view(stroke=None)
