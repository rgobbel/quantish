"""Circuit diagrams as Vega-Altair charts, for the web/app.

Same geometry as the TikZ renderer — spec_from_simulation, compute_layout
and route_wires supply the columns, rows and wire polylines — drawn as
Altair layers instead of TeX. Styling follows the Mermaid diagrams:
white background, pale yellow stage boxes, pale blue gate boxes,
lavender port boxes whose values (after a run) sit INSIDE the box, and
stadium-shaped value blobs where a dangling output's value lands
outside any gate. Pan/zoom and hover tooltips come free.
"""
import math
import textwrap

import altair as alt
import pandas as pd

from quantish.display import pos_value_str, strip_markdown
from quantish.tikz_diagram import (CONTROL_HALF_W, GATE_WIDTH, PORT_DY,
                                   PORT_IN_DX, PORT_OUT_DX, PORT_W,
                                   WIRE_STUB_LEN,
                                   compute_layout, route_wires,
                                   spec_from_simulation)
from quantish.util import SEP, subscript_digits

# The palette. Edit these hex values and save; the app picks the change
# up on the next ▶ Run (module autoreload). Input (particle) and output
# (stadium) blobs deliberately share VALUE_FILL/VALUE_STROKE.
STAGE_FILL, STAGE_STROKE = '#ffffde', '#aaaa33'    # Mermaid yellow
GATE_FILL, GATE_STROKE = '#e6f4f1', '#2f9e8f'      # pale teal
PORT_FILL, PORT_STROKE = '#e0e7ff', '#5c64d1'      # pale indigo
DELAY_FILL, DELAY_STROKE = '#e2e8f0', '#64748b'    # slate gray
VALUE_FILL, VALUE_STROKE = '#f4f4f6', '#8b93a0'    # very pale gray
PARTICLE_FILL = VALUE_FILL
WIRE_COLOR = '#22314a'

# the default rendered width of a wide circuit, in pixels. Charts never
# exceed it (a fixed width is the one sizing marimo's vega wrapper
# renders faithfully — its container-width mode bakes in a mismeasured
# mount-time width), and narrower circuits keep their natural size.
MAX_WIDTH = 900

LINE_H = 0.26           # height of one text line, in layout units
PORT_PAD = 0.14         # padding inside port boxes
CHAR_W = 0.115          # approx character width at the value font size


def _sub(s) -> str:
    return subscript_digits(str(s))


_SVG_PANZOOM_JS = """
const svg = document.querySelector('svg');
const vb0 = svg.viewBox.baseVal;
const home = { x: vb0.x, y: vb0.y, w: vb0.width, h: vb0.height };
let vb = { ...home };
function apply() {
  svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
}
svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  const r = svg.getBoundingClientRect();
  const mx = vb.x + (e.clientX - r.left) / r.width * vb.w;
  const my = vb.y + (e.clientY - r.top) / r.height * vb.h;
  const f = Math.exp(e.deltaY * 0.002);
  const w = Math.min(home.w, Math.max(home.w / 40, vb.w * f));
  const k = w / vb.w;
  vb = { x: mx - (mx - vb.x) * k, y: my - (my - vb.y) * k,
         w, h: vb.h * k };
  apply();
}, { passive: false });
let pan = null;
svg.addEventListener('mousedown', (e) => {
  pan = { x: e.clientX, y: e.clientY, vx: vb.x, vy: vb.y };
  svg.classList.add('panning');
});
window.addEventListener('mousemove', (e) => {
  if (!pan) return;
  const r = svg.getBoundingClientRect();
  vb.x = pan.vx - (e.clientX - pan.x) / r.width * vb.w;
  vb.y = pan.vy - (e.clientY - pan.y) / r.height * vb.h;
  apply();
});
window.addEventListener('mouseup', () => {
  pan = null;
  svg.classList.remove('panning');
});
svg.addEventListener('dblclick', () => {
  vb = { ...home };
  apply();
});
"""


