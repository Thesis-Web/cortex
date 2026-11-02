/* nkvt.c (2026-10-30): the bridge. Mother pastes a formula into one SQLite connection whose tables are the brains' regions, seen through
   this virtual table module: no copy, no catalogue of neurons. dna is one name in SQL and per-neuron regions underneath; every table is
   found by its key (gate, run, (run, cell), (gate, before, trigger), symbol); a whole table is read only when a formula asks for all of
   it. Writes a formula makes (a cell, a shard's call, a line into a mailbox, a replay, a birth) go straight into the region, and the
   physics follow as they would from the egg's triggers. */
#include "nk.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct Cur Cur;
typedef struct TDesc {
  const char *name, *ddl; int ncols;
  int nidx; int idxcols[8][3]; int idxn[8];                      /* candidate keys, the most specific first */
  void (*begin)(Cur *c, int idx, sqlite3_value **argv);          /* position before the first row of the chosen iteration */
  int  (*step)(Cur *c);                                          /* advance to the next row; 1 = at a row, 0 = done */
  void (*column)(Cur *c, sqlite3_context *ctx, int col);
  i64  (*rowid)(Cur *c);
  int  (*update)(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err);
  i64 keyed, scanned;                                            /* reads by a key, reads that walked the whole region */
} TDesc;
typedef struct { sqlite3_vtab base; TDesc *d; Brain *b; } VT;
struct Cur { sqlite3_vtab_cursor base; TDesc *d; Brain *b; int idx; i64 e, e_end, i, n; int eof; i64 k1, k2, k3; int started; };

static i64 V(sqlite3_value *v){ return sqlite3_value_type(v) == SQLITE_NULL ? 0 : sqlite3_value_int64(v); }
static void R(sqlite3_context *ctx, i64 v){ sqlite3_result_int64(ctx, v); }
static void RN(sqlite3_context *ctx, i64 v){ if(v) sqlite3_result_int64(ctx, v); else sqlite3_result_null(ctx); }   /* 0 is NULL for before, trigger, call, spawn, parent, cell, about */
static void RT(sqlite3_context *ctx, const char *s){ if(s) sqlite3_result_text(ctx, s, -1, SQLITE_TRANSIENT); else sqlite3_result_null(ctx); }

/* --- generic "entity, then offset" iteration: e over [e, e_end], i over the entity's rows [0, n) --- */
#define ENT_BEGIN(c, lo, hi) do { (c)->e = (lo); (c)->e_end = (hi); (c)->i = -1; (c)->n = 0; (c)->started = 0; } while(0)

