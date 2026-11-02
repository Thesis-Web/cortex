#!/usr/bin/env python3
# inspect31.py: reads two small kernels side by side, to see why their chains differ. Reads only.
import socket, json, sys
def ask(port, req, t=30):
    s = socket.create_connection(("127.0.0.1", port), timeout=t); s.settimeout(t); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(port, sql): return ask(port, "q " + sql).get("rows") or []
for p in map(int, sys.argv[1:]):
    st = ask(p, "stats"); m, x = st["main"], st["sixth"]
    print("== port", p, "main runs", m["runs"], "hops", m["hops"], "pending", m["pending"], "| sixth runs", x["runs"], "pending", x["pending"], "refused", m["refused"], x["refused"])
    print("spawned", q(p, "SELECT sent, count(*) FROM sixth.spawned GROUP BY sent"), "asked", q(p, "SELECT count(*) FROM sixth.asked"))
    print("define shards", q(p, "SELECT before, trigger, call, times FROM dna WHERE gate = (SELECT gate FROM label WHERE symbol = 'define')"))
    print("why shards", q(p, "SELECT before, trigger, call, times FROM dna WHERE gate = (SELECT gate FROM label WHERE symbol = 'why')"))
    print("seen shards", q(p, "SELECT before, trigger, call, times FROM sixth.dna WHERE gate = (SELECT gate FROM sixth.label WHERE symbol = 'seen')"))
    print("lines from the sixth", q(p, "SELECT count(*) FROM main.run WHERE arrival = 5 AND kind = 0"), "typed", q(p, "SELECT count(*) FROM main.run WHERE arrival = 1 AND kind = 0"))
    txt = "(SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM main.seq s JOIN main.label l ON l.gate = s.gate WHERE s.run = r.id ORDER BY s.pos))"
    print("newest from the sixth", [str(t)[:40] for (t,) in q(p, f"SELECT {txt} FROM main.run r WHERE r.arrival = 5 AND r.kind = 0 ORDER BY r.id DESC LIMIT 6")])
    print("first from the sixth", [str(t)[:40] for (t,) in q(p, f"SELECT {txt} FROM main.run r WHERE r.arrival = 5 AND r.kind = 0 ORDER BY r.id LIMIT 6")])
    print("open cells on the newest top runs", q(p, "SELECT s.run, s.cell, s.state FROM main.run_sheet s WHERE s.state = 0 ORDER BY s.run DESC LIMIT 6"))

txt = "(SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM main.seq s JOIN main.label l ON l.gate = s.gate WHERE s.run = r.id ORDER BY s.pos))"
a, b = [[t for (t,) in q(int(p), f"SELECT {txt} FROM main.run r WHERE r.arrival = 5 AND r.kind = 0 AND {txt} LIKE 'define%' ORDER BY r.id")] for p in sys.argv[1:3]]
i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), None)
print("defines sent by the sixth: control", len(a), "changed", len(b), "same set", set(a) == set(b), "same order", a == b, "first difference at", i, (a[i], b[i]) if i is not None else "")
