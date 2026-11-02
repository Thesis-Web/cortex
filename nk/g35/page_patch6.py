#!/usr/bin/env python3
# g35/page_patch6.py (2026-11-02): the pages read the brain's formulas and places (the look unchanged: the kinds list, sliders, directions,
# stage, play, step, prompt as they are). Applied to the kernel's page (hp ~/nk and tries/28/door) and the hub's page (/home/exnulla/neuron/hub/page).
#  - the kinds' pull sliders and direction choices start from the brain's pull and formula rows (once per load; the owner's sliders still rule the drawing)
#  - a point the brain has placed (xyz) starts its drawing there instead of at its neighbours' mean
#  - a clicked point shows the brain's x, y, z, how many times it moved, the run, clock, shard, before and next of its last move
# serve8.py (the kernel's door): the two reads answered from the bundle.
import sys, os
def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (p, s.count(old), old[:90])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s); print('patched', p, len(pairs))
PAGE = [
    ("      q('SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ? ORDER BY id', [HISTLAST])\n    ]).then(absorb);",
     "      q('SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ? ORDER BY id', [HISTLAST]),\n"
     "      q('SELECT gate, x, y, z, moved FROM main.xyz').catch(function () { return []; }),   // the places the brain holds (none before the xyz table is laid)\n"
     "      q('SELECT p.kind, f.pull, f.rest, f.dx, f.dy, f.dz, f.mode FROM main.pull p JOIN main.formula f ON f.id = p.formula').catch(function () { return []; })   // the formulas: each kind's pull, rest and direction, the brain's rows\n"
     "    ]).then(absorb);"),
    ("    var g = R[1]; DNA = g.dna; NODES = g.nodes || {}; REL = g.rel || []; MEMN = g.mem || {}; FIRST = g.first || {};\n",
     "    var g = R[1]; DNA = g.dna; NODES = g.nodes || {}; REL = g.rel || []; MEMN = g.mem || {}; FIRST = g.first || {};\n"
     "    XYZ = {}; (R[11] || []).forEach(function (r) { XYZ[r[0]] = r; }); applyFormulas(R[12] || []);   // the brain's places and formulas (2026-11-02)\n"),
    ("  function addKind(k, w, title) { if (RELSET[k]) return; RELSET[k] = { on: true, w: w, dir: DEFAULT_DIR[k] || '' }; $('reltypes').insertAdjacentHTML('beforeend', kindRow(k, w, title)); }\n",
     "  function addKind(k, w, title) { if (RELSET[k]) return; RELSET[k] = { on: true, w: w, dir: DEFAULT_DIR[k] || '' }; $('reltypes').insertAdjacentHTML('beforeend', kindRow(k, w, title)); }\n"
     "  // the brain's formulas (pull, rest, direction per kind: its formula and pull rows) become the kinds' defaults, once per load; a slider or drop-down moved after that rules the drawing\n"
     "  var XYZ = {}, FORMULA_APPLIED = false;\n"
     "  function applyFormulas(rows) {\n"
     "    if (FORMULA_APPLIED || !rows.length) return; FORMULA_APPLIED = true;\n"
     "    rows.forEach(function (r) { var s = LAB[r[0]]; if (s === undefined) return; var k = REL_OF[s] || s; if (!RELSET[k]) addKind(k, r[1], 'a rel row: the kind word ' + s);\n"
     "      var dir = r[6] === 2 ? 'across' : r[6] === 1 ? (r[3] < 0 ? '-x' : r[3] > 0 ? 'x' : r[4] < 0 ? '-y' : r[4] > 0 ? 'y' : r[5] < 0 ? '-z' : r[5] > 0 ? 'z' : '') : '';\n"
     "      RELSET[k].w = r[1]; REST[k] = r[2]; RELSET[k].dir = dir;\n"
     "      var sl = document.querySelector('input[data-relw=\"' + k + '\"]'); if (sl) sl.value = r[1]; var se = document.querySelector('select[data-reldir=\"' + k + '\"]'); if (se) se.value = dir; });\n"
     "  }\n"),
    ("      n = NODE[k] = { key: k, pos: p, fixed: fixed, unplaced: !fixed, ghost: k.charAt(0) === 'g', mem: k.charAt(0) === 'm' };\n",
     "      n = NODE[k] = { key: k, pos: p, fixed: fixed, unplaced: !fixed, ghost: k.charAt(0) === 'g', mem: k.charAt(0) === 'm' };\n"
     "      var bx = (!fixed && !n.ghost && !n.mem) ? XYZ[+k] : null; if (bx) { n.pos.set(bx[1], bx[2], bx[3]); n.unplaced = false; }   // the brain's own place for the point, when it holds one: the drawing starts there\n"),
    ("(the page\\'s drawing, not the brain\\'s)</span>';",
     "(the page\\'s drawing)</span><span class=\"m\" id=\"brainxyz\">reading the brain\\'s place…</span>';"),
    ("    $('sel').innerHTML = h;\n",
     "    $('sel').innerHTML = h;\n"
     "    q('SELECT x, y, z, shard, before, next, at, run, moved FROM main.xyz WHERE gate = ?', [g]).then(function (r) { var el = $('brainxyz'); if (!el || SELG !== g) return; if (!r.length) { el.textContent = 'the brain holds no place for it yet (a point is placed at its first use, or by a settle pass)'; return; } var x = r[0]; el.textContent = 'the brain holds it at ' + (+x[0]).toFixed(1) + ', ' + (+x[1]).toFixed(1) + ', ' + (+x[2]).toFixed(1) + ' · moved ' + x[8] + ' times · last by run ' + x[7] + ' at clock ' + x[6] + ' (shard ' + x[3] + ', before ' + (x[4] === null ? '∅' : nameOf(x[4])) + ', next ' + (x[5] === null ? '∅' : nameOf(x[5])) + ')'; }).catch(function () { var el = $('brainxyz'); if (el) el.textContent = 'the brain holds no xyz table'; });\n"),
]
SERVE8 = [
    ("    if s.startswith('SELECT run, gate, shard, input FROM main.run_memory'): return {'cols': [], 'rows': d['memrows']}\n",
     "    if s.startswith('SELECT run, gate, shard, input FROM main.run_memory'): return {'cols': [], 'rows': d['memrows']}\n"
     "    if s.startswith('SELECT gate, x, y, z, moved FROM main.xyz'): return {'cols': [], 'rows': d.get('xyz', [])}   # the places of the included points (the xyz table is read by gate; the bundle carries them)\n"
     "    if s.startswith('SELECT p.kind, f.pull, f.rest, f.dx, f.dy, f.dz, f.mode FROM main.pull p'): return {'cols': [], 'rows': d.get('formula', [])}\n"),
]
if __name__ == '__main__':
    for p in sys.argv[1:]:
        if p.endswith('.html'): patch(p, PAGE)
        elif p.endswith('serve8.py'): patch(p, SERVE8)