/* label */
static void label_begin(Cur *c, int idx, sqlite3_value **argv){ if(idx == 1){ i64 g = V(argv[0]); ENT_BEGIN(c, g, g); } else if(idx == 2){ int g = label_gate(c->b, (const char*)sqlite3_value_text(argv[0])); ENT_BEGIN(c, g, g ? g : 0); if(!g) c->e_end = -1; } else ENT_BEGIN(c, 1, c->b->label.n); }
static int label_step(Cur *c){ if(!c->started){ c->started = 1; } else c->e++; return c->e >= 1 && c->e <= c->e_end && c->e <= c->b->label.n; }
static void label_col(Cur *c, sqlite3_context *x, int col){ if(col == 0) R(x, c->e); else RT(x, c->b->label.sym[c->e]); }
static i64 label_rowid(Cur *c){ return c->e; }
static int label_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){
  if(argc == 1) return SQLITE_OK;                                       /* delete: a symbol is never unlaid */
  if(sqlite3_value_type(argv[0]) == SQLITE_NULL){ const char *s = (const char*)sqlite3_value_text(argv[3]); if(!s) return SQLITE_OK; int g = label_gate(b, s); if(g){ return SQLITE_OK; } g = label_new(b, s); *rowid = g; return SQLITE_OK; }
  return SQLITE_OK;
}
/* neuron (gate, born) */
static void neuron_begin(Cur *c, int idx, sqlite3_value **argv){ if(idx == 1){ i64 g = V(argv[0]); ENT_BEGIN(c, g, g); } else ENT_BEGIN(c, 1, c->b->label.n); }
static int neuron_step(Cur *c){ if(!c->started) c->started = 1; else c->e++; return c->e >= 1 && c->e <= c->e_end && c->e <= c->b->label.n; }
static void neuron_col(Cur *c, sqlite3_context *x, int col){ Neuron *n = neuron_of(c->b, (int)c->e); switch(col){ case 0: R(x, c->e); break; case 1: R(x, n ? n->born : 0); break; case 2: R(x, n ? n->narrived : 0); break; case 3: R(x, n ? n->nnode : 0); break; case 4: R(x, n ? n->nmem : 0); break; case 5: R(x, n ? n->nsh : 0); break; } }
static int neuron_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){
  if(argc == 1) return SQLITE_OK;
  i64 g = V(argv[2]); Neuron *n = neuron_of(b, (int)g);
  if(!n){ *err = sqlite3_mprintf("no such gate %lld", (long long)g); return SQLITE_ERROR; }
  if(sqlite3_value_type(argv[0]) == SQLITE_NULL){ if(n->born){ *err = sqlite3_mprintf("neuron %lld already exists", (long long)g); return SQLITE_CONSTRAINT; } n->born = 1; *rowid = g; return SQLITE_OK; }
  n->born = (int)V(argv[3]); return SQLITE_OK;
}
/* dna (gate, shard, before, trigger, call, spawn, times): entity gate, rows its shards */
static void dna_begin(Cur *c, int idx, sqlite3_value **argv){
  if(idx == 1){ i64 g = V(argv[0]); c->k1 = V(argv[1]); c->k2 = V(argv[2]); ENT_BEGIN(c, g, g); c->idx = 1; }   /* (gate, before, trigger): the shard itself */
  else if(idx == 2){ i64 g = V(argv[0]); ENT_BEGIN(c, g, g); }                                                 /* gate: that neuron's shards */
  else ENT_BEGIN(c, 1, c->b->label.n);
}
static int dna_step(Cur *c){
  for(;;){
    if(c->idx == 1){ if(c->started) return 0; c->started = 1; Neuron *n = neuron_of(c->b, (int)c->e); if(!n || !n->born) return 0; i64 ix = hmap_get(&n->h, c->k1, c->k2); if(!ix){ shard_lay(c->b, (int)c->e, (int)c->k1, (int)c->k2, 0); ix = n->nsh; } c->i = ix - 1; return 1; }   /* a row named by its full key (a binding line) exists from then on: the hop lays none for a pass */
    if(!c->started){ c->started = 1; c->i = -1; }
    Neuron *n = (c->e >= 1 && c->e <= c->e_end && c->e <= c->b->label.n) ? neuron_of(c->b, (int)c->e) : 0;
    if(!n) return 0;
    c->i++; if(c->i < n->nsh) return 1;
    c->e++; c->i = -1; if(c->e > c->e_end) return 0;
  }
}
static void dna_col(Cur *c, sqlite3_context *x, int col){ Neuron *n = neuron_of(c->b, (int)c->e); Shard *s = &n->sh[c->i]; switch(col){ case 0: R(x, c->e); break; case 1: R(x, s->id); break; case 2: RN(x, s->before); break; case 3: RN(x, s->trigger); break; case 4: RN(x, s->call); break; case 5: RN(x, s->spawn); break; case 6: R(x, s->times); break; } }
static i64 dna_rowid(Cur *c){ return (c->e << 32) | (c->i + 1); }
static int dna_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){
  if(argc == 1) return SQLITE_OK;   /* a shard is never unlaid */
  if(sqlite3_value_type(argv[0]) == SQLITE_NULL){       /* INSERT INTO dna (gate, shard, before, trigger, call, spawn, times) */
    int g = (int)V(argv[2]); Neuron *n = neuron_of(b, g); if(!n){ *err = sqlite3_mprintf("no such gate %d", g); return SQLITE_ERROR; }
    if(!n->born) n->born = 1;                           /* laying a shard into a gate with no region births it */
    int before = (int)V(argv[4]), trigger = (int)V(argv[5]);
    Shard *s = shard_find(b, g, before, trigger); if(s) return SQLITE_OK;          /* INSERT OR IGNORE-like: one shard per key */
    s = shard_lay(b, g, before, trigger, V(argv[8]));
    if(sqlite3_value_type(argv[3]) != SQLITE_NULL){ i64 want = V(argv[3]); if(want > b->shards) b->shards = want; s->id = want; }
    s->call = V(argv[6]); s->spawn = V(argv[7]);
    *rowid = ((i64)g << 32) | n->nsh; return SQLITE_OK;
  }
  i64 rid = V(argv[0]); int g = (int)(rid >> 32); i64 ix = (rid & 0xffffffff) - 1; Neuron *n = neuron_of(b, g); if(!n || ix < 0 || ix >= n->nsh) return SQLITE_ERROR;
  Shard *s = &n->sh[ix];
  int nb = (int)V(argv[4]), nt = (int)V(argv[5]);
  if(nb != s->before || nt != s->trigger){ hmap_del(&n->h, s->before, s->trigger); s->before = nb; s->trigger = nt; hmap_put(&n->h, nb, nt, ix + 1); }
  if(s->call != V(argv[6]) || s->spawn != V(argv[7])){ s->changed_at = b->clock; b->rewrite_at = b->clock; }
  s->call = V(argv[6]); s->spawn = V(argv[7]); s->times = V(argv[8]);
  return SQLITE_OK;
}
/* node (gate, id, source, run) */
static void node_begin(Cur *c, int idx, sqlite3_value **argv){ if(idx == 1){ i64 g = V(argv[0]); ENT_BEGIN(c, g, g); } else ENT_BEGIN(c, 1, c->b->label.n); }
static int node_step(Cur *c){ for(;;){ if(!c->started){ c->started = 1; c->i = -1; } Neuron *n = (c->e >= 1 && c->e <= c->e_end && c->e <= c->b->label.n) ? neuron_of(c->b, (int)c->e) : 0; if(!n) return 0; c->i++; if(c->i < n->nnode) return 1; c->e++; c->i = -1; if(c->e > c->e_end) return 0; } }
static void node_col(Cur *c, sqlite3_context *x, int col){ Neuron *n = neuron_of(c->b, (int)c->e); NodeRow *r = &n->node[c->i]; switch(col){ case 0: R(x, c->e); break; case 1: R(x, c->i + 1); break; case 2: R(x, r->source); break; case 3: R(x, r->run); break; } }
static i64 node_rowid(Cur *c){ return (c->e << 32) | (c->i + 1); }
static int node_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc == 1 || sqlite3_value_type(argv[0]) != SQLITE_NULL) return SQLITE_OK; int g = (int)V(argv[2]); Neuron *n = neuron_of(b, g); if(!n) return SQLITE_ERROR; if(n->nnode >= n->cnode){ n->cnode = n->cnode ? n->cnode * 2 : 8; n->node = realloc(n->node, n->cnode * sizeof(NodeRow)); } n->node[n->nnode].source = (int)V(argv[4]); n->node[n->nnode].run = V(argv[5]); n->nnode++; return SQLITE_OK; }
/* run (id, arrival, parent, root, kind, cell, about, at, moment): keys id, parent (the kids list), about (the neuron's list), arrival (scan) */
static void run_begin(Cur *c, int idx, sqlite3_value **argv){
  c->idx = idx; c->started = 0; c->i = -1;
  if(idx == 1){ i64 id = V(argv[0]); ENT_BEGIN(c, id, id); }
  else if(idx == 2){ c->k1 = V(argv[0]); ENT_BEGIN(c, 0, 0); }
  else if(idx == 3){ c->k1 = V(argv[0]); ENT_BEGIN(c, 0, 0); }
  else if(idx == 4){ c->k1 = V(argv[0]); ENT_BEGIN(c, 0, 0); }
  else ENT_BEGIN(c, 1, c->b->nruns);
}
static int run_step(Cur *c){
  if(c->idx == 4){ Neuron *n = neuron_of(c->b, (int)c->k1); if(!n) return 0; c->i++; if(c->i < n->narrived){ c->e = n->arrived[c->i]; return 1; } return 0; }
  if(c->idx == 2){ Run *p = run_of(c->b, c->k1); if(!p) return 0; c->i++; if(c->i < p->nkids){ c->e = p->kids[c->i]; return 1; } return 0; }
  if(c->idx == 3){ Neuron *n = neuron_of(c->b, (int)c->k1); if(!n) return 0; c->i++; if(c->i < n->nabout){ c->e = n->about_runs[c->i]; return 1; } return 0; }
  if(!c->started) c->started = 1; else c->e++;
  return c->e >= 1 && c->e <= c->e_end && c->e <= c->b->nruns;
}
static void run_col(Cur *c, sqlite3_context *x, int col){ Run *r = run_of(c->b, c->e); switch(col){ case 0: R(x, c->e); break; case 1: R(x, r->arrival); break; case 2: if(r->parent_set) R(x, r->parent); else sqlite3_result_null(x); break; case 3: R(x, r->root); break; case 4: R(x, r->kind); break; case 5: RN(x, r->cell); break; case 6: RN(x, r->about); break; case 7: R(x, r->at); break; case 8: R(x, r->moment); break; case 9: RN(x, r->from_run); break; case 10: if(r->build_pos >= 0) R(x, r->build_pos); else sqlite3_result_null(x); break; case 11: RN(x, r->same_as); break; case 12: R(x, r->again); break; case 13: R(x, r->last_at); break; case 14: R(x, r->last_run); break; case 15: R(x, r->ended); break; case 16: R(x, r->from_ord); break; case 17: RN(x, r->src); break; case 18: RN(x, r->srcgate); break; case 19: RN(x, r->replay_src); break; case 20: R(x, r->kept); break; } }
static i64 run_rowid(Cur *c){ return c->e; }
static int run_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc > 1 && sqlite3_value_type(argv[0]) != SQLITE_NULL){ Run *r = run_of(b, V(argv[0])); if(r){ r->root = V(argv[5]); } } return SQLITE_OK; }
/* seq (run, pos, gate) */
static void seq_begin(Cur *c, int idx, sqlite3_value **argv){ c->idx = idx; if(idx >= 1){ i64 r = V(argv[0]); ENT_BEGIN(c, r, r); if(idx == 2) c->k1 = V(argv[1]); } else ENT_BEGIN(c, 1, c->b->nruns); }
static int *SEQP; static int SEQN, SEQCAPV; static i64 SEQRUN = -1;
static void seq_of(Cur *c, i64 run){ if(run != SEQRUN){ int n; const int *p = nk_seq(c->b, run, &n); if(n > SEQCAPV){ SEQCAPV = n * 2 + 16; SEQP = realloc(SEQP, SEQCAPV * sizeof(int)); } if(p && n) memcpy(SEQP, p, n * sizeof(int)); SEQN = p ? n : 0; SEQRUN = run; } }
static int seq_step(Cur *c){
  if(c->idx == 2){ if(c->started) return 0; c->started = 1; seq_of(c, c->e); if(!SEQP || c->k1 < 1 || c->k1 > SEQN) return 0; c->i = c->k1 - 1; return 1; }
  for(;;){ if(!c->started){ c->started = 1; c->i = -1; } if(!(c->e >= 1 && c->e <= c->e_end && c->e <= c->b->nruns)) return 0; seq_of(c, c->e); c->i++; if(SEQP && c->i < SEQN) return 1; c->e++; c->i = -1; if(c->e > c->e_end) return 0; }
}
static void seq_col(Cur *c, sqlite3_context *x, int col){ seq_of(c, c->e); switch(col){ case 0: R(x, c->e); break; case 1: R(x, c->i + 1); break; case 2: R(x, SEQP ? SEQP[c->i] : 0); break; } }
static i64 seq_rowid(Cur *c){ return (c->e << 24) | (c->i + 1); }
static int seq_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc == 1 || sqlite3_value_type(argv[0]) != SQLITE_NULL) return SQLITE_OK; Run *r = run_of(b, V(argv[2])); if(!r) return SQLITE_ERROR; int pos = (int)V(argv[3]); if(pos != r->nseq + 1) { *err = sqlite3_mprintf("seq is written in order"); return SQLITE_ERROR; } if(r->nseq % 8 == 0) r->seq = realloc(r->seq, (r->nseq + 8) * sizeof(int)); r->seq[r->nseq++] = (int)V(argv[4]); return SQLITE_OK; }

