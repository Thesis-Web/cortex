cd ~/nk; sed -n 1,6p same_export.py | cut -c1-170
one(){ bin=$1; port=$2; d=$3; rm -rf "$d"; mkdir -p "$d/src"; cp sources-slice/*.db "$d/src/"; bash carry-src.sh "$d/src" > /dev/null
  NK_JOURNAL="$d/typed.txt" nohup "$bin" "$port" egg-symbols.txt "$d/src" wn gcide mw mwt moby map sqldoc measured guess > "$d/nk.log" 2>&1 &
  echo $! > "$d/pid"
  for i in $(seq 1 40); do python3 -c "import socket; socket.create_connection(('127.0.0.1', $port), timeout=1).close()" 2>/dev/null && break; sleep 1; done
  for f in LINES-nk.txt DEFINES-1.txt; do python3 nkbottom.py "$port" --lines "$f" --ledger "$d/L-$(basename $f .txt).md" --quiet | tail -1 | cut -c1-90; done
  python3 - "$port" "/home/james/nk/$d/exp" <<'PY'
import socket, sys
p = int(sys.argv[1]); s = socket.create_connection(("127.0.0.1", p), timeout=120); s.sendall(("export " + sys.argv[2] + "\n").encode()); b = b""
while not b.endswith(b"\n"): b += s.recv(1 << 20)
print(b[:120])
PY
  kill "$(cat $d/pid)"; }
one ./nk 7015 out/g31E; one g31/build/nkfix 7016 out/g31F
python3 same_export.py out/g31E/exp out/g31F/exp 2>&1 | tail -n 6 | cut -c1-200
