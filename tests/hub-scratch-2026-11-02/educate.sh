#!/bin/bash
# educate.sh (2026-11-02): a fresh Cortex brain on hp2, educated with hp's own line files in the order hp's ledgers show. Build time, once.
set -u
cd ~/cortex/nk
B=$HOME/cortex/brain; mkdir -p $B/ledgers
pkill -x nk; sleep 1
rm -f $B/brain.map $B/brain.map.*
SOURCES="wn gcide mwt moby map sqldoc measured guess wikt"
(NK_MAP=$B/brain.map nohup ./nk 7007 egg-symbols.txt sources $SOURCES > $B/nk.log 2>&1 < /dev/null &)
for i in $(seq 1 60); do python3 -c "import socket; socket.create_connection(('127.0.0.1',7007),timeout=1).close()" 2>/dev/null && break; sleep 1; done
cat $B/nk.log
ask(){ python3 - "$1" <<'PY'
import socket, json, sys
s = socket.create_connection(("127.0.0.1", 7007), timeout=3600); s.sendall((sys.argv[1] + "\n").encode()); b = b""
while True:
    d = s.recv(1 << 20)
    if not d: break
    b += d
    if b.endswith(b"\n"): break
print(b.decode().strip()[:700])
PY
}
t(){ f=$1; L=$B/ledgers/LEDGER-$(basename $f .txt).md; echo "=== $f $(date +%T)"; python3 nkbottom.py 7007 --lines $f --ledger $L --quiet > $B/ledgers/$(basename $f .txt).out 2>&1; echo "typed $(grep -c '^| [0-9]' $L) lines, refused $(grep -c '| refused |' $L) ($(date +%T))"; grep '| refused |' $L | cut -c1-160 | head -5; ask stats | cut -c1-260; }
t LINES-nk.txt
echo "=== wikt born"; ask "type main wikt" | cut -c1-200
G=$(ask "q SELECT gate FROM main.label WHERE symbol = 'wikt'" | python3 -c "import sys, json; print(json.load(sys.stdin)['rows'][0][0])")
echo "wikt gate $G"; ask "q UPDATE wikt.me SET gate = $G"; echo "wikt.me now: $(ask "q SELECT gate FROM wikt.me")"
for f in TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt TEACH-5-nk.txt TEACH-6-nk.txt TEACH-7-nk.txt TEACH-8-nk.txt RECALL-nk.txt RECALL-2-nk.txt SHAPE-nk.txt RECALL-3-nk.txt REBIND-nk.txt RECALL-5-nk.txt BORN-nk.txt RELMAP-nk.txt RECALL-6-nk.txt RECALL-7-nk.txt FORMULA-nk.txt REBIND-g35-nk.txt SHAPE-2-nk.txt; do t $f; done
echo "=== DONE $(date +%T)"