/* defwords (gate, word, defined): the words of a point's definition rows, each once, and whether the word holds definition rows itself now
   (the guesser's rows, source 15, do not count). Keyed by the point; the recall's known and unknown cells read it. */
static int *DWW; static unsigned char *DWD; static int DWN, DWCAP; static i64 DWGATE = -1;
static void defwords_of(Brain *b, int gate){
  if(gate == DWGATE) return; DWGATE = gate; DWN = 0; Neuron *n = neuron_of(b, gate); if(!n || !n->nnode) return;
  int wikt = label_gate(b, "wikt"); HMap seen; hmap_init(&seen, 1 << 10);
  for(int j = 0; j < n->nnode; j++){ i64 run = n->node[j].run; Run *r = run_of(b, run); if(!r || !((r->arrival >= 7 && r->arrival <= 14) || r->arrival == wikt)) continue;
    int ns; const int *sq = nk_seq(b, run, &ns);
    for(int k = 0; sq && k < ns; k++){ int x = sq[k]; if(x <= 0 || x > b->label.n) continue; unsigned char c0 = (unsigned char)b->label.sym[x][0]; if(!((c0 >= 'A' && c0 <= 'Z') || (c0 >= 'a' && c0 <= 'z'))) continue;
      if(hmap_get(&seen, x, 0)) continue; hmap_put(&seen, x, 0, 1);
      if(DWN >= DWCAP){ DWCAP = DWCAP ? DWCAP * 2 : 1024; DWW = realloc(DWW, DWCAP * sizeof(int)); DWD = realloc(DWD, DWCAP); }
      Neuron *w = neuron_of(b, x); int def = 0; if(w) for(int q = 0; q < w->nnode; q++) if(w->node[q].source != 15){ def = 1; break; }
      DWW[DWN] = x; DWD[DWN] = (unsigned char)def; DWN++; } }
  free(seen.e);
}
static void defwords_begin(Cur *c, int idx, sqlite3_value **argv){ c->idx = idx; c->started = 0; c->i = -1; if(idx == 1){ c->k1 = V(argv[0]); defwords_of(c->b, (int)c->k1); } else { DWGATE = -1; DWN = 0; } }
static int defwords_step(Cur *c){ if(c->idx != 1) return 0; c->i++; return c->i < DWN; }
static void defwords_col(Cur *c, sqlite3_context *x, int col){ switch(col){ case 0: R(x, c->k1); break; case 1: R(x, DWW[c->i]); break; case 2: R(x, DWD[c->i]); break; } }
static i64 defwords_rowid(Cur *c){ return (c->k1 << 24) | (c->i + 1); }
/* run_sheet (run, cell, state, value) */
static void sheet_begin(Cur *c, int idx, sqlite3_value **argv){ c->idx = idx; if(idx >= 1){ i64 r = V(argv[0]); ENT_BEGIN(c, r, r); if(idx == 2) c->k1 = V(argv[1]); } else ENT_BEGIN(c, 1, c->b->nruns); }
static int sheet_step(Cur *c){
  if(c->idx == 2){ if(c->started) return 0; c->started = 1; Run *r = run_of(c->b, c->e); if(!r) return 0; for(int i = 0; i < r->ncells; i++) if(r->cells[i].cell == c->k1){ c->i = i; return 1; } return 0; }
  for(;;){ if(!c->started){ c->started = 1; c->i = -1; } Run *r = (c->e >= 1 && c->e <= c->e_end && c->e <= c->b->nruns) ? run_of(c->b, c->e) : 0; if(!r) return 0; c->i++; if(c->i < r->ncells) return 1; c->e++; c->i = -1; if(c->e > c->e_end) return 0; }
}
static void sheet_col(Cur *c, sqlite3_context *x, int col){ Run *r = run_of(c->b, c->e); Cell *k = &r->cells[c->i]; switch(col){ case 0: R(x, c->e); break; case 1: R(x, k->cell); break; case 2: R(x, k->state); break; case 3: RT(x, val_text(c->b, &k->v)); break; } }
static i64 sheet_rowid(Cur *c){ return (c->e << 16) | (c->i + 1); }
static int sheet_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){
  if(argc == 1) return SQLITE_OK;
  i64 run; int cell;
  if(sqlite3_value_type(argv[0]) == SQLITE_NULL){ run = V(argv[2]); cell = (int)V(argv[3]); }
  else { i64 rid = V(argv[0]); run = rid >> 16; Run *r = run_of(b, run); int i = (int)(rid & 0xffff) - 1; if(!r || i < 0 || i >= r->ncells) return SQLITE_ERROR; cell = r->cells[i].cell; }
  const char *val = sqlite3_value_type(argv[5]) == SQLITE_NULL ? 0 : (const char*)sqlite3_value_text(argv[5]);
  cell_set(b, run, cell, (int)V(argv[4]), val); *rowid = (run << 16) | 1; return SQLITE_OK;
}
/* run_receipt (id, run, pos, gate, shard, kept): keyed by run (the run's own receipts, held or re-hopped); whole: every held receipt, run by run */
static Rc *RCP; static int RCN, RCKEPT, RCCAPV; static i64 RCRUN = -1;
static void rcs_of(Cur *c, i64 run){ if(run != RCRUN){ Rc *p; int n = nk_receipts(c->b, run, &p, &RCKEPT); if(n > RCCAPV){ RCCAPV = n * 2 + 16; RCP = realloc(RCP, RCCAPV * sizeof(Rc)); } if(p && n) memcpy(RCP, p, n * sizeof(Rc)); RCN = p ? n : 0; RCRUN = run; } }
static void rc_begin(Cur *c, int idx, sqlite3_value **argv){ c->idx = idx; c->i = -1; c->started = 0; RCRUN = -1; if(idx == 1){ c->k1 = V(argv[0]); ENT_BEGIN(c, c->k1, c->k1); } else ENT_BEGIN(c, 1, c->b->nruns); }
static int rc_step(Cur *c){
  if(c->idx == 1){ rcs_of(c, c->k1); c->i++; return c->i < RCN; }
  for(;;){ if(!c->started){ c->started = 1; c->i = -1; } if(!(c->e >= 1 && c->e <= c->e_end && c->e <= c->b->nruns)) return 0; Run *r = run_of(c->b, c->e); c->i++; if(r && r->nrc && c->i < r->nrc){ RCP = r->rcs; RCN = r->nrc; RCKEPT = 1; RCRUN = c->e; return 1; } c->e++; c->i = -1; if(c->e > c->e_end) return 0; }
}
static void rc_col(Cur *c, sqlite3_context *x, int col){ Rc *k = &RCP[c->i]; switch(col){ case 0: R(x, c->e * 1000000 + c->i); break; case 1: R(x, c->e); break; case 2: R(x, k->pos); break; case 3: R(x, k->gate); break; case 4: R(x, k->shard); break; case 5: R(x, RCKEPT); break; } }
static i64 rc_rowid(Cur *c){ return c->e * 1000000 + c->i; }
/* run_memory (run, input, source, gate, shard, at): keys run, gate (the neuron's ended list), input (the newest with that input) */
static void mem_begin(Cur *c, int idx, sqlite3_value **argv){ c->idx = idx; c->i = -1; c->started = 0; if(idx == 1){ i64 r = V(argv[0]); ENT_BEGIN(c, r, r); } else if(idx == 2){ c->k1 = V(argv[0]); ENT_BEGIN(c, 0, 0); }
  else if(idx == 3){ /* the symbols as text "g g g": hashed as a seq, then the chain of memory rows with those symbols */ const char *s = (const char*)sqlite3_value_text(argv[0]); int buf[4096], n = 0; if(s){ const char *q = s; while(*q && n < 4096){ while(*q == ' ') q++; if(!*q) break; buf[n++] = atoi(q); while(*q && *q != ' ') q++; } } i64 head = n ? hmap_get(&c->b->memt, (i64)seqhash(buf, n), 0) : 0; ENT_BEGIN(c, head, head); }
  else ENT_BEGIN(c, 1, c->b->nruns); }
