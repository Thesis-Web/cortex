#!/bin/bash
# hp-agree-slice.sh: the agreement configuration on a second kernel (port 7008): tries/19's slice sources (mw attached, no wikt), the sixty lines, an export
cd ~/nk; rm -rf out/agree; mkdir -p out/agree; rm -f sources-slice/*.db-journal
mkdir -p out/agree/src; cp sources-slice/*.db out/agree/src/; bash carry-src.sh out/agree/src > /dev/null
pkill -f "nk 7008" 2>/dev/null; sleep 0.5
(NK_JOURNAL=out/agree/typed.txt nohup ./nk 7008 egg-symbols.txt out/agree/src wn gcide mw mwt moby map sqldoc measured guess > out/agree/nk.log 2>&1 &)
for i in $(seq 1 60); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 7008), timeout=1).close()" 2>/dev/null && break; sleep 1; done
python3 nkbottom.py 7008 --lines LINES-nk.txt --ledger out/agree/LEDGER-agree-60.md --quiet | tail -1 | cut -c1-260
python3 - <<'PY'
import socket, json
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7008)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
print(ask("export /home/james/nk/out/agree/exp"))
print("errors from mother in this run:", ask("q SELECT count(*) FROM run WHERE kind = 3 AND arrival = 4 AND id IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'error'))")["rows"])
PY
pkill -f "nk 7008"; echo "second kernel stopped"
