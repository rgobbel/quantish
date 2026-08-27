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
    SVG diagrams); the TikZ renderer does the same in TeX math."""
    s = re.sub(r'(?<=[^\W\d_])(\d+)',
               lambda mt: mt.group(1).translate(_SUBSCRIPT_DIGITS), s)
    return re.sub(r'_([0-9A-Za-zβγρφχ])(?![0-9A-Za-z])',
                  lambda mt: (mt.group(1).translate(_SUBSCRIPT_DIGITS)
                              if mt.group(1).isdigit()
                              else _SUBSCRIPT_LETTERS.get(mt.group(1),
                                                          mt.group(0))), s)


_SUPERSCRIPTS = str.maketrans('0123456789+-=()ni',
                              '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ')

# the LaTeX subset every text surface understands: greek letters and
# the symbols that come up in this domain. TikZ output keeps real
# LaTeX and does not use this table.
_MATH_COMMANDS = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ',
    'epsilon': 'ε', 'zeta': 'ζ', 'eta': 'η', 'theta': 'θ',
    'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ', 'nu': 'ν',
    'xi': 'ξ', 'pi': 'π', 'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ',
    'upsilon': 'υ', 'phi': 'φ', 'varphi': 'φ', 'chi': 'χ',
    'psi': 'ψ', 'omega': 'ω',
    'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ',
    'Xi': 'Ξ', 'Pi': 'Π', 'Sigma': 'Σ', 'Phi': 'Φ', 'Psi': 'Ψ',
    'Omega': 'Ω',
    'angle': '∠', 'times': '×', 'cdot': '·', 'pm': '±', 'mp': '∓',
    'le': '≤', 'leq': '≤', 'ge': '≥', 'geq': '≥', 'ne': '≠',
    'neq': '≠', 'approx': '≈', 'infty': '∞', 'sqrt': '√',
    'sum': '∑', 'prod': '∏', 'int': '∫', 'partial': '∂',
    'to': '→', 'rightarrow': '→', 'leftarrow': '←',
    'ldots': '…', 'dots': '…', 'circ': '°', 'degree': '°',
}


def _subscript_str(s: str) -> str:
    return ''.join(_SUBSCRIPT_LETTERS.get(c, c.translate(_SUBSCRIPT_DIGITS))
                   for c in s)


def math_runs(s: str) -> list:
    """The $...$ label as typographic runs [(fragment, level)] with
    level 0 normal, -1 subscript, +1 superscript — for renderers that
    can shift baselines (SVG tspans). Unicode subscript glyphs only
    exist for digits and a few letters ('b' has none), so wire labels
    like $w_{1b}$ need real subscripts, not glyph substitution."""
    runs = []

    def add(txt, lvl=0):
        if txt:
            if runs and runs[-1][1] == lvl:
                runs[-1][0] += txt
            else:
                runs.append([txt, lvl])

    pos = 0
    for m in re.finditer(r'\$([^$]*)\$', str(s)):
        add(str(s)[pos:m.start()])
        seg = re.sub(r'\\([a-zA-Z]+)',
                     lambda mt: _MATH_COMMANDS.get(mt.group(1),
                                                   mt.group(0)),
                     m.group(1))
        i = 0
        while i < len(seg):
            ch = seg[i]
            if ch in '_^':
                lvl = -1 if ch == '_' else 1
                if i + 1 < len(seg) and seg[i + 1] == '{':
                    j = seg.find('}', i + 2)
                    j = len(seg) if j < 0 else j
                    add(seg[i + 2:j], lvl)
                    i = j + 1
                else:
                    add(seg[i + 1:i + 2], lvl)
                    i += 2
            else:
                add(ch, 0)
                i += 1
        pos = m.end()
    add(str(s)[pos:])
    return [(txt, lvl) for txt, lvl in runs]


_SUB_BACK = {c: b for b, c in zip('0123456789', '₀₁₂₃₄₅₆₇₈₉')}
_SUB_BACK.update({'ₐ': 'a', 'ₑ': 'e', 'ₕ': 'h', 'ᵢ': 'i', 'ⱼ': 'j',
                  'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm', 'ₙ': 'n', 'ₒ': 'o',
                  'ₚ': 'p', 'ᵣ': 'r', 'ₛ': 's', 'ₜ': 't', 'ᵤ': 'u',
                  'ᵥ': 'v', 'ₓ': 'x', '₊': '+', '₋': '−',
                  'ᵦ': 'β', 'ᵧ': 'γ', 'ᵨ': 'ρ', 'ᵩ': 'φ', 'ᵪ': 'χ'})
_SUP_BACK = {c: b for b, c in zip('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')}
_SUP_BACK.update({'ⁱ': 'i', 'ⁿ': 'n', '⁺': '+', '⁻': '−'})


def unicode_runs(s: str) -> list:
    """A string with unicode sub/superscript glyphs as typographic
    runs [(fragment, level)] — the glyphs mapped back to their base
    characters at level -1/+1 so renderers can draw REAL shifted
    scripts, matching math_runs output everywhere."""
    runs = []
    for ch in str(s):
        if ch in _SUB_BACK:
            frag, lvl = _SUB_BACK[ch], -1
        elif ch in _SUP_BACK:
            frag, lvl = _SUP_BACK[ch], 1
        else:
            frag, lvl = ch, 0
        if runs and runs[-1][1] == lvl:
            runs[-1][0] += frag
        else:
            runs.append([frag, lvl])
    return [(frag, lvl) for frag, lvl in runs]


def fmt_label(s) -> str:
    """The one label formatter for every non-TikZ text surface:
    $...$ math becomes unicode (math_to_unicode) and bare digits after
    letters auto-subscript (subscript_digits) — so plain labels need
    no markup at all."""
    return subscript_digits(math_to_unicode(str(s)))


def math_to_unicode(s: str) -> str:
    """$...$ math segments rendered as plain unicode, covering the
    subset the diagrams need: subscripts ($Q_1$ → Q₁, $w_{2a}$ → w₂ₐ),
    superscripts ($x^2$ → x²), greek and symbol commands
    ($\\theta_1 = \\pi/6$ → θ₁ = π/6, $\\angle$ → ∠). For surfaces
    with no LaTeX rendering (the SVG widgets, Mermaid
    labels, chart titles); mo.md surfaces render the math themselves
    and don't need this. Plain text outside $...$ passes through
    untouched."""
    def _segment(m):
        seg = m.group(1)
        seg = re.sub(r'\\([a-zA-Z]+)',
                     lambda c: _MATH_COMMANDS.get(c.group(1),
                                                  c.group(0)), seg)
        seg = re.sub(r'_\{([^{}]*)\}',
                     lambda c: _subscript_str(c.group(1)), seg)
        seg = re.sub(r'_(\S)',
                     lambda c: _subscript_str(c.group(1)), seg)
        seg = re.sub(r'\^\{([^{}]*)\}',
                     lambda c: c.group(1).translate(_SUPERSCRIPTS), seg)
        seg = re.sub(r'\^(\S)',
                     lambda c: c.group(1).translate(_SUPERSCRIPTS), seg)
        return seg.replace('{', '').replace('}', '')
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