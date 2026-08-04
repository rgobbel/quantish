import logging


from multiworld.simulation import Simulation
from multiworld.util import SEP, parse_position, sstr, wstr
import multiworld.qnumber as qn
import python_mermaid.diagram as pmd
import python_mermaid.node as pm
from collections import namedtuple, defaultdict
import re
import math as m
import time

DiagramFields = namedtuple('DiagramFields', ('field', 'label'))

gate_fields = {'upper': DiagramFields(field='upper', label='UPPER'),
               'lower': DiagramFields(field='lower', label='LOWER'),
               'control': DiagramFields(field='control', label='CONTROL')}

# def argand(plot_data, cats):
#     size = 350
#     print(f'plot_data={plot_data}, cats={cats}')
#     plot_frame = pd.DataFrame({
#         'parallel': plot_data[:,0],
#         'perpendicular': plot_data[:,1],
#         'component': cats})
#     base = alt.Chart(plot_frame)
#     points = base.mark_rule().encode(
#         x2=alt.datum(0.0),
#         x=alt.X('parallel', axis=alt.Axis(title='Parallel'),
#                 scale=alt.Scale(domain=[-1.1,1.1])),
#         y2=alt.datum(0.0),
#         y=alt.Y('perpendicular', axis=alt.Axis(title='Perpendicular'),
#                 scale=alt.Scale(domain=[-1.1,1.1])),
#         color='component:N').properties(width=size, height=size)
#     labels = base.mark_text(
#         align='left',
#         baseline='middle',
#         dx=7).encode(
#         x='parallel:Q',
#         y='perpendicular:Q',
#         color='component:N')
#
#     final_chart = (points + labels).properties(
#         title='Quantish Weights')
#     return final_chart

def short_config(point):
    """Compact one-line label for a world's coordinates: sign, gate, and the
    port initial for each particle, e.g. '+g2c|+g2l|+g3u'."""
    parts = []
    for coord in point.coords.values():
        port = coord.position.origin or coord.position.endpoint
        if port is None:
            parts.append(f'{sstr(coord.sign)}?')
        else:
            parts.append(f'{sstr(coord.sign)}{port.gate}{(port.port or "c")[0]}')
    return '|'.join(parts)


def network_graph(result_space, diagram_path, sim, show=True):
    """Render the weight-evolution trace, save it as a PDF next to
    diagram_path, and optionally show it on screen."""
    from matplotlib import pyplot as plt
    fig = network_graph_figure(result_space, sim)
    out_path = diagram_path.with_stem(diagram_path.stem + '_graph').with_suffix('.pdf')
    fig.savefig(out_path, orientation='landscape', bbox_inches='tight')
    if show:
        plt.show()
    plt.close(fig)


