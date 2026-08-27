"""The network builder's drag-and-drop canvas, as an anywidget.

The widget edits the plain-dict graph that quantish.builder consumes:
gates and particles with positions, and links from outputs to inputs.
All drawing is hand-rolled SVG in the same visual language as the
circuit diagrams; there are no external JS dependencies, so the widget
works in the WASM builds too.

Interactions:
  palette        miniature object icons beside the canvas — circuit
                 elements on top (gate, particle, phase plate, delay),
                 the two group kinds below the divider (run stage,
                 diagram group); tooltips name them
  toolbar        delete, clear the canvas (confirmed, and undo-able),
                 undo / redo
  drag body      move a gate or particle (a shift-selection moves
                 together); drag on empty canvas pans the view, and
                 the wheel (or trackpad pinch) zooms around the cursor
  drag out-port  rubber-band a wire; drop on a free in-port to connect
  click          select a gate, particle, or wire (then Delete works)
  shift-click    (also ⌘- or ctrl-click) toggle the clicked object in
                 the multi-selection; the selection holds one kind at a
                 time — clicking another kind starts over with it.
                 Shift-drag on empty canvas sweeps up gates (or, when
                 the box holds no gates, particles)
  double-click   on a name: rename (a particle's prompt takes the sign
                 too; a stage or diagram-group box label renames the
                 whole group) - gate body: edit its angle - phase
                 plate body: its phase - particle body: flip its sign -
                 a wire or port: edit the wire label (an unconnected
                 port labels a null input/output stub)
  keyboard       Delete removes the selection; ⌘Z / ⇧⌘Z undo and redo
"""
import anywidget
import traitlets

_CSS = """
.qb-root { font-family: -apple-system, 'Segoe UI', Helvetica, sans-serif; }
.qb-toolbar { display: flex; gap: 8px; align-items: center;
              flex-wrap: wrap; padding: 6px 2px; }
.qb-toolbar button { font-size: 13px; padding: 4px 10px;
                     border: 1px solid #bbb; border-radius: 6px;
                     background: #fff; cursor: pointer; color: #000;
                     white-space: nowrap; }
.qb-toolbar button:hover { border-color: #5c64d1; background: #f6f7ff; }
.qb-hint { font-size: 12px; color: #000; margin-left: auto; }
.qb-body { display: flex; gap: 8px; align-items: flex-start; }
.qb-palette { display: flex; flex-direction: column; width: 84px;
              border: 1px solid #bbb; border-radius: 8px;
              background: #fff; overflow: hidden; }
.qb-palette button { width: 100%; padding: 6px 2px 7px;
                     border: none; border-radius: 0;
                     border-bottom: 1px solid #e2e2e8;
                     background: #fff; cursor: pointer;
                     display: flex; flex-direction: column;
                     align-items: center; gap: 2px; }
.qb-palette button:last-child { border-bottom: none; }
.qb-palette button:hover { background: #f6f7ff; }
.qb-palette button svg { display: block; width: 48px; height: 42px; }
.qb-palette .qb-pal-label { font-size: 12.5px; color: #000;
                            line-height: 1.1; }
.qb-pal-sep { border-top: 3px double #8b93a0; margin: 0; }
.qb-svg { border: 1px solid #ddd; border-radius: 8px; background: #fff;
          display: block; flex: 1; min-width: 0;
          user-select: none; -webkit-user-select: none; }
.qb-dialog { position: absolute; top: 60px; left: 50%;
             transform: translateX(-50%); z-index: 10;
             background: #fff; border: 1px solid #8b93a0;
             border-radius: 8px; padding: 12px 14px;
             box-shadow: 0 4px 16px rgba(20, 30, 50, 0.18);
             min-width: 340px; font-size: 13px; color: #000; }
.qb-dialog .qb-dlg-title { font-weight: 600; margin-bottom: 8px; }
.qb-dialog input { width: 100%; box-sizing: border-box;
                   font-size: 14px; padding: 5px 8px;
                   border: 1px solid #bbb; border-radius: 5px;
                   color: #000; }
.qb-dialog .qb-dlg-row { display: flex; align-items: center;
                         gap: 8px; margin-top: 10px; }
.qb-dialog .qb-dlg-preview { margin-right: auto; color: #000; }
.qb-dialog button { font-size: 13px; padding: 4px 14px;
                    border: 1px solid #bbb; border-radius: 6px;
                    background: #fff; cursor: pointer; color: #000; }
.qb-dialog button:hover { border-color: #5c64d1; background: #f6f7ff; }
.qb-dialog button.qb-dlg-ok { border-color: #5c64d1;
                              background: #eef1ff; font-weight: 600; }
.qb-dialog button.qb-dlg-ok:hover { background: #dfe5ff; }
"""

