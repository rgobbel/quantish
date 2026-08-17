import logging


from multiworld.simulation import Simulation
from multiworld.config_space import GatePort
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

def short_config(point, key=None):
    """Compact one-line label for a (classical) world's coordinates: sign, gate, and the
    port initial for each particle, e.g. '+g2c|+g2l|+g3u'. Coordinates
    appear in particle-name order unless a sort key (e.g.
    sim.coord_sort_key) is supplied."""
    coords = point.coords.values()
    if key is not None:
        coords = sorted(coords, key=key)
    parts = []
    for coord in coords:
        port = coord.position.origin or coord.position.endpoint
        if port is None:
            parts.append(f'{sstr(coord.sign)}?')
        else:
            parts.append(f'{sstr(coord.sign)}{port.gate}{(port.port or "c")[0]}')
    return '|'.join(parts)


def circuit_value_figure(sim):
    """PROTOTYPE — the circuit diagram (as in the Mermaid rendering: gates
    with control/upper/lower ports, wires from the model's links, dashed
    group boxes, gate angles) with the quantities shown as colors instead
    of numbers.

    Every port has an in-cell (left edge) and an out-cell (right edge)
    holding one chip per particle±sign present there — hue = particle,
    lightness = signed amplitude (black = −1, mid-gray = 0, white = +1;
    complex → magnitude signed by dominant axis) — plus a monochrome Σ
    chip for the aggregate. Dotted interior wires are the gate's
    straight/cross switch paths; solid wires follow the model's links,
    tinted by the particle that traverses them.
    """
    import colorsys
    from matplotlib import pyplot as plt
    from matplotlib.patches import Rectangle, FancyBboxPatch

    hues = [0.00, 0.33, 0.62, 0.78, 0.09, 0.50]
    pnames = list(sim.particles.keys())
    hue_of = {pname: hues[i % len(hues)] for i, pname in enumerate(pnames)}

    def signed_amp(value):
        try:
            c = complex(value)
        except (TypeError, ValueError):
            return 0.0
        mag = abs(c)
        if mag < 1e-12:
            return 0.0
        ref = c.real if abs(c.real) >= abs(c.imag) else c.imag
        return max(-1.0, min(1.0, mag if ref >= 0 else -mag))

    def chip_color(value, hue=None):
        light = (signed_amp(value) + 1.0) / 2.0
        if hue is None:
            return (light, light, light)
        return colorsys.hls_to_rgb(hue, light, 0.85)

    def port_amps(step, port, end):
        """[(label, value, hue)] for the particles at `port`: one chip per
        particle±sign plus a monochrome Σ chip per particle."""
        if sim.all_points is None:
            return []
        per_sign, per_particle = {}, {}
        for point in sim.all_points.index.values():
            if point.step != step or point.cancelled:
                continue
            for pname, coord in point.coords.items():
                where = (coord.position.origin if end == 'origin'
                         else coord.position.endpoint)
                if where != port:
                    continue
                try:
                    w = complex(point.weight)
                except (TypeError, ValueError):
                    return []  # symbolic with free symbols: no chips
                key = (pname, str(coord.sign))
                per_sign[key] = per_sign.get(key, 0j) + w
                per_particle[pname] = per_particle.get(pname, 0j) + w
        chips = []
        for pname in sorted(per_particle):
            for sign in ('+', '-'):
                if (pname, sign) in per_sign:
                    chips.append((f'{pname}{sign}', per_sign[(pname, sign)],
                                  hue_of.get(pname, 0.0)))
            chips.append(('Σ', per_particle[pname], None))
        return chips

    # ---- layout ---------------------------------------------------------
    GW, RH = 0.66, 0.30          # gate box width, port row height
    CW, CH = 0.26, 0.22          # port cell width/height
    rows = ('control', 'upper', 'lower')
    stage_of = {g: i for i, stage in enumerate(sim.run_stages) for g in stage}
    n_cols = len(sim.run_stages)
    stack_h = max(len(stage) for stage in sim.run_stages)
    gate_h = len(rows) * RH + 0.14

    gate_xy = {}
    for i, stage in enumerate(sim.run_stages):
        n = len(stage)
        for j, g in enumerate(stage):
            gate_xy[g] = (1.0 + 1.55 * i, ((n - 1) / 2.0 - j) * (gate_h + 0.5))

    def cell_xy(gname, port, end):
        gx, gy = gate_xy[gname]
        row_i = rows.index(port) if port in rows else 0
        y = gy + gate_h / 2 - 0.14 - (row_i + 0.5) * RH
        x = gx - GW / 2 + CW / 2 + 0.02 if end == 'in' else gx + GW / 2 - CW / 2 - 0.02
        return x, y

    fig_w = min(3.0 + 2.6 * (n_cols + 1), 26)
    fig_h = min(2.0 + 1.9 * stack_h * (gate_h + 0.5), 20)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    def draw_chips(cx, cy, chips):
        if not chips:
            return
        n = len(chips)
        w = min(CW / n, 0.11)
        x0 = cx - n * w / 2
        for k, (label, value, hue) in enumerate(chips):
            ax.add_patch(Rectangle((x0 + k * w, cy - CH / 2), w, CH,
                                   facecolor=chip_color(value, hue),
                                   edgecolor='0.3', linewidth=0.4, zorder=4))
            ax.annotate(label, (x0 + (k + 0.5) * w, cy - CH / 2), xytext=(0, -2),
                        textcoords='offset points', ha='center', va='top',
                        fontsize=4.5, color='0.35', zorder=4)

    # gates: box, header (name + angle), port rows with in/out cells
    for gname, (gx, gy) in gate_xy.items():
        gate = sim.gates[gname]
        simple = (gate.report_type() == 'DelayGate'
                  or gname in getattr(sim, 'pass_through_gates', set()))
        ax.add_patch(FancyBboxPatch((gx - GW / 2, gy - gate_h / 2), GW, gate_h,
                                    boxstyle='round,pad=0.02',
                                    facecolor='#ffffde', edgecolor='#aaaa33',
                                    linewidth=1.0, zorder=2))
        try:
            header = f'{gname}: {float(gate.theta.degrees):.1f}º'
        except (AttributeError, TypeError):
            header = gname
        ax.annotate(header if not simple else gname,
                    (gx, gy + gate_h / 2 - 0.02), ha='center', va='top',
                    fontsize=7, color='0.25', zorder=4)
        step = sim.gate_step.get(gname)
        ports = ('control',) if simple else rows
        for port in ports:
            x_in, y_row = cell_xy(gname, port, 'in')
            x_out, _ = cell_xy(gname, port, 'out')
            ax.annotate(port[0], (gx, y_row), ha='center', va='center',
                        fontsize=5, color='0.6', zorder=3)
            for x, end, s in ((x_in, 'endpoint', step - 1),
                              (x_out, 'origin', step)):
                ax.add_patch(Rectangle((x - CW / 2, y_row - CH / 2), CW, CH,
                                       facecolor='#ececec', edgecolor='#999999',
                                       linewidth=0.5, zorder=3))
                draw_chips(x, y_row, port_amps(s, GatePort(gname, port), end))
        if not simple:  # interior straight/cross switch wires, dotted
            for p_in in ('upper', 'lower'):
                for p_out in ('upper', 'lower'):
                    (x1, y1), (x2, y2) = (cell_xy(gname, p_in, 'in'),
                                          cell_xy(gname, p_out, 'out'))
                    ax.plot([x1 + CW / 2, x2 - CW / 2], [y1, y2],
                            color='0.65', lw=0.6, linestyle=':', zorder=2.5)

    # particle sources
    part_xy = {}
    for i, pname in enumerate(pnames):
        y = ((len(pnames) - 1) / 2.0 - i) * 0.8
        part_xy[pname] = (0.0, y)
        ax.add_patch(FancyBboxPatch((-0.18, y - 0.14), 0.36, 0.28,
                                    boxstyle='round,pad=0.02,rounding_size=0.12',
                                    facecolor='#ececec', edgecolor='#999999',
                                    linewidth=0.8, zorder=3))
        ax.annotate(pname, (0.0, y + 0.05), ha='center', va='center',
                    fontsize=7, color='0.25', zorder=4)
        chip = [(str(sim.particles[pname].sign),
                 sim.particles[pname].weight, hue_of[pname])]
        draw_chips(0.0, y - 0.06, chip)

    # wires from the model's links, tinted by the traversing particle
    def wire_carrier(src):
        gname, port = (src.split(SEP) + [None])[:2]
        step = sim.gate_step.get(gname)
        if step is None or sim.all_points is None:
            return None
        carriers = set()
        for point in sim.all_points.index.values():
            if point.step != step or point.cancelled:
                continue
            for pname, coord in point.coords.items():
                if coord.position.origin == GatePort(gname, port):
                    carriers.add(pname)
        return carriers.pop() if len(carriers) == 1 else None

    for src, dst in sim.links.items():
        dst_g, dst_p = dst.split(SEP)
        if dst_g not in gate_xy:
            continue
        dst_p = dst_p if dst_p in rows else 'control'
        x2, y2 = cell_xy(dst_g, dst_p, 'in')
        if SEP in src:
            src_g, src_p = src.split(SEP)
            if src_g not in gate_xy:
                continue
            x1, y1 = cell_xy(src_g, src_p if src_p in rows else 'control', 'out')
            x1 += CW / 2
            carrier = wire_carrier(src)
        else:
            x1, y1 = part_xy[src]
            x1 += 0.20
            carrier = src
        color = (colorsys.hls_to_rgb(hue_of[carrier], 0.45, 0.7)
                 if carrier in hue_of else '0.45')
        ax.annotate('', (x2 - CW / 2, y2), (x1, y1),
                    arrowprops=dict(arrowstyle='-|>', color=color,
                                    lw=1.1, alpha=0.8), zorder=1)

    # dashed group boxes, as in the Mermaid subgraphs
    for group_name, group in sim.diagram_groups.items():
        members = [g for g in group if g in gate_xy]
        if not members:
            continue
        xs = [gate_xy[g][0] for g in members]
        ys = [gate_xy[g][1] for g in members]
        ax.add_patch(FancyBboxPatch(
            (min(xs) - GW / 2 - 0.10, min(ys) - gate_h / 2 - 0.10),
            max(xs) - min(xs) + GW + 0.20,
            max(ys) - min(ys) + gate_h + 0.34,
            boxstyle='round,pad=0.02', fill=False, edgecolor='0.6',
            linewidth=0.9, linestyle='--', zorder=0.5))
        ax.annotate(group_name, ((min(xs) + max(xs)) / 2,
                                 max(ys) + gate_h / 2 + 0.22),
                    ha='center', va='bottom', fontsize=8, color='0.45',
                    style='italic', zorder=4)

    ax.set_xlim(-0.6, 1.0 + 1.55 * (n_cols - 1) + 1.0)
    all_y = [y for _, y in gate_xy.values()] + [y for _, y in part_xy.values()]
    ax.set_ylim(min(all_y) - gate_h, max(all_y) + gate_h + 0.4)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(f'{sim.title} — circuit values', fontsize=11)
    fig.text(0.01, 0.01,
             'cells: left = arriving, right = leaving; chips: hue = particle '
             '(± split), gray chip = Σ per particle; black = −1, mid-gray = 0, '
             'white = +1 (complex → magnitude signed by dominant axis); '
             'dotted = switch paths, arrows = links tinted by particle',
             fontsize=7, color='0.4')
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
        out_value_str = sim.pos_value_str(out_pos)
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
        out_value_str = sim.pos_value_str(position)
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
            make1(graph_node_id, f'{gcontent}: {cs}', bold=sim.pos_value_str(position))
        else:
            make1(graph_node_id, f'{gcontent}', bold=sim.pos_value_str(position))
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
