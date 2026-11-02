#!/bin/bash
# hp-g31.sh (2026-10-31): two small kernels on the slice sources, each in its own folder and on its own port. Neither reads or writes
# ~/nk/sources, the big kernel's folder. A keeps the old lines (the control); B has guess_out.py typed. The same define goes into both, each
# chain runs to its end, then the test reads both. Each kernel is stopped by the PID this script started, never by a pattern.
cd ~/nk
start(){ d=$1; port=$2
  mkdir -p "$d/src"; cp sources-slice/*.db "$d/src/"; bash carry-src.sh "$d/src" > /dev/null
  NK_JOURNAL="$d/typed.txt" nohup ${NK:-./nk} "$port" egg-symbols.txt "$d/src" wn gcide mw mwt moby map sqldoc measured guess > "$d/nk.log" 2>&1 &
  echo $! > "$d/pid"
  for i in $(seq 1 60); do python3 -c "import socket; socket.create_connection(('127.0.0.1', $port), timeout=1).close()" 2>/dev/null && break; sleep 1; done
  for f in LINES-nk.txt TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt GUESS-LINE-nk.txt TEACH-5-nk.txt TEACH-8-nk.txt; do
    python3 nkbottom.py "$port" --lines "$f" --ledger "$d/LEDGER-$(basename "$f" .txt).md" --quiet | tail -1 | cut -c1-110
  done; }
settle(){ python3 - "$1" <<'PY'
import socket, json, sys, time
port = int(sys.argv[1])
def stats():
    s = socket.create_connection(("127.0.0.1", port), timeout=30); s.sendall(b"stats\n"); buf = b""
    while not buf.endswith(b"\n"): buf += s.recv(1 << 20)
    s.close(); return json.loads(buf.decode())
t = time.time(); last = None; same = 0
while time.time() - t < 200:
    st = stats(); now = (st["main"]["hops"], st["sixth"]["hops"]); idle = now == last and st["main"]["pending"] == 0 and st["sixth"]["pending"] == 0
    same = same + 1 if idle else 0; last = now
    if same >= 3: break
    time.sleep(1)
print("port %d settled after %.1f s: runs %d, hops %d, pastes %d, refused %d, paste_s %.2f" % (port, time.time() - t, st["main"]["runs"], st["main"]["hops"], st["main"]["pastes"], st["main"]["refused"], st["main"]["paste_s"]))
PY
}
A=out/g31A; B=out/g31B; rm -rf "$A" "$B"
echo "== control kernel"; start "$A" 7011
echo "== changed kernel"; start "$B" 7012
echo "== the sixth's define shard bound on both, as it is on the big kernel"; for p in 7011 7012; do python3 g31/bind5.py "$p"; done
echo "== the guesser out of define and why, on the changed kernel only"; python3 g31/guess_out.py 7012
python3 g31/test_guess_distinct.py --base 7011 7012 > out/g31-base.json; cat out/g31-base.json
for p in 7011 7012; do python3 - "$p" <<'PY'
import socket, sys
p = int(sys.argv[1]); s = socket.create_connection(("127.0.0.1", p), timeout=120); s.sendall(b"type main define : the\n"); b = b""
while not b.endswith(b"\n"): b += s.recv(1 << 20)
print("typed on", p, b[:120])
PY
done
for p in 7011 7012; do python3 nkbottom.py "$p" --lines DEFINES-1.txt --ledger "out/g31-defines-$p.md" --quiet | tail -1 | cut -c1-110; done
settle 7011; settle 7012
echo "== the test"; python3 g31/test_guess_distinct.py 7011 7012 out/g31-base.json; echo "test exit $?"
python3 g31/inspect31.py 7011 7012 2>&1 | cut -c1-240 | tail -n 1
echo "== G3's negative control: a third kernel, the guesser out, one source emptied"; C=out/g31C; rm -rf "$C"; start "$C" 7013; sqlite3 "$C/src/mwt.db" 'DELETE FROM corpus'; python3 g31/bind5.py 7013; python3 g31/guess_out.py 7013 > /dev/null
python3 - 7013 <<'PY'
import socket, sys
p = int(sys.argv[1]); s = socket.create_connection(("127.0.0.1", p), timeout=120); s.sendall(b"type main define : the\n"); b = b""
while not b.endswith(b"\n"): b += s.recv(1 << 20)
PY
python3 nkbottom.py 7013 --lines DEFINES-1.txt --ledger out/g31-defines-7013.md --quiet | tail -1 | cut -c1-80; settle 7013; python3 g31/test_guess_distinct.py --g3only 7012 7013; echo "g3 control exit $?"; kill "$(cat $C/pid)"
kill "$(cat $A/pid)" "$(cat $B/pid)"; sleep 1; echo "stopped: $(cat $A/pid) $(cat $B/pid)"; pgrep -af 'nk 70[0-9][0-9] ' | grep -v bash | cut -c1-60