_ESM = r"""
const GW = 132, GH = 110;                      // gate box size
const PW = 46, PH = 46;                        // phase-plate box size
const DW = 40, DH = 40;                        // delay-gate box size
const PORT_Y = { control: 48, upper: 72, lower: 96 };
const WIRES = ['control', 'upper', 'lower'];
const PR = 18;                                 // particle half-height
// particles draw as stadiums so longer names fit; width follows the
// name (sign included)
const partW = (name) =>
  Math.max(2 * PR, 16 + 8.5 * (String(name).length + 1));
const C = {
  gateFill: '#e6f4f1', gateStroke: '#2f9e8f',
  plateFill: '#f3e8ff', plateStroke: '#8b5cf6',
  delayFill: '#eef1f8', delayStroke: '#8b93a0',
  portFill: '#e0e7ff', portStroke: '#5c64d1',
  particleFill: '#f4f4f6', particleStroke: '#8b93a0',
  wire: '#22314a', select: '#d97706', target: '#16a34a',
};
const SUB = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅',
             '6':'₆','7':'₇','8':'₈','9':'₉',
             'a':'ₐ','e':'ₑ','h':'ₕ','i':'ᵢ','j':'ⱼ','k':'ₖ',
             'l':'ₗ','m':'ₘ','n':'ₙ','o':'ₒ','p':'ₚ','r':'ᵣ',
             's':'ₛ','t':'ₜ','u':'ᵤ','v':'ᵥ','x':'ₓ',
             'β':'ᵦ','γ':'ᵧ','ρ':'ᵨ','φ':'ᵩ','χ':'ᵪ'};
const SUP = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵',
             '6':'⁶','7':'⁷','8':'⁸','9':'⁹','+':'⁺','-':'⁻',
             '=':'⁼','(':'⁽',')':'⁾','n':'ⁿ','i':'ⁱ'};
// the same LaTeX subset the Python side renders (util.fmt_label);
// TikZ keeps real LaTeX and does not use this
const MATHCMD = {alpha:'α',beta:'β',gamma:'γ',delta:'δ',epsilon:'ε',
  zeta:'ζ',eta:'η',theta:'θ',iota:'ι',kappa:'κ',lambda:'λ',mu:'μ',
  nu:'ν',xi:'ξ',pi:'π',rho:'ρ',sigma:'σ',tau:'τ',upsilon:'υ',
  phi:'φ',varphi:'φ',chi:'χ',psi:'ψ',omega:'ω',
  Gamma:'Γ',Delta:'Δ',Theta:'Θ',Lambda:'Λ',Xi:'Ξ',Pi:'Π',Sigma:'Σ',
  Phi:'Φ',Psi:'Ψ',Omega:'Ω',
  angle:'∠',times:'×',cdot:'·',pm:'±',mp:'∓',le:'≤',leq:'≤',
  ge:'≥',geq:'≥',ne:'≠',neq:'≠',approx:'≈',infty:'∞',sqrt:'√',
  sum:'∑',prod:'∏',int:'∫',partial:'∂',to:'→',rightarrow:'→',
  leftarrow:'←',ldots:'…',dots:'…',circ:'°',degree:'°'};
const _subStr = (s) => [...s].map((c) => SUB[c] ?? c).join('');
const _supStr = (s) => [...s].map((c) => SUP[c] ?? c).join('');
// $...$ math only — wire labels carry explicit subscripts in the
// YAML, so they get no automatic digit-subscripting
const mathOnly = (s) => String(s)
  .replace(/\$([^$]+)\$/g, (m, seg) => seg
    .replace(/\\([a-zA-Z]+)/g, (c, w) => MATHCMD[w] ?? c)
    .replace(/_\{([^{}]*)\}/g, (c, w) => _subStr(w))
    .replace(/_(\S)/g, (c, w) => _subStr(w))
    .replace(/\^\{([^{}]*)\}/g, (c, w) => _supStr(w))
    .replace(/\^(\S)/g, (c, w) => _supStr(w))
    .replace(/[{}]/g, ''));
const subName = (s) => String(s)
  .replace(/\$([^$]+)\$/g, (m, seg) => seg
    .replace(/\\([a-zA-Z]+)/g, (c, w) => MATHCMD[w] ?? c)
    .replace(/_\{([^{}]*)\}/g, (c, w) => _subStr(w))
    .replace(/_(\S)/g, (c, w) => _subStr(w))
    .replace(/\^\{([^{}]*)\}/g, (c, w) => _supStr(w))
    .replace(/\^(\S)/g, (c, w) => _supStr(w))
    .replace(/[{}]/g, ''))
  .replace(/(?<=[A-Za-zφ])(\d+)/g,
           (m) => [...m].map((c) => SUB[c] ?? c).join(''));

// phase plates and delay gates are compact one-wire gates; everything
// geometric branches through these. A delay gate has no ports at all —
// links address it by bare name.
const isPlate = (gd) => gd.kind === 'phase';
const isDelay = (gd) => gd.kind === 'delay';
const dims = (gd) => isPlate(gd) ? [PW, PH]
                   : isDelay(gd) ? [DW, DH] : [GW, GH];
const wiresOf = (gd) => isDelay(gd) ? []
                      : isPlate(gd) ? ['control'] : WIRES;
const portY = (gd, w) => isPlate(gd) || isDelay(gd)
  ? dims(gd)[1] / 2 : PORT_Y[w];

function h(tag, attrs = {}, ...children) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const c of children)
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  return el;
}

function render({ model, el }) {
  el.innerHTML = '';
  const root = document.createElement('div');
  root.className = 'qb-root';
  root.style.position = 'relative';
  const bar = document.createElement('div');
  bar.className = 'qb-toolbar';
  // the add palette: miniature versions of the objects as drawn on
  // the canvas, with tooltips naming them
  const mkIcon = (title, label, body) => {
    const b = document.createElement('button');
    b.title = title;
    b.innerHTML = `<svg viewBox="0 0 40 40">${body}</svg>`
      + `<span class="qb-pal-label">${label}</span>`;
    return b;
  };
  const _dash = (x1, y1, x2, y2) =>
    `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" `
    + 'stroke="#22314a" stroke-width="1" stroke-dasharray="2 2"/>';
  const addGateBtn = mkIcon('add a Fredkin gate', 'gate', `
    <rect x="7" y="3" width="26" height="34" rx="4"
          fill="#e6f4f1" stroke="#2f9e8f" stroke-width="1.6"/>
    <circle cx="20" cy="10" r="2.6" fill="#e0e7ff" stroke="#5c64d1"/>
    ${['18', '28'].map((y) => `
      <circle cx="7" cy="${y}" r="2.4" fill="#e0e7ff" stroke="#5c64d1"/>
      <circle cx="33" cy="${y}" r="2.4" fill="#e0e7ff" stroke="#5c64d1"/>
    `).join('')}
    ${_dash(12, 18, 28, 18)}${_dash(12, 28, 28, 28)}
    ${_dash(12, 18, 28, 28)}${_dash(12, 28, 28, 18)}`);
  const addPlateBtn = mkIcon('add a φ phase plate', 'phase', `
    <rect x="9" y="9" width="22" height="22" rx="5"
          fill="#f3e8ff" stroke="#8b5cf6" stroke-width="1.6"/>
    <text x="20" y="25" text-anchor="middle" font-size="14"
          font-weight="600" fill="#000">φ</text>`);
  const addDelayBtn = mkIcon('add a delay gate', 'delay', `
    <rect x="10" y="10" width="20" height="20" rx="5"
          fill="#eef1f8" stroke="#8b93a0" stroke-width="1.6"/>
    <circle cx="10" cy="20" r="2.4" fill="#e0e7ff" stroke="#5c64d1"/>
    <circle cx="30" cy="20" r="2.4" fill="#e0e7ff" stroke="#5c64d1"/>
    <text x="20" y="24.5" text-anchor="middle" font-size="12"
          font-weight="600" fill="#000">d</text>`);
  const addPartBtn = mkIcon('add a particle', 'particle', `
    <rect x="5" y="12" width="30" height="16" rx="8"
          fill="#f4f4f6" stroke="#8b93a0" stroke-width="1.6"/>
    <circle cx="35" cy="20" r="2.4" fill="#e0e7ff" stroke="#5c64d1"/>
    <text x="19" y="24.5" text-anchor="middle" font-size="11"
          font-weight="600" fill="#000">+p</text>`);
  const _minis = `
    <rect x="10" y="14" width="8" height="12" rx="2"
          fill="#e6f4f1" stroke="#2f9e8f"/>
    <rect x="22" y="14" width="8" height="12" rx="2"
          fill="#e6f4f1" stroke="#2f9e8f"/>`;
  const stageBtn = mkIcon(
    'group the selected gates into a named run stage', 'stage', `
    <rect x="5" y="8" width="30" height="24" rx="6"
          fill="none" stroke="#2f9e8f" stroke-width="1.8"/>${_minis}`);
  const dgroupBtn = mkIcon(
    'group the selected gates into a named diagram group', 'group', `
    <rect x="5" y="8" width="30" height="24" rx="6" fill="none"
          stroke="#22314a" stroke-width="1.4"
          stroke-dasharray="4 3"/>${_minis}`);
  const delBtn = document.createElement('button');
  delBtn.textContent = 'delete selected';
  const clearBtn = document.createElement('button');
  clearBtn.textContent = '✕ clear';
  clearBtn.title = 'wipe the canvas (undo can bring it back)';
  const mkBtn = (label, title) => {
    const b = document.createElement('button');
    b.textContent = label;
    b.title = title;
    return b;
  };
  const undoBtn = mkBtn('↩', 'undo (⌘Z)');
  const redoBtn = mkBtn('↪', 'redo (⇧⌘Z)');
  const hint = document.createElement('div');
  hint.className = 'qb-hint';
  hint.textContent = 'drag output → input to wire · double-click a ' +
    'body to edit, a name to rename · shift-click or shift-drag to ' +
    'select · scroll/pinch zooms, drag on empty space pans';
  bar.append(delBtn, clearBtn, undoBtn, redoBtn, hint);
  const svg = h('svg', { class: 'qb-svg', height: 560 });
  const body = document.createElement('div');
  body.className = 'qb-body';
  const palette = document.createElement('div');
  palette.className = 'qb-palette';
  const sep = document.createElement('div');
  sep.className = 'qb-pal-sep';
  palette.append(addGateBtn, addPartBtn, addPlateBtn, addDelayBtn,
                 sep, stageBtn, dgroupBtn);
  body.append(palette, svg);
  root.append(bar, body);
  el.appendChild(root);

  const graph = () => model.get('graph');
  // per-gate display labels ('pi/6 (30.0°)'), computed Python-side
  // where the specs can actually be evaluated
  const angleLabel = (name, spec) =>
    (model.get('angle_labels') || {})[name] ?? `${spec ?? 0}`;
  // undo history: JSON snapshots of the graph before each commit.
  // Drags mutate the model's graph in place while moving, so they pass
  // their own before-drag snapshot.
  const undoStack = [], redoStack = [];
  const commit = (g, before) => {
    undoStack.push(before ?? JSON.stringify(model.get('graph')));
    if (undoStack.length > 80) undoStack.shift();
    redoStack.length = 0;
    model.set('graph', JSON.parse(JSON.stringify(g)));
    model.save_changes();
  };
  const restore = (snap) => {
    selected = null;
    clearMulti();
    model.set('graph', JSON.parse(snap));
    model.save_changes();
  };
  const undo = () => {
    if (!undoStack.length) return;
    redoStack.push(JSON.stringify(model.get('graph')));
    restore(undoStack.pop());
  };
  const redo = () => {
    if (!redoStack.length) return;
    undoStack.push(JSON.stringify(model.get('graph')));
    restore(redoStack.pop());
  };

  // local, uncommitted interaction state
  let zoom = 1;               // canvas zoom factor
  let pan = { x: 0, y: 0 };   // canvas pan offset, in screen px
  let panning = null;         // {x, y, ox, oy, moved} while dragging
  let selected = null;        // {kind:'gate'|'particle'|'link', key}
  let drag = null;            // {kind, key, dx, dy, others, before}
  let wire = null;            // {src, x, y}
  let marquee = null;         // {x0, y0, x1, y1} shift-drag selection
  const multi = new Set();    // multi-selection keys (one kind at a time)
  let multiKind = null;       // 'gate' | 'particle' | 'link'
  const clearMulti = () => {
    multi.clear();
    multiKind = null;
  };
  const inMultiOf = (kind, key) => multiKind === kind && multi.has(key);

  const outXY = (g, src) => {
    if (src.includes('.')) {
      const [gn, w] = src.split('.');
      const gd = g.gates[gn];
      return gd && [gd.x + dims(gd)[0], gd.y + portY(gd, w)];
    }
    const d = g.gates[src];   // a bare name: delay gate or particle
    if (d) return [d.x + dims(d)[0], d.y + dims(d)[1] / 2];
    const p = g.particles[src];
    return p && [p.x + partW(src), p.y + PR];
  };
  const inXY = (g, dst) => {
    if (!dst.includes('.')) {
      const d = g.gates[dst];
      return d && [d.x, d.y + dims(d)[1] / 2];
    }
    const [gn, w] = dst.split('.');
    const gd = g.gates[gn];
    return gd && [gd.x, gd.y + portY(gd, w)];
  };
  const usedSrc = (g) => new Set(g.links.map((l) => l[0]));
  const usedDst = (g) => new Set(g.links.map((l) => l[1]));

  // A small orthogonal router for the committed wires: straight when
  // clear, else out–channel–in, else a lane detour around the nodes.
  // Wires register their segments so parallel runs spread instead of
  // stacking; corners get rounded in roundedPath. Runs fresh on every
  // redraw, so it tracks drags live.
  function routeWires(g) {
    const M = 8;                 // clearance around nodes
    const obstacles = [];
    for (const [n, gd] of Object.entries(g.gates))
      obstacles.push({ n, r: [gd.x - M, gd.y - M,
                              gd.x + dims(gd)[0] + M,
                              gd.y + dims(gd)[1] + M] });
    for (const [n, p] of Object.entries(g.particles))
      obstacles.push({ n, r: [p.x - M, p.y - M,
                              p.x + partW(n) + M, p.y + 2 * PR + M] });
    // a wire is never blocked by its own endpoints' nodes — it starts
    // and ends on their edges, inside the clearance margin
    let skip = new Set();
    const hBlocked = (y, xa, xb) => obstacles.some(
      ({ n, r: [ax, ay, bx, by] }) => !skip.has(n) &&
        y > ay && y < by &&
        Math.max(Math.min(xa, xb), ax) < Math.min(Math.max(xa, xb), bx));
    const vBlocked = (x, ya, yb) => obstacles.some(
      ({ n, r: [ax, ay, bx, by] }) => !skip.has(n) &&
        x > ax && x < bx &&
        Math.max(Math.min(ya, yb), ay) < Math.min(Math.max(ya, yb), by));
    const usedV = [], usedH = [];
    const SPREAD = 8;
    const vClash = (x, ya, yb) => usedV.some(
      (s) => Math.abs(s.x - x) < SPREAD &&
             Math.max(Math.min(ya, yb), s.a) <
             Math.min(Math.max(ya, yb), s.b));
    const hClash = (y, xa, xb) => usedH.some(
      (s) => Math.abs(s.y - y) < SPREAD &&
             Math.max(Math.min(xa, xb), s.a) + 2 <
             Math.min(Math.max(xa, xb), s.b) - 2);
    const register = (pts) => {
      for (let j = 0; j + 1 < pts.length; j++) {
        const [x1, y1] = pts[j], [x2, y2] = pts[j + 1];
        if (Math.abs(y1 - y2) < 0.5)
          usedH.push({ y: y1, a: Math.min(x1, x2), b: Math.max(x1, x2) });
        else
          usedV.push({ x: x1, a: Math.min(y1, y2), b: Math.max(y1, y2) });
      }
    };

    const endNode = (e) => e.includes('.') ? e.split('.')[0] : e;
    return g.links.map((l) => {
      const a = outXY(g, l[0]), b = inXY(g, l[1]);
      if (!a || !b) return null;
      skip = new Set([endNode(l[0]), endNode(l[1])]);
      const [sx, sy] = a, [dx, dy] = b;
      let pts = null;
      if (Math.abs(dy - sy) < 1 && dx > sx + 4 &&
          !hBlocked(sy, sx + 1, dx - 1) && !hClash(sy, sx, dx))
        pts = [[sx, sy], [dx, dy]];
      if (!pts && dx > sx + 2 * SPREAD) {
        // a vertical channel between the endpoints, fanned around the
        // midpoint until everything clears
        for (let k = 0; k < 24 && !pts; k++) {
          const f = 0.5 + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 0.06;
          if (f < 0.04 || f > 0.96) continue;
          const cx = sx + (dx - sx) * f;
          if (!hBlocked(sy, sx + 1, cx) && !hBlocked(dy, cx, dx - 1) &&
              !vBlocked(cx, sy, dy) && !vClash(cx, sy, dy) &&
              !hClash(sy, sx, cx) && !hClash(dy, cx, dx))
            pts = [[sx, sy], [cx, sy], [cx, dy], [dx, dy]];
        }
      }
      if (!pts) {
        // detour: out right, along a lane above or below, in from the
        // left
        for (let k = 0; k < 10 && !pts; k++) {
          const out = sx + 14 + k * SPREAD;
          const inn = dx - 14 - k * SPREAD;
          if (vClash(out, sy, sy) || vClash(inn, dy, dy)) continue;
          for (const dir of [1, -1]) {
            for (let off = 26; off <= 400 && !pts; off += 14) {
              const ly = dir > 0 ? Math.max(sy, dy) + off
                                 : Math.min(sy, dy) - off;
              if (ly < -200) break;
              if (hBlocked(ly, Math.min(out, inn), Math.max(out, inn))
                  || hClash(ly, Math.min(out, inn), Math.max(out, inn))
                  || vBlocked(out, sy, ly) || vBlocked(inn, ly, dy)
                  || vClash(out, sy, ly) || vClash(inn, ly, dy))
                continue;
              pts = [[sx, sy], [out, sy], [out, ly],
                     [inn, ly], [inn, dy], [dx, dy]];
            }
            if (pts) break;
          }
        }
      }
      if (!pts) pts = [[sx, sy], [dx, dy]];   // give up gracefully
      register(pts);
      return pts;
    });
  }

  function roundedPath(pts) {
    if (pts.length < 3)
      return `M ${pts[0][0]} ${pts[0][1]} L ${pts[1][0]} ${pts[1][1]}`;
    let d = `M ${pts[0][0]} ${pts[0][1]}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const [px, py] = pts[i - 1], [bx, by] = pts[i];
      const [nx, ny] = pts[i + 1];
      const din = Math.hypot(bx - px, by - py) || 1;
      const dout = Math.hypot(nx - bx, ny - by) || 1;
      const r = Math.min(7, din / 2, dout / 2);
      d += ` L ${bx - (bx - px) / din * r} ${by - (by - py) / din * r}`
         + ` Q ${bx} ${by}`
         + ` ${bx + (nx - bx) / dout * r} ${by + (ny - by) / dout * r}`;
    }
    return d + ` L ${pts[pts.length - 1][0]} ${pts[pts.length - 1][1]}`;
  }

  function svgPoint(ev) {
    const r = svg.getBoundingClientRect();
    return [(ev.clientX - r.left - pan.x) / zoom,
            (ev.clientY - r.top - pan.y) / zoom];
  }

  function wirePath(x1, y1, x2, y2) {
    const mx = Math.max(30, Math.abs(x2 - x1) / 2);
    return `M ${x1} ${y1} C ${x1 + mx} ${y1}, ${x2 - mx} ${y2}, ` +
           `${x2} ${y2}`;
  }

  function redraw() {
    const g = graph();
    svg.innerHTML = '';
    const layer = h('g', zoom === 1 && !pan.x && !pan.y ? {} : {
      transform: `translate(${pan.x} ${pan.y}) scale(${zoom})`,
    });
    svg.appendChild(layer);
    const srcTaken = usedSrc(g), dstTaken = usedDst(g);

    // group outlines first, behind everything: diagram groups (dark
    // dashed, outermost), then run-stage boxes (teal) inside them
    const outline = (kind, byName, pad, top, style) => {
      for (const [gname, grpd] of Object.entries(byName)) {
        const members = grpd.ds;
        const x1 = Math.min(...members.map((m) => m.x)) - pad;
        const y1 = Math.min(...members.map((m) => m.y)) - top;
        const x2 = Math.max(...members.map((m) => m.x + dims(m)[0]))
                   + pad;
        const y2 = Math.max(...members.map((m) => m.y + dims(m)[1]))
                   + pad;
        layer.appendChild(h('rect', {
          x: x1, y: y1, width: x2 - x1, height: y2 - y1, rx: 10,
          fill: 'none', 'stroke-width': 1, 'pointer-events': 'none',
          ...style,
        }));
        // the label renames on double-click
        layer.appendChild(h('text', {
          x: x1 + 8, y: y1 + 13, 'font-size': 11.5, fill: '#000',
          'font-style': 'italic', 'data-grouplabel': gname,
          'data-groupkind': kind, style: 'cursor: pointer',
        }, subName(gname)));
      }
    };
    const dgroups = {}, stageBoxes = {};
    for (const [gn, gd] of Object.entries(g.gates)) {
      if (gd.dgroup) {
        (dgroups[gd.dgroup] ??= { ds: [], names: [] });
        dgroups[gd.dgroup].ds.push(gd);
        dgroups[gd.dgroup].names.push(gn);
      }
      if (gd.stage) {
        (stageBoxes[gd.stage] ??= { ds: [], names: [] });
        stageBoxes[gd.stage].ds.push(gd);
        stageBoxes[gd.stage].names.push(gn);
      }
    }
    // a diagram group that exactly coincides with a run stage (same
    // name, same gates) is the stage — one box stands for both
    const distinctGroups = Object.fromEntries(
      Object.entries(dgroups).filter(([n, d]) => {
        const s = stageBoxes[n];
        return !(s && s.names.length === d.names.length &&
                 d.names.every((x) => s.names.includes(x)));
      }));
    outline('dgroup', distinctGroups, 18, 34,
            { stroke: C.wire, 'stroke-dasharray': '6 4' });
    outline('stage', stageBoxes, 8, 20, { stroke: C.gateStroke });

    // wires next, under the nodes — routed orthogonally with rounded
    // corners, like the results diagram
    const routed = routeWires(g);
    g.links.forEach((l, i) => {
      const pts = routed[i];
      if (!pts) return;
      const d = roundedPath(pts);
      const sel = (selected?.kind === 'link' && selected.key === i)
                  || inMultiOf('link', i);
      layer.appendChild(h('path', {
        d, fill: 'none',
        stroke: sel ? C.select : C.wire, 'stroke-width': sel ? 3 : 2,
        'data-link': i, style: 'cursor: pointer',
      }));
      // a fatter invisible hit area so wires are clickable
      layer.appendChild(h('path', {
        d, fill: 'none', stroke: 'transparent',
        'stroke-width': 10, 'data-link': i, style: 'cursor: pointer',
      }));
    });

    // wire labels: on the wire near its source; plus labeled stubs at
    // unconnected ports ('>g.port' null inputs, bare-key null outputs)
    const wl = g.wire_labels || {};
    const wlText = (x, y, label) => {
      const el = h('text', {
        x, y, 'text-anchor': 'middle', 'font-size': 11,
        'font-style': 'italic', fill: '#000', 'pointer-events': 'none',
      });
      // $...$ math as real sub/superscript tspans (unicode lacks
      // subscript forms for most letters, e.g. the book's w1b)
      const parts = String(label).split(/\$([^$]*)\$/);
      parts.forEach((seg, i) => {
        if (i % 2 === 0) {
          if (seg) el.appendChild(document.createTextNode(seg));
          return;
        }
        seg = seg.replace(/\\([a-zA-Z]+)/g,
                          (c, w) => MATHCMD[w] ?? c);
        let j = 0;
        while (j < seg.length) {
          const ch = seg[j];
          if (ch === '_' || ch === '^') {
            let frag;
            if (seg[j + 1] === '{') {
              const end = seg.indexOf('}', j + 2);
              frag = seg.slice(j + 2, end < 0 ? seg.length : end);
              j = (end < 0 ? seg.length : end) + 1;
            } else {
              frag = seg.slice(j + 1, j + 2);
              j += 2;
            }
            el.appendChild(h('tspan', {
              'font-size': '64%',
              'baseline-shift': ch === '_' ? '-25%' : '38%',
            }, frag));
          } else {
            el.appendChild(document.createTextNode(ch));
            j += 1;
          }
        }
      });
      layer.appendChild(el);
    };
    g.links.forEach((l, i) => {
      if (!wl[l[0]] || !routed[i]) return;
      const [x0, y0] = routed[i][0];
      wlText(x0 + 24, y0 - 7, wl[l[0]]);
    });
    for (const [key, label] of Object.entries(wl)) {
      if (key.startsWith('>')) {
        const end = key.slice(1);
        if (dstTaken.has(end)) continue;
        const p = inXY(g, end);
        if (!p) continue;
        layer.appendChild(h('line', {
          x1: p[0] - 30, y1: p[1], x2: p[0] - 2, y2: p[1],
          stroke: C.wire, 'stroke-width': 2,
        }));
        wlText(p[0] - 18, p[1] - 7, label);
      } else if (!srcTaken.has(key)) {
        const p = outXY(g, key);
        if (!p) continue;
        layer.appendChild(h('line', {
          x1: p[0] + 2, y1: p[1], x2: p[0] + 30, y2: p[1],
          stroke: C.wire, 'stroke-width': 2,
        }));
        wlText(p[0] + 18, p[1] - 7, label);
      }
    }

    for (const [name, gd] of Object.entries(g.gates)) {
      const [w0, h0] = dims(gd);
      const plate = isPlate(gd);
      const delay = isDelay(gd);
      const sel = selected?.kind === 'gate' && selected.key === name;
      const inMulti = inMultiOf('gate', name);
      const grp = h('g', { 'data-gate': name, style: 'cursor: move' });
      grp.appendChild(h('rect', {
        x: gd.x, y: gd.y, width: w0, height: h0, rx: 8,
        fill: plate ? C.plateFill : delay ? C.delayFill : C.gateFill,
        stroke: (sel || inMulti) ? C.select
                                 : plate ? C.plateStroke
                                 : delay ? C.delayStroke : C.gateStroke,
        'stroke-width': (sel || inMulti) ? 2.5 : 1.5,
        ...(inMulti && !sel ? { 'stroke-dasharray': '5 3' } : {}),
      }));
      if (delay) {
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + h0 / 2 + 5,
          'text-anchor': 'middle',
          'font-size': 14, 'font-weight': 600, fill: '#000',
          'data-name': name,
        }, subName(name)));
      } else if (plate) {
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + h0 / 2 - 3, 'text-anchor': 'middle',
          'font-size': 15, 'font-weight': 600, fill: '#000',
          'data-name': name,
        }, subName(name)));
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + h0 - 8, 'text-anchor': 'middle',
          'font-size': 11.5, fill: '#000',
        }, subName(angleLabel(name, gd.phase))));
      } else {
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + 18, 'text-anchor': 'middle',
          'font-size': 15, 'font-weight': 600, fill: '#000',
          'data-name': name,
        }, subName(name)));
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + 37, 'text-anchor': 'middle',
          'font-size': 11.5, fill: '#000',
        }, subName(angleLabel(name, gd.angle))));
        // the network diagram's dotted straight-and-crossed switch
        // lines between the two switch-wire rows
        const xA = gd.x + 46, xB = gd.x + w0 - 46;
        const yU = gd.y + PORT_Y.upper, yL = gd.y + PORT_Y.lower;
        for (const [xa, ya, xb, yb] of [[xA, yU, xB, yU],
                                        [xA, yL, xB, yL],
                                        [xA, yU, xB, yL],
                                        [xA, yL, xB, yU]])
          grp.appendChild(h('line', {
            x1: xa, y1: ya, x2: xb, y2: yb, stroke: C.wire,
            'stroke-width': 1, 'stroke-dasharray': '3 3',
            'pointer-events': 'none',
          }));
      }
      for (const w of wiresOf(gd)) {
        const y = gd.y + portY(gd, w);
        if (!plate && w === 'control') grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: y + 4, 'text-anchor': 'middle',
          'font-size': 11.5, fill: '#000',
        }, w));
        else if (!plate) {
          // switch-wire names sit at both the in and the out side,
          // like the network diagram's port boxes
          grp.appendChild(h('text', {
            x: gd.x + 10, y: y + 4, 'text-anchor': 'start',
            'font-size': 11.5, fill: '#000',
          }, w));
          grp.appendChild(h('text', {
            x: gd.x + w0 - 10, y: y + 4, 'text-anchor': 'end',
            'font-size': 11.5, fill: '#000',
          }, w));
        }
        const inKey = `${name}.${w}`;
        const inOk = wire && !dstTaken.has(inKey);
        grp.appendChild(h('circle', {
          cx: gd.x, cy: y, r: 6,
          fill: dstTaken.has(inKey) ? C.portStroke : C.portFill,
          stroke: inOk ? C.target : C.portStroke,
          'stroke-width': inOk ? 2.5 : 1.5,
          'data-inport': inKey, style: 'cursor: crosshair',
        }));
        const outKey = `${name}.${w}`;
        grp.appendChild(h('circle', {
          cx: gd.x + w0, cy: y, r: 6,
          fill: srcTaken.has(outKey) ? C.portStroke : C.portFill,
          stroke: C.portStroke, 'stroke-width': 1.5,
          'data-outport': outKey, style: 'cursor: crosshair',
        }));
      }
      if (delay) {
        const y = gd.y + h0 / 2;
        const inOk = wire && !dstTaken.has(name);
        grp.appendChild(h('circle', {
          cx: gd.x, cy: y, r: 6,
          fill: dstTaken.has(name) ? C.portStroke : C.portFill,
          stroke: inOk ? C.target : C.portStroke,
          'stroke-width': inOk ? 2.5 : 1.5,
          'data-inport': name, style: 'cursor: crosshair',
        }));
        grp.appendChild(h('circle', {
          cx: gd.x + w0, cy: y, r: 6,
          fill: srcTaken.has(name) ? C.portStroke : C.portFill,
          stroke: C.portStroke, 'stroke-width': 1.5,
          'data-outport': name, style: 'cursor: crosshair',
        }));
      }
      layer.appendChild(grp);
    }

    for (const [name, p] of Object.entries(g.particles)) {
      const sel = selected?.kind === 'particle' && selected.key === name;
      const inMulti = inMultiOf('particle', name);
      const pw = partW(name);
      const grp = h('g', { 'data-particle': name, style: 'cursor: move' });
      grp.appendChild(h('rect', {
        x: p.x, y: p.y, width: pw, height: 2 * PR, rx: PR,
        fill: C.particleFill,
        stroke: (sel || inMulti) ? C.select : C.particleStroke,
        'stroke-width': (sel || inMulti) ? 2.5 : 1.5,
        ...(inMulti && !sel ? { 'stroke-dasharray': '5 3' } : {}),
      }));
      grp.appendChild(h('text', {
        x: p.x + pw / 2, y: p.y + PR + 4, 'text-anchor': 'middle',
        'font-size': 14, 'font-weight': 600, fill: '#000',
        'data-name': name,
      }, (p.sign < 0 ? '−' : '+') + subName(name)));
      grp.appendChild(h('circle', {
        cx: p.x + pw, cy: p.y + PR, r: 6,
        fill: srcTaken.has(name) ? C.portStroke : C.portFill,
        stroke: C.portStroke, 'stroke-width': 1.5,
        'data-outport': name, style: 'cursor: crosshair',
      }));
      layer.appendChild(grp);
    }

    if (wire) {
      const a = outXY(g, wire.src);
      if (a) layer.appendChild(h('path', {
        d: wirePath(...a, wire.x, wire.y), fill: 'none',
        stroke: C.select, 'stroke-width': 2, 'stroke-dasharray': '5 4',
        'pointer-events': 'none',
      }));
      // generous invisible drop zones over the free in-ports, drawn
      // last so releasing near a port lands the wire
      for (const [name, gd] of Object.entries(g.gates)) {
        if (isDelay(gd)) {
          if (!dstTaken.has(name)) layer.appendChild(h('circle', {
            cx: gd.x, cy: gd.y + dims(gd)[1] / 2, r: 16,
            fill: 'transparent', 'data-inport': name,
            style: 'cursor: crosshair',
          }));
          continue;
        }
        for (const w of wiresOf(gd)) {
          const key = `${name}.${w}`;
          if (dstTaken.has(key)) continue;
          layer.appendChild(h('circle', {
            cx: gd.x, cy: gd.y + portY(gd, w), r: 16,
            fill: 'transparent', 'data-inport': key,
            style: 'cursor: crosshair',
          }));
        }
      }
    }

    if (marquee) layer.appendChild(h('rect', {
      x: Math.min(marquee.x0, marquee.x1),
      y: Math.min(marquee.y0, marquee.y1),
      width: Math.abs(marquee.x1 - marquee.x0),
      height: Math.abs(marquee.y1 - marquee.y0),
      fill: 'rgba(217, 119, 6, 0.08)', stroke: C.select,
      'stroke-width': 1, 'stroke-dasharray': '4 3',
      'pointer-events': 'none',
    }));
  }

  function nextName(prefix, coll) {
    let i = 1;
    while (coll[`${prefix}${i}`]) i += 1;
    return `${prefix}${i}`;
  }

  // first slot not already occupied — slot #count lands on top of an
  // existing component once anything has been deleted
  function freeSpot(taken, slot) {
    for (let i = 0; ; i++) {
      const [x, y] = slot(i);
      if (!taken.some((p) => Math.abs(p.x - x) < 30 &&
                             Math.abs(p.y - y) < 30))
        return [x, y];
    }
  }
  const gateSlot = (i) => [170 + (i % 4) * 190,
                           40 + Math.floor(i / 4) * 150];
  const partSlot = (i) => [24, 60 + i * 70];

  // one add path for click (default slot) and palette-drag (at the
  // drop point)
  function addObject(kind, at) {
    const g = graph();
    const copy = JSON.parse(JSON.stringify(g));
    if (kind === 'particle') {
      const name = nextName('p', g.particles);
      const [x, y] = at
        ? [Math.max(0, at[0] - PR), Math.max(0, at[1] - PR)]
        : freeSpot(Object.values(g.particles), partSlot);
      copy.particles[name] = { x, y, sign: 1, weight: 1 };
    } else {
      const proto = kind === 'phase' ? { kind: 'phase', phase: 0 }
                  : kind === 'delay' ? { kind: 'delay' }
                  : { angle: 0 };
      const prefix = kind === 'phase' ? 'φ'
                   : kind === 'delay' ? 'd' : 'g';
      const name = nextName(prefix, g.gates);
      const [w0, h0] = dims(proto);
      const [x, y] = at
        ? [Math.max(0, at[0] - w0 / 2), Math.max(0, at[1] - h0 / 2)]
        : freeSpot(Object.values(g.gates), gateSlot);
      copy.gates[name] = { x, y, ...proto };
    }
    commit(copy);
  }

  // palette items add on click, or drag onto the canvas to drop the
  // new object at the pointer; releasing anywhere else cancels
  let palDrag = null;
  for (const [btn, kind] of [[addGateBtn, 'gate'],
                             [addPartBtn, 'particle'],
                             [addPlateBtn, 'phase'],
                             [addDelayBtn, 'delay']])
    btn.addEventListener('mousedown', (ev) => {
      ev.preventDefault();
      palDrag = kind;
      document.body.style.cursor = 'copy';
    });
  const _palUp = (ev) => {
    if (!palDrag) return;
    const kind = palDrag;
    palDrag = null;
    document.body.style.cursor = '';
    const r = svg.getBoundingClientRect();
    if (ev.clientX >= r.left && ev.clientX <= r.right &&
        ev.clientY >= r.top && ev.clientY <= r.bottom)
      addObject(kind, [(ev.clientX - r.left - pan.x) / zoom,
                       (ev.clientY - r.top - pan.y) / zoom]);
    else if ((ev.composedPath ? ev.composedPath() : []).some(
        (n) => n.classList && n.classList.contains('qb-palette')))
      // released back over the palette: a plain click, default slot
      addObject(kind, null);
  };
  document.addEventListener('mouseup', _palUp);

  // stage… / diagram group… name the multi-selection (or the single
  // selected gate); an empty name clears the assignment
  const assign = (field, label) => {
    const g = graph();
    const targets = (multiKind === 'gate' && multi.size)
      ? [...multi].filter((k) => g.gates[k])
      : (selected?.kind === 'gate' ? [selected.key] : []);
    if (!targets.length) {
      window.alert('select gates first (shift-click selects several), '
                   + `then set their ${label}`);
      return;
    }
    const cur = g.gates[targets[0]][field] || '';
    const raw = window.prompt(
      `${label} for ${targets.join(', ')} (empty to clear)`, cur);
    if (raw === null) return;
    const name = raw.trim();
    const copy = JSON.parse(JSON.stringify(g));
    for (const k of targets) {
      if (name) copy.gates[k][field] = name;
      else delete copy.gates[k][field];
    }
    if (field === 'dgroup' && name) {
      // the hierarchy: run stages ARE the diagram groups until a
      // group that isn't exactly a run stage appears — that promotes
      // every named stage to an (editable) diagram group of its own
      const members = new Set(Object.keys(copy.gates)
        .filter((k) => copy.gates[k].dgroup === name));
      const stageSets = {};
      for (const [k, gd] of Object.entries(copy.gates))
        if (gd.stage) (stageSets[gd.stage] ??= new Set()).add(k);
      const isAStage = Object.values(stageSets).some(
        (s) => s.size === members.size &&
               [...s].every((k) => members.has(k)));
      if (!isAStage)
        for (const gd of Object.values(copy.gates))
          if (gd.stage && !gd.dgroup) gd.dgroup = gd.stage;
    }
    clearMulti();
    commit(copy);
  };
  stageBtn.onclick = () => assign('stage', 'stage name');
  dgroupBtn.onclick = () => assign('dgroup', 'diagram group');
  undoBtn.onclick = undo;
  redoBtn.onclick = redo;
  clearBtn.onclick = () => {
    const g = graph();
    if (!Object.keys(g.gates).length &&
        !Object.keys(g.particles).length)
      return;
    if (!window.confirm('Really wipe out everything on the canvas?'))
      return;
    selected = null;
    clearMulti();
    commit({ gates: {}, particles: {}, links: [] });
  };

  // wheel (and trackpad pinch, which arrives as ctrl+wheel) zooms
  // around the cursor, adjusting the pan so the point under the
  // pointer stays put — same feel as the results diagram
  svg.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    const r = svg.getBoundingClientRect();
    const sx = ev.clientX - r.left, sy = ev.clientY - r.top;
    const k = ev.ctrlKey ? 0.01 : 0.002;
    const z = Math.min(4, Math.max(0.3, zoom * Math.exp(-ev.deltaY * k)));
    pan.x = sx - (sx - pan.x) * (z / zoom);
    pan.y = sy - (sy - pan.y) * (z / zoom);
    zoom = z;
    redraw();
  }, { passive: false });

  const dropLabels = (copy, pred) => {
    for (const key of Object.keys(copy.wire_labels || {}))
      if (pred(key.startsWith('>') ? key.slice(1) : key))
        delete copy.wire_labels[key];
  };
  const dropGate = (copy, k) => {
    delete copy.gates[k];
    copy.links = copy.links.filter(
      (l) => l[0] !== k && l[1] !== k &&
             !l[0].startsWith(k + '.') && !l[1].startsWith(k + '.'));
    dropLabels(copy, (e) => e === k || e.startsWith(k + '.'));
  };
  const dropParticle = (copy, k) => {
    delete copy.particles[k];
    copy.links = copy.links.filter((l) => l[0] !== k);
    dropLabels(copy, (e) => e === k);
  };

  function deleteSelected() {
    if (multi.size) {
      const copy = JSON.parse(JSON.stringify(graph()));
      if (multiKind === 'link')
        copy.links = copy.links.filter((_, i) => !multi.has(i));
      else for (const k of multi)
        (multiKind === 'gate' ? dropGate : dropParticle)(copy, k);
      clearMulti();
      selected = null;
      commit(copy);
      return;
    }
    if (!selected) return;
    const copy = JSON.parse(JSON.stringify(graph()));
    if (selected.kind === 'link') copy.links.splice(selected.key, 1);
    else if (selected.kind === 'gate') dropGate(copy, selected.key);
    else dropParticle(copy, selected.key);
    selected = null;
    commit(copy);
  }
  delBtn.onclick = deleteSelected;
  root.tabIndex = 0;
  root.addEventListener('keydown', (ev) => {
    if (ev.key === 'Delete' || ev.key === 'Backspace') {
      ev.preventDefault();
      deleteSelected();
    } else if ((ev.metaKey || ev.ctrlKey) &&
               ev.key.toLowerCase() === 'z') {
      ev.preventDefault();
      if (ev.shiftKey) redo();
      else undo();
    }
  });

  // Double-clicks are detected by hand: every redraw() rebuilds the
  // SVG nodes, and the browser only counts clicks on the *same* node,
  // so the native dblclick event never fires here.
  let lastDown = { key: null, t: 0 };

  // A quick local radians evaluator for the live degrees preview in
  // the angle dialog: numbers, pi, rad(), and the usual functions.
  // Python (sympy) stays the authority once the value is accepted —
  // anything this cannot handle previews as '?'.
  function radEval(s) {
    let x = String(s).trim();
    if (!x || !/^[0-9a-z_+\-*/(). ]+$/i.test(x)) return null;
    // π as a placeholder: anything ASCII ('Math.PI', '#PI#') would be
    // re-matched by the later \bpi\b pass
    x = x.replace(/\b(sqrt|sin|cos|tan|acos|asin|atan|exp|log)\s*\(/gi,
                  '#$1#(')
         .replace(/\brad\s*\(/gi, '((π/180)*1)*(')
         .replace(/\bpi\b/gi, 'π');
    if (/[a-z_]/i.test(x.replace(/#(sqrt|sin|cos|tan|acos|asin|atan|exp|log)#/gi, '')))
      return null;
    x = x.replace(/π/g, 'Math.PI')
         .replace(/#(sqrt|sin|cos|tan|acos|asin|atan|exp|log)#/gi,
                  (m, f) => 'Math.' + f.toLowerCase());
    try {
      const v = Function('"use strict"; return (' + x + ')')();
      return Number.isFinite(v) ? v : null;
    } catch {
      return null;
    }
  }

  // Dialog input semantics: a bare number — optionally with a ° —
  // means DEGREES (what users almost always want); anything else is a
  // radians expression in the model files' syntax. degSpec turns the
  // input into the stored spec, previewDeg evaluates for the live
  // readout.
  const BARE_DEG = /^-?\d+(\.\d+)?\s*[°º˚]?$/;
  const degSpec = (s) => {
    // stored exactly as typed, so re-editing presents what was
    // entered; a bare number gets its implied degree mark
    if (!BARE_DEG.test(s)) return s;
    return /[°º˚]$/.test(s) ? s : s + '°';
  };
  const previewDeg = (s) => {
    if (BARE_DEG.test(s)) return parseFloat(s);
    const v = radEval(s);
    return v === null ? null : v * 180 / Math.PI;
  };

  function angleDialog(title, initial, onOk) {
    const box = document.createElement('div');
    box.className = 'qb-dialog';
    const head = document.createElement('div');
    head.className = 'qb-dlg-title';
    head.textContent = title;
    const input = document.createElement('input');
    input.value = `${initial}`;
    const row = document.createElement('div');
    row.className = 'qb-dlg-row';
    const preview = document.createElement('span');
    preview.className = 'qb-dlg-preview';
    const cancel = document.createElement('button');
    cancel.textContent = 'Cancel';
    const ok = document.createElement('button');
    ok.textContent = 'OK';
    ok.className = 'qb-dlg-ok';
    row.append(preview, cancel, ok);
    box.append(head, input, row);
    root.appendChild(box);
    const update = () => {
      const v = previewDeg(input.value.trim());
      preview.textContent = v === null ? '= ?°'
        : `= ${Math.round(v * 100) / 100}°`;
    };
    update();
    input.addEventListener('input', update);
    const close = () => box.remove();
    cancel.onclick = close;
    ok.onclick = () => {
      const s = input.value.trim();
      close();
      if (s) onOk(s);
    };
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') ok.onclick();
      else if (ev.key === 'Escape') close();
      ev.stopPropagation();
    });
    input.focus();
    input.select();
  }

  function renameGroup(kind, name) {
    const field = kind === 'stage' ? 'stage' : 'dgroup';
    const orderKey = kind === 'stage' ? 'stage_order' : 'dgroup_order';
    const what = kind === 'stage' ? 'stage' : 'diagram group';
    const raw = window.prompt(
      `new name for ${what} ${name} (renaming onto an existing ${what} `
      + 'merges them)', name);
    if (raw === null) return;
    const nn = raw.trim();
    if (!nn || nn === name) return;
    const copy = JSON.parse(JSON.stringify(graph()));
    for (const gd of Object.values(copy.gates))
      if (gd[field] === name) gd[field] = nn;
    if (Array.isArray(copy[orderKey]))
      copy[orderKey] = copy[orderKey].includes(nn)
        ? copy[orderKey].filter((x) => x !== name)
        : copy[orderKey].map((x) => (x === name ? nn : x));
    commit(copy);
  }

  function editWireLabel(key) {
    const cur = (graph().wire_labels || {})[key] || '';
    const raw = window.prompt(
      `wire label for ${key} (empty to remove)`, cur);
    if (raw === null) return;
    const copy = JSON.parse(JSON.stringify(graph()));
    copy.wire_labels = copy.wire_labels || {};
    const s = raw.trim();
    if (s) copy.wire_labels[key] = s;
    else delete copy.wire_labels[key];
    if (!Object.keys(copy.wire_labels).length)
      delete copy.wire_labels;
    commit(copy);
  }

  const NAME_OK = /^[^\s.]+$/;

  function checkName(copy, nn, current) {
    if (!NAME_OK.test(nn)) {
      window.alert(`cannot rename to "${nn}": no spaces or dots in names`);
      return false;
    }
    if (nn !== current && (copy.gates[nn] || copy.particles[nn])) {
      window.alert(`cannot rename to "${nn}": that name is taken`);
      return false;
    }
    return true;
  }

  function renameGate(copy, name) {
    const raw = window.prompt(`new name for ${name}`, name);
    if (raw === null) return;
    const nn = raw.trim();
    if (!nn || nn === name || !checkName(copy, nn, name)) return;
    const gates = {};
    for (const [k, v] of Object.entries(copy.gates))
      gates[k === name ? nn : k] = v;
    copy.gates = gates;
    copy.links = copy.links.map(([a, b]) => [
      a === name ? nn
        : a.startsWith(name + '.') ? nn + a.slice(name.length) : a,
      b === name ? nn
        : b.startsWith(name + '.') ? nn + b.slice(name.length) : b,
    ]);
    if (copy.wire_labels) {
      const renamed = {};
      for (const [key, lab] of Object.entries(copy.wire_labels)) {
        const gt = key.startsWith('>');
        const end = gt ? key.slice(1) : key;
        const nend = end === name ? nn
          : end.startsWith(name + '.') ? nn + end.slice(name.length)
          : end;
        renamed[(gt ? '>' : '') + nend] = lab;
      }
      copy.wire_labels = renamed;
    }
    selected = null;
    clearMulti();
    commit(copy);
  }

  function renameParticle(copy, name) {
    const p = copy.particles[name];
    const raw = window.prompt(
      'particle name, sign first (+name or -name)',
      (p.sign < 0 ? '-' : '+') + name);
    if (raw === null) return;
    let s = raw.trim();
    let sign = p.sign;
    if (s.startsWith('+')) { sign = 1; s = s.slice(1).trim(); }
    else if (s.startsWith('-') || s.startsWith('−')) {
      sign = -1;
      s = s.slice(1).trim();
    }
    if (!s || !checkName(copy, s, name)) return;
    if (s !== name) {
      const parts = {};
      for (const [k, v] of Object.entries(copy.particles))
        parts[k === name ? s : k] = v;
      copy.particles = parts;
      copy.links = copy.links.map(([a, b]) => [a === name ? s : a, b]);
      if (copy.wire_labels && copy.wire_labels[name] !== undefined) {
        copy.wire_labels[s] = copy.wire_labels[name];
        delete copy.wire_labels[name];
      }
      selected = null;
    }
    copy.particles[s].sign = sign;
    commit(copy);
  }

  function editNode(grp, target) {
    const copy = JSON.parse(JSON.stringify(graph()));
    const onName = target?.dataset?.name !== undefined;
    if (grp.dataset.gate) {
      if (onName || isDelay(copy.gates[grp.dataset.gate])) {
        renameGate(copy, grp.dataset.gate);
        return;
      }
      const gname = grp.dataset.gate;
      const field = isPlate(copy.gates[gname]) ? 'phase' : 'angle';
      angleDialog(
        `${field} for ${gname} — degrees (30, 22.5°), or a radians `
        + 'expression: pi/6, rad(30), acos(4/5)',
        copy.gates[gname][field] ?? 0,
        (s) => {
          const fresh = JSON.parse(JSON.stringify(graph()));
          const gd = fresh.gates[gname];
          if (!gd) return;
          // a bare number means degrees and stores as rad(n);
          // expressions store verbatim — the app validates and
          // reports anything unparseable in the problems list
          gd[field] = degSpec(s);
          commit(fresh);
        });
      return;
    } else {
      if (onName) {
        renameParticle(copy, grp.dataset.particle);
        return;
      }
      const p = copy.particles[grp.dataset.particle];
      p.sign = p.sign < 0 ? 1 : -1;
    }
    commit(copy);
  }

  svg.addEventListener('mousedown', (ev) => {
    const t = ev.target;
    const [x, y] = svgPoint(ev);
    if (t.dataset.outport) {
      const okey = `op:${t.dataset.outport}`;
      if (lastDown.key === okey && ev.timeStamp - lastDown.t < 400) {
        // double-click on an out-port labels its wire (or, when
        // unconnected, its null-output stub)
        lastDown = { key: null, t: 0 };
        wire = null;
        redraw();
        editWireLabel(t.dataset.outport);
        return;
      }
      lastDown = { key: okey, t: ev.timeStamp };
      wire = { src: t.dataset.outport, x, y };
      redraw();
      return;
    }
    if (t.dataset.inport && !ev.shiftKey) {
      const ikey = `ip:${t.dataset.inport}`;
      if (lastDown.key === ikey && ev.timeStamp - lastDown.t < 400) {
        // double-click on an in-port labels the incoming wire, or a
        // '>port' null-input stub when nothing enters there
        lastDown = { key: null, t: 0 };
        drag = null;
        const port = t.dataset.inport;
        const link = graph().links.find((l) => l[1] === port);
        editWireLabel(link ? link[0] : '>' + port);
        return;
      }
      lastDown = { key: ikey, t: ev.timeStamp };
      // fall through: a single press on an in-port drags the node
    }
    // a stage / diagram-group box label: double-click renames
    if (t.dataset && t.dataset.grouplabel !== undefined) {
      const gkey = `${t.dataset.groupkind}:${t.dataset.grouplabel}`;
      if (lastDown.key === gkey && ev.timeStamp - lastDown.t < 400) {
        lastDown = { key: null, t: 0 };
        renameGroup(t.dataset.groupkind, t.dataset.grouplabel);
      } else {
        lastDown = { key: gkey, t: ev.timeStamp };
      }
      return;
    }
    // shift/⌘/ctrl extend or toggle the selection
    const modSel = ev.shiftKey || ev.metaKey || ev.ctrlKey;
    const grp = t.closest('[data-gate],[data-particle]');
    if (!grp && t.dataset.link === undefined && modSel) {
      marquee = { x0: x, y0: y, x1: x, y1: y };
      redraw();
      return;
    }

    // what got clicked, as (kind, key)
    let kind = null, key = null;
    if (grp) {
      kind = grp.dataset.gate ? 'gate' : 'particle';
      key = grp.dataset.gate ?? grp.dataset.particle;
    } else if (t.dataset.link !== undefined) {
      kind = 'link';
      key = Number(t.dataset.link);
    }

    if (modSel && kind) {
      // same kind: toggle membership (seeding from a single selection);
      // a different kind: the just-clicked item wins
      if (multiKind !== null && multiKind !== kind) clearMulti();
      if (multi.size === 0 && selected && selected.kind === kind
          && selected.key !== key)
        multi.add(selected.key);
      multiKind = kind;
      if (multi.has(key)) multi.delete(key);
      else multi.add(key);
      if (selected && selected.kind !== kind) selected = null;
      if (multi.size === 0) multiKind = null;
      lastDown = { key: null, t: 0 };
      redraw();
      return;
    }

    if (grp) {
      const dkey = `${kind}:${key}`;
      if (lastDown.key === dkey && ev.timeStamp - lastDown.t < 400) {
        lastDown = { key: null, t: 0 };
        drag = null;
        editNode(grp, t);
        return;
      }
      lastDown = { key: dkey, t: ev.timeStamp };
      const g = graph();
      const before = JSON.stringify(g);
      const coll = kind === 'gate' ? g.gates : g.particles;
      const node = coll[key];
      selected = { kind, key };
      drag = { kind, key, dx: x - node.x, dy: y - node.y, before };
      if (inMultiOf(kind, key))
        // dragging a multi-selected component carries the others along
        drag.others = [...multi]
          .filter((k) => k !== key && coll[k])
          .map((k) => ({ k, ox: coll[k].x - node.x,
                         oy: coll[k].y - node.y }));
      else clearMulti();
      redraw();
      return;
    }
    if (kind === 'link') {
      const lkey = `link:${key}`;
      if (lastDown.key === lkey && ev.timeStamp - lastDown.t < 400) {
        lastDown = { key: null, t: 0 };
        editWireLabel(graph().links[key][0]);
        return;
      }
      lastDown = { key: lkey, t: ev.timeStamp };
      clearMulti();
      selected = { kind: 'link', key };
      redraw();
      return;
    }
    // empty canvas: drag to pan; a motionless click clears the
    // selection on mouseup (marquee keeps its modifier key)
    panning = { x: ev.clientX, y: ev.clientY,
                ox: pan.x, oy: pan.y, moved: false };
  });

  svg.addEventListener('mousemove', (ev) => {
    if (panning) {
      pan.x = panning.ox + ev.clientX - panning.x;
      pan.y = panning.oy + ev.clientY - panning.y;
      if (Math.abs(ev.clientX - panning.x) > 3 ||
          Math.abs(ev.clientY - panning.y) > 3)
        panning.moved = true;
      redraw();
      return;
    }
    const [x, y] = svgPoint(ev);
    if (marquee) {
      marquee.x1 = x;
      marquee.y1 = y;
      redraw();
      return;
    }
    if (wire) {
      wire.x = x;
      wire.y = y;
      redraw();
    } else if (drag) {
      const g = graph();   // mutate the model's copy locally, commit on drop
      const coll = drag.kind === 'gate' ? g.gates : g.particles;
      const node = coll[drag.key];
      node.x = Math.max(0, x - drag.dx);
      node.y = Math.max(0, y - drag.dy);
      // snap: a connected wire within a few pixels of horizontal pulls
      // the node the rest of the way (smallest nudge wins)
      const ownerOf = (e) => e.includes('.') ? e.split('.')[0] : e;
      let snap = null;
      for (const l of g.links) {
        const oS = ownerOf(l[0]), oD = ownerOf(l[1]);
        if ((oS === drag.key) === (oD === drag.key)) continue;
        const a = outXY(g, l[0]), b = inXY(g, l[1]);
        if (!a || !b) continue;
        const d = oS === drag.key ? b[1] - a[1] : a[1] - b[1];
        if (Math.abs(d) < 7 &&
            (snap === null || Math.abs(d) < Math.abs(snap)))
          snap = d;
      }
      if (snap !== null) node.y += snap;
      for (const o of drag.others || []) {
        coll[o.k].x = Math.max(0, node.x + o.ox);
        coll[o.k].y = Math.max(0, node.y + o.oy);
      }
      drag.moved = true;
      redraw();
    }
  });

  svg.addEventListener('mouseup', (ev) => {
    if (panning) {
      if (!panning.moved) {
        clearMulti();
        selected = null;
      }
      panning = null;
      redraw();
      return;
    }
    if (marquee) {
      const g = graph();
      const xlo = Math.min(marquee.x0, marquee.x1);
      const xhi = Math.max(marquee.x0, marquee.x1);
      const ylo = Math.min(marquee.y0, marquee.y1);
      const yhi = Math.max(marquee.y0, marquee.y1);
      const hitGates = Object.entries(g.gates).filter(([, gd]) => {
        const [w0, h0] = dims(gd);
        return gd.x < xhi && gd.x + w0 > xlo &&
               gd.y < yhi && gd.y + h0 > ylo;
      }).map(([n]) => n);
      const hitParts = Object.entries(g.particles).filter(([n, p]) =>
        p.x < xhi && p.x + partW(n) > xlo &&
        p.y < yhi && p.y + 2 * PR > ylo).map(([n]) => n);
      // one kind at a time: gates win a mixed sweep
      const kind2 = hitGates.length ? 'gate'
                  : hitParts.length ? 'particle' : null;
      if (kind2) {
        if (multiKind !== kind2) clearMulti();
        multiKind = kind2;
        for (const n of (kind2 === 'gate' ? hitGates : hitParts))
          multi.add(n);
      }
      marquee = null;
      redraw();
      return;
    }
    if (wire) {
      const t = ev.target;
      const g = graph();
      if (t.dataset.inport && !usedDst(g).has(t.dataset.inport) &&
          !usedSrc(g).has(wire.src)) {
        const copy = JSON.parse(JSON.stringify(g));
        copy.links.push([wire.src, t.dataset.inport]);
        wire = null;
        commit(copy);
      } else {
        wire = null;
        redraw();
      }
      return;
    }
    if (drag) {
      if (drag.moved) commit(graph(), drag.before);
      drag = null;
    }
  });
  svg.addEventListener('mouseleave', () => {
    if (wire || drag || marquee || panning) {
      wire = null;
      drag = null;
      marquee = null;
      panning = null;
      redraw();
    }
  });

  model.on('change:graph', redraw);
  model.on('change:angle_labels', redraw);
  redraw();
  return () => document.removeEventListener('mouseup', _palUp);
}

export default { render };
"""


