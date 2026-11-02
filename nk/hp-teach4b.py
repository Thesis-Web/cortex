#!/usr/bin/env python3
import socket, json, subprocess, time
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
def text6(run): r = q(f"SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM sixth.seq s JOIN sixth.label l ON l.gate = s.gate WHERE s.run = {run} ORDER BY s.pos)"); return r[0][0] if r and r[0][0] else ''
print("the sweep's reply the first time:", text6(q("SELECT id FROM sixth.run WHERE parent = 7506 AND kind = 3 ORDER BY id LIMIT 1")[0][0])[:100])
print("the sixth's error replies after the new observing line was bound (runs > 7539):", [(n, text6(r)[:80]) for (n, r) in q("SELECT count(*), min(id) FROM sixth.run WHERE id > 7539 AND kind = 3 AND arrival = 4 AND id IN (SELECT run FROM sixth.seq WHERE pos = 1 AND gate = (SELECT gate FROM sixth.label WHERE symbol = 'error')) GROUP BY (SELECT group_concat(gate, ' ') FROM (SELECT gate FROM sixth.seq WHERE run = sixth.run.id ORDER BY pos))")])
print(subprocess.run(["bash", "run-on-hp.sh", "type", "TEACH-4b-nk.txt"], capture_output=True, text=True).stdout.strip()[-100:])
for l in open("out/LEDGER-TEACH-4b-nk.md", encoding="utf-8"):
    if l.startswith("| 1 |"): print("   ", " | ".join(x.strip()[:90] for x in l.split("|")[1:11]))
print("after the sweep: by sent flag", q("SELECT sent, count(*) FROM sixth.spawned GROUP BY sent"), "| capitalized rel rows", q("SELECT count(*) FROM rel WHERE kind = (SELECT gate FROM label WHERE symbol = 'capitalized')")[0][0])
print("a few:", [(a, b) for a, b in q("SELECT (SELECT symbol FROM label WHERE gate = r.gate), (SELECT symbol FROM label WHERE gate = r.other) FROM rel r WHERE r.kind = (SELECT gate FROM label WHERE symbol = 'capitalized') ORDER BY r.rowid LIMIT 12")])
t = time.time(); r = ask("type main define unknown : 50"); print("50 defines: %.1f s" % (time.time() - t), "| waiting now", q("SELECT count(*) FROM sixth.spawned WHERE sent = 0")[0][0], "| handled as forms", q("SELECT count(*) FROM sixth.spawned WHERE sent = 3")[0][0])
print("the 50 it defined:", [s for (s,) in q("SELECT l.symbol FROM sixth.spawned p JOIN label l ON l.gate = p.gate WHERE p.sent = 1 ORDER BY p.id DESC LIMIT 50")][::-1])
print("waiting, capitalized, with a lowercase point (should be 0):", q("SELECT count(*) FROM sixth.spawned p JOIN label l ON l.gate = p.gate WHERE p.sent = 0 AND l.symbol GLOB '[A-Z]*' AND EXISTS (SELECT 1 FROM label x WHERE x.symbol = lower(l.symbol))")[0][0])
print(subprocess.run(["bash", "run-on-hp.sh", "snapshot"], capture_output=True, text=True).stdout.strip().split("\n")[-1])
