cd ~/nk/g31/build || exit 1
python3 - <<'PY'
s=open('nk.c').read()
a="r->same_as = f; if(!r->seq_shared) free(r->seq); r->seq = cn->seq; r->seq_shared = 1; b->deduped++;"
b="r->same_as = f; if(!r->seq_shared) free(r->seq); r->seq = cn->seq; r->seq_shared = 1; b->deduped++; cn->again++; /* counted when the repeat starts, not when it ends: it borrows cn's symbols from here on, and compaction leaves a run with again > 0 alone */"
c="if(cn){ cn->again++; cn->last_at = r->at; cn->last_run = run; }"
d="if(cn){ cn->last_at = r->at; cn->last_run = run; }"
assert s.count(a)==1 and s.count(c)==1
open('nk.c','w').write(s.replace(a,b).replace(c,d))
PY
diff ../../nk.c nk.c | cut -c1-200 | head -n 8
gcc -g -O1 -fsanitize=address -fno-omit-frame-pointer -Wno-unused-function -I. -o nkdbg nk.c nkvt.c nkio.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | tail -n 3 | cut -c1-160
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -I. -o nkfix nk.c nkvt.c nkio.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | tail -n 3 | cut -c1-160
ls -la nkdbg nkfix | cut -c1-80
cd ~/nk; export ASAN_OPTIONS=detect_leaks=0; NK=g31/build/nkdbg bash g31/hp-g31.sh 2>&1 | cut -c1-280 | tail -n 36
for d in out/g31A out/g31B; do grep -c "AddressSanitizer" $d/nk.log; done
