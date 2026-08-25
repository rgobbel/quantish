"""The network builder's drag-and-drop canvas, as an anywidget.

The widget edits the plain-dict graph that quantish.builder consumes:
gates and particles with positions, and links from outputs to inputs.
All drawing is hand-rolled SVG in the same visual language as the
circuit diagrams; there are no external JS dependencies, so the widget
works in the WASM builds too.

Interactions:
  toolbar        add a gate / phase plate / particle, group the
                 selection into a stage or diagram group, delete
  drag body      move a gate or particle (a shift-selection moves
                 together)
  drag out-port  rubber-band a wire; drop on a free in-port to connect
  click          select a gate, particle, or wire (then Delete works)
  shift-click    toggle a gate in the multi-selection (for grouping)
  double-click   gate: edit its angle - phase plate: edit its phase -
                 particle: flip its sign
"""
import anywidget
import traitlets

_CSS = """
.qb-root { font-family: -apple-system, 'Segoe UI', Helvetica, sans-serif; }
.qb-toolbar { display: flex; gap: 8px; align-items: center;
              padding: 6px 2px; }
.qb-toolbar button { font-size: 13px; padding: 4px 10px;
                     border: 1px solid #bbb; border-radius: 6px;
                     background: #fff; cursor: pointer; color: #000; }
.qb-toolbar button:hover { border-color: #5c64d1; background: #f6f7ff; }
.qb-hint { font-size: 12px; color: #000; margin-left: auto; }
.qb-svg { border: 1px solid #ddd; border-radius: 8px; background: #fff;
          display: block; width: 100%; }
"""

