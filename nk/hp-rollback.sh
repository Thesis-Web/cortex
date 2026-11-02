#!/bin/bash
# hp-rollback.sh (2026-10-30 19:30): back to the 15:45 snapshot after my fresh run erased the live sources' state; Wiktionary's gate restored by hand
cd ~/nk; pkill -x nk; pkill -f serve8.py; sleep 1
echo "--- wikt me before: $(sqlite3 sources/wikt.db 'SELECT gate FROM me')"
sqlite3 sources/wikt.db "UPDATE me SET gate = 443" && echo "wikt me set back to 443 by hand (what my fresh run erased); inbox $(sqlite3 sources/wikt.db 'SELECT count(*) FROM inbox') outbox $(sqlite3 sources/wikt.db 'SELECT count(*) FROM outbox')"
STAMP=$(date +%H%M); cp out/typed.txt "out/typed-before-rollback-$STAMP.txt"; head -n 119 "out/typed-before-rollback-$STAMP.txt" > out/typed.txt; echo "journal cut to $(wc -l < out/typed.txt) lines (the rest kept in out/typed-before-rollback-$STAMP.txt, not replayed: its bind lines carry run numbers)"
rm -f out/snap-latest; ln -s snap-20261030-154531 out/snap-latest; echo "snapshot: $(readlink out/snap-latest), typed lines $(cat out/snap-latest/typed-lines.txt)"
bash run-on-hp.sh resume 2>&1 | tail -2
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
st = ask("stats")["main"]; print("rolled back:", {k: st[k] for k in ("runs", "receipts", "refused", "gates", "pending")})
PY
bash run-on-hp.sh type TEACH-3-nk.txt | tail -1 | cut -c1-120
python3 - <<'PY'
import socket, json, time, subprocess
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
print("wikt gate in the brain:", q("SELECT gate FROM label WHERE symbol = 'wikt'"), "| wikt.ME:", q("SELECT gate FROM wikt.ME"))
t = time.time(); r = ask("type main define unknown : 50"); st = ask("stats")["main"]
rss = int(subprocess.run(["bash", "-c", "ps -o rss= -C nk"], capture_output=True, text=True).stdout.strip() or 0) // 1024
print("50 defines: %.1f s" % (time.time() - t), "| refused now:", st["refused"], "| wikt returns in this round:", q("SELECT count(*) FROM run WHERE arrival = (SELECT gate FROM label WHERE symbol = 'wikt') AND id > %d" % r["run"])[0][0], "| deduped:", st["deduped_runs"], "| rss MB:", rss)
PY
