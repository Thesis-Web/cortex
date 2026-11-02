#!/bin/bash
# g34/hp-g34-hop.sh (2026-11-01): the hop as one shard, applied on hp. Patch, build, the kernel started again on its file (the brain comes
# back), then the back population (`hop`) started in the background: it walks every neuron and every run once. Read `out/hop.json` when done.
cd ~/nk
cp nk.c nk.c.before-g34; cp nk.h nk.h.before-g34; cp nkvt.c nkvt.c.before-g34; cp nkio.c nkio.c.before-g34; cp serve8.py serve8.py.before-g34
cp NEURON-POINT-OF-CONNECTION-nk-2026-10-30.html NEURON-POINT-OF-CONNECTION-nk-2026-10-30.html.before-g34
python3 g34/hop_patch.py || exit 1
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o /tmp/nkb nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error|warning" | head -n 8 | cut -c1-220
[ -x /tmp/nkb ] || { echo "BUILD FAILED"; exit 1; }
rm -f /tmp/nkb
echo "--- before: $(curl -s localhost:8058/api/stats | python3 -c 'import json,sys; d=json.load(sys.stdin); print({k: d["main"].get(k) for k in ("shards","shard_rows","runs","defined","refused")})')"
timeout 300 bash run-on-hp.sh up 2>&1 | tail -n 2 | cut -c1-120
for i in $(seq 1 60); do curl -sf localhost:8058/api/stats > /dev/null && break; sleep 1; done
echo "--- after restart: $(curl -s localhost:8058/api/stats | python3 -c 'import json,sys; d=json.load(sys.stdin); print({k: d["main"].get(k) for k in ("shards","shard_rows","runs","defined","refused","pending")}, {k: d["sixth"].get(k) for k in ("shards","shard_rows","pending")})')"
rm -f out/hop.json
nohup python3 - > out/hop.json 2>&1 <<'PY' &
import socket, time
t = time.time()
s = socket.create_connection(("127.0.0.1", 7007), timeout=7200); s.settimeout(7200); s.sendall(b"hop\n"); b = b""
while not b.endswith(b"\n"): b += s.recv(1 << 20)
s.close(); print(b.decode().strip()); print("wall_s", round(time.time() - t, 1))
PY
echo "hop started in the background"
