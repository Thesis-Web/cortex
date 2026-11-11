/* nk.c (2026-10-30): the physics of v7's egg, done natively over regions in memory. Every function here is one of the egg's triggers
   (gen_egg6.py) said in C: input_go/third_go/secondary_go (line_in, secondary_in), replay_go (replay), land_go (land), hit_go (hit),
   ended_go + memory_go + sheet_fill + complete_go (ended, cell_set), out_mother_go (the span to mother). It decides nothing a row
   did not ask for, and it scans nothing: every find is by key. */
#include "nk.h"
#include <time.h>
i64 now_ns(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (i64)t.tv_sec * 1000000000LL + t.tv_nsec; }
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* ---------------- hash map ---------------- */
static inline uint64_t mix(uint64_t a, uint64_t b){ uint64_t h = a * 0x9E3779B97F4A7C15ULL ^ (b + 0x632BE59BD9B4E019ULL); h ^= h >> 29; h *= 0xBF58476D1CE4E5B9ULL; h ^= h >> 32; return h; }
void hmap_init(HMap *m, size_t cap){ m->cap = cap < 8 ? 8 : cap; m->n = 0; m->e = calloc(m->cap, sizeof(HEnt)); }
static void hmap_grow(HMap *m){ HEnt *old = m->e; size_t oc = m->cap; m->cap *= 2; m->e = calloc(m->cap, sizeof(HEnt)); m->n = 0; for(size_t i = 0; i < oc; i++) if(old[i].v) hmap_put(m, old[i].k1, old[i].k2, old[i].v); free(old); }
i64 hmap_get(HMap *m, i64 k1, i64 k2){ if(!m->e) return 0; size_t i = mix(k1, k2) & (m->cap - 1); for(;;){ HEnt *e = &m->e[i]; if(!e->v) return 0; if(e->k1 == k1 && e->k2 == k2) return e->v; i = (i + 1) & (m->cap - 1); } }
void hmap_put(HMap *m, i64 k1, i64 k2, i64 v){ if(!m->e) hmap_init(m, 8); if((m->n + 1) * 10 > m->cap * 7) hmap_grow(m); size_t i = mix(k1, k2) & (m->cap - 1); for(;;){ HEnt *e = &m->e[i]; if(!e->v){ e->k1 = k1; e->k2 = k2; e->v = v; m->n++; return; } if(e->k1 == k1 && e->k2 == k2){ e->v = v; return; } i = (i + 1) & (m->cap - 1); } }
void hmap_del(HMap *m, i64 k1, i64 k2){ /* rebuild without the key (rare) */ if(!hmap_get(m, k1, k2)) return; HEnt *old = m->e; size_t oc = m->cap; m->e = calloc(m->cap, sizeof(HEnt)); m->n = 0; for(size_t i = 0; i < oc; i++) if(old[i].v && !(old[i].k1 == k1 && old[i].k2 == k2)) hmap_put(m, old[i].k1, old[i].k2, old[i].v); free(old); }
uint64_t seqhash(const int *seq, int n){ uint64_t h = 1469598103934665603ULL ^ (uint64_t)n; for(int i = 0; i < n; i++){ h ^= (uint64_t)(uint32_t)seq[i]; h *= 1099511628211ULL; h ^= h >> 29; } return h; }
uint64_t strhash(const char *s){ uint64_t h = 1469598103934665603ULL; while(*s){ h ^= (unsigned char)*s++; h *= 1099511628211ULL; } return h; }

#define GROW(arr, n, cap, T) do { if((n) >= (cap)){ (cap) = (cap) ? (cap) * 2 : 2; (arr) = realloc((arr), (cap) * sizeof(T)); } } while(0)   /* small arrays start small: a run has two cells, most neurons one shard */

/* ---------------- the brain ---------------- */
void brain_init(Brain *b, const char *name, int is_main){
  memset(b, 0, sizeof(*b)); b->name = name; b->is_main = is_main;
  hmap_init(&b->label.h, 1024); hmap_init(&b->relh, 1024); hmap_init(&b->memh, 1024); hmap_init(&b->hith, 1 << 12); hmap_init(&b->memt, 1024); hmap_init(&b->shid, 1 << 14);
  b->label.cap = 256; b->label.sym = calloc(b->label.cap, sizeof(char*)); b->label.n = 0;   /* sym[gate], gate from 1 */
  b->cruns = 1024; b->runs = calloc(b->cruns, sizeof(Run)); b->nruns = 0;
  b->cnr = 256; b->nr = calloc(b->cnr, sizeof(Neuron)); b->nnr = 0;
  b->arrival_of_third = is_main ? SIXTH : MAIN;
}
int label_gate(Brain *b, const char *sym){ if(!sym) return 0; return (int)hmap_get(&b->label.h, (i64)strhash(sym), 1); }   /* a NULL symbol names no gate (a join on a NULL key fell here, 2026-11-01) */
int label_new(Brain *b, const char *sym){
  int g = label_gate(b, sym); if(g) return g;
  g = ++b->label.n; if(g >= b->label.cap){ b->label.cap *= 2; b->label.sym = realloc(b->label.sym, b->label.cap * sizeof(char*)); }
  b->label.sym[g] = strdup(sym); hmap_put(&b->label.h, (i64)strhash(sym), 1, g);
  /* a symbol's gate exists before its region is born (as in v6 a label row exists before the gate's tables) */
  if(g >= b->cnr){ int oc = b->cnr; b->cnr = g * 2; b->nr = realloc(b->nr, b->cnr * sizeof(Neuron)); memset(b->nr + oc, 0, (b->cnr - oc) * sizeof(Neuron)); }
  if(g > b->nnr) b->nnr = g;
  return g;
}
Neuron *neuron_of(Brain *b, int gate){ if(gate <= 0 || gate >= b->cnr) return 0; return &b->nr[gate]; }
static i64 SHROWS[2];   /* the DNA rows each brain holds (the id counter b->shards never comes down) */
i64 nk_shard_rows(Brain *b){ return SHROWS[b->is_main]; }
void nk_count_rows(Brain *b){ i64 n = 0; for(int g = 1; g <= b->label.n; g++){ Neuron *x = neuron_of(b, g); if(x) n += x->nsh; } SHROWS[b->is_main] = n; }
Shard *shard_find(Brain *b, int gate, int before, int trigger){ Neuron *n = neuron_of(b, gate); if(!n || !n->born) return 0; i64 i = hmap_get(&n->h, before, trigger); return i ? &n->sh[i - 1] : 0; }
Shard *shard_lay(Brain *b, int gate, int before, int trigger, i64 times){
  Neuron *n = neuron_of(b, gate); if(!n) return 0;
  GROW(n->sh, n->nsh, n->csh, Shard);
  Shard *s = &n->sh[n->nsh++]; s->id = ++b->shards; s->before = before; s->trigger = trigger; s->call = 0; s->spawn = 0; s->times = times; s->changed_at = b->clock; SHROWS[b->is_main]++;
  hmap_put(&n->h, before, trigger, n->nsh); hmap_put(&b->shid, gate, s->id, n->nsh);
  return s;
}
/* the hop: one shard for every point. The owner (2026-11-01): "the function of the hop is one dna shard, it basically = spacebar in a sentence ...
   the trigger to go the hop meaning points to the same shard of dna for all points"; "a substitution shard ... that accepts the before and remainder
   as two variables". It is the space neuron's row (before and trigger both none: the variables come from the run itself). */
