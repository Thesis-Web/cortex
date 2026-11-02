#!/usr/bin/env python3
# hp-teach2.py: type TEACH-2 (why searches harder; the sixth watches the brain's own lines), then read what filled
import socket, json, subprocess
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): r = ask("q " + sql); return r.get("rows", r)
def text(run): r = q(f"SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM seq s JOIN label l ON l.gate = s.gate WHERE s.run = {run} ORDER BY s.pos)"); return r[0][0] if r and r[0][0] else ''
runs0 = ask("stats")["main"]["runs"]; third0 = q("SELECT count(*) FROM third")[0][0]
print(subprocess.run(["bash", "run-on-hp.sh", "type", "TEACH-2-nk.txt"], capture_output=True, text=True).stdout.strip()[-200:])
for l in open("out/LEDGER-TEACH-2-nk.md", encoding="utf-8"):
    if l.startswith("| ") and l[2].isdigit(): print("   ", " | ".join(x.strip() for x in l.split("|")[1:10]))
sym = dict(q("SELECT gate, symbol FROM label"))
errs = q(f"SELECT count(*), min(id) FROM run WHERE kind = 3 AND arrival = 4 AND id > {runs0} AND id IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'error')) GROUP BY (SELECT group_concat(gate, ' ') FROM (SELECT gate FROM seq WHERE run = run.id ORDER BY pos))")
print("mother's errors among the new runs:", [(n, text(r)[:90]) for (n, r) in errs])
print("why lines the sweep sent:", q("SELECT count(*) FROM third")[0][0] - third0)
rows = q(f"SELECT t.run, (SELECT value FROM run_sheet WHERE run = t.run AND cell = 23), (SELECT state FROM run_sheet WHERE run = t.run AND cell = 24), (SELECT value FROM run_sheet WHERE run = t.run AND cell = 24) FROM third t WHERE t.run <= {runs0} AND t.run IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'define')) ORDER BY t.id")
print("the brain's own defines whose definition came late or never (word: def cell now, the run that filled it and where it arrived from):")
shown = 0
for (run, w, st, v) in rows:
    src_returns = q(f"SELECT count(*) FROM run r WHERE r.parent = {run} AND r.kind = 3 AND r.arrival IN (7,8,10,11,12,13,14,(SELECT gate FROM label WHERE symbol = 'wikt'))")[0][0]
    late = q(f"SELECT count(*) FROM run r WHERE r.parent = {run} AND r.kind = 3 AND r.id > {runs0}")[0][0]
    if late or st == 0:
        src = q(f"SELECT (SELECT symbol FROM label WHERE gate = arrival) FROM run WHERE id = {int(v)}")[0][0] if v and str(v).isdigit() else None
        print(f"   {sym.get(int(w), w)!r}: def {'filled' if st == 1 else 'EMPTY'}{' by run ' + str(v) + ' from ' + str(src) if v else ''}; source returns {src_returns}, of them late {late}"); shown += 1
    if shown >= 24: break
print("guesses now:", q("SELECT word, guess, printf('%.2f', confidence), printf('%.2f', belief) FROM guess.guesses ORDER BY id DESC LIMIT 14"))
print("stats:", {k: v for k, v in ask("stats")["main"].items() if k in ("runs", "gates", "receipts", "pending")})
print(subprocess.run(["bash", "run-on-hp.sh", "door"], capture_output=True, text=True).stdout.strip()[-120:])
