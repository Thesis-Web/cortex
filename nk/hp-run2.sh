#!/bin/bash
cd ~/nk; pkill -x nk; pkill -f serve8.py; sleep 0.5
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -I. -o nk nk.c nkvt.c nkio.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | head -5
(nohup ./nk 7007 egg-symbols.txt sources > nk.log 2>&1 &); sleep 1; cat nk.log
python3 nkbottom.py 7007 --lines LINES-nk.txt --ledger out/LEDGER-nk-60-lines.md --quiet 2>&1 | tail -1 | cut -c1-300
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
print("scans after the sixty lines:"); [print("  ", r) for r in ask("scans")]
for name, sql in [("shape", "SELECT h.call FROM hit h WHERE h.gate = 1 AND h.before = 1 AND h.next IS 2 AND h.call IS NOT NULL ORDER BY h.id DESC LIMIT 1"),
                  ("know", "SELECT count(*) FROM seq s WHERE s.run = 7 AND EXISTS (SELECT 1 FROM run r JOIN run_memory m ON m.run = r.id WHERE r.kind = 3 AND r.about = s.gate)"),
                  ("remember", "SELECT max(m.run) FROM run_memory m WHERE m.run < 700 AND m.input = (SELECT group_concat(gate, ' ') FROM (SELECT gate FROM seq WHERE run = 700 ORDER BY pos))"),
                  ("bind", "UPDATE dna SET call = 1 WHERE gate = 16 AND before IS NULL AND trigger IS NULL"),
                  ("node", "SELECT n.id, n.source, n.run FROM node n WHERE n.gate = 81 ORDER BY n.id"),
                  ("history", "SELECT id, run, gate, shard FROM run_receipt WHERE id > 48600 ORDER BY id"),
                  ("sixth asked", "SELECT s.run, s.cell FROM main.run_sheet s WHERE s.state = 0")]:
    r = ask("q EXPLAIN QUERY PLAN " + sql); print(f"  {name:12s}", " / ".join(row[3] for row in r["rows"]))
PY
(nohup python3 serve8.py 8058 7007 NEURON-POINT-OF-CONNECTION-nk-2026-10-30.html LINES-nk.txt FIRST-RUNS-nk.txt 0.0.0.0 > door.log 2>&1 &); sleep 1; cat door.log
