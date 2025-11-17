from quantish.simulation_v2 import Simulation
from quantish.util import SEP, parse_position
import python_mermaid.diagram as pm
from collections import namedtuple
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

def make_gnode(sim, gname, inout, wire, mermaid_nodes):
    sink_nodes = []
    def make1(node_id, content, shape='normal'):
        gnode = pm.Node(node_id, shape=shape)
        mermaid_nodes[node_id] = gnode
        gnode.content = content
        return gnode
    position = f'{gname}{SEP}{wire}'
    sep = '' if inout == '' else '_'
    graph_node_id = f'{position}{sep}{inout}'
    gcontent = f'{gate_fields[wire].label}'
    if inout == 'in':
        if position in sim.state_dict.keys():
            pos_str = sim.pos_value_str(position)
            cs = f'{pos_str}'
            make1(graph_node_id, f'{gcontent}: {cs}')
        else:
            make1(graph_node_id, 'None')
    elif inout == 'out':
        out_pos = f'{gname}{SEP}{wire}'
        pos_sink = sim.sinks.get(out_pos)
        if pos_sink is None:
            cs = f'None'
        else:
            cs = f'{pos_sink.vstr}'
        if out_pos not in sim.links.keys():
            sink_node_id = f'{position}_sink'
            sink_nodes += [make1(sink_node_id, f'{gcontent}: {cs}', shape='stadium-shape')]
        make1(graph_node_id, f'{gcontent}: {cs}')
    elif inout == '':
        pos_sink = sim.sinks.get(position)
        if pos_sink is None:
            cs = 'None'
        else:
            cs = f'{pos_sink.vstr}'
        if position not in sim.links.keys():
            sink_node_id = f'{position}_sink'
            sink_nodes += [make1(sink_node_id, f'{gcontent}: {cs}', shape='stadium-shape')]
        make1(graph_node_id, f'{gcontent}: {cs}')
    return sink_nodes

def gnodes(sim, gname, mermaid_nodes):
    sink_nodes = []
    sink_nodes += make_gnode(sim, gname, '', 'control', mermaid_nodes)
    for switch_set in ('upper', 'lower'):
        for inout in ('in', 'out'):
            sink_nodes += make_gnode(sim, gname, inout, switch_set, mermaid_nodes)
    return sink_nodes

def diagram(sim:Simulation, output_file=None, has_run=False):
    mermaid_nodes = {}
    norm_in = f'{"not " if not sim.normalize_inputs else ""}normalizing inputs'
    norm_out = f'{"not " if not sim.normalize_outputs else ""}normalizing outputs'
    merge = f'{"not " if not sim.merge_before_measure else ""}merging before measuring'
    combine = f'{"not " if not sim.combine_signs else ""}combining signs'
    parms = f'{norm_in}, {norm_out}, {merge}, {combine}'
    mode = f'{"SYMBOLIC" if sim.symbolic else "FLOATING POINT"}'
    title = f"{sim.title} {'after' if has_run else 'before'} run at {time.asctime()} {parms}, {mode}"
    diag = pm.Diagram(title=title, orientation='left to right')
    phase_graphs = {}
    mermaid_links = []
    for particle_name, particle in sim.particles.items():
        pcontent = particle.ps(short=True)
        pname = particle_name.split('<')[0]
        particle_node = pm.Node(id=pname, shape='stadium-shape')
        particle_node.content = pcontent
        mermaid_nodes[pname] = particle_node
        diag.add_nodes([particle_node])
    # for delay_name, delay_gate in sim.delay_gates.items():
    #     dgcontent = 'D'
    #     dgnode = pm.Node(id=delay_name)
    #     dgnode.content = dgcontent
    #     mermaid_nodes[delay_name] = dgnode
    for phase_name, phase_gates in sim.phases.items():
        pg = diag.add_subgraph(phase_name)
        phase_graphs[phase_name] = pg
        for gate_name in phase_gates:
            gate = sim.gates[gate_name]
            gg = pg.add_subgraph(gate_name)
            gg.header = f'subgraph {gate_name}["{gate_name}: {float(gate.theta.degrees):.0f}º"]'
            ggi = gg.add_subgraph(f'{gate_name}.inputs')
            ggi.header = f'subgraph {gate_name}.inputs[inputs]'
            ggo = gg.add_subgraph(f'{gate_name}.outputs')
            ggo.header = f'subgraph {gate_name}.outputs[outputs]'
            sink_nodes = gnodes(sim, gate_name, mermaid_nodes)
            diag.add_nodes(sink_nodes)
            gg.add_nodes([mermaid_nodes[f'{gate_name}.{gate_fields['control'].field}']])
            ggi.add_nodes([mermaid_nodes[f'{gate_name}.{gate_fields['upper'].field}_in'],
                           mermaid_nodes[f'{gate_name}.{gate_fields['lower'].field}_in']])
            ggo.add_nodes([mermaid_nodes[f'{gate_name}.{gate_fields['upper'].field}_out'],
                           mermaid_nodes[f'{gate_name}.{gate_fields['lower'].field}_out']])
            mermaid_links += [
                pm.Link(mermaid_nodes[f'{gate_name}.{gate_fields['upper'].field}_in'],
                        mermaid_nodes[f'{gate_name}.{gate_fields['upper'].field}_out'], shape='dotted'),
                pm.Link(mermaid_nodes[f'{gate_name}.{gate_fields['upper'].field}_in'],
                        mermaid_nodes[f'{gate_name}.{gate_fields['lower'].field}_out'], shape='dotted'),
                pm.Link(mermaid_nodes[f'{gate_name}.{gate_fields['lower'].field}_in'],
                        mermaid_nodes[f'{gate_name}.{gate_fields['lower'].field}_out'], shape='dotted'),
                pm.Link(mermaid_nodes[f'{gate_name}.{gate_fields['lower'].field}_in'],
                        mermaid_nodes[f'{gate_name}.{gate_fields['upper'].field}_out'], shape='dotted')]
    for gate_name, gate in sim.gates.items():
        control_pos = f'{gate_name}{SEP}control'
        ctrl_gate_node = mermaid_nodes[control_pos]
        if control_pos in sim.reverse_links.keys():
            ctrl_source_name = sim.reverse_links[control_pos]
            ctrl_source_parts = parse_position(ctrl_source_name)
            if type(ctrl_source_parts) is str:
                ctrl_input_node = mermaid_nodes[ctrl_source_name]
                mermaid_links.append(pm.Link(ctrl_input_node, ctrl_gate_node))
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
        mermaid_links.append(pm.Link(ctrl_gate_node, dest_node))
        for switch_set in ('upper', 'lower'):
            switch_pos = f'{gate_name}{SEP}{switch_set}'
            for inout in ('in', 'out'):
                switch_node_id = f'{switch_pos}_{inout}'
                switch_node = mermaid_nodes[switch_node_id]
                if inout == 'in' and switch_pos in sim.reverse_links.keys():
                    switch_input = sim.reverse_links[switch_pos]
                    input_pos = parse_position(switch_input)
                    if type(input_pos) is str:
                        switch_input_node = mermaid_nodes[switch_input]
                        mermaid_links.append(pm.Link(switch_input_node, switch_node))
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
                    mermaid_links.append(pm.Link(switch_node, dest_node))

    diag.add_links(mermaid_links)
    diag.graph.header = 'flowchart LR'
    diag.pretty_print = True
    if output_file is not None:
        with open(output_file, 'w') as f:
            f.write(str(diag))
    return diag
