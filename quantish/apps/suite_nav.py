"""The suite's section row: an anywidget that shows one section of
the page at a time. Every section is a cell output wrapped in
`<div class="suite-sec suite-sec-<key>">`; the widget keeps the chosen
key in `data-section` on the page's root element, which the
stylesheet (css/suite.css) turns into display rules — so a switch
touches no cell and settles in a frame. The choice is also the URL
fragment (#sec-<key>), so a section can be linked from any prose, and
the widget catches clicks on such links wherever they are on the page
(the fragment alone would not do: marimo moves the address through
the history API, which leaves CSS `:target` behind). `current` syncs
to Python, and setting it from Python switches the page.
"""
from __future__ import annotations

import anywidget
import traitlets

_ESM = r"""
function render({ model, el }) {
  const root = document.documentElement;
  const keyOf = (hash) => (hash || '').replace(/^#sec-/, '');
  const known = () => new Set((model.get('sections') || []).map((s) => s[0]));
  const apply = (key) => {
    if (!known().has(key)) key = 'home';
    root.setAttribute('data-section', key);
    for (const a of el.querySelectorAll('a[data-key]'))
      a.classList.toggle('active', a.dataset.key === key);
    if (model.get('current') !== key) { model.set('current', key); model.save_changes(); }
  };
  const goTo = (key) => {
    if (location.hash !== `#sec-${key}`)
      history.replaceState(null, '', `#sec-${key}`);
    apply(key);
    window.scrollTo({ top: 0 });
  };
  const nav = document.createElement('nav');
  nav.className = 'suite-nav';
  for (const [key, label] of model.get('sections') || []) {
    const a = document.createElement('a');
    a.href = `#sec-${key}`;
    a.dataset.key = key;
    a.textContent = label;
    nav.appendChild(a);
  }
  el.appendChild(nav);
  // a link to a section anywhere on the page opens it (capture phase:
  // ahead of the notebook's own link handling)
  const onClick = (ev) => {
    const a = ev.target && ev.target.closest && ev.target.closest('a[href^="#sec-"]');
    if (!a) return;
    ev.preventDefault();
    ev.stopPropagation();
    goTo(keyOf(a.getAttribute('href')));
  };
  document.addEventListener('click', onClick, true);
  const onHash = () => apply(keyOf(location.hash));
  window.addEventListener('hashchange', onHash);
  model.on('change:current', () => {
    const key = model.get('current');
    if (key && key !== root.getAttribute('data-section')) goTo(key);
  });
  apply(location.hash ? keyOf(location.hash) : (model.get('current') || 'home'));
  return () => {
    document.removeEventListener('click', onClick, true);
    window.removeEventListener('hashchange', onHash);
  };
}
export default { render };
"""


class SectionNav(anywidget.AnyWidget):
    """The section row. `sections`: [(key, label), …]; `current`: the
    key shown (synced both ways)."""
    _esm = _ESM
    sections = traitlets.List([]).tag(sync=True)
    current = traitlets.Unicode('home').tag(sync=True)
