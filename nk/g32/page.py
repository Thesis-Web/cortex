import re
p='/home/james/nk/NEURON-POINT-OF-CONNECTION-nk-light-2026-10-30.html'; s=open(p,encoding='utf-8').read()
open(p+'.before-2026-11-01','w',encoding='utf-8').write(s)
def R(a,b,n=1):
    global s
    assert s.count(a)>=1, a[:70]
    s=s.replace(a,b) if n==0 else s.replace(a,b,n)
# a defined point is blue, an undefined one stays grey
R("return touched ? (G && G.nodes ? 0xa9c3dc : 0xbfc6cf) : 0x5f6874; }","return (G && G.nodes) ? 0x6ea8fe : (touched ? 0xbfc6cf : 0x5f6874); }")
R("var COLORS = { 'dna before': 0x6f8fb8,","var COLORS = { memory: 0x5fcf92, 'dna before': 0x6f8fb8,")
# memory nodes: small green points, one a line, tied to the gates of the line
R("  function addSpring(a, b, kind, w) {","""  function ensureMem(id, gates) {
    if (!hasGL) return; var k = 'm:' + id, n = NODE[k]; if (n) return n;
    n = NODE[k] = { key: k, g: gates[0], pos: new THREE.Vector3(0, 0, 0), fixed: false, unplaced: true, touched: false, mem: true, f: new THREE.Vector3() };
    n.mesh = new THREE.Mesh(dotGeo, new THREE.MeshBasicMaterial({ color: 0x5fcf92, transparent: true, opacity: .95 })); n.mesh.scale.setScalar(.8); n.mesh.userData = { g: gates[0], base: .8 }; dotGroup.add(n.mesh);
    n.label = makeLabel(' ', '#5fcf92', 9); labelGroup.add(n.label);
    gates.forEach(function (g) { if (NODE[String(g)]) addSpring(k, g, 'memory', .6); }); return n;
  }
  function addSpring(a, b, kind, w) {""")
# a run read into the stage: alone, or added to what is there (follow)
R("function loadRun(schema, id, cb) {","function loadRun(schema, id, cb, merge) {")
R("      RUN = r; SCHEMA = schema; GATES = r.gates; NAMES = r.names; TK = r.hops.length;\n      clearStage();\n","""      if (!merge) FOLLOW = false;
      var over = merge && Object.keys(NODE).length > 1400;
      if (merge && !over && Object.keys(GATES).length) { Object.keys(r.gates).forEach(function (g) { GATES[g] = r.gates[g]; }); Object.keys(r.names).forEach(function (g) { NAMES[g] = r.names[g]; }); RUN = r; SCHEMA = schema; TK = r.hops.length; }
      else { RUN = r; SCHEMA = schema; GATES = r.gates; NAMES = r.names; TK = r.hops.length; clearStage(); }
""")
R("      FIXED = touched[1] ? 1 : (r.hops.length ? r.hops[0][2] : null);\n      Object.keys(GATES).forEach(function (g) { ensureNode(+g, true); });\n      Object.keys(GATES).forEach(function (g) { GATES[g].shards.forEach(","""      if (!merge || over || FIXED === null) FIXED = touched[1] ? 1 : (r.hops.length ? r.hops[0][2] : (r.line && r.line[0]) || null);
      Object.keys(r.gates).forEach(function (g) { ensureNode(+g, true); var n = NODE[g]; n.touched = true; if (hasGL) { n.mesh.material.color.setHex(colorOf(+g, true)); n.mesh.material.opacity = .95; } });
      Object.keys(r.gates).forEach(function (g) { r.gates[g].shards.forEach(""")
R("      placeNew(); settle(60); animLeft = 40; FIT = true; fit();\n","""      if (r.line && r.line.length) { ensureMem(r.run.id, r.line.filter(function (g) { return NODE[String(g)]; }).concat(r.mem_gate && NODE[String(r.mem_gate)] ? [r.mem_gate] : [])); }
      placeNew(); settle(merge ? 12 : 60); animLeft = merge ? 16 : 40; FIT = true; fit();
""")
# follow the brain, and colour points as they are resolved
R("  setInterval(function () { if (!playing) api('/api/stats').then(function (s) { STATS = s; tiles(); }); }, 15000);\n","""  setInterval(function () { if (!playing) api('/api/stats').then(function (s) { STATS = s; tiles(); }); }, 3000);
  var FOLLOW = true, following = false, lastFollow = 0;
  function followTick() {
    if (!FOLLOW || playing || following || !ready) return; following = true;
    api('/api/newest?schema=main&n=6').then(function (N) {
      NEWEST = N; renderNewest();
      var l = (N.told || []).filter(function (x) { return x.ended && /^define/.test(x.text); })[0] || N.lines[0];
      if (!l || l.run === lastFollow) { following = false; return; }
      lastFollow = l.run; loadRun('main', l.run, function () { following = false; }, true);
      setTimeout(function () { following = false; }, 4000);
    }).catch(function () { following = false; });
  }
  setInterval(followTick, 1500);
  setInterval(function () {
    var grey = Object.keys(NODE).filter(function (k) { var n = NODE[k]; return !n.mem && !(GATES[k] && GATES[k].nodes); }).slice(0, 500); if (!grey.length) return;
    api('/api/q', { sql: 'SELECT gate, nodes FROM ' + SCHEMA + '.neuron WHERE gate IN (' + grey.join(',') + ')' }).then(function (r) { (r.rows || []).forEach(function (x) { if (x[1] > 0) { GATES[x[0]] = GATES[x[0]] || { s: nameOf(x[0]), shards: [], rel: [] }; GATES[x[0]].nodes = x[1]; var n = NODE[String(x[0])]; if (n && hasGL) n.mesh.material.color.setHex(0x6ea8fe); } }); });
  }, 4000);
""")
R("var T = [['runs', fmtN(m.runs)],","var T = [['points defined', fmtN(m.defined)], ['runs', fmtN(m.runs)],")
# the button
R("""  <div id="busy\"""","""  <div id="busy\"""") if False else None
m=re.search(r'<div id="controls">',s); assert m
s=s[:m.end()]+'<label style="white-space:nowrap"><input type="checkbox" id="follow" checked> follow the brain</label>'+s[m.end():]
R("  $('gap').addEventListener('input',","  $('follow').addEventListener('change', function () { FOLLOW = this.checked; });\n  $('gap').addEventListener('input',")
R("      renderRun(); renderNewest(); ready = true;","      $('follow').checked = FOLLOW; renderRun(); renderNewest(); ready = true;")
open(p,'w',encoding='utf-8').write(s); print('page patched',len(s))
