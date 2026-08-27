"""Circuit diagram layout: the geometry every renderer draws from.

Same skeleton as the TikZ renderer — spec_from_simulation,
compute_layout and route_wires supply the columns, rows and wire
polylines — flattened here into plain JSON-serializable geometry for
the native SVG presenters (the app widget and the file exporter).
Styling follows the Mermaid diagrams:
white background, pale yellow stage boxes, pale blue gate boxes,
lavender port boxes whose values (after a run) sit INSIDE the box, and
stadium-shaped value blobs where a dangling output's value lands
outside any gate.
"""
import math
import re
from bisect import bisect_right
import textwrap

from quantish.display import pos_value_str, strip_markdown
from quantish.tikz_diagram import (CONTROL_HALF_W, GATE_WIDTH, PORT_DY,
                                   PORT_IN_DX, PORT_OUT_DX, PORT_W,
                                   WIRE_STUB_LEN,
                                   compute_layout, route_wires,
                                   spec_from_simulation)
from quantish.util import (angle_label, fmt_label, math_runs,
                           math_to_unicode, unicode_runs, SEP)

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

LINE_H = 0.26           # height of one text line, in layout units
PORT_PAD = 0.14         # padding inside port boxes
CHAR_W = 0.115          # approx character width at the value font size


def _sub(s) -> str:
    return fmt_label(s)


