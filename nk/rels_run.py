#!/usr/bin/env python3
# g34/rels_run.py (2026-11-01): drives the kernel's `rels N` pass over the defined points, N a call, until done; prints each call's own report.
import socket, json, time, sys
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=3600); s.sendall((req + "\n").encode()); b = b""
    while not b.endswith(b"\n"):
        d = s.recv(1 << 20)
        if not d: raise SystemExit("the kernel closed the socket (gone?)")
        b += d
    s.close(); return json.loads(b.decode())
t0 = time.time(); tot = {"points": 0, "already_had": 0, "returns_read": 0, "rows_laid": 0}; calls = 0
while True:
    r = ask("rels %d" % N); calls += 1
    if "error" in r: print("ERROR", r); break
    for k in tot: tot[k] += r.get(k, 0)
    print("call %d: gates %d..%d of %d, points %d (had %d), returns %d, rows %d, %.1f s" % (calls, r["from_gate"], r["next_gate"], r["gates"], r["points"], r["already_had"], r["returns_read"], r["rows_laid"], r["seconds"]), flush=True)
    if r.get("done"): break
print("DONE in %.0f s:" % (time.time() - t0), tot, flush=True)
st = ask("stats")["main"]; print("stats: refused", st["refused"], "pending", st["pending"], "runs", st["runs"])
