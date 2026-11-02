#!/usr/bin/env python3
# hp-unknowns.py: the state of the unknowns on the kernel: how many wait, how many were sent and defined, what the frontier is made of
import socket, json, collections, re
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
st = ask("stats")["main"]
print("kernel:", {k: st[k] for k in ("runs", "receipts", "deduped_runs", "gates", "shards", "pending", "refused")})
sp = q("SELECT sent, count(*) FROM sixth.spawned GROUP BY sent"); print("spawned (the sixth's unknowns): by sent flag", sp, "| typed defines by the owner's lines:", q("SELECT count(*) FROM input WHERE run IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'define'))")[0][0])
print("points with definition rows:", q("SELECT count(DISTINCT gate) FROM node")[0][0], "| define runs that ended with def filled / empty / no end:", q("SELECT sum(CASE WHEN s.state = 1 THEN 1 ELSE 0 END), sum(CASE WHEN s.state = 0 THEN 1 ELSE 0 END), sum(CASE WHEN r.ended = 0 THEN 1 ELSE 0 END) FROM run r JOIN run_sheet s ON s.run = r.id AND s.cell = 24 WHERE r.kind = 0 AND r.id IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'define'))")[0])
rows = q("SELECT l.symbol, p.shared FROM sixth.spawned p JOIN label l ON l.gate = p.gate WHERE p.sent = 0")
syms = [r[0] for r in rows]; shared = [r[1] for r in rows]
cap = sum(1 for s in syms if s[:1].isupper()); non = sum(1 for s in syms if not re.match(r'^[A-Za-z]+$', s)); short = sum(1 for s in syms if len(s) <= 2)
print(f"waiting unknowns {len(syms)}: capitalized {cap} ({100*cap/len(syms):.0f}%), not plain letters {non}, one or two letters {short}")
hist = collections.Counter(min(s, 10) for s in shared); print("how many unknown lists name each waiting point (1..10+):", sorted(hist.items()))
top = q("SELECT l.symbol, p.shared FROM sixth.spawned p JOIN label l ON l.gate = p.gate WHERE p.sent = 0 ORDER BY p.shared DESC, p.id LIMIT 40"); print("the most shared waiting:", [(s, n) for s, n in top])
sent = q("SELECT l.symbol FROM sixth.spawned p JOIN label l ON l.gate = p.gate WHERE p.sent = 1 ORDER BY p.id LIMIT 60"); print("the first sixty the brain defined on its own:", [s for (s,) in sent])
print("definition rows by source:", q("SELECT (SELECT symbol FROM label WHERE gate = n.source), count(*), count(DISTINCT n.gate) FROM node n GROUP BY n.source"))
print("known over all symbols in the newest 20 defines (how much of a definition is already defined):", [(k, u) for (k, u) in q("SELECT length((SELECT value FROM run_sheet WHERE run = t.run AND cell = (SELECT gate FROM label WHERE symbol = 'known'))) - length(replace((SELECT value FROM run_sheet WHERE run = t.run AND cell = (SELECT gate FROM label WHERE symbol = 'known')), ' ', '')) + 1, length((SELECT value FROM run_sheet WHERE run = t.run AND cell = (SELECT gate FROM label WHERE symbol = 'unknown'))) - length(replace((SELECT value FROM run_sheet WHERE run = t.run AND cell = (SELECT gate FROM label WHERE symbol = 'unknown')), ' ', '')) + 1 FROM third t WHERE t.run IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'define')) ORDER BY t.id DESC LIMIT 20")])
print("guesses:", q("SELECT count(*) FROM guess.guesses")[0][0], "| the newest guesses:", q("SELECT word, guess, printf('%.2f', confidence) FROM guess.guesses ORDER BY id DESC LIMIT 8"))
print("relationship rows:", q("SELECT count(*) FROM rel")[0][0], "| mutual like pairs:", q("SELECT count(*) FROM rel a JOIN rel b ON a.gate = b.other AND a.other = b.gate AND a.gate < b.gate")[0][0])
