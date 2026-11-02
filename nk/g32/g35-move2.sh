#!/bin/bash
# g35-move.sh (2026-11-01): the one move of the brain out of RAM into its stored file. Used once.
cd ~/nk
log(){ echo "$(date +%H:%M:%S) $*"; }
pkill -f 'g35-move[.]sh'; pkill -f 'run-on-hp[.]sh snapshot'; pkill -x nk; pkill -f 'serve8[.]py'; sleep 2
pgrep -x nk > /dev/null && { sleep 5; pkill -9 -x nk; sleep 1; }
log "the old kernel and the snapshot are killed, at the owner's word"
rm -rf out/snap-20261101-011907; rm -f out/brain.map out/brain.map.main.db out/brain.map.sixth.db
S=out/snap-20261031-233036; log "the brain comes from $S"
for f in "$S"/*.db; do b=$(basename "$f"); [ "$b" = brain.db -o "$b" = sixth.db ] && continue; cp "$f" "sources/$b"; done
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -I. -o nk nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E " error " | head -n 5
SOURCES="wn gcide mwt moby map sqldoc measured guess wikt"
log "the stored kernel starts, the brain pours into its file"
(NK_MAP=$HOME/nk/out/brain.map NK_LOAD="$S" nohup ./nk 7007 egg-symbols.txt sources $SOURCES > nk.log 2>&1 &)
for i in $(seq 1 3600); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 7007), timeout=1).close()" 2>/dev/null && break; pgrep -x nk > /dev/null || { log "the kernel died in the load"; tail -n 3 nk.log; echo FAILED > out/g32-apply.done; exit 1; }; sleep 1; done
log "the kernel answers"; tail -n 2 nk.log | cut -c1-140
python3 - <<'PY'
import socket
s = socket.create_connection(("127.0.0.1", 7007)); s.sendall(b"type sixth BUILD CREATE INDEX IF NOT EXISTS sixth.spawned_sent_shared ON spawned ( sent , shared DESC ) ; CREATE INDEX IF NOT EXISTS sixth.asked_run_cell ON asked ( run , cell ) ; BUILD\n"); b = b""
while not b.endswith(b"\n"): b += s.recv(1 << 20)
print(b[:140])
PY
python3 g31/guess_out.py 7007 | tail -n 3 | cut -c1-110
python3 - <<'PY'
import socket, json, time
def ask(r, t=120):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=t); s.settimeout(t); s.sendall((r + "\n").encode()); b = b""
    while not b.endswith(b"\n"): b += s.recv(1 << 20)
    s.close(); return json.loads(b.decode())
time.sleep(5); st = ask("stats")
print({k: st["main"][k] for k in ("runs", "pending", "refused")}, st["sixth"]["pending"])
if st["main"]["pending"] == 0 and st["sixth"]["pending"] == 0:
    r = ask("type main define : node"); print("chain started by define : node", r.get("run"), r.get("seconds"))
PY
(nohup python3 serve8.py 8058 7007 NEURON-POINT-OF-CONNECTION-nk-2026-10-30.html LINES-nk.txt FIRST-RUNS-nk.txt 0.0.0.0 > door.log 2>&1 &); sleep 1; cat door.log | cut -c1-120
du -h out/brain.map* | cut -c1-60; ps -o rss,vsz,etime -p "$(pgrep -x nk)" | cut -c1-50
echo DONE > out/g32-apply.done; log "done"
