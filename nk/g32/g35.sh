mkdir -p ~/nk/g35 && cd ~/nk/g35 || exit 1
cp ../g34/nk.c ../g34/nk.h ../g34/nkio.c ../g34/nkvt.c ../sqlite3.h . ; cp ../g32/nkmap.c .
python3 - <<'PY'
# ---- nk.h
s=open('nk.h').read()
rep=[
('int nk_map_open(const char *path, uint64_t cap); uint64_t nk_map_used(void);','int nk_map_open(const char *path, uint64_t cap, uint64_t layout); uint64_t nk_map_used(void); void *nk_map_root(void); void nk_map_set_root(void *p); void nk_map_ready(void); void nk_map_sync(void);'),
('typedef struct { int cell, state; char *value; } Cell;','/* a value on a sheet: a number, a list of numbers, or gates. Text lives in the encoder only (the owner, 2026-11-01); a value is read back through it */\ntypedef struct { int kind, n; union { i64 num; int *g; } u; } Val;   /* kind 0 null, 1 a number, 2 numbers (u.g[n]), 3 gates (u.g[n]) */\ntypedef struct { int cell, state; Val v; } Cell;'),
('char *mem_input; int mem_source','int mem_source'),
('typedef struct { i64 id, run; int cell; char *value; } Out;','typedef struct { i64 id, run; int cell; Val v; } Out;'),
('typedef struct { i64 id; char *text, *error; } Refused;','typedef struct { i64 id; Val text, error; } Refused;'),
('void   cell_set(Brain *b,','void   val_set(Brain *b, Val *v, const char *s); void val_free(Val *v); void val_copy(Val *to, const Val *from); const char *val_text(Brain *b, const Val *v);\nvoid   cell_set(Brain *b,'),
]
for a,b in rep:
    assert s.count(a)==1,a; s=s.replace(a,b)
