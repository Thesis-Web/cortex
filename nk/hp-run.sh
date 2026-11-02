#!/bin/bash
# hp-run.sh: rebuild the kernel, type the sixty lines, export, profile, start the door, check it end to end (run on hp from ~/nk)
cd ~/nk
pkill -x nk; pkill -f serve8.py; sleep 0.5
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -I. -o nk nk.c nkvt.c nkio.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | head -5
(nohup ./nk 7007 egg-symbols.txt sources > nk.log 2>&1 &); sleep 1; cat nk.log
time python3 nkbottom.py 7007 --lines LINES-nk.txt --ledger out/LEDGER-nk-60-lines.md --quiet 2>&1 | tail -1 | cut -c1-500
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
print(ask("export /home/james/nk/out"))
p = ask("profile 12"); print("pastes profiled:", p["texts"], "texts, total", p["total_s"], "s")
for t in p["top"]: print(f"  {t['s']:7.3f} s  {t['n']:5d} x {t['us']:9.0f} us  {t['text'][:150]}")
print("receipts id > 48600:", ask("q SELECT count(*) FROM run_receipt WHERE id > 48600"), "run 7:", ask("q SELECT count(*) FROM run_receipt WHERE run = 7"))
PY
(nohup python3 serve8.py 8058 7007 NEURON-POINT-OF-CONNECTION-nk-2026-10-30.html LINES-nk.txt FIRST-RUNS-nk.txt > door.log 2>&1 &); sleep 1; cat door.log
echo "--- door checks"
curl -s localhost:8058/api/info | cut -c1-300; echo
echo -n "graph bytes: "; curl -s "localhost:8058/api/graph?schema=main" | wc -c
curl -s localhost:8058/api/lines | python3 -c 'import sys, json; d = json.load(sys.stdin); L = d["lines"]; print(len(L), "lines listed; line 1:", L[0]["line"][:60], "run", L[0]["run"], "| line 13 run:", L[12]["run"], "| first-runs lines:", sum(1 for x in L if x["file"] == "first"))'
curl -s -X POST localhost:8058/api/q -H "content-type: application/json" -d '{"sql": "SELECT id, source, run FROM main.node WHERE gate = (SELECT gate FROM main.label WHERE symbol = '"'"'who'"'"') ORDER BY id"}' | cut -c1-200; echo
curl -s -X POST localhost:8058/api/type -H "content-type: application/json" -d '{"line": "print dna : who", "prompt": "main"}' | python3 -c 'import sys, json; j = json.load(sys.stdin); r = j["result"]; print("typed through the door:", {k: r[k] for k in ("schema", "run", "runs", "hits", "born", "seconds")}); [print("   ", o) for o in r["out"][:8]]'
echo -n "page bytes: "; curl -s localhost:8058/ | wc -c
