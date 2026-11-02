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
int label_gate(Brain *b, const char *sym){ return (int)hmap_get(&b->label.h, (i64)strhash(sym), 1); }
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
Shard *shard_find(Brain *b, int gate, int before, int trigger){ Neuron *n = neuron_of(b, gate); if(!n || !n->born) return 0; i64 i = hmap_get(&n->h, before, trigger); return i ? &n->sh[i - 1] : 0; }
Shard *shard_lay(Brain *b, int gate, int before, int trigger, i64 times){
  Neuron *n = neuron_of(b, gate); if(!n) return 0;
  GROW(n->sh, n->nsh, n->csh, Shard);
  Shard *s = &n->sh[n->nsh++]; s->id = ++b->shards; s->before = before; s->trigger = trigger; s->call = 0; s->spawn = 0; s->times = times; s->changed_at = b->clock;
  hmap_put(&n->h, before, trigger, n->nsh); hmap_put(&b->shid, gate, s->id, n->nsh);
  return s;
}
Shard *shard_by_id(Brain *b, int gate, i64 id){ Neuron *n = neuron_of(b, gate); if(!n) return 0; i64 i = hmap_get(&b->shid, gate, id); return i ? &n->sh[i - 1] : 0; }
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
  /* complete_go: the cells to the user's out mailbox, by cell */
  int order[1024], n = 0; for(int i = 0; i < r->ncells && n < 1024; i++) order[n++] = i;
  for(int i = 1; i < n; i++){ int k = order[i], j = i - 1; while(j >= 0 && r->cells[order[j]].cell > r->cells[k].cell){ order[j + 1] = order[j]; j--; } order[j + 1] = k; }
  for(int i = 0; i < n; i++){ Cell *c = &r->cells[order[i]]; GROW(b->out, b->nout, b->cout, Out); Out *o = &b->out[b->nout]; o->id = b->nout + 1; o->run = run; o->cell = c->cell; o->value = c->value ? strdup(c->value) : 0; b->nout++; }
}
static int sheet_open(Run *r){ for(int i = 0; i < r->ncells; i++) if(r->cells[i].state == 0) return 1; return 0; }
int sheet_open_pub(Brain *b, i64 run){ Run *r = run_of(b, run); return r ? sheet_open(r) : 0; }
void cell_set(Brain *b, i64 run, int cell, int state, const char *value){
  Run *r = run_of(b, run); if(!r) return;
  Cell *c = 0; for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell){ c = &r->cells[i]; break; }
  if(!c){ GROW(r->cells, r->ncells, r->ccells, Cell); c = &r->cells[r->ncells++]; c->cell = cell; c->value = 0; }
  else { free(c->value); c->value = 0; }
  c->state = state; c->value = value ? strdup(value) : 0;
  if(state == 1 && r->has_mem && !sheet_open(r)) complete_run(b, run);          /* sheet_fill */
}
const char *cell_get(Brain *b, i64 run, int cell){ Run *r = run_of(b, run); if(!r) return 0; for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == cell && r->cells[i].state == 1 && r->cells[i].value) return r->cells[i].value; return 0; }

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
static i64 memkey2(Run *r){ return ((i64)r->arrival << 40) | ((i64)r->cell << 20) | (i64)r->about; }
/* a run whose symbols, arrival, cell and about repeat a run that already ended with its own receipts, hit no new word and whose shards have
   not been rewritten since, will hop exactly as that run did: it points at it (same_as), shares its seq and stores no receipts of its own */
