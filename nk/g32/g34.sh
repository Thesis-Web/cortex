mkdir -p ~/nk/g34 && cd ~/nk/g34 || exit 1
cp ../nk.c ../nkvt.c ../sqlite3.h . ; cp ../g32/nk.h ../g32/nkio.c ../g32/nkmap.c .
python3 - <<'PY'
import re
# ---- nk.h
s=open('nk.h').read()
a="typedef struct {\n  int arrival, parent_set;"
b="typedef struct { int ord, pos, gate, via; i64 shard; } Ev;   /* what a closed run fires, in order: a call, a spawn, a BUILD. Draft 3.2: \"one hop to the memory\" */\n"+a
assert s.count(a)==1; s=s.replace(a,b)
a="} Run;"; b="  Ev *ev; int nev, cev, ev_built; i64 ok_at;   /* a closed run's firings, read once from its receipt; ok_at: when its shards were last seen unchanged */\n} Run;"
assert s.count(a)==1; s=s.replace(a,b)
a="HOP_REPLAY = 3 }"; b="HOP_REPLAY = 3, HOP_FIRE = 4 }"
assert s.count(a)==1; s=s.replace(a,b)
a="} Brain;"; b="  i64 rewrite_at;                           /* the clock when a shard's call or spawn last changed */\n} Brain;"
assert s.count(a)==1; s=s.replace(a,b)
open('nk.h','w').write(s)
# ---- nk.c
s=open('nk.c').read()
a="  for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; Shard *s = shard_by_id(b, k->gate, k->shard); if(!s || s->changed_at > cn->mem_at) return; }\n"
b="  if(cn->ok_at <= b->rewrite_at){ for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; Shard *s = shard_by_id(b, k->gate, k->shard); if(!s || s->changed_at > cn->mem_at) return; } cn->ok_at = b->clock; cn->ev_built = 0; }   /* read again only after a shard was rewritten */\n"
assert s.count(a)==1; s=s.replace(a,b)
a="static void first_landing(Brain *b, i64 run){ Run *r = run_of(b, run); dedupe_check(b, run); if(r->nseq > 0) land(b, run, 0, r->arrival, 0, r->seq[0], 0); }"
b='''/* draft 3.2: a closed run repeated is "one hop to the memory. No rows fire, nothing is laid, and mother is not called"; the firings its first run found are what it does */
static void to_memory(Brain *b, i64 run){
  Run *r = run_of(b, run), *cn = run_of(b, r->same_as);
  if(!cn->ev_built){ cn->nev = 0; for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; Shard *s = shard_by_id(b, k->gate, k->shard); if(s && (s->call || s->spawn || (k->gate == BUILD && k->via == 0))){ GROW(cn->ev, cn->nev, cn->cev, Ev); Ev *e = &cn->ev[cn->nev++]; e->ord = i; e->pos = k->pos; e->gate = k->gate; e->via = k->via; e->shard = k->shard; } } cn->ev_built = 1; }
  Hop h = {0}; h.type = HOP_FIRE; h.run = run; h.a = 0; push(b, h);
}
static void first_landing(Brain *b, i64 run){ Run *r = run_of(b, run); dedupe_check(b, run); if(r->nseq <= 0) return; if(r->same_as){ to_memory(b, run); return; } land(b, run, 0, r->arrival, 0, r->seq[0], 0); }'''
assert s.count(a)==1; s=s.replace(a,b)
a="  dedupe_check(b, id);\n  if(r->nseq > 0){ Hop h = {0}; h.type = HOP_LAND; h.run = id;"
b="  dedupe_check(b, id);\n  if(r->nseq > 0 && r->same_as){ to_memory(b, id); return; }\n  if(r->nseq > 0){ Hop h = {0}; h.type = HOP_LAND; h.run = id;"
assert s.count(a)==1; s=s.replace(a,b)
# the BUILD step, one function for a walked run and a closed run
i=s.index("  if(gate == BUILD && via == 0){\n    if(r->build_pos < 0) r->build_pos = pos;")
j=s.index("\n}\n", i)
block=s[i:j]; inner=block[block.index("\n")+1:block.rindex("\n  }")]
s=s[:i]+"  if(gate == BUILD && via == 0) build_gate(b, run, pos, ord);"+s[j:]
fn="static void build_gate(Brain *b, i64 run, int pos, int ord){\n  Run *r = run_of(b, run);\n"+inner+"\n}\n"
a="static void hit(Brain *b, i64 run, int pos, int gate, int before, int next, int via, int had, Shard *s){"
assert s.count(a)==1; s=s.replace(a,fn+a)
a="/* ---------------- the end of a run"
fire='''/* a closed run repeated: its firings in order, nothing else; the next one waits under what this one fires, as in hit_go's order */
static void fire(Brain *b, i64 run, int i){
  Run *r = run_of(b, run), *cn = r ? run_of(b, r->same_as) : 0; if(!cn) return;
  if(i >= cn->nev){ r->nhops = cn->nhops; Hop h = {0}; h.type = HOP_ENDED; h.run = run; h.gate = cn->mem_gate; h.a = cn->mem_shard; push(b, h); return; }
  Ev e = cn->ev[i]; ++b->hops_done;
  Hop h = {0}; h.type = HOP_FIRE; h.run = run; h.a = i + 1; push(b, h);
  Shard *s = shard_by_id(b, e.gate, e.shard);
  if(s && s->spawn) replay_push_from(b, run, s->spawn, 2, run, e.ord);
  if(s && s->call) replay_push_from(b, run, s->call, 1, run, e.ord);
  if(e.gate == BUILD && e.via == 0) build_gate(b, run, e.pos, e.ord);
}
'''
assert s.count(a)==1; s=s.replace(a,fire+a)
a="      case HOP_REPLAY: replay(b, h.run, h.a, h.kind, h.from_run, h.from_ord); break;\n"
b=a+"      case HOP_FIRE: fire(b, h.run, (int)h.a); break;\n"
assert s.count(a)==1; s=s.replace(a,b)
# the line as a string in the memory row: gone, the run holds it as gates
a='''    size_t cap = 64 + (size_t)r->nseq * 12; char *inp = malloc(cap); inp[0] = 0; size_t len = 0;
    for(int i = 0; i < r->nseq; i++){ len += snprintf(inp + len, cap - len, i ? " %d" : "%d", r->seq[i]); }
    r->mem_input = inp; r->mem_source'''
