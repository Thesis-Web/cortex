#!/usr/bin/env python3
# g34/read_runs.py (2026-11-01): the texts of the runs the next lines must follow exactly, and the bundle's own cost at the kernel.
import socket, json, time, sys
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=900); s.sendall((req + "\n").encode()); b = b""
    while not b.endswith(b"\n"): b += s.recv(1 << 20)
    s.close(); return b
def askj(req): return json.loads(ask(req).decode())
def q(sql): return askj("q " + sql)["rows"]
def text(run): return q("SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM main.seq s JOIN main.label l ON l.gate = s.gate WHERE s.run = %d ORDER BY s.pos)" % run)[0][0]
print("=== run 6459431 (the live define run) in full:"); print(text(6459431))
print("=== run 7 (heard's call):"); print(text(7)[:1200])
print("=== heard's DNA rows:", q("SELECT gate, shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = 1"))
print("=== replays under the recall define : bread (19936565):", q("SELECT parent, source, kind FROM main.replay WHERE parent = 19936565"), q("SELECT parent, source, kind FROM main.replay WHERE parent = 19936570"))
t = time.time(); n = q("SELECT count(*) FROM main.hit WHERE gate = 156")[0][0]; print("=== hits ever on define (gate 156):", n, "read in %.3f s" % (time.time() - t))
t = time.time(); n = q("SELECT count(*) FROM main.hit WHERE gate = 424")[0][0]; print("=== hits ever on print (gate 424):", n, "read in %.3f s" % (time.time() - t))
t = time.time(); b = ask("bundle 2000"); dt = time.time() - t
d = json.loads(b.decode()); print("=== bundle 2000 at the kernel: %.1f s, %.1f MB" % (dt, len(b) / 1e6), {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in d.items() if k != "T"}, "counts", d.get("counts"))
