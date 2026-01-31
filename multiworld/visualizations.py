from multiworld.simulation import Simulation
from multiworld.util import SEP, parse_position
import multiworld.qnumber as qn
import python_mermaid.diagram as pmd
import python_mermaid.node as pm
from collections import namedtuple
import re
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
            sink_node_id = f'{position}_sink'
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
            sink_node_id = f'{position}_sink'
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
    # norm_in = f'{"not " if not sim.normalize_input else ""}normalizing input'
    # norm_out = f'{"not " if not sim.normalize_output else ""}normalizing output'
    # merge = f'{"not " if not sim.merge_before_measure else ""}merging before measuring'
    # combine = f'{"not " if not sim.combine_signs else ""}combining signs'
    # always_forward_controls = f'{"always forward control weights, " if sim.always_forward_control_weights else ""}'
    # always_forward_switches = f'{"always forward switch weights, " if sim.always_forward_switch_weights else ""}'
    # parms = f'{always_forward_controls}{always_forward_switches}{norm_in}, {norm_out}, {merge}, {combine}'
    # mode = f'{"SYMBOLIC" if sim.symbolic else "FLOATING POINT"}'
    # title = f"{sim.title} {'after' if has_run else 'before'} run at {time.asctime()} {parms}, {mode}"
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
    **combine**:
    &nbsp;&nbsp;&nbsp;&nbsp;**signs**: {f"{sim.combine_signs}".lower()}
    &nbsp;&nbsp;&nbsp;&nbsp;**names**: {f"{sim.combine_names}".lower()}
    **normalize**
    &nbsp;&nbsp;&nbsp;&nbsp;**input**: {f"{sim.normalize_input}".lower()}
    &nbsp;&nbsp;&nbsp;&nbsp;**output**: {f"{sim.normalize_output}".lower()}
    **merge before**
    &nbsp;&nbsp;&nbsp;&nbsp;**measure**: {f"{sim.merge_before_measure}".lower()}
    &nbsp;&nbsp;&nbsp;&nbsp;**forward**: {f"{sim.merge_before_forward}".lower()}
    **always forward**
    &nbsp;&nbsp;&nbsp;&nbsp;**control weights**: {f"{sim.always_forward_control_weights}".lower()}
    &nbsp;&nbsp;&nbsp;&nbsp;**switch weights**: {f"{sim.always_forward_switch_weights}".lower()}
    **add with signs**: {f"{sim.add_with_signs}".lower()}
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
    for stage_name, stage in sim.diagram_groups.items():
        stage_id = f'{stage_name}_stage'
        pg = diag.add_subgraph(stage_id)
        pg.header = f'subgraph {stage_id}["{stage_name}"]'
        phase_graphs[stage_id] = pg
        for gname in stage:
            gate = sim.gates[gname]
            if gate.report_type() == 'DelayGate':
                gate_inout = f'{gate.name}{SEP}control'
                if has_run and gate_inout not in sim.links.keys():
                    sink_node_id = f'{gate_inout}_sink'
                    sink_node = pmd.Node(sink_node_id, gate.name, shape='stadium-shape')
                    mermaid_nodes[sink_node_id] = sink_node
                    diag.add_nodes([sink_node])
                gn = pm.Node(gate.name, gate.name, shape='stadium-shape')
                mermaid_nodes[gname] = gn
                pg.add_nodes([gn])
            else:
                gg = pg.add_subgraph(gname)
                gg.header = f'subgraph {gname}["{gname}: {float(gate.theta.degrees):.0f}º"]'
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
                dest_node = mermaid_nodes[f'{control_pos}_sink']
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
                        dest_node = mermaid_nodes[f'{switch_pos}_sink']
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
      considerModelOrder: PREFER_NODES
title:
"""
        styled_diag = re.sub("title:", graph_config, str(diag))
        with open(output_file, 'w') as f:
            f.write(styled_diag)
    return diag
