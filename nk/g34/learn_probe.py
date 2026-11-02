#!/usr/bin/env python3
# g34/learn_probe.py (2026-11-01). After the recall lines: (1) the kernel's own time for a recall, read from its type reply, not the door;
# (2) a point this brain has never defined, typed define : X, to see the long way still runs: the sources asked, returns landed, node rows laid.
import socket, json, time, urllib.request, sys
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=900); s.sendall((req + "\n").encode()); b = b""
    while not b.endswith(b"\n"): b += s.recv(1 << 20)
    s.close(); return json.loads(b.decode())
def q(sql): return ask("q " + sql)["rows"]
def get(u): return json.load(urllib.request.urlopen("http://localhost:8058" + u, timeout=900))
def run_report(word, g, run, t0):
    while True:
        d = get("/api/run?schema=main&id=%d" % run)
        if d["run"].get("ended") or time.time() - t0 > 600: break
        time.sleep(0.05)
    t2 = time.time()
    tree = d["tree"]; rets = [x for x in tree if x["kind"] == 3]
    cells = {c[0]: c for c in d["cells"]}
    n1 = q("SELECT count(*) FROM main.node WHERE gate = %d" % g)[0][0] if g else None
    defc = cells.get(24)
    print(json.dumps({"word": word, "gate": g, "run": run, "ended_s": round(t2 - t0, 3), "hops": d["run"]["hops"], "tree_runs": d["tree_runs"],
                      "returns": len(rets), "returns_about_it": len([x for x in rets if x["about"] == g]), "sources": sorted(set(x["arrival"] for x in rets)),
                      "node_after": n1, "def_cell": defc[2] if defc else None, "def_text": (defc[3]["text"][:100] if defc and defc[3] else None),
                      "known_n": len((cells.get(150) or [0, 0, ""])[2].split()) if cells.get(150) and cells[150][2] else 0,
                      "unknown_n": len((cells.get(155) or [0, 0, ""])[2].split()) if cells.get(155) and cells[155][2] else 0,
                      "ok": (cells.get(91) or [None, None, None])[2], "complete": d["run"]["complete"]}), flush=True)
# (1) a recall, timed by the kernel itself
for w in ("stone", "river"):
    g = q("SELECT gate FROM main.label WHERE symbol = '%s'" % w)[0][0]
    t0 = time.time(); r = ask("type main define : %s" % w)
    print("KERNEL", w, {k: r.get(k) for k in ("run", "hits", "born", "seconds", "refused")}, "socket_wall_s", round(time.time() - t0, 3), "out", [o for o in r.get("out", []) if o[2] in ("def", "say", "reply")][:3], flush=True)
    run_report(w, g, r["run"], t0)
# (2) a point never defined here
pick = None
for w in ("lantern", "saddle", "anvil", "quartz", "pebble", "harbor", "walnut", "kettle", "meadow", "copper", "gazebo", "trellis", "ferrule", "oarlock", "bobbin"):
    gg = q("SELECT gate FROM main.label WHERE symbol = '%s'" % w)
    n = q("SELECT count(*) FROM main.node WHERE gate = %d" % gg[0][0])[0][0] if gg else None
    print("candidate", w, "gate", gg[0][0] if gg else None, "node rows", n, flush=True)
    if gg and n == 0: pick = (w, gg[0][0]); break
    if not gg and pick is None: pick = (w, None)
if pick is None: print("no undefined candidate found"); sys.exit(0)
w, g = pick
st0 = ask("stats")["main"]
t0 = time.time(); r = ask("type main define : %s" % w)
print("KERNEL", w, {k: r.get(k) for k in ("run", "hits", "born", "seconds", "refused")}, "socket_wall_s", round(time.time() - t0, 3), flush=True)
if g is None:
    gg = q("SELECT gate FROM main.label WHERE symbol = '%s'" % w); g = gg[0][0] if gg else None
run_report(w, g, r["run"], t0)
st1 = ask("stats")["main"]
print("stats delta: runs +%d, defined +%d, returns +%d, shard_rows %d -> %d" % (st1["runs"] - st0["runs"], st1["defined"] - st0["defined"], st1["returns"] - st0["returns"], st0["shard_rows"], st1["shard_rows"]))
