#!/usr/bin/env python3
# g34/recall_check.py (2026-11-01). The owner: "if you ask define : ??? <-- insert anyword that has a full known definition, it should respond
# with that definition at runtime speed... if it doesn't something is likely incorrect... check on about 10 words and report back".
# Each word: its gate, its definition rows before, the typed define through the door, the time until the run ended, what the run did
# (hops, runs under it, returns from sources), what landed on its sheet, its definition rows after. Read live; nothing is a test.
import json, urllib.request, time, sys
D = "http://localhost:8058"
def get(u): return json.loads(urllib.request.urlopen(D + u, timeout=600).read())
def post(u, o):
    r = urllib.request.Request(D + u, data=json.dumps(o).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=600).read())
def q(sql, params=[]): return post("/api/q", {"sql": sql, "params": params})
def one(sql, params=[]):
    r = q(sql, params); return r["rows"][0] if r.get("rows") else None
words = sys.argv[1:] or "hinge know truth water house river stone bread horse tree".split()
st0 = get("/api/stats")["main"]; print("before: runs", st0["runs"], "defined", st0["defined"], "returns", st0["returns"], flush=True)
unk = one("SELECT gate FROM main.label WHERE symbol = 'unknown'")[0]; okg = one("SELECT gate FROM main.label WHERE symbol = 'ok'")[0]
print("gate unknown", unk, "gate ok", okg)
def n_of(c): return len((c[2] or "").split()) if c and c[2] else 0
for w in words:
    g = one("SELECT gate FROM main.label WHERE symbol = ?", [w]); g = g[0] if g else None
    if not g: print(w, "no gate", flush=True); continue
    n0 = one("SELECT count(*) FROM main.node WHERE gate = ?", [g])[0]
    t0 = time.time(); r = post("/api/type", {"line": "define : " + w}); t1 = time.time()
    run = (r.get("result") or {}).get("run"); err = r.get("error")
    if not run: print(w, g, n0, "TYPE FAILED", err, json.dumps(r)[:300], flush=True); continue
    while True:
        d = get("/api/run?schema=main&id=%d" % run)
        if d["run"].get("ended") or time.time() - t0 > 600: break
        time.sleep(0.05)
    t2 = time.time()
    n1 = one("SELECT count(*) FROM main.node WHERE gate = ?", [g])[0]
    tree = d["tree"]; rets = [x for x in tree if x["kind"] == 3 and x["about"] == g]
    srcs = sorted(set(x["arrival"] for x in rets))
    cells = {c[0]: c for c in d["cells"]}
    defc = cells.get(24); known = cells.get(150)
    print(json.dumps({"word": w, "gate": g, "run": run, "node_before": n0, "node_after": n1, "door_s": round(t1 - t0, 3), "ended_s": round(t2 - t0, 3),
                      "hops": d["run"]["hops"], "tree_runs": d["tree_runs"], "returns_about_it": len(rets), "sources": srcs,
                      "def_cell": defc[2] if defc else None, "def_text": (defc[3]["text"][:90] if defc and defc[3] else None),
                      "known_n": n_of(known), "unknown_n": n_of(cells.get(unk)), "ok": (cells.get(okg) or [None, None, None])[2],
                      "ended": d["run"]["ended"], "complete": d["run"]["complete"], "same_as": d["run"]["same_as"]}), flush=True)
st1 = get("/api/stats")["main"]; print("after: runs", st1["runs"], "defined", st1["defined"], "returns", st1["returns"], flush=True)