def network_graph_figure(result_space, sim):
    """Weight-evolution trace of the simulation, as a matplotlib Figure.

    One column per step, one node per world. A node is a stack of bands,
    one per particle: hue identifies the particle; each band is split into
    a left (input) and right (output) half whose brightness encodes the
    particle's cumulative amplitude factor before and after the step
    (light = strong, dark = weak). Bands acted on this step get a heavy
    outline. Edge width tracks the amplitude each parent world contributed
    — a merged world shows one incoming edge per interfering contribution.
    """
    logging.getLogger('multiworld').setLevel(logging.WARN)
    from matplotlib import pyplot as plt
    from matplotlib import colormaps
    plt.set_loglevel("warning")

    layers = defaultdict(list)
    for p in result_space.index.values():
        layers[p.step].append(p)
    steps = sorted(layers.keys())
    layer_max = max(len(v) for v in layers.values())

    def primary_parent(w):
        best, best_mag = None, -1.0
        for parent, contrib in w.contributions.items():
            try:
                mag = abs(complex(contrib))
            except (TypeError, ValueError):
                mag = 0.0
            if mag > best_mag:
                best, best_mag = parent, mag
        return best

    # Cumulative per-particle display amplitude: the product of the branch
    # factors the particle has taken along its (primary-parent) lineage.
    # This is what the band brightness shows — the particle's share of the
    # world's weight, not just the latest step's factor.
    display_val = {}
    for step in steps:
        for w in layers[step]:
            parent = primary_parent(w)
            for pname in w.coords:
                factor = w.factors.get(pname)
                if parent is None:  # initial world: factors are the weights
                    value = factor if factor is not None else 1.0
                else:
                    value = display_val.get((id(parent), pname), 1.0)
                    if factor is not None:
                        try:
                            value = complex(value) * complex(factor)
                        except (TypeError, ValueError):
                            pass
                display_val[(id(w), pname)] = value

    def _moved(w, pname):
        parent = primary_parent(w)
        return (parent is not None
                and pname in parent.coords
                and parent.coords[pname].key != w.coords[pname].key)

    # Vertical order within a column: per acted-on particle, by gate, then
    # port in the book's order (control, upper, lower), then sign (+ first).
    port_rank = {'control': 0, 'upper': 1, 'lower': 2}

    def world_ranks(w):
        ranks = []
        if w.step != steps[0]:
            for pname in sorted(w.coords.keys()):
                coord = w.coords[pname]
                acted = w.factors.get(pname) is not None or _moved(w, pname)
                if not acted:
                    continue
                origin = coord.position.origin
                ranks.append((origin.gate if origin else '',
                              port_rank.get(origin.port if origin else None, 3),
                              0 if int(coord.sign) >= 0 else 1))
        return ranks

    def sort_key(w):
        return (tuple(world_ranks(w)), w.key)

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

    # Edges: parent -> child, one per recorded contribution.
    for p, (x, y) in pos.items():
        for parent, contrib in p.contributions.items():
            if parent not in pos:
                continue
            px, py = pos[parent]
            try:
                mag = abs(complex(contrib))
            except (TypeError, ValueError):
                mag = 0.5
            ax.plot([px, x], [py, y], color='0.55',
                    lw=0.4 + 2.6 * mag, alpha=0.75, zorder=1,
                    solid_capstyle='round')

    # Nodes: per-particle bands, each split into input (left) and output
    # (right) halves.
    from matplotlib.patches import Rectangle
    band_cmaps = [colormaps[name] for name in ('Reds', 'Greens', 'Blues',
                                               'Purples', 'Oranges', 'Greys')]
    n_particles = max(len(p.coords) for p in pos)
    # Size the node in *screen* inches (the data aspect is far from square),
    # so the stack renders taller than it is wide.
    _x_range = (steps[-1] - steps[0]) + 1.2
    _y_range = (layer_max + 1) + 1.2
    node_w = 0.34 * _x_range / fig_w
    band_h = min(0.20 * _y_range / fig_h, 0.78 / max(1, n_particles))
    node_h = band_h * n_particles

    def shade(cmap, value):
        try:
            v = min(1.0, abs(complex(value)))
        except (TypeError, ValueError):
            v = 0.5
        return cmap(0.2 + 0.7 * (1.0 - v))

    for p, (x, y) in pos.items():
        parent = primary_parent(p)
        for i, pname in enumerate(sorted(p.coords.keys())):
            cmap = band_cmaps[i % len(band_cmaps)]
            out_v = display_val.get((id(p), pname), 1.0)
            in_v = (display_val.get((id(parent), pname), out_v)
                    if parent is not None else out_v)
            acted = (p.step != steps[0]
                     and (p.factors.get(pname) is not None or _moved(p, pname)))
            y0 = y + node_h / 2 - (i + 1) * band_h
            ax.add_patch(Rectangle((x - node_w / 2, y0), node_w / 2, band_h,
                                   facecolor=shade(cmap, in_v),
                                   edgecolor='none', zorder=3))
            ax.add_patch(Rectangle((x, y0), node_w / 2, band_h,
                                   facecolor=shade(cmap, out_v),
                                   edgecolor='none', zorder=3))
            ax.add_patch(Rectangle((x - node_w / 2, y0), node_w, band_h,
                                   fill=False,
                                   edgecolor='black' if acted else '0.55',
                                   linewidth=1.0 if acted else 0.35,
                                   zorder=3.5))

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

    # experimental cluster boxes: group each column's worlds by the first
    # (gate, port) coordinate that differs between them
    _port_names = {0: 'control', 1: 'upper', 2: 'lower'}
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
            ax.annotate(f'{_gate} {_port_names.get(_prank, "?")}',
                        (step - node_w / 2 - 0.08, (min(ys) + max(ys)) / 2),
                        ha='right', va='center', fontsize=max(5, tick_fs - 3),
                        color='0.5', rotation=90, zorder=2.6)
    for i in range(1, len(steps)):
        step = steps[i]
        gates = sim.run_stages[i - 1] if i - 1 < len(sim.run_stages) else []
        y_lo, y_hi = box_y[step]
        ax.add_patch(FancyBboxPatch((step - 0.38, y_lo), 0.76, y_hi - y_lo,
                                    boxstyle='round,pad=0.02',
                                    facecolor='0.97', edgecolor='0.75',
                                    linewidth=0.8, zorder=0.5))
        ax.annotate(', '.join(gates), (step, y_hi), xytext=(0, -3),
                    textcoords='offset points', ha='center', va='top',
                    fontsize=tick_fs, color='0.35', zorder=4)
    # dashed stage boxes for diagram groups spanning several gates
    for group_name, group in sim.diagram_groups.items():
        cols = sorted(sim.gate_step[g] for g in group if g in sim.gate_step)
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

    tick_labels = ['initial'] + [f'stage {s}' for s in steps[1:]]
    ax.set_xticks([float(s) for s in steps], tick_labels, fontsize=tick_fs)
    ax.set_yticks([])
    for spine in ('top', 'right', 'left'):
        ax.spines[spine].set_visible(False)
    ax.set_xlim(steps[0] - 0.6, steps[-1] + 0.6)
    ax.set_ylim(-(layer_max + 1) / 2.0 - 0.5, (layer_max + 1) / 2.0 + 0.7)
    ax.set_title(f'{sim.title} — weight evolution', fontsize=max(11, tick_fs + 2))
    fig.text(0.01, 0.01,
             'bands: hue = particle; halves: left = in, right = out, '
             'light↔dark = strong↔weak amplitude; heavy outline = particle '
             'acted on this stage; edge width = |contributed amplitude|',
             fontsize=max(7, tick_fs - 1), color='0.4')
    return fig

