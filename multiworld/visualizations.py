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

    One column per step, one node per world. Node hue encodes the weight's
    phase, node area its probability |w|^2; each node is labeled with its
    weight and compact coordinates. Edge width tracks the magnitude of the
    amplitude the parent world contributed to the child — a merged world
    shows one incoming edge per interfering contribution, and its weight is
    the sum of them.
    """
    import cmath
    logging.getLogger('multiworld').setLevel(logging.WARN)
    from matplotlib import pyplot as plt
    from matplotlib import colormaps
    plt.set_loglevel("warning")

    layers = defaultdict(list)
    for p in result_space.index.values():
        layers[p.step].append(p)
    steps = sorted(layers.keys())
    layer_max = max(len(v) for v in layers.values())

    # Stable vertical order: first layer by key; later layers by the mean y
    # of their contributing parents (barycenter), which keeps edges short.
    pos = {}
    for step in steps:
        layer = layers[step]
        def barycenter(p):
            ys = [pos[q][1] for q in p.contributions.keys() if q in pos]
            return sum(ys) / len(ys) if ys else 0.0
        if step == steps[0]:
            layer.sort(key=lambda p: p.key)
        else:
            layer.sort(key=lambda p: (-barycenter(p), p.key))
        n = len(layer)
        for i, p in enumerate(layer):
            pos[p] = (float(p.step), (n - 1) / 2.0 - i)

    fig_w = min(2.0 + 2.2 * len(steps), 24)
    fig_h = min(1.5 + 0.85 * layer_max, 22)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    # Sparse graphs get big legible labels; dense ones stay compact.
    label_fs = max(4.5, min(9.0, 36.0 / m.sqrt(layer_max)))
    tick_fs = max(7.0, min(11.0, label_fs + 2))

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

    # Nodes: hue = phase, marker area = probability. Markers are sized in
    # screen points so they stay circular whatever the data aspect is.
    hsv = colormaps['hsv']
    for p, (x, y) in pos.items():
        try:
            w = complex(p.weight)
            prob = abs(w) ** 2
            hue = (cmath.phase(w) / (2 * m.pi)) % 1.0
        except (TypeError, ValueError):
            prob, hue = 0.25, 0.0
        size = 50 + 850 * prob
        ax.scatter([x], [y], s=size, facecolor=hsv(hue),
                   edgecolor='black', linewidth=0.6, zorder=3)
        label = f'{wstr(p.weight, precision=2)}\n{short_config(p)}'
        ax.annotate(label, (x, y), xytext=(0, -(9 + 0.55 * m.sqrt(size))),
                    textcoords='offset points', ha='center', va='top',
                    fontsize=label_fs, zorder=4, family='monospace')

    # X axis: step number plus the gates that fired to produce that column.
    tick_labels = ['initial']
    for i in range(1, len(steps)):
        gates = sim.run_stages[i - 1] if i - 1 < len(sim.run_stages) else []
        tick_labels.append(f'step {steps[i]}\n{", ".join(gates)}')
    ax.set_xticks([float(s) for s in steps], tick_labels, fontsize=tick_fs)
    ax.set_yticks([])
    for spine in ('top', 'right', 'left'):
        ax.spines[spine].set_visible(False)
    ax.set_xlim(steps[0] - 0.6, steps[-1] + 0.6)
    ax.set_ylim(-(layer_max + 1) / 2.0, (layer_max + 1) / 2.0)
    ax.set_title(f'{sim.title} — weight evolution', fontsize=max(11, tick_fs + 2))
    fig.text(0.01, 0.01,
             'node hue = phase, area = |w|²; edge width = |contributed amplitude|',
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
            if gate.report_type() == 'DelayGate':
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
        if gate.report_type() == 'DelayGate':
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
            if dest_gate.report_type() == 'DelayGate':
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
        if gate.report_type() == 'DelayGate': continue
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
                        if dest_gate.report_type() == 'DelayGate':
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