_DIAGRAM_CSS = """
.qd-root { background: #fff; border: 1px solid #ddd;
           border-radius: 8px; height: 480px;
           resize: vertical; overflow: hidden; }
.qd-root svg { display: block; width: 100%; height: 100%;
               cursor: grab; user-select: none;
               -webkit-user-select: none; }
.qd-root svg.panning { cursor: grabbing; }
"""

_DIAGRAM_ESM = r"""
function h(tag, attrs = {}, ...children) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const c of children)
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  return el;
}

function render({ model, el }) {
  el.innerHTML = '';
  const root = document.createElement('div');
  root.className = 'qd-root';
  el.appendChild(root);

  function draw() {
    const g = model.get('geometry') || {};
    if (root._cleanup) root._cleanup();
    root.innerHTML = '';
    if (!g.boxes) return;
    const W = g.x1 - g.x0, H = g.y1 - g.y0;
    const fy = (y) => g.y1 - y;          // layout y grows up; svg down
    const S = g.scale;                   // px per layout unit at natural size
    const svg = h('svg', { viewBox: `${g.x0} 0 ${W} ${H}` });
    root.appendChild(svg);

    for (const b of g.boxes.concat(
        (g.stadiums || []).map((s) => ({ ...s, fill: g.value_fill,
                                         stroke: g.value_stroke })))) {
      const hgt = b.y2 - b.y;
      const rect = h('rect', {
        x: b.x, y: fy(b.y2), width: b.x2 - b.x, height: hgt,
        rx: Math.min(b.corner * 1.5 / S, hgt / 2),
        fill: b.fill, stroke: b.stroke, 'stroke-width': 1.2 / S,
      });
      if (b.amp) {
        const tip = h('title');
        tip.textContent = `amplitude: ${b.amp}`
          + (b.pr ? `\nPr: ${b.pr}` : '');
        rect.appendChild(tip);
      }
      svg.appendChild(rect);
    }
    for (const seg of g.dots || [])
      svg.appendChild(h('polyline', {
        points: seg.map((p) => `${p.x},${fy(p.y)}`).join(' '),
        fill: 'none', stroke: '#000000', 'stroke-width': 1 / S,
        'stroke-dasharray': `${3 / S} ${3 / S}`,
      }));
    for (const seg of g.wires || [])
      svg.appendChild(h('polyline', {
        points: seg.map((p) => `${p.x},${fy(p.y)}`).join(' '),
        fill: 'none', stroke: g.wire_color, 'stroke-width': 1.3 / S,
      }));
    for (const a of g.arrows || []) {
      const s = 5.4 / S;   // matches the chart's size-45 triangles
      svg.appendChild(h('path', {
        d: `M 0 ${-s} L ${0.62 * s} ${0.55 * s} L ${-0.62 * s} ${0.55 * s} Z`,
        fill: g.wire_color,
        transform: `translate(${a.x} ${fy(a.y)}) rotate(${a.angle})`,
      }));
    }
    for (const tx of g.texts || [])
      tx.lines.forEach((line, k) => {
        const el = h('text', {
          x: tx.x, y: fy(tx.y - k * g.line_h),
          'text-anchor': 'middle', 'dominant-baseline': 'central',
          'font-size': tx.size / S, 'font-weight': tx.weight,
          fill: tx.color,
          'font-family': 'sans-serif', 'pointer-events': 'none',
        });
        const runs = (tx.runs || [])[k];
        if (runs && runs.some((r) => r[1])) {
          // real sub/superscripts (unicode lacks most letters)
          for (const [frag, lvl] of runs) {
            if (!lvl) {
              el.appendChild(document.createTextNode(frag));
            } else {
              el.appendChild(h('tspan', {
                'font-size': '64%',
                'baseline-shift': lvl < 0 ? '-25%' : '38%',
              }, frag));
            }
          }
        } else {
          el.appendChild(document.createTextNode(line));
        }
        svg.appendChild(el);
      });

    // One-size-fits-all frame: every diagram opens in the same box at
    // the same natural scale (ppu screen px per layout unit — set so
    // in-diagram text sizes sit just under the surrounding prose),
    // left-aligned, with pan/zoom to reach whatever the box cuts off.
    // Stretching the box (CSS resize) shows more or less of the plane
    // without rescaling the contents. No zoom-out limit.
    //
    // User actions override defaults: the window-level stash carries
    // the stretched box height and the zoom across widget rebuilds
    // (model load, show-values toggle, a run). The exact pan position
    // comes back too when the geometry is the same one it was saved
    // for; a different geometry re-places at the kept zoom.
    // Double-click resets zoom and pan (never the box height).
    const st = window.__qdState = window.__qdState || {};
    const sig = `${g.x0},${g.x1},${g.y1},${S},${g.boxes.length}`;
    // an explicit frame size in the geometry overrides the default CSS
    // box AND the stashed user height (grid layouts size their own)
    if (g.frame_w) root.style.width = `${g.frame_w}px`;
    if (g.frame_h) root.style.height = `${g.frame_h}px`;
    else if (st.boxH) root.style.height = `${st.boxH}px`;
    const ZOOM = 1.2;                 // natural-scale boost
    const ppu0 = S * ZOOM;
    let ppu = st.ppu || ppu0, vx = 0, vy = 0;
    const apply = () => {
      const r = root.getBoundingClientRect();
      if (!r.width || !r.height) return;
      svg.setAttribute('viewBox',
        `${vx} ${vy} ${r.width / ppu} ${r.height / ppu}`);
    };
    const save = () => {
      st.ppu = ppu;
      st.sig = sig;
      st.vx = vx;
      st.vy = vy;
    };
    const place = () => {
      const r = root.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const vh = r.height / ppu;
      vx = g.x0 - 28 / ppu;               // left-aligned, small margin
      vy = H <= vh ? -(vh - H) / 2 : 0;   // center, or show the top
      apply();
    };
    if (st.sig === sig && st.vx !== undefined) {
      vx = st.vx;
      vy = st.vy;
      apply();
    } else {
      place();
      save();
    }
    svg.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      const r = svg.getBoundingClientRect();
      const mx = vx + (ev.clientX - r.left) / ppu;
      const my = vy + (ev.clientY - r.top) / ppu;
      const f = Math.exp(-ev.deltaY * (ev.ctrlKey ? 0.01 : 0.002));
      const k = Math.min(ppu0 * 40, Math.max(ppu0 / 40, ppu * f)) / ppu;
      ppu *= k;
      vx = mx - (mx - vx) / k;
      vy = my - (my - vy) / k;
      save();
      apply();
    }, { passive: false });
    let pan = null;
    svg.addEventListener('mousedown', (ev) => {
      pan = { x: ev.clientX, y: ev.clientY, vx, vy };
      svg.classList.add('panning');
    });
    const _move = (ev) => {
      if (!pan) return;
      vx = pan.vx - (ev.clientX - pan.x) / ppu;
      vy = pan.vy - (ev.clientY - pan.y) / ppu;
      save();
      apply();
    };
    const _up = () => {
      pan = null;
      svg.classList.remove('panning');
    };
    window.addEventListener('mousemove', _move);
    window.addEventListener('mouseup', _up);
    // stretching the frame extends the view; the scale stays put
    const ro = new ResizeObserver(() => {
      const r = root.getBoundingClientRect();
      if (r.height) st.boxH = Math.round(r.height);
      apply();
    });
    ro.observe(root);
    root._cleanup = () => {
      window.removeEventListener('mousemove', _move);
      window.removeEventListener('mouseup', _up);
      ro.disconnect();
    };
    svg.addEventListener('dblclick', () => {
      ppu = ppu0;
      place();
      save();
    });
  }

  model.on('change:geometry', draw);
  draw();
  return () => root._cleanup && root._cleanup();
}

export default { render };
"""