static i64 HOPID[2];
Shard *hop_shard(Brain *b){ Neuron *n = neuron_of(b, SPACE); if(!n) return 0; if(!n->born) n->born = 1; Shard *s = shard_find(b, SPACE, 0, 0); if(!s) s = shard_lay(b, SPACE, 0, 0, 0); HOPID[b->is_main] = s->id; return s; }
i64 hop_id(Brain *b){ if(!HOPID[b->is_main]) hop_shard(b); return HOPID[b->is_main]; }
Shard *shard_by_id(Brain *b, int gate, i64 id){ Neuron *n = neuron_of(b, gate); if(!n) return 0; i64 i = hmap_get(&b->shid, gate, id); if(i) return &n->sh[i - 1]; if(id == hop_id(b)) return hop_shard(b); return 0; }
Run *run_of(Brain *b, i64 id){ if(id <= 0 || id > b->nruns) return 0; return &b->runs[id]; }
i64 new_run(Brain *b, int arrival, i64 parent, int has_parent, int kind, int cell, int about){
  b->clock++;
  i64 id = ++b->nruns; if(id >= b->cruns){ i64 oc = b->cruns; b->cruns *= 2; b->runs = realloc(b->runs, b->cruns * sizeof(Run)); memset(b->runs + oc, 0, (b->cruns - oc) * sizeof(Run)); }
  Run *r = &b->runs[id]; memset(r, 0, sizeof(*r));
  r->arrival = arrival; r->parent_set = has_parent; r->parent = has_parent ? parent : 0; r->kind = kind; r->cell = cell; r->about = about;
  r->at = b->clock; r->moment = (i64)time(0); r->build_pos = -1;
  Run *p = has_parent ? run_of(b, parent) : 0; r->root = p ? p->root : id;
  if(p){ GROW(p->kids, p->nkids, p->ckids, i64); p->kids[p->nkids++] = id; }
  if(about){ Neuron *n = neuron_of(b, about); if(n){ GROW(n->about_runs, n->nabout, n->cabout, i64); n->about_runs[n->nabout++] = id; } }
  { Neuron *n = neuron_of(b, arrival); if(n){ GROW(n->arrived, n->narrived, n->carrived, i64); n->arrived[n->narrived++] = id; } }
  char v[32]; snprintf(v, sizeof v, "%lld", (long long)id); cell_set(b, id, ME, 1, v);
  if(has_parent){ snprintf(v, sizeof v, "%lld", (long long)parent); cell_set(b, id, ABOVE, 1, v); }
  return id;
}

/* ---------------- the sheet ---------------- */
static void complete_run(Brain *b, i64 run){
  Run *r = run_of(b, run); if(!r || r->complete) return; r->complete = 1;
  if(r->kind != 0) return;
  { int ok = label_gate(b, "ok"); if(ok) cell_set(b, run, ok, 1, "ok"); r = run_of(b, run); }   /* every cell populated: ok marks the sheet, so the brain knows */
  /* complete_go: the cells to the user's out mailbox, by cell */
  int order[1024], n = 0; for(int i = 0; i < r->ncells && n < 1024; i++) order[n++] = i;
  for(int i = 1; i < n; i++){ int k = order[i], j = i - 1; while(j >= 0 && r->cells[order[j]].cell > r->cells[k].cell){ order[j + 1] = order[j]; j--; } order[j + 1] = k; }
  for(int i = 0; i < n; i++){ Cell *c = &r->cells[order[i]]; GROW(b->out, b->nout, b->cout, Out); Out *o = &b->out[b->nout]; o->id = b->nout + 1; o->run = run; o->cell = c->cell; val_copy(&o->v, &c->v); b->nout++; }
}
/* the cells of a run by cell, as complete_run sends them (the tick's answer reads the sheet the first run left) */
static int *OUTC; static int OUTCAP;
void nk_out_of(Brain *b, i64 run, int **cells, int *n){
  Run *r = run_of(b, run); *n = 0; *cells = 0; if(!r) return;
  if(r->ncells > OUTCAP){ OUTCAP = r->ncells * 2 + 8; OUTC = realloc(OUTC, OUTCAP * sizeof(int)); }
  for(int i = 0; i < r->ncells; i++){ int k = i - 1; while(k >= 0 && r->cells[OUTC[k]].cell > r->cells[i].cell){ OUTC[k + 1] = OUTC[k]; k--; } OUTC[k + 1] = i; }
  *cells = OUTC; *n = r->ncells;
}
static int sheet_open(Run *r){ for(int i = 0; i < r->ncells; i++) if(r->cells[i].state == 0) return 1; return 0; }
int sheet_open_pub(Brain *b, i64 run){ Run *r = run_of(b, run); return r ? sheet_open(r) : 0; }
void cell_set(Brain *b, i64 run, int cell, int state, const char *value){
  Run *r = run_of(b, run); if(!r) return;
  Cell *c = 0; for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell){ c = &r->cells[i]; break; }
  if(!c){ GROW(r->cells, r->ncells, r->ccells, Cell); c = &r->cells[r->ncells++]; c->cell = cell; memset(&c->v, 0, sizeof c->v); }
  else val_free(&c->v);
  c->state = state; val_set(b, &c->v, value);
  if(state == 1 && r->kind == 0){ int ok = label_gate(b, "ok"); if(ok && cell != ok){ Shard *o = shard_find(b, ok, cell, 0); if(!o) o = shard_lay(b, ok, cell, 0, 0); if(o) o->times++; } }   /* ok listens: a row of the ok neuron for each cell, ticked when that cell populates */
  if(state == 1 && r->has_mem && !sheet_open(r)) complete_run(b, run);          /* sheet_fill */
}
const char *cell_get(Brain *b, i64 run, int cell){ Run *r = run_of(b, run); if(!r) return 0; for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell && r->cells[i].state == 1 && r->cells[i].v.kind) return val_text(b, &r->cells[i].v); return 0; }

/* ---------------- the hop stack ---------------- */
static void push(Brain *b, Hop h){ GROW(b->hop, b->nhop, b->chop, Hop); b->hop[b->nhop++] = h; }
int pending(Brain *b){ return (int)b->nhop; }
static void land(Brain *b, i64 run, int pos, int gate, int before, int next, int via);
static void hit(Brain *b, i64 run, int pos, int gate, int before, int next, int via, int had, Shard *s);
static void ended(Brain *b, i64 run, int gate, i64 shard);
static void replay(Brain *b, i64 parent, i64 source, int kind, i64 from_run, int from_ord);
static void dedupe_check(Brain *b, i64 run);

