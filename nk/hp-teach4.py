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
print("before: waiting", q("SELECT count(*) FROM sixth.spawned WHERE sent = 0")[0][0], "| capitalized among them", q("SELECT count(*) FROM sixth.spawned p JOIN label l ON l.gate = p.gate WHERE p.sent = 0 AND l.symbol GLOB '[A-Z]*'")[0][0], "| of those with a lowercase point", q("SELECT count(*) FROM sixth.spawned p JOIN label l ON l.gate = p.gate WHERE p.sent = 0 AND l.symbol GLOB '[A-Z]*' AND EXISTS (SELECT 1 FROM label x WHERE x.symbol = lower(l.symbol))")[0][0])
print(subprocess.run(["bash", "run-on-hp.sh", "type", "TEACH-4-nk.txt"], capture_output=True, text=True).stdout.strip()[-160:])
for l in open("out/LEDGER-TEACH-4-nk.md", encoding="utf-8"):
    if l.startswith("| ") and l[2].isdigit(): print("   ", " | ".join(x.strip()[:70] for x in l.split("|")[1:11]))
print("after the sweep: by sent flag", q("SELECT sent, count(*) FROM sixth.spawned GROUP BY sent"), "| capitalized rel rows", q("SELECT count(*) FROM rel WHERE kind = (SELECT gate FROM label WHERE symbol = 'capitalized')")[0][0])
print("a few:", [(a, b) for a, b in q("SELECT (SELECT symbol FROM label WHERE gate = r.gate), (SELECT symbol FROM label WHERE gate = r.other) FROM rel r WHERE r.kind = (SELECT gate FROM label WHERE symbol = 'capitalized') ORDER BY r.rowid DESC LIMIT 10")])
print("capitalized defined:", q("SELECT (SELECT symbol FROM label WHERE gate = n.source), count(*) FROM node n WHERE n.gate = (SELECT gate FROM label WHERE symbol = 'capitalized') GROUP BY n.source"))
t = time.time(); r = ask("type main define unknown : 50"); print("50 defines: %.1f s" % (time.time() - t), "| waiting now", q("SELECT count(*) FROM sixth.spawned WHERE sent = 0")[0][0], "| handled as forms", q("SELECT count(*) FROM sixth.spawned WHERE sent = 3")[0][0], "| the sixth's errors in this round:", q("SELECT count(*) FROM sixth.run WHERE kind = 3 AND arrival = 4 AND id > (SELECT max(id) - 400 FROM sixth.run) AND id IN (SELECT run FROM sixth.seq WHERE pos = 1 AND gate = (SELECT gate FROM sixth.label WHERE symbol = 'error'))")[0][0])
print("the 50 it defined:", [s for (s,) in q("SELECT l.symbol FROM sixth.spawned p JOIN label l ON l.gate = p.gate WHERE p.sent = 1 ORDER BY p.id DESC LIMIT 50")][::-1])
print(subprocess.run(["bash", "run-on-hp.sh", "snapshot"], capture_output=True, text=True).stdout.strip().split("\n")[-1])