import re
s2=re.sub(r'\n[^\n]*nk_compact[^\n]*','',s); open('nk.h','w').write(s2)
# ---- nk.c
s=open('nk.c').read()
a='  for(int i = 0; i < n; i++){ Cell *c = &r->cells[order[i]]; GROW(b->out, b->nout, b->cout, Out); Out *o = &b->out[b->nout]; o->id = b->nout + 1; o->run = run; o->cell = c->cell; o->value = c->value ? strdup(c->value) : 0; b->nout++; }'
b='  for(int i = 0; i < n; i++){ Cell *c = &r->cells[order[i]]; GROW(b->out, b->nout, b->cout, Out); Out *o = &b->out[b->nout]; o->id = b->nout + 1; o->run = run; o->cell = c->cell; val_copy(&o->v, &c->v); b->nout++; }'
assert s.count(a)==1; s=s.replace(a,b)
a='''  if(!c){ GROW(r->cells, r->ncells, r->ccells, Cell); c = &r->cells[r->ncells++]; c->cell = cell; c->value = 0; }
  else { free(c->value); c->value = 0; }
  c->state = state; c->value = value ? strdup(value) : 0;
'''
b='''  if(!c){ GROW(r->cells, r->ncells, r->ccells, Cell); c = &r->cells[r->ncells++]; c->cell = cell; memset(&c->v, 0, sizeof c->v); }
  else val_free(&c->v);
  c->state = state; val_set(b, &c->v, value);
'''
assert s.count(a)==1; s=s.replace(a,b)
a='if(r->cells[i].cell == cell && r->cells[i].state == 1 && r->cells[i].value) return r->cells[i].value; return 0; }'
b='if(r->cells[i].cell == cell && r->cells[i].state == 1 && r->cells[i].v.kind) return val_text(b, &r->cells[i].v); return 0; }'
assert s.count(a)==1; s=s.replace(a,b)
a='f->text = strdup(t); f->error = strdup("no such neuron");'
b='memset(&f->text, 0, sizeof f->text); memset(&f->error, 0, sizeof f->error); val_set(b, &f->text, t); val_set(b, &f->error, "no such neuron");'
assert s.count(a)==1; s=s.replace(a,b)
# the value functions, after the encoder's cut
a='static i64 memkey2(Run *r){'
b='''/* the encoder, for a value: a canonical number stays a number, a list of them stays numbers, anything else becomes gates */
static int canon_int(const char *s, size_t n, i64 *out){ size_t i = 0; int neg = 0; if(n && s[0] == '-'){ neg = 1; i = 1; } if(n == i || n - i > 18) return 0; if(s[i] == '0' && (neg || n - i > 1)) return 0; i64 x = 0; for(; i < n; i++){ if(s[i] < '0' || s[i] > '9') return 0; x = x * 10 + (s[i] - '0'); } *out = neg ? -x : x; return 1; }
void val_free(Val *v){ if(v->kind >= 2 && v->u.g) free(v->u.g); memset(v, 0, sizeof *v); }
void val_copy(Val *to, const Val *from){ *to = *from; if(from->kind >= 2 && from->n){ to->u.g = malloc(sizeof(int) * from->n); memcpy(to->u.g, from->u.g, sizeof(int) * from->n); } }
void val_set(Brain *b, Val *v, const char *s){
  memset(v, 0, sizeof *v); if(!s) return;
  size_t L = strlen(s); i64 x; if(canon_int(s, L, &x)){ v->kind = 1; v->u.num = x; return; }
  if(L && s[0] != ' ' && s[L - 1] != ' ' && strchr(s, ' ')){
    int cnt = 1, good = 1; for(size_t i = 0; i < L; i++) if(s[i] == ' ') cnt++;
    int *g = malloc(sizeof(int) * cnt); int k = 0; const char *p = s;
    while(good){ const char *e = strchr(p, ' '); size_t m = e ? (size_t)(e - p) : strlen(p); if(!m || !canon_int(p, m, &x) || x < 0 || x > 2147483647){ good = 0; break; } g[k++] = (int)x; if(!e) break; p = e + 1; }
    if(good){ v->kind = 2; v->n = k; v->u.g = g; return; }
    free(g);
  }
  int cap = 16, n = 0; int *g = malloc(sizeof(int) * cap); size_t i = 0; char buf[4096];
  while(i < L){ size_t j = i; if(is_letter((unsigned char)s[i])){ while(j < L && j - i < sizeof buf - 1 && is_letter((unsigned char)s[j])) j++; } else j = i + u8len((unsigned char)s[i]); if(j > L) j = L;
    size_t m = j - i; memcpy(buf, s + i, m); buf[m] = 0; int gt = label_gate(b, buf); if(!gt) gt = label_new(b, buf);
    if(n == cap){ cap *= 2; g = realloc(g, sizeof(int) * cap); } g[n++] = gt; i = j; }
  v->kind = 3; v->n = n; v->u.g = g;
}
const char *val_text(Brain *b, const Val *v){
  static char *ring[8]; static size_t caps[8]; static int ri;
  if(!v->kind) return 0;
  int at = ri; ri = (ri + 1) & 7; size_t need = 32;
  if(v->kind == 2) need += (size_t)v->n * 12; else if(v->kind == 3) for(int i = 0; i < v->n; i++){ int g = v->u.g[i]; if(g > 0 && g <= b->label.n) need += strlen(b->label.sym[g]); }
  if(need > caps[at]){ caps[at] = need * 2; ring[at] = realloc(ring[at], caps[at]); }
  char *o = ring[at]; size_t len = 0; o[0] = 0;
  if(v->kind == 1) snprintf(o, need, "%lld", (long long)v->u.num);
  else if(v->kind == 2) for(int i = 0; i < v->n; i++) len += snprintf(o + len, need - len, i ? " %d" : "%d", v->u.g[i]);
  else for(int i = 0; i < v->n; i++){ int g = v->u.g[i]; if(g > 0 && g <= b->label.n){ size_t m = strlen(b->label.sym[g]); memcpy(o + len, b->label.sym[g], m); len += m; } o[len] = 0; }
  return o;
}
static i64 memkey2(Run *r){'''
assert s.count(a)==1; s=s.replace(a,b)
# a formula's symbols are shared, not copied
a='  if(src) for(int i = 0; i < src->nseq; i++) seq_push(r, src->seq[i]);\n'
b='  if(src && src->seq){ r->seq = src->seq; r->nseq = src->nseq; r->seq_shared = 1; }   /* the formula is held once */\n'
assert s.count(a)==1; s=s.replace(a,b)
# compaction: deleted
i=s.index('/* ---------------- the cut: when a main run has completed'); j=s.index('const int *nk_seq') 
head=s[i:j]; k=head.index('static void cut_into') if 'static void cut_into' in head else None
keep=head[k:] if k is not None else ''
s=s[:i]+keep+s[j:]
# a closed define lets go of its returns, by key
a='  if(!sheet_open(r)) complete_run(b, run);\n}\n'
b='''  if(!sheet_open(r)) complete_run(b, run);
  /* a closed line lets go of the gates of its returns: the source row holds them. By the line's own kids, at its end: no sweep */
  r = run_of(b, run); if(r->kind == 0) for(int i = 0; i < r->nkids; i++){ Run *k = run_of(b, r->kids[i]); if(k && k->ended && k->src && k->seq && !k->seq_shared){ free(k->seq); k->seq = 0; k->kept = 0; } }
}
'''
assert s.count(a)==1,'ended tail'; s=s.replace(a,b)
a='k->value = ISNULL(st, 3) ? 0 : strdup(T(st, 3)); }'
b='val_set(b, &k->v, ISNULL(st, 3) ? 0 : T(st, 3)); }'
assert s.count(a)==1; s=s.replace(a,b)
a='o->value = ISNULL(st, 3) ? 0 : strdup(T(st, 3)); }'
b='val_set(b, &o->v, ISNULL(st, 3) ? 0 : T(st, 3)); }'
assert s.count(a)==1; s=s.replace(a,b)
a='f->text = strdup(T(st, 1) ? T(st, 1) : ""); f->error = strdup(T(st, 2) ? T(st, 2) : "");'
b='val_set(b, &f->text, T(st, 1) ? T(st, 1) : ""); val_set(b, &f->error, T(st, 2) ? T(st, 2) : "");'
assert s.count(a)==1; s=s.replace(a,b)
open('nk.c','w').write(s)
print('cut block kept:', len(keep), 'seq_push still used:', s.count('seq_push('))
# ---- nkvt.c
s=open('nkvt.c').read()
rep=[('case 3: RT(x, k->value); break; } }','case 3: RT(x, val_text(c->b, &k->v)); break; } }'),
('case 3: RT(x, o->value); break; } }','case 3: RT(x, val_text(c->b, &o->v)); break; } }'),
('case 1: RT(x, r->text); break; case 2: RT(x, r->error); break; } }','case 1: RT(x, val_text(c->b, &r->text)); break; case 2: RT(x, val_text(c->b, &r->error)); break; } }'),
('"CREATE VIRTUAL TABLE %s.%s USING nk(%s, %s)"','"CREATE VIRTUAL TABLE IF NOT EXISTS %s.%s USING nk(%s, %s)"')]
for a,b in rep:
    assert s.count(a)==1,a; s=s.replace(a,b)
