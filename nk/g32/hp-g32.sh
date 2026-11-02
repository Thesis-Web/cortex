#!/bin/bash
# hp-g32.sh (2026-11-01): two small kernels, own folders and ports, never ~/nk/sources. A = the kernel as it runs today, B = the same code with
# every region in a stored file. NK_WAIT_EMPTY so every line ends before the next. Stopped by the PID started here.
cd ~/nk
A=out/g32A; B=out/g32B
start(){ d=$1; port=$2; bin=$3; map=$4
  rm -rf "$d"; mkdir -p "$d/src"; cp sources-slice/*.db "$d/src/"; bash carry-src.sh "$d/src" > /dev/null
  NK_MAP="$map" NK_WAIT_EMPTY=1 NK_JOURNAL="$d/typed.txt" nohup "$bin" "$port" egg-symbols.txt "$d/src" wn gcide mw mwt moby map sqldoc measured guess > "$d/nk.log" 2>&1 &
  echo $! > "$d/pid"
  for i in $(seq 1 60); do python3 -c "import socket; socket.create_connection(('127.0.0.1', $port), timeout=1).close()" 2>/dev/null && break; sleep 1; done
  for f in LINES-nk.txt TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt GUESS-LINE-nk.txt TEACH-5-nk.txt TEACH-8-nk.txt; do
    python3 nkbottom.py "$port" --lines "$f" --ledger "$d/L-$(basename "$f" .txt).md" --quiet 2>&1 | tail -1 | cut -c1-90
  done
  python3 g31/bind5.py "$port" | cut -c1-90; python3 g31/guess_out.py "$port" | tail -n 1
  python3 nkbottom.py "$port" --lines DEFINES-1.txt --ledger "$d/L-defines.md" --quiet 2>&1 | tail -1 | cut -c1-130
  python3 - "$port" "/home/james/nk/$d/exp" <<'PY'
import socket, sys
p = int(sys.argv[1]); s = socket.create_connection(("127.0.0.1", p), timeout=500); s.sendall(("export " + sys.argv[2] + "\n").encode()); b = b""
while not b.endswith(b"\n"): b += s.recv(1 << 20)
print("exported", b[:60])
PY
}
start "$A" 7021 g32/nkheap ""
start "$B" 7022 g32/nkstored /home/james/nk/out/g32B.map
python3 g32/test_stored.py "$A" "$B" "$(cat $A/pid)" "$(cat $B/pid)"; echo "test exit $?"
ls -la --block-size=M out/g32B.map | cut -c20-90; du -h out/g32B.map | cut -f1
kill "$(cat $A/pid)" "$(cat $B/pid)"; sleep 1; rm -f out/g32B.map; pgrep -af 'nk(heap|stored)? 70[0-9][0-9] ' | grep -v bash | cut -c1-60