/* ---------------- the cut (the encoder) ---------------- */
static int is_letter(unsigned char c){ return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_'; }   /* C27 (the owner, 11-04 04:30): a word is one symbol in any script; a byte of a non-ascii letter no longer ends it */
static int u8len(unsigned char c){ if(c < 0x80) return 1; if((c >> 5) == 6) return 2; if((c >> 4) == 14) return 3; if((c >> 3) == 30) return 4; return 1; }
/* C27 (the owner, 11-04 04:30): a word is one symbol in any script. A character of another script continues the word; the punctuation of other
   scripts does not: U+0080-00BF (the Latin-1 symbols: middle dot, guillemets, degree) and U+2000-206F (quotes, dashes, the hyphenation point,
   the ellipsis). Returns the byte length of the letter at s, 0 when s does not begin a letter. */
static int letter_len(const unsigned char *s, size_t rem){
  if(!rem) return 0; unsigned char c = s[0];
  if(c < 0x80) return is_letter(c) ? 1 : 0;
  int n = u8len(c); if((size_t)n > rem) return 0;
  if(c == 0xC2) return 0;                                              /* U+0080-00BF */
  if(c == 0xE2 && n == 3 && (s[1] == 0x80 || s[1] == 0x81)) return 0;   /* U+2000-207F: general punctuation, super/subscripts kept out of a word? no: U+2070-207F are superscripts; keep them */
  return n;
}
/* GROW above for seq uses nseq as cap guard; give seq its own growth */
static void seq_push(Run *r, int g){ if(r->nseq % 8 == 0){ r->seq = realloc(r->seq, (r->nseq + 8) * sizeof(int)); } r->seq[r->nseq++] = g; }

static void cut2(Brain *b, i64 run, const char *text){
  Run *r = run_of(b, run); size_t i = 0, L = strlen(text); char buf[4096];
  while(i < L){
    size_t j = i;
    if(letter_len((const unsigned char*)text + i, L - i)){ int k; while(j < L && (k = letter_len((const unsigned char*)text + j, L - j))) j += k; }
    else j = i + u8len((unsigned char)text[i]);
    if(j > L) j = L;
    size_t n = j - i; if(n >= sizeof buf) n = sizeof buf - 1;
    memcpy(buf, text + i, n); buf[n] = 0;
    int g = label_gate(b, buf); if(!g) g = label_new(b, buf);
    seq_push(r, g); i = j;
  }
}
/* the encoder, for a value: a canonical number stays a number, a list of them stays numbers, anything else becomes gates */
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
  while(i < L){ size_t j = i; if(letter_len((const unsigned char*)s + i, L - i)){ int k; while(j < L && j - i < sizeof buf - 8 && (k = letter_len((const unsigned char*)s + j, L - j))) j += k; } else j = i + u8len((unsigned char)s[i]); if(j > L) j = L;
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
static i64 memkey2(Run *r){ return ((i64)r->arrival << 40) | ((i64)r->cell << 20) | (i64)r->about; }
/* the owner, 2026-11-11: "add two flags to the encoder that trip it a trigger changes on a dna shard.. that means the meaning of that shard has
   changed.. and the run data sheet will be different on that run. so the run has to be re run". The flags are the shard's changed_at and the brain's
   rewrite_at. A memory is unchanged when every function row its run hit is as it was, and no function row has been laid since on a point it only
   passed (the pass wrote no receipt: the before and next of each point follow from the seq, as in land). Read again only after a rewrite. */
static int shards_same(Brain *b, Run *cn){
  if(cn->ok_at > b->rewrite_at) return 1;
  for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; Shard *s = shard_by_id(b, k->gate, k->shard); if(!s || s->changed_at > cn->mem_at) return 0; }
  i64 hid = hop_id(b);
  for(int p = 1; p <= cn->nseq; p++){ int g = cn->seq[p - 1]; if(g == SPACE || g <= 0) continue;
    int kb = cn->arrival, kx = 0; for(int q = p - 1; q >= 1; q--) if(cn->seq[q - 1] != SPACE){ kb = cn->seq[q - 1]; break; }
    for(int q = p + 1; q <= cn->nseq; q++) if(cn->seq[q - 1] != SPACE){ kx = cn->seq[q - 1]; break; }
    Shard *s = shard_find(b, g, kb, kx); if(s && s->id != hid && (s->call || s->spawn) && s->changed_at > cn->mem_at) return 0; }
  cn->ok_at = b->clock; cn->ev_built = 0; return 1;
}
static inline int rc_ord(Run *r, int i){ return r->nrc == r->nhops ? i : r->rcs[i].ord; }   /* a run from before 11-11 holds every hop: its index is its ordinal */
/* a run whose symbols, arrival, cell and about repeat a run that already ended with its own receipts, hit no new word and whose shards have
   not been rewritten since, will hop exactly as that run did: it points at it (same_as), shares its seq and stores no receipts of its own */
static void dedupe_check(Brain *b, i64 run){
  Run *r = run_of(b, run); if(r->nseq == 0) return;
  i64 f = hmap_get(&b->memh, (i64)seqhash(r->seq, r->nseq), memkey2(r)); if(!f || f == run) return;
  Run *cn = run_of(b, f); if(!cn || !cn->has_mem || cn->same_as || !cn->clean || !cn->kept || cn->nhops == 0 || cn->nseq != r->nseq || !cn->seq) return;
  if(memcmp(cn->seq, r->seq, sizeof(int) * r->nseq) != 0) return;
  if(!shards_same(b, cn)) return;   /* read again only after a shard was rewritten */
  r->same_as = f; if(!r->seq_shared) free(r->seq); r->seq = cn->seq; r->seq_shared = 1; b->deduped++; cn->again++; /* counted when the repeat starts, not when it ends: it borrows cn's symbols from here on, and compaction leaves a run with again > 0 alone */
}
/* draft 3.2: a closed run repeated is "one hop to the memory. No rows fire, nothing is laid, and mother is not called"; the firings its first run found are what it does */
static void to_memory(Brain *b, i64 run){
  Run *r = run_of(b, run), *cn = run_of(b, r->same_as);
  if(!cn->ev_built){ cn->nev = 0; for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; Shard *s = shard_by_id(b, k->gate, k->shard); if(s && (s->call || s->spawn || (k->gate == BUILD && k->via == 0))){ GROW(cn->ev, cn->nev, cn->cev, Ev); Ev *e = &cn->ev[cn->nev++]; e->ord = rc_ord(cn, i); e->pos = k->pos; e->gate = k->gate; e->via = k->via; e->shard = k->shard; } } cn->ev_built = 1; }
  Hop h = {0}; h.type = HOP_FIRE; h.run = run; h.a = 0; push(b, h);
}
static void first_landing(Brain *b, i64 run){ Run *r = run_of(b, run); dedupe_check(b, run); if(r->nseq <= 0) return; if(r->same_as){ to_memory(b, run); return; } land(b, run, 0, r->arrival, 0, r->seq[0], 0); }

/* a line arriving at a prompt: input (heard) or third (the other brain) */
/* the repeat is a tick (the owner, 2026-10-03: "memories in a node that all should be the same until the truth changes, just get a timestamp and
   counter +1 for each new, and then truth change new row. also the full context of the memory is never duped, anywhere else a memory lives not is
   just a pointer to that memory"; 2026-10-06: "these long runs should be learned once... and never done again unless a step back is needed ... the
   only reason to rerun long runs ever are to reason . or if the truth has changed"; 2026-11-10: "a repeat sentance should only be storing the time,
   and project information ... it should be just another comma separated value in at most 3 cells"). A line at a prompt whose symbols and arrival
   repeat a memory whose shards are unchanged since makes no run: the memory counts it (again), its clock cell takes the time, its source cell takes
   the key (the marker run of typemark, 0 for none); the ear's mailbox and the timeline take a pointer to the memory. Nothing fires, nothing is laid,
   mother is not called, the sixth is not told. A line that opens a BUILD span asks mother, so it runs every time; a shard of the memory's receipt
   rewritten since is the truth changed, so the line runs and its run is the new row. */
i64 nk_last_tick;   /* the memory the last line at a prompt ticked; 0 when the line ran */
i64 nk_line_key;    /* the key the next line at a prompt carries (the marker run of typemark); line_in takes it and clears it */
i64 nk_line_time;   /* the time the next line at a prompt carries (typemark @time, for the record typed again from the copy); 0 = now */
int nk_last_arrival;   /* which arrival of its memory the last tick was, from 0 */
int nk_last_formula;   /* 1 when the last tick was a formula's arrival (the line read back = the memory's line with this arrival's values) */
static int file_under(Brain *b, i64 mem, i64 key, i64 when, const int *vars);
static int shards_same(Brain *b, Run *cn);
static void cut_into(Brain *b, const char *text, int **out, int *n);
static void cell_append(Run *r, int cell, i64 x){
  Cell *c = 0; for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell){ c = &r->cells[i]; break; }
  if(!c){ GROW(r->cells, r->ncells, r->ccells, Cell); c = &r->cells[r->ncells++]; c->cell = cell; memset(&c->v, 0, sizeof c->v); c->state = 1; c->v.kind = 1; c->v.u.num = (int)x; return; }   /* one value: a number, no list yet */
  if(c->v.kind == 1){ i64 old = c->v.u.num; c->v.u.g = malloc(sizeof(int)); c->v.u.g[0] = (int)old; c->v.n = 1; c->v.kind = 2; }
  else if(c->v.kind != 2){ val_free(&c->v); c->v.kind = 2; }
  c->state = 1; c->v.u.g = realloc(c->v.u.g, sizeof(int) * (c->v.n + 1)); c->v.u.g[c->v.n++] = (int)x;
}
/* the three cells (the owner, 2026-11-10 14:05: "a repeat sentance should only be storing the time, and project information? which I am assuming is the
   key ... just another comma separated value in at most 3 cells"; 16:12: "if we just add a couple or few of columns to the memory table then ...
   sentances that repeat could be stored as data similar to a file tree just by changing a cell (could be similar to a dropdown menu, or comma separate
   which ever prevents drift"). On the sentence's memory: time (when) and key (the memory of the marker line it arrived under, 0 for none), one value
   each per arrival, in step. On the key's memory: receipt, the memories filed under it, each once. Every value is a receipt number of a memory the
   brain holds (the dropdown: nothing else is ever written), so the lists cannot drift. A key line under a project line is filed the same way: the tree. */
static int word_gate(Brain *b, const char *w){ int g = label_gate(b, w); return g ? g : label_new(b, w); }
static int cell_holds(Run *r, int cell, i64 x){ for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell){ Val *v = &r->cells[i].v; if(v->kind == 1) return v->u.num == x; if(v->kind == 2) for(int j = 0; j < v->n; j++) if(v->u.g[j] == (int)x) return 1; return 0; } return 0; }
static int cell_there(Run *r, int cell){ for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell) return 1; return 0; }
static Val *cell_val(Run *r, int cell){ for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell) return &r->cells[i].v; return 0; }
static int val_n(const Val *v){ return !v ? 0 : v->kind == 1 ? 1 : v->kind == 2 ? v->n : 0; }
static int val_at(const Val *v, int i){ return v->kind == 1 ? (int)v->u.num : v->u.g[i]; }
/* the hippocampus's condense (the owner, 2026-10-09: "part of the hc job is to keep these reasonable and condense and store runs that have many many runs so
   that a memory table doesn't have 10k timestamps or a counter in the 100's of trillions if we have that many and the truth hasn't changed our belief in
   that row is extremly high but that particular row doesn't need all that information to tell us that"; 10-03: "we don't have memories with 50k
   rewrites ... we felt that 6-10 truth shifts were probably enough to hold in a memory neuron"). The same sentence under the same key keeps its
   HC_KEEP newest times; an older one drops off as the next arrives (at the arrival, on this memory alone: no pass, no timer). The count of every
   arrival stays on the memory (again). A formula's arrivals are other lines, each its own values: they are not condensed here. */
