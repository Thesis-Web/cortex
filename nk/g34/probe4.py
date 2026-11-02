#!/usr/bin/env python3
# g34/probe4.py (2026-11-01, 18:05): what birth does today (the born row calls run 1), the markers Wiktionary and Webster returns carry, the
# gates of the bracket symbols, the sixth's live line (what it does with a define's unknowns).
import socket, json
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=900); s.sendall((req + "\n").encode()); b = b""
    while not b.endswith(b"\n"): b += s.recv(1 << 20)
    s.close(); return json.loads(b.decode())
def q(sql, schema="main"):
    r = ask("q " + sql); return r.get("rows", r)
def text(run, schema="main"): return q("SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM %s.seq s JOIN %s.label l ON l.gate = s.gate WHERE s.run = %d ORDER BY s.pos)" % (schema, schema, run))[0][0]
print("=== run 1 (born's call), full:"); print(text(1))
print("=== runs 2..6, first 200 chars each:")
for i in range(2, 7): print("  run", i, "|", (text(i) or "")[:200])
print("=== gates:", {s: q("SELECT gate FROM main.label WHERE symbol = '%s'" % s) for s in ("[", "]", "{", "}", ";", ",", "to", "newgate", "wikt", "capitalized", "like", "opposite")})
print("=== wikt returns of river (3393) with markers:")
n = 0
for (nid, src, run) in q("SELECT id, source, run FROM main.node WHERE gate = 3393 ORDER BY id"):
    if src != 443: continue
    t = text(run) or ""
    if "[" in t: print("  run", run, "|", t[:420]); n += 1
    if n >= 4: break
print("=== wikt returns of know (26) with synonyms/antonyms:")
n = 0
for (nid, src, run) in q("SELECT id, source, run FROM main.node WHERE gate = 26 ORDER BY id"):
    if src != 443: continue
    t = text(run) or ""
    if "synonym" in t or "antonym" in t or "hypernym" in t: print("  run", run, "|", t[:420]); n += 1
    if n >= 3: break
print("=== gcide returns of river, two longest:")
rows = [(len(text(run) or ""), run) for (nid, src, run) in q("SELECT id, source, run FROM main.node WHERE gate = 3393 ORDER BY id") if src == 8]
for L, run in sorted(rows, reverse=True)[:2]: print("  run", run, "|", (text(run) or "")[:400])
print("=== mwt and map returns of know:")
for (nid, src, run) in q("SELECT id, source, run FROM main.node WHERE gate = 26 ORDER BY id"):
    if src in (10, 12): print("  source", src, "run", run, "|", (text(run) or "")[:200])
print("=== the sixth's live line 2792575, first 1600 chars:"); print((text(2792575, "sixth") or "")[:1600])
print("=== the sixth's DNA rows on gate 92 and the spawned table:", q("SELECT gate, shard, before, trigger, call, spawn, times FROM sixth.dna WHERE gate = 92"), q("SELECT count(*) FROM sixth.spawned"), q("SELECT count(*) FROM sixth.spawned WHERE sent = 0"))
