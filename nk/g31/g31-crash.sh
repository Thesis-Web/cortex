cd ~/nk; d=out/g31C; rm -rf "$d"; mkdir -p "$d/src"; cp sources-slice/*.db "$d/src/"; bash carry-src.sh "$d/src" > /dev/null
( ulimit -c 0; NK_JOURNAL="$d/typed.txt" ./nk 7013 egg-symbols.txt "$d/src" wn gcide mw mwt moby map sqldoc measured guess > "$d/nk.log" 2>&1; echo "kernel exit status $?" >> "$d/nk.log" ) &
for i in $(seq 1 30); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 7013), timeout=1).close()" 2>/dev/null && break; sleep 1; done
for f in LINES-nk.txt TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt GUESS-LINE-nk.txt TEACH-5-nk.txt TEACH-8-nk.txt; do python3 nkbottom.py 7013 --lines "$f" --ledger "$d/L-$f.md" --quiet | tail -1 | cut -c1-130; done
python3 - <<'PY'
import socket,json,time
def ask(r,t=20):
    s=socket.create_connection(("127.0.0.1",7013),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while True:
        d=s.recv(1<<20)
        if not d: break
        b+=d
        if b.endswith(b"\n"): break
    s.close(); return b.decode()[:300]
print("before", ask("stats")[:160])
try: print("typed", ask("type main define : the")[:240])
except Exception as e: print("type failed", repr(e))
for i in range(6):
    time.sleep(1)
    try: print(i, ask("stats")[:120])
    except Exception as e: print(i,"gone",repr(e)); break
PY
sleep 1; tail -n 4 "$d/nk.log" | cut -c1-200; pkill -f '^\./nk 7013 ' ; which gdb valgrind 2>/dev/null; grep -c . "$d/L-TEACH-8-nk.txt.md"; grep -n -i "error\|refused" "$d/L-TEACH-8-nk.txt.md" | cut -c1-220 | head -n 6