#define HC_KEEP 10
static void hc_condense(Run *m, int tg, int kg, i64 key){
  Val *kv = cell_val(m, kg), *tv = cell_val(m, tg); if(!kv || !tv || kv->kind != 2 || tv->kind != 2 || kv->n != tv->n || kv->n <= HC_KEEP) return;
  int n = kv->n, cnt = 0; for(int i = 0; i < n; i++) if(kv->u.g[i] == (int)key) cnt++;
  if(cnt <= HC_KEEP) return;
  int drop = cnt - HC_KEEP, w = 0; for(int i = 0; i < n; i++){ if(drop && kv->u.g[i] == (int)key){ drop--; continue; } kv->u.g[w] = kv->u.g[i]; tv->u.g[w] = tv->u.g[i]; w++; }
  kv->n = tv->n = w;
}
/* vars: the values of this arrival at the memory's variable places (a formula, below); 0 = the memory's own line (its own values) */
static int file_under(Brain *b, i64 mem, i64 key, i64 when, const int *vars){
  Run *m = run_of(b, mem); if(!m) return 0;
  int kg = word_gate(b, "key"), tg = word_gate(b, "time"), rg = word_gate(b, "receipt"), fg = label_gate(b, "formula"); m = run_of(b, mem);
  int filed = key ? cell_holds(m, kg, key) : 1, at = val_n(cell_val(m, tg));
  cell_append(m, tg, when); cell_append(m, kg, key);
  Val *f = fg ? cell_val(m, fg) : 0; int k = val_n(f);
  if(k){ int vg = word_gate(b, "variable"); m = run_of(b, mem); for(int j = 0; j < k; j++){ f = cell_val(m, fg); cell_append(m, vg, vars ? vars[j] : m->seq[val_at(f, j) - 1]); } }
  else hc_condense(m, tg, kg, key);
  Run *kr = key ? run_of(b, key) : 0; if(kr && !filed) cell_append(kr, rg, mem);
  return at;   /* which arrival of the memory this is, from 0 */
}
static i64 tick_of(Brain *b, int arrival, const int *seq, int n, i64 key){
  if(n <= 0) return 0;
  for(int i = 0; i < n; i++) if(seq[i] <= 0 || (seq[i] == BUILD && !key)) return 0;   /* a symbol with no gate: no memory holds the line; BUILD: the line asks mother (under a key it is content: a word like any other) */
  i64 f = hmap_get(&b->memh, (i64)seqhash(seq, n), (i64)arrival << 40); if(!f) return 0;   /* memkey2 of a line: its arrival, cell 0, about 0 */
  Run *cn = run_of(b, f); if(!cn || !cn->has_mem || cn->same_as || cn->kind != 0 || cn->nseq != n || !cn->seq || cn->nhops == 0) return 0;
  if(memcmp(cn->seq, seq, sizeof(int) * n) != 0) return 0;
  if(!shards_same(b, cn)) return 0;
  /* the owner, 2026-11-11: the shortcut is for "runs that don't have reasoning on them .... deterministic runs"; 2026-10-12 (330): "stays silent is a trap".
     A line whose words called a tool (a function row past the arrival) is asked again every time: it runs, by its memory's firings (same_as). */
  if(!key) for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; if(k->pos <= 0 || k->gate == BORN) continue; Shard *s = shard_by_id(b, k->gate, k->shard); if(s && (s->call || s->spawn)) return 0; }
  return f;
}
static void tick(Brain *b, i64 f, int which, i64 key, i64 when, const int *vars){
  Run *cn = run_of(b, f); b->clock++;
  int tg = word_gate(b, "time"); cn = run_of(b, f);
  if(!cell_there(cn, tg) && cn->mem_source != cn->arrival) file_under(b, f, cn->mem_source, cn->moment, 0);   /* a memory first heard under a key before the cells: that arrival, then this one. A first arrival with no key is the run's own row (its moment); the cells hold what came after */
  nk_last_arrival = file_under(b, f, key, when ? when : (i64)time(0), vars); cn = run_of(b, f);
  cn->again++; cn->last_at = b->clock; cn->last_run = f; b->deduped++;
  /* nothing else: no mailbox row, no timeline row. The owner, 2026-11-11: "run reciept 24 bytes fair the first time that run is used. from then on because
     of the run pointer which is like 4 bytes, and the fact that a new dupe of that run is just a time stamp and kind data... like maybe 15 bytes total".
     The time of a repeat is in the memory's time cell; the pointer is the key's receipt cell. */
}
/* ---------------- the formula: a line that is a learned line with a few other values ----------------
   The owner, 2026-11-10 14:05: "a learned run does not have to be rerun, it can just have a shortcut path, or better a formula shortcut path an entire
   sentance can be reduced to the formula gate and the varibles .... so thus a sentance that is used alot but has a couple different nouns, verbs, or
   adjectives doesn't have to be completely repeated it can just have a few values representing the entire sentance"; 2026-10-01: "Substitution theory
   is that I have a variable that I have to substitute into this formula. That's it. You already know the formula"; 2026-11-11: "long way, then
   shortcut, then formula for every fucking run not wait later".
   The long way: a new line runs once and is a memory. The shortcut: the same line again is a tick. The formula: a new line that has the same first and
   last symbol and the same length as a learned line (the two key words the timeline keeps of a memory, found by key in the encoder: no search), and
   differs from it in few places (at most half of its words: the formula is taken when it is the shorter way), makes no run. The learned line's
   memory takes the cell formula (the places that vary) and, per arrival, the cell variable (the values at those places), in step with time and key.
   The line is read back by putting the values into the learned line. A value must be a symbol the brain already holds as a point (a new word is
   born and defined the long way first). A line that asks a tool is never taken this way: it runs, every time (a function row on any of its
   points, or a span). At the bare prompt the line is answered with the sheet the learned line left (the owner, 10-01: "You don't have to run the
   entire hops all the way through. You already know it. The compute's already been done"; 330: "stays silent is a trap"). */
