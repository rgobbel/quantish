import logging
from collections import defaultdict
from pathlib import Path
import math as m

from multiworld.config_space import ConfigSpace, ConfigSpacePoint
from multiworld.simulation import Simulation
from multiworld.qnumber import probability, to_float, ZERO_THRESHOLD, to_native


class NetworkGraph:
    def __init__(self, result_space: ConfigSpace, sim: Simulation, diagram_path: Path=None, show=True):
        """Render the weight-evolution trace, save it as a PDF next to
        diagram_path, and optionally show it on screen."""
        from matplotlib import pyplot as plt
        self.result_space = result_space
        self.sim = sim
        fig = self.figure()
        if diagram_path is not None:
            out_path = diagram_path.with_stem(diagram_path.stem + '_graph').with_suffix('.pdf')
            fig.savefig(out_path, orientation='landscape', bbox_inches='tight')
            if show:
                plt.show()
            plt.close(fig)

    def figure(self):
        """Weight-evolution trace of the simulation, as a matplotlib Figure.

        One column per step, one node per world. A node is
        a stack of bands: one per particle showing the branch factor the
        stage applied to it (hue = particle; black = −1, mid-gray = 0,
        white = +1; hatched = not active in this stage), then a bottom monochrome
        band showing the combined world weight on the same scale. Complex
        values display as magnitude signed by the dominant axis, so ±i·sinθcosθ
        branches are distinguishable. Bands active on this step get a heavy
        outline. Edge width tracks the amplitude each parent world contributed
        — a merged world shows one incoming edge per interfering contribution.
        """

        def primary_parent(w: ConfigSpacePoint):
            best, best_mag = None, -1.0
            for parent, contrib in w.contributions.items():
                try:
                    mag = abs(complex(contrib))
                except (TypeError, ValueError):
                    mag = 0.0
                if mag > best_mag:
                    best, best_mag = parent, mag
            return best

        def _moved(w: ConfigSpacePoint, pname):
            parent = primary_parent(w)
            return (parent is not None
                    and pname in parent.coords
                    and parent.coords[pname].key != w.coords[pname].key)

        def world_ranks(w: ConfigSpacePoint):
            ranks = []
            if w.step != steps[0]:
                for pname in sorted(w.coords.keys()):
                    coord = w.coords[pname]
                    active = w.factors.get(pname) is not None or _moved(w, pname)
                    if not active:
                        continue
                    origin = coord.position.origin
                    ranks.append((origin.gate if origin else '',
                                  port_rank.get(origin.port if origin else None, 3),
                                  0 if int(coord.sign) >= 0 else 1))
            return ranks

        def sort_key(w: ConfigSpacePoint):
            return tuple(world_ranks(w)), w.key

        def signed_amp(value):
            try:
                c = to_native(value)
            except (TypeError, ValueError):
                return 0.0
            mag = abs(c)
            if mag < ZERO_THRESHOLD:
                return 0.0
            ref = c.real if abs(c.real) >= abs(c.imag) else c.imag
            return max(-1.0, min(1.0, mag if ref >= 0 else -mag))

        def band_color(value, hue=None):
            if hue is None:  # monochrome (the combined-weight column)
                light = to_float(value)
                return light, light, light
            light = (signed_amp(value) + 1.0) / 2.0
            return colorsys.hls_to_rgb(hue, light, 0.85)

        def band_y(point: ConfigSpacePoint, pname):
            i = sorted(point.coords.keys()).index(pname)
            return pos[point][1] + node_h / 2 - (i + 0.5) * band_h

        def line_color(i):
            return colorsys.hls_to_rgb(hues[i % len(hues)], 0.45, 0.7)

        logging.getLogger('multiworld').setLevel(logging.WARN)
        from matplotlib import pyplot as plt
        plt.set_loglevel("warning")

        layers = defaultdict(list)
        for p in self.result_space.index.values():
            layers[p.step].append(p)
        steps = sorted(layers.keys())
        layer_max = max(len(v) for v in layers.values())

        # Vertical order within a column: per active-on particle, by gate, then
        # port in the book's order (control, upper, lower), then sign (+ first).
        port_rank = {'control': 0, 'upper': 1, 'lower': 2}

        pos = {}
        for step in steps:
            layer = layers[step]
            layer.sort(key=sort_key)
            n = len(layer)
            for i, p in enumerate(layer):
                pos[p] = (float(p.step), (n - 1) / 2.0 - i)

        fig_w = min(2.0 + 2.2 * len(steps), 24)
        fig_h = min(1.2 + 0.72 * layer_max, 22)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        tick_fs = max(7.0, min(11.0, 38.0 / m.sqrt(layer_max)))

        # Node geometry and the shared value scale (−1 → black, 0 → mid-gray,
        # +1 → white; complex values as magnitude signed by the dominant axis).
        import colorsys
        from matplotlib.patches import Rectangle
        hues = [0.00, 0.33, 0.62, 0.78, 0.09, 0.50]  # red green blue purple orange cyan

        n_particles = max(len(p.coords) for p in pos)
        # Size the node in *screen* inches (the data aspect is far from square),
        # so the stack renders taller than it is wide.
        _x_range = (steps[-1] - steps[0]) + 1.2
        _y_range = (layer_max + 1) + 1.2
        node_w = 0.34 * _x_range / fig_w
        band_h = min(0.20 * _y_range / fig_h, 0.78 / max(1, n_particles))
        node_h = band_h * n_particles
        comb_w = 0.32 * node_w   # right-side combined-weight column
        fact_w = node_w - comb_w  # left-side stack of per-particle factor bands

        # Edges: one line per moved particle per contribution, tinted with the
        # particle's hue, running from the particle's band in the parent world
        # to its band in the child — the port routing is in the geometry, like
        # the Mermaid diagram's links. Width still tracks |contributed
        # amplitude|; a merged world shows one bundle per interfering branch.
        for p, (x, y) in pos.items():
            for parent, contrib in p.contributions.items():
                if parent not in pos:
                    continue
                px, py = pos[parent]
                try:
                    mag = abs(complex(contrib))
                except (TypeError, ValueError):
                    mag = 0.5
                moved = [(i, pname)
                         for i, pname in enumerate(sorted(p.coords.keys()))
                         if p.factors.get(pname) is not None
                         or (pname in parent.coords
                             and parent.coords[pname].key != p.coords[pname].key)]
                if not moved:  # nothing active this stage: neutral world line
                    ax.plot([px + node_w / 2, x - node_w / 2], [py, y],
                            color='black', lw=0.5,
                            zorder=1, solid_capstyle='round')
                    continue
                for i, pname in moved:
                    y_from = band_y(parent, pname) if pname in parent.coords else py
                    ax.plot([px + node_w / 2, x - node_w / 2],
                            [y_from, band_y(p, pname)],
                            color='black', lw=0.5,
                            zorder=1, solid_capstyle='round')

        # Nodes: a stack of hued factor bands (one per particle, the factor
        # this stage applied) with a full-height monochrome column on the
        # right showing the combined world weight, on the shared value scale.
        for p, (x, y) in pos.items():
            x_left = x - node_w / 2
            for i, pname in enumerate(sorted(p.coords.keys())):
                factor = p.factors.get(pname)
                active = (p.step != steps[0]
                         and (factor is not None or _moved(p, pname)))
                y0 = y + node_h / 2 - (i + 1) * band_h
                if factor is None and p.step != steps[0]:
                    # untouched this stage: hatched placeholder keeps the
                    # particle's row position without asserting a value
                    ax.add_patch(Rectangle((x_left, y0), fact_w, band_h,
                                           facecolor='white', hatch='///',
                                           edgecolor='0.8', linewidth=0.3,
                                           zorder=3))
                    continue
                # step 0 stores the configured particle weights as "factors"
                ax.add_patch(Rectangle((x_left, y0), fact_w, band_h,
                                       facecolor=band_color(
                                           factor if factor is not None else 1.0,
                                           hues[i % len(hues)]),
                                       edgecolor='black' if active else '0.55',
                                       linewidth=1.0 if active else 0.35,
                                       zorder=3))
            ax.add_patch(Rectangle((x_left + fact_w, y - node_h / 2),
                                   comb_w, node_h,
                                   facecolor=band_color(to_float(probability(p.weight))),
                                   edgecolor='black', linewidth=0.6, zorder=3))
            if p.cancelled:
                ax.add_patch(Rectangle((x_left, y - node_h / 2),
                                       node_w, node_h, fill=False,
                                       edgecolor='crimson', linewidth=1.1,
                                       linestyle=(0, (2, 2)), zorder=3.6))

        # Boxes marking gate boundaries: one per step column (labeled with the
        # gate that fired), plus a dashed outer box per multi-gate diagram
        # group, plus (experimental) thin boxes around the upper/lower halves
        # of each gate's outcomes.
        from matplotlib.patches import FancyBboxPatch
        label_space = 0.12
        col_extent = {}
        for p, (x, y) in pos.items():
            y_lo, y_hi = col_extent.get(p.step, (y, y))
            col_extent[p.step] = (min(y_lo, y), max(y_hi, y))
        box_y = {}
        for step, (y_lo, y_hi) in col_extent.items():
            # extra headroom at the top of each column for the gate label
            box_y[step] = (y_lo - node_h / 2 - label_space, y_hi + node_h / 2 + 0.55)

        # cluster boxes: group each column's worlds by the first (gate, port)
        # coordinate that differs between them — unlabeled, since the hued
        # band-to-band lines carry the port routing
        for step in steps[1:]:
            ranked = [(w, world_ranks(w)) for w in layers[step]]
            ranked = [(w, r) for w, r in ranked if r]
            if len(ranked) < 2:
                continue
            _depth = min(len(r) for _, r in ranked)
            _vary = next((idx for idx in range(_depth)
                          if len({r[idx][:2] for _, r in ranked}) > 1), None)
            if _vary is None:
                continue
            clusters = {}
            for w, r in ranked:
                clusters.setdefault(r[_vary][:2], []).append(pos[w][1])
            if len(clusters) < 2:
                continue
            for (_gate, _prank), ys in clusters.items():
                ax.add_patch(Rectangle((step - node_w / 2 - 0.05,
                                        min(ys) - node_h / 2 - 0.05),
                                       node_w + 0.10,
                                       max(ys) - min(ys) + node_h + 0.10,
                                       fill=False, edgecolor='0.65',
                                       linewidth=0.6, linestyle=':', zorder=2.5))
        for i in range(1, len(steps)):
            step = steps[i]
            gates = self.sim.run_stages[i - 1] if i - 1 < len(self.sim.run_stages) else []
            y_lo, y_hi = box_y[step]
            ax.add_patch(FancyBboxPatch((step - 0.38, y_lo), 0.76, y_hi - y_lo,
                                        boxstyle='round,pad=0.02',
                                        facecolor='0.97', edgecolor='0.75',
                                        linewidth=0.8, zorder=0.5))
            ax.annotate(', '.join(gates), (step, y_hi), xytext=(0, -3),
                        textcoords='offset points', ha='center', va='top',
                        fontsize=tick_fs, color='0.35', zorder=4)
        # dashed stage boxes for diagram groups spanning several gates
        for group_name, group in self.sim.diagram_groups.items():
            cols = sorted(self.sim.gate_step[g] for g in group if g in self.sim.gate_step)
            if len(cols) < 2:
                continue
            y_lo = min(box_y[c][0] for c in cols if c in box_y) - 0.12
            y_hi = max(box_y[c][1] for c in cols if c in box_y) + 0.35
            ax.add_patch(FancyBboxPatch((cols[0] - 0.45, y_lo),
                                        cols[-1] - cols[0] + 0.9, y_hi - y_lo,
                                        boxstyle='round,pad=0.02', fill=False,
                                        edgecolor='0.6', linewidth=0.9,
                                        linestyle='--', zorder=0.4))
            ax.annotate(group_name, ((cols[0] + cols[-1]) / 2, y_hi), xytext=(0, 3),
                        textcoords='offset points', ha='center', va='bottom',
                        fontsize=tick_fs, color='0.45', style='italic', zorder=4)

        tick_labels = ['initial'] + [f'{k} ' for k in self.sim.config['run_groups'].keys()]
        ax.set_xticks([float(s) for s in steps], tick_labels, fontsize=tick_fs)
        ax.set_yticks([])
        for spine in ('top', 'right', 'left'):
            ax.spines[spine].set_visible(False)
        ax.set_xlim(steps[0] - 0.6, steps[-1] + 0.6)
        ax.set_ylim(-(layer_max + 1) / 2.0 - 0.5, (layer_max + 1) / 2.0 + 0.7)
        ax.set_title(f'{self.sim.title} — weight evolution', fontsize=max(11, tick_fs + 2))
        fig.text(0.25, 0.01,
                 'left column: hue = particle factor this stage; right column = '
                 'marginal probability (black = 0, white = 1)\nhatched = '
                 'untouched; heavy outline = control present; '
                 'lines: one per moved particle',
                 fontsize=max(7, tick_fs - 1), color='0.4', horizontalalignment='left')
        fig.subplots_adjust(bottom=0.2)
        return fig