class DiagramWidget(anywidget.AnyWidget):
    """The results diagram drawn natively from diagram_geometry's
    output — the same layout, router, and geometry as the TikZ
    renderer and the SVG file exporter. Wheel
    zooms, drag pans, double-click resets; no vl-convert, WASM-safe."""
    _esm = _DIAGRAM_ESM
    _css = _DIAGRAM_CSS
    geometry = traitlets.Dict({}).tag(sync=True)


_WSPLIT_CSS = """
.qw-root { background: #fff; border: 1px solid #ddd;
           border-radius: 8px; resize: both; overflow: hidden; }
.qw-root svg { display: block; user-select: none;
               -webkit-user-select: none; }
"""

_WSPLIT_ESM = r"""
// the tableau10 categorical palette
const CAT10 = ['#4c78a8', '#f58518', '#e45756', '#72b7b2',
               '#54a24b', '#eeca3b', '#b279a2', '#ff9da6'];

function h(tag, attrs = {}, ...children) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const c of children)
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  return el;
}

function niceTicks(d0, d1, count) {
  const span = d1 - d0;
  const raw = span / Math.max(4, count || 4);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 5, 10].map((m) => m * mag)
    .find((s) => raw <= s * 1.2) || 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(d0 / step - 1e-9) * step; v <= d1 + 1e-9;
       v += step)
    ticks.push(Math.abs(v) < 1e-9 ? 0 : +v.toFixed(10));
  return ticks;
}

function render({ model, el }) {
  el.innerHTML = '';
  const root = document.createElement('div');
  root.className = 'qw-root';
  el.appendChild(root);

  // The zoomable data domain (wheel zoom + drag pan).
  // Both the domain and the frame size live in a window-level stash:
  // the widget is rebuilt on every parameter or selection change, and
  // the user's zoom and resize must ride through — only an explicit
  // double-click resets the zoom to the default.
  const st = window.__qwState = window.__qwState || {};
  let dom = st.dom ? { ...st.dom } : null;
  const HOME = [-1.2, 1.2];   // the [-1.1, 1.1] data range, niced
  const M = { l: 52, r: 8, t: 34, b: 46 };
  const LEG = 100;
  // the plot is sized by its frame: grab the frame's corner to
  // stretch it, and the square plot grows to fill (no size slider)
  let curSize = st.size || null;
  let sized = false;

  function draw() {
    const d = model.get('data') || {};
    const selected = model.get('selected') || [];
    root.innerHTML = '';
    if (!d.vectors) return;
    if (!dom) dom = { x0: HOME[0], x1: HOME[1], y0: HOME[0], y1: HOME[1] };
    const size = curSize || d.size || 420;
    const W = M.l + size + M.r + LEG, H = M.t + size + M.b;
    if (!sized) {
      sized = true;
      curSize = size;
      root.style.width = `${W}px`;
      root.style.height = `${H}px`;
    }
    const svg = h('svg', { viewBox: `0 0 ${W} ${H}`,
                           width: W, height: H });
    root.appendChild(svg);
    const sx = (v) => M.l + (v - dom.x0) / (dom.x1 - dom.x0) * size;
    const sy = (v) => M.t + (dom.y1 - v) / (dom.y1 - dom.y0) * size;
    const color = (name) => CAT10[(d.order || []).indexOf(name) % 10];
    const dim = (name) =>
      selected.length && !selected.includes(name);

    // plot frame + clip
    svg.appendChild(h('clipPath', { id: 'qwclip' },
      h('rect', { x: M.l, y: M.t, width: size, height: size })));

    // gridlines and axes (light grid, outside ticks)
    const nTicks = Math.max(4, Math.round(size / 45));
    const xt = niceTicks(dom.x0, dom.x1, nTicks);
    const yt = niceTicks(dom.y0, dom.y1, nTicks);
    // tick labels carry the step's precision ('1.0', not '1')
    const dec = (ts) => Math.max(0, ...ts.map((v) =>
      (String(v).split('.')[1] || '').length));
    const xd = dec(xt), yd = dec(yt);
    const fmtT = (v, dd) =>
      (v < 0 ? '\u2212' : '') + Math.abs(v).toFixed(dd);
    for (const v of xt) {
      svg.appendChild(h('line', { x1: sx(v), y1: M.t, x2: sx(v),
        y2: M.t + size, stroke: '#ddd', 'stroke-width': 1 }));
      svg.appendChild(h('line', { x1: sx(v), y1: M.t + size,
        x2: sx(v), y2: M.t + size + 5, stroke: '#888' }));
      svg.appendChild(h('text', { x: sx(v), y: M.t + size + 16,
        'text-anchor': 'middle', 'font-size': 10, fill: '#000',
        'font-family': 'sans-serif' }, fmtT(v, xd)));
    }
    for (const v of yt) {
      svg.appendChild(h('line', { x1: M.l, y1: sy(v), x2: M.l + size,
        y2: sy(v), stroke: '#ddd', 'stroke-width': 1 }));
      svg.appendChild(h('line', { x1: M.l - 5, y1: sy(v), x2: M.l,
        y2: sy(v), stroke: '#888' }));
      svg.appendChild(h('text', { x: M.l - 8, y: sy(v) + 3,
        'text-anchor': 'end', 'font-size': 10, fill: '#000',
        'font-family': 'sans-serif' }, fmtT(v, yd)));
    }
    svg.appendChild(h('rect', { x: M.l, y: M.t, width: size,
      height: size, fill: 'none', stroke: '#888', 'stroke-width': 1 }));
    svg.appendChild(h('text', { x: M.l + size / 2, y: H - 10,
      'text-anchor': 'middle', 'font-size': 11, 'font-weight': 'bold',
      fill: '#000', 'font-family': 'sans-serif' }, 'Parallel (Re)'));
    svg.appendChild(h('text', {
      x: 14, y: M.t + size / 2, 'text-anchor': 'middle',
      'font-size': 11, 'font-weight': 'bold', fill: '#000',
      'font-family': 'sans-serif',
      transform: `rotate(-90 14 ${M.t + size / 2})`,
    }, 'Perpendicular (Im)'));
    if (d.title)
      svg.appendChild(h('text', { x: M.l + size / 2, y: 18,
        'text-anchor': 'middle', 'font-size': 13,
        'font-weight': 'bold', fill: '#000',
        'font-family': 'sans-serif' }, d.title));

    // the vectors, clipped to the plot
    const plot = h('g', { 'clip-path': 'url(#qwclip)' });
    svg.appendChild(plot);
    for (const name of d.order || []) {
      const v = d.vectors[name];
      if (!v) continue;
      const [re, im] = v;
      plot.appendChild(h('line', {
        x1: sx(0), y1: sy(0), x2: sx(re), y2: sy(im),
        stroke: color(name),
        'stroke-width': selected.includes(name) ? 5.5 : 4,
        opacity: dim(name) ? 0.35 : 1,
      }));
      plot.appendChild(h('line', {
        x1: sx(0), y1: sy(0), x2: sx(re), y2: sy(im),
        stroke: 'transparent', 'stroke-width': 12,
        'data-item': name, style: 'cursor: pointer',
      }));
      plot.appendChild(h('text', {
        x: sx(re) + 7, y: sy(im), 'text-anchor': 'start',
        'dominant-baseline': 'central', 'font-size': 11,
        fill: color(name), opacity: dim(name) ? 0.35 : 1,
        'font-family': 'sans-serif', 'data-item': name,
        style: 'cursor: pointer',
      }, name));
    }

    // legend
    const lx = M.l + size + 24;
    svg.appendChild(h('text', { x: lx, y: M.t + 4, 'font-size': 11,
      'font-weight': 'bold', fill: '#000',
      'font-family': 'sans-serif' }, 'component'));
    (d.order || []).forEach((name, i) => {
      const y = M.t + 18 + i * 16;
      const g = h('g', { 'data-item': name,
                         style: 'cursor: pointer' });
      g.appendChild(h('circle', { cx: lx + 5, cy: y - 2, r: 5,
        fill: color(name), opacity: dim(name) ? 0.35 : 1 }));
      g.appendChild(h('text', { x: lx + 15, y, 'font-size': 10.5,
        fill: '#000', 'font-family': 'sans-serif',
        'dominant-baseline': 'central',
        opacity: dim(name) ? 0.35 : 1 }, name));
      svg.appendChild(g);
    });

    // Finder-style selection: click picks, modifier-click toggles,
    // empty plot space clears
    svg.addEventListener('mousedown', (ev) => {
      const item = ev.target.closest && ev.target.closest('[data-item]');
      const mods = ev.shiftKey || ev.metaKey || ev.ctrlKey;
      let sel = [...(model.get('selected') || [])];
      if (item) {
        const name = item.getAttribute('data-item');
        if (mods)
          sel = sel.includes(name) ? sel.filter((s) => s !== name)
                                   : [...sel, name];
        else sel = [name];
      } else if (!mods) {
        const r = svg.getBoundingClientRect();
        const px = (ev.clientX - r.left) / r.width * W;
        const py = (ev.clientY - r.top) / r.height * H;
        const inPlot = px >= M.l && px <= M.l + size &&
                       py >= M.t && py <= M.t + size;
        if (!inPlot) return;
        pan = { x: ev.clientX, y: ev.clientY, moved: false,
                d: { ...dom } };
        return;
      } else return;
      model.set('selected', sel);
      model.save_changes();
      draw();
    });

    // wheel zooms the domain around the cursor; drag pans;
    // double-click resets
    svg.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      const r = svg.getBoundingClientRect();
      if (!r.width || !r.height) return;   // hidden (collapsed section)
      const px = (ev.clientX - r.left) / r.width * W;
      const py = (ev.clientY - r.top) / r.height * H;
      const cx = dom.x0 + (px - M.l) / size * (dom.x1 - dom.x0);
      const cy = dom.y1 - (py - M.t) / size * (dom.y1 - dom.y0);
      const f = Math.exp(ev.deltaY * (ev.ctrlKey ? 0.01 : 0.002));
      const w = Math.min(40, Math.max(0.05, (dom.x1 - dom.x0) * f));
      const k = w / (dom.x1 - dom.x0);
      dom = { x0: cx - (cx - dom.x0) * k, x1: cx + (dom.x1 - cx) * k,
              y0: cy - (cy - dom.y0) * k, y1: cy + (dom.y1 - cy) * k };
      st.dom = { ...dom };
      draw();
    }, { passive: false });
    svg.addEventListener('dblclick', () => {
      dom = null;
      delete st.dom;
      draw();
    });
  }

  let pan = null;
  const _wsMove = (ev) => {
    if (!pan) return;
    pan.moved = true;
    const size = curSize || 420;
    const svg = root.querySelector('svg');
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    if (!r.width) return;                  // hidden (collapsed section)
    const scale = (pan.d.x1 - pan.d.x0) / size *
      (svg.viewBox.baseVal.width / r.width);
    dom = {
      x0: pan.d.x0 - (ev.clientX - pan.x) * scale,
      x1: pan.d.x1 - (ev.clientX - pan.x) * scale,
      y0: pan.d.y0 + (ev.clientY - pan.y) * scale,
      y1: pan.d.y1 + (ev.clientY - pan.y) * scale,
    };
    st.dom = { ...dom };
    draw();
  };
  const _wsUp = () => {
    if (pan && !pan.moved) {
      // a motionless press on empty plot space clears the selection
      model.set('selected', []);
      model.save_changes();
      draw();
    }
    pan = null;
  };
  window.addEventListener('mousemove', _wsMove);
  window.addEventListener('mouseup', _wsUp);

  // frame resize (the CSS resize grip) → refit the square plot
  const ro = new ResizeObserver(() => {
    if (curSize == null) return;
    const r = root.getBoundingClientRect();
    const s = Math.round(Math.min(r.width - (M.l + M.r + LEG),
                                  r.height - (M.t + M.b)));
    if (s >= 120 && Math.abs(s - curSize) > 1) {
      curSize = s;
      st.size = s;
      draw();
    }
  });
  ro.observe(root);

  model.on('change:data', () => draw());
  model.on('change:selected', () => draw());
  draw();
  return () => {
    window.removeEventListener('mousemove', _wsMove);
    window.removeEventListener('mouseup', _wsUp);
    ro.disconnect();
  };
}

export default { render };
"""