static i64 frame_key(int arrival, const int *seq, int n){ int k[3] = { seq[0], seq[n - 1], n }; (void)arrival; return (i64)seqhash(k, 3); }
#define FRAME_NS(arrival) ((i64)0x4600000000000000LL | (i64)(arrival))
static int *FVARS; static int FVCAP;
static void cell_put_list(Run *r, int cell, const int *vals, int n){
  Cell *c = 0; for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell){ c = &r->cells[i]; break; }
  if(!c){ GROW(r->cells, r->ncells, r->ccells, Cell); c = &r->cells[r->ncells++]; c->cell = cell; memset(&c->v, 0, sizeof c->v); } else val_free(&c->v);
  c->state = 1; c->v.kind = 2; c->v.n = n; c->v.u.g = malloc(sizeof(int) * (n ? n : 1)); if(n) memcpy(c->v.u.g, vals, sizeof(int) * n);
}
static i64 formula_of(Brain *b, int arrival, const int *seq, int n, i64 key, const int **vars){
  if(n < 3) return 0;
  for(int i = 0; i < n; i++) if(seq[i] <= 0 || (seq[i] == BUILD && !key)) return 0;
  i64 f = hmap_get(&b->memt, frame_key(arrival, seq, n), FRAME_NS(arrival)); if(!f) return 0;
  Run *cn = run_of(b, f); if(!cn || !cn->has_mem || cn->same_as || cn->kind != 0 || cn->parent_set || cn->arrival != arrival || cn->nseq != n || !cn->seq || cn->nhops == 0) return 0;
  if(!shards_same(b, cn)) return 0;
  if(!key){ /* at the bare prompt: the learned line asked no tool, and this line would ask none (no function row on any of its points, by its own before and next) */
    for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; if(k->pos <= 0 || k->gate == BORN) continue; Shard *s = shard_by_id(b, k->gate, k->shard); if(s && (s->call || s->spawn)) return 0; }
    for(int p = 1; p <= n; p++){ int g = seq[p - 1]; if(g == SPACE) continue; int kb = arrival, kx = 0; for(int q = p - 1; q >= 1; q--) if(seq[q - 1] != SPACE){ kb = seq[q - 1]; break; }
      for(int q = p + 1; q <= n; q++) if(seq[q - 1] != SPACE){ kx = seq[q - 1]; break; }
      Shard *s = shard_find(b, g, kb, kx); if(s && (s->call || s->spawn)) return 0; } }
  int fg = label_gate(b, "formula"); Val *fv = fg ? cell_val(cn, fg) : 0; int k = val_n(fv), words = 0, nd = 0;
  if(n > FVCAP){ FVCAP = n * 2 + 16; FVARS = realloc(FVARS, FVCAP * sizeof(int) * 3); }
  int *pos = FVARS + FVCAP, *all = FVARS + 2 * FVCAP;   /* the places that differ (1 based); the formula's places with them */
  for(int p = 1; p <= n; p++){ if(cn->seq[p - 1] != SPACE) words++; if(cn->seq[p - 1] != seq[p - 1]){ if(cn->seq[p - 1] == SPACE || seq[p - 1] == SPACE) return 0; pos[nd++] = p; } }
  if(nd == 0) return 0;
  /* the places: the formula's own, and any new place this line varies at (both lists ascend) */
  int na = 0, grew = 0; { int i = 0, j = 0; while(i < k || j < nd){ int x = i < k ? val_at(fv, i) : 0x7fffffff, y = j < nd ? pos[j] : 0x7fffffff; if(x == y){ all[na++] = x; i++; j++; } else if(x < y){ all[na++] = x; i++; } else { all[na++] = y; j++; grew = 1; } } }
  if(na * 2 > words) return 0;   /* the formula is taken when it is the shorter way: at most half of the words vary */
  for(int d = 0; d < na; d++){ int g = seq[all[d] - 1]; Neuron *x = neuron_of(b, g); if(!x || !x->born) return 0; }
  if(grew){ /* learned now, or a place more: the places, and for every arrival so far its values at them (a new place held the learned line's own word: the back population) */
    int tg = word_gate(b, "time"), vg = word_gate(b, "variable"); fg = word_gate(b, "formula"); cn = run_of(b, f); fv = cell_val(cn, fg);
    if(!cell_there(cn, tg) && cn->mem_source != cn->arrival){ file_under(b, f, cn->mem_source, cn->moment, 0); cn = run_of(b, f); fv = cell_val(cn, fg); }
    int had = val_n(cell_val(cn, tg)); Val *ov = cell_val(cn, vg); if(k && val_n(ov) != had * k) return 0;   /* the lists are not in step: leave it, the line runs the long way */
    int *nv = malloc(sizeof(int) * (had * na > 0 ? had * na : 1));
    for(int a = 0; a < had; a++){ int j = 0; for(int d = 0; d < na; d++){ while(j < k && val_at(fv, j) < all[d]) j++; nv[a * na + d] = (j < k && val_at(fv, j) == all[d]) ? val_at(ov, a * k + j) : cn->seq[all[d] - 1]; } }
    cell_put_list(cn, vg, nv, had * na); cell_put_list(cn, fg, all, na); free(nv); }
  for(int d = 0; d < na; d++) FVARS[d] = seq[all[d] - 1];
  *vars = FVARS; return f;
}
void line_in(Brain *b, int which, const char *text){
  int arrival = which == 0 ? HEARD : b->arrival_of_third;
  i64 key = nk_line_key, when = nk_line_time; nk_line_key = 0; nk_line_time = 0; nk_last_tick = 0;
  if(key >= 0) b->ndef++;   /* the lines heard at this prompt: a run, a tick or a formula's arrival (a marker line is not one). What ci/size divides the growth by. The field of the old pass: the layout stays */
  nk_last_arrival = 0; nk_last_formula = 0;
  { int *s, n; cut_into(b, text, &s, &n); int marker = key < 0; if(marker) key = 0;
    i64 f = tick_of(b, arrival, s, n, key);
    if(f && marker){ nk_last_tick = f; return; }   /* a marker line heard again only names its memory: nothing is written */
    if(f){ tick(b, f, which, key, when, 0); nk_last_tick = f; return; }
    const int *vars = 0; if(!marker) f = formula_of(b, arrival, s, n, key, &vars);
    if(f){ tick(b, f, which, key, when, vars); nk_last_tick = f; nk_last_formula = 1; return; } }
  i64 run = new_run(b, arrival, 0, 0, 0, 0, 0); run_of(b, run)->kept = 1; if(key) run_of(b, run)->mem_source = (int)key; if(when) run_of(b, run)->moment = when;
  Mail **box = which == 0 ? &b->input : &b->third; i64 *n = which == 0 ? &b->ninput : &b->nthird; i64 *c = which == 0 ? &b->cinput : &b->cthird;
  GROW(*box, *n, *c, Mail); Mail *m = &(*box)[*n]; m->id = *n + 1; m->text = 0; m->run = run; (*n)++;   /* the text is let go */
  cut2(b, run, text); first_landing(b, run);
}
/* a return: mother's or a source's answer, with the key */
void secondary_in(Brain *b, i64 run, int cell, int gate, int about, const char *text, i64 src){
  i64 id = new_run(b, gate, run, 1, 3, cell, about); Run *rr = run_of(b, id); rr->from_run = b->cur_run; rr->from_ord = b->cur_ord; rr->src = src; rr->srcgate = gate; rr->kept = 1;
  GROW(b->sec, b->nsec, b->csec, Sec); Sec *s = &b->sec[b->nsec]; s->id = b->nsec + 1; s->run = run; s->cell = cell; s->gate = gate; s->about = about; s->text = 0; s->made = id; s->src = src; b->nsec++;
  /* the owner, 2026-11-01: a define goes "to the fucking sources... pull the fucking information to the run data sheet"; "walkers are illegal"; draft 4.2 "pulled",
     "compares", "builds the definition table". A return is cut by the encoder into gates and arrives on the sheet. It is not stepped through the neurons. */
  cut2(b, id, text ? text : ""); rr = run_of(b, id);
  if(rr->nseq > 0){ Hop h = {0}; h.type = HOP_ENDED; h.run = id; h.gate = rr->seq[rr->nseq - 1]; h.a = 0; push(b, h); }
}
static void replay_push_from(Brain *b, i64 parent, i64 source, int kind, i64 from_run, int from_ord){ Hop h = {0}; h.type = HOP_REPLAY; h.run = parent; h.a = source; h.kind = kind; h.from_run = from_run; h.from_ord = from_ord; push(b, h); }
void replay_push(Brain *b, i64 parent, i64 source, int kind){ replay_push_from(b, parent, source, kind, b->cur_run, b->cur_ord); }
static void replay(Brain *b, i64 parent, i64 source, int kind, i64 from_run, int from_ord){
  i64 id = new_run(b, SAID, parent, 1, kind, 0, 0);
  Run *src = run_of(b, source), *r = run_of(b, id); r->from_run = from_run; r->from_ord = from_ord; r->replay_src = source; r->kept = 1;
  if(src && src->seq){ r->seq = src->seq; r->nseq = src->nseq; r->seq_shared = 1; }   /* the formula is held once */
  dedupe_check(b, id);
  if(r->nseq > 0 && r->same_as){ to_memory(b, id); return; }
  if(r->nseq > 0){ Hop h = {0}; h.type = HOP_LAND; h.run = id; h.pos = 0; h.gate = SAID; h.before = 0; h.next = r->seq[0]; h.via = 0; push(b, h); }
}

