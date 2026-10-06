"""The sign-vocabulary switch: H / V (polarization, a superscript
after the particle's name) or the book's + / − (before it). The choice
is the page root's `data-signs` attribute — the canvases that draw
labels in the browser read it live — remembered in localStorage across
the site's pages and visits, and synced to Python (`signs`), where
`quantish.signs.set_style` makes it the vocabulary of every display
(quantish.apps.common.apply_signs). The suite's section row draws the
same control at its right end (quantish.apps.suite_nav)."""
from __future__ import annotations

import anywidget
import traitlets

# the control's script, shared with the section row: appends the two
# buttons to `el`, syncing the choice with the model's `trait`
SIGNS_JS = r"""
const SIGNS_KEY = 'quantish-signs';
function signsControl(model, trait) {
  const root = document.documentElement;
  const wrap = document.createElement('span');
  wrap.className = 'signs-toggle';
  wrap.title = "how a particle's two states are written: H and V "
    + "(polarization, a superscript after the name) or the book's "
    + "plus and minus (before it)";
  const label = document.createElement('span');
  label.className = 'signs-label';
  label.textContent = 'states';
  wrap.appendChild(label);
  const btns = {};
  const apply = (key) => {
    if (key !== 'pm' && key !== 'hv') key = 'hv';
    root.setAttribute('data-signs', key);
    for (const [k, b] of Object.entries(btns)) b.classList.toggle('active', k === key);
    try { localStorage.setItem(SIGNS_KEY, key); } catch (e) { /* private mode */ }
    if (model.get(trait) !== key) { model.set(trait, key); model.save_changes(); }
  };
  for (const [key, text] of [['hv', 'H / V'], ['pm', '+ / −']]) {
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.signs = key;
    b.textContent = text;
    b.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); apply(key); });
    wrap.appendChild(b);
    btns[key] = b;
  }
  let stored = null;
  try { stored = localStorage.getItem(SIGNS_KEY); } catch (e) { /* private mode */ }
  model.on(`change:${trait}`, () => apply(model.get(trait)));
  apply(stored || model.get(trait) || 'hv');
  return wrap;
}
"""

SIGNS_CSS = """
.signs-toggle { display: inline-flex; align-items: center; gap: 0.3em;
                font-size: 0.85em; color: #333; }
.signs-toggle .signs-label { margin-right: 0.25em; }
.signs-toggle button { font: inherit; padding: 0.15em 0.6em; line-height: 1.3;
                       border: 1px solid #c8c8c8; background: #fff; color: #333;
                       border-radius: 4px; cursor: pointer; }
.signs-toggle button:hover { background: #f4f5fb; }
.signs-toggle button.active { background: #2b3aa0; color: #fff; border-color: #2b3aa0; }
"""

_ESM = SIGNS_JS + r"""
function render({ model, el }) { el.appendChild(signsControl(model, 'signs')); }
export default { render };
"""


class SignsToggle(anywidget.AnyWidget):
    """The switch on its own, for an app running as its own page.
    `signs`: 'hv' or 'pm', synced both ways."""
    _esm = _ESM
    _css = SIGNS_CSS
    signs = traitlets.Unicode('hv').tag(sync=True)