_ESM = r"""
const GW = 132, GH = 108;                      // gate box size
const PW = 46, PH = 46;                        // phase-plate box size
const PORT_Y = { control: 24, upper: 52, lower: 80 };
const WIRES = ['control', 'upper', 'lower'];
const PR = 18;                                 // particle radius
const C = {
  gateFill: '#e6f4f1', gateStroke: '#2f9e8f',
  plateFill: '#f3e8ff', plateStroke: '#8b5cf6',
  portFill: '#e0e7ff', portStroke: '#5c64d1',
  particleFill: '#f4f4f6', particleStroke: '#8b93a0',
  wire: '#22314a', select: '#d97706', target: '#16a34a',
};
const SUB = {'0':'₀','1':'₁','2':'₂','3':'₃',
             '4':'₄','5':'₅','6':'₆','7':'₇',
             '8':'₈','9':'₉'};
const subName = (s) => s.replace(/(?<=[A-Za-zφ])(\d+)/g,
  (m) => [...m].map((c) => SUB[c] ?? c).join(''));

// a phase plate is a compact one-wire gate; everything geometric
// branches through these
const isPlate = (gd) => gd.kind === 'phase';
const dims = (gd) => isPlate(gd) ? [PW, PH] : [GW, GH];
const wiresOf = (gd) => isPlate(gd) ? ['control'] : WIRES;
const portY = (gd, w) => isPlate(gd) ? PH / 2 : PORT_Y[w];
const showDeg = (v) => `${Math.round((v ?? 0) * 10000) / 10000}°`;

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
  const bar = document.createElement('div');
  bar.className = 'qb-toolbar';
  const addGateBtn = document.createElement('button');
  addGateBtn.textContent = '+ gate';
  const addPlateBtn = document.createElement('button');
  addPlateBtn.textContent = '+ φ plate';
  const addPartBtn = document.createElement('button');
  addPartBtn.textContent = '+ particle';
  const stageBtn = document.createElement('button');
  stageBtn.textContent = 'stage…';
  const dgroupBtn = document.createElement('button');
  dgroupBtn.textContent = 'diagram group…';
  const delBtn = document.createElement('button');
  delBtn.textContent = 'delete selected';
  const hint = document.createElement('div');
  hint.className = 'qb-hint';
  hint.textContent = 'drag output → input to wire · double-click to ' +
    'edit · shift-click gates, then stage…/diagram group…';
  bar.append(addGateBtn, addPlateBtn, addPartBtn, stageBtn, dgroupBtn,
             delBtn, hint);
  const svg = h('svg', { class: 'qb-svg', height: 560 });
  root.append(bar, svg);
  el.appendChild(root);

  const graph = () => model.get('graph');
  const commit = (g) => {
    model.set('graph', JSON.parse(JSON.stringify(g)));
    model.save_changes();
  };

  // local, uncommitted interaction state
  let selected = null;        // {kind:'gate'|'particle'|'link', key}
  let drag = null;            // {kind, key, dx, dy, others}
  let wire = null;            // {src, x, y}
  const multi = new Set();    // shift-selected gate names

  const outXY = (g, src) => {
    if (src.includes('.')) {
      const [gn, w] = src.split('.');
      const gd = g.gates[gn];
      return gd && [gd.x + dims(gd)[0], gd.y + portY(gd, w)];
    }
    const p = g.particles[src];
    return p && [p.x + 2 * PR, p.y + PR];
  };
  const inXY = (g, dst) => {
    const [gn, w] = dst.split('.');
    const gd = g.gates[gn];
    return gd && [gd.x, gd.y + portY(gd, w)];
  };
  const usedSrc = (g) => new Set(g.links.map((l) => l[0]));
  const usedDst = (g) => new Set(g.links.map((l) => l[1]));

  function svgPoint(ev) {
    const r = svg.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top];
  }

  function wirePath(x1, y1, x2, y2) {
    const mx = Math.max(30, Math.abs(x2 - x1) / 2);
    return `M ${x1} ${y1} C ${x1 + mx} ${y1}, ${x2 - mx} ${y2}, ` +
           `${x2} ${y2}`;
  }

  function redraw() {
    const g = graph();
    svg.innerHTML = '';
    const srcTaken = usedSrc(g), dstTaken = usedDst(g);

    // diagram-group outlines first, behind everything
    const dgroups = {};
    for (const gd of Object.values(g.gates))
      if (gd.dgroup) (dgroups[gd.dgroup] ??= []).push(gd);
    for (const [gname, members] of Object.entries(dgroups)) {
      const x1 = Math.min(...members.map((m) => m.x)) - 10;
      const y1 = Math.min(...members.map((m) => m.y)) - 22;
      const x2 = Math.max(...members.map((m) => m.x + dims(m)[0])) + 10;
      const y2 = Math.max(...members.map((m) => m.y + dims(m)[1])) + 10;
      svg.appendChild(h('rect', {
        x: x1, y: y1, width: x2 - x1, height: y2 - y1, rx: 10,
        fill: 'none', stroke: C.wire, 'stroke-width': 1,
        'stroke-dasharray': '6 4', 'pointer-events': 'none',
      }));
      svg.appendChild(h('text', {
        x: x1 + 8, y: y1 + 13, 'font-size': 10, fill: '#000',
        'font-style': 'italic', 'pointer-events': 'none',
      }, subName(gname)));
    }

    // wires next, under the nodes
    g.links.forEach((l, i) => {
      const a = outXY(g, l[0]), b = inXY(g, l[1]);
      if (!a || !b) return;
      const sel = selected?.kind === 'link' && selected.key === i;
      svg.appendChild(h('path', {
        d: wirePath(...a, ...b), fill: 'none',
        stroke: sel ? C.select : C.wire, 'stroke-width': sel ? 3 : 2,
        'data-link': i, style: 'cursor: pointer',
      }));
      // a fatter invisible hit area so wires are clickable
      svg.appendChild(h('path', {
        d: wirePath(...a, ...b), fill: 'none', stroke: 'transparent',
        'stroke-width': 10, 'data-link': i, style: 'cursor: pointer',
      }));
    });

    for (const [name, gd] of Object.entries(g.gates)) {
      const [w0, h0] = dims(gd);
      const plate = isPlate(gd);
      const sel = selected?.kind === 'gate' && selected.key === name;
      const inMulti = multi.has(name);
      const grp = h('g', { 'data-gate': name, style: 'cursor: move' });
      grp.appendChild(h('rect', {
        x: gd.x, y: gd.y, width: w0, height: h0, rx: 8,
        fill: plate ? C.plateFill : C.gateFill,
        stroke: (sel || inMulti) ? C.select
                                 : plate ? C.plateStroke : C.gateStroke,
        'stroke-width': (sel || inMulti) ? 2.5 : 1.5,
        ...(inMulti && !sel ? { 'stroke-dasharray': '5 3' } : {}),
      }));
      if (gd.stage) grp.appendChild(h('text', {
        x: gd.x + w0, y: gd.y - 5, 'text-anchor': 'end',
        'font-size': 10, 'font-style': 'italic', fill: '#000',
      }, subName(gd.stage)));
      if (plate) {
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + h0 / 2 - 3, 'text-anchor': 'middle',
          'font-size': 13, 'font-weight': 600, fill: '#000',
        }, subName(name)));
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + h0 - 8, 'text-anchor': 'middle',
          'font-size': 10, fill: '#000',
        }, showDeg(gd.phase)));
      } else {
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + 15, 'text-anchor': 'middle',
          'font-size': 13, 'font-weight': 600, fill: '#000',
        }, subName(name)));
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + h0 - 6, 'text-anchor': 'middle',
          'font-size': 11, fill: '#000',
        }, showDeg(gd.angle)));
      }
      for (const w of wiresOf(gd)) {
        const y = gd.y + portY(gd, w);
        if (!plate) grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: y + 3.5, 'text-anchor': 'middle',
          'font-size': 10, fill: '#000',
        }, w));
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
      svg.appendChild(grp);
    }

    for (const [name, p] of Object.entries(g.particles)) {
      const sel = selected?.kind === 'particle' && selected.key === name;
      const grp = h('g', { 'data-particle': name, style: 'cursor: move' });
      grp.appendChild(h('circle', {
        cx: p.x + PR, cy: p.y + PR, r: PR,
        fill: C.particleFill,
        stroke: sel ? C.select : C.particleStroke,
        'stroke-width': sel ? 2.5 : 1.5,
      }));
      grp.appendChild(h('text', {
        x: p.x + PR, y: p.y + PR + 4, 'text-anchor': 'middle',
        'font-size': 12, 'font-weight': 600, fill: '#000',
      }, (p.sign < 0 ? '−' : '+') + subName(name)));
      grp.appendChild(h('circle', {
        cx: p.x + 2 * PR, cy: p.y + PR, r: 6,
        fill: srcTaken.has(name) ? C.portStroke : C.portFill,
        stroke: C.portStroke, 'stroke-width': 1.5,
        'data-outport': name, style: 'cursor: crosshair',
      }));
      svg.appendChild(grp);
    }

    if (wire) {
      const a = outXY(g, wire.src);
      if (a) svg.appendChild(h('path', {
        d: wirePath(...a, wire.x, wire.y), fill: 'none',
        stroke: C.select, 'stroke-width': 2, 'stroke-dasharray': '5 4',
        'pointer-events': 'none',
      }));
      // generous invisible drop zones over the free in-ports, drawn
      // last so releasing near a port lands the wire
      for (const [name, gd] of Object.entries(g.gates)) {
        for (const w of wiresOf(gd)) {
          const key = `${name}.${w}`;
          if (dstTaken.has(key)) continue;
          svg.appendChild(h('circle', {
            cx: gd.x, cy: gd.y + portY(gd, w), r: 16,
            fill: 'transparent', 'data-inport': key,
            style: 'cursor: crosshair',
          }));
        }
      }
    }
  }

  function nextName(prefix, coll) {
    let i = 1;
    while (coll[`${prefix}${i}`]) i += 1;
    return `${prefix}${i}`;
  }

  addGateBtn.onclick = () => {
    const g = graph();
    const n = Object.keys(g.gates).length;
    const name = nextName('g', g.gates);
    const copy = JSON.parse(JSON.stringify(g));
    copy.gates[name] = { x: 170 + (n % 4) * 190,
                         y: 40 + Math.floor(n / 4) * 150, angle: 0 };
    commit(copy);
  };
  addPlateBtn.onclick = () => {
    const g = graph();
    const n = Object.keys(g.gates).length;
    const name = nextName('φ', g.gates);
    const copy = JSON.parse(JSON.stringify(g));
    copy.gates[name] = { x: 170 + (n % 4) * 190,
                         y: 40 + Math.floor(n / 4) * 150,
                         kind: 'phase', phase: 0 };
    commit(copy);
  };
  addPartBtn.onclick = () => {
    const g = graph();
    const n = Object.keys(g.particles).length;
    const name = nextName('p', g.particles);
    const copy = JSON.parse(JSON.stringify(g));
    copy.particles[name] = { x: 24, y: 60 + n * 70, sign: 1, weight: 1 };
    commit(copy);
  };

  // stage… / diagram group… name the multi-selection (or the single
  // selected gate); an empty name clears the assignment
  const assign = (field, label) => {
    const g = graph();
    const targets = multi.size
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
    const copy = JSON.parse(JSON.stringify(g));
    for (const k of targets) {
      if (raw.trim()) copy.gates[k][field] = raw.trim();
      else delete copy.gates[k][field];
    }
    multi.clear();
    commit(copy);
  };
  stageBtn.onclick = () => assign('stage', 'stage name');
  dgroupBtn.onclick = () => assign('dgroup', 'diagram group');

  function deleteSelected() {
    if (multi.size) {
      const copy = JSON.parse(JSON.stringify(graph()));
      for (const k of multi) {
        delete copy.gates[k];
        copy.links = copy.links.filter(
          (l) => !l[0].startsWith(k + '.') && !l[1].startsWith(k + '.'));
      }
      multi.clear();
      selected = null;
      commit(copy);
      return;
    }
    if (!selected) return;
    const copy = JSON.parse(JSON.stringify(graph()));
    if (selected.kind === 'link') {
      copy.links.splice(selected.key, 1);
    } else if (selected.kind === 'gate') {
      delete copy.gates[selected.key];
      copy.links = copy.links.filter(
        (l) => !l[0].startsWith(selected.key + '.') &&
               !l[1].startsWith(selected.key + '.'));
    } else {
      delete copy.particles[selected.key];
      copy.links = copy.links.filter((l) => l[0] !== selected.key);
    }
    selected = null;
    commit(copy);
  }
  delBtn.onclick = deleteSelected;
  root.tabIndex = 0;
  root.addEventListener('keydown', (ev) => {
    if (ev.key === 'Delete' || ev.key === 'Backspace') {
      ev.preventDefault();
      deleteSelected();
    }
  });

  // Double-clicks are detected by hand: every redraw() rebuilds the
  // SVG nodes, and the browser only counts clicks on the *same* node,
  // so the native dblclick event never fires here.
  let lastDown = { key: null, t: 0 };

  function editNode(grp) {
    const copy = JSON.parse(JSON.stringify(graph()));
    if (grp.dataset.gate) {
      const gd = copy.gates[grp.dataset.gate];
      const field = isPlate(gd) ? 'phase' : 'angle';
      const raw = window.prompt(
        `${field} for ${grp.dataset.gate} (degrees)`, gd[field] ?? 0);
      if (raw === null) return;
      const v = parseFloat(raw);
      if (Number.isNaN(v)) return;
      gd[field] = v;
    } else {
      const p = copy.particles[grp.dataset.particle];
      p.sign = p.sign < 0 ? 1 : -1;
    }
    commit(copy);
  }

  svg.addEventListener('mousedown', (ev) => {
    const t = ev.target;
    const [x, y] = svgPoint(ev);
    if (t.dataset.outport) {
      wire = { src: t.dataset.outport, x, y };
      redraw();
      return;
    }
    const grp = t.closest('[data-gate],[data-particle]');
    if (grp) {
      if (ev.shiftKey && grp.dataset.gate) {
        // shift-click builds the multi-selection for grouping
        if (multi.has(grp.dataset.gate)) multi.delete(grp.dataset.gate);
        else multi.add(grp.dataset.gate);
        lastDown = { key: null, t: 0 };
        redraw();
        return;
      }
      const key = grp.dataset.gate ? `g:${grp.dataset.gate}`
                                   : `p:${grp.dataset.particle}`;
      if (lastDown.key === key && ev.timeStamp - lastDown.t < 400) {
        lastDown = { key: null, t: 0 };
        drag = null;
        editNode(grp);
        return;
      }
      lastDown = { key, t: ev.timeStamp };
      const g = graph();
      if (grp.dataset.gate) {
        const gd = g.gates[grp.dataset.gate];
        selected = { kind: 'gate', key: grp.dataset.gate };
        drag = { kind: 'gate', key: grp.dataset.gate,
                 dx: x - gd.x, dy: y - gd.y };
        if (multi.has(grp.dataset.gate))
          // dragging a shift-selected gate carries the others along
          drag.others = [...multi]
            .filter((k) => k !== grp.dataset.gate && g.gates[k])
            .map((k) => ({ k, ox: g.gates[k].x - gd.x,
                           oy: g.gates[k].y - gd.y }));
        else multi.clear();
      } else {
        multi.clear();
        const p = g.particles[grp.dataset.particle];
        selected = { kind: 'particle', key: grp.dataset.particle };
        drag = { kind: 'particle', key: grp.dataset.particle,
                 dx: x - p.x, dy: y - p.y };
      }
      redraw();
      return;
    }
    if (t.dataset.link !== undefined) {
      multi.clear();
      selected = { kind: 'link', key: Number(t.dataset.link) };
      redraw();
      return;
    }
    multi.clear();
    selected = null;
    redraw();
  });

  svg.addEventListener('mousemove', (ev) => {
    const [x, y] = svgPoint(ev);
    if (wire) {
      wire.x = x;
      wire.y = y;
      redraw();
    } else if (drag) {
      const g = graph();   // mutate the model's copy locally, commit on drop
      const node = drag.kind === 'gate' ? g.gates[drag.key]
                                        : g.particles[drag.key];
      node.x = Math.max(0, x - drag.dx);
      node.y = Math.max(0, y - drag.dy);
      for (const o of drag.others || []) {
        g.gates[o.k].x = Math.max(0, node.x + o.ox);
        g.gates[o.k].y = Math.max(0, node.y + o.oy);
      }
      drag.moved = true;
      redraw();
    }
  });

  svg.addEventListener('mouseup', (ev) => {
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
      if (drag.moved) commit(graph());
      drag = null;
    }
  });
  svg.addEventListener('mouseleave', () => {
    if (wire || drag) {
      wire = null;
      drag = null;
      redraw();
    }
  });

  model.on('change:graph', redraw);
  redraw();
}

export default { render };
"""


class BuilderWidget(anywidget.AnyWidget):
    """The canvas. `graph` mirrors the on-screen network and is what
    quantish.builder turns into a runnable config."""
    _esm = _ESM
    _css = _CSS
    graph = traitlets.Dict(
        {'gates': {}, 'particles': {}, 'links': []}).tag(sync=True)
