"""How the displays name a particle's two sign values.

The engine's sign is `util.Sign` (+1 / −1) and never changes. What
changes is the vocabulary the displays and prose use for it, a
process-wide setting like `CalcMode.mode`:

- 'pm', the book's: plus and minus, written before the name ('+p1',
  '−p1', '±p1' for a particle superposed over both), the attribute
  called the *sign*
- 'hv', the polarization vocabulary: H and V, written as a superscript
  after the name (p1ᴴ, p1ⱽ, p1ᴴ⁄ⱽ for both), the attribute called the
  *polarization*

The CLI and the tests keep 'pm' (the golden outputs are the book's);
the apps default to 'hv' and switch from their UI (`apps.common`).
Every display goes through `mark`, `label`, `attr`, or `word`; prose
carries `⟦…⟧` tokens that `prose` expands (see it)."""
from __future__ import annotations

import re

STYLES = ('pm', 'hv')


class SignStyle:
    """The current vocabulary: 'pm' or 'hv'."""
    style = 'pm'


def set_style(style: str) -> str:
    if style not in STYLES:
        raise ValueError(f'sign style {style!r}: one of {STYLES}')
    SignStyle.style = style
    return style


def hv() -> bool:
    return SignStyle.style == 'hv'


def _int(sign) -> int:
    """A sign however it comes — Sign, int, or a mark ('+', '-', '−',
    '1', '-1', 'H', 'V'; '±', '0', 'H/V' for both) — as +1, −1, or 0."""
    if isinstance(sign, str):
        s = sign.strip()
        if s in ('+', '1', '+1', 'H', 'plus'):
            return 1
        if s in ('-', '−', '-1', 'V', 'minus'):
            return -1
        if s in ('±', '0', 'H/V', 'both'):
            return 0
        raise ValueError(f'not a sign: {sign!r}')
    return (int(sign) > 0) - (int(sign) < 0)


# the superscript forms of H, V, and H/V for plain text (tables,
# Mermaid, the terminal); SVG text draws real superscript runs instead
SUP = {'H': 'ᴴ', 'V': 'ⱽ', 'H/V': 'ᴴ⁄ⱽ'}
_HTML_SUP = {'ᴴ': '<sup>H</sup>', 'ⱽ': '<sup>V</sup>', 'ᴴ⁄ⱽ': '<sup>H/V</sup>'}


def mark(sign) -> str:
    """The sign's mark: '+' / '−' (pm) or 'H' / 'V' (hv); both signs
    give `both()`."""
    s = _int(sign)
    if s == 0:
        return both()
    if hv():
        return 'H' if s > 0 else 'V'
    return '+' if s > 0 else '−'


def both() -> str:
    """The mark of a particle superposed over both signs."""
    return 'H/V' if hv() else '±'


def word(sign) -> str:
    """The sign as prose says it: 'plus' / 'minus', or 'H' / 'V'."""
    s = _int(sign)
    if hv():
        return both() if s == 0 else 'H' if s > 0 else 'V'
    return 'both' if s == 0 else 'plus' if s > 0 else 'minus'


def adjective(sign) -> str:
    """The sign as an adjective: 'plus-sign' / 'minus-sign', or
    'horizontally polarized' / 'vertically polarized'."""
    s = _int(sign)
    if hv():
        return 'horizontally polarized' if s > 0 else 'vertically polarized'
    return 'plus-sign' if s > 0 else 'minus-sign'


def attr(capital: bool = False) -> str:
    """What the attribute is called: 'sign' or 'polarization'."""
    a = 'polarization' if hv() else 'sign'
    return a.capitalize() if capital else a


def label(name: str, sign, html: bool = False) -> str:
    """A signed name as text: '+p1' / '−p1' / '±p1', or p1ᴴ / p1ⱽ /
    p1ᴴ⁄ⱽ (with `html`, a real <sup>)."""
    m = mark(sign)
    if not hv():
        return f'{m}{name}'
    return f'{name}{_HTML_SUP[SUP[m]] if html else SUP[m]}'


def label_runs(name_runs: list, sign) -> list:
    """The SVG text runs of a signed name: `name_runs` ([(fragment,
    level), …], level −1 sub, 0 plain, +1 super) with the sign's mark
    before it (pm) or as a superscript after it (hv)."""
    if hv():
        return list(name_runs) + [(mark(sign), 1)]
    return [(mark(sign), 0)] + list(name_runs)


def label_tex(body: str, sign) -> str:
    """A signed name in TeX math (no $): '+p_1' or 'p_1^{H}'."""
    s = _int(sign)
    if hv():
        return rf'{body}^{{{mark(s)}}}' if s else rf'{body}^{{H/V}}'
    return (r'\pm ' if s == 0 else '+' if s > 0 else '-') + body


def group_display(key: str, particle: str = '', html: bool = False) -> str:
    """A sweep or screen group's display name from its key: the keys
    are the engine's ('+', '−', a gate name, or '+E1' for both); a
    sign key names the sorting particle ('+p2' / p2ᴴ), a both key the
    gate (+E1 / E1ᴴ)."""
    if key in ('+', '−', '-'):
        return label(particle, key, html) if particle else mark(key)
    if len(key) > 1 and key[0] in '+−-':
        return label(key[1:], key[0], html)
    return key


def coordinate_key(coordinate: str) -> str:
    """A sweep's group_by coordinate as the engine keys it: 'sign'
    (also spelled 'polarization' in a model file), 'position', 'both'."""
    return 'sign' if coordinate == 'polarization' else coordinate


def coordinate_name(coordinate: str) -> str:
    """A coordinate key as the current vocabulary names it."""
    if coordinate == 'sign':
        return attr()
    if coordinate == 'both':
        return f'{attr()} and position'
    return coordinate


def to_html(text: str) -> str:
    """Plain-text superscript marks as real <sup> tags, for HTML that
    was built from `label` text."""
    for k, v in _HTML_SUP.items():
        text = text.replace(k, v)
    return text


_TOKEN = re.compile(r'⟦([^⟦⟧]+)⟧')


def prose(text: str) -> str:
    """Expand the sign tokens in a piece of prose. `⟦+⟧` `⟦−⟧` `⟦±⟧`
    are the marks, `⟦plus⟧` `⟦minus⟧` the words, `⟦plus-sign⟧`
    `⟦minus-sign⟧` the adjectives ('vertically polarized'), `⟦sign⟧` `⟦Sign⟧`
    `⟦signs⟧` the attribute, and `⟦+p_2⟧` (a mark, then a TeX name) a
    signed name in math ('$+p_2$' or '$p_2^{H}$')."""
    def one(m):
        tok = m.group(1)
        if tok in ('+', '−', '-', '±'):
            return mark(tok)
        if tok in ('plus', 'minus'):
            return word(tok)
        if tok in ('plus-sign', 'minus-sign'):
            return adjective(tok.split('-')[0])
        if tok == 'sign':
            return attr()
        if tok == 'Sign':
            return attr(capital=True)
        if tok == 'signs':
            return attr() + 's'
        if tok[0] in '+−-±':
            return f'${label_tex(tok[1:], tok[0])}$'
        raise ValueError(f'unknown sign token ⟦{tok}⟧')
    return _TOKEN.sub(one, text)
