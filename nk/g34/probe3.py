#!/usr/bin/env python3
# g34/probe3.py (2026-11-01, 17:55). Live reads for the owner's build-step prose: (a) the markers the sources' returns carry (wn, gcide,
# wikt, mwt, moby) on a defined point; (b) what the sixth does with a line now (its live line, its define row); (c) a sentence with a point that
# has no definition rows: is it defined by anyone, within 20 s; (d) a symbol the encoder has never seen, typed as define : X: its gate, its
# DNA rows, its definition rows, its sheet, the sixth's lines; (e) the page's own reads for a point (node rows, memory rows) through the door.
import socket, json, time, urllib.request, sys
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=900); s.sendall((req + "\n").encode()); b = b""
    while not b.endswith(b"\n"): b += s.recv(1 << 20)
    s.close(); return json.loads(b.decode())
def q(sql):
    r = ask("q " + sql); return r.get("rows", r)
def text(run, schema="main"): return q("SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM %s.seq s JOIN %s.label l ON l.gate = s.gate WHERE s.run = %d ORDER BY s.pos)" % (schema, schema, run))[0][0]
def gate(w):
    r = q("SELECT gate FROM main.label WHERE symbol = '%s'" % w); return r[0][0] if r else None
print("=== (a) returns of stone (924), one per source, first 260 chars:")
seen = set()
for (nid, src, run) in q("SELECT id, source, run FROM main.node WHERE gate = 924 ORDER BY id"):
    if src in seen: continue
    seen.add(src); print("  source", src, q("SELECT symbol FROM main.label WHERE gate = %d" % src), "run", run, "|", text(run)[:260])
print("=== (a2) a wn return with pointers, full:", text(19934921)[:700])
print("=== (b) the sixth: its newest told lines:")
for l in ask("newest sixth 6").get("lines", [])[:6]: print("  ", l)
print("   the sixth's define row on main:", q("SELECT gate, shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = 156"))
print("   born (16) rows:", q("SELECT gate, shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = 16"), "sixth (5) rows:", q("SELECT gate, shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = 5"))
print("=== (c) a sentence with hancock (gate 506885, 0 definition rows):")
st0 = ask("stats"); r = ask("type main the hancock is here"); print("   typed:", {k: r.get(k) for k in ("run", "hits", "born", "seconds")}, "out:", [str(o)[:80] for o in r.get("out", [])][:6])
time.sleep(20)
st1 = ask("stats"); print("   after 20 s: hancock node rows", q("SELECT count(*) FROM main.node WHERE gate = 506885")[0][0], "| runs +%d, defined +%d, returns +%d | sixth runs +%d" % (st1["main"]["runs"] - st0["main"]["runs"], st1["main"]["defined"] - st0["main"]["defined"], st1["main"]["returns"] - st0["main"]["returns"], st1["sixth"]["runs"] - st0["sixth"]["runs"]))
print("   the sixth's newest told lines now:", [(l["run"], l["text"][:60]) for l in ask("newest sixth 4").get("lines", [])])
print("   sheet of the line:", json.load(urllib.request.urlopen("http://localhost:8058/api/run?schema=main&id=%d" % r["run"])).get("cells"))
print("=== (d) a symbol the encoder has never seen: define : zorblaxen")
print("   before: gate", gate("zorblaxen"), "| labels", st1["main"]["gates"])
st0 = ask("stats"); r = ask("type main define : zorblaxen"); print("   typed:", {k: r.get(k) for k in ("run", "hits", "born", "seconds")}, "out:", [str(o)[:100] for o in r.get("out", [])][:8])
time.sleep(5)
g = gate("zorblaxen"); st1 = ask("stats")
print("   after: gate", g, "| labels +%d, runs +%d, defined +%d, returns +%d, sixth runs +%d" % (st1["main"]["gates"] - st0["main"]["gates"], st1["main"]["runs"] - st0["main"]["runs"], st1["main"]["defined"] - st0["main"]["defined"], st1["main"]["returns"] - st0["main"]["returns"], st1["sixth"]["runs"] - st0["sixth"]["runs"]))
if g:
    print("   its DNA rows:", q("SELECT gate, shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = %d" % g))
    print("   its node rows:", q("SELECT count(*) FROM main.node WHERE gate = %d" % g)[0][0], "| neuron:", q("SELECT gate, born, arrived, nodes, memories, shards FROM main.neuron WHERE gate = %d" % g))
d = json.load(urllib.request.urlopen("http://localhost:8058/api/run?schema=main&id=%d" % r["run"]))
print("   tree:", [(t["id"], t["kind"], t["arrival"], (t.get("text") or "")[:50]) for t in d["tree"]][:12])
print("   cells:", str(d.get("cells"))[:500])
print("   the sixth's newest:", [(l["run"], l["text"][:60]) for l in ask("newest sixth 4").get("lines", [])])
print("=== (e) the page's reads for stone through the door:")
def door_q(sql, params=[]):
    rq = urllib.request.Request("http://localhost:8058/api/q", data=json.dumps({"sql": sql, "params": params}).encode(), headers={"Content-Type": "application/json"})
    j = json.load(urllib.request.urlopen(rq, timeout=120)); return (len(j.get("rows", [])), j.get("error"))
print("   node rows:", door_q("SELECT id, source, run FROM main.node WHERE gate = 924 ORDER BY id"))
print("   memory rows:", door_q("SELECT run, shard, at, input FROM main.run_memory WHERE gate = ? ORDER BY run DESC LIMIT 60", [924]))
print("   born-in:", door_q("SELECT run FROM main.run_sheet WHERE cell = ? AND value = ? ORDER BY run LIMIT 1", [21, "924"]))
print("   rel rows of stone:", q("SELECT count(*) FROM main.rel WHERE gate = 924"), q("SELECT kind, other, run FROM main.rel WHERE gate = 924 LIMIT 5"), "kinds in rel:", q("SELECT l.symbol, count(*) FROM main.rel r JOIN main.label l ON l.gate = r.kind GROUP BY r.kind ORDER BY 2 DESC LIMIT 12"))