class WeightSplitWidget(anywidget.AnyWidget):
    """The weight-split explorer's vector view: axes, grid,
    category colors, legend, Finder-style selection, and
    wheel-zoom/pan/double-click-reset, with the selection synced
    through the `selected` trait."""
    _esm = _WSPLIT_ESM
    _css = _WSPLIT_CSS
    data = traitlets.Dict({}).tag(sync=True)
    selected = traitlets.List([]).tag(sync=True)


_NETGRAPH_CSS = """
.qn-root { background: #fff; border: 1px solid #ddd;
           border-radius: 8px; resize: both; overflow: hidden; }
.qn-root svg { display: block; width: 100%; height: 100%;
               cursor: default; user-select: none;
               -webkit-user-select: none; }
"""

_NETGRAPH_ESM = r"""
function h(tag, attrs = {}, ...children) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const c of children)
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  return el;
}

function render({ model, el }) {
  el.innerHTML = '';
  const root = document.createElement('div');
  root.className = 'qn-root';
  el.appendChild(root);
  let selected = null;   // clicked node id; its edges highlight

  function draw() {
    const m = model.get('model') || {};
    root.innerHTML = '';
    if (!m.cells) return;
    const nCols = m.n_columns, layerMax = m.layer_max;
    const bandH = m.band_h;
    // the same geometry the file exporter draws
    // (svg_export.network_graph_svg)
    const xLo = -0.75, xHi = nCols - 1 + 0.6;
    const ySpan = (layerMax + 1) / 2.0;
    const yLo = -ySpan - 0.75, yHi = ySpan + 0.4;
    const W = Math.min(170 * nCols, 900);
    const H = Math.max(Math.min(Math.round(58 * (layerMax + 2)), 900), 220);
    const pxX = W / (xHi - xLo), pxY = H / (yHi - yLo);
    const cellW = bandH * pxY / pxX;
    // title above the plot
    const titleLines = [];
    {
      const words = String(m.title || '').split(/\s+/);
      const maxCh = Math.max(20, Math.round(W / 9));
      let cur = '';
      for (const w of words) {
        if (cur && (cur + ' ' + w).length > maxCh) {
          titleLines.push(cur);
          cur = w;
        } else cur = cur ? cur + ' ' + w : w;
      }
      if (cur) titleLines.push(cur);
    }
    const T = 10 + 18 * titleLines.length;
    const px = (x) => (x - xLo) * pxX;
    const py = (y) => T + (yHi - y) * pxY;
    const svg = h('svg', { viewBox: `0 0 ${W} ${T + H}` });
    root.style.width = `${W + 2}px`;
    root.style.height = `${T + H + 2}px`;
    root.appendChild(svg);
    titleLines.forEach((ln, i) => svg.appendChild(h('text', {
      x: W / 2, y: 16 + 18 * i, 'text-anchor': 'middle',
      'font-size': 13, 'font-weight': 'bold', fill: '#000',
      'font-family': 'sans-serif' }, ln)));

    // arrows: shafts trimmed to the cell edges, real polygon heads
    const HEAD_LEN = 6.0, HEAD_HALF = 2.4;
    const arrowEls = [];
    for (const a of m.arrows || []) {
      const x1 = px(a.x + cellW / 2 + 0.02), y1 = py(a.y);
      const x2 = px(a.x2 - cellW / 2 - 0.02), y2 = py(a.y2);
      const dx = x2 - x1, dy = y2 - y1;
      const n = Math.hypot(dx, dy) || 1;
      const ux = dx / n, uy = dy / n;
      const bx = x2 - HEAD_LEN * ux, by = y2 - HEAD_LEN * uy;
      const g = h('g', { 'data-src': a.src, 'data-dst': a.dst });
      g.appendChild(h('line', { x1, y1, x2: bx, y2: by,
        stroke: '#000', 'stroke-width': 1 }));
      g.appendChild(h('path', { fill: '#000',
        d: `M ${x2} ${y2} L ${bx - HEAD_HALF * -uy} ${by - HEAD_HALF * ux}` +
           ` L ${bx + HEAD_HALF * -uy} ${by + HEAD_HALF * ux} Z` }));
      svg.appendChild(g);
      arrowEls.push(g);
    }

    // cells: border underlay + inset fill
    const nodeBounds = {};
    const cellEls = [];
    for (const c of m.cells || []) {
      const x0 = px(c.x - cellW / 2), x1 = px(c.x + cellW / 2);
      const y0 = py(c.y1), y1 = py(c.y0);   // y flips
      const g = h('g', { 'data-node': c.node, style: 'cursor: pointer' });
      g.appendChild(h('rect', { x: x0, y: y0, width: x1 - x0,
        height: y1 - y0, fill: c.stroke }));
      g.appendChild(h('rect', {
        x: x0 + c.sw, y: y0 + c.sw,
        width: Math.max(0, x1 - x0 - 2 * c.sw),
        height: Math.max(0, y1 - y0 - 2 * c.sw), fill: c.fill }));
      const tip = h('title');
      tip.textContent = `configuration-space point: ${c.cs_point}\n` +
        `particle: ${c.particle}\nvalue: ${c.value}\nPr(point): ${c.pr}`;
      g.appendChild(tip);
      svg.appendChild(g);
      cellEls.push(g);
      const b = nodeBounds[c.node] ||
        (nodeBounds[c.node] = { x0, y0, x1, y1 });
      b.x0 = Math.min(b.x0, x0); b.y0 = Math.min(b.y0, y0);
      b.x1 = Math.max(b.x1, x1); b.y1 = Math.max(b.y1, y1);
    }

    // fine diagonal stripes for untouched cells
    const N_STRIPES = 5;
    for (const [xc, y0d, y1d, sw] of m.stripes || []) {
      const x0 = px(xc - cellW / 2) + sw, x1 = px(xc + cellW / 2) - sw;
      const yTop = py(y1d) + sw, yBot = py(y0d) - sw;
      for (let k = 1; k < 2 * N_STRIPES; k++) {
        const c = -1 + k / N_STRIPES;
        const u0 = Math.max(0, -c), u1 = Math.min(1, 1 - c);
        if (u0 >= u1) continue;
        svg.appendChild(h('line', {
          x1: x0 + u0 * (x1 - x0), y1: yBot - (u0 + c) * (yBot - yTop),
          x2: x0 + u1 * (x1 - x0), y2: yBot - (u1 + c) * (yBot - yTop),
          stroke: '#000', 'stroke-width': 0.4,
          'pointer-events': 'none' }));
      }
    }

    for (const l of m.labels || [])
      svg.appendChild(h('text', {
        x: px(l.x - cellW / 2 - 0.04), y: py(l.y),
        'text-anchor': 'end', 'dominant-baseline': 'central',
        'font-size': 11, fill: '#404040',
        'font-family': 'sans-serif' }, l.text));
    (m.col_labels || []).forEach((label, i) =>
      svg.appendChild(h('text', { x: px(i), y: py(yLo + 0.35),
        'text-anchor': 'middle', 'font-size': 13, fill: '#000',
        'font-family': 'sans-serif' }, label)));

    // Click a configuration-space point: its whole ancestry and
    // descendancy — every arrow on a path into or out of it — stays
    // bold while the rest fade. Shift-click limits the highlight to
    // the immediate predecessors and successors. Click again (or
    // empty space) to clear.
    const preds = {}, succs = {};
    for (const a of m.arrows || []) {
      (succs[a.src] = succs[a.src] || []).push(a.dst);
      (preds[a.dst] = preds[a.dst] || []).push(a.src);
    }
    const reach = (start, step) => {
      const seen = new Set([start]);
      const queue = [start];
      while (queue.length) {
        for (const nb of step[queue.shift()] || [])
          if (!seen.has(nb)) { seen.add(nb); queue.push(nb); }
      }
      return seen;
    };
    let outline = null;
    let singleLevel = false;
    const applySel = () => {
      if (outline) { outline.remove(); outline = null; }
      let back = null, fwd = null;
      if (selected !== null) {
        back = singleLevel ? new Set([selected])
                           : reach(selected, preds);
        fwd = singleLevel ? new Set([selected])
                          : reach(selected, succs);
      }
      for (const g of arrowEls) {
        const on = selected !== null &&
          (back.has(g.getAttribute('data-dst')) ||
           fwd.has(g.getAttribute('data-src')));
        g.setAttribute('opacity', selected === null ? 1 : (on ? 1 : 0.12));
        g.querySelector('line').setAttribute('stroke-width', on ? 2.2 : 1);
      }
      if (selected !== null && nodeBounds[selected]) {
        const b = nodeBounds[selected];
        outline = h('rect', { x: b.x0 - 1.5, y: b.y0 - 1.5,
          width: b.x1 - b.x0 + 3, height: b.y1 - b.y0 + 3,
          fill: 'none', stroke: '#5c64d1', 'stroke-width': 1.5,
          'pointer-events': 'none' });
        svg.appendChild(outline);
      }
    };
    svg.addEventListener('mousedown', (ev) => {
      const cell = ev.target.closest && ev.target.closest('[data-node]');
      const node = cell ? cell.getAttribute('data-node') : null;
      const mode = !!ev.shiftKey;
      // re-click with the other mode switches depth; same mode clears
      selected = (node === null ||
                  (node === selected && mode === singleLevel))
        ? null : node;
      singleLevel = mode;
      applySel();
    });
  }

  model.on('change:model', draw);
  draw();
}

export default { render };
"""