static int mem_step(Cur *c){
  if(c->idx == 2){ Neuron *n = neuron_of(c->b, (int)c->k1); if(!n) return 0; c->i++; if(c->i < n->nmem){ c->e = n->mem_runs[c->i]; return 1; } return 0; }
  if(c->idx == 3){ if(!c->started){ c->started = 1; return c->e > 0; } Run *r = run_of(c->b, c->e); if(!r || !r->mem_sibling) return 0; c->e = r->mem_sibling; return 1; }
  for(;;){ if(!c->started) c->started = 1; else c->e++; if(!(c->e >= 1 && c->e <= c->e_end && c->e <= c->b->nruns)) return 0; Run *r = run_of(c->b, c->e); if(r && r->has_mem && !r->same_as && r->kept) return 1; }   /* a memory row: a main run, or a pattern that repeats; a dropped sub-run has none */
}
static char *MEMTXT; static size_t MEMCAP;
static const char *mem_text(Brain *b, i64 run){ int n; const int *q = nk_seq(b, run, &n); if(!q) return 0; size_t need = 16 + (size_t)n * 12; if(need > MEMCAP){ MEMCAP = need * 2; MEMTXT = realloc(MEMTXT, MEMCAP); } size_t len = 0; MEMTXT[0] = 0; for(int i = 0; i < n; i++) len += snprintf(MEMTXT + len, MEMCAP - len, i ? " %d" : "%d", q[i]); return MEMTXT; }
static void mem_col(Cur *c, sqlite3_context *x, int col){ Run *r = run_of(c->b, c->e); switch(col){ case 0: R(x, c->e); break; case 1: RT(x, r->kept ? mem_text(c->b, c->e) : 0); break; case 2: { char t[24]; snprintf(t, sizeof t, "%d", r->mem_source); RT(x, t); } break; case 3: R(x, r->mem_gate); break; case 4: R(x, r->mem_shard); break; case 5: R(x, r->mem_at); break; case 6: R(x, r->again); break; case 7: R(x, r->last_at); break; case 8: R(x, r->last_run); break; } }
static i64 mem_rowid(Cur *c){ return c->e; }
/* timeline (id, at, run, key1, key2) */
static void tl_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, c->b->ntl - 1); }
static int tl_step(Cur *c){ if(!c->started) c->started = 1; else c->e++; return c->e <= c->e_end; }
static void tl_col(Cur *c, sqlite3_context *x, int col){ Tl *t = &c->b->tl[c->e]; switch(col){ case 0: R(x, c->e + 1); break; case 1: R(x, t->at); break; case 2: R(x, t->run); break; case 3: R(x, t->key1); break; case 4: R(x, t->key2); break; } }
static i64 tl_rowid(Cur *c){ return c->e + 1; }
/* input / third (id, text, run); an insert is a line arriving at that prompt */
static void in_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, c->b->ninput - 1); }
static int in_step(Cur *c){ if(!c->started) c->started = 1; else c->e++; return c->e <= c->e_end; }
static void in_col(Cur *c, sqlite3_context *x, int col){ Mail *m = &c->b->input[c->e]; switch(col){ case 0: R(x, m->id); break; case 1: RT(x, m->text); break; case 2: R(x, m->run); break; } }
static i64 in_rowid(Cur *c){ return c->e + 1; }
static int in_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc == 1 || sqlite3_value_type(argv[0]) != SQLITE_NULL) return SQLITE_OK; const char *t = (const char*)sqlite3_value_text(argv[3]); line_in(b, 0, t ? t : ""); *rowid = b->ninput; return SQLITE_OK; }
static void th_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, c->b->nthird - 1); }
static int th_step(Cur *c){ if(!c->started) c->started = 1; else c->e++; return c->e <= c->e_end; }
static void th_col(Cur *c, sqlite3_context *x, int col){ Mail *m = &c->b->third[c->e]; switch(col){ case 0: R(x, m->id); break; case 1: RT(x, m->text); break; case 2: R(x, m->run); break; } }
static int th_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc == 1 || sqlite3_value_type(argv[0]) != SQLITE_NULL) return SQLITE_OK; const char *t = (const char*)sqlite3_value_text(argv[3]); line_in(b, 1, t ? t : ""); *rowid = b->nthird; return SQLITE_OK; }
/* secondary (id, run, cell, gate, about, text, made): an insert is a return with its key */
static void sec_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, c->b->nsec - 1); }
static int sec_step(Cur *c){ if(!c->started) c->started = 1; else c->e++; return c->e <= c->e_end; }
static void sec_col(Cur *c, sqlite3_context *x, int col){ Sec *s = &c->b->sec[c->e]; switch(col){ case 0: R(x, s->id); break; case 1: R(x, s->run); break; case 2: RN(x, s->cell); break; case 3: R(x, s->gate); break; case 4: RN(x, s->about); break; case 5: RT(x, s->text); break; case 6: R(x, s->made); break; case 7: RN(x, s->src); break; } }
static int sec_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc == 1 || sqlite3_value_type(argv[0]) != SQLITE_NULL) return SQLITE_OK; const char *t = (const char*)sqlite3_value_text(argv[7]); i64 src = argc > 9 ? V(argv[9]) : 0; i64 t0 = now_ns(); secondary_in(b, V(argv[3]), (int)V(argv[4]), (int)V(argv[5]), (int)V(argv[6]), t ? t : "", src); b->sec_ns += now_ns() - t0; b->secs++; *rowid = b->nsec; return SQLITE_OK; }
/* out_user (id, run, cell, value) */
static void out_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, c->b->nout - 1); }
static int out_step(Cur *c){ if(!c->started) c->started = 1; else c->e++; return c->e <= c->e_end; }
static void out_col(Cur *c, sqlite3_context *x, int col){ Out *o = &c->b->out[c->e]; switch(col){ case 0: R(x, o->id); break; case 1: R(x, o->run); break; case 2: R(x, o->cell); break; case 3: RT(x, val_text(c->b, &o->v)); break; } }
/* refused (id, text, error) */
static void ref_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, c->b->nref - 1); }
static int ref_step(Cur *c){ if(!c->started) c->started = 1; else c->e++; return c->e <= c->e_end; }
static void ref_col(Cur *c, sqlite3_context *x, int col){ Refused *r = &c->b->ref[c->e]; switch(col){ case 0: R(x, r->id); break; case 1: RT(x, val_text(c->b, &r->text)); break; case 2: RT(x, val_text(c->b, &r->error)); break; } }
/* hit (id, run, pos, gate, before, next, via, had, shard, call, spawn): every hit, as v6's hit table. Keyed by (gate, call IS NOT NULL): the
   neuron's own list of the hits on it that carried a call or spawn (the standing question shape asks exactly that). Any other read walks
   every run's receipts: before and next follow from the run's seq, via and had sit on the receipt, call and spawn as they were at the hit. */
