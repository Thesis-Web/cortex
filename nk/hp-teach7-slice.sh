#!/bin/bash
# hp-teach7-slice.sh (2026-10-31): a second kernel on port 7008 with the slice sources; the sixty lines, the teaching files in order, then
# TEACH-7 (the observing line without the sweep), then one define typed; watch: is a (run, cell) asked once, does the chain send one define
# per define seen, does the stack come back to zero, does the whole-graph read answer on a cut brain (the read that killed the big kernel).
cd ~/nk; rm -rf out/t7; mkdir -p out/t7/src; rm -f sources-slice/*.db-journal; cp sources-slice/*.db out/t7/src/; bash carry-src.sh out/t7/src > /dev/null
pkill -f "nk 7008" 2>/dev/null; sleep 0.5
(NK_JOURNAL=out/t7/typed.txt nohup ./nk 7008 egg-symbols.txt out/t7/src wn gcide mw mwt moby map sqldoc measured guess > out/t7/nk.log 2>&1 &)
for i in $(seq 1 60); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 7008), timeout=1).close()" 2>/dev/null && break; sleep 1; done
for f in LINES-nk.txt TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt GUESS-LINE-nk.txt TEACH-5-nk.txt TEACH-8-nk.txt; do
  echo "-- $f: $(python3 nkbottom.py 7008 --lines $f --ledger out/t7/LEDGER-$(basename $f .txt).md --quiet | tail -1 | cut -c1-160)"
done
python3 - <<'PY'
import socket, json, time
def ask(req, t=120):
    s = socket.create_connection(("127.0.0.1", 7008), timeout=t); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return buf.decode().strip()
def q(sql): return json.loads(ask("q " + sql)).get("rows")
def snap(tag):
    st = json.loads(ask("stats")); m = st["main"]
    print("%-14s runs %7d pending %6d refused %d | asked %s (distinct run,cell %s) | sends %s waiting %s | defined %s" % (tag, m["runs"], m["pending"], m["refused"],
        q("SELECT count(*) FROM sixth.asked")[0][0], q("SELECT count(*) FROM (SELECT DISTINCT run, cell FROM sixth.asked)")[0][0],
        q("SELECT count(*) FROM sixth.spawned WHERE sent = 1")[0][0], q("SELECT count(*) FROM sixth.spawned WHERE sent = 0")[0][0], q("SELECT count(DISTINCT gate) FROM main.node")[0][0]))
print("seen's call in the sixth:", q("SELECT call FROM sixth.dna WHERE gate = (SELECT gate FROM sixth.label WHERE symbol = 'seen') AND before = 6 AND trigger = 68"))
snap("before")
t = time.time(); r = json.loads(ask("type main define : the")); print("the define typed: %.2f s, runs %d, out cells %d" % (time.time() - t, r["runs"], len(r.get("out", []))))
for i in range(9):
    time.sleep(10); snap("+%ds" % ((i + 1) * 10))
print("lines told to main since the define, in order:", [r[0] for r in (q("SELECT (SELECT group_concat(l.symbol, ) FROM main.seq s JOIN main.label l ON l.gate = s.gate WHERE s.run = r.id) FROM main.run r WHERE r.arrival = 5 AND r.kind = 0 AND r.id > 944 ORDER BY r.id") or [["(no rows)"]])][:40])
print("asked rows (run, cell):", q("SELECT run, cell, sent FROM sixth.asked ORDER BY id"))
t = time.time(); g = ask("graph main"); print("graph main answered: %d bytes in %.2f s (the read that killed the big kernel)" % (len(g), time.time() - t))
print("stubs:", json.loads(ask("stats"))["main"]["stubs"])
PY
pkill -f "nk 7008"; echo "second kernel stopped"