b="    r->mem_source"
assert s.count(a)==1; s=s.replace(a,b)
a='r->mem_input = strdup(T(st, 1) ? T(st, 1) : ""); '
assert s.count(a)==1; s=s.replace(a,'')
# the receipt rebuild: deleted
i=s.index("  /* re-hopped from the symbols:"); j=s.index("  *out = RCBUF; *kept = 0; return m;\n")+len("  *out = RCBUF; *kept = 0; return m;\n")
s=s[:i]+"  *out = 0; *kept = 0; return 0;   /* a closed sub-run has no receipt and none is rebuilt: the main run's receipt and sheet are its memory */\n"+s[j:]
open('nk.c','w').write(s)
# ---- nkvt.c
s=open('nkvt.c').read()
a="if(s->call != V(argv[6]) || s->spawn != V(argv[7])) s->changed_at = b->clock;"
b="if(s->call != V(argv[6]) || s->spawn != V(argv[7])){ s->changed_at = b->clock; b->rewrite_at = b->clock; }"
assert s.count(a)==1; s=s.replace(a,b)
a="&& !r->same_as && r->mem_input) return 1;"; b="&& !r->same_as && r->kept) return 1;"
assert s.count(a)==1; s=s.replace(a,b)
a="static void mem_col(Cur *c, sqlite3_context *x, int col){"
b='''static char *MEMTXT; static size_t MEMCAP;
static const char *mem_text(Brain *b, i64 run){ int n; const int *q = nk_seq(b, run, &n); if(!q) return 0; size_t need = 16 + (size_t)n * 12; if(need > MEMCAP){ MEMCAP = need * 2; MEMTXT = realloc(MEMTXT, MEMCAP); } size_t len = 0; MEMTXT[0] = 0; for(int i = 0; i < n; i++) len += snprintf(MEMTXT + len, MEMCAP - len, i ? " %d" : "%d", q[i]); return MEMTXT; }
'''+a
assert s.count(a)==1; s=s.replace(a,b)
a="case 1: RT(x, r->mem_input); break; case 2: { char t[24];"
b="case 1: RT(x, r->kept ? mem_text(c->b, c->e) : 0); break; case 2: { char t[24];"
assert s.count(a)==1; s=s.replace(a,b)
open('nkvt.c','w').write(s)
print("patched")
PY
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o nknew nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error|warning" | grep -v misleading | head -n 12 | cut -c1-180
ls -la nknew | cut -c24-70; grep -n "RT(" nkvt.c | head -n 2 | cut -c1-140; sed -n "$(grep -n 'static void build_gate' nk.c | cut -d: -f1),+9p" nk.c | cut -c1-130
tail -n 1 ../out/g32-apply.log | cut -c1-100; du -sh ../out/snap-20261101-011907 | cut -f1; date +%H:%M:%S