open('nkvt.c','w').write(s)
# ---- nkio.c
s=open('nkio.c').read()
rep=[
('static sqlite3 *DB; static Brain MAINB, SIXTHB;','static sqlite3 *DB; static Brain *MAINP, *SIXTHP;\n#define MAINB (*MAINP)\n#define SIXTHB (*SIXTHP)'),
('    int is_ptr = (w->cell == REPLY || w->cell == DEF || w->cell == SAY || w->cell == REMEMBER);\n','    int is_ptr = (w->cell == REPLY || w->cell == DEF || w->cell == SAY || w->cell == REMEMBER); const char *wv = val_text(b, &w->v);\n'),
('  nk_compact(&MAINB); nk_compact(&SIXTHB);\n',''),
('if(busy){ pump_all(256); nk_compact(&MAINB); nk_compact(&SIXTHB); } continue; }','if(busy) pump_all(256); continue; }'),
('Cell *c = &root->cells[i]; if(i) sb_str(o, ","); sb_fmt(o, "[%d,%d,", c->cell, c->state);','Cell *c = &root->cells[i]; const char *cv = val_text(b, &c->v); if(i) sb_str(o, ","); sb_fmt(o, "[%d,%d,", c->cell, c->state);'),
('cells_b += sizeof(Cell) + (r->cells[c].value ? strlen(r->cells[c].value) + 1 + 16 : 0);','cells_b += sizeof(Cell) + (r->cells[c].v.kind >= 2 ? (i64)r->cells[c].v.n * 4 + 16 : 0);'),
(' if(r->mem_input) mem_b += strlen(r->mem_input) + 1 + 16;',''),
('  if(sqlite3_open(":memory:", &DB) != SQLITE_OK) return -1;\n','''  /* the brain's own tables (rel, asked, spawned ...) are stored beside it; the neurons' tables are the regions */
  const char *mp = getenv("NK_MAP"); char *fm = (mp && *mp) ? sqlite3_mprintf("%s.main.db", mp) : 0, *fs = (mp && *mp) ? sqlite3_mprintf("%s.sixth.db", mp) : 0;
  if(sqlite3_open(fm ? fm : ":memory:", &DB) != SQLITE_OK) return -1;
  if(fm) sqlite3_exec(DB, "PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA cache_size = -60000", 0, 0, 0);
'''),
('  sqlite3_exec(DB, "ATTACH \':memory:\' AS sixth", 0, 0, 0);\n','''  { char *q = sqlite3_mprintf("ATTACH '%q' AS sixth", fs ? fs : ":memory:"); sqlite3_exec(DB, q, 0, 0, 0); sqlite3_free(q); }
  if(fs) sqlite3_exec(DB, "PRAGMA sixth.journal_mode = OFF; PRAGMA sixth.synchronous = OFF; PRAGMA sixth.cache_size = -60000", 0, 0, 0);
'''),
('  if(getenv("NK_MAP") && *getenv("NK_MAP")){ if(nk_map_open(getenv("NK_MAP"), 220ULL << 30) != 0) return 1; }\n','''  int attached = 0; { const char *mp = getenv("NK_MAP"); if(mp && *mp){ attached = nk_map_open(mp, 400ULL << 30, ((uint64_t)sizeof(Run) << 40) ^ ((uint64_t)sizeof(Brain) << 20) ^ sizeof(Cell)); if(attached < 0) return 1; } }
  signal(SIGTERM, on_stop);
'''),
('  brain_init(&MAINB, "main", 1); brain_init(&SIXTHB, "sixth", 0); MAINB.tell = &SIXTHB;\n','''  if(attached){ Brain **root = nk_map_root(); MAINP = root[0]; SIXTHP = root[1]; }
  else { Brain **root = malloc(sizeof(Brain *) * 2); MAINP = root[0] = calloc(1, sizeof(Brain)); SIXTHP = root[1] = calloc(1, sizeof(Brain)); nk_map_set_root(root); brain_init(&MAINB, "main", 1); brain_init(&SIXTHB, "sixth", 0); }
  MAINB.name = "main"; SIXTHB.name = "sixth"; MAINB.tell = &SIXTHB;
'''),
('  else { lay_egg(&MAINB, argv[2]); lay_egg(&SIXTHB, argv[2]); }\n','  else if(!attached){ lay_egg(&MAINB, argv[2]); lay_egg(&SIXTHB, argv[2]); }\n'),
('  int s = socket(AF_INET, SOCK_STREAM, 0); int one = 1;','  nk_map_ready();\n  int s = socket(AF_INET, SOCK_STREAM, 0); int one = 1;'),
('    int busy = pending(&MAINB) || pending(&SIXTHB);\n','    if(STOP){ nk_map_sync(); sqlite3_close(DB); fprintf(stderr, "nk: stopped; the brain is in its file\\n"); return 0; }\n    int busy = pending(&MAINB) || pending(&SIXTHB);\n'),
('int main(int argc, char **argv){\n','static volatile sig_atomic_t STOP; static void on_stop(int n){ STOP = 1; }\nint main(int argc, char **argv){\n'),
('#include <poll.h>\n','#include <poll.h>\n#include <signal.h>\n'),
]
for a,b in rep:
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
s=s.replace('if(is_ptr && w->value && atoll(w->value) > 0){ i64 rr = atoll(w->value);','if(is_ptr && wv && atoll(wv) > 0){ i64 rr = atoll(wv);')
s=s.replace('(strcmp(cname, "unknown") == 0) && w->value){ const char *p = w->value;','(strcmp(cname, "unknown") == 0) && wv){ const char *p = wv;').replace('strcmp(cname, "unknown") == 0) && w->value){ const char *p = w->value;','strcmp(cname, "unknown") == 0) && wv){ const char *p = wv;')
s=s.replace('else sb_str(&v, w->value ? w->value : "");','else sb_str(&v, wv ? wv : "");')
s=s.replace('if(c->value) sb_json(o, c->value); else sb_str(o, "null");','if(cv) sb_json(o, cv); else sb_str(o, "null");')
s=s.replace('i64 rv = (c->value && runcell) ? atoll(c->value) : 0;','i64 rv = (cv && runcell) ? atoll(cv) : 0;')
s=s.replace('if(x && strspn(c->value, "0123456789") == strlen(c->value)){','if(x && strspn(cv, "0123456789") == strlen(cv)){')
s=s.replace('else if(c->value && (c->cell == label_gate(b, "known") || c->cell == label_gate(b, "unknown"))){','else if(cv && (c->cell == label_gate(b, "known") || c->cell == label_gate(b, "unknown"))){')
s=s.replace('const char *q = c->value; int nw = 0','const char *q = cv; int nw = 0')
open('nkio.c','w').write(s)
print('left in nkio:', s.count('->value'), s.count('nk_compact'), 'nkvt:', open('nkvt.c').read().count('->value'))
PY
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o nkall nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error|warning" | grep -v misleading | head -n 16 | cut -c1-190
ls -la nkall 2>&1 | cut -c24-70; grep -n "value\b" nk.c | grep -v "cell_set\|const char \*value\|val_set(b, &c->v, value)\|/\*\|run_sheet\|SELECT\|out_user" | cut -c1-140 | head; du -sh ../out/snap-20261101-011907 | cut -f1; date +%H:%M:%S
