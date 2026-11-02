cd ~/nk
one(){ bin=$1; port=$2; d=$3; rm -rf "$d"; mkdir -p "$d/src"; cp sources-slice/*.db "$d/src/"; bash carry-src.sh "$d/src" > /dev/null
  NK_WAIT_EMPTY=1 NK_JOURNAL="$d/typed.txt" nohup "$bin" "$port" egg-symbols.txt "$d/src" wn gcide mw mwt moby map sqldoc measured guess > "$d/nk.log" 2>&1 &
  echo $! > "$d/pid"
  for i in $(seq 1 40); do python3 -c "import socket; socket.create_connection(('127.0.0.1', $port), timeout=1).close()" 2>/dev/null && break; sleep 1; done
  for f in LINES-nk.txt DEFINES-1.txt; do python3 nkbottom.py "$port" --lines "$f" --ledger "$d/L-$(basename $f .txt).md" --quiet | tail -1 | cut -c1-70; done
  python3 - "$port" "/home/james/nk/$d/exp" <<'PY'
import socket, sys
p = int(sys.argv[1]); s = socket.create_connection(("127.0.0.1", p), timeout=120); s.sendall(("export " + sys.argv[2] + "\n").encode()); b = b""
while not b.endswith(b"\n"): b += s.recv(1 << 20)
PY
  kill "$(cat $d/pid)"; sleep 0.3; }
one ./nk 7015 out/g31E; one ./nk 7016 out/g31G; one g31/build/nkfix 7017 out/g31F
for pair in "E G old-binary-twice" "E F old-vs-fixed"; do set -- $pair; echo "=== $3"; for f in brain.db sixth.db; do python3 same_export.py out/g31$1/exp/$f out/g31$2/exp/$f 2>&1 | tail -n 3 | cut -c1-170; done; done
rm -rf out/g31E out/g31F out/g31G
