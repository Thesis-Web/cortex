#!/usr/bin/env python3
# hp-fullpoints.py: how many points are fully defined (every one of their definition rows fully known), then more rounds while memory allows
import socket, json, collections, subprocess, time, sys
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
defined = {g for (g,) in q("SELECT DISTINCT gate FROM node")}
rows = q("SELECT n.gate, n.source, n.run FROM node n")
missing = collections.defaultdict(int); rows_of = collections.Counter(); dict_rows_of = collections.Counter(); dict_full_of = collections.Counter()
WIKT = q("SELECT gate FROM label WHERE symbol = 'wikt'")[0][0]
for i in range(0, len(rows), 400):
    chunk = rows[i:i+400]; seqs = collections.defaultdict(list)
    for r, g in q("SELECT run, gate FROM seq WHERE run IN (%s) ORDER BY run, pos" % ",".join(str(r) for (_, _, r) in chunk)): seqs[r].append(g)
    for (g, src, r) in chunk:
        gs = seqs.get(r, []); need = sum(1 for x in gs if x > 80 and x not in defined); rows_of[g] += 1; missing[g] += need
        if src in (7, 8, WIKT): dict_rows_of[g] += 1; dict_full_of[g] += (need == 0)
full = [g for g in rows_of if missing[g] == 0]; dict_full = [g for g in dict_rows_of if dict_full_of[g] == dict_rows_of[g]]
sym = dict(q("SELECT gate, symbol FROM label WHERE gate IN (%s)" % ",".join(str(g) for g in (full + dict_full)[:200]))) if (full or dict_full) else {}
print(f"points with definition rows {len(rows_of)}; fully defined (every row of every source fully known) {len(full)}: {[sym.get(g) for g in full[:30]]}")
print(f"points whose dictionary rows (WordNet, GCIDE, Wiktionary) are all fully known: {len(dict_full)}: {[sym.get(g) for g in dict_full[:30]]}")
print(f"points by undefined symbols across their rows: 0: {len(full)}, 1-10: {sum(1 for g in rows_of if 0 < missing[g] <= 10)}, 11-100: {sum(1 for g in rows_of if 10 < missing[g] <= 100)}, more: {sum(1 for g in rows_of if missing[g] > 100)}")
K = int(sys.argv[1]) if len(sys.argv) > 1 else 0
if K:
    t0 = time.time(); r0 = rss()
    for k in range(K):
        t = time.time(); ask("type main define unknown : 50"); st = ask("stats")["main"]; m = rss()
        print(f"round {k+1:2d}: {time.time()-t:4.1f} s | defined points {q('SELECT count(DISTINCT gate) FROM node')[0][0]} | waiting {q('SELECT count(*) FROM sixth.spawned WHERE sent = 0')[0][0]} | rss {m} MB")
        if m > 6200: print("memory near the box's limit; stopping"); break
    print(f"{(k+1)*50} defines in {time.time()-t0:.0f} s; rss {r0} -> {rss()} MB")
    print(subprocess.run(["bash", "run-on-hp.sh", "snapshot"], capture_output=True, text=True).stdout.strip().split("\n")[-1])
