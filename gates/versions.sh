#!/bin/bash
cd ~/cortex/gates/kernel
echo "VERSIONS (tries/38, read live on hp2 $(date "+%F %T %Z"))"
echo "kernel binary nk sha256 $(sha256sum nk | cut -c1-16) built $(date -r nk "+%F %T") on hp2 from the archive kernel sources (tries/28 kernel, the uncommitted working tree after tries/37), build line of run-on-hp.sh:"
sha256sum nk.c nk.h nkio.c nkmap.c nkvt.c nkxyz.c sqlite3.h | cut -c1-16,65-
echo
echo "line files typed into the scratch brain, in the ledger order (copied from hp:~/nk on 11-02 14:50, the files that educated the Cortex brain), sha256 first 16, bytes:"
for f in LINES-nk.txt TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt TEACH-5-nk.txt TEACH-6-nk.txt TEACH-7-nk.txt TEACH-8-nk.txt RECALL-nk.txt RECALL-2-nk.txt SHAPE-nk.txt RECALL-3-nk.txt REBIND-nk.txt RECALL-5-nk.txt BORN-nk.txt RELMAP-nk.txt RECALL-6-nk.txt RECALL-7-nk.txt FORMULA-nk.txt REBIND-g35-nk.txt SHAPE-2-nk.txt egg-symbols.txt nkbottom.py; do printf "%s  %-22s %7s bytes\n" "$(sha256sum $f | cut -c1-16)" "$f" "$(stat -c %s $f)"; done
echo
echo "sources (a copy of the Cortex kernel folder sources; the guesser file present but out of define since 10-31): bytes, time, file"
ls -l --time-style="+%F %T" ../sources | awk "NR>1{print \$5, \$6, \$7, \$8}"
echo
echo "machine: $(hostname), $(nproc) cores, $(free -m | awk "/Mem:/{print \$2}") MB, $(df -h /home | awk "NR==2{print \$4}") free; linux $(uname -r); sqlite $(python3 -c "import sqlite3;print(sqlite3.sqlite_version)"); gcc $(gcc -dumpversion)"
echo "scratch kernel: 127.0.0.1:7009, NK_MAP=$HOME/cortex/gates/brain/brain.map, folder $HOME/cortex/gates; educated $(grep -o "=== DONE .*" ~/cortex/gates/brain-educate.log) with refused 0 (the ledgers: no refused row); the Cortex brain on 7007 untouched"
echo "scratch brain after education: $(python3 - <<PY
import socket, json
s = socket.create_connection(("127.0.0.1", 7009), timeout=60); s.sendall(b"stats\n"); b = b""
while True:
    d = s.recv(1 << 20)
    if not d: break
    b += d
    if b.endswith(b"\n"): break
m = json.loads(b.decode())["main"]; print("defined", m["defined"], "runs", m["runs"], "hops", m["hops"], "gates", m["gates"], "refused", m["refused"], "shard_rows", m["shard_rows"])
PY
)"
