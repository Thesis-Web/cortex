#!/bin/bash
# g32-apply.sh (2026-11-01): the big kernel moved to the stored file: a snapshot of the brain as it stands, the stored kernel built, the brain loaded into it.
# To undo: run-on-hp.sh with NK_MAP removed from the start line and the build without nkmap.c; resume loads the same snapshot.
cd ~/nk
log(){ echo "$(date +%H:%M:%S) $*"; }
log "snapshot starts"; bash run-on-hp.sh snapshot || { log "snapshot failed; nothing changed"; echo FAILED > out/g32-apply.done; exit 1; }
S="out/$(readlink out/snap-latest)"; log "snapshot done: $S, typed lines $(cat "$S/typed-lines.txt"), journal $(wc -l < out/typed.txt)"
log "snapshot run rows: $(sqlite3 "file:$S/brain.db?mode=ro" 'SELECT count(*) FROM run')"
cp g32/nk.h g32/nkio.c g32/nkmap.c . || exit 1
python3 - <<'PY'
s = open("run-on-hp.sh").read()
a = "-o nk nk.c nkvt.c nkio.c -L"; b = "-o nk nk.c nkvt.c nkio.c nkmap.c -L"
assert s.count(a) == 1; s = s.replace(a, b)
a = '(NK_JOURNAL=out/typed.txt NK_LOAD="$SNAP" nohup ./nk 7007'; b = 'rm -f out/brain-*.map; (NK_MAP=$HOME/nk/out/brain-$(date +%Y%m%d-%H%M%S).map NK_JOURNAL=out/typed.txt NK_LOAD="$SNAP" nohup ./nk 7007'
assert s.count(a) == 1; s = s.replace(a, b)
a = '(NK_JOURNAL=out/typed.txt nohup ./nk 7007'; b = 'rm -f out/brain-*.map; (NK_MAP=$HOME/nk/out/brain-$(date +%Y%m%d-%H%M%S).map NK_JOURNAL=out/typed.txt nohup ./nk 7007'
assert s.count(a) == 1; s = s.replace(a, b)
open("run-on-hp.sh", "w").write(s)
PY
bash -n run-on-hp.sh || exit 1
log "resume starts"; bash run-on-hp.sh resume 2>&1 | cut -c1-200; log "resume ended"
pgrep -af '^\./nk 7007' | cut -c1-70; ls -la --block-size=M out/brain-*.map | cut -c20-90; du -h out/brain-*.map | cut -f1
echo DONE > out/g32-apply.done; log "done"
