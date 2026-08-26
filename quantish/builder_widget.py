"""The network builder's drag-and-drop canvas, as an anywidget.

The widget edits the plain-dict graph that quantish.builder consumes:
gates and particles with positions, and links from outputs to inputs.
All drawing is hand-rolled SVG in the same visual language as the
circuit diagrams; there are no external JS dependencies, so the widget
works in the WASM builds too.

Interactions:
  toolbar        add a gate / phase plate / particle, group the
                 selection into a stage or diagram group, delete,
                 clear the canvas (confirmed, and undo-able),
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
                 plate body: its phase - particle body: flip its sign
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
.qb-svg { border: 1px solid #ddd; border-radius: 8px; background: #fff;
          display: block; width: 100%;
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
const SUB = {'0':'₀','1':'₁','2':'₂','3':'₃',
             '4':'₄','5':'₅','6':'₆','7':'₇',
             '8':'₈','9':'₉'};
const subName = (s) => s.replace(/(?<=[A-Za-zφ])(\d+)/g,
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
  const addGateBtn = document.createElement('button');
  addGateBtn.textContent = '+ gate';
  const addPlateBtn = document.createElement('button');
  addPlateBtn.textContent = '+ φ plate';
  const addDelayBtn = document.createElement('button');
  addDelayBtn.textContent = '+ delay';
  const addPartBtn = document.createElement('button');
  addPartBtn.textContent = '+ particle';
  const stageBtn = document.createElement('button');
  stageBtn.textContent = 'stage…';
  const dgroupBtn = document.createElement('button');
  dgroupBtn.textContent = 'diagram group…';
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
  bar.append(addGateBtn, addPlateBtn, addDelayBtn, addPartBtn,
             stageBtn, dgroupBtn, delBtn, clearBtn, undoBtn, redoBtn,
             hint);
  const svg = h('svg', { class: 'qb-svg', height: 560 });
  root.append(bar, svg);
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

    // wires next, under the nodes
    g.links.forEach((l, i) => {
      const a = outXY(g, l[0]), b = inXY(g, l[1]);
      if (!a || !b) return;
      const sel = (selected?.kind === 'link' && selected.key === i)
                  || inMultiOf('link', i);
      layer.appendChild(h('path', {
        d: wirePath(...a, ...b), fill: 'none',
        stroke: sel ? C.select : C.wire, 'stroke-width': sel ? 3 : 2,
        'data-link': i, style: 'cursor: pointer',
      }));
      // a fatter invisible hit area so wires are clickable
      layer.appendChild(h('path', {
        d: wirePath(...a, ...b), fill: 'none', stroke: 'transparent',
        'stroke-width': 10, 'data-link': i, style: 'cursor: pointer',
      }));
    });

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
        }, angleLabel(name, gd.phase)));
      } else {
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + 18, 'text-anchor': 'middle',
          'font-size': 15, 'font-weight': 600, fill: '#000',
          'data-name': name,
        }, subName(name)));
        grp.appendChild(h('text', {
          x: gd.x + w0 / 2, y: gd.y + 37, 'text-anchor': 'middle',
          'font-size': 11.5, fill: '#000',
        }, angleLabel(name, gd.angle)));
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

  addGateBtn.onclick = () => {
    const g = graph();
    const name = nextName('g', g.gates);
    const [x, y] = freeSpot(Object.values(g.gates), gateSlot);
    const copy = JSON.parse(JSON.stringify(g));
    copy.gates[name] = { x, y, angle: 0 };
    commit(copy);
  };
  addPlateBtn.onclick = () => {
    const g = graph();
    const name = nextName('φ', g.gates);
    const [x, y] = freeSpot(Object.values(g.gates), gateSlot);
    const copy = JSON.parse(JSON.stringify(g));
    copy.gates[name] = { x, y, kind: 'phase', phase: 0 };
    commit(copy);
  };
  addDelayBtn.onclick = () => {
    const g = graph();
    const name = nextName('d', g.gates);
    const [x, y] = freeSpot(Object.values(g.gates), gateSlot);
    const copy = JSON.parse(JSON.stringify(g));
    copy.gates[name] = { x, y, kind: 'delay' };
    commit(copy);
  };
  addPartBtn.onclick = () => {
    const g = graph();
    const name = nextName('p', g.particles);
    const [x, y] = freeSpot(Object.values(g.particles), partSlot);
    const copy = JSON.parse(JSON.stringify(g));
    copy.particles[name] = { x, y, sign: 1, weight: 1 };
    commit(copy);
  };

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

  const dropGate = (copy, k) => {
    delete copy.gates[k];
    copy.links = copy.links.filter(
      (l) => l[0] !== k && l[1] !== k &&
             !l[0].startsWith(k + '.') && !l[1].startsWith(k + '.'));
  };
  const dropParticle = (copy, k) => {
    delete copy.particles[k];
    copy.links = copy.links.filter((l) => l[0] !== k);
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
      const v = radEval(input.value);
      preview.textContent = v === null ? '= ?°'
        : `= ${Math.round(v * 180 / Math.PI * 100) / 100}°`;
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
        `${field} for ${gname} — radians, the model files' syntax: `
        + '0, pi/6, rad(30), acos(4/5), 0.5',
        copy.gates[gname][field] ?? 0,
        (s) => {
          const fresh = JSON.parse(JSON.stringify(graph()));
          const gd = fresh.gates[gname];
          if (!gd) return;
          // stored verbatim; the app validates the spec and reports
          // anything unparseable in the problems list
          gd[field] = /^-?\d+(\.\d+)?$/.test(s) ? parseFloat(s) : s;
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
      wire = { src: t.dataset.outport, x, y };
      redraw();
      return;
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
    # display labels for gate angles / plate phases ({'g1':
    # 'pi/6 (30.0°)'}), computed by the app — specs are sympy syntax
    # the browser cannot evaluate
    angle_labels = traitlets.Dict({}).tag(sync=True)