/* ---------------- the landing and the hit (land_go, hit_go) ---------------- */
static void land(Brain *b, i64 run, int pos, int gate, int before, int next, int via){
  Run *r = run_of(b, run); if(!r) return;
  int kb = 0, kx = 0;
  if(!(pos == 0 || via == 1 || gate == SPACE)){
    kb = r->arrival; for(int p = pos - 1; p >= 1; p--) if(r->seq[p - 1] != SPACE){ kb = r->seq[p - 1]; break; }
    for(int p = pos + 1; p <= r->nseq; p++) if(r->seq[p - 1] != SPACE){ kx = r->seq[p - 1]; break; }
  }
  { int np = pos + 1; while(np <= r->nseq && r->seq[np - 1] == SPACE) np++; next = np <= r->nseq ? r->seq[np - 1] : 0; }   /* the space is the hop: the run steps from symbol to symbol */
  Neuron *n = neuron_of(b, gate);
  if(!n || !n->born){ /* a landing on a gate with no region: as v6's paste into a missing table, the step is refused and the run stalls */
    GROW(b->ref, b->nref, b->cref, Refused); Refused *f = &b->ref[b->nref]; f->id = b->nref + 1; char t[128]; snprintf(t, sizeof t, "land run %lld pos %d gate %d", (long long)run, pos, gate); memset(&f->text, 0, sizeof f->text); memset(&f->error, 0, sizeof f->error); val_set(b, &f->text, t); val_set(b, &f->error, "no such neuron"); b->nref++; b->refused_n++; return; }
  Shard *s = shard_find(b, gate, kb, kx);
  if(!s) s = hop_shard(b);   /* no function row of its own for this before and next: the hop, one shard for every point; nothing is laid for a pass */
  s->times++;
  if(!(pos == 0 || via == 1 || gate == SPACE)) nk_xyz_land(b, gate, s->id, kb, kx, run, pos);   /* the place: a shard used on the point with another before or next than its last use moves it by its relationships (nkxyz.c) */
  int had = 0; if(next){ Neuron *nn = neuron_of(b, next); had = (nn && nn->born) ? 1 : 0; }
  hit(b, run, pos, gate, before, next, via, had, s);
}
static char *decode_span(Brain *b, i64 run, int from_pos, int to_pos){
  Run *r = run_of(b, run); size_t cap = 1024, len = 0; char *out = malloc(cap); out[0] = 0;
  i64 parent = r->parent_set ? r->parent : 0; Run *pr = parent ? run_of(b, parent) : 0; i64 gp = (pr && pr->parent_set) ? pr->parent : 0;
  for(int p = from_pos + 1; p < to_pos; p++){
    int g = r->seq[p - 1]; const char *piece = cell_get(b, run, g);
    if(!piece && parent) piece = cell_get(b, parent, g);
    if(!piece && gp) piece = cell_get(b, gp, g);
    if(!piece) piece = b->label.sym[g];
    size_t pl = strlen(piece); if(len + pl + 1 > cap){ while(len + pl + 1 > cap) cap *= 2; out = realloc(out, cap); }
    memcpy(out + len, piece, pl); len += pl; out[len] = 0;
  }
  return out;
}
static void build_gate(Brain *b, i64 run, int pos, int ord){
  Run *r = run_of(b, run);
    if(r->build_pos < 0) r->build_pos = pos;
    else {
      int from = r->build_pos; r->build_pos = -1;
      /* C28 (the owner, 11-04 05:00): a hand laid symbol in this span, an uppercase word whose lowercase twin is a defined point, merges into the twin */
      for(int p = from + 1; p < pos; p++){ int g = r->seq[p - 1]; if(g <= 0 || g > b->label.n) continue; const char *s = b->label.sym[g]; size_t L = strlen(s); if(L < 2) continue;
        int up = 1; for(size_t i = 0; i < L; i++) if(s[i] < 'A' || s[i] > 'Z'){ up = 0; break; } if(!up) continue;
        char lo[256]; if(L >= sizeof lo) continue; for(size_t i = 0; i <= L; i++) lo[i] = s[i] >= 'A' && s[i] <= 'Z' ? s[i] + 32 : s[i];
        int t = label_gate(b, lo); if(!t || t == g) continue; Neuron *tn = neuron_of(b, t); if(!tn || !tn->nnode) continue;
        char out[512]; nk_merge(b, g, t, out, sizeof out); }
      char *text = decode_span(b, run, from, pos);
      i64 save_run = b->cur_run; int save_ord = b->cur_ord; b->cur_run = run; b->cur_ord = ord;
      i64 t0 = now_ns(); char *ans = mother_paste(text); free(text); b->paste_ns += now_ns() - t0; b->pastes++;
      secondary_in(b, run, REPLY, MOTHER, 0, ans, 0); free(ans);      /* her answer arrives from mother, for the reply cell, under this run */
      b->cur_run = save_run; b->cur_ord = save_ord;
    }
}
static void hit(Brain *b, i64 run, int pos, int gate, int before, int next, int via, int had, Shard *s){
  Run *r = run_of(b, run); int ord = r->nhops++;
  ++b->hops_done;
  /* a line that arrived under a key is content, not a command (the owner, 2026-09-25: the encoder "delivers the data and the sensory metadata ... the
     pertaining to what"; 2026-10-11: "how you arrive determines which dna row are availible to pick from"): past its arrival row its words fire no
     tool and open no span. A new word is still born and defined. */
  int data = (pos > 0 && gate != BORN && r->kind == 0 && !r->parent_set && r->mem_source != 0);
  if(!r->same_as){
    /* the receipt, on the run. The owner, 2026-10-01: "the fucking memory is a fucking run reciept... one long string of numbers"; 2026-11-11: "the
       receipt is the dupe... it's only written at the end of a run". The string of numbers is the run's seq. A plain pass (the hop shard: no row of
       its own, nothing fired, nothing born) repeats it, so it writes nothing; only a hop that hit a row of its own, fired or bore is written. */
    int plain = (via == 0 && pos > 0 && s->id == hop_id(b) && !s->call && !s->spawn && gate != BUILD && (had == 1 || next == 0));
    if(plain) b->last_compacted++;   /* the passes that wrote no receipt (the field of the old pass, which is gone: the layout stays) */
    if(!plain){ GROW(r->rcs, r->nrc, r->crc, Rc); Rc *c = &r->rcs[r->nrc++]; c->pos = pos; c->gate = gate; c->shard = s->id; c->via = (unsigned char)via; c->had = (unsigned char)had; c->ord = ord; }
    if(s->call || s->spawn){ GROW(b->hit, b->nhit, b->chit, Hit); Hit *h = &b->hit[b->nhit]; h->run = run; h->ord = ord; h->pos = pos; h->gate = gate; h->before = before; h->next = next; h->via = via; h->had = had; h->shard = s->id; h->call = s->call; h->spawn = s->spawn; hmap_put(&b->hith, run, ord, b->nhit + 1); Neuron *ng = neuron_of(b, gate); if(ng){ GROW(ng->hits, ng->nhits, ng->chits, i64); ng->hits[ng->nhits++] = b->nhit; } b->nhit++; }
  }
  /* the steps, pushed in hit_go's order; the one pushed last runs first */
  if(next == 0 && via == 0){ Hop h = {0}; h.type = HOP_ENDED; h.run = run; h.gate = gate; h.a = s->id; push(b, h); }
  if(next != 0 && (via == 1 || had == 1)){ int np = pos + 1; while(np <= r->nseq && r->seq[np - 1] == SPACE) np++; int nn = np + 1; while(nn <= r->nseq && r->seq[nn - 1] == SPACE) nn++; Hop h = {0}; h.type = HOP_LAND; h.run = run; h.pos = np; h.gate = next; h.before = via == 1 ? before : gate; h.next = nn <= r->nseq ? r->seq[nn - 1] : 0; h.via = 0; push(b, h); }
  if(next != 0 && via == 0 && had == 0){
    char v[32]; snprintf(v, sizeof v, "%d", next); cell_set(b, run, NEWGATE, 1, v);
    Hop h = {0}; h.type = HOP_LAND; h.run = run; h.pos = pos; h.gate = BORN; h.before = gate; h.next = next; h.via = 1; push(b, h);
  }
  if(s->spawn && !data) replay_push_from(b, run, s->spawn, 2, run, ord);
  if(s->call && !data) replay_push_from(b, run, s->call, 1, run, ord);
  if(gate == BUILD && via == 0 && !data) build_gate(b, run, pos, ord);
}
/* a closed run repeated: its firings in order, nothing else; the next one waits under what this one fires, as in hit_go's order */
static void fire(Brain *b, i64 run, int i){
  Run *r = run_of(b, run), *cn = r ? run_of(b, r->same_as) : 0; if(!cn) return;
  if(i >= cn->nev){ r->nhops = cn->nhops; Hop h = {0}; h.type = HOP_ENDED; h.run = run; h.gate = cn->mem_gate; h.a = cn->mem_shard; push(b, h); return; }
  Ev e = cn->ev[i]; ++b->hops_done;
  Hop h = {0}; h.type = HOP_FIRE; h.run = run; h.a = i + 1; push(b, h);
  Shard *s = shard_by_id(b, e.gate, e.shard);
  if(e.pos > 0 && e.gate != BORN && r->kind == 0 && !r->parent_set && r->mem_source != 0) return;   /* under a key the line is content (see hit) */
  if(s && s->spawn) replay_push_from(b, run, s->spawn, 2, run, e.ord);
  if(s && s->call) replay_push_from(b, run, s->call, 1, run, e.ord);
  if(e.gate == BUILD && e.via == 0) build_gate(b, run, e.pos, e.ord);
}
/* ---------------- the end of a run (ended_go, memory_go, the node, complete) ---------------- */
/* the hippocampus's drop-off (the owner: "the hc is important to control bloat at scale, it decides what becomes what type of memory, and how it's store,
   what is pruned"; nk.h: a sub-run's receipts "are process and go when its main run completes"). The kernel of 10-31 did this as a pass over the runs;
   the pass was taken out on 11-01 with the sweeps and nothing took its place, so process receipts stayed for good. Here it is done at the line's own
   end, by the line's own tree (its kids lists: no pass, no timer): a run under the line that ended keeps its receipts only while it is the pattern
   later runs repeat (the encoder's entry for its symbols names it, or a repeat already points at it). Its stub, its sheet and its symbols stay. */