def responsive_svg(chart) -> str:
    """The chart as an SVG that scales uniformly with its container —
    geometry and text together, aspect preserved — via viewBox. Raises
    when vl-convert (a native wheel; absent under WASM) is missing, so
    callers can fall back to the interactive fixed-size chart."""
    import re as _re

    import altair as alt
    import vl_convert as vlc

    # the marimo data transformer stores data behind virtual-file URLs
    # vl-convert cannot fetch; inline it for the standalone render
    with alt.data_transformers.enable('default', max_rows=None):
        spec = chart.to_json()
    svg = vlc.vegalite_to_svg(spec)
    m = _re.search(r'<svg[^>]*>', svg)
    tag = m.group(0)
    w = _re.search(r'width="([\d.]+)"', tag)
    h = _re.search(r'height="([\d.]+)"', tag)
    new_tag = tag
    if w and h and 'viewBox' not in tag:
        new_tag = new_tag.replace(
            '<svg', f'<svg viewBox="0 0 {w.group(1)} {h.group(1)}"', 1)
    new_tag = _re.sub(r'\s(?:width|height)="[\d.]+"', '', new_tag)
    new_tag = new_tag.replace(
        '<svg', '<svg style="width: 100%; height: auto; display: block"',
        1)
    return svg.replace(tag, new_tag, 1)


def svg_diagram_iframe(chart) -> str:
    """The chart as a self-contained <iframe> of hand-driven
    interactive SVG: it tracks the container width at the diagram's
    true aspect ratio, and inside it the wheel zooms around the cursor,
    dragging pans, and a double-click resets — the same read-the-text
    affordance as the Vega chart's wheel zoom, with no external
    dependencies. Raises without vl-convert (the WASM build); callers
    fall back to the interactive fixed-size chart."""
    import html as _html
    import re as _re

    svg = responsive_svg(chart)
    vb = _re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    aspect = f'{vb.group(1)} / {vb.group(2)}' if vb else '3 / 1'
    doc = ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
           'html, body { margin: 0; padding: 0; overflow: hidden;'
           ' background: #fff; }'
           ' svg { cursor: grab; } svg.panning { cursor: grabbing; }'
           '</style></head><body>'
           + svg
           + '<script>' + _SVG_PANZOOM_JS + '</script></body></html>')
    return (f'<iframe srcdoc="{_html.escape(doc, quote=True)}" '
            f'style="width: 100%; aspect-ratio: {aspect}; '
            'border: none; display: block"></iframe>')


