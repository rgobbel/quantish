import logging
import re
from enum import IntEnum
from typing import Iterable

import networkx as nx
from quantish.qnumber import isq, issym
import sympy as sym
import cmath as cm
import math as m
from sympy import N
from logging import StreamHandler
import sys

SEP = '.'

log = logging.getLogger('quantish')

SWITCH_WIRES = ('upper', 'lower')
WIRES = ('control',) + SWITCH_WIRES
OTHER = {'upper': 'lower', 'lower': 'upper'}

class Sign(IntEnum):
    minus = -1
    NOSIGN = 0
    plus = 1

    def negate(self):
        return self.__class__(0 - self)

    def __neg__(self):
        return self.negate()

    def __repr__(self):
        if self.value == 1:
            return '+'
        elif self.value == -1:
            return '-'
        elif self.value == 0:
            return '*'
        else:
            raise ValueError(f'Unexpected value for sign: {self.value}')

    def __str__(self):
        if self.value == 1:
            return '+'
        elif self.value == -1:
            return '-'
        elif self.value == 0:
            return '*'
        else:
            raise ValueError(f'Unexpected value for sign: {self.value}')

def show_points(points, indent='', loglevel=logging.INFO):
    pad_len = [0] * len(points[0].coords.values())
    for point in points:
        logstr = [f'{coord.key}' for coord in point.coords.values()]
        for i, s in enumerate(logstr):
            pad_len[i] = max(pad_len[i], len(s))
    for point in points:
        logstr = '|'.join([f'{f"{coord.key}":<{pad_len[i]}}' for i, coord in
                               enumerate(point.coords.values())])
        log.log(loglevel, f'{indent}{logstr}:{point.weight.display()}')


class QLogger(StreamHandler):
    def __init__(self, stream=None):
        super().__init__(sys.stdout)
    def emit(self, record):
        super().emit(record)
        super().flush()

def symbolic_angle(spec):
    """The display form of a gate-angle spec when it is symbolic ('pi/6',
    'rad(30)', 'theta1'): the expression verbatim. None when the spec is
    numeric — including the builder's degree-marked entries ('30°') —
    so callers show degrees instead."""
    if not isinstance(spec, str):
        return None
    probe = spec.strip()
    if probe and probe[-1] in '°º˚':
        probe = probe[:-1].strip()
    try:
        float(probe)
        return None
    except ValueError:
        return spec


def angle_label(spec, degrees, degree_sign='º'):
    """Diagram label for a gate angle: a symbolic spec shows verbatim
    with its value in degrees appended, 'pi/6 (30.0º)'; a numeric spec
    shows just the degrees. Long decimal literals inside the spec are
    shortened for display — rad(36.87), not rad(36.8698976458)."""
    symbolic = symbolic_angle(spec)
    deg = f'{float(degrees):.1f}{degree_sign}'
    if symbolic is None:
        return deg
    shown = re.sub(r'\d+\.\d{3,}',
                   lambda mt: f'{float(mt.group()):.2f}', symbolic)
    return f'{shown} ({deg})'


_SUBSCRIPT_DIGITS = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')

# letters (and a few Greek letters) that have Unicode subscript forms,
# for explicit _x subscripts in names like the double-slit's g_φ
_SUBSCRIPT_LETTERS = dict(zip(
    'aehijklmnoprstuvxβγρφχ',
    'ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓᵦᵧᵨᵩᵪ'))


def subscript_digits(s: str) -> str:
    """Digits directly after letters become unicode subscripts, as in the
    book's labels: q5 → q₅, theta2 → theta₂; an explicit underscore
    subscripts a single character where Unicode has a form for it:
    g_p → gₚ, g_φ → gᵩ. For plain-text surfaces (Mermaid labels, the
    Altair diagrams); the TikZ renderer does the same in TeX math."""
    s = re.sub(r'(?<=[A-Za-z])(\d+)',
               lambda mt: mt.group(1).translate(_SUBSCRIPT_DIGITS), s)
    return re.sub(r'_([0-9A-Za-zβγρφχ])(?![0-9A-Za-z])',
                  lambda mt: (mt.group(1).translate(_SUBSCRIPT_DIGITS)
                              if mt.group(1).isdigit()
                              else _SUBSCRIPT_LETTERS.get(mt.group(1),
                                                          mt.group(0))), s)


def math_to_unicode(s: str) -> str:
    """$...$ math segments in caption text rendered as plain unicode:
    $Q_1$ → Q₁, $Q_{12}$ → Q₁₂. For surfaces with no LaTeX rendering
    (Mermaid labels, chart titles); mo.md surfaces render the math
    itself and don't need this."""
    def _segment(m):
        return re.sub(r'_\{?(\w+)\}?',
                      lambda t: t.group(1).translate(_SUBSCRIPT_DIGITS),
                      m.group(1))
    return re.sub(r'\$([^$]+)\$', _segment, s)





def parse_position(pos:str):
    parts = pos.split(SEP)
    if len(parts) == 1:
        return parts[0]
    else:
        return parts

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

def log_seq(name:str, items:Iterable, loglevel=logging.INFO, enum_items=False):
    log.log(loglevel, f'{name}:')
    if isinstance(items, dict):
        items = items.items()
    for i, item in enumerate(items):
        if isinstance(item, tuple) and len(item) == 2:
            k, v = item
            if type(v) in (list, tuple):
                v = ', '.join(v)
            item = ': '.join([str(x) for x in [k, v]])
        else:
            if type(item) in (list, tuple):
                item = ', '.join(item)
        log.log(loglevel, f'   {f"{i}. " if enum_items else ""}{item}')
    log.log(loglevel, ' ')