def diagram_geometry(sim, has_run: bool = False, scale: float = 46.0,
                     angle_overrides: dict | None = None,
                     show_values: bool | None = None) -> dict:
    """Everything the circuit drawing is made of, as plain
    JSON-serializable lists in layout coordinates (y grows upward):
    boxes (fill/stroke/corner px, hover amp/Pr), texts (multi-line
    blocks anchored on their first line, line_h apart), wires and dots
    (polylines), arrows (position + clockwise angle, 0 = up), stadiums,
    and the padded bounds. One geometry, two presenters: the app's
    native SVG widget (builder_widget.DiagramWidget) and the file
    exporter (svg_export.diagram_svg).

    show_values (default: has_run) separates layout from display: with
    has_run=True, show_values=False the geometry is laid out exactly
    as the results view — boxes sized and placed for their value
    blocks — but the values themselves stay hidden, so the only
    visible change when they appear is the values themselves."""
    if show_values is None:
        show_values = has_run
    spec = spec_from_simulation(sim)
    L = compute_layout(spec)
    routes = route_wires(spec, L)
    parsed = spec.topology['parsed']

    # after a run the boxes hold their value text: rows spread
    # vertically and columns horizontally to make room
    KY = 1.6 if has_run else 1.0
    KX = 1.8 if has_run else 1.0
    # Horizontal positions go through fx(), a piecewise-linear map:
    # gate columns always stretch by KX (their port boxes hold value
    # text), but a gap whose crossing wires are all straight
    # horizontals needs no fan room and stays tight. Gaps holding a
    # delay box or particle blob keep full width for the box itself.
    KX_TIGHT = min(KX, 0.7)

    def _x_map():
        cols = sorted((gx, gx + GATE_WIDTH)
                      for gx, _ in L.gate_xy.values())
        merged = []
        for a, b in cols:
            if merged and a <= merged[-1][1] + 1e-9:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        soft = ([x for x, _ in L.delay_xy.values()]
                + [x for x, _ in L.particle_xy.values()])
        segs = []
        for i, (a, b) in enumerate(merged):
            segs.append((a, b, KX))
            if i + 1 < len(merged):
                ga, gb = b, merged[i + 1][0]
                straight = all(
                    abs(y1 - y2) < 1e-9
                    for r in routes
                    for (x1, y1), (x2, y2) in zip(r.points, r.points[1:])
                    if min(x1, x2) < gb - 1e-6 and max(x1, x2) > ga + 1e-6)
                occupied = any(ga - 1e-6 < x < gb + 1e-6 for x in soft)
                segs.append((ga, gb,
                             KX_TIGHT if straight and not occupied else KX))
        if not segs:
            return lambda x: x * KX
        nodes_x, nodes_fx = [segs[0][0]], [segs[0][0] * KX]
        for a, b, f in segs:
            nodes_x.append(b)
            nodes_fx.append(nodes_fx[-1] + (b - a) * f)
        def fx(x):
            if x <= nodes_x[0]:
                return nodes_fx[0] + (x - nodes_x[0]) * KX
            if x >= nodes_x[-1]:
                return nodes_fx[-1] + (x - nodes_x[-1]) * KX
            i = bisect_right(nodes_x, x) - 1
            a, b = nodes_x[i], nodes_x[i + 1]
            u = (x - a) / (b - a) if b > a else 0.0
            return nodes_fx[i] + u * (nodes_fx[i + 1] - nodes_fx[i])
        return fx

    fx = _x_map()

    boxes, texts, wires, arrows, dots, stadiums = [], [], [], [], [], []
    frames = {}   # drawn gate/delay frame extents, for the stage boxes
    # scaled wire-endpoint -> x of the DRAWN box edge there, so wires and
    # arrowheads stop at the boundary even when a box grew for its text
    edge_clip = {}
    # scaled wire-endpoint -> corrected y, for delay boxes drawn away
    # from their layout row (the tuck-in below)
    delay_y_new = {}

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

    def emit_box(cx, cy, w, h, lines, fill, stroke, corner=3, tip=(),
                 shown=None):
        # `lines` sized the box; `shown` (default: lines) is what is
        # actually written into it — the values-hidden view keeps the
        # box exactly where and how big the values view needs it
        if shown is None or show_values:
            shown = lines
        tip = list(tip) if show_values else []
        pr = tip[1] if len(tip) > 1 else ''
        boxes.append(dict(x=cx - w / 2, x2=cx + w / 2,
                          y=cy - h / 2, y2=cy + h / 2,
                          fill=fill, stroke=stroke, corner=corner,
                          amp=tip[0] if tip else '',
                          pr=pr.removeprefix('Pr: ')))
        # a multi-line block anchors on its first line: shift up so
        # the whole block centers in the box. The name line is bold;
        # value lines (if any) follow in a separate normal-weight block.
        top_y = cy + (len(shown) - 1) * LINE_H / 2
        texts.append(dict(x=cx, y=top_y, lines=[shown[0]], size=10,
                          color='#2b3442', weight='bold'))
        if len(shown) > 1:
            texts.append(dict(x=cx, y=top_y - LINE_H,
                          lines=shown[1:], size=10,
                          color='#333333', weight='normal'))

    def port_lines(name, pos=None, entry=None):
        # full lines (for sizing and the values view), the hover tip,
        # and the values-hidden display (name, plus the entry
        # annotation a pre-run port shows)
        vals = value_lines(pos) if pos else []
        hidden = [name, entry] if entry else [name]
        if vals:
            return [name] + vals, vals, hidden
        return hidden, [], hidden

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
        left = fx(gx)
        right = fx(gx + GATE_WIDTH)
        cx = (left + right) / 2
        # the header rides halfway with the row stretch, so the gap
        # between the angle text and the control box stays modest when
        # value blocks spread the rows
        KH = 1 + (KY - 1) * 0.5
        texts.append(dict(x=cx, y=top - 0.24 * KH, lines=[_sub(gname)],
                          size=13, color='#222222', weight='bold'))
        angle_text = ((angle_overrides or {}).get(gname)
                      or _sub(gdata.get('angle', '')))
        _gph = getattr(sim.gates.get(gname), 'phase', None)
        if (_gph is not None and abs(complex(_gph.v)) > 1e-12
                and gname not in (angle_overrides or {})):
            _phspec = ((sim.config.get('gates', {}).get(gname) or {})
                       .get('phase', 0))
            angle_text += ', φ ' + _sub(
                angle_label(_phspec, float(_gph.degrees), '°'))
        texts.append(dict(x=cx, y=top - 0.60 * KH, lines=[angle_text],
                          size=10, color='#777777', weight='normal'))
        deg = float(gdata.get('deg', 0.0))
        # compass needle: just to the right of the gate name, anchored
        # to the name's own position so it sits identically before and
        # after a run
        ccx = cx + 0.115 * (len(gname) + 1) / 2 + 0.45
        ccy = top - 0.24 * KH
        dx_c, dy_c = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        wires.append([dict(route=f'{gname}~c', order=0,
                           x=ccx - 0.26 * dx_c, y=ccy - 0.26 * dy_c),
                      dict(route=f'{gname}~c', order=1,
                           x=ccx + 0.26 * dx_c, y=ccy + 0.26 * dy_c)])
        arrows.append(dict(x=ccx + 0.26 * dx_c, y=ccy + 0.26 * dy_c,
                           angle=(90 - deg) % 360))

        clines, ctip, chid = port_lines(
            'control', pos=f'{gname}{SEP}control',
            entry=entry_annotation(f'{gname}{SEP}control'))
        cw, ch = measure(clines, PORT_W)
        ccy_port = top + PORT_DY['control'] * KY
        emit_box(cx, ccy_port, cw, ch, clines,
                 PORT_FILL, PORT_STROKE, corner=2, tip=ctip, shown=chid)
        gcx = gx + GATE_WIDTH / 2
        edge_clip[clip_key(fx(gcx - CONTROL_HALF_W), ccy_port)] = cx - cw / 2
        edge_clip[clip_key(fx(gcx + CONTROL_HALF_W), ccy_port)] = cx + cw / 2

        # measure both switch rows first: the two in-boxes then share a
        # common right edge and the two out-boxes a common left edge, so
        # a narrow (empty) box lines up with its valued neighbor and the
        # dotted X below connects to every box
        rows = {}
        for wname in ('upper', 'lower'):
            pos = f'{gname}{SEP}{wname}'
            ilines, itip, ihid = port_lines(wname,
                                            entry=entry_annotation(pos))
            olines, otip, ohid = port_lines(wname, pos=pos)
            rows[wname] = (ilines, itip, measure(ilines, PORT_W), ihid,
                           olines, otip, measure(olines, PORT_W), ohid)
        in_right = left + inset + max(r[2][0] for r in rows.values())
        out_left = right - inset - max(r[6][0] for r in rows.values())
        low_h = ch
        for wname in ('upper', 'lower'):
            py = top + PORT_DY[wname] * KY
            (ilines, itip, (iw, ih), ihid,
             olines, otip, (ow, oh), ohid) = rows[wname]
            emit_box(in_right - iw / 2, py, iw, ih, ilines,
                     PORT_FILL, PORT_STROKE, corner=2, tip=itip,
                     shown=ihid)
            edge_clip[clip_key(fx(gx + PORT_IN_DX), py)] = in_right - iw
            emit_box(out_left + ow / 2, py, ow, oh, olines,
                     PORT_FILL, PORT_STROKE, corner=2, tip=otip,
                     shown=ohid)
            edge_clip[clip_key(fx(gx + PORT_OUT_DX), py)] = out_left + ow
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
        _ph = getattr(sim.gates.get(dname), 'phase', None)
        _is_plate = _ph is not None and abs(complex(_ph.v)) > 1e-12
        if _is_plate:
            # a phase plate: its phase — and the resulting aggregate
            # angle of what passed through — are the whole story;
            # magnitudes are unaffected (full values stay on hover)
            _override = (angle_overrides or {}).get(dname)
            _spec = ((sim.config.get('gates', {}).get(dname) or {})
                     .get('phase', 0))
            _angles = re.findall(r'∠\S+', ' '.join(vals))
            vals = ([_override if _override
                     else _sub(angle_label(_spec, float(_ph.degrees),
                                           '°'))]
                    + _angles)
        lines = ([_sub(dname)] + vals) if vals else [_sub(dname)]
        w, h = measure(lines, 2 * CONTROL_HALF_W)
        if _is_plate:
            # the compass needle sits to the right of the name inside
            # the box — widen the box so the needle never pokes out
            _needle_ext = 0.115 * (len(dname) + 1) / 2 + 0.38 + 0.22
            w = max(w, 2 * (_needle_ext + 0.12))
        # A delay sharing its column with gates tucks in just below the
        # lowest gate frame: scaling its layout row by KY would open a
        # gate-sized chasm (the row pitch stretches, the small box does
        # not). Delay-only columns keep their inline wire-level y.
        _cy = dy_ * KY
        _col = L.col_of.get(dname)
        _mates = [frames[g] for g in L.gate_xy
                  if L.col_of.get(g) == _col and g in frames]
        if _mates:
            _cy = min(f[1] for f in _mates) - 0.45 - h / 2
        emit_box(fx(dx_), _cy, w, h, lines, DELAY_FILL, DELAY_STROKE,
                 corner=3, tip=value_lines(pos), shown=[_sub(dname)])
        if _is_plate:
            # the same compass needle full gates carry, angled by the
            # phase, just to the right of the plate's name (the name is
            # the first display line, centered in the box)
            _deg = float(_ph.degrees)
            _ncx = fx(dx_) + 0.115 * (len(dname) + 1) / 2 + 0.38
            _ncy = _cy + (len(lines) - 1) * LINE_H / 2
            _dxc, _dyc = (math.cos(math.radians(_deg)),
                          math.sin(math.radians(_deg)))
            wires.append([dict(route=f'{dname}~c', order=0,
                               x=_ncx - 0.22 * _dxc,
                               y=_ncy - 0.22 * _dyc),
                          dict(route=f'{dname}~c', order=1,
                               x=_ncx + 0.22 * _dxc,
                               y=_ncy + 0.22 * _dyc)])
            arrows.append(dict(x=_ncx + 0.22 * _dxc,
                               y=_ncy + 0.22 * _dyc,
                               angle=(90 - _deg) % 360))
        edge_clip[clip_key(fx(dx_ - CONTROL_HALF_W), dy_ * KY)] = fx(dx_) - w / 2
        edge_clip[clip_key(fx(dx_ + CONTROL_HALF_W), dy_ * KY)] = fx(dx_) + w / 2
        # wires still aim at the layout row's y; steer their endpoints
        # to the tucked-in box, dropping/rising OUTSIDE the column's
        # gate frames so the vertical runs clear the stage box
        if _cy != dy_ * KY:
            _all_frames = _mates + [(fx(dx_) - w / 2, 0,
                                     fx(dx_) + w / 2, 0)]
            # clear of the frames plus the stage box's GROUP_PAD
            _safe_l = min(f[0] for f in _all_frames) - 0.48
            _safe_r = max(f[2] for f in _all_frames) + 0.48
            delay_y_new[clip_key(fx(dx_ - CONTROL_HALF_W), dy_ * KY)] = \
                (_cy, dy_ * KY, _safe_l, _safe_r)
            delay_y_new[clip_key(fx(dx_ + CONTROL_HALF_W), dy_ * KY)] = \
                (_cy, dy_ * KY, _safe_l, _safe_r)
        frames[dname] = (fx(dx_) - w / 2, _cy - h / 2,
                         fx(dx_) + w / 2, _cy + h / 2)

    # particles: stadium blobs sized to their names (a fixed circle
    # clips longer names like AIM_Figure12's control1/control2)
    for pname, (px, py) in L.particle_xy.items():
        sign = spec.topology['topo']['particle_signs'].get(pname, 1)
        label = f'{"+" if sign > 0 else "−"}{_sub(pname)}'
        pw = 2 * PORT_PAD + CHAR_W * (len(label) + 1)
        ph = 2 * PORT_PAD + LINE_H
        cx, cy = fx(px), py * KY
        boxes.append(dict(x=cx - pw / 2, x2=cx + pw / 2,
                          y=cy - ph / 2, y2=cy + ph / 2,
                          fill=PARTICLE_FILL, stroke=VALUE_STROKE,
                          corner=int(ph * scale / 2), amp='', pr=''))
        texts.append(dict(x=cx, y=cy, lines=[label],
                          size=11, color='#333333', weight='bold'))
        # the particle's wire starts at the blob: clip its first point
        # to the stadium's right edge
        edge_clip[clip_key(fx(px + 0.4), cy)] = cx + pw / 2

    # stadium value blobs: a dangling output's value lands outside the
    # gate, past its stub wire (matching the Mermaid sinks). Only gates
    # in the last column have free space to their right; an interior
    # gate's dangling output keeps its value inside the out-port box.
    #
    # The blobs appear together with the values: empty outlines in the
    # values-hidden view told too much of the story. Flip
    # BLOBS_WITH_VALUES_ONLY to False to bring the empty outlines (and
    # their port-name headers) back into that view.
    BLOBS_WITH_VALUES_ONLY = True
    _wire_labels = getattr(sim, 'wire_labels', {})
    if has_run and (show_values or not BLOBS_WITH_VALUES_ONLY):
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
                stub_end = fx(gx + GATE_WIDTH + WIRE_STUB_LEN)
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
                        raw = fx(gx + GATE_WIDTH / 2 + CONTROL_HALF_W)
                    else:
                        raw = fx(gx + PORT_OUT_DX)
                    px0 = edge_clip.get(clip_key(raw, cy), raw)
                    wires.append([dict(route=f'{pos}~blob', order=0,
                                       x=px0, y=cy),
                                  dict(route=f'{pos}~blob', order=1,
                                       x=blob_left, y=cy)])
                    arrows.append(dict(x=blob_left - 0.10, y=cy, angle=90))
                bx = stub_end + 0.1 + w / 2
                shown = lines if show_values else [wname]
                top_y = cy + (len(shown) - 1) * LINE_H / 2
                texts.append(dict(x=bx, y=top_y, lines=[wname], size=10,
                                  color='#2b3442', weight='bold'))
                if show_values:
                    texts.append(dict(x=bx, y=top_y - LINE_H, lines=vals,
                                      size=10, color='#333333',
                                      weight='normal'))

    # wires, arrowheads, wire labels (scaled by KX/KY)
    CHAMFER = 0.12
    for i, r in enumerate(routes):
        if len(r.points) < 2:
            continue
        pts = [(fx(x), y * KY) for x, y in r.points]
        # stop at the drawn box edge, even when the box grew for text
        first, last = clip_key(*pts[0]), clip_key(*pts[-1])
        if first in edge_clip:
            pts[0] = (edge_clip[first], pts[0][1])
        if last in edge_clip:
            pts[-1] = (edge_clip[last], pts[-1][1])
        if last in delay_y_new:
            # incoming wire: run at the source's level, drop down left
            # of the column's frames (outside the stage box), then in
            new_y, old_y, safe_l, _ = delay_y_new[last]
            p0, pe = pts[0], pts[-1]
            pts = ([p0] +
                   ([] if abs(p0[1] - new_y) < 1e-6 else
                    [(safe_l, p0[1]), (safe_l, new_y)]) +
                   [(pe[0], new_y)])
        if first in delay_y_new:
            # outgoing wire: leave at box level, rise right of the
            # frames, then continue at the destination's level
            new_y, old_y, _, safe_r = delay_y_new[first]
            p0, pe = pts[0], pts[-1]
            pts = ([(p0[0], new_y)] +
                   ([] if abs(pe[1] - new_y) < 1e-6 else
                    [(safe_r, new_y), (safe_r, pe[1])]) +
                   [pe])
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
                lx = fx(lx)
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
                lx = fx(lx)
                ly *= KY
            texts.append(dict(x=lx, y=ly + 0.22,
                              lines=[math_to_unicode(r.label)], size=10,
                              color='#222222', weight='normal',
                              runs=[math_runs(r.label)]))

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
        texts.append(dict(x=(gx1 + gx2) / 2, y=gy2 + 0.28,
                          lines=[_sub(label)],
                          size=11, color='#888888', weight='normal'))

    # every text with unicode sub/superscript glyphs gains runs, so
    # the renderers draw ALL scripts as shifted tspans — one style for
    # wire labels, value blocks, gate names, and stage labels alike
    for tx in texts:
        if 'runs' in tx:
            continue
        rr = [unicode_runs(ln) for ln in tx['lines']]
        if any(lvl for line in rr for _, lvl in line):
            tx['runs'] = rr

    # ---- assemble ----
    x0, y0, x1, y1 = L.bounds
    x0 = fx(x0)
    x1 = fx(x1)
    y0 *= KY
    y1 *= KY
    for row in boxes + stadiums:
        x0, x1 = min(x0, row['x']), max(x1, row['x2'])
        y0, y1 = min(y0, row['y']), max(y1, row['y2'])
    for p in (p for seg in wires for p in seg):
        x0, x1 = min(x0, p['x']), max(x1, p['x'])
        y0, y1 = min(y0, p['y']), max(y1, p['y'])
    pad = 0.4
    return dict(boxes=boxes, texts=texts, wires=wires, arrows=arrows,
                dots=dots, stadiums=stadiums, line_h=LINE_H,
                wire_color=WIRE_COLOR, value_fill=VALUE_FILL,
                value_stroke=VALUE_STROKE, scale=scale,
                x0=x0 - pad, y0=y0 - pad, x1=x1 + pad, y1=y1 + pad)
