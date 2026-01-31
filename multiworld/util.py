import logging
from enum import IntEnum
from itertools import accumulate

import networkx as nx
from addict import Addict
from multiworld.qnumber import Complex, isq, issym, Real
from graphlib import TopologicalSorter
from collections import defaultdict, deque
import sympy as sym
import cmath as cm
import math as m
from sympy import N
import numpy as np
from logging import StreamHandler
import sys
import random

SEP = '.'

log = logging.getLogger('multiworld')

SWITCH_WIRES = ('upper', 'lower')
WIRES = ('control',) + SWITCH_WIRES
OTHER = {'upper': 'lower', 'lower': 'upper'}
STRAIGHT = {w: w for w in SWITCH_WIRES}
SWAPPED = {w: OTHER[w] for w in SWITCH_WIRES}

def default_wires():
    return {wire: [] for wire in WIRES}

def default_switches():
    return {wire: [] for wire in SWITCH_WIRES}

INITIAL_WIRES = lambda: {k: 'undefined' for k in ['control', 'upper', 'lower']}

class Sign(IntEnum):
    minus = -1
    plus = 1

    def __repr__(self):
        if self.value == 1:
            return '+'
        elif self.value == -1:
            return '-'
        else:
            raise ValueError(f'Unexpected value for sign: {self.value}')

    def __str__(self):
        if self.value == 1:
            return '+'
        elif self.value == -1:
            return '-'
        else:
            raise ValueError(f'Unexpected value for sign: {self.value}')

astr = lambda x: ', '.join([str(s) for s in x]) if x else 'None'

GENSYM_NAMES = defaultdict(int)

class Gensym:
    def __init__(self, label='g'):
        global GENSYM_NAMES
        self.n = GENSYM_NAMES[label]
        GENSYM_NAMES[label] += 1
        self.label = f'{label}_{self.n:02d}'
        self.name = self.label

    def __repr__(self):
        return self.name

def to_float(x):
    try:
        result = float(x)
    except TypeError:
        if x.imag == 0:
            # if sym.im(x) == 0:
            result = complex(x).real
        else:
            raise
    return result

def enough(x, threshold):
    if not x: return False
    flx = to_float(x)
    tx = to_float(threshold)
    # return (not np.isclose(flx, 0)) and flx >= threshold
    return flx >= tx

ZERO_THRESHOLD = 1e-19

def filter_weights(particles, threshold=ZERO_THRESHOLD):
    # return particles
    return [p for p in particles if enough(p.probability, threshold)]

def rotate(w, theta):
    return w * cm.exp(1j * theta)

class QLogger(StreamHandler):
    def __init__(self, stream=None):
        super().__init__(sys.stdout)
    def emit(self, record):
        super().emit(record)
        super().flush()

def wangle(weight:Complex):
    # if weight == 0:
    #     return f'{angstr(0)}'
    # elif weight.imag == 0:
    #     return f'{angstr(0)}'
    # else:
    return f'{angstr(cm.phase(weight))}'

def angstr(theta, precision=0):
    try:
        n_theta = N(theta)
        if type(n_theta) not in (int, float, sym.Float):
            n_theta = cm.phase(n_theta)
        if n_theta == 0: n_theta = 0
        return f'∆{m.degrees(n_theta):.{precision}f}º'
    except ZeroDivisionError:
        return '∆0º'

def wstr(xc, precision=1):
    if isq(xc):
        xc = xc.v
    if issym(xc):
        frep = sym.re(xc).as_real_imag()[0]
        fimp = sym.im(xc).as_real_imag()[0]
    else:
        frep = xc.real
        fimp = xc.imag
    return f'{frep:.{precision}f}{fimp:+.{precision}f}j{wangle(xc)}'

def sstr(sign:Sign):
    return str(sign)

def parse_position(pos:str):
    parts = pos.split(SEP)
    if len(parts) == 1:
        return parts[0]
    else:
        return parts

def topo_sort(links):
    sorter = TopologicalSorter()
    reverse_links = defaultdict(list)
    link_tuples = []
    for source, dest in links.items():
        link_tuples += [(source, dest)]
        source_parts = source.split(SEP)
        dest_parts = dest.split(SEP)
        if len(dest_parts) == 2:
            dest_gate, dest_wire = dest_parts
            if dest_wire != 'control':
                other_dest = f'{dest_gate}{SEP}{OTHER[dest_wire]}'
                link_tuples += [(source, other_dest)]
    for source, dest in link_tuples:
        source_parts = source.split(SEP)
        dest_gate, dest_wire = dest.split(SEP)
        if len(source_parts) == 1: # particle
            particle = source_parts[0]
            sorter.add(particle)
            reverse_links[dest_gate] += [particle]
        else:
            source_gate, source_wire = source_parts
            reverse_links[dest_gate] += [source_gate]
    for dest, reverse_links in reverse_links.items():
        sorter.add(dest, *reverse_links)
    order = sorter.static_order()
    return list(order)

