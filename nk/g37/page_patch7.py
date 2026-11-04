#!/usr/bin/env python3
# g37/page_patch7.py (2026-11-02): the pages draw the brain's own places and move them as the brain moves them. The owner (11-02): "the points
# are static and don't move based on which shard was used? which each fucking shard might have a different meaning which would mean the
# relationship pulls would adjust at least slightly changing the meaning in the graph slightly". A switch on the stage, "the brain's places",
# on by default: a point sits at the brain's x y z times the spacing slider (the drawing only); the page's own springs and space-apart pass
# are not run (the brain's physics decides); the page asks the door every two seconds which points moved and glides them there; a settle
# pass makes it read every place again. Off: the page draws as before (its own springs). A clicked point still shows the brain's place.
# The kernel's door: /api/moved?since=CLOCK answers the kernel's moved read; /api/graph?fresh=1 reads the bundle again; the memory nodes of
# the chosen line are answered from the bundle (the keyed kernel refused that read before, so the line's memory nodes never showed).
import sys
def patch(p, pairs):
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (p, s.count(old), old[:90])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s); print('patched', p, len(pairs))
PAGE = [
    # the switch, beside the memory switch in the stage's list
    ("<input type=\"checkbox\" id=\"memall\"",
     "<input type=\"checkbox\" id=\"brainxyz\" checked> the brain's places (a point sits where the brain holds it, times the spacing; it moves when the brain moves it; off: the page's own springs)<br><input type=\"checkbox\" id=\"memall\""),
    # the places read: XYZ from the bundle (hp) or the table (hub); a poll for moves
    ("  var XYZ = {}, FORMULA_APPLIED = false;\n",
     "  var XYZ = {}, FORMULA_APPLIED = false, XYZCLOCK = 0, BRAINXYZ = true;\n"
     "  function brainOn() { var el = document.getElementById('brainxyz'); return el ? el.checked : false; }\n"
     "  function brainPos(k, n) { var b = XYZ[+k]; if (!b) return false; n.pos.set(b[1] * SP, b[2] * SP, b[3] * SP); n.unplaced = false; return true; }\n"
     "  // which points the brain moved since the last ask: the kernel's door answers /api/moved; the hub's door answers the table by its clock column\n"
     "  function pollMoved() {\n"
     "    if (!ready || !brainOn()) return;\n"
     "    api('/api/moved?since=' + XYZCLOCK).then(function (j) { if (j.passes) { api('/api/graph?fresh=1').then(function (g) { XYZ = {}; (g.xyz || []).forEach(function (r) { XYZ[r[0]] = r; }); Object.keys(NODE).forEach(function (k) { if (NODE[k].mesh && NODE[k].mesh.visible) brainPos(k, NODE[k]); }); }); }\n"
     "      (j.moved || []).forEach(function (m) { XYZ[m[0]] = [m[0], m[1], m[2], m[3], 0]; var n = NODE[String(m[0])]; if (n && n.mesh && n.mesh.visible) { n.glide = new THREE.Vector3(m[1] * SP, m[2] * SP, m[3] * SP); } });\n"
     "      if (j.clock) XYZCLOCK = j.clock; }).catch(function () {\n"
     "      q('SELECT gate, x, y, z, at FROM main.xyz WHERE at > ? ORDER BY at LIMIT 20000', [XYZCLOCK]).then(function (rows) { rows.forEach(function (m) { XYZ[m[0]] = [m[0], m[1], m[2], m[3], 0]; var n = NODE[String(m[0])]; if (n && n.mesh && n.mesh.visible) n.glide = new THREE.Vector3(m[1] * SP, m[2] * SP, m[3] * SP); if (m[4] > XYZCLOCK) XYZCLOCK = m[4]; }); }).catch(function () {}); });\n"
     "  }\n"
     "  setInterval(pollMoved, 2000);\n"),
    # a new node takes the brain's place when the switch is on
    ("      n = NODE[k] = { key: k, pos: p, fixed: fixed, unplaced: !fixed, ghost: k.charAt(0) === 'g', mem: k.charAt(0) === 'm' };\n",
     "      n = NODE[k] = { key: k, pos: p, fixed: fixed, unplaced: !fixed, ghost: k.charAt(0) === 'g', mem: k.charAt(0) === 'm' };\n"
     "      if (brainOn() && !fixed && !n.ghost && !n.mem) brainPos(k, n);\n"),
    # the settle: with the brain's places on, the page's springs do not move points; the glide to a new place does
    ("  function settle(steps) {\n",
     "  function settle(steps) {\n"
     "    if (brainOn()) { Object.keys(NODE).forEach(function (k) { var n = NODE[k]; if (n.glide) { n.pos.lerp(n.glide, 0.25); if (n.pos.distanceTo(n.glide) < 0.05) { n.pos.copy(n.glide); n.glide = null; } } else if (n.unplaced && !n.mem && !n.ghost && brainPos(k, n)) {} }); placeNew(); _apartMs = 0; return; }\n"),
    # the switch re-places every point when turned on, and lets the springs settle when turned off
    ("    ['mapall', 'ghostlabels', 'spacept', 'runspace', 'memall', 'runmode'].forEach(function (id) {",
     "    $('brainxyz').addEventListener('change', function () { if (brainOn()) { Object.keys(NODE).forEach(function (k) { var n = NODE[k]; if (n.mesh && !n.fixed && !n.ghost && !n.mem) brainPos(k, n); }); } render(TK, true); reshape(); });\n"
     "    ['mapall', 'ghostlabels', 'spacept', 'runspace', 'memall', 'runmode'].forEach(function (id) {"),
    # XYZ read at load (both pages), as before, plus the clock
    ("    XYZ = {}; (R[11] || []).forEach(function (r) { XYZ[r[0]] = r; }); applyFormulas(R[12] || []);",
     "    XYZ = {}; (R[11] || []).forEach(function (r) { XYZ[r[0]] = r; }); applyFormulas(R[12] || []); if (!XYZCLOCK && g.clock) XYZCLOCK = g.clock;"),
]
SERVE8 = [
    ("            if u.path == '/api/graph':\n                d = bundle();",
     "            if u.path == '/api/moved': return self.send(200, ask('moved ' + str(int(qs.get('since', ['0'])[0]))))   # the points the brain moved since a clock (the timeline's move receipts)\n"
     "            if u.path == '/api/graph':\n                if qs.get('fresh', ['0'])[0] == '1': BUNDLE['d'] = None\n                d = bundle();"),
    ("'xyz': d.get('xyz', []), 'formula': d.get('formula', []), 'tables':",
     "'xyz': d.get('xyz', []), 'formula': d.get('formula', []), 'clock': ask('stats').get('main', {}).get('clock', 0), 'tables':"),
    # the memory nodes of the chosen line, from the bundle (the kernel refuses the keyless join)
    ("    if s.startswith('SELECT run, gate, shard, input FROM main.run_memory'): return {'cols': [], 'rows': d['memrows']}\n",
     "    if s.startswith('SELECT run, gate, shard, input FROM main.run_memory'): return {'cols': [], 'rows': d['memrows']}\n"
     "    if s.startswith('SELECT m.run, m.gate, m.shard, m.input FROM main.run_memory m JOIN main.run r'):\n"
     "        root = int(params[0]) if params else 0; roots = {r[0]: r[3] for r in d['runs']}; return {'cols': [], 'rows': [m for m in d['memrows'] if m[0] == root or roots.get(m[0]) == root]}\n"),
]
if __name__ == '__main__':
    for p in sys.argv[1:]:
        if p.endswith('.html'): patch(p, PAGE)
        elif p.endswith('serve8.py'): patch(p, SERVE8)
