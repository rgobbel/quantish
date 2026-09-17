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
  // the page scrolls in an inner container, not the window
  const scroller = () => {
    let e = el.getRootNode().host || el;
    for (; e && e !== document.documentElement; e = e.parentElement)
      if (/auto|scroll/.test(getComputedStyle(e).overflowY)) return e;
    return document.scrollingElement;
  };
  const goTo = (key) => {
    if (location.hash !== `#sec-${key}`)
      history.replaceState(null, '', `#sec-${key}`);
    apply(key);
    scroller().scrollTo({ top: 0 });
    place();
  };
  // the row is fixed at the top of the viewport (sticky cannot leave
  // its own cell), over a spacer that keeps its place in the flow and
  // gives it its left edge and width
  const spacer = document.createElement('div');
  spacer.className = 'suite-nav-spacer';
  const nav = document.createElement('nav');
  nav.className = 'suite-nav';
  for (const [key, label] of model.get('sections') || []) {
    const a = document.createElement('a');
    a.href = `#sec-${key}`;
    a.dataset.key = key;
    a.textContent = label;
    nav.appendChild(a);
  }
  el.appendChild(spacer);
  el.appendChild(nav);
  // (a ResizeObserver never fires in marimo's page, so the placement
  // is redone by frame until the spacer has a width, on every switch,
  // and on window resize)
  // the cell's output block wraps the widget in marimo's margins;
  // the row needs none of them
  const block = el.getRootNode().host?.closest?.('.output.block');
  if (block) block.style.margin = '0';
  const place = () => {
    const r = spacer.getBoundingClientRect();
    if (!r.width) return false;
    nav.style.left = `${r.left}px`;
    nav.style.width = `${r.width}px`;
    // the spacer reserves only what the row covers below the spacer's
    // own unscrolled position (the page's top padding already clears
    // the rest)
    const unscrolledTop = r.top + scroller().scrollTop;
    spacer.style.height = `${Math.max(0, nav.offsetHeight - unscrolledTop)}px`;
    return true;
  };
  let tries = 0;
  const settle = () => { if (!place() && tries++ < 600) requestAnimationFrame(settle); };
  settle();
  window.addEventListener('resize', place);
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
    window.removeEventListener('resize', place);
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
