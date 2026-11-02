#!/usr/bin/env python3
# bind5.py PORT: the recipe's bind of define's (the sixth, :) shard can run before that shard exists, so on a small kernel it may hold no call.
# On the big kernel it holds the define formula. This puts the small kernel in the big kernel's state before the test.
import socket, json, sys
P = int(sys.argv[1])
def ask(r, t=60):
    s = socket.create_connection(("127.0.0.1", P), timeout=t); s.settimeout(t); s.sendall((r + "\n").encode()); b = b""
    while not b.endswith(b"\n"): b += s.recv(1 << 20)
    s.close(); return json.loads(b.decode())
def q(sql): return ask("q " + sql).get("rows") or []
g = q("SELECT gate FROM label WHERE symbol = 'define'")[0][0]; c = q(f"SELECT call FROM dna WHERE gate = {g} AND before = 1 AND trigger = 68")[0][0]
ask(f"type main BUILD UPDATE dna SET call = {c} WHERE gate = {g} AND before = 5 AND trigger = 68 ; BUILD")
print(P, "define shards", q(f"SELECT before, trigger, call FROM dna WHERE gate = {g} AND trigger = 68 AND before IN (1, 5)"))