static void hit_begin(Cur *c, int idx, sqlite3_value **argv){ c->idx = idx; c->i = -1; c->started = 0; RCRUN = -1; if(idx == 1){ c->k1 = V(argv[0]); ENT_BEGIN(c, 0, 0); } else if(idx == 2){ c->k1 = V(argv[0]); ENT_BEGIN(c, c->k1, c->k1); } else if(idx == 3){ c->k1 = V(argv[0]); c->k2 = V(argv[1]); ENT_BEGIN(c, c->k1, c->k1); } else ENT_BEGIN(c, 1, c->b->nruns); }
static int hit_step(Cur *c){
  if(c->idx == 1){ Neuron *n = neuron_of(c->b, (int)c->k1); if(!n) return 0; c->i++; if(c->i < n->nhits){ c->e = n->hits[c->i]; return 1; } return 0; }
  if(c->idx == 2){ rcs_of(c, c->k1); c->i++; return c->i < RCN; }
  if(c->idx == 3){ if(c->started) return 0; c->started = 1; rcs_of(c, c->k1); if(c->k2 < 0 || c->k2 >= RCN) return 0; c->i = (int)c->k2; return 1; }
  for(;;){ if(!c->started){ c->started = 1; c->i = -1; } if(!(c->e >= 1 && c->e <= c->e_end && c->e <= c->b->nruns)) return 0; Run *r = run_of(c->b, c->e); c->i++; if(r && r->nrc && c->i < r->nrc){ RCP = r->rcs; RCN = r->nrc; RCKEPT = 1; RCRUN = c->e; return 1; } c->e++; c->i = -1; if(c->e > c->e_end) return 0; }
}
static void hit_col(Cur *c, sqlite3_context *x, int col){
  if(c->idx == 1){ Hit *h = &c->b->hit[c->e]; switch(col){ case 0: R(x, h->run * 1000000 + h->ord); break; case 1: R(x, h->run); break; case 2: R(x, h->pos); break; case 3: R(x, h->gate); break; case 4: RN(x, h->before); break; case 5: RN(x, h->next); break; case 6: R(x, h->via); break; case 7: R(x, h->had); break; case 8: R(x, h->shard); break; case 9: RN(x, h->call); break; case 10: RN(x, h->spawn); break; case 11: R(x, h->ord); break; case 12: R(x, 1); break; } return; }
  i64 run = c->e; Rc *k = &RCP[c->i]; int n; const int *seq = nk_seq(c->b, run, &n); Run *r = run_of(c->b, run);
  int before = k->via ? (k->pos >= 1 && k->pos <= n ? seq[k->pos - 1] : 0) : (k->pos >= 2 && k->pos - 1 <= n ? seq[k->pos - 2] : 0);
  int next = (seq && k->pos + 1 <= n) ? seq[k->pos] : 0;
  i64 hrun = (r && r->same_as) ? r->same_as : run; i64 hx = hmap_get(&c->b->hith, hrun, c->i); Hit *h = hx ? &c->b->hit[hx - 1] : 0;
  switch(col){ case 0: R(x, run * 1000000 + c->i); break; case 1: R(x, run); break; case 2: R(x, k->pos); break; case 3: R(x, k->gate); break; case 4: RN(x, before); break; case 5: RN(x, next); break; case 6: R(x, k->via); break; case 7: R(x, k->had); break; case 8: R(x, k->shard); break; case 9: RN(x, h ? h->call : 0); break; case 10: RN(x, h ? h->spawn : 0); break; case 11: R(x, c->i); break; case 12: R(x, RCKEPT); break; }
}
static i64 hit_rowid(Cur *c){ if(c->idx == 1){ Hit *h = &c->b->hit[c->e]; return h->run * 1000000 + h->ord; } return c->e * 1000000 + c->i; }
/* hop (id, text, p1, p2, p3): the stack as it stands, the row that runs next last; land (id, run, pos, gate, before, next, via): every landing, as v6's land table, read from the receipts */
static void hop_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, c->b->nhop - 1); }
static int hop_step(Cur *c){ if(!c->started) c->started = 1; else c->e++; return c->e <= c->e_end; }
static void hop_col(Cur *c, sqlite3_context *x, int col){ Hop *h = &c->b->hop[c->e]; switch(col){ case 0: R(x, c->e + 1); break; case 1: RT(x, h->type == HOP_LAND ? "land" : h->type == HOP_ENDED ? "ended" : "replay"); break; case 2: R(x, h->type); break; case 3: R(x, h->run); break; case 4: R(x, h->pos); break; case 5: R(x, h->gate); break; case 6: R(x, h->before); break; case 7: R(x, h->next); break; case 8: R(x, h->via); break; case 9: R(x, h->a); break; case 10: R(x, h->b); break; case 11: R(x, h->kind); break; case 12: R(x, h->from_run); break; case 13: R(x, h->from_ord); break; } }
static void land_col(Cur *c, sqlite3_context *x, int col){
  i64 run = c->e; Rc *k = &RCP[c->i]; int n; const int *seq = nk_seq(c->b, run, &n);
  int before = k->via ? (k->pos >= 1 && k->pos <= n ? seq[k->pos - 1] : 0) : (k->pos >= 2 && k->pos - 1 <= n ? seq[k->pos - 2] : 0);
  int next = (seq && k->pos + 1 <= n) ? seq[k->pos] : 0;
  switch(col){ case 0: R(x, run * 1000000 + c->i); break; case 1: R(x, run); break; case 2: R(x, k->pos); break; case 3: R(x, k->gate); break; case 4: RN(x, before); break; case 5: RN(x, next); break; case 6: R(x, k->via); break; }
}
/* clock (n), shards (n) */
static void one_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, 0); }
static int one_step(Cur *c){ if(!c->started){ c->started = 1; return 1; } return 0; }
static void clock_col(Cur *c, sqlite3_context *x, int col){ R(x, c->b->clock); }
static void shards_col(Cur *c, sqlite3_context *x, int col){ R(x, nk_shard_rows(c->b)); }   /* the rows held, not the id counter */
static int shards_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc > 1 && sqlite3_value_type(argv[0]) != SQLITE_NULL) b->shards = V(argv[2]); return SQLITE_OK; }
/* complete (run) */
static void cmp_begin(Cur *c, int idx, sqlite3_value **argv){ c->idx = idx; if(idx == 1){ i64 r = V(argv[0]); ENT_BEGIN(c, r, r); } else ENT_BEGIN(c, 1, c->b->nruns); }
static int cmp_step(Cur *c){ for(;;){ if(!c->started) c->started = 1; else c->e++; if(!(c->e >= 1 && c->e <= c->e_end && c->e <= c->b->nruns)) return 0; Run *r = run_of(c->b, c->e); if(r && r->complete) return 1; } }
static void cmp_col(Cur *c, sqlite3_context *x, int col){ R(x, c->e); }
/* replay (parent, source, kind): write only */
static void rp_begin(Cur *c, int idx, sqlite3_value **argv){ ENT_BEGIN(c, 0, -1); }
static int rp_step(Cur *c){ return 0; }
static void rp_col(Cur *c, sqlite3_context *x, int col){ sqlite3_result_null(x); }
static int rp_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc == 1 || sqlite3_value_type(argv[0]) != SQLITE_NULL) return SQLITE_OK; replay_push(b, V(argv[2]), V(argv[3]), (int)V(argv[4])); *rowid = 1; return SQLITE_OK; }
static i64 plain_rowid(Cur *c){ return c->e + 1; }
/* xyz (gate, x, y, z, shard, before, next, at, run, moved): the point's place, by gate (nkxyz.c); UPDATE or INSERT of x, y, z sets it */
static double XX, XY, XZ; static i64 XS, XAT, XRUN; static int XB, XN, XM, XOK;
static void xyz_begin(Cur *c, int idx, sqlite3_value **argv){ c->started = 0; c->idx = idx; c->k1 = idx == 1 ? V(argv[0]) : 0; XOK = (idx == 1 && c->b->is_main) ? nk_xyz_get((int)c->k1, &XX, &XY, &XZ, &XS, &XB, &XN, &XAT, &XRUN, &XM) : 0; }
static int xyz_vstep(Cur *c){ if(!c->started){ c->started = 1; return XOK; } return 0; }
static void xyz_col(Cur *c, sqlite3_context *x, int col){ switch(col){ case 0: R(x, c->k1); break; case 1: sqlite3_result_double(x, XX); break; case 2: sqlite3_result_double(x, XY); break; case 3: sqlite3_result_double(x, XZ); break; case 4: R(x, XS); break; case 5: RN(x, XB); break; case 6: RN(x, XN); break; case 7: R(x, XAT); break; case 8: R(x, XRUN); break; case 9: R(x, XM); break; } }
static i64 xyz_rowid(Cur *c){ return c->k1; }
static int xyz_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc == 1) return SQLITE_OK; int g = (int)V(argv[2]); if(!b->is_main || g <= 0){ *err = sqlite3_mprintf("xyz is the main brain's, by gate"); return SQLITE_ERROR; } nk_xyz_set(b, g, sqlite3_value_double(argv[3]), sqlite3_value_double(argv[4]), sqlite3_value_double(argv[5])); *rowid = g; return SQLITE_OK; }