class NetworkGraphWidget(anywidget.AnyWidget):
    """The weight-evolution graph drawn natively from
    NetworkGraph.build_model() — the same geometry and palette as
    the file exporter, plus interaction: click a
    configuration-space point to highlight its predecessor and
    successor arrows."""
    _esm = _NETGRAPH_ESM
    _css = _NETGRAPH_CSS
    model = traitlets.Dict({}).tag(sync=True)


_PLOT_CSS = """
.qp-root { background: #fff; }
.qp-root svg { display: block; user-select: none;
               -webkit-user-select: none; }
"""

_PLOT_HELPERS = r"""
function h(tag, attrs = {}, ...children) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const c of children)
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  return el;
}

function niceTicks(d0, d1, count) {
  const span = d1 - d0;
  const raw = span / Math.max(2, count || 4);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 5, 10].map((m) => m * mag)
    .find((s) => raw <= s * 1.2) || 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(d0 / step - 1e-9) * step; v <= d1 + 1e-9;
       v += step)
    ticks.push(Math.abs(v) < 1e-9 ? 0 : +v.toFixed(10));
  return ticks;
}

function axes(svg, M, pw, ph, oy, xd, yd, xlabel, ylabel) {
  const sx = (v) => M.l + (v - xd[0]) / (xd[1] - xd[0]) * pw;
  const sy = (v) => oy + ph - (v - yd[0]) / (yd[1] - yd[0]) * ph;
  const fmt = (ts) => Math.max(0, ...ts.map((v) =>
    (String(v).split('.')[1] || '').length));
  const xt = niceTicks(xd[0], xd[1], Math.round(pw / 60));
  const yt = niceTicks(yd[0], yd[1], Math.round(ph / 40));
  const dx = fmt(xt), dy = fmt(yt);
  const label = (v, d) =>
    (v < 0 ? '\u2212' : '') + Math.abs(v).toFixed(d);
  for (const v of xt) {
    svg.appendChild(h('line', { x1: sx(v), y1: oy, x2: sx(v),
      y2: oy + ph, stroke: '#ddd', 'stroke-width': 1 }));
    svg.appendChild(h('line', { x1: sx(v), y1: oy + ph, x2: sx(v),
      y2: oy + ph + 5, stroke: '#888' }));
    svg.appendChild(h('text', { x: sx(v), y: oy + ph + 16,
      'text-anchor': 'middle', 'font-size': 10, fill: '#000',
      'font-family': 'sans-serif' }, label(v, dx)));
  }
  for (const v of yt) {
    svg.appendChild(h('line', { x1: M.l, y1: sy(v), x2: M.l + pw,
      y2: sy(v), stroke: '#ddd', 'stroke-width': 1 }));
    svg.appendChild(h('line', { x1: M.l - 5, y1: sy(v), x2: M.l,
      y2: sy(v), stroke: '#888' }));
    svg.appendChild(h('text', { x: M.l - 8, y: sy(v) + 3,
      'text-anchor': 'end', 'font-size': 10, fill: '#000',
      'font-family': 'sans-serif' }, label(v, dy)));
  }
  svg.appendChild(h('rect', { x: M.l, y: oy, width: pw, height: ph,
    fill: 'none', stroke: '#888', 'stroke-width': 1 }));
  if (xlabel)
    svg.appendChild(h('text', { x: M.l + pw / 2, y: oy + ph + 32,
      'text-anchor': 'middle', 'font-size': 11, 'font-weight': 'bold',
      fill: '#000', 'font-family': 'sans-serif' }, xlabel));
  if (ylabel)
    svg.appendChild(h('text', { x: 12, y: oy + ph / 2,
      'text-anchor': 'middle', 'font-size': 11, 'font-weight': 'bold',
      fill: '#000', 'font-family': 'sans-serif',
      transform: `rotate(-90 12 ${oy + ph / 2})` }, ylabel));
  return { sx, sy };
}

function polyline(xs, ys, sx, sy, color, dash) {
  const attrs = { fill: 'none', stroke: color, 'stroke-width': 1.8,
    points: xs.map((x, i) => `${sx(x)},${sy(ys[i])}`).join(' ') };
  if (dash) attrs['stroke-dasharray'] = dash;
  return h('polyline', attrs);
}
"""

