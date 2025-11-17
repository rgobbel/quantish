from itertools import accumulate

from quantish.qnumber import Complex, isq, issym
from graphlib import TopologicalSorter
from collections import defaultdict
import sympy as sym
import cmath as cm
import math as m
from sympy import N
import numpy as np
from logging import StreamHandler
import sys

SEP = '.'

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
    return (not np.isclose(flx, 0)) and flx >= threshold

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

# def angstr(theta):
#     if hasattr(theta, 'radians'):
#         theta = theta.radians
#     if type(theta) in (int, float):
#         theta = float(theta)
#     degs = float(theta.degrees)
#     return f'∆{degs:.0f}º'

def angstr(theta):
    try:
        nx = N(theta)
        if type(nx) not in (int, float, sym.Float):
            nx = cm.phase(nx)
        if nx == 0: nx = 0
        txstr = f'{m.degrees(nx):.0f}'
        if txstr == '-0': txstr = '0'
        return f'∆{txstr}º'
    except ZeroDivisionError:
        return '∆0º'

def wstr(xc, precision=1):
    # theta = xc.phase
    pstr = f'%+.{precision}f'
    zstr = (f'%+.{precision}f' % 0.0)
    mstr = zstr.replace('+', '-')
    if isq(xc):
        xc = xc.v
    if issym(xc):
        frep = sym.re(xc).as_real_imag()[0]
        fimp = sym.im(xc).as_real_imag()[0]
    else:
        frep = xc.real
        fimp = xc.imag
    freps = pstr % frep
    if freps == mstr: freps = zstr
    fimps = pstr % fimp
    if fimps == mstr: fimps = zstr
    return f'{freps}{fimps}j{wangle(xc)}'

def sstr(sign:int):
    return '+' if sign > 0 else '-'


def parse_position(pos:str):
    parts = pos.split(SEP)
    if len(parts) == 1:
        return parts[0]
    else:
        return parts

def topo_sort(links):
    sorter = TopologicalSorter()
    reverse_links = defaultdict(list)
    for k, v in links.items():
        source = parse_position(k)
        dest = parse_position(v)
        if isinstance(source, str):
            sorter.add(source)
            gate_name = dest[0]
            reverse_links[gate_name] += [source]
        else:
            gate_name, _ = source
            if isinstance(dest, str):
                reverse_links[dest] += [gate_name]
            else:
                dest_gate_name, _ = dest
                reverse_links[dest_gate_name] += [gate_name]
    for dest, reverse_links in reverse_links.items():
        sorter.add(dest, *reverse_links)
    order = sorter.static_order()
    return list(order)

def normalize_list(data):
    total = sum(data)
    if total == 0: return data
    return [x/total for x in data]

def select(weights, selector):
    target = list(accumulate(normalize_list(weights)))
    for i in range(len(weights)):
        if target[i] > selector:
            return i
    return len(weights)-1