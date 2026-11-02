#!/bin/bash
# hp-dedupe-check.sh: the kernel with the dedupe, fresh: the sixty lines, export, then the big brain back from its snapshot
cd ~/nk; cp out/typed.txt out/typed-big.txt
bash run-on-hp.sh fresh 2>&1 | tail -2
python3 - <<'PY'
import socket, json
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
st = ask("stats"); print("fresh sixty lines:", {k: st["main"][k] for k in ("runs", "hops", "receipts", "deduped_runs", "shards", "gates")}, "| sixth", {k: st["sixth"][k] for k in ("runs", "receipts", "deduped_runs")})
print(ask("export /home/james/nk/out/expD"))
print("memory rows:", ask("q SELECT count(*), sum(again) FROM run_memory")["rows"], "| runs ended:", ask("q SELECT count(*) FROM run WHERE ended = 1")["rows"], "| repeated:", ask("q SELECT count(*) FROM run WHERE same_as IS NOT NULL")["rows"])
print("the most repeated:", [(r[0], r[1][:40]) for r in ask("q SELECT m.again, (SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM seq s JOIN label l ON l.gate = s.gate WHERE s.run = m.run ORDER BY s.pos)) FROM run_memory m ORDER BY m.again DESC LIMIT 5")["rows"]])
print("remember still finds the earlier line (define : who twice):", ask("q SELECT run, value FROM run_sheet WHERE cell = 27 AND run IN (SELECT run FROM input ORDER BY id DESC LIMIT 60) AND value <> '0' LIMIT 6")["rows"])
PY
# the big brain back, with the journal lines typed since its snapshot
mv out/typed-big.txt out/typed.txt
rm -f out/snap-latest; ln -s $(ls -d out/snap-2026* | sort | tail -1 | xargs basename) out/snap-latest; echo "snapshot to resume: $(readlink out/snap-latest)"
bash run-on-hp.sh resume 2>&1 | tail -3
python3 - <<'PY'
import socket, json
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
st = ask("stats"); print("big brain back:", {k: st["main"][k] for k in ("runs", "receipts", "deduped_runs", "gates", "pending")})
PY
