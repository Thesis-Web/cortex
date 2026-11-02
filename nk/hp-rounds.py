#!/usr/bin/env python3
# hp-rounds.py N K: K rounds of 'define unknown : N' on the kernel, timed; what the brain defined, the relationships laid, the guesses; a snapshot at the end
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
def q(sql): r = ask("q " + sql); return r.get("rows", r)
def rss(): return int(subprocess.run(["bash", "-c", "ps -o rss= -C nk"], capture_output=True, text=True).stdout.strip() or 0) // 1024
st0 = ask("stats")["main"]; print("before:", {k: st0[k] for k in ("runs", "gates", "shards", "receipts", "paste_us", "return_us")}, "rss MB", rss(), "| waiting:", q("SELECT count(*) FROM sixth.spawned WHERE sent = 0")[0][0])
T0 = time.time()
for k in range(K):
    t = time.time(); r = ask(f"type main define unknown : {N}")
    st = ask("stats")["main"]
    print(f"round {k+1}: {N} defines in {time.time() - t:.1f} s; runs {st['runs']}, gates {st['gates']}, shards {st['shards']}, receipts {st['receipts']}; paste {st['paste_us']:.0f} us mean, return {st['return_us']:.0f} us; rss {rss()} MB; waiting {q('SELECT count(*) FROM sixth.spawned WHERE sent = 0')[0][0]}")
print(f"{N*K} defines in {time.time() - T0:.1f} s")
sym = dict(q("SELECT gate, symbol FROM label"))
print("\nthe brain's own defines, in order (what: returns, known, unknown):")
rows = q("SELECT t.run, (SELECT value FROM run_sheet WHERE run = t.run AND cell = 23), (SELECT count(*) FROM run r WHERE r.parent = t.run AND r.kind = 3 AND r.arrival IN (7,8,10,11,12,13,14,(SELECT gate FROM label WHERE symbol = 'wikt'))), (SELECT value FROM run_sheet WHERE run = t.run AND cell = (SELECT gate FROM label WHERE symbol = 'known')), (SELECT value FROM run_sheet WHERE run = t.run AND cell = (SELECT gate FROM label WHERE symbol = 'unknown')) FROM third t WHERE t.run IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'define')) ORDER BY t.id")
line = []
for (run, what, ret, known, unknown) in rows:
    line.append(f"{sym.get(int(what), what) if what else '?'}({ret}r {len(known.split()) if known else 0}k {len(unknown.split()) if unknown else 0}u)")
print("  ", " ".join(line[:120]))
print("\nnodes (definition rows) per source:", q("SELECT (SELECT symbol FROM label WHERE gate = n.source), count(*) FROM node n GROUP BY n.source"))
print("neurons with definition rows:", q("SELECT count(DISTINCT gate) FROM node")[0][0], "| rel rows:", q("SELECT count(*) FROM rel")[0][0], "by kind:", [(sym.get(k, k), c) for (k, c) in q("SELECT kind, count(*) FROM rel GROUP BY kind")])
print("a few relationships:", [(sym.get(g, g), sym.get(k, k), sym.get(o, o)) for (g, k, o) in q("SELECT gate, kind, other FROM rel ORDER BY run DESC LIMIT 12")])
print("mutual pairs (like both ways):", q("SELECT count(*) FROM rel a JOIN rel b ON a.gate = b.other AND a.other = b.gate AND a.gate < b.gate")[0][0])
print("guesses:", q("SELECT word, guess, printf('%.2f', confidence), printf('%.2f', belief), used FROM guess.guesses ORDER BY id DESC LIMIT 10"))
print("asked (why) rows:", q("SELECT count(*) FROM sixth.asked")[0][0], "| open cells on the user's lines:", q("SELECT count(*) FROM run_sheet s JOIN run r ON r.id = s.run WHERE r.kind = 0 AND r.arrival = 1 AND s.state = 0")[0][0])
print("scans:", [(x["table"], x["scanned"]) for x in ask("scans") if x["scanned"]])
p = ask("profile 5"); [print(f"   {t['s']:7.3f} s {t['n']:5d} x {t['us']:9.0f} us  {t['text'][:110]}") for t in p['top']]
print(subprocess.run(["bash", "run-on-hp.sh", "snapshot"], capture_output=True, text=True).stdout.strip()[-300:])