def circuit_chart(sim, has_run: bool = False, scale: float = 46.0,
                  width: int | None = None,
                  angle_overrides: dict | None = None):
    """The circuit as a layered Altair chart. With has_run, every port
    box contains its value block (rows and columns spread to make room),
    dangling valued outputs get stadium blobs past their stub wires, and
    the same values appear as hover tooltips. The chart renders at its
    natural width, capped at MAX_WIDTH (pass width to override).
    angle_overrides replaces a gate's angle-label text ({'φ': 'φ(x)'})."""
    spec = spec_from_simulation(sim)
    L = compute_layout(spec)
    routes = route_wires(spec, L)
    parsed = spec.topology['parsed']

    # after a run the boxes hold their value text: rows spread
    # vertically and columns horizontally to make room
    KY = 1.6 if has_run else 1.0
    KX = 1.8 if has_run else 1.0

    boxes, texts, wires, arrows, dots, stadiums = [], [], [], [], [], []
    frames = {}   # drawn gate/delay frame extents, for the stage boxes
    # scaled wire-endpoint -> x of the DRAWN box edge there, so wires and
    # arrowheads stop at the boundary even when a box grew for its text
    edge_clip = {}

    def clip_key(x, y):
        return (round(x, 3), round(y, 3))

    def value_lines(pos):
        if not has_run:
            return []
        block = pos_value_str(sim, pos)
        return [] if block is None else [_sub(ln) for ln in block.split('\n')]

    def measure(lines, min_w):
        h = 2 * PORT_PAD + LINE_H * max(1, len(lines))
        w = max(min_w, 2 * PORT_PAD + CHAR_W * max(len(ln) for ln in lines))
        return w, h

    def emit_box(cx, cy, w, h, lines, fill, stroke, corner=3, tip=()):
        tip = list(tip)
        pr = tip[1] if len(tip) > 1 else ''
        boxes.append(dict(x=cx - w / 2, x2=cx + w / 2,
                          y=cy - h / 2, y2=cy + h / 2,
                          fill=fill, stroke=stroke, corner=corner,
                          amp=tip[0] if tip else '',
                          pr=pr.removeprefix('Pr: ')))
        # Vega anchors a multi-line block by its first line: shift up so
        # the whole block centers in the box. The name line is bold;
        # value lines (if any) follow in a separate normal-weight block.
        top_y = cy + (len(lines) - 1) * LINE_H / 2
        texts.append(dict(x=cx, y=top_y, lines=[lines[0]], size=10,
                          color='#2b3442', weight='bold'))
        if len(lines) > 1:
            texts.append(dict(x=cx, y=top_y - LINE_H,
                          lines=lines[1:], size=10,
                          color='#333333', weight='normal'))

    def port_lines(name, pos=None, entry=None):
        vals = value_lines(pos) if pos else []
        if vals:
            return [name] + vals, vals
        if entry:
            return [name, entry], []
        return [name], []

    def entry_annotation(pos):
        # a particle entering the circuit here shows its signed weight,
        # as in the Mermaid diagrams
        src = sim.sources.get(pos)
        if src is not None and SEP not in src and src in sim.particles:
            import quantish.qnumber as qn
            w = qn.to_float(sim.particles[src].weight.real)
            return f'{_sub(src)} {w:+.{sim.precision}f}'
        return None

    # gates: header (name, angle, compass), ports, dotted X, frame
    inset = PORT_IN_DX * KX
    for gname, (gx, gy) in L.gate_xy.items():
        gdata = parsed.gates.get(gname, {})
        top = gy * KY
        left = gx * KX
        right = left + GATE_WIDTH * KX
        cx = (left + right) / 2
        # the header rides halfway with the row stretch, so the gap
        # between the angle text and the control box stays modest when
        # value blocks spread the rows
        KH = 1 + (KY - 1) * 0.5
        texts.append(dict(x=cx, y=top - 0.24 * KH, lines=[_sub(gname)],
                          size=13, color='#222222', weight='bold'))
        angle_text = ((angle_overrides or {}).get(gname)
                      or _sub(gdata.get('angle', '')))
        texts.append(dict(x=cx, y=top - 0.60 * KH, lines=[angle_text],
                          size=10, color='#777777', weight='normal'))
        deg = float(gdata.get('deg', 0.0))
        # compass needle: 0.75 of the gate width, centered vertically on
        # the two header text lines
        ccx = left + 0.75 * (right - left)
        ccy = top - 0.42 * KH
        dx_c, dy_c = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        wires.append([dict(route=f'{gname}~c', order=0,
                           x=ccx - 0.26 * dx_c, y=ccy - 0.26 * dy_c),
                      dict(route=f'{gname}~c', order=1,
                           x=ccx + 0.26 * dx_c, y=ccy + 0.26 * dy_c)])
        arrows.append(dict(x=ccx + 0.26 * dx_c, y=ccy + 0.26 * dy_c,
                           angle=(90 - deg) % 360))

        clines, ctip = port_lines('control', pos=f'{gname}{SEP}control',
                                  entry=entry_annotation(
                                      f'{gname}{SEP}control'))
        cw, ch = measure(clines, PORT_W)
        ccy_port = top + PORT_DY['control'] * KY
        emit_box(cx, ccy_port, cw, ch, clines,
                 PORT_FILL, PORT_STROKE, corner=2, tip=ctip)
        gcx = gx + GATE_WIDTH / 2
        edge_clip[clip_key((gcx - CONTROL_HALF_W) * KX, ccy_port)] = cx - cw / 2
        edge_clip[clip_key((gcx + CONTROL_HALF_W) * KX, ccy_port)] = cx + cw / 2

        # measure both switch rows first: the two in-boxes then share a
        # common right edge and the two out-boxes a common left edge, so
        # a narrow (empty) box lines up with its valued neighbor and the
        # dotted X below connects to every box
        rows = {}
        for wname in ('upper', 'lower'):
            pos = f'{gname}{SEP}{wname}'
            ilines, itip = port_lines(wname, entry=entry_annotation(pos))
            olines, otip = port_lines(wname, pos=pos)
            rows[wname] = (ilines, itip, measure(ilines, PORT_W),
                           olines, otip, measure(olines, PORT_W))
        in_right = left + inset + max(r[2][0] for r in rows.values())
        out_left = right - inset - max(r[5][0] for r in rows.values())
        low_h = ch
        for wname in ('upper', 'lower'):
            py = top + PORT_DY[wname] * KY
            ilines, itip, (iw, ih), olines, otip, (ow, oh) = rows[wname]
            emit_box(in_right - iw / 2, py, iw, ih, ilines,
                     PORT_FILL, PORT_STROKE, corner=2, tip=itip)
            edge_clip[clip_key((gx + PORT_IN_DX) * KX, py)] = in_right - iw
            emit_box(out_left + ow / 2, py, ow, oh, olines,
                     PORT_FILL, PORT_STROKE, corner=2, tip=otip)
            edge_clip[clip_key((gx + PORT_OUT_DX) * KX, py)] = out_left + ow
            low_h = oh
        # the gate frame wraps header and ports with an even margin
        bottom = top + PORT_DY['lower'] * KY - low_h / 2 - 0.3
        frames[gname] = (left, bottom, right, top)
        boxes.insert(0, dict(x=left, x2=right, y=bottom, y2=top,
                             fill=GATE_FILL, stroke=GATE_STROKE, corner=4,
                             amp='', pr=''))
        # dotted X between the switch port columns, box edge to box edge
        uy = top + PORT_DY['upper'] * KY
        ly = top + PORT_DY['lower'] * KY
        xin = in_right + 0.06
        xout = out_left - 0.06
        if xout > xin + 0.2:
            for i, (ya, yb) in enumerate(((uy, uy), (ly, ly),
                                          (uy, ly), (ly, uy))):
                dots.append([
                    dict(route=f'{gname}~x{i}', order=0, x=xin, y=ya),
                    dict(route=f'{gname}~x{i}', order=1, x=xout, y=yb)])

    # delay / pass-through boxes
    for dname, (dx_, dy_) in L.delay_xy.items():
        pos = f'{dname}{SEP}control'
        vals = value_lines(pos) if pos in parsed.links else []
        lines = ([_sub(dname)] + vals) if vals else [_sub(dname)]
        w, h = measure(lines, 2 * CONTROL_HALF_W)
        emit_box(dx_ * KX, dy_ * KY, w, h, lines, DELAY_FILL, DELAY_STROKE,
                 corner=3, tip=value_lines(pos))
        edge_clip[clip_key((dx_ - CONTROL_HALF_W) * KX, dy_ * KY)] = dx_ * KX - w / 2
        edge_clip[clip_key((dx_ + CONTROL_HALF_W) * KX, dy_ * KY)] = dx_ * KX + w / 2
        frames[dname] = (dx_ * KX - w / 2, dy_ * KY - h / 2,
                         dx_ * KX + w / 2, dy_ * KY + h / 2)

    # particles: stadium blobs sized to their names (a fixed circle
    # clips longer names like AIM_Figure12's control1/control2)
    for pname, (px, py) in L.particle_xy.items():
        sign = spec.topology['topo']['particle_signs'].get(pname, 1)
        label = f'{"+" if sign > 0 else "−"}{_sub(pname)}'
        pw = 2 * PORT_PAD + CHAR_W * (len(label) + 1)
        ph = 2 * PORT_PAD + LINE_H
        cx, cy = px * KX, py * KY
        boxes.append(dict(x=cx - pw / 2, x2=cx + pw / 2,
                          y=cy - ph / 2, y2=cy + ph / 2,
                          fill=PARTICLE_FILL, stroke=VALUE_STROKE,
                          corner=int(ph * scale / 2), amp='', pr=''))
        texts.append(dict(x=cx, y=cy, lines=[label],
                          size=11, color='#333333', weight='bold'))
        # the particle's wire starts at the blob: clip its first point
        # to the stadium's right edge
        edge_clip[clip_key((px + 0.4) * KX, cy)] = cx + pw / 2

    # stadium value blobs: a dangling output's value lands outside the
    # gate, past its stub wire (matching the Mermaid sinks). Only gates
    # in the last column have free space to their right; an interior
    # gate's dangling output keeps its value inside the out-port box.
    _wire_labels = getattr(sim, 'wire_labels', {})
    if has_run:
        last_col = max(L.col_of.values(), default=0)
        for gname, (gx, gy) in L.gate_xy.items():
            if L.col_of.get(gname) != last_col:
                continue
            for wname in ('upper', 'lower', 'control'):
                pos = f'{gname}{SEP}{wname}'
                if pos in parsed.links:
                    continue
                vals = value_lines(pos)
                if not vals:
                    continue
                lines = [wname] + vals
                w, h = measure(lines, 0)
                w += 0.3
                stub_end = (gx + GATE_WIDTH + WIRE_STUB_LEN) * KX
                cy = gy * KY + PORT_DY[wname] * KY
                blob_left = stub_end + 0.1
                stadiums.append(dict(x=blob_left, x2=blob_left + w,
                                     y=cy - h / 2, y2=cy + h / 2,
                                     corner=int(h * scale / 2)))
                # the wire reaches the blob: a labeled stub extends to
                # it via the clip map; an unlabeled dangling output gets
                # its own connector
                edge_clip[clip_key(stub_end, cy)] = blob_left
                if pos not in _wire_labels:
                    if wname == 'control':
                        raw = (gx + GATE_WIDTH / 2 + CONTROL_HALF_W) * KX
                    else:
                        raw = (gx + PORT_OUT_DX) * KX
                    px0 = edge_clip.get(clip_key(raw, cy), raw)
                    wires.append([dict(route=f'{pos}~blob', order=0,
                                       x=px0, y=cy),
                                  dict(route=f'{pos}~blob', order=1,
                                       x=blob_left, y=cy)])
                    arrows.append(dict(x=blob_left - 0.10, y=cy, angle=90))
                bx = stub_end + 0.1 + w / 2
                top_y = cy + (len(lines) - 1) * LINE_H / 2
                texts.append(dict(x=bx, y=top_y, lines=[wname], size=10,
                                  color='#2b3442', weight='bold'))
                texts.append(dict(x=bx, y=top_y - LINE_H, lines=vals,
                                  size=10, color='#333333',
                                  weight='normal'))

    # wires, arrowheads, wire labels (scaled by KX/KY)
    CHAMFER = 0.12
    for i, r in enumerate(routes):
        if len(r.points) < 2:
            continue
        pts = [(x * KX, y * KY) for x, y in r.points]
        # stop at the drawn box edge, even when the box grew for text
        first, last = clip_key(*pts[0]), clip_key(*pts[-1])
        if first in edge_clip:
            pts[0] = (edge_clip[first], pts[0][1])
        if last in edge_clip:
            pts[-1] = (edge_clip[last], pts[-1][1])
        # round interior corners: a small quadratic bezier through each
        # corner, sampled into the polyline
        if len(pts) > 2:
            rounded = [pts[0]]
            for a, b, c in zip(pts, pts[1:], pts[2:]):
                ins, outs = [], []
                for (ox, oy), acc in ((a, ins), (c, outs)):
                    dxs, dys = ox - b[0], oy - b[1]
                    d = math.hypot(dxs, dys) or 1.0
                    k = min(CHAMFER, d / 2) / d
                    acc.append((b[0] + dxs * k, b[1] + dys * k))
                (p1x, p1y), (p2x, p2y) = ins[0], outs[0]
                rounded.append((p1x, p1y))
                for s in (0.25, 0.5, 0.75):
                    u = 1 - s
                    rounded.append((u * u * p1x + 2 * u * s * b[0] + s * s * p2x,
                                    u * u * p1y + 2 * u * s * b[1] + s * s * p2y))
                rounded.append((p2x, p2y))
            rounded.append(pts[-1])
            pts = rounded
        wires.append([dict(route=f'w{i}', order=j, x=x, y=y)
                      for j, (x, y) in enumerate(pts)])
        # arrowhead: tip meets the boundary, so back its center off a bit
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        seg = math.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / seg, (y2 - y1) / seg
        ang = math.degrees(math.atan2(uy, ux))
        arrows.append(dict(x=x2 - 0.10 * ux, y=y2 - 0.10 * uy,
                           angle=(90 - ang) % 360))
        if r.label:
            if r.label_at is not None:
                lx, ly = r.label_at
                lx *= KX
                ly *= KY
                # clear of the neighboring stage-box border: push away
                # from whichever end the label hugs
                if r.label_side == 'dst':
                    lx -= 0.30
                elif r.label_side == 'src':
                    lx += 0.30
            else:
                best = None
                for (ax, ay), (bx, by) in zip(r.points, r.points[1:]):
                    if abs(ay - by) < 0.01 and (best is None
                                                or abs(bx - ax) > best[0]):
                        best = (abs(bx - ax), (ax + bx) / 2, ay)
                if best is None:
                    continue
                _, lx, ly = best
                lx *= KX
                ly *= KY
            texts.append(dict(x=lx, y=ly + 0.22,
                              lines=[_sub(r.label)], size=10,
                              color='#222222', weight='normal'))

    # stage boxes and labels, wrapping the frames as actually drawn
    # small enough that adjacent stage boxes (e.g. a delay-only stage
    # like the double-slit's slits/phase next to a gate stage) never
    # overlap their neighbors
    GROUP_PAD = 0.18
    for members, label in zip(parsed.stage_gates, parsed.stage_names):
        rects = [frames[m] for m in members if m in frames]
        if not rects:
            continue
        gx1 = min(r[0] for r in rects) - GROUP_PAD
        gy1 = min(r[1] for r in rects) - GROUP_PAD
        gx2 = max(r[2] for r in rects) + GROUP_PAD
        gy2 = max(r[3] for r in rects) + GROUP_PAD
        boxes.insert(0, dict(x=gx1, x2=gx2, y=gy1, y2=gy2,
                             fill=STAGE_FILL, stroke=STAGE_STROKE,
                             corner=6, amp='', pr=''))
        texts.append(dict(x=(gx1 + gx2) / 2, y=gy2 + 0.28, lines=[label],
                          size=11, color='#888888', weight='normal'))

    # ---- assemble ----
    x0, y0, x1, y1 = L.bounds
    x0 *= KX
    x1 *= KX
    y0 *= KY
    y1 *= KY
    for row in boxes + stadiums:
        x0, x1 = min(x0, row['x']), max(x1, row['x2'])
        y0, y1 = min(y0, row['y']), max(y1, row['y2'])
    for p in (p for seg in wires for p in seg):
        x0, x1 = min(x0, p['x']), max(x1, p['x'])
        y0, y1 = min(y0, p['y']), max(y1, p['y'])
    pad = 0.4
    xscale = alt.Scale(domain=[x0 - pad, x1 + pad])
    yscale = alt.Scale(domain=[y0 - pad, y1 + pad])
    xe = alt.X('x:Q', scale=xscale, axis=None)
    ye = alt.Y('y:Q', scale=yscale, axis=None)
    # natural_px is the width at which geometry and font sizes match
    # exactly; the rendered width never exceeds MAX_WIDTH (or the
    # caller's explicit width), and a smaller circuit keeps its natural
    # size — never stretched, which would distort the drawn angles
    x_extent = x1 - x0 + 2 * pad
    natural_px = x_extent * scale
    if width is None:
        width = int(min(natural_px, MAX_WIDTH))
    # keep the drawn aspect ratio true: when a circuit is wider than
    # its rendered width, shrink the height by the same factor, so
    # boxes and their contents are not stretched tall
    fit = min(1.0, width / natural_px)
    height = int((y1 - y0 + 2 * pad) * scale * fit)
    # pixel-sized glyphs (text, arrowheads, particle dots) don't follow
    # the scales, so two live factors are applied to their sizes:
    # WF — how far the container squeezes the natural width (never
    # enlarged past 1), via vega's view-width signal; ZF — the current
    # wheel-zoom relative to the initial x domain
    zoom = alt.selection_interval(bind='scales', name='zoomsel')
    WF = f'min(1, width / {natural_px:.1f})'
    ZF = (f'(isValid(zoomsel_x) ? {x_extent:.5f}'
          ' / abs(zoomsel_x[1] - zoomsel_x[0]) : 1)')

    def rect_layer(df, radius, tooltips=False):
        enc = dict(x=alt.X('x:Q', scale=xscale, axis=None), x2='x2:Q',
                   y=alt.Y('y:Q', scale=yscale, axis=None), y2='y2:Q',
                   fill=alt.Fill('fill:N', scale=None),
                   stroke=alt.Stroke('stroke:N', scale=None))
        if tooltips:
            enc['tooltip'] = [alt.Tooltip('amp:N', title='amplitude'),
                              alt.Tooltip('pr:N', title='Pr')]
        return alt.Chart(df).mark_rect(
            strokeWidth=1, cornerRadius=radius).encode(**enc)

    # rounded corners per box class (cornerRadius is a mark constant,
    # so each radius gets its own layer; insertion order is preserved
    # within a radius class, stages first). Only boxes that actually
    # hold a value get a tooltip; the rest stay hover-silent.
    box_df = pd.DataFrame(boxes)
    layers = []
    for r in sorted(box_df.corner.unique(), reverse=True):
        cls = box_df[box_df.corner == r]
        for valued in (False, True):
            sel = cls[(cls.amp != '') == valued]
            if len(sel):
                layers.append(rect_layer(sel, int(r * 1.5),
                                         tooltips=valued and has_run))

    if stadiums:
        st_df = pd.DataFrame(stadiums)
        layers.append(alt.Chart(st_df).mark_rect(
            strokeWidth=1, fill=VALUE_FILL, stroke=VALUE_STROKE,
            cornerRadius=int(st_df.corner.max())).encode(
            x=alt.X('x:Q', scale=xscale, axis=None), x2='x2:Q',
            y=alt.Y('y:Q', scale=yscale, axis=None), y2='y2:Q'))

    # No order channel: the rows are emitted in drawing order, and a
    # line mark follows data order within each detail group. (An
    # explicit order field breaks under marimo's CSV data transformer,
    # which delivers it as strings — "10" sorts before "2".)
    layers.append(alt.Chart(pd.DataFrame(
        [p for seg in dots for p in seg])).mark_line(
        color='#000000', strokeWidth=1.0, strokeDash=[3, 3]).encode(
        x=xe, y=ye, detail='route:N'))
    layers.append(alt.Chart(pd.DataFrame(
        [p for seg in wires for p in seg])).mark_line(
        color=WIRE_COLOR, strokeWidth=1.3).encode(
        x=xe, y=ye, detail='route:N'))
    layers.append(alt.Chart(pd.DataFrame(arrows)).mark_point(
        shape='triangle', filled=True, color=WIRE_COLOR).encode(
        x=xe, y=ye, angle=alt.Angle('angle:Q', scale=None),
        size=alt.value(alt.expr(f'45 * pow({WF} * {ZF}, 2)'))))
    text_rows = []
    for tx in texts:
        for k, line in enumerate(tx['lines']):
            text_rows.append(dict(x=tx['x'], y=tx['y'] - k * LINE_H,
                                  text=line, size=tx['size'],
                                  color=tx['color'], weight=tx['weight']))
    text_df = pd.DataFrame(text_rows)
    for weight in ('normal', 'bold'):
        by_weight = text_df[text_df.weight == weight]
        for fsize in sorted(by_weight['size'].unique()):
            sel = by_weight[by_weight['size'] == fsize]
            layers.append(alt.Chart(sel).mark_text(
                fontWeight=weight, baseline='middle').encode(
                x=xe, y=ye, text='text:N',
                size=alt.value(alt.expr(f'{fsize} * {WF} * {ZF}')),
                color=alt.Color('color:N', scale=None)))

    chart = alt.layer(*layers).properties(width=width, height=height)
    if getattr(sim, 'caption', ''):
        # wrap the title: vega titles are single-line, and a long
        # caption would silently widen the canvas past the chart width
        # (the mystery horizontal scrollbar)
        title_lines = textwrap.wrap(
            f'{sim.title} — {strip_markdown(sim.caption)}',
            width=max(20, int(width / 7)))
        chart = chart.properties(title=alt.TitleParams(
            text=title_lines, fontSize=13, anchor='start',
            fontWeight='bold'))
    return (chart.configure_view(stroke=None)
            .configure(background='white').add_params(zoom))
