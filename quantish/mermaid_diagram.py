from pathlib import Path

from quantish.display import pos_value_str
from quantish.simulation import Simulation
from quantish.util import (SEP, angle_label, fmt_label,
                           math_to_unicode, parse_position)
import quantish.qnumber as qn
import python_mermaid.diagram as pmd
import python_mermaid.link as pml
import python_mermaid.node as pm
from collections import namedtuple
import re
import time

def mmdc_cmd():
    """The mermaid-cli command, with our puppeteer config when present.

    Homebrew's mermaid-cli pins an exact headless-Chrome version that
    breaks on every upgrade; puppeteer-config.json points it at the
    installed Google Chrome instead.
    """
    cmd = ['mmdc']
    pconfig = Path(__file__).resolve().parents[1] / 'puppeteer-config.json'
    if pconfig.exists():
        cmd += ['-p', str(pconfig)]
    return cmd


DiagramFields = namedtuple('DiagramFields', ('field', 'label'))

gate_fields = {'upper': DiagramFields(field='upper', label='UPPER'),
               'lower': DiagramFields(field='lower', label='LOWER'),
               'control': DiagramFields(field='control', label='CONTROL')}



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

    def entry_annotation():
        # a particle entering the circuit here shows its signed weight in
        # the port rectangle ('p1 +1.00'); interior ports stay bare, their
        # values being visible as the upstream gate's outputs
        src = sim.sources.get(position)
        if src is not None and SEP not in src and src in sim.particles:
            weight = qn.to_float(sim.particles[src].weight.real)
            return f'\n{src} {weight:+.{sim.precision}f}'
        return ''

    if inout == 'in':
        # interior in-ports mirror the upstream output port's value block
        # (deliberately redundant); circuit-entry ports show the arriving
        # particle's weight instead
        content = f'{gcontent}{entry_annotation()}'
        src = sim.sources.get(position)
        if show_outputs and src is not None and SEP in src:
            src_value = pos_value_str(sim, src)
            if src_value is not None:
                content = f'{gcontent}:\n{src_value}'
        make1(graph_node_id, content)
    elif inout == 'out':
        out_pos = f'{gname}{SEP}{wire}'
        # TODO(roadmap: Mermaid after-diagrams): mark the sampled/selected
        # output once port values come from final-world marginals.
        selected = False
        out_value_str = pos_value_str(sim, out_pos) if show_outputs else None
        cs = '' if not show_outputs else (out_value_str
                                          if out_value_str is not None else 'None')
        # sinks only exist for ports that actually carry a value
        if (show_outputs and out_pos not in sim.links.keys()
                and out_value_str is not None):
            sink_nodes += [make1(f'{position}_SINK',
                                 f'{gcontent}:\n{out_value_str}',
                                 shape='stadium-shape')]
        if len(cs) > 0:
            make1(graph_node_id, f'{gcontent}:\n{cs}', bold=selected)
        else:
            make1(graph_node_id, f'{gcontent}', bold=selected)
    elif inout == '':
        out_value_str = pos_value_str(sim, position) if show_outputs else None
        occupied = out_value_str is not None
        cs = '' if not show_outputs else (out_value_str if occupied else 'None')
        if (show_outputs and position not in sim.links.keys() and occupied):
            sink_nodes += [make1(f'{position}_SINK',
                                 f'{gcontent}:\n{out_value_str}',
                                 shape='stadium-shape')]
        if len(cs) > 0:
            make1(graph_node_id, f'{gcontent}: {cs}', bold=occupied)
        else:
            make1(graph_node_id, f'{gcontent}{entry_annotation()}', bold=occupied)
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

    _wire_labels = getattr(sim, 'wire_labels', {})

    def wire_label(source):
        # the model's label for the wire leaving `source` (the book's
        # w₂, w₂ₐ... names), shown as the mermaid edge label
        return fmt_label(_wire_labels.get(source, ''))

    mermaid_nodes = {}
    if has_run:
        title = f'{sim.title} after run at {time.asctime()}'
    else:
        title = f'{sim.title}, {time.asctime()}'
    diag = pmd.Diagram(title=title, orientation='left to right')
    phase_graphs = {}
    mermaid_links = []

    if getattr(sim, 'caption', ''):
        # the model's caption, as a free-standing box ahead of the circuit
        # (node content is emitted inside double quotes: escape any).
        # Captions are Markdown; when one uses markers, wrap it as a
        # mermaid "markdown string" (backticks inside the quotes) so the
        # bold/italics render instead of showing literal asterisks.
        caption_node = pmd.Node(id='model_caption')
        # $...$ math has no renderer here: convert to unicode subscripts
        text = math_to_unicode(sim.caption).replace('"', '#quot;')
        if any(marker in text for marker in ('*', '_')):
            text = f'`{text}`'
        caption_node.content = text
        diag.add_nodes([caption_node])

    # a minimum-length link shape for the output stubs, so the dangling
    # wires hug their gate instead of stretching a full rank
    pml.LINK_SHAPES.setdefault('short', '--')

    def stub_anchor(node_id, label=None):
        # the outer end of a labeled stub wire: a Mermaid edge needs a
        # node at both ends, so the wire ends at a box that is invisible
        # except for its content (the custom shape smuggles in a style
        # line, as the bold HACK does). OUTPUT stubs carry their label
        # here — at the outer end, outside the gate box, where an edge
        # label would land inside the cluster; INPUT stubs get a blank
        # anchor and carry the label on the edge, which lays out tighter.
        shape_name = f'{node_id}_invis'
        base = pm.NODE_SHAPES['normal']
        pm.NODE_SHAPES[shape_name] = pm.NodeShape(
            start=base.start,
            end=base.end + f'\nstyle {node_id} fill:transparent,'
                           f'stroke:transparent')
        node = pmd.Node(node_id, shape=shape_name)
        node.content = fmt_label(label) if label else ' '
        mermaid_nodes[node.id] = node
        diag.add_nodes([node])
        return node

    for particle_name, particle in sim.particles.items():
        pname = particle_name.split('<')[0]
        particle_node = pmd.Node(id=pname, shape='stadium-shape')
        # name + sign only; the weight shows at the entry port instead
        psign = '+' if qn.to_float(particle.sign) >= 0 else '-'
        particle_node.content = f'{pname}{psign}'
        mermaid_nodes[pname] = particle_node
        diag.add_nodes([particle_node])

    # null-INPUT stub anchors join the model here, with the particles:
    # ELK honors model order, so they must precede the gates to be laid
    # out on the left, feeding in like the particles do
    for _key in _wire_labels:
        if _key.startswith('>'):
            stub_anchor(f'{_key[1:]}_nullin')
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
                # a symbolic angle spec labels the gate verbatim with its
                # degrees appended; a numeric one shows degrees only
                _angle = fmt_label(
                    angle_label(sim.config.gates[gname].angle,
                                gate.theta.degrees))
                _phase = sim.config.gates[gname].get('phase')
                if _phase is not None:
                    _angle += ' φ=' + fmt_label(
                        angle_label(_phase, gate.phase.degrees))
                gg.header = f'subgraph {gname}["{gname}: {_angle}"]'
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
                mermaid_links.append(pmd.Link(
                    ctrl_input_node, ctrl_gate_node,
                    message=wire_label(ctrl_source_name)))
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
        elif has_run:
            # value-less sinks aren't created; .get covers empty ports
            dest_node = mermaid_nodes.get(f'{control_pos}_SINK')
        if dest_node is not None:
            mermaid_links.append(pmd.Link(ctrl_gate_node, dest_node,
                                          message=wire_label(control_pos)))
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
                        mermaid_links.append(pmd.Link(
                            switch_input_node, switch_node,
                            message=wire_label(switch_input)))
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
                        dest_node = mermaid_nodes.get(f'{switch_pos}_SINK')
                    if dest_node is not None:
                        mermaid_links.append(pmd.Link(
                            switch_node, dest_node,
                            message=wire_label(switch_pos)))

    # Labeled null-input/output stubs, drawn only because a label asks
    # for them (input anchors were created up with the particles for
    # left-side placement; output anchors join last, landing rightmost).
    # A labeled unlinked output whose value SINK exists after a run
    # already shows its label on that sink's edge above.
    for key, stub_label in _wire_labels.items():
        into = key.startswith('>')
        port = key[1:] if into else key
        if (not into and port in sim.links) or SEP not in port:
            continue
        gname, wname = port.split(SEP)
        if is_delay(gname):
            port_node = mermaid_nodes.get(gname)
        elif wname == 'control':
            port_node = mermaid_nodes.get(port)
        else:
            port_node = mermaid_nodes.get(f'{port}_{"in" if into else "out"}')
        if port_node is None:
            continue
        if into:
            anchor = mermaid_nodes[f'{port}_nullin']
            mermaid_links.append(pmd.Link(
                anchor, port_node,
                message=f'"{fmt_label(stub_label)}"'))
        elif f'{port}_SINK' not in mermaid_nodes:
            anchor = stub_anchor(f'{port}_nullout', stub_label)
            # switch-output stubs hug their gate; the control stub keeps
            # the normal length (it exits from mid-cluster)
            shape = 'normal' if wname == 'control' else 'short'
            mermaid_links.append(pmd.Link(port_node, anchor, shape=shape))

    diag.add_links(mermaid_links)
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
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(styled_diag)
    return diag
