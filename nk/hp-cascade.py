#!/usr/bin/env python3
# hp-cascade.py N K: a snapshot first (the journal and the snapshot in step), then K rounds of 'define unknown : N' with the dedupe, a snapshot every 10 rounds, memory watched
import socket, json, subprocess, time, sys
N, K = int(sys.argv[1]), int(sys.argv[2])
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
def rss(): return int(subprocess.run(["bash", "-c", "ps -o rss= -C nk"], capture_output=True, text=True).stdout.strip() or 0) // 1024
def snap(): return subprocess.run(["bash", "run-on-hp.sh", "snapshot"], capture_output=True, text=True).stdout.strip().split("\n")[-1]
print(snap())
st0 = ask("stats")["main"]; r0 = rss(); T0 = time.time()
print("start:", {k: st0[k] for k in ("runs", "receipts", "deduped_runs", "gates", "shards")}, "rss", r0, "waiting", q("SELECT count(*) FROM sixth.spawned WHERE sent = 0")[0][0], "defined", q("SELECT count(DISTINCT gate) FROM node")[0][0])
for k in range(1, K + 1):
    t = time.time(); ask(f"type main define unknown : {N}"); st = ask("stats")["main"]
    print(f"round {k:2d}: {time.time() - t:5.1f} s | runs {st['runs']} receipts {st['receipts']} deduped {st['deduped_runs']} gates {st['gates']} | rss {rss()} MB | waiting {q('SELECT count(*) FROM sixth.spawned WHERE sent = 0')[0][0]} | refused {st['refused']}")
    if rss() > 5200: print("memory past 5.2 GB; stopping the rounds"); break
    if k % 10 == 0: print("  ", snap())
st = ask("stats")["main"]; r1 = rss(); n = st["runs"] - st0["runs"]
print(f"{K * N} defines asked in {time.time() - T0:.0f} s; memory {r0} -> {r1} MB = {(r1 - r0) / (K * N):.2f} MB a define; receipts stored {st['receipts'] - st0['receipts']} of {st['hops'] - st0['hops']} hops ({100 * (1 - (st['receipts'] - st0['receipts']) / max(1, st['hops'] - st0['hops'])):.0f}% repeated)")
print("defined words (with definition rows):", q("SELECT count(DISTINCT gate) FROM node")[0][0], "| node rows by source:", q("SELECT (SELECT symbol FROM label WHERE gate = n.source), count(*) FROM node n GROUP BY n.source"))
print("relationship rows:", q("SELECT count(*) FROM rel")[0][0], "| mutual like pairs:", q("SELECT count(*) FROM rel a JOIN rel b ON a.gate = b.other AND a.other = b.gate AND a.gate < b.gate")[0][0], "| guesses:", q("SELECT count(*) FROM guess.guesses")[0][0], "| why asks:", q("SELECT count(*) FROM sixth.asked")[0][0])
print("memory rows:", q("SELECT count(*), sum(again) FROM run_memory")[0], "| the most ticked:", [(r[0], r[1][:30]) for r in q("SELECT m.again, (SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM seq s JOIN label l ON l.gate = s.gate WHERE s.run = m.run ORDER BY s.pos)) FROM run_memory m ORDER BY m.again DESC LIMIT 5")])
p = ask("profile 4"); [print("  %7.2f s %6d x %8.0f us  %s" % (t["s"], t["n"], t["us"], t["text"][:100])) for t in p["top"]]
print(snap())