def make_gate_subgraph(graph, gate_name):
    if gate_name not in graph:
        graph.add_node(gate_name, qtype='gate')
        graph.add_node(f'{gate_name}.control_in', qtype='port', gate=gate_name, wire='control', direction='input')
        graph.add_node(f'{gate_name}.control_out', qtype='port', gate=gate_name, wire='control', direction='output')
        graph.add_edge(f'{gate_name}.control_in', gate_name, edge_type='hack')
        graph.add_edge(gate_name, f'{gate_name}.control_out', edge_type='hack')
        for wire in SWITCH_WIRES:
            graph.add_node(f'{gate_name}.{wire}_in', qtype='port', gate=gate_name, wire=wire, direction='input')
            graph.add_node(f'{gate_name}.{wire}_out', qtype='port', gate=gate_name, wire=wire, direction='output')
            # graph.add_edge(f'{gate_name}.{wire}_in', f'{gate_name}.{wire}_out', edge_type='internal')
            # graph.add_edge(f'{gate_name}.{wire}_in', f'{gate_name}.{OTHER[wire]}_out', edge_type='internal')
            graph.add_edge(f'{gate_name}.{wire}_in', gate_name, edge_type='hack')
            graph.add_edge(gate_name, f'{gate_name}.{wire}_out', edge_type='hack')

def expand_graph(links):
    expanded_links = nx.MultiDiGraph()
    for source, dest in links.items():
        source_parts = source.split(SEP)
        if len(source_parts) == 1:
            if source not in expanded_links:
                expanded_links.add_node(source, qtype='particle')
                expanded_links.add_edge(source, f'{dest}_in', edge_type='external')
        else:
            source_gate, source_wire = source_parts
            dest_gate, _ = dest.split('.')
            make_gate_subgraph(expanded_links, dest_gate)
            make_gate_subgraph(expanded_links, source_gate)
            expanded_links.add_edge(f'{source}_out', f'{dest}_in', edge_type='external')
    return expanded_links

def simplify_graph(links):
    slinks = nx.DiGraph()
    for source_pos, dest_pos in links.items():
        source_parts = source_pos.split(SEP)
        dest_parts = dest_pos.split(SEP)
        dest_gate, dest_wire = dest_parts
        if len(source_parts) == 1:
            source_type = 'particle'
            source = source_pos
        else:
            source_type = 'gate'
            source_gate, source_wire = source_parts
            source = source_gate
        if source not in slinks:
            slinks.add_node(source, qtype=source_type)
        if dest_gate not in slinks:
            slinks.add_node(dest_gate, qtype='gate')
        slinks.add_edge(source, dest_gate)
    return slinks

def path_lengths(links):
    log.debug(f'{links=}')
    particles = []
    gates = set()
    list_links = {}
    gate_depths = defaultdict(dict)
    particle_depths = defaultdict(dict)
    for key in links.keys():
        key_parts = key.split(SEP)
        if len(key_parts) == 1:
            particles.append(key)
        else:
            gate, port = key_parts
            gates.add(gate)
    log.debug(f'{particles=}, {gates=}')
    for key in links.keys():
        depth = 0
        while links.get(key):
            key_next = links[key]
            gate, port = key_next.split(SEP)
            if port in SWITCH_WIRES:
                list_links[key] = [key_next, f'{gate}{SEP}{OTHER[port]}']
            else:
                list_links[key] = [key_next]
            log.debug(f'list_links[{key}]={list_links[key]}')
            depth += 1
            key = key_next
    log.debug(f'{list_links=}')
    depths = {}
    ppositions = defaultdict(list)
    for particle in particles:
        queue = deque([particle])
        depth = 0
        while queue:
            log.debug(f'{queue=}')
            for _ in range(len(queue)):
                node = queue.popleft()
                ppositions[particle] += [node]
                node_parts = node.split(SEP)
                if len(node_parts) == 2:
                    gate, port = node.split(SEP)
                    if gate not in gate_depths.keys():
                        gate_depths[gate] = {particle: depth}
                    elif particle not in gate_depths[gate].keys():
                        gate_depths[gate][particle] = depth
                    else:
                        gate_depths[gate][particle] = max(gate_depths[gate][particle], depth)
                    if particle not in particle_depths.keys():
                        particle_depths[particle] = {gate: depth}
                    elif gate not in particle_depths[particle].keys():
                        particle_depths[particle][gate] = depth
                    else:
                        particle_depths[particle][gate] = max(particle_depths[particle][gate], depth)
                children =  list_links.get(node)
                if children: queue += children
            depth += 1
        depths[particle] = depth
    log.debug(f'{depths=}')
    log.debug(f'{gate_depths=}')
    log.debug(f'{particle_depths=}')
    log.debug(f'{ppositions=}')
    return depths, gate_depths, particle_depths, ppositions

def normalize_list(data):
    total = sum(data)
    if total == 0: return data
    return [x/total for x in data]

def select(weights:list[float], threshold:float):
    " return the index of the selected value "
    if not weights: return 0
    target = list(accumulate(normalize_list(weights)))
    result = len(weights) - 1
    for i in range(len(weights)):
        if target[i] >= threshold:
            result = i
            break
    return result

def max_width(items):
    return max([len(str(x)) for x in items])

def flat_list(l: list, *, max_depth: int=100) -> list:
    def flat_list_recursive(l,depth):
        for elem in l:
            if isinstance(elem, list) and depth:
                flat_list_recursive(elem,depth-1)
            else:
                out.append(elem)
    if not isinstance(l, list): return [l]
    out = []
    flat_list_recursive(l,max_depth)
    return out
