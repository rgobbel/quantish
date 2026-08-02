import logging


from multiworld.simulation import Simulation
from multiworld.util import SEP, parse_position, enough
from multiworld.config_space import ConfigSpacePoint, NOWHERE
import multiworld.qnumber as qn
import python_mermaid.diagram as pmd
import python_mermaid.node as pm
from collections import namedtuple, defaultdict
import networkx as nx
import re
import numpy as np
import math as m
# import altair as alt
# import pandas as pd
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

def cs_patch(point:ConfigSpacePoint, layer_max, max_step, sim):
    logging.getLogger('multiworld').setLevel(logging.WARN)
    from matplotlib.offsetbox import DrawingArea
    from matplotlib import colormaps
    from matplotlib.patches import Rectangle
    nvals = len(point.coords)
    side_base = 75 / m.sqrt(layer_max)
    cmaps = [colormaps['Reds'], colormaps['Greens'], colormaps['Blues']]
    da = DrawingArea(side_base, side_base, side_base/2, side_base/2)
    # the outline box is mainly uuseful for debugging
    # outline_box = [-side_base/4, nvals * -side_base/8, side_base/2, (side_base/4)*nvals]
    # da.add_artist(Rectangle(outline_box[:2], outline_box[2], outline_box[3], edgecolor='black', facecolor='white'))
    boxes = []
    for i in range(nvals):
        boxes.append([
            -side_base/4,
            (nvals * -side_base/8) + (nvals - 1 - i)*side_base/4,
            side_base/2,
            side_base/4
        ])
    # the weight belongs to the world, so every particle row shows the
    # world's probability in that particle's colormap
    world_prob = float(point.probability)
    for i, coord in enumerate(point.coords.values()):
        color = cmaps[i % len(cmaps)]((0.7 * (1.0 - world_prob)) + 0.2)
        da.add_artist(
            Rectangle(boxes[i][:2],
                      boxes[i][2], boxes[i][3], facecolor=color))
    return da

def network_graph(result_space, diagram_path, sim):
    logging.getLogger('multiworld').setLevel(logging.WARN)
    from matplotlib.offsetbox import AnnotationBbox
    from matplotlib import pyplot as plt
    plt.set_loglevel("info")
    all_points = [point for point in result_space.index.values()]
    sorted_points = sorted(list(set(all_points)), key=lambda x: f'{x.step}{x.key}')
    nonzeros = [point for point in sorted_points if not qn.zerop(point.weight)]
    graph_points = sorted_points
    layers = defaultdict(list)
    max_step = max([point.step for point in all_points])
    for p in graph_points:
        layers[p.step] += [p]
    for k, v in layers.items():
        layers[k] = sorted(v, key=lambda x: x.key)
    layer_max = max([len(x) for x in layers.values()])
    exe_graph = nx.MultiDiGraph()
    exe_graph.add_nodes_from(graph_points)
    exe_nodes = list(exe_graph.nodes)
    rejected = []
    for node in exe_nodes:
        for succ in node.successors:
            if succ not in graph_points:
                rejected.append(succ)
                continue
            if node.key != succ.key and not exe_graph.has_edge(node, succ):
                exe_graph.add_edge(node, succ)
    pos = nx.multipartite_layout(exe_graph, layers)
    fig, ax = plt.subplots()
    fig.set_size_inches(11, 8.5)
    ax.axis('off')
    nx.draw_networkx_edges(exe_graph, pos=pos, ax=ax, arrows=True, arrowstyle='->', arrowsize=5)
    for cs_point, coord in pos.items():
        da = cs_patch(cs_point, layer_max, max_step, sim)
        ab = AnnotationBbox(da, coord, frameon=False)
        ax.add_artist(ab)
    plt.title(sim.title)
    plt.savefig(diagram_path.with_stem(diagram_path.stem + '_graph').with_suffix('.pdf'),
                orientation='landscape', bbox_inches='tight')
    plt.show()

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
        parts = position.split(SEP)
        gname, gwire = parts
        if sim.gates[gname].inputs[gwire]:
            pos_str = sim.pos_value_str(position, 'inputs')
            # pos_str = str(sim.gates[gname].input[gwire])
            cs = f'{pos_str}'
            if len(cs) > 0:
                make1(graph_node_id, f'{gcontent}:\n{cs}')
            else:
                make1(graph_node_id, f'{gcontent}')
        elif show_outputs:
            make1(graph_node_id, f'{gcontent}: None')
        else:
            make1(graph_node_id, f'{gcontent}')
    elif inout == 'out':
        out_pos = f'{gname}{SEP}{wire}'
        gname, gwire = out_pos.split(SEP)
        gate = sim.gates[gname]
        selected = gwire == gate.output_wire
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
