#!/usr/bin/env python3
# guess_out.py (2026-10-31): takes the guessing brain out of define and why, at the owner's word. usage: guess_out.py PORT
# It uses the kernel's own way: it reads the formula each shard is bound to from the brain, cuts the one span that touches the guessing
# brain, types the line that is left at the prompt, and rebinds the shard. No kernel code changes, no rows are deleted: the guessing
# brain stays attached, every guess it ever made stays where it is, and the old runs stay in the brain so the old binding can be put back.
import socket, json, sys, re
PORT = int(sys.argv[1])

def ask(req, t=300):
    s = socket.create_connection(("127.0.0.1", PORT), timeout=t); s.settimeout(t); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())

def q(sql): return ask("q " + sql).get("rows") or []
def text_of(run): return q(f"SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM seq s JOIN label l ON l.gate = s.gate WHERE s.run = {run} ORDER BY s.pos)")[0][0]

SPAN = re.compile(r"\s*BUILD INSERT (?:OR IGNORE )?INTO guess\.(?:corpus|inbox)\b.*?; BUILD")

def relay(name, befores):
    gate = q(f"SELECT gate FROM label WHERE symbol = '{name}'")[0][0]
    old = {b: q(f"SELECT call FROM dna WHERE gate = {gate} AND before = {b} AND trigger = 68") for b in befores}
    calls = {r[0][0] for r in old.values() if r and r[0][0]}  # a shard with no call is left as it is
    if len(calls) != 1: sys.exit(f"{name}: expected one formula on the shards, found {old}")
    call = calls.pop(); text = text_of(call)
    if not text or "guess." not in text: print(f"{name}: run {call} does not touch the guessing brain; nothing to do"); return
    new, n = SPAN.subn("", text)
    if n != 1 or "guess." in new or new.count("BUILD") % 2 or not new.startswith("BUILD"): sys.exit(f"{name}: run {call}: the cut is not clean ({n} spans, {new.count('BUILD')} BUILD); nothing typed")
    print(f"{name}: run {call}, {len(text)} symbols of text, cut to {len(new)}")
    r = ask("type main " + new); run = r.get("run")
    if not run: sys.exit(f"{name}: the line was not taken: {str(r)[:300]}")
    back = text_of(run)
    if back != new: sys.exit(f"{name}: run {run} does not read back as typed; not bound")
    for b in old:
        if old[b] and old[b][0][0]: ask(f"type main BUILD UPDATE dna SET call = {run} WHERE gate = {gate} AND before = {b} AND trigger = 68 ; BUILD")
    now = {b: q(f"SELECT call FROM dna WHERE gate = {gate} AND before = {b} AND trigger = 68") for b in befores}
    print(f"{name}: new run {run}, shards now {now}")
    if any(old[b] and old[b][0][0] and now[b][0][0] != run for b in old): sys.exit(f"{name}: a shard did not take the new run")

relay("define", (1, 5))
relay("why", (5,))
print("refused", ask("stats")["main"]["refused"])
