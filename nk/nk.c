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
static int is_letter(unsigned char c){ return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_'; }
static int u8len(unsigned char c){ if(c < 0x80) return 1; if((c >> 5) == 6) return 2; if((c >> 4) == 14) return 3; if((c >> 3) == 30) return 4; return 1; }
/* GROW above for seq uses nseq as cap guard; give seq its own growth */
static void seq_push(Run *r, int g){ if(r->nseq % 8 == 0){ r->seq = realloc(r->seq, (r->nseq + 8) * sizeof(int)); } r->seq[r->nseq++] = g; }

static void cut2(Brain *b, i64 run, const char *text){
  Run *r = run_of(b, run); size_t i = 0, L = strlen(text); char buf[4096];
  while(i < L){
    size_t j = i;
    if(is_letter((unsigned char)text[i])){ while(j < L && is_letter((unsigned char)text[j])) j++; }
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
static i64 memkey2(Run *r){ return ((i64)r->arrival << 40) | ((i64)r->cell << 20) | (i64)r->about; }
/* a run whose symbols, arrival, cell and about repeat a run that already ended with its own receipts, hit no new word and whose shards have
   not been rewritten since, will hop exactly as that run did: it points at it (same_as), shares its seq and stores no receipts of its own */
static void dedupe_check(Brain *b, i64 run){
  Run *r = run_of(b, run); if(r->nseq == 0) return;
  i64 f = hmap_get(&b->memh, (i64)seqhash(r->seq, r->nseq), memkey2(r)); if(!f || f == run) return;
  Run *cn = run_of(b, f); if(!cn || !cn->has_mem || cn->same_as || !cn->clean || !cn->kept || cn->nrc == 0 || cn->nseq != r->nseq || !cn->seq) return;
  if(memcmp(cn->seq, r->seq, sizeof(int) * r->nseq) != 0) return;
  if(cn->ok_at <= b->rewrite_at){ for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; Shard *s = shard_by_id(b, k->gate, k->shard); if(!s || s->changed_at > cn->mem_at) return; } cn->ok_at = b->clock; cn->ev_built = 0; }   /* read again only after a shard was rewritten */
  r->same_as = f; if(!r->seq_shared) free(r->seq); r->seq = cn->seq; r->seq_shared = 1; b->deduped++; cn->again++; /* counted when the repeat starts, not when it ends: it borrows cn's symbols from here on, and compaction leaves a run with again > 0 alone */
}
/* draft 3.2: a closed run repeated is "one hop to the memory. No rows fire, nothing is laid, and mother is not called"; the firings its first run found are what it does */
static void to_memory(Brain *b, i64 run){
  Run *r = run_of(b, run), *cn = run_of(b, r->same_as);
  if(!cn->ev_built){ cn->nev = 0; for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; Shard *s = shard_by_id(b, k->gate, k->shard); if(s && (s->call || s->spawn || (k->gate == BUILD && k->via == 0))){ GROW(cn->ev, cn->nev, cn->cev, Ev); Ev *e = &cn->ev[cn->nev++]; e->ord = i; e->pos = k->pos; e->gate = k->gate; e->via = k->via; e->shard = k->shard; } } cn->ev_built = 1; }
  Hop h = {0}; h.type = HOP_FIRE; h.run = run; h.a = 0; push(b, h);
}
static void first_landing(Brain *b, i64 run){ Run *r = run_of(b, run); dedupe_check(b, run); if(r->nseq <= 0) return; if(r->same_as){ to_memory(b, run); return; } land(b, run, 0, r->arrival, 0, r->seq[0], 0); }

/* a line arriving at a prompt: input (heard) or third (the other brain) */
void line_in(Brain *b, int which, const char *text){
  int arrival = which == 0 ? HEARD : b->arrival_of_third;
  i64 run = new_run(b, arrival, 0, 0, 0, 0, 0); run_of(b, run)->kept = 1;
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
  if(!(pos == 0 || via == 1 || gate == SPACE)) nk_xyz_land(b, gate, s->id, kb, kx, run);   /* the place: a shard used on the point with another before or next than its last use moves it by its relationships (nkxyz.c) */
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
  if(!r->same_as){
    /* the receipt, on the run */
    GROW(r->rcs, r->nrc, r->crc, Rc); Rc *c = &r->rcs[r->nrc++]; c->pos = pos; c->gate = gate; c->shard = s->id; c->via = (unsigned char)via; c->had = (unsigned char)had;
    if(s->call || s->spawn){ GROW(b->hit, b->nhit, b->chit, Hit); Hit *h = &b->hit[b->nhit]; h->run = run; h->ord = ord; h->pos = pos; h->gate = gate; h->before = before; h->next = next; h->via = via; h->had = had; h->shard = s->id; h->call = s->call; h->spawn = s->spawn; hmap_put(&b->hith, run, ord, b->nhit + 1); Neuron *ng = neuron_of(b, gate); if(ng){ GROW(ng->hits, ng->nhits, ng->chits, i64); ng->hits[ng->nhits++] = b->nhit; } b->nhit++; }
  }
  /* the steps, pushed in hit_go's order; the one pushed last runs first */
  if(next == 0 && via == 0){ Hop h = {0}; h.type = HOP_ENDED; h.run = run; h.gate = gate; h.a = s->id; push(b, h); }
  if(next != 0 && (via == 1 || had == 1)){ int np = pos + 1; while(np <= r->nseq && r->seq[np - 1] == SPACE) np++; int nn = np + 1; while(nn <= r->nseq && r->seq[nn - 1] == SPACE) nn++; Hop h = {0}; h.type = HOP_LAND; h.run = run; h.pos = np; h.gate = next; h.before = via == 1 ? before : gate; h.next = nn <= r->nseq ? r->seq[nn - 1] : 0; h.via = 0; push(b, h); }
  if(next != 0 && via == 0 && had == 0){
    char v[32]; snprintf(v, sizeof v, "%d", next); cell_set(b, run, NEWGATE, 1, v);
    Hop h = {0}; h.type = HOP_LAND; h.run = run; h.pos = pos; h.gate = BORN; h.before = gate; h.next = next; h.via = 1; push(b, h);
  }
  if(s->spawn) replay_push_from(b, run, s->spawn, 2, run, ord);
  if(s->call) replay_push_from(b, run, s->call, 1, run, ord);
  if(gate == BUILD && via == 0) build_gate(b, run, pos, ord);
}
/* a closed run repeated: its firings in order, nothing else; the next one waits under what this one fires, as in hit_go's order */
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
/* ---------------- the end of a run (ended_go, memory_go, the node, complete) ---------------- */
static void ended(Brain *b, i64 run, int gate, i64 shard){
  Run *r = run_of(b, run); if(!r || r->ended) return; r->ended = 1;
  if(r->same_as){
    /* a repeat: one tick and a time stamp on the run it repeats; no row of its own */
    Run *cn = run_of(b, r->same_as); if(cn){ cn->last_at = r->at; cn->last_run = run; } r->has_mem = 1;
  } else {
    /* the memory: the line as gates, who it arrived from, the ending gate and shard, the clock */
    r->mem_source = r->arrival; r->mem_gate = gate; r->mem_shard = shard; r->mem_at = r->at; r->has_mem = 1; r->last_at = r->at; r->last_run = run;
    r->clean = 1; for(int i = 0; i < r->nrc; i++) if(r->rcs[i].via){ r->clean = 0; break; }
    i64 sh = (i64)seqhash(r->seq, r->nseq);
    hmap_put(&b->memh, sh, memkey2(r), run);                                /* the newest run that ended with its own receipts: what a repeat points at */
    r->mem_sibling = hmap_get(&b->memt, sh, 0); hmap_put(&b->memt, sh, 0, run);   /* the chain of memory rows with these symbols, the newest first */
    Neuron *ng = neuron_of(b, gate); if(ng && r->kind == 0){ GROW(ng->mem_runs, ng->nmem, ng->cmem, i64); ng->mem_runs[ng->nmem++] = run; }
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
  while(i < L){ size_t j = i; if(is_letter((unsigned char)text[i])){ while(j < L && is_letter((unsigned char)text[j])) j++; } else j = i + u8len((unsigned char)text[i]); if(j > L) j = L;
    size_t m = j - i; if(m >= sizeof buf) m = sizeof buf - 1; memcpy(buf, text + i, m); buf[m] = 0;
    if(*n >= SEQCAP){ SEQCAP = SEQCAP ? SEQCAP * 2 : 4096; SEQBUF = realloc(SEQBUF, SEQCAP * sizeof(int)); } SEQBUF[(*n)++] = label_gate(b, buf); i = j; }
  *out = SEQBUF;
}
const int *nk_seq(Brain *b, i64 run, int *n){
  Run *r = run_of(b, run); if(!r){ *n = 0; return 0; }
  if(r->same_as && r->same_as != run) return nk_seq(b, r->same_as, n);   /* a repeat's symbols are the pattern's */
  if(r->seq || r->nseq == 0){ *n = r->seq ? r->nseq : 0; return r->seq; }
  if(r->replay_src && r->replay_src != run) return nk_seq(b, r->replay_src, n);
  if(r->src && r->srcgate){ const char *t = nk_source_text(r->srcgate, r->src); if(t){ int *s; cut_into(b, t, &s, n); return s; } }
  *n = 0; return 0;
}
static Rc *RCBUF; static int RCCAP;
int nk_receipts(Brain *b, i64 run, Rc **out, int *kept){
  Run *r = run_of(b, run); if(!r){ *out = 0; *kept = 0; return 0; }
  if(r->same_as){ Run *cn = run_of(b, r->same_as); if(cn) r = cn; }
  if(r->kept || r->nrc){ *out = r->rcs; *kept = 1; return r->nrc; }
  *out = 0; *kept = 0; return 0;   /* a closed sub-run has no receipt and none is rebuilt: the main run's receipt and sheet are its memory */
}