static void let_go(Brain *b, i64 line){
  Run *r = run_of(b, line); if(!r || !r->nkids) return;
  int cap = 64, n = 0; i64 *stk = malloc(sizeof(i64) * cap);
  for(int i = 0; i < r->nkids; i++){ if(n == cap){ cap *= 2; stk = realloc(stk, sizeof(i64) * cap); } stk[n++] = r->kids[i]; }
  while(n){ i64 id = stk[--n]; Run *s = run_of(b, id); if(!s) continue;
    for(int i = 0; i < s->nkids; i++){ if(n == cap){ cap *= 2; stk = realloc(stk, sizeof(i64) * cap); } stk[n++] = s->kids[i]; }
    if(!s->ended || s->kind == 0 || !s->nrc || s->again > 0) continue;
    if(s->seq && s->nseq && hmap_get(&b->memh, (i64)seqhash(s->seq, s->nseq), memkey2(s)) == id) continue;
    free(s->rcs); s->rcs = 0; s->crc = 0; b->dropped_receipts += s->nrc; s->nrc = 0; s->kept = 0;
    if(s->ev){ free(s->ev); s->ev = 0; s->nev = 0; s->cev = 0; s->ev_built = 0; } }
  free(stk);
}
static void ended(Brain *b, i64 run, int gate, i64 shard){
  Run *r = run_of(b, run); if(!r || r->ended) return; r->ended = 1;
  if(r->same_as){
    /* a repeat: one tick and a time stamp on the run it repeats; no row of its own */
    Run *cn = run_of(b, r->same_as); if(cn){ cn->last_at = r->at; cn->last_run = run; } r->has_mem = 1;
    if(r->kind == 0 && !r->parent_set && r->mem_source){ i64 key = r->mem_source, when = r->moment, mem = r->same_as; Run *m = run_of(b, mem); if(m && !cell_there(m, word_gate(b, "time"))){ m = run_of(b, mem); if(m->mem_source != m->arrival) file_under(b, mem, m->mem_source, m->moment, 0); } file_under(b, mem, key, when, 0); r = run_of(b, run); }   /* a line under a key that ran again (its truth is the same): filed on its memory */
  } else {
    /* the memory: the line as gates, who it arrived from, the ending gate and shard, the clock */
    if(!r->mem_source) r->mem_source = r->arrival; r->mem_gate = gate;   /* typemark (11-10) sets the marker before the run ends */ r->mem_shard = shard; r->mem_at = r->at; r->has_mem = 1; r->last_at = r->at; r->last_run = run;
    r->clean = 1; for(int i = 0; i < r->nrc; i++) if(r->rcs[i].via){ r->clean = 0; break; }
    i64 sh = (i64)seqhash(r->seq, r->nseq);
    i64 was = hmap_get(&b->memh, sh, memkey2(r));
    hmap_put(&b->memh, sh, memkey2(r), run);                                /* the newest run that ended with its own receipts: what a repeat points at */
    if(was && was != run){ Run *w = run_of(b, was); if(w && w->kind != 0 && w->ended && w->again == 0 && w->nrc){ free(w->rcs); w->rcs = 0; w->crc = 0; b->dropped_receipts += w->nrc; w->nrc = 0; w->kept = 0; if(w->ev){ free(w->ev); w->ev = 0; w->nev = 0; w->cev = 0; w->ev_built = 0; } } r = run_of(b, run); }   /* the hippocampus: a process pattern no run repeated, now replaced, lets go of its receipts */
    if(r->kind == 0 && !r->parent_set && r->nseq >= 3){ i64 fk = frame_key(r->arrival, r->seq, r->nseq); i64 cur = hmap_get(&b->memt, fk, FRAME_NS(r->arrival)); Run *c = cur ? run_of(b, cur) : 0; int fg = label_gate(b, "formula"); if(!c || !fg || !cell_there(c, fg)) hmap_put(&b->memt, fk, FRAME_NS(r->arrival), run); r = run_of(b, run); }   /* the learned line of its frame (first symbol, last symbol, length): the newest, until one is a formula */
    r->mem_sibling = hmap_get(&b->memt, sh, 0); hmap_put(&b->memt, sh, 0, run);   /* the chain of memory rows with these symbols, the newest first */
    Neuron *ng = neuron_of(b, gate); if(ng && r->kind == 0){ GROW(ng->mem_runs, ng->nmem, ng->cmem, i64); ng->mem_runs[ng->nmem++] = run; }
    if(r->kind == 0 && !r->parent_set && r->mem_source != r->arrival){ file_under(b, run, r->mem_source, r->moment, 0); r = run_of(b, run); }   /* a new line under a key: its first time and key, and the key's receipt */
  }
  /* memory_go: the timeline, then the other brain is told a prompt's run ended */
  GROW(b->tl, b->ntl, b->ctl, Tl); Tl *t = &b->tl[b->ntl++]; t->at = r->at; t->run = run; t->key1 = r->nseq ? r->seq[0] : 0; t->key2 = r->nseq ? r->seq[r->nseq - 1] : 0;
  if(r->kind == 0 && b->tell){ char line[64]; snprintf(line, sizeof line, "seen : %lld", (long long)run); line_in(b->tell, 1, line); }
  /* a return fills the cell it was asked for, on the run that asked */
  if(r->cell && r->parent_set){ char v[32]; snprintf(v, sizeof v, "%lld", (long long)run); cell_set(b, r->parent, r->cell, 1, v); }
  /* and lands a row in the definition node of the gate it is about */
  if(r->about && !r->same_as){ Neuron *n = neuron_of(b, r->about); if(n){ if(n->nnode == 0) b->dropped_runs++; GROW(n->node, n->nnode, n->cnode, NodeRow); n->node[n->nnode].source = r->arrival; n->node[n->nnode].run = run; n->nnode++; } }
  if(!sheet_open(r)) complete_run(b, run);
  /* a closed line lets go of the gates of its returns: the source row holds them. By the line's own kids, at its end: no sweep */
  r = run_of(b, run); if(r->kind == 0) for(int i = 0; i < r->nkids; i++){ Run *k = run_of(b, r->kids[i]); if(k && k->ended && k->src && k->seq && !k->seq_shared){ free(k->seq); k->seq = 0; k->kept = 0; } }
  if(r->kind == 0 && !r->parent_set) let_go(b, run);
}

/* ---------------- the pump of one brain: n steps of its stack, the newest first ---------------- */
void pump_batch(Brain *b, int n){
  while(n-- > 0 && b->nhop > 0){
    Hop h = b->hop[--b->nhop]; i64 t0 = now_ns();
    switch(h.type){
      case HOP_LAND: land(b, h.run, h.pos, h.gate, h.before, h.next, h.via); break;
      case HOP_ENDED: ended(b, h.run, h.gate, h.a); break;
      case HOP_REPLAY: replay(b, h.run, h.a, h.kind, h.from_run, h.from_ord); break;
      case HOP_FIRE: fire(b, h.run, (int)h.a); break;
    }
    b->hop_ns += now_ns() - t0; b->hops_run++;
  }
}