static void dedupe_check(Brain *b, i64 run){
  Run *r = run_of(b, run); if(r->nseq == 0) return;
  i64 f = hmap_get(&b->memh, (i64)seqhash(r->seq, r->nseq), memkey2(r)); if(!f || f == run) return;
  Run *cn = run_of(b, f); if(!cn || !cn->has_mem || cn->same_as || !cn->clean || !cn->kept || cn->nrc == 0 || cn->nseq != r->nseq || !cn->seq) return;
  if(memcmp(cn->seq, r->seq, sizeof(int) * r->nseq) != 0) return;
  for(int i = 0; i < cn->nrc; i++){ Rc *k = &cn->rcs[i]; Shard *s = shard_by_id(b, k->gate, k->shard); if(!s || s->changed_at > cn->mem_at) return; }
  r->same_as = f; if(!r->seq_shared) free(r->seq); r->seq = cn->seq; r->seq_shared = 1; b->deduped++; cn->again++; /* counted when the repeat starts, not when it ends: it borrows cn's symbols from here on, and compaction leaves a run with again > 0 alone */
}
static void first_landing(Brain *b, i64 run){ Run *r = run_of(b, run); dedupe_check(b, run); if(r->nseq > 0) land(b, run, 0, r->arrival, 0, r->seq[0], 0); }

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
  cut2(b, id, text ? text : ""); first_landing(b, id);
}
static void replay_push_from(Brain *b, i64 parent, i64 source, int kind, i64 from_run, int from_ord){ Hop h = {0}; h.type = HOP_REPLAY; h.run = parent; h.a = source; h.kind = kind; h.from_run = from_run; h.from_ord = from_ord; push(b, h); }
void replay_push(Brain *b, i64 parent, i64 source, int kind){ replay_push_from(b, parent, source, kind, b->cur_run, b->cur_ord); }
static void replay(Brain *b, i64 parent, i64 source, int kind, i64 from_run, int from_ord){
  i64 id = new_run(b, SAID, parent, 1, kind, 0, 0);
  Run *src = run_of(b, source), *r = run_of(b, id); r->from_run = from_run; r->from_ord = from_ord; r->replay_src = source; r->kept = 1;
  if(src) for(int i = 0; i < src->nseq; i++) seq_push(r, src->seq[i]);
  dedupe_check(b, id);
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
  Neuron *n = neuron_of(b, gate);
  if(!n || !n->born){ /* a landing on a gate with no region: as v6's paste into a missing table, the step is refused and the run stalls */
    GROW(b->ref, b->nref, b->cref, Refused); Refused *f = &b->ref[b->nref]; f->id = b->nref + 1; char t[128]; snprintf(t, sizeof t, "land run %lld pos %d gate %d", (long long)run, pos, gate); f->text = strdup(t); f->error = strdup("no such neuron"); b->nref++; b->refused_n++; return; }
  Shard *s = shard_find(b, gate, kb, kx);
  if(!s) s = shard_lay(b, gate, kb, kx, 0);
  s->times++;
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
  if(next != 0 && (via == 1 || had == 1)){ Hop h = {0}; h.type = HOP_LAND; h.run = run; h.pos = pos + 1; h.gate = next; h.before = via == 1 ? before : gate; h.next = (pos + 2 <= r->nseq) ? r->seq[pos + 1] : 0; h.via = 0; push(b, h); }
  if(next != 0 && via == 0 && had == 0){
    char v[32]; snprintf(v, sizeof v, "%d", next); cell_set(b, run, NEWGATE, 1, v);
    Hop h = {0}; h.type = HOP_LAND; h.run = run; h.pos = pos; h.gate = BORN; h.before = gate; h.next = next; h.via = 1; push(b, h);
  }
  if(s->spawn) replay_push_from(b, run, s->spawn, 2, run, ord);
  if(s->call) replay_push_from(b, run, s->call, 1, run, ord);
  if(gate == BUILD && via == 0){
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
}
/* ---------------- the end of a run (ended_go, memory_go, the node, complete) ---------------- */
static void ended(Brain *b, i64 run, int gate, i64 shard){
  Run *r = run_of(b, run); if(!r || r->ended) return; r->ended = 1;
  if(r->same_as){
    /* a repeat: one tick and a time stamp on the run it repeats; no row of its own */
    Run *cn = run_of(b, r->same_as); if(cn){ cn->last_at = r->at; cn->last_run = run; } r->has_mem = 1;
  } else {
    /* the memory: the line as gates, who it arrived from, the ending gate and shard, the clock */
    size_t cap = 64 + (size_t)r->nseq * 12; char *inp = malloc(cap); inp[0] = 0; size_t len = 0;
    for(int i = 0; i < r->nseq; i++){ len += snprintf(inp + len, cap - len, i ? " %d" : "%d", r->seq[i]); }
    r->mem_input = inp; r->mem_source = r->arrival; r->mem_gate = gate; r->mem_shard = shard; r->mem_at = r->at; r->has_mem = 1; r->last_at = r->at; r->last_run = run;
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
  if(r->about && !r->same_as){ Neuron *n = neuron_of(b, r->about); if(n && n->born){ GROW(n->node, n->nnode, n->cnode, NodeRow); n->node[n->nnode].source = r->arrival; n->node[n->nnode].run = run; n->nnode++; } }
  if(!sheet_open(r)) complete_run(b, run);
}

/* ---------------- the pump of one brain: n steps of its stack, the newest first ---------------- */
void pump_batch(Brain *b, int n){
  while(n-- > 0 && b->nhop > 0){
    Hop h = b->hop[--b->nhop]; i64 t0 = now_ns();
    switch(h.type){
      case HOP_LAND: land(b, h.run, h.pos, h.gate, h.before, h.next, h.via); break;
      case HOP_ENDED: ended(b, h.run, h.gate, h.a); break;
      case HOP_REPLAY: replay(b, h.run, h.a, h.kind, h.from_run, h.from_ord); break;
    }
    b->hop_ns += now_ns() - t0; b->hops_run++;
  }
}

/* ---------------- the cut: when a main run has completed, the runs under it are process; their receipts and symbols go, their stubs stay ----------------
   Kept: every main run (a line at a prompt) with its receipts and sheet; every run that repeats (a pattern, again > 0) with its receipts; the
   shards and their times; the node rows (each a pointer to the source row); the relationship rows. Let go: a sub-run's receipts and, where
   they can be read again from the source row or the run it replays, its symbols. What is let go is re-stepped on demand (nk_seq, nk_receipts). */
/* 1 = nothing more to do for this run; 0 = it is still running (or its main run is), look again next pass */
static int try_compact(Brain *b, i64 id){
  Run *r = &b->runs[id]; if(r->kind == 0 || r->again > 0 || !r->kept) return 1;
  Run *root = run_of(b, r->root); if(!r->ended || (root && !root->ended)) return 0;
  if(r->nrc){ free(r->rcs); r->rcs = 0; r->crc = 0; b->dropped_receipts += r->nrc; r->nrc = 0; }
  if(r->seq && !r->seq_shared && (r->src || r->replay_src)){ free(r->seq); r->seq = 0; }
  else if(r->seq_shared){ r->seq = 0; r->seq_shared = 0; }
  if(r->mem_input){ free(r->mem_input); r->mem_input = 0; }
  r->kept = 0; b->dropped_runs++; return 1;
}
void nk_compact(Brain *b){
  /* called between batches while runs are in flight (the chain) as well as after a typed line: a run passed while still running is deferred, not skipped for good (the fault of 2026-10-31: 14 M receipts kept under the chain) */
  int keep = 0; for(int i = 0; i < b->ndef; i++){ i64 id = b->deferred[i]; if(!try_compact(b, id)) b->deferred[keep++] = id; } b->ndef = keep;
  for(i64 id = b->last_compacted + 1; id <= b->nruns; id++) if(!try_compact(b, id)){ GROW(b->deferred, b->ndef, b->cdef, i64); b->deferred[b->ndef++] = id; }
  b->last_compacted = b->nruns;
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
  /* re-hopped from the symbols: the landing on the arrival, then one hop a symbol with v6's key; the births of the first time are not repeated */
  int n; const int *seq = nk_seq(b, run, &n); if(!seq){ *out = 0; *kept = 0; return 0; }
  int need = n + 1; if(need > RCCAP){ RCCAP = need * 2; RCBUF = realloc(RCBUF, RCCAP * sizeof(Rc)); }
  int m = 0; Shard *s0 = shard_find(b, r->arrival, 0, 0); RCBUF[m].pos = 0; RCBUF[m].gate = r->arrival; RCBUF[m].shard = s0 ? s0->id : 0; RCBUF[m].via = 0; RCBUF[m].had = 1; m++;
  for(int p = 1; p <= n; p++){ int g = seq[p - 1], kb = 0, kx = 0;
    if(g != SPACE){ kb = r->arrival; for(int q = p - 1; q >= 1; q--) if(seq[q - 1] != SPACE){ kb = seq[q - 1]; break; } for(int q = p + 1; q <= n; q++) if(seq[q - 1] != SPACE){ kx = seq[q - 1]; break; } }
    Shard *s = shard_find(b, g, kb, kx); RCBUF[m].pos = p; RCBUF[m].gate = g; RCBUF[m].shard = s ? s->id : 0; RCBUF[m].via = 0; RCBUF[m].had = 1; m++; }
  *out = RCBUF; *kept = 0; return m;
}
/* ---------------- a brain back from its export: the inverse of nkio's export, row for row ---------------- */
static sqlite3_stmt *Q(sqlite3 *db, const char *sql){ sqlite3_stmt *st = 0; if(sqlite3_prepare_v2(db, sql, -1, &st, 0) != SQLITE_OK){ fprintf(stderr, "load: %s: %s\n", sql, sqlite3_errmsg(db)); return 0; } return st; }
#define I(st, i) sqlite3_column_int64(st, i)
#define ISNULL(st, i) (sqlite3_column_type(st, i) == SQLITE_NULL)
#define T(st, i) ((const char*)sqlite3_column_text(st, i))
int nk_load(Brain *b, const char *path){
  sqlite3 *db = 0; if(sqlite3_open_v2(path, &db, SQLITE_OPEN_READONLY, 0) != SQLITE_OK){ fprintf(stderr, "load: cannot open %s\n", path); return -1; }
  sqlite3_stmt *st; int bad = 0;
  if((st = Q(db, "SELECT gate, symbol FROM label ORDER BY gate"))){ while(sqlite3_step(st) == SQLITE_ROW){ int g = label_new(b, T(st, 1)); if(g != (int)I(st, 0)){ fprintf(stderr, "load: label %lld came back as %d\n", (long long)I(st, 0), g); bad++; } } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT gate, born FROM neuron"))){ while(sqlite3_step(st) == SQLITE_ROW){ Neuron *n = neuron_of(b, (int)I(st, 0)); if(n) n->born = (int)I(st, 1); } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT gate, shard, before, trigger, call, spawn, times FROM dna ORDER BY shard"))){ while(sqlite3_step(st) == SQLITE_ROW){ int g = (int)I(st, 0); Shard *s = shard_lay(b, g, ISNULL(st, 2) ? 0 : (int)I(st, 2), ISNULL(st, 3) ? 0 : (int)I(st, 3), I(st, 6)); if(s){ Neuron *n = neuron_of(b, g); if(s->id != I(st, 1)){ hmap_del(&b->shid, g, s->id); s->id = I(st, 1); hmap_put(&b->shid, g, s->id, n->nsh); } s->call = ISNULL(st, 4) ? 0 : I(st, 4); s->spawn = ISNULL(st, 5) ? 0 : I(st, 5); s->changed_at = 0; } } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT gate, source, run FROM node ORDER BY gate, id"))){ while(sqlite3_step(st) == SQLITE_ROW){ Neuron *n = neuron_of(b, (int)I(st, 0)); if(!n) continue; if(n->nnode >= n->cnode){ n->cnode = n->cnode ? n->cnode * 2 : 8; n->node = realloc(n->node, n->cnode * sizeof(NodeRow)); } n->node[n->nnode].source = (int)I(st, 1); n->node[n->nnode].run = I(st, 2); n->nnode++; } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT id, arrival, parent, root, kind, cell, about, at, moment, from_run, build_pos, same_as, again, last_at, last_run, from_ord, src, srcgate, replay_src, kept, ended FROM run ORDER BY id"))){
    while(sqlite3_step(st) == SQLITE_ROW){
      i64 id = ++b->nruns; if(id != I(st, 0)){ fprintf(stderr, "load: run %lld where %lld was expected\n", (long long)I(st, 0), (long long)id); bad++; }
      if(id >= b->cruns){ i64 oc = b->cruns; while(id >= b->cruns) b->cruns *= 2; b->runs = realloc(b->runs, b->cruns * sizeof(Run)); memset(b->runs + oc, 0, (b->cruns - oc) * sizeof(Run)); }
      Run *r = &b->runs[id]; memset(r, 0, sizeof(*r));
      r->arrival = (int)I(st, 1); r->parent_set = !ISNULL(st, 2); r->parent = r->parent_set ? I(st, 2) : 0; r->root = I(st, 3); r->kind = (int)I(st, 4); r->cell = ISNULL(st, 5) ? 0 : (int)I(st, 5); r->about = ISNULL(st, 6) ? 0 : (int)I(st, 6); r->at = I(st, 7); r->moment = I(st, 8); r->from_run = ISNULL(st, 9) ? 0 : I(st, 9); r->build_pos = ISNULL(st, 10) ? -1 : (int)I(st, 10); r->same_as = ISNULL(st, 11) ? 0 : I(st, 11); r->again = I(st, 12); r->last_at = I(st, 13); r->last_run = I(st, 14); r->from_ord = (int)I(st, 15); r->src = I(st, 16); r->srcgate = (int)I(st, 17); r->replay_src = I(st, 18); r->kept = (int)I(st, 19); r->ended = (int)I(st, 20); if(r->same_as) b->deduped++; if(!r->kept) b->dropped_runs++;
      Run *p = r->parent_set ? run_of(b, r->parent) : 0; if(p){ GROW(p->kids, p->nkids, p->ckids, i64); p->kids[p->nkids++] = id; }
      if(r->about){ Neuron *n = neuron_of(b, r->about); if(n){ GROW(n->about_runs, n->nabout, n->cabout, i64); n->about_runs[n->nabout++] = id; } }
      { Neuron *n = neuron_of(b, r->arrival); if(n){ GROW(n->arrived, n->narrived, n->carrived, i64); n->arrived[n->narrived++] = id; } }
    } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT run, gate FROM seq ORDER BY run, pos"))){ while(sqlite3_step(st) == SQLITE_ROW){ Run *r = run_of(b, I(st, 0)); if(r) seq_push(r, (int)I(st, 1)); } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT run, cell, state, value FROM run_sheet ORDER BY run"))){ while(sqlite3_step(st) == SQLITE_ROW){ Run *r = run_of(b, I(st, 0)); if(!r) continue; GROW(r->cells, r->ncells, r->ccells, Cell); Cell *k = &r->cells[r->ncells++]; k->cell = (int)I(st, 1); k->state = (int)I(st, 2); k->value = ISNULL(st, 3) ? 0 : strdup(T(st, 3)); } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT run, ord, pos, gate, via, had, shard, call, spawn FROM hit WHERE kept = 1 ORDER BY run, ord"))){
    while(sqlite3_step(st) == SQLITE_ROW){
      Run *r = run_of(b, I(st, 0)); if(!r) continue; int ord = (int)I(st, 1);
      GROW(r->rcs, r->nrc, r->crc, Rc); Rc *k = &r->rcs[r->nrc++]; k->pos = (int)I(st, 2); k->gate = (int)I(st, 3); k->via = (unsigned char)I(st, 4); k->had = (unsigned char)I(st, 5); k->shard = I(st, 6); if(ord + 1 > r->nhops) r->nhops = ord + 1;
      if(!ISNULL(st, 7) || !ISNULL(st, 8)){ GROW(b->hit, b->nhit, b->chit, Hit); Hit *x = &b->hit[b->nhit]; x->run = I(st, 0); x->ord = ord; x->pos = k->pos; x->gate = k->gate; x->via = k->via; x->had = k->had; x->shard = k->shard; x->call = ISNULL(st, 7) ? 0 : I(st, 7); x->spawn = ISNULL(st, 8) ? 0 : I(st, 8);
        x->before = k->via ? (k->pos >= 1 && k->pos <= r->nseq ? r->seq[k->pos - 1] : 0) : (k->pos >= 2 && k->pos - 1 <= r->nseq ? r->seq[k->pos - 2] : 0); x->next = (k->pos + 1 <= r->nseq) ? r->seq[k->pos] : 0;
        hmap_put(&b->hith, x->run, ord, b->nhit + 1); Neuron *ng = neuron_of(b, k->gate); if(ng){ GROW(ng->hits, ng->nhits, ng->chits, i64); ng->hits[ng->nhits++] = b->nhit; } b->nhit++; }
      b->hops_done++;
    } sqlite3_finalize(st); }
  b->last_compacted = 0;   /* the first compaction after a load looks at every loaded run: what the snapshot held of finished sub-runs is let go (the fault of 2026-10-31: 1.1 GB of receipts carried over) */
  if((st = Q(db, "SELECT run, input, source, gate, shard, at FROM run_memory ORDER BY run"))){ while(sqlite3_step(st) == SQLITE_ROW){ Run *r = run_of(b, I(st, 0)); if(!r) continue; r->mem_input = strdup(T(st, 1) ? T(st, 1) : ""); r->mem_source = atoi(T(st, 2) ? T(st, 2) : "0"); r->mem_gate = (int)I(st, 3); r->mem_shard = I(st, 4); r->mem_at = I(st, 5); r->has_mem = 1; r->ended = 1; if(!r->last_at){ r->last_at = r->at; r->last_run = I(st, 0); }
      r->clean = 1; for(int i = 0; i < r->nrc; i++) if(r->rcs[i].via){ r->clean = 0; break; }
      if(!r->same_as && r->seq){ i64 sh = (i64)seqhash(r->seq, r->nseq); hmap_put(&b->memh, sh, memkey2(r), I(st, 0)); r->mem_sibling = hmap_get(&b->memt, sh, 0); hmap_put(&b->memt, sh, 0, I(st, 0)); }
      Neuron *ng = neuron_of(b, r->mem_gate); if(ng && r->kind == 0){ GROW(ng->mem_runs, ng->nmem, ng->cmem, i64); ng->mem_runs[ng->nmem++] = I(st, 0); } } sqlite3_finalize(st); }
  /* a repeated run that ended marks itself as remembered, and shares the seq of the run it repeats */
  for(i64 i = 1; i <= b->nruns; i++){ Run *r = &b->runs[i]; if(r->same_as){ Run *cn = run_of(b, r->same_as); if(cn && cn->nseq == r->nseq){ free(r->seq); r->seq = cn->seq; r->seq_shared = 1; } if(r->ended || r->last_at) r->has_mem = 1; } }
  if((st = Q(db, "SELECT at, run, key1, key2 FROM timeline ORDER BY id"))){ while(sqlite3_step(st) == SQLITE_ROW){ GROW(b->tl, b->ntl, b->ctl, Tl); Tl *t = &b->tl[b->ntl++]; t->at = I(st, 0); t->run = I(st, 1); t->key1 = (int)I(st, 2); t->key2 = (int)I(st, 3); } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT id, run FROM input ORDER BY id"))){ while(sqlite3_step(st) == SQLITE_ROW){ GROW(b->input, b->ninput, b->cinput, Mail); Mail *m = &b->input[b->ninput++]; m->id = I(st, 0); m->text = 0; m->run = I(st, 1); } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT id, run FROM third ORDER BY id"))){ while(sqlite3_step(st) == SQLITE_ROW){ GROW(b->third, b->nthird, b->cthird, Mail); Mail *m = &b->third[b->nthird++]; m->id = I(st, 0); m->text = 0; m->run = I(st, 1); } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT id, run, cell, gate, about, made FROM secondary ORDER BY id"))){ while(sqlite3_step(st) == SQLITE_ROW){ GROW(b->sec, b->nsec, b->csec, Sec); Sec *s = &b->sec[b->nsec++]; s->id = I(st, 0); s->run = I(st, 1); s->cell = ISNULL(st, 2) ? 0 : (int)I(st, 2); s->gate = (int)I(st, 3); s->about = ISNULL(st, 4) ? 0 : (int)I(st, 4); s->text = 0; s->made = I(st, 5); } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT id, run, cell, value FROM out_user ORDER BY id"))){ while(sqlite3_step(st) == SQLITE_ROW){ GROW(b->out, b->nout, b->cout, Out); Out *o = &b->out[b->nout++]; o->id = I(st, 0); o->run = I(st, 1); o->cell = (int)I(st, 2); o->value = ISNULL(st, 3) ? 0 : strdup(T(st, 3)); } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT id, text, error FROM refused ORDER BY id"))){ while(sqlite3_step(st) == SQLITE_ROW){ GROW(b->ref, b->nref, b->cref, Refused); Refused *f = &b->ref[b->nref++]; f->id = I(st, 0); f->text = strdup(T(st, 1) ? T(st, 1) : ""); f->error = strdup(T(st, 2) ? T(st, 2) : ""); b->refused_n++; } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT run FROM complete"))){ while(sqlite3_step(st) == SQLITE_ROW){ Run *r = run_of(b, I(st, 0)); if(r) r->complete = 1; } sqlite3_finalize(st); }
  if((st = Q(db, "SELECT n FROM clock"))){ if(sqlite3_step(st) == SQLITE_ROW) b->clock = I(st, 0); sqlite3_finalize(st); }
  if((st = Q(db, "SELECT n FROM shards"))){ if(sqlite3_step(st) == SQLITE_ROW) b->shards = I(st, 0); sqlite3_finalize(st); }
  if((st = Q(db, "SELECT type, run, pos, gate, before, next, via, a, b, kind, from_run, from_ord FROM hop ORDER BY id"))){ while(sqlite3_step(st) == SQLITE_ROW){ Hop h = {0}; h.type = (int)I(st, 0); h.run = I(st, 1); h.pos = (int)I(st, 2); h.gate = (int)I(st, 3); h.before = (int)I(st, 4); h.next = (int)I(st, 5); h.via = (int)I(st, 6); h.a = I(st, 7); h.b = I(st, 8); h.kind = (int)I(st, 9); h.from_run = I(st, 10); h.from_ord = (int)I(st, 11); push(b, h); } sqlite3_finalize(st); }
  sqlite3_close(db);
  fprintf(stderr, "load %s: %d symbols, %lld runs (%lld stubs), %lld receipts kept, %lld memories, %lld hops pending%s\n", path, b->label.n, (long long)b->nruns, (long long)b->dropped_runs, (long long)b->hops_done, (long long)b->ntl, (long long)b->nhop, bad ? " (WITH MISMATCHES)" : "");
  return bad ? -1 : 0;
}