_SCREEN_ESM = _PLOT_HELPERS + r"""
function render({ model, el }) {
  el.innerHTML = '';
  const root = document.createElement('div');
  root.className = 'qp-root';
  el.appendChild(root);

  function draw() {
    const d = model.get('data') || {};
    root.innerHTML = '';
    if (!d.curve) return;
    const M = { l: 46, r: 10, t: 26, b: 40 };
    const pw = (d.width || 380);
    const SCREEN_H = 190, LINE_H = 100, GAP = 4;
    const W = M.l + pw + M.r;
    const H = M.t + SCREEN_H + GAP + LINE_H + M.b;
    const svg = h('svg', { viewBox: `0 0 ${W} ${H}`,
                           width: W, height: H });
    root.appendChild(svg);
    svg.appendChild(h('text', { x: M.l + pw / 2, y: 16,
      'text-anchor': 'middle', 'font-size': 12, 'font-weight': 'bold',
      fill: '#000', 'font-family': 'sans-serif' }, d.title || ''));
    // the screen: a dark plate that lights up where particles land
    svg.appendChild(h('rect', { x: M.l, y: M.t, width: pw,
      height: SCREEN_H, fill: '#101018', stroke: '#444' }));
    const hx = (x) => M.l + (x + 1) / 2 * pw;
    const hy = (y) => M.t + SCREEN_H - y * SCREEN_H;
    for (const [x, y] of d.hits || [])
      svg.appendChild(h('circle', { cx: hx(x), cy: hy(y), r: 1.4,
        fill: '#f5f0c0', opacity: 0.65 }));
    // the exact intensity curve, flush under the screen
    const oy = M.t + SCREEN_H + GAP;
    const { sx, sy } = axes(svg, M, pw, LINE_H, oy, [-1, 1], [0, 1.05],
                            'screen position', 'intensity');
    svg.appendChild(polyline(d.curve.x, d.curve.y, sx, sy, '#4477cc'));
  }

  model.on('change:data', draw);
  draw();
}

export default { render };
"""

