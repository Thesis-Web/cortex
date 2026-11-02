#!/usr/bin/env python3
# hp-graphcheck.py: the page's graph bundle against the kernel's own tables (is the drawing's data the brain's data?)
import socket, json
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
g = ask("graph main")
print("graph bundle: dna rows", len(g["dna"]), "| the shards counter", q("SELECT n FROM shards")[0][0], "| dna rows read by SQL", q("SELECT count(*) FROM dna")[0][0])
print("graph bundle: neurons with a region", g["tables"], "| by SQL", q("SELECT count(*) FROM neuron WHERE born = 1")[0][0], "| rel rows", len(g["rel"]), "by SQL", q("SELECT count(*) FROM rel")[0][0], "| memory gates", len(g["mem"]), "| first-gate map", len(g["first"]), "| runs", q("SELECT count(*) FROM run")[0][0])
row = g["dna"][12345]; print("a dna row of the bundle", row, "| the same shard by SQL", q("SELECT gate, shard, before, trigger, call, spawn, times FROM dna WHERE gate = %d AND shard = %d" % (row[0], row[1])))
print("gates born but never landed on (no shard, drawn at origin by the page's rule):", q("SELECT count(*) FROM neuron n WHERE n.born = 1 AND NOT EXISTS (SELECT 1 FROM dna d WHERE d.gate = n.gate)")[0][0], "| gates with one shard:", q("SELECT count(*) FROM (SELECT gate FROM dna GROUP BY gate HAVING count(*) = 1)")[0][0])
