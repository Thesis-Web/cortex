#!/usr/bin/env python3
# g34/probe2.py (2026-11-01): type each line given, wait until its run ended, and print what the kernel reports: its own seconds and hits,
# the runs under it, the source returns, the node rows of the point named after ":", the sheet (def, known, unknown, know, remember, shape, ok).
import socket, json, time, urllib.request, sys
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=900); s.sendall((req + "\n").encode()); b = b""
    while not b.endswith(b"\n"):
        d = s.recv(1 << 20)
        if not d: raise SystemExit("the kernel closed the socket (gone?)")
        b += d
    s.close(); return json.loads(b.decode())
def q(sql): return ask("q " + sql)["rows"]
def get(u): return json.load(urllib.request.urlopen("http://localhost:8058" + u, timeout=900))
for text in sys.argv[1:]:
    parts = text.split(" : ", 1); word = parts[1].strip() if len(parts) == 2 else None
    gg = q("SELECT gate FROM main.label WHERE symbol = '%s'" % word) if word else []
    g = gg[0][0] if gg else None
    n0 = q("SELECT count(*) FROM main.node WHERE gate = %d" % g)[0][0] if g else None
    s0 = ask("stats")["main"]
    t0 = time.time(); r = ask("type main " + text); w = time.time() - t0
    if "error" in r: print("REFUSED", text, r); continue
    run = r["run"]
    while True:
        d = get("/api/run?schema=main&id=%d" % run)
        if d["run"].get("ended") or time.time() - t0 > 900: break
        time.sleep(0.05)
    t_end = time.time() - t0
    if g is None and word:
        gg = q("SELECT gate FROM main.label WHERE symbol = '%s'" % word); g = gg[0][0] if gg else None
    n1 = q("SELECT count(*) FROM main.node WHERE gate = %d" % g)[0][0] if g else None
    s1 = ask("stats")["main"]
    rets = [x for x in d["tree"] if x["kind"] == 3]
    src = [x for x in rets if 7 <= x["arrival"] <= 15 or x["arrival"] > 29]
    cells = {c[0]: c for c in d["cells"]}
    def val(c): return cells[c][2] if cells.get(c) else None
    defc = cells.get(24)
    out = [o for o in r.get("out", []) if o[2] in ("def", "say", "reply")]
    print(json.dumps({"typed": text, "run": run, "kernel_s": r.get("seconds"), "hits": r.get("hits"), "born": r.get("born"), "ended_s": round(t_end, 3),
                      "tree_runs": d["tree_runs"], "returns": len(rets), "source_returns": len(src), "sources": sorted(set(x["arrival"] for x in src)),
                      "errors": [x.get("text", "")[:80] for x in rets if str(x.get("text", "")).startswith("error")],
                      "gate": g, "node_before": n0, "node_after": n1, "def_text": (defc[3]["text"][:110] if defc and defc[3] else None),
                      "known_n": len(val(150).split()) if val(150) else 0, "unknown_n": len(val(155).split()) if val(155) else 0,
                      "know": val(26), "remember": val(27), "shape": val(28), "ok": val(91), "complete": d["run"]["complete"],
                      "stats_delta": {k: (round(s1[k] - s0[k], 4) if isinstance(s0[k], float) else s1[k] - s0[k]) for k in ("hops", "hop_s", "pastes", "paste_s", "returns", "return_s", "runs", "defined")},
                      "out": [str(o[3])[:120] for o in out[:2]]}), flush=True)
