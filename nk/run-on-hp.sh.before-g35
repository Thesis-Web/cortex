#!/bin/bash
# run-on-hp.sh (2026-11-01): the kernel on hp, from ~/nk. The brain is its stored file, out/brain.map, with its own tables beside it. Reference
# draft 5.8: "It can be turned back on in the same state, because it is stored, not held only in RAM." No snapshot, no load, no journal.
#   bash run-on-hp.sh up          the kernel built and started on the file: the brain comes back as it stopped; the door up
#   bash run-on-hp.sh stop        the kernel and the door stopped; the brain stays in its file
#   bash run-on-hp.sh door        the door started again
#   bash run-on-hp.sh type FILE   a lines file typed in order (ledger in out/LEDGER-<file>.md)
cd ~/nk; MODE=${1:-up}
SOURCES="wn gcide mwt moby map sqldoc measured guess wikt"
door(){ pkill -f 'serve8[.]py'; sleep 0.3; (nohup python3 serve8.py 8058 7007 NEURON-POINT-OF-CONNECTION-nk-2026-10-30.html LINES-nk.txt FIRST-RUNS-nk.txt 0.0.0.0 > door.log 2>&1 < /dev/null &); sleep 1; cat door.log; }
build(){ gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -I. -o nk nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl || exit 1; }
stop(){ pkill -x nk; for i in $(seq 1 600); do pgrep -x nk > /dev/null || break; sleep 1; done; pkill -f 'serve8[.]py'; }
case "$MODE" in
  stop) stop; echo stopped ;;
  door) door ;;
  type) python3 nkbottom.py 7007 --lines "$2" --ledger "out/LEDGER-$(basename "$2" .txt).md" --quiet | tail -1 | cut -c1-300 ;;
  up) stop; build
    (NK_MAP=$HOME/nk/out/brain.map nohup ./nk 7007 egg-symbols.txt sources $SOURCES > nk.log 2>&1 < /dev/null &)
    for i in $(seq 1 300); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 7007), timeout=1).close()" 2>/dev/null && break; sleep 1; done
    tail -n 1 nk.log; door ;;
esac
