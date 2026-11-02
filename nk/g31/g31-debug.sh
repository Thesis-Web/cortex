cd ~/nk; grep -n "gcc\|cc " run-on-hp.sh | head -n 4 | cut -c1-220; which gdb valgrind; git status --short | grep -v '^??' | head; git log -1 --format='%h %ad' --date=iso
mkdir -p g31/build && cp nk.c nk.h nkio.c nkvt.c *.h g31/build/ 2>/dev/null && cd g31/build
LINE=$(grep -n "gcc" ../../run-on-hp.sh | head -1 | sed 's/^[0-9]*://')
echo "build line: $LINE" | cut -c1-200
gcc -g -O1 -fsanitize=address -fno-omit-frame-pointer -Wno-unused-function -I. -o nkdbg nk.c nkvt.c nkio.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | tail -n 4 | cut -c1-200
ls -la nkdbg | cut -c1-90
cd ~/nk; d=out/g31D; rm -rf "$d"; mkdir -p "$d/src"; cp sources-slice/*.db "$d/src/"; bash carry-src.sh "$d/src" > /dev/null
( ASAN_OPTIONS=detect_leaks=0:abort_on_error=0 NK_JOURNAL="$d/typed.txt" g31/build/nkdbg 7014 egg-symbols.txt "$d/src" wn gcide mw mwt moby map sqldoc measured guess > "$d/nk.log" 2>&1; echo "kernel exit status $?" >> "$d/nk.log" ) &
for i in $(seq 1 40); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 7014), timeout=1).close()" 2>/dev/null && break; sleep 1; done
for f in LINES-nk.txt TEACH-LINES-nk.txt TEACH-2-nk.txt TEACH-3-nk.txt TEACH-4-nk.txt GUESS-LINE-nk.txt TEACH-5-nk.txt TEACH-8-nk.txt; do python3 nkbottom.py 7014 --lines "$f" --ledger "$d/L-$f.md" --quiet 2>&1 | tail -1 | cut -c1-110; done
sleep 2; wc -l "$d/typed.txt"; tail -n 1 "$d/typed.txt" | cut -c1-120; echo --- ; grep -n -m1 "ERROR: AddressSanitizer" -A14 "$d/nk.log" | cut -c1-170; tail -n 2 "$d/nk.log" | cut -c1-160
for p in $(pgrep -f 'g31/build/nkdbg 7014'); do kill "$p"; done
