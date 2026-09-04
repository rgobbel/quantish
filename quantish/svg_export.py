"""Static SVG renderings of the native diagrams, for file export.

These are Python ports of the drawing halves of the app widgets
(builder_widget's DiagramWidget and NetworkGraphWidget ESMs): the same
geometry sources — diagram_layout.diagram_geometry and
NetworkGraph.build_model — drawn to standalone SVG text with no
interactivity. PNG/PDF come from rasterizing this SVG (vl-convert's
svg_to_png / svg_to_pdf).
"""
import math
from xml.sax.saxutils import escape


# Sub/superscript runs as tspans shifted with dy, mirroring the
# widget's appendRuns: WebKit (Safari, every iPhone browser) ignores a
# percentage baseline-shift and lands subscripts as superscripts, so
# the shift is an explicit dy in user units, undone by the next run.
SCRIPT_SIZE, SUB_DROP, SUP_RAISE = 0.64, 0.25, 0.38
# Text sits on the default alphabetic baseline, this fraction of the
# font size below its intended visual center — no dominant-baseline,
# which iOS Safari mishandles (the widget's BASELINE_CENTER).
BASELINE_CENTER = 0.3


def script_spans(runs, font_size):
    """tspan markup for [(frag, lvl), ...] (lvl -1/0/+1) inside a text
    element of `font_size` user units."""
    cur = 0.0
    for frag, lvl in runs:
        want = (SUB_DROP * font_size if lvl < 0
                else -SUP_RAISE * font_size if lvl > 0 else 0.0)
        attrs = ''
        if want != cur:
            attrs += f' dy="{want - cur:.4g}"'
        if lvl:
            attrs += f' font-size="{SCRIPT_SIZE:.0%}"'
        yield f'<tspan{attrs}>{escape(frag)}</tspan>'
        cur = want


def _el(tag, /, text=None, **attrs):
    parts = ''.join(f' {k.replace("_", "-")}="{v}"'
                    for k, v in attrs.items())
    if text is None:
        return f'<{tag}{parts}/>'
    return f'<{tag}{parts}>{escape(str(text))}</{tag}>'


def diagram_svg(g: dict) -> str:
    """The circuit diagram geometry as standalone SVG (the widget's
    natural scale; the full padded extent, no zoom viewport)."""
    S = g['scale']
    x0, y0, x1, y1 = g['x0'], g['y0'], g['x1'], g['y1']
    W, H = x1 - x0, y1 - y0

    def fy(y):
        return y1 - y

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'viewBox="{x0:g} 0 {W:g} {H:g}" '
           f'width="{W * S:g}" height="{H * S:g}" '
           f'font-family="sans-serif">',
           _el('rect', x=f'{x0:g}', y='0', width=f'{W:g}',
               height=f'{H:g}', fill='#ffffff')]
    stadiums = [dict(s, fill=g['value_fill'], stroke=g['value_stroke'])
                for s in g.get('stadiums', [])]
    for b in g['boxes'] + stadiums:
        hgt = b['y2'] - b['y']
        out.append(_el(
            'rect', x=f"{b['x']:.4g}", y=f"{fy(b['y2']):.4g}",
            width=f"{b['x2'] - b['x']:.4g}", height=f'{hgt:.4g}',
            rx=f"{min(b['corner'] * 1.5 / S, hgt / 2):.4g}",
            fill=b['fill'], stroke=b['stroke'],
            stroke_width=f'{1.2 / S:.4g}'))
    for seg in g.get('dots', []):
        pts = ' '.join(f"{p['x']:.4g},{fy(p['y']):.4g}" for p in seg)
        out.append(_el('polyline', points=pts, fill='none',
                       stroke='#000000', stroke_width=f'{1 / S:.4g}',
                       stroke_dasharray=f'{3 / S:.4g} {3 / S:.4g}'))
    for seg in g.get('wires', []):
        pts = ' '.join(f"{p['x']:.4g},{fy(p['y']):.4g}" for p in seg)
        out.append(_el('polyline', points=pts, fill='none',
                       stroke=g['wire_color'],
                       stroke_width=f'{1.3 / S:.4g}'))
    for a in g.get('arrows', []):
        s = 5.4 / S
        out.append(_el(
            'path',
            d=f'M 0 {-s:.4g} L {0.62 * s:.4g} {0.55 * s:.4g} '
              f'L {-0.62 * s:.4g} {0.55 * s:.4g} Z',
            fill=g['wire_color'],
            transform=f"translate({a['x']:.4g} {fy(a['y']):.4g}) "
                      f"rotate({a['angle']:g})"))
    for tx in g.get('texts', []):
        for k, line in enumerate(tx['lines']):
            attrs = dict(x=f"{tx['x']:.4g}",
                         y=f"{fy(tx['y'] - k * g['line_h']) + BASELINE_CENTER * tx['size'] / S:.4g}",
                         text_anchor='middle',
                         font_size=f"{tx['size'] / S:.4g}",
                         font_weight=tx['weight'], fill=tx['color'])
            runs = (tx.get('runs') or [None] * len(tx['lines']))[k]
            if runs and any(lvl for _, lvl in runs):
                spans = ''.join(script_spans(runs, tx['size'] / S))
                parts = ''.join(f' {a.replace("_", "-")}="{v}"'
                                for a, v in attrs.items())
                out.append(f'<text{parts}>{spans}</text>')
            else:
                out.append(_el('text', text=line, **attrs))
    out.append('</svg>')
    return '\n'.join(out)


