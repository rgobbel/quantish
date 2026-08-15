from quantish.simulation import Simulation
from quantish.util import SEP, parse_position
from quantish.particle import Particle
import quantish.qnumber as qn
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

def make_gnode(sim, gname, inout, wire, mermaid_nodes, show_ratios=False, ratios=None):
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
            pos_str = sim.pos_value_str(position)
            # pos_str = str(sim.gates[gname].input[gwire])
            cs = f'{pos_str}'
            make1(graph_node_id, f'{gcontent}:\n{cs}')
        else:
            make1(graph_node_id, f'{gcontent}: None')
    elif inout == 'out':
        out_pos = f'{gname}{SEP}{wire}'
        gname, gwire = out_pos.split(SEP)
        gate = sim.gates[gname]
        selected = gwire == gate.output_wire
        out_value_str = sim.pos_value_str(out_pos)
        # pos_sink = sim.sinks.get(out_pos)
        if out_value_str is None:
            cs = f'None'
        else:
            cs = f'{out_value_str}'
        if out_pos not in sim.links.keys():
            if show_ratios:
                ratio = ratios[gwire]
                ratio_str = f' ({ratio:.0%})'
            else:
                ratio_str = ''
            sink_node_id = f'{position}_sink'
            sink_nodes += [make1(sink_node_id, f'{gcontent}:\n{cs}{ratio_str}', shape='stadium-shape')]
        make1(graph_node_id, f'{gcontent}:\n{cs}', bold=selected)
    elif inout == '':
        out_value_str = sim.pos_value_str(position)
        if out_value_str is None:
            cs = 'None'
        else:
            cs = f'{out_value_str}'
        if position not in sim.links.keys():
            sink_node_id = f'{position}_sink'
            sink_nodes += [make1(sink_node_id, f'{gcontent}:\n{cs}', shape='stadium-shape')]
        make1(graph_node_id, f'{gcontent}: {cs}', bold=sim.pos_value_str(position))
    return sink_nodes

def gnodes(sim, gname, mermaid_nodes):
    gate = sim.gates[gname]
    upper = f'{gname}{SEP}upper'
    lower = f'{gname}{SEP}lower'
    if upper not in sim.links.keys() and lower not in sim.links.keys():
        show_ratio = True
        gate = sim.gates[gname]
        upper_probability = Particle.merge(gate.weights['upper']).probability
        lower_probability = Particle.merge(gate.weights['lower']).probability
        total_probability = upper_probability + lower_probability
        if total_probability == 0:
            ratios = {'upper': 0, 'lower': 0}
        else:
            ratios = {'upper': upper_probability / total_probability, 'lower': lower_probability / total_probability}
    else:
        show_ratio = False
        ratios = None
    sink_nodes = []
    sink_nodes += make_gnode(sim, gname, '', 'control', mermaid_nodes)
    for switch_set in ('upper', 'lower'):
        for inout in ('in', 'out'):
            sink_nodes += make_gnode(sim, gname, inout, switch_set, mermaid_nodes, show_ratio, ratios)
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
    **numerics**: {qn.CalcMode.mode}
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
            gg = pg.add_subgraph(gname)
            if gate.last_swap_threshold is None:
                swapstr = 'never used'
            else:
                swapstr = f'{gate.last_swap_threshold:.2f}'
            if callable(gate.forwarding_threshold):
                fwdstr = f'(call){gate.last_forwarding_threshold:.2f}'
            else:
                fwdstr = f'{gate.forwarding_threshold:.2f}'
            gg.header = f'subgraph {gname}["{gname}: {float(gate.theta.degrees):.0f}º, thresholds: swap={swapstr}, fwd={fwdstr}"]'
            ggi = gg.add_subgraph(f'{gname}.input')
            ggi.header = f'subgraph {gname}.input[input]'
            ggo = gg.add_subgraph(f'{gname}.output')
            ggo.header = f'subgraph {gname}.output[output]'
            sink_nodes = gnodes(sim, gname, mermaid_nodes)
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
        ctrl_gate_node = mermaid_nodes[control_pos]
        if control_pos in sim.sources.keys():
            ctrl_source_name = sim.sources[control_pos]
            ctrl_source_parts = parse_position(ctrl_source_name)
            if type(ctrl_source_parts) is str:
                ctrl_input_node = mermaid_nodes[ctrl_source_name]
                mermaid_links.append(pmd.Link(ctrl_input_node, ctrl_gate_node))
        if control_pos in sim.links.keys():
            dest = sim.links[control_pos]
            dest_parts = parse_position(dest)
            if dest_parts[1] == 'control':
                dest_node = mermaid_nodes[dest]
            elif dest_parts[1] == 'input':
                dest_node = mermaid_nodes[dest_parts[0]]
            else:
                dest_node = mermaid_nodes[f'{dest}_in']
        else:
            dest_node = mermaid_nodes[f'{control_pos}_sink']
        mermaid_links.append(pmd.Link(ctrl_gate_node, dest_node))
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
                    if switch_pos in sim.links.keys():
                        dest = sim.links[switch_pos]
                        dest_parts = parse_position(dest)
                        if dest_parts[1] == 'control':
                            dest_node = mermaid_nodes[dest]
                        elif dest_parts[1] == 'input': # delay gate
                            dest_node = mermaid_nodes[dest_parts[0]]
                        else:
                            dest_node = mermaid_nodes[f'{dest}_in']
                    else:
                        dest_node = mermaid_nodes[f'{switch_pos}_sink']
                    mermaid_links.append(pmd.Link(switch_node, dest_node))

    diag.add_links(mermaid_links)
    diag.graph.header = 'flowchart LR\nstyle legend text-align:left'
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
