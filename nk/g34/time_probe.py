#!/usr/bin/env python3
# g34/time_probe.py (2026-11-01). Where a recall's time goes, from the kernel's own counters (stats before and after one typed line), its
# profile request, and the runs under the line; then a point this brain has never defined, so the long way is seen to run.
import socket, json, time, urllib.request, sys
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=900); s.sendall((req + "\n").encode()); b = b""
    while not b.endswith(b"\n"): b += s.recv(1 << 20)
    s.close(); return json.loads(b.decode())
def q(sql): return ask("q " + sql)["rows"]
def get(u): return json.load(urllib.request.urlopen("http://localhost:8058" + u, timeout=900))
KEYS = ("hops", "hop_s", "pastes", "paste_s", "returns", "return_s", "receipts", "hops_run", "runs", "deduped_runs")
def delta(a, b): return {k: (round(b[k] - a[k], 4) if isinstance(a[k], float) else b[k] - a[k]) for k in KEYS if k in a and k in b}
def line(text):
    s0 = ask("stats"); t0 = time.time(); r = ask("type main " + text); w = time.time() - t0; s1 = ask("stats")
    print("TYPED", repr(text), "kernel_s", r.get("seconds"), "hits", r.get("hits"), "wall_s", round(w, 3))
    print("   main delta", delta(s0["main"], s1["main"]))
    print("   sixth delta", delta(s0["sixth"], s1["sixth"]))
    d = get("/api/run?schema=main&id=%d" % r["run"])
    for t in d["tree"]: print("   run", t["id"], "kind", t["kind"], "from", t["arrival"], "hops", t["hops"], "same_as", t["same_as"], "|", (t.get("text") or "")[:70])
    return r, d
line("define : bread")
print("PROFILE", json.dumps(ask("profile"))[:1800])
# a point never defined here: rarer words
pick = None
for w in ("zymurgy", "quokka", "gudgeon", "ocarina", "kumquat", "isthmus", "haiku", "tungsten", "sprocket", "flange", "yurt", "theodolite", "gnomon", "pipette", "spelunker", "umiak", "quinsy", "xebec", "zarf", "ziggurat", "wombat", "numbat", "echidna", "pangolin", "axolotl", "capybara", "okapi", "tapir", "marmoset", "ptarmigan"):
    gg = q("SELECT gate FROM main.label WHERE symbol = '%s'" % w)
    n = q("SELECT count(*) FROM main.node WHERE gate = %d" % gg[0][0])[0][0] if gg else None
    if gg and n == 0: pick = (w, gg[0][0]); print("candidate", w, "gate", gg[0][0], "node rows 0"); break
    if not gg and pick is None: pick = (w, None)
    print("candidate", w, "gate", gg[0][0] if gg else None, "node rows", n)
if pick is None: print("no undefined candidate found"); sys.exit(0)
w, g = pick
s0 = ask("stats")["main"]
r, d = line("define : " + w)
if g is None:
    gg = q("SELECT gate FROM main.label WHERE symbol = '%s'" % w); g = gg[0][0] if gg else None
t0 = time.time()
while True:
    d = get("/api/run?schema=main&id=%d" % r["run"])
    if d["run"].get("ended") or time.time() - t0 > 600: break
    time.sleep(0.1)
cells = {c[0]: c for c in d["cells"]}; defc = cells.get(24)
rets = [x for x in d["tree"] if x["kind"] == 3]
print("LEARNED", json.dumps({"word": w, "gate": g, "run": r["run"], "kernel_s": r.get("seconds"), "hits": r.get("hits"), "tree_runs": d["tree_runs"], "returns": len(rets), "returns_about_it": len([x for x in rets if x["about"] == g]), "sources": sorted(set(x["arrival"] for x in rets)), "node_after": q("SELECT count(*) FROM main.node WHERE gate = %d" % g)[0][0] if g else None, "def_text": (defc[3]["text"][:100] if defc and defc[3] else None), "known_n": len(cells[150][2].split()) if cells.get(150) and cells[150][2] else 0, "unknown_n": len(cells[155][2].split()) if cells.get(155) and cells[155][2] else 0, "ok": (cells.get(91) or [None, None, None])[2], "complete": d["run"]["complete"]}))
s1 = ask("stats")["main"]
print("stats delta after learning: runs +%d, defined +%d, returns +%d, shard_rows %d -> %d" % (s1["runs"] - s0["runs"], s1["defined"] - s0["defined"], s1["returns"] - s0["returns"], s0["shard_rows"], s1["shard_rows"]))
# and the same word again: the recall of what it just learned
time.sleep(1.0)
r2, d2 = line("define : " + w)
cells = {c[0]: c for c in d2["cells"]}; defc = cells.get(24)
print("RECALLED", json.dumps({"word": w, "run": r2["run"], "kernel_s": r2.get("seconds"), "hits": r2.get("hits"), "tree_runs": d2["tree_runs"], "returns": len([x for x in d2["tree"] if x["kind"] == 3 and x["about"] == g]), "node_after": q("SELECT count(*) FROM main.node WHERE gate = %d" % g)[0][0] if g else None, "def_text": (defc[3]["text"][:100] if defc and defc[3] else None), "ok": (cells.get(91) or [None, None, None])[2], "complete": d2["run"]["complete"]}))
