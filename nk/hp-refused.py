#!/usr/bin/env python3
# hp-refused.py: the burst of refused landings traced: which gates, which runs, did the births fail
import socket, json, collections
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
print("refused rows:", q("SELECT count(*) FROM refused")[0][0], "| first:", q("SELECT id, text, error FROM refused ORDER BY id LIMIT 3"), "| last:", q("SELECT id, text FROM refused ORDER BY id DESC LIMIT 2"))
rows = q("SELECT text FROM refused ORDER BY id LIMIT 3000")
gates = collections.Counter(int(t.split("gate ")[1]) for (t,) in rows); runs = collections.Counter(int(t.split()[2]) for (t,) in rows)
print("distinct gates refused (first 3000):", len(gates), "most:", gates.most_common(4), "| distinct runs:", len(runs))
g = gates.most_common(1)[0][0]
print("that gate:", q(f"SELECT gate, symbol FROM label WHERE gate = {g}"), "its row:", q(f"SELECT born, arrived, nodes, shards FROM neuron WHERE gate = {g}"))
r = runs.most_common(1)[0][0]
print("a refusing run:", q(f"SELECT id, arrival, parent, kind, cell, about, same_as, ended FROM run WHERE id = {r}"), "| text:", q(f"SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM seq s JOIN label l ON l.gate = s.gate WHERE s.run = {r} ORDER BY s.pos)")[0][0][:120])
print("its receipts:", q(f"SELECT pos, gate, shard, via FROM run_receipt WHERE run = {r} ORDER BY id LIMIT 10"))
par = q(f"SELECT parent FROM run WHERE id = {r}")[0][0]
print("born runs under the same parent:", q(f"SELECT id, same_as, ended, (SELECT value FROM run_sheet WHERE run = r.id AND cell = 22) AS reply FROM run r WHERE parent = {par} AND kind = 1 LIMIT 6") if par else None)
print("gates with a label but no region:", q("SELECT count(*) FROM neuron WHERE born = 0")[0][0], "e.g.", q("SELECT n.gate, l.symbol FROM neuron n JOIN label l ON l.gate = n.gate WHERE n.born = 0 LIMIT 6"))
print("runs with no end:", q("SELECT count(*) FROM run WHERE ended = 0")[0][0], "| the newest without an end:", q("SELECT id, arrival, kind, same_as FROM run WHERE ended = 0 ORDER BY id DESC LIMIT 4"))
print("stats:", {k: v for k, v in ask("stats")["main"].items() if k in ("runs", "refused", "deduped_runs", "pending", "receipts")})