_LINEPLOT_ESM = _PLOT_HELPERS + r"""
function render({ model, el }) {
  el.innerHTML = '';
  const root = document.createElement('div');
  root.className = 'qp-root';
  el.appendChild(root);

  function draw() {
    const d = model.get('data') || {};
    root.innerHTML = '';
    if (!d.series) return;
    const legendH = d.series.some((s) => s.name) ? 20 : 0;
    const M = { l: 46, r: 10, t: 8 + legendH, b: 40 };
    const pw = d.width || 900, ph = d.height || 180;
    const W = M.l + pw + M.r, H = M.t + ph + M.b;
    const svg = h('svg', { viewBox: `0 0 ${W} ${H}`,
                           width: W, height: H });
    root.appendChild(svg);
    if (legendH) {
      let lx = M.l;
      for (const s of d.series) {
        const attrs = { x1: lx, y1: 12, x2: lx + 22, y2: 12,
          stroke: s.color, 'stroke-width': 2 };
        if (s.dash) attrs['stroke-dasharray'] = s.dash;
        svg.appendChild(h('line', attrs));
        const t = h('text', { x: lx + 27, y: 15, 'font-size': 11,
          fill: '#000', 'font-family': 'sans-serif' }, s.name || '');
        svg.appendChild(t);
        lx += 27 + 7 * (s.name || '').length + 24;
      }
    }
    const allx = d.series.flatMap((s) => s.x);
    const ally = d.series.flatMap((s) => s.y);
    const xd = d.xdomain || [Math.min(...allx), Math.max(...allx)];
    const yd = d.ydomain || [Math.min(0, ...ally),
                             Math.max(...ally) * 1.02];
    const { sx, sy } = axes(svg, M, pw, ph, M.t, xd, yd,
                            d.xlabel, d.ylabel);
    for (const s of d.series)
      svg.appendChild(polyline(s.x, s.y, sx, sy, s.color, s.dash));
  }

  model.on('change:data', draw);
  draw();
}

export default { render };
"""


class ScreenPanelWidget(anywidget.AnyWidget):
    """The double-slit results panel: a dark screen accumulating
    photon hits, with the exact intensity curve flush beneath it —
    both panels flush-aligned in one native SVG."""
    _esm = _SCREEN_ESM
    _css = _PLOT_CSS
    data = traitlets.Dict({}).tag(sync=True)


class LinePlotWidget(anywidget.AnyWidget):
    """A small multi-series line plot (axes, grid, legend, dashes) in
    the same house style as the other native widgets."""
    _esm = _LINEPLOT_ESM
    _css = _PLOT_CSS
    data = traitlets.Dict({}).tag(sync=True)


class BuilderWidget(anywidget.AnyWidget):
    """The canvas. `graph` mirrors the on-screen network and is what
    quantish.builder turns into a runnable config."""
    _esm = _ESM
    _css = _CSS
    graph = traitlets.Dict(
        {'gates': {}, 'particles': {}, 'links': []}).tag(sync=True)
    # display labels for gate angles / plate phases ({'g1':
    # 'pi/6 (30.0°)'}), computed by the app — specs are sympy syntax
    # the browser cannot evaluate
    angle_labels = traitlets.Dict({}).tag(sync=True)
