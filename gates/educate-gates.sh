#!/bin/bash
# educate-gates.sh (2026-11-02 22:2x, tries/38): a fresh scratch brain on hp2, port 7009, its own map file, educated with the same line files in the same order as the Cortex brain (educate.sh). Never touches the Cortex kernel on 7007 (no pkill) nor hp.
set -u
cd ~/cortex/gates/kernel
B=$HOME/cortex/gates/brain; mkdir -p $B/ledgers
P=7009
rm -f $B/brain.map $B/brain.map.*
SOURCES="wn gcide mwt moby map sqldoc measured guess wikt"
(NK_MAP=$B/brain.map nohup ./nk $P egg-symbols.txt ../sources $SOURCES > $B/nk.log 2>&1 < /dev/null &)
for i in $(seq 1 60); do python3 -c "import socket; socket.create_connection((127.0.0.1,$P),timeout=1).close()" 2>/dev/null && break; sleep 1; done
cat $B/nk.log
ask(){ python3 - "$1" "$P" <<'PY'
import socket, json, sys
s = socket.create_connection(("127.0.0.1", int(sys.argv[2])), timeout=3600); s.sendall((sys.argv[1] + "\n").encode()); b = b""
while True:
    d = s.recv(1 << 20)
    if not d: break
    b += d
    if b.endswith(b"\n"): break
print(b.decode().strip()[:700])
PY
}
t(){ f=$1; L=$B/ledgers/LEDGER-$(basename $f .txt).md; echo "=== $f $(date +%T)"; python3 nkbottom.py $P --lines $f --ledger $L --quiet > $B/ledgers/$(basename $f .txt).out 2>&1; echo "typed $(grep -c '^| [0-9]' $L) lines, refused $(grep -c '| refused |' $L) ($(date +%T))"; grep '| refused |' $L | cut -c1-160 | head -5; ask stats | cut -c1-260; }
t LINES-nk.txt
echo "=== wikt born"; ask "type main wikt" | cut -c1-200
G=$(ask "q SELECT gate FROM main.label WHERE symbol = 'wikt'" | python3 -c "import sys, json; print(json.load(sys.stdin)['rows'][0][0])")
echo "wikt gate $G"; ask "q UPDATE wikt.me SET gate = $G"; echo "wikt.me now: $(ask "q SELECT gate FROM wikt.me")"
for f in TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt TEACH-5-nk.txt TEACH-6-nk.txt TEACH-7-nk.txt TEACH-8-nk.txt RECALL-nk.txt RECALL-2-nk.txt SHAPE-nk.txt RECALL-3-nk.txt REBIND-nk.txt RECALL-5-nk.txt BORN-nk.txt RELMAP-nk.txt RECALL-6-nk.txt RECALL-7-nk.txt FORMULA-nk.txt REBIND-g35-nk.txt SHAPE-2-nk.txt; do t $f; done
echo "=== DONE $(date +%T)"