def network_graph_svg(m: dict) -> str:
    """The weight-evolution model as standalone SVG — the widget's
    geometry, drawn statically."""
    n_cols, layer_max, band_h = (m['n_columns'], m['layer_max'],
                                 m['band_h'])
    x_lo, x_hi = -0.75, n_cols - 1 + 0.6
    y_span = (layer_max + 1) / 2.0
    y_lo, y_hi = -y_span - 0.75, y_span + 0.4
    W = min(170 * n_cols, 900)
    H = max(min(round(58 * (layer_max + 2)), 900), 220)
    px_x, px_y = W / (x_hi - x_lo), H / (y_hi - y_lo)
    cell_w = band_h * px_y / px_x

    words = str(m.get('title', '')).split()
    max_ch = max(20, round(W / 9))
    title_lines, cur = [], ''
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_ch:
            title_lines.append(cur)
            cur = w
        else:
            cur = f'{cur} {w}'.strip()
    if cur:
        title_lines.append(cur)
    T = 10 + 18 * len(title_lines)

    def px(x):
        return (x - x_lo) * px_x

    def py(y):
        return T + (y_hi - y) * px_y

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'viewBox="0 0 {W:g} {T + H:g}" width="{W:g}" '
           f'height="{T + H:g}" font-family="sans-serif">',
           _el('rect', x='0', y='0', width=f'{W:g}', height=f'{T + H:g}',
               fill='#ffffff')]
    for i, line in enumerate(title_lines):
        out.append(_el('text', text=line, x=f'{W / 2:g}',
                       y=f'{16 + 18 * i:g}', text_anchor='middle',
                       font_size='13', font_weight='bold',
                       fill='#000000'))
    head_len, head_half = 6.0, 2.4
    for a in m.get('arrows', []):
        ax1, ay1 = px(a['x'] + cell_w / 2 + 0.02), py(a['y'])
        ax2, ay2 = px(a['x2'] - cell_w / 2 - 0.02), py(a['y2'])
        dx, dy = ax2 - ax1, ay2 - ay1
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        bx, by = ax2 - head_len * ux, ay2 - head_len * uy
        out.append(_el('line', x1=f'{ax1:.2f}', y1=f'{ay1:.2f}',
                       x2=f'{bx:.2f}', y2=f'{by:.2f}',
                       stroke='#000000', stroke_width='1'))
        out.append(_el(
            'path', fill='#000000',
            d=f'M {ax2:.2f} {ay2:.2f} '
              f'L {bx - head_half * -uy:.2f} {by - head_half * ux:.2f} '
              f'L {bx + head_half * -uy:.2f} {by + head_half * ux:.2f} Z'))
    for c in m.get('cells', []):
        cx0, cx1 = px(c['x'] - cell_w / 2), px(c['x'] + cell_w / 2)
        cy0, cy1 = py(c['y1']), py(c['y0'])
        sw = c['sw']
        out.append(_el('rect', x=f'{cx0:.2f}', y=f'{cy0:.2f}',
                       width=f'{cx1 - cx0:.2f}',
                       height=f'{cy1 - cy0:.2f}', fill=c['stroke']))
        out.append(_el('rect', x=f'{cx0 + sw:.2f}', y=f'{cy0 + sw:.2f}',
                       width=f'{max(0, cx1 - cx0 - 2 * sw):.2f}',
                       height=f'{max(0, cy1 - cy0 - 2 * sw):.2f}',
                       fill=c['fill']))
    n_stripes = 5
    for xc, sy0, sy1, sw in m.get('stripes', []):
        sx0, sx1 = px(xc - cell_w / 2) + sw, px(xc + cell_w / 2) - sw
        y_top, y_bot = py(sy1) + sw, py(sy0) - sw
        for k in range(1, 2 * n_stripes):
            c = -1 + k / n_stripes
            u0, u1 = max(0.0, -c), min(1.0, 1.0 - c)
            if u0 >= u1:
                continue
            out.append(_el(
                'line',
                x1=f'{sx0 + u0 * (sx1 - sx0):.2f}',
                y1=f'{y_bot - (u0 + c) * (y_bot - y_top):.2f}',
                x2=f'{sx0 + u1 * (sx1 - sx0):.2f}',
                y2=f'{y_bot - (u1 + c) * (y_bot - y_top):.2f}',
                stroke='#000000', stroke_width='0.4'))
    for lb in m.get('labels', []):
        out.append(_el('text', text=lb['text'],
                       x=f"{px(lb['x'] - cell_w / 2 - 0.04):.2f}",
                       y=f"{py(lb['y']) + BASELINE_CENTER * 11:.2f}",
                       text_anchor='end', font_size='11',
                       fill='#404040'))
    for i, label in enumerate(m.get('col_labels', [])):
        out.append(_el('text', text=label, x=f'{px(i):.2f}',
                       y=f'{py(y_lo + 0.35):.2f}', text_anchor='middle',
                       font_size='13', fill='#000000'))
    out.append('</svg>')
    return '\n'.join(out)