def make_gate_node(sim, gname, inout, wire, mermaid_nodes, show_outputs=True):
    sink_nodes = []
    def make1(node_id, content, shape='normal', bold=False):
        if bold: # HACK!!
            standard_shape = pm.NODE_SHAPES[shape]
            custom_shape = pm.NodeShape(start=standard_shape.start, end=f'{standard_shape.end}\nstyle {node_id} stroke-width:4px')
            custom_name = f'{node_id}_bold'
            pm.NODE_SHAPES[custom_name] = custom_shape
            shape = custom_name
        gnode = pmd.Node(node_id, shape=shape)
        mermaid_nodes[node_id] = gnode
        gnode.content = content
        return gnode
    position = f'{gname}{SEP}{wire}'
    sep = '' if inout == '' else '_'
    graph_node_id = f'{position}{sep}{inout}'
    gcontent = f'{gate_fields[wire].label}'
    if inout == 'in':
        make1(graph_node_id, f'{gcontent}')
    elif inout == 'out':
        out_pos = f'{gname}{SEP}{wire}'
        gname, gwire = out_pos.split(SEP)
        # TODO(roadmap: Mermaid after-diagrams): mark the sampled/selected
        # output once port values come from final-world marginals.
        selected = False
        out_value_str = sim.pos_value_str(out_pos, 'weights')
        # pos_sink = sim.sinks.get(out_pos)
        if not show_outputs:
            cs = ''
        elif out_value_str is None:
            cs = f'None'
        else:
            cs = f'{out_value_str}'
        if show_outputs and out_pos not in sim.links.keys():
            sink_node_id = f'{position}_SINK'
            if len(cs) > 0:
                sink_nodes += [make1(sink_node_id, f'{gcontent}:\n{cs}', shape='stadium-shape')]
            else:
                sink_nodes += [make1(sink_node_id, f'{gcontent}', shape='stadium-shape')]
        if len(cs) > 0:
            make1(graph_node_id, f'{gcontent}:\n{cs}', bold=selected)
        else:
            make1(graph_node_id, f'{gcontent}', bold=selected)
    elif inout == '':
        out_value_str = sim.pos_value_str(position, 'weights')
        if not show_outputs:
            cs = ''
        elif out_value_str is None:
            cs = 'None'
        else:
            cs = f'{out_value_str}'
        if show_outputs and position not in sim.links.keys():
            sink_node_id = f'{position}_SINK'
            if len(cs) > 0:
                sink_nodes += [make1(sink_node_id, f'{gcontent}:\n{cs}', shape='stadium-shape')]
            else:
                sink_nodes += [make1(sink_node_id, f'{gcontent}', shape='stadium-shape')]
        if len(cs) > 0:
            make1(graph_node_id, f'{gcontent}: {cs}', bold=sim.pos_value_str(position, 'weights'))
        else:
            make1(graph_node_id, f'{gcontent}', bold=sim.pos_value_str(position, 'weights'))
    return sink_nodes

