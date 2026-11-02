mkdir -p ~/nk/g33 && cd ~/nk/g33 || exit 1
cp ../g32/*.c ../g32/*.h . 
python3 - <<'PY'
s=open('nk.c').read()
a='''  cut2(b, id, text ? text : ""); first_landing(b, id);
}'''
b='''  /* the owner, 2026-11-01: a define goes "to the fucking sources... pull the fucking information to the run data sheet"; "walkers are illegal"; draft 4.2 "pulled",
     "compares", "builds the definition table". A return is cut by the encoder into gates and arrives on the sheet. It is not stepped through the neurons. */
  cut2(b, id, text ? text : ""); rr = run_of(b, id);
  if(rr->nseq > 0){ Hop h = {0}; h.type = HOP_ENDED; h.run = id; h.gate = rr->seq[rr->nseq - 1]; h.a = 0; push(b, h); }
}'''
assert s.count(a)==1; open('nk.c','w').write(s.replace(a,b))
PY
sed -n 100,116p nk.c | cut -c1-200 | grep -n "label_new\|label_gate" | head -n 4
grep -n "static void push\|void push" nk.c | head -n 3 | cut -c1-140
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -I. -o nkret nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error|warning: impl" | head -n 10 | cut -c1-170
ls -la nkret | cut -c24-70
cat > hp-g33.sh <<'H'
#!/bin/bash
# hp-g33.sh: old kernel against the new one on small kernels in their own folders: a guard that nothing was lost, not the proof. The proof is the live brain.
cd ~/nk
start(){ d=$1; port=$2; bin=$3
  rm -rf "$d"; mkdir -p "$d/src"; cp sources-slice/*.db "$d/src/"; bash carry-src.sh "$d/src" > /dev/null
  NK_JOURNAL="$d/typed.txt" nohup "$bin" "$port" egg-symbols.txt "$d/src" wn gcide mw mwt moby map sqldoc measured guess > "$d/nk.log" 2>&1 &
  echo $! > "$d/pid"
  for i in $(seq 1 60); do python3 -c "import socket; socket.create_connection(('127.0.0.1', $port), timeout=1).close()" 2>/dev/null && break; sleep 1; done
  for f in LINES-nk.txt TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt GUESS-LINE-nk.txt TEACH-5-nk.txt TEACH-8-nk.txt; do python3 nkbottom.py "$port" --lines "$f" --ledger "$d/L-$(basename "$f" .txt).md" --quiet > /dev/null 2>&1; done
  python3 g31/bind5.py "$port" | cut -c1-80; python3 g31/guess_out.py "$port" | tail -n 1
  python3 nkbottom.py "$port" --lines DEFINES-1.txt --ledger "$d/L-defines.md" --quiet 2>&1 | tail -1 | cut -c1-120; }
settle(){ python3 - "$1" <<'PY'
import socket, json, sys, time
port = int(sys.argv[1])
def stats():
    s = socket.create_connection(("127.0.0.1", port), timeout=30); s.sendall(b"stats\n"); buf = b""
    while not buf.endswith(b"\n"): buf += s.recv(1 << 20)
    s.close(); return json.loads(buf.decode())
t = time.time(); last = None; same = 0
while time.time() - t < 280:
    st = stats(); now = (st["main"]["hops"], st["sixth"]["hops"], st["main"]["runs"]); idle = now == last and st["main"]["pending"] == 0 and st["sixth"]["pending"] == 0
    same = same + 1 if idle else 0; last = now
    if same >= 3: break
    time.sleep(1)
m = st["main"]; print("port %d settled %.0f s: runs %d, hops %d, gates %d, DNA rows %d, pastes %d, refused %d, paste_s %.1f, hop_s %.2f" % (port, time.time() - t, m["runs"], m["hops"], m["gates"], m["shards"], m["pastes"], m["refused"], m["paste_s"], m["hop_s"]))
PY
}
A=out/g33A; B=out/g33B
start "$A" 7031 "$1" & start "$B" 7032 "$2" & wait
settle 7031; settle 7032
python3 g31/test_guess_distinct.py --g3only 7031 7032 2>&1 | cut -c1-170
python3 - <<'PY'
import socket, json
for p in (7031, 7032):
    s = socket.create_connection(("127.0.0.1", p), timeout=30); s.sendall(b"q SELECT count(DISTINCT about) FROM main.run WHERE kind = 3\n"); b = b""
    while not b.endswith(b"\n"): b += s.recv(1 << 20)
    print(p, "points with a return", json.loads(b.decode())["rows"])
PY
kill "$(cat $A/pid)" "$(cat $B/pid)"; echo FINISHED
H