static int *SEQBUF; static int SEQCAP;
static void cut_into(Brain *b, const char *text, int **out, int *n){
  size_t i = 0, L = strlen(text); char buf[4096]; *n = 0;
  while(i < L){ size_t j = i; if(letter_len((const unsigned char*)text + i, L - i)){ int k; while(j < L && (k = letter_len((const unsigned char*)text + j, L - j))) j += k; } else j = i + u8len((unsigned char)text[i]); if(j > L) j = L;
    size_t m = j - i; if(m >= sizeof buf) m = sizeof buf - 1; memcpy(buf, text + i, m); buf[m] = 0;
    if(*n >= SEQCAP){ SEQCAP = SEQCAP ? SEQCAP * 2 : 4096; SEQBUF = realloc(SEQBUF, SEQCAP * sizeof(int)); } SEQBUF[(*n)++] = label_gate(b, buf); i = j; }
  *out = SEQBUF;
}
static int *HSEQ; static int HSEQCAP;
const int *nk_seq(Brain *b, i64 run, int *n){
  if(NK_ARR(run) > 0){ /* an arrival of a formula: the learned line with this arrival's values at its places (the owner: "I have a variable that I have to substitute into this formula") */
    i64 m = NK_MEM(run); int a = NK_ARR(run) - 1; const int *base = nk_seq(b, m, n); Run *cn = run_of(b, m); if(cn && cn->same_as) cn = run_of(b, cn->same_as);
    int fg = label_gate(b, "formula"), vg = label_gate(b, "variable"); Val *f = (cn && fg) ? cell_val(cn, fg) : 0, *v = (cn && vg) ? cell_val(cn, vg) : 0; int k = val_n(f);
    if(!base || !k || (a + 1) * k > val_n(v)) return base;
    if(*n > HSEQCAP){ HSEQCAP = *n * 2 + 16; HSEQ = realloc(HSEQ, HSEQCAP * sizeof(int)); }
    memcpy(HSEQ, base, sizeof(int) * *n); for(int j = 0; j < k; j++){ int p = val_at(f, j); if(p >= 1 && p <= *n) HSEQ[p - 1] = val_at(v, a * k + j); }
    return HSEQ; }
  Run *r = run_of(b, run); if(!r){ *n = 0; return 0; }
  if(r->same_as && r->same_as != run) return nk_seq(b, r->same_as, n);   /* a repeat's symbols are the pattern's */
  if(r->seq || r->nseq == 0){ *n = r->seq ? r->nseq : 0; return r->seq; }
  if(r->replay_src && r->replay_src != run) return nk_seq(b, r->replay_src, n);
  if(r->src && r->srcgate){ const char *t = nk_source_text(r->srcgate, r->src); if(t){ int *s; cut_into(b, t, &s, n); return s; } }
  *n = 0; return 0;
}

/* C27 (the owner, 11-04 04:30): a return is re-cut from its source row at every read (nk_seq); after the encoder changed, a symbol never seen
   whole has no gate and reads as 0. The back population gives every symbol of the held rows a gate under the encoder as it stands. */
int nk_learn_text(Brain *b, const char *s){
  size_t i = 0, L = strlen(s); char buf[4096]; int born = 0;
  while(i < L){ size_t j = i; if(letter_len((const unsigned char*)s + i, L - i)){ int k; while(j < L && j - i < sizeof buf - 8 && (k = letter_len((const unsigned char*)s + j, L - j))) j += k; } else j = i + u8len((unsigned char)s[i]); if(j > L) j = L;
    size_t m = j - i; memcpy(buf, s + i, m); buf[m] = 0; if(!label_gate(b, buf)){ label_new(b, buf); born++; } i = j; }
  return born;
}
/* C28 (the owner, 11-04 05:00): "the hand laid neurons dna tables and memories should merge with the correct neuron for that word ... the dna
   table of the real gate just adds the dna table of the hand laid, since the rows are numbered in sequence you don't even have to change the
   dna shard numbers ... the memory tables attached or pointed to that shard should just follow". The symbol of h names t from now on; gate h
   keeps its text so the rows already laid still read; a shard of h whose key (before, trigger) t already holds stays with t's own. */
int nk_merge(Brain *b, int h, int t, char *out, size_t cap){
  if(h <= 0 || t <= 0 || h == t || h > b->label.n || t > b->label.n){ snprintf(out, cap, "error: gates %d and %d", h, t); return -1; }
  Neuron *H = neuron_of(b, h), *T = neuron_of(b, t); if(!H || !T){ snprintf(out, cap, "error: no neuron for %d or %d", h, t); return -1; }
  if(!T->born) T->born = 1;
  int moved = 0, kept = 0;
  for(int i = 0; i < H->nsh; i++){ Shard *s = &H->sh[i]; if(hmap_get(&T->h, s->before, s->trigger)){ kept++; continue; }
    GROW(T->sh, T->nsh, T->csh, Shard); T->sh[T->nsh++] = *s; hmap_put(&T->h, s->before, s->trigger, T->nsh); hmap_put(&b->shid, t, s->id, T->nsh); moved++; }
  int nodes = H->nnode, mems = H->nmem, about = H->nabout, hits = H->nhits, arrived = H->narrived;
  for(int i = 0; i < H->nnode; i++){ GROW(T->node, T->nnode, T->cnode, NodeRow); T->node[T->nnode++] = H->node[i]; }
  for(int i = 0; i < H->nmem; i++){ GROW(T->mem_runs, T->nmem, T->cmem, i64); T->mem_runs[T->nmem++] = H->mem_runs[i]; }
  for(int i = 0; i < H->nabout; i++){ GROW(T->about_runs, T->nabout, T->cabout, i64); T->about_runs[T->nabout++] = H->about_runs[i]; }
  for(int i = 0; i < H->nhits; i++){ GROW(T->hits, T->nhits, T->chits, i64); T->hits[T->nhits++] = H->hits[i]; }
  for(int i = 0; i < H->narrived; i++){ GROW(T->arrived, T->narrived, T->carrived, i64); T->arrived[T->narrived++] = H->arrived[i]; }
  H->nsh = 0; H->nnode = 0; H->nmem = 0; H->nabout = 0; H->nhits = 0; H->narrived = 0; H->born = 0;
  hmap_put(&b->label.h, (i64)strhash(b->label.sym[h]), 1, t);
  snprintf(out, cap, "merged %s %d into %s %d: shards %d moved, %d kept by the twin, node rows %d, memories %d, about %d, hits %d, arrived %d", b->label.sym[h], h, b->label.sym[t], t, moved, kept, nodes, mems, about, hits, arrived);
  return 0;
}
static Rc *RCBUF; static int RCCAP;
int nk_receipts(Brain *b, i64 run, Rc **out, int *kept){
  Run *r = run_of(b, run); if(!r){ *out = 0; *kept = 0; return 0; }
  if(r->same_as){ Run *cn = run_of(b, r->same_as); if(cn) r = cn; }
  if(!r->kept && !r->nrc){ *out = 0; *kept = 0; return 0; }   /* a closed sub-run has no receipt and none is rebuilt: the main run's receipt and sheet are its memory */
  if(r->nrc == r->nhops || !r->seq){ *out = r->rcs; *kept = 1; return r->nrc; }
  /* re-stepped: the arrival, then each symbol that is not the space, in order; a written hop stands at its ordinal; every other hop was a plain pass */
  if(r->nhops > RCCAP){ RCCAP = r->nhops * 2 + 16; RCBUF = realloc(RCBUF, RCCAP * sizeof(Rc)); }
  i64 hid = hop_id(b); int e = 0, p = 0, last = 0; for(int q = r->nseq; q >= 1; q--) if(r->seq[q - 1] != SPACE){ last = q; break; }
  for(int o = 0; o < r->nhops; o++){
    if(e < r->nrc && r->rcs[e].ord == o){ RCBUF[o] = r->rcs[e]; if(!r->rcs[e].via) p = r->rcs[e].pos; e++; continue; }
    int np = p + 1; while(np <= r->nseq && r->seq[np - 1] == SPACE) np++; if(np > r->nseq) np = r->nseq; p = np;
    Rc *c = &RCBUF[o]; c->pos = p; c->gate = p >= 1 ? r->seq[p - 1] : r->arrival; c->shard = hid; c->via = 0; c->had = (unsigned char)(p == last ? 0 : 1); c->ord = o; }
  *out = RCBUF; *kept = 1; return r->nhops;
}