def gnodes(sim, gname, mermaid_nodes, show_outputs=True):
    sink_nodes = []
    sink_nodes += make_gate_node(sim, gname, '', 'control', mermaid_nodes, show_outputs)
    for switch_set in ('upper', 'lower'):
        for inout in ('in', 'out'):
            sink_nodes += make_gate_node(sim, gname, inout, switch_set, mermaid_nodes, show_outputs)
    return sink_nodes

def diagram(sim:Simulation, output_file=None, has_run=False):
    def is_delay(gname):
        # explicit DelayGate instances, plus gates wired only through their
        # control port (pure pass-throughs) — both render as simple boxes
        return (sim.gates[gname].report_type() == 'DelayGate'
                or gname in getattr(sim, 'pass_through_gates', set()))

    mermaid_nodes = {}
    if has_run:
        title = f'{sim.title} after run at {time.asctime()}'
    else:
        title = f'{sim.title}, {time.asctime()}'
    diag = pmd.Diagram(title=title, orientation='left to right')
    phase_graphs = {}
    mermaid_links = []
    if has_run:
        legend = pmd.Node(id='Legend')
        legend.content = f"""**Parameters**
    **numerics**: {qn.CalcMode.default()}
    """
        diag.add_nodes([legend])
    for particle_name, particle in sim.particles.items():
        pcontent = particle.ps(short=True)
        pname = particle_name.split('<')[0]
        particle_node = pmd.Node(id=pname, shape='stadium-shape')
        particle_node.content = pcontent
        mermaid_nodes[pname] = particle_node
        diag.add_nodes([particle_node])
    # for delay_name, delay_gate in sim.delay_gates.items():
    #     dgcontent = 'D'
    #     dgnode = pm.Node(id=delay_name)
    #     dgnode.content = dgcontent
    #     mermaid_nodes[delay_name] = dgnode
    for group_name, gate_group in sim.diagram_groups.items():
        stage_id = f'{group_name}_stage'
        pg = diag.add_subgraph(stage_id)
        pg.header = f'subgraph {stage_id}["{group_name}"]'
        phase_graphs[stage_id] = pg
        for gname in gate_group:
            gate = sim.gates[gname]
            if is_delay(gname):
                gate_inout = f'{gate.name}{SEP}control'
                if has_run and gate_inout not in sim.links.keys():
                    sink_node_id = f'{gate_inout}_SINK'
                    sink_node = pmd.Node(sink_node_id, gate.name, shape='stadium-shape')
                    mermaid_nodes[sink_node_id] = sink_node
                    diag.add_nodes([sink_node])
                gn = pm.Node(gate.name, gate.name, shape='stadium-shape')
                mermaid_nodes[gname] = gn
                pg.add_nodes([gn])
            else:
                gg = pg.add_subgraph(gname)
                gg.header = f'subgraph {gname}["{gname}: {float(gate.theta.degrees):.1f}º"]'
                ggi = gg.add_subgraph(f'{gname}.input')
                ggi.header = f'subgraph {gname}.input[input]'
                ggo = gg.add_subgraph(f'{gname}.output')
                ggo.header = f'subgraph {gname}.output[output]'
                sink_nodes = gnodes(sim, gname, mermaid_nodes, show_outputs=has_run)
                if has_run:
                    diag.add_nodes(sink_nodes)
                gg.add_nodes([mermaid_nodes[f'{gname}.{gate_fields['control'].field}']])
                ggi.add_nodes([mermaid_nodes[f'{gname}.{gate_fields['upper'].field}_in'],
                               mermaid_nodes[f'{gname}.{gate_fields['lower'].field}_in']])
                ggo.add_nodes([mermaid_nodes[f'{gname}.{gate_fields['upper'].field}_out'],
                               mermaid_nodes[f'{gname}.{gate_fields['lower'].field}_out']])
                mermaid_links += [
                    pmd.Link(mermaid_nodes[f'{gname}.{gate_fields['upper'].field}_in'],
                             mermaid_nodes[f'{gname}.{gate_fields['upper'].field}_out'], shape='dotted'),
                    pmd.Link(mermaid_nodes[f'{gname}.{gate_fields['upper'].field}_in'],
                             mermaid_nodes[f'{gname}.{gate_fields['lower'].field}_out'], shape='dotted'),
                    pmd.Link(mermaid_nodes[f'{gname}.{gate_fields['lower'].field}_in'],
                             mermaid_nodes[f'{gname}.{gate_fields['lower'].field}_out'], shape='dotted'),
                    pmd.Link(mermaid_nodes[f'{gname}.{gate_fields['lower'].field}_in'],
                             mermaid_nodes[f'{gname}.{gate_fields['upper'].field}_out'], shape='dotted')]
    for gate_name, gate in sim.gates.items():
        control_pos = f'{gate_name}{SEP}control'
        if is_delay(gate_name):
            ctrl_gate_node = mermaid_nodes[gate_name]
        else:
            ctrl_gate_node = mermaid_nodes[control_pos]
        if control_pos in sim.sources.keys():
            ctrl_source_name = sim.sources[control_pos]
            ctrl_source_parts = parse_position(ctrl_source_name)
            if type(ctrl_source_parts) is str:
                ctrl_input_node = mermaid_nodes[ctrl_source_name]
                mermaid_links.append(pmd.Link(ctrl_input_node, ctrl_gate_node))
        dest_node = None
        if control_pos in sim.links.keys():
            dest = sim.links[control_pos]
            dest_parts = parse_position(dest)
            dest_gate_name, dest_wire = dest_parts
            dest_gate = sim.gates[dest_gate_name]
            if is_delay(dest_gate_name):
                dest_node = mermaid_nodes[dest_gate_name]
            else:
                if dest_wire == 'control':
                    dest_node = mermaid_nodes[dest]
                elif dest_wire == 'input':
                    dest_node = mermaid_nodes[dest_gate_name]
                else:
                    dest_node = mermaid_nodes[f'{dest}_in']
        else:
            if has_run:
                dest_node = mermaid_nodes[f'{control_pos}_SINK']
        if dest_node is not None:
            mermaid_links.append(pmd.Link(ctrl_gate_node, dest_node))
        if is_delay(gate_name): continue
        for switch_set in ('upper', 'lower'):
            switch_pos = f'{gate_name}{SEP}{switch_set}'
            for inout in ('in', 'out'):
                switch_node_id = f'{switch_pos}_{inout}'
                switch_node = mermaid_nodes[switch_node_id]
                if inout == 'in' and switch_pos in sim.sources.keys():
                    switch_input = sim.sources[switch_pos]
                    input_pos = parse_position(switch_input)
                    if type(input_pos) is str:
                        switch_input_node = mermaid_nodes[switch_input]
                        mermaid_links.append(pmd.Link(switch_input_node, switch_node))
                elif inout == 'out':
                    dest_node = None
                    if switch_pos in sim.links.keys():
                        dest = sim.links[switch_pos]
                        dest_parts = parse_position(dest)
                        dest_gate_name, dest_wire = dest_parts
                        dest_gate = sim.gates[dest_gate_name]
                        if is_delay(dest_gate_name):
                            dest_node = mermaid_nodes[dest_gate_name]
                        else:
                            if dest_wire == 'control':
                                dest_node = mermaid_nodes[dest]
                            else:
                                dest_node = mermaid_nodes[f'{dest}_in']
                    elif has_run:
                        dest_node = mermaid_nodes[f'{switch_pos}_SINK']
                    if dest_node is not None:
                        mermaid_links.append(pmd.Link(switch_node, dest_node))

    diag.add_links(mermaid_links)
    if has_run:
        diag.graph.header = 'flowchart LR\nstyle legend text-align:left'
    else:
        diag.graph.header = 'flowchart LR\n'
    diag.pretty_print = True
    if output_file is not None:
        graph_config = """config:
layout: elk
elk:
   forceNodeModelOrder: true
   nodePlacementStrategy: LINEAR_SEGMENTS
   considerModelOrder: NODES_AND_EDGES
title:
"""
        styled_diag = re.sub("title:", graph_config, str(diag))
        with open(output_file, 'w') as f:
            f.write(styled_diag)
    return diag
