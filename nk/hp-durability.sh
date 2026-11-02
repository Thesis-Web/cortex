#!/bin/bash
# hp-durability.sh: fresh egg + sixty lines -> export A -> snapshot -> stop -> load the snapshot -> export B -> compare; then one line typed on the loaded brain
cd ~/nk; pkill -x nk; pkill -f serve8.py; sleep 0.5
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -I. -o nk nk.c nkvt.c nkio.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl || exit 1
rm -rf out/expA out/expB out/snap-test; mkdir -p out/expA out/expB; rm -f sources/*.db; cp sources-egg/*.db sources/; rm -f out/typed.txt
(NK_JOURNAL=out/typed.txt nohup ./nk 7007 egg-symbols.txt sources > nk.log 2>&1 &); sleep 1
python3 nkbottom.py 7007 --lines LINES-nk.txt --ledger out/LEDGER-nk-60-lines.md --quiet | tail -1 | cut -c1-120
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
print(ask("export /home/james/nk/out/expA")); print(ask("snapshot /home/james/nk/out/snap-test"))
PY
pkill -x nk; sleep 0.5
(NK_JOURNAL=out/typed.txt NK_LOAD=out/snap-test nohup ./nk 7007 egg-symbols.txt sources > nk-load.log 2>&1 &); sleep 2; cat nk-load.log
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
print(ask("export /home/james/nk/out/expB"))
r = ask("type main print dna : who"); print("typed on the loaded brain:", {k: r[k] for k in ("run", "runs", "hits", "born", "refused")}); [print("   ", o) for o in r["out"][:3]]
print("stats:", ask("stats")["main"])
PY
echo "--- main export A vs B"; python3 same_export.py out/expA/brain.db out/expB/brain.db
echo "--- sixth export A vs B"; python3 same_export.py out/expA/sixth.db out/expB/sixth.db