static TDesc TABLES[] = {
  {"label", "CREATE TABLE x(gate INTEGER, symbol TEXT)", 2, 2, {{0},{1}}, {1,1}, label_begin, label_step, label_col, label_rowid, label_update},
  {"neuron", "CREATE TABLE x(gate INTEGER, born INTEGER, arrived INTEGER, nodes INTEGER, memories INTEGER, shards INTEGER)", 6, 1, {{0}}, {1}, neuron_begin, neuron_step, neuron_col, label_rowid, neuron_update},   /* arrived: runs that arrived from this gate (a source's returns); the counts a formula reads by key */
  {"dna", "CREATE TABLE x(gate INTEGER, shard INTEGER, before INTEGER, trigger INTEGER, call INTEGER, spawn INTEGER, times INTEGER)", 7, 2, {{0,2,3},{0}}, {3,1}, dna_begin, dna_step, dna_col, dna_rowid, dna_update},
  {"node", "CREATE TABLE x(gate INTEGER, id INTEGER, source INTEGER, run INTEGER)", 4, 1, {{0}}, {1}, node_begin, node_step, node_col, node_rowid, node_update},
  {"run", "CREATE TABLE x(id INTEGER, arrival INTEGER, parent INTEGER, root INTEGER, kind INTEGER, cell INTEGER, about INTEGER, at INTEGER, moment INTEGER, from_run INTEGER, build_pos INTEGER, same_as INTEGER, again INTEGER, last_at INTEGER, last_run INTEGER, ended INTEGER, from_ord INTEGER, src INTEGER, srcgate INTEGER, replay_src INTEGER, kept INTEGER)", 21, 4, {{0},{2},{6},{1}}, {1,1,1,1}, run_begin, run_step, run_col, run_rowid, run_update},   /* from_hit, build_pos: the kernel's (step back; a span open at a snapshot) */
  {"seq", "CREATE TABLE x(run INTEGER, pos INTEGER, gate INTEGER)", 3, 2, {{0},{0,1}}, {1,2}, seq_begin, seq_step, seq_col, seq_rowid, seq_update},
  {"run_sheet", "CREATE TABLE x(run INTEGER, cell INTEGER, state INTEGER, value TEXT)", 4, 2, {{0},{0,1}}, {1,2}, sheet_begin, sheet_step, sheet_col, sheet_rowid, sheet_update},
  {"run_receipt", "CREATE TABLE x(id INTEGER, run INTEGER, pos INTEGER, gate INTEGER, shard INTEGER, kept INTEGER)", 6, 1, {{1}}, {1}, rc_begin, rc_step, rc_col, rc_rowid, 0},
  {"run_memory", "CREATE TABLE x(run INTEGER, input TEXT, source TEXT, gate INTEGER, shard INTEGER, at INTEGER, again INTEGER, last_at INTEGER, last_run INTEGER)", 9, 3, {{0},{3},{1}}, {1,1,1}, mem_begin, mem_step, mem_col, mem_rowid, 0},   /* one row per run with its own receipts; again / last_at / last_run count its repeats (the owner's shape) */
  {"timeline", "CREATE TABLE x(id INTEGER, at INTEGER, run INTEGER, key1 INTEGER, key2 INTEGER)", 5, 0, {{0}}, {0}, tl_begin, tl_step, tl_col, tl_rowid, 0},
  {"input", "CREATE TABLE x(id INTEGER, text TEXT, run INTEGER)", 3, 0, {{0}}, {0}, in_begin, in_step, in_col, in_rowid, in_update},
  {"third", "CREATE TABLE x(id INTEGER, text TEXT, run INTEGER)", 3, 0, {{0}}, {0}, th_begin, th_step, th_col, in_rowid, th_update},
  {"secondary", "CREATE TABLE x(id INTEGER, run INTEGER, cell INTEGER, gate INTEGER, about INTEGER, text TEXT, made INTEGER, src INTEGER)", 8, 0, {{0}}, {0}, sec_begin, sec_step, sec_col, plain_rowid, sec_update},
  {"out_user", "CREATE TABLE x(id INTEGER, run INTEGER, cell INTEGER, value TEXT)", 4, 0, {{0}}, {0}, out_begin, out_step, out_col, plain_rowid, 0},
  {"refused", "CREATE TABLE x(id INTEGER, text TEXT, error TEXT)", 3, 0, {{0}}, {0}, ref_begin, ref_step, ref_col, plain_rowid, 0},
  {"hit", "CREATE TABLE x(id INTEGER, run INTEGER, pos INTEGER, gate INTEGER, before INTEGER, next INTEGER, via INTEGER, had INTEGER, shard INTEGER, call INTEGER, spawn INTEGER, ord INTEGER, kept INTEGER)", 13, 3, {{3},{1},{1,11}}, {1,1,2}, hit_begin, hit_step, hit_col, hit_rowid, 0},
  {"hop", "CREATE TABLE x(id INTEGER, text TEXT, type INTEGER, run INTEGER, pos INTEGER, gate INTEGER, before INTEGER, next INTEGER, via INTEGER, a INTEGER, b INTEGER, kind INTEGER, from_run INTEGER, from_ord INTEGER)", 14, 0, {{0}}, {0}, hop_begin, hop_step, hop_col, plain_rowid, 0},
  {"land", "CREATE TABLE x(id INTEGER, run INTEGER, pos INTEGER, gate INTEGER, before INTEGER, next INTEGER, via INTEGER)", 7, 0, {{0}}, {0}, hit_begin, hit_step, land_col, hit_rowid, 0},
  {"clock", "CREATE TABLE x(n INTEGER)", 1, 0, {{0}}, {0}, one_begin, one_step, clock_col, plain_rowid, 0},
  {"shards", "CREATE TABLE x(n INTEGER)", 1, 0, {{0}}, {0}, one_begin, one_step, shards_col, plain_rowid, shards_update},
  {"complete", "CREATE TABLE x(run INTEGER)", 1, 1, {{0}}, {1}, cmp_begin, cmp_step, cmp_col, run_rowid, 0},
  {"replay", "CREATE TABLE x(parent INTEGER, source INTEGER, kind INTEGER)", 3, 0, {{0}}, {0}, rp_begin, rp_step, rp_col, plain_rowid, rp_update},
  {"defwords", "CREATE TABLE x(gate INTEGER, word INTEGER, defined INTEGER)", 3, 1, {{0}}, {1}, defwords_begin, defwords_step, defwords_col, defwords_rowid, 0},
  {"xyz", "CREATE TABLE x(gate INTEGER, x REAL, y REAL, z REAL, shard INTEGER, before INTEGER, next INTEGER, at INTEGER, run INTEGER, moved INTEGER)", 10, 1, {{0}}, {1}, xyz_begin, xyz_vstep, xyz_col, xyz_rowid, xyz_update},   /* the point's place (nkxyz.c) */
};
#define NTABLES (int)(sizeof(TABLES) / sizeof(TABLES[0]))
static Brain *BRAINS[2]; static const char *BNAMES[2] = {"main", "sixth"};

static int xConnect(sqlite3 *db, void *aux, int argc, const char *const *argv, sqlite3_vtab **pp, char **err){
  if(argc < 5){ *err = sqlite3_mprintf("nk(brain, table)"); return SQLITE_ERROR; }
  Brain *b = 0; for(int i = 0; i < 2; i++) if(BRAINS[i] && strcmp(argv[3], BNAMES[i]) == 0) b = BRAINS[i];
  TDesc *d = 0; for(int i = 0; i < NTABLES; i++) if(strcmp(TABLES[i].name, argv[4]) == 0) d = &TABLES[i];
  if(!b || !d){ *err = sqlite3_mprintf("no such brain or table: %s %s", argv[3], argv[4]); return SQLITE_ERROR; }
  if(sqlite3_declare_vtab(db, d->ddl) != SQLITE_OK) return SQLITE_ERROR;
  VT *v = sqlite3_malloc(sizeof(VT)); memset(v, 0, sizeof(*v)); v->d = d; v->b = b; *pp = &v->base; return SQLITE_OK;
}
static int xDisconnect(sqlite3_vtab *v){ sqlite3_free(v); return SQLITE_OK; }
static int xBestIndex(sqlite3_vtab *tab, sqlite3_index_info *info){
  VT *v = (VT*)tab; TDesc *d = v->d;
  for(int k = 0; k < d->nidx; k++){
    int found = 0, argpos[3] = {-1, -1, -1};
    for(int j = 0; j < d->idxn[k]; j++){
      for(int i = 0; i < info->nConstraint; i++){
        const struct sqlite3_index_constraint *c = &info->aConstraint[i];
        if(!c->usable || c->iColumn != d->idxcols[k][j]) continue;
        if(c->op == SQLITE_INDEX_CONSTRAINT_EQ || c->op == SQLITE_INDEX_CONSTRAINT_IS || c->op == SQLITE_INDEX_CONSTRAINT_ISNULL){ argpos[j] = i; found++; break; }
      }
    }
    if(found == d->idxn[k] && k == 0 && strcmp(d->name, "hit") == 0){ int nn = 0; for(int i = 0; i < info->nConstraint; i++){ const struct sqlite3_index_constraint *q = &info->aConstraint[i]; if(q->usable && q->iColumn == 9 && q->op == SQLITE_INDEX_CONSTRAINT_ISNOTNULL) nn = 1; } if(!nn) found = -1; }
    if(found == d->idxn[k]){
      for(int j = 0; j < d->idxn[k]; j++){ info->aConstraintUsage[argpos[j]].argvIndex = j + 1; info->aConstraintUsage[argpos[j]].omit = 0; }
      info->idxNum = k + 1; info->estimatedCost = 1.0 + k; info->estimatedRows = 1; return SQLITE_OK;
    }
  }
  /* no search: a read comes with its key or it does not happen. The owner, 2026-11-01: "no sweep, search table, find nothing". Clock and shards are one row */
  if(strcmp(d->name, "clock") == 0 || strcmp(d->name, "shards") == 0 || strcmp(d->name, "replay") == 0 || strcmp(d->name, "refused") == 0){ info->idxNum = 0; info->estimatedCost = 1; info->estimatedRows = 1; return SQLITE_OK; }
  return SQLITE_CONSTRAINT;
}
static int xOpen(sqlite3_vtab *tab, sqlite3_vtab_cursor **pc){ Cur *c = sqlite3_malloc(sizeof(Cur)); memset(c, 0, sizeof(*c)); c->d = ((VT*)tab)->d; c->b = ((VT*)tab)->b; *pc = &c->base; return SQLITE_OK; }
static int xClose(sqlite3_vtab_cursor *pc){ sqlite3_free(pc); return SQLITE_OK; }
static int xFilter(sqlite3_vtab_cursor *pc, int idxNum, const char *idxStr, int argc, sqlite3_value **argv){
  Cur *c = (Cur*)pc; c->idx = idxNum; c->eof = 0; c->started = 0; c->i = -1; if(idxNum) c->d->keyed++; else c->d->scanned++; SEQRUN = -1; RCRUN = -1;
  /* an ISNULL constraint carries no argument: pass a NULL value so the key is 0 */
  sqlite3_value *args[3] = {0, 0, 0}; for(int i = 0; i < argc && i < 3; i++) args[i] = argv[i];
  static sqlite3_value *nullv = 0; if(!nullv){ sqlite3_stmt *st; sqlite3_prepare_v2(mother_db(), "SELECT NULL", -1, &st, 0); sqlite3_step(st); nullv = sqlite3_value_dup(sqlite3_column_value(st, 0)); sqlite3_finalize(st); }
  for(int i = 0; i < 3; i++) if(!args[i]) args[i] = nullv;
  c->d->begin(c, idxNum, args);
  c->eof = !c->d->step(c); return SQLITE_OK;
}
static int xNext(sqlite3_vtab_cursor *pc){ Cur *c = (Cur*)pc; c->eof = !c->d->step(c); return SQLITE_OK; }
static int xEof(sqlite3_vtab_cursor *pc){ return ((Cur*)pc)->eof; }
static int xColumn(sqlite3_vtab_cursor *pc, sqlite3_context *ctx, int col){ Cur *c = (Cur*)pc; c->d->column(c, ctx, col); return SQLITE_OK; }
static int xRowid(sqlite3_vtab_cursor *pc, sqlite3_int64 *p){ Cur *c = (Cur*)pc; *p = c->d->rowid(c); return SQLITE_OK; }
static int xUpdate(sqlite3_vtab *tab, int argc, sqlite3_value **argv, sqlite3_int64 *rowid){ VT *v = (VT*)tab; if(!v->d->update) return SQLITE_OK; char *err = 0; int rc = v->d->update(v->b, argc, argv, rowid, &err); if(err){ sqlite3_free(tab->zErrMsg); tab->zErrMsg = err; } return rc; }
static sqlite3_module MOD = { 0, xConnect, xConnect, xBestIndex, xDisconnect, xDisconnect, xOpen, xClose, xFilter, xNext, xEof, xColumn, xRowid, xUpdate };

void nkvt_scans(char *out, size_t cap){ size_t n = 0; out[0] = 0; for(int i = 0; i < NTABLES; i++){ if(!TABLES[i].keyed && !TABLES[i].scanned) continue; n += snprintf(out + n, cap - n, "%s{\"table\":\"%s\",\"keyed\":%lld,\"scanned\":%lld}", n ? "," : "", TABLES[i].name, (long long)TABLES[i].keyed, (long long)TABLES[i].scanned); if(n >= cap) break; } }
void nkvt_register(sqlite3 *db, Brain *main, Brain *sixth){
  BRAINS[0] = main; BRAINS[1] = sixth;
  sqlite3_create_module(db, "nk", &MOD, 0);
  for(int bi = 0; bi < 2; bi++){
    if(!BRAINS[bi]) continue;
    for(int i = 0; i < NTABLES; i++){
      char *q = sqlite3_mprintf("CREATE VIRTUAL TABLE IF NOT EXISTS %s.%s USING nk(%s, %s)", BNAMES[bi], TABLES[i].name, BNAMES[bi], TABLES[i].name);
      char *e = 0; if(sqlite3_exec(db, q, 0, 0, &e) != SQLITE_OK){ fprintf(stderr, "nkvt: %s: %s\n", q, e); sqlite3_free(e); } sqlite3_free(q);
    }
  }
}
