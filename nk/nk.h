/* nk.h (2026-10-30): the neuron kernel's regions. Numbers only; the encoder is the one place a symbol's spelling lives.
   A brain is a region: its encoder, its neurons (each a region of shards keyed by (before, trigger)), its runs (seq, sheet, receipts),
   its memories, its timeline, its mailboxes, its hop stack. Two rules: no choice points, no scans (see DESIGN-nk). */
#ifndef NK_H
#define NK_H
#include <stdint.h>
#include <stddef.h>
#include "sqlite3.h"
#include <stdlib.h>
#include <string.h>
/* where the brain's bytes live: nkmap.c */
int nk_map_open(const char *path, uint64_t cap, uint64_t layout); uint64_t nk_map_used(void); void *nk_map_root(void); void nk_map_set_root(void *p); void nk_map_ready(void); void nk_map_sync(void);
void *nk_malloc(size_t); void *nk_calloc(size_t, size_t); void *nk_realloc(void *, size_t); void nk_free(void *); char *nk_strdup(const char *);
#ifndef NK_MAP_SELF
#define malloc nk_malloc
#define calloc nk_calloc
#define realloc nk_realloc
#define free nk_free
#define strdup nk_strdup
#endif

typedef int64_t i64;

/* a hash map from a pair of 64-bit keys to a 64-bit value (open addressing); 0 never stored as a value */
typedef struct { i64 k1, k2, v; } HEnt;
typedef struct { HEnt *e; size_t cap, n; } HMap;
void  hmap_init(HMap *m, size_t cap);
i64   hmap_get(HMap *m, i64 k1, i64 k2);            /* 0 when absent */
void  hmap_put(HMap *m, i64 k1, i64 k2, i64 v);
void  hmap_del(HMap *m, i64 k1, i64 k2);

/* a string table: symbol -> gate (hash by content), gate -> symbol (array) */
typedef struct { char **sym; int n, cap; HMap h; } Label;

typedef struct { i64 id; int before, trigger; i64 call, spawn, times; i64 changed_at; } Shard;   /* before/trigger 0 = NULL; changed_at: the clock when call or spawn was last written */
typedef struct { int source; i64 run; } NodeRow;
typedef struct { int born; Shard *sh; int nsh, csh; HMap h; NodeRow *node; int nnode, cnode; i64 *about_runs; int nabout, cabout; i64 *mem_runs; int nmem, cmem; i64 *hits; int nhits, chits; i64 *arrived; int narrived, carrived; } Neuron;   /* arrived: the runs that arrived from this gate */   /* hits: the hits on this neuron that carried a call or spawn (what the standing question shape reads) */

/* a value on a sheet: a number, a list of numbers, or gates. Text lives in the encoder only (the owner, 2026-11-01); a value is read back through it */
typedef struct { int kind, n; union { i64 num; int *g; } u; } Val;   /* kind 0 null, 1 a number, 2 numbers (u.g[n]), 3 gates (u.g[n]) */
typedef struct { int cell, state; Val v; } Cell;
typedef struct { int pos, gate; i64 shard; unsigned char via, had; } Rc;   /* a receipt, one hop of a run; before/next follow from the run's seq */
typedef struct { int ord, pos, gate, via; i64 shard; } Ev;   /* what a closed run fires, in order: a call, a spawn, a BUILD. Draft 3.2: "one hop to the memory" */
typedef struct {
  int arrival, parent_set; i64 parent, root; int kind, cell, about; i64 at, moment;
  int *seq; int nseq;
  Cell *cells; int ncells, ccells;
  Rc *rcs; int nrc, crc, nhops;            /* the run's own receipts (kept for a main run and for a pattern that repeats; a sub-run's are process and go when its main run completes), and how many hops it made */
  int ended, complete, build_pos;          /* build_pos: the open BUILD mark, -1 when none */
  i64 *kids; int nkids, ckids;             /* the runs under this one, so a formula finds them by key */
  i64 from_run; int from_ord;              /* the receipt (run, ordinal) whose call, spawn or BUILD span made this run; 0 for a line at a prompt: step back */
  i64 src, replay_src; int srcgate, kept;  /* src: a return's row in its source (srcgate names the source); replay_src: the run a replay re-runs; kept: receipts and seq still held */
  /* the memory of a run that ended. The owner's shape (the prose; v5 strayed from it): a run that repeats an earlier identical run is not a
     second row but a tick on the first: same_as names that run, which keeps again (how many times) and last_at / last_run (the newest). A
     repeated run stores no receipts and shares the first's seq; its hops still happen and the shards' times still tick. */
  int mem_source, mem_gate; i64 mem_shard, mem_at; int has_mem;
  i64 same_as, again, last_at, last_run, mem_sibling; int nhops_run, seq_shared, clean;   /* clean: ended with no born hop, so a repeat hits the same shards; mem_sibling: the next memory row with the same symbols from another arrival */
  Ev *ev; int nev, cev, ev_built; i64 ok_at;   /* a closed run's firings, read once from its receipt; ok_at: when its shards were last seen unchanged */
} Run;

typedef struct { i64 at, run; int key1, key2; } Tl;
typedef struct { i64 id; char *text; i64 run; } Mail;                 /* input, third */
typedef struct { i64 id, run; int cell, gate, about; char *text; i64 made, src; } Sec;   /* secondary; src: the source row the return came from */
typedef struct { i64 id, run; int cell; Val v; } Out;          /* out_user */
typedef struct { i64 id; Val text, error; } Refused;
typedef struct { i64 run; int ord, pos, gate, before, next, via, had; i64 shard, call, spawn; } Hit;  /* the call or spawn a hit carried, as it was at the hit; every other column of v6's hit table follows from the receipt */
typedef struct { int gate, kind, other; i64 run; } Rel;

enum { HOP_LAND = 1, HOP_ENDED = 2, HOP_REPLAY = 3, HOP_FIRE = 4 };
typedef struct { int type; i64 run; int pos, gate, before, next, via; i64 a, b; int kind; i64 from_run; int from_ord; } Hop;   /* from: the receipt that pushed a replay */

typedef struct Brain {
  const char *name; int is_main;
  Label label;
  Neuron *nr; int nnr, cnr;                 /* indexed by gate */
  Run *runs; i64 nruns, cruns;              /* runs[id], id from 1 */
  i64 clock, shards;
  Tl *tl; i64 ntl, ctl;
  Rel *rel; i64 nrel, crel; HMap relh;      /* (gate,kind,other) -> index+1 */
  Mail *input; i64 ninput, cinput; Mail *third; i64 nthird, cthird;
  Sec *sec; i64 nsec, csec; Out *out; i64 nout, cout; Refused *ref; i64 nref, cref;
  Hit *hit; i64 nhit, chit;
  Hop *hop; i64 nhop, chop;                 /* the stack: the row written last runs first */
  HMap memh;                                /* (hash of the seq, arrival|cell|about) -> the newest run that ended with its own receipts (the canonical instance a repeat points at) */
  HMap memt;                                /* (hash of the seq, 0) -> the head of the chain of memory rows with those symbols, any arrival (the input key of run_memory) */
  HMap shid;                                /* (gate, shard id) -> index+1 into the neuron's shards */
  i64 deduped;                              /* runs that repeated an earlier identical run and stored no receipts */
  struct Brain *tell;                       /* the brain told when a prompt's run ends (main -> sixth) */
  int arrival_of_third;                     /* what a line in third arrives from: the sixth (5) in main, main (6) in the sixth */
  HMap hith;                                /* (run, ordinal) -> index+1 into hit, for the hits that carried a call or spawn */
  i64 last_compacted, dropped_runs, dropped_receipts; i64 *deferred; int ndef, cdef;   /* runs the compaction passed while they were still running; looked at again next pass */   /* the cut: sub-runs made stubs when their main run completed */
  i64 hops_done, refused_n;
  i64 hop_ns, paste_ns, pastes, hops_run;  /* hops_run: hops done since this start (the mean is over these) */             /* where the time goes: inside the hops, inside mother's pastes */
  i64 cur_run; int cur_ord;                 /* the receipt whose span mother is pasting now (the returns it brings are made from it) */
  i64 sec_ns, secs;                         /* time inside the arrival of returns (secondary_in) and how many */                              /* the receipt whose span mother is pasting now (the returns it brings are made from it) */
  i64 rewrite_at;                           /* the clock when a shard's call or spawn last changed */
} Brain;

/* gates of the hand-laid core (egg6) */
enum { HEARD = 1, SAID = 2, SPACE = 3, MOTHER = 4, SIXTH = 5, MAIN = 6, BORN = 16, HOP_G = 17, CLOCK_G = 18, ME = 19, ABOVE = 20, NEWGATE = 21, REPLY = 22, WHAT = 23, DEF = 24, SAY = 25, KNOW = 26, REMEMBER = 27, SHAPE = 28, BUILD = 29 };

void   brain_init(Brain *b, const char *name, int is_main);
uint64_t strhash(const char *s);
uint64_t seqhash(const int *seq, int n);
Shard *shard_by_id(Brain *b, int gate, i64 id);
Shard *hop_shard(Brain *b); i64 hop_id(Brain *b); i64 nk_shard_rows(Brain *b); void nk_count_rows(Brain *b);
/* the place of a point and the pull of its relationships (nkxyz.c) */
int nk_xyz_open(const char *path); void nk_xyz_land(Brain *b, int gate, i64 shard, int before, int next, i64 run, int pos); void nk_xyz_settle(Brain *b, int passes, char *out, size_t cap); void nk_xyz_restep(Brain *b, i64 clock, const int *gates, int ngates, char *out, size_t cap); void nk_xyz_moved(Brain *b, i64 clock, int limit, char *out, size_t cap); void nk_xyz_base(Brain *b, const char *path); int nk_xyz_get(int gate, double *x, double *y, double *z, i64 *shard, int *before, int *next, i64 *at, i64 *run, int *moved); int nk_xyz_set(Brain *b, int gate, double x, double y, double z); void nk_xyz_sync(void);
i64    now_ns(void);
int    label_gate(Brain *b, const char *sym);           /* 0 when the symbol has no gate */
int    label_new(Brain *b, const char *sym);            /* the next gate, born into the encoder (no neuron region yet) */
Neuron*neuron_of(Brain *b, int gate);
Shard *shard_find(Brain *b, int gate, int before, int trigger);
Shard *shard_lay(Brain *b, int gate, int before, int trigger, i64 times);
Run   *run_of(Brain *b, i64 id);
i64    new_run(Brain *b, int arrival, i64 parent, int has_parent, int kind, int cell, int about);
void   val_set(Brain *b, Val *v, const char *s); void val_free(Val *v); void val_copy(Val *to, const Val *from); const char *val_text(Brain *b, const Val *v);
void   cell_set(Brain *b, i64 run, int cell, int state, const char *value);   /* INSERT OR REPLACE, with sheet_fill */
const char *cell_get(Brain *b, i64 run, int cell);                            /* state 1 and value not null, else NULL */
void   line_in(Brain *b, int which, const char *text);     /* which: 0 input (heard), 1 third */
void   secondary_in(Brain *b, i64 run, int cell, int gate, int about, const char *text, i64 src);
const int *nk_seq(Brain *b, i64 run, int *n);
int nk_learn_text(Brain *b, const char *s);                     /* C27 back population: every symbol of a text given a gate under the encoder as it stands (label_new); the count born */
int nk_merge(Brain *b, int h, int t, char *out, size_t cap);    /* C28 (the owner, 11-04 05:00): the hand laid neuron h merges into the neuron t of its word: shards (ids kept), node rows, memories, about, hits, arrived; the symbol of h names t */               /* a run's symbols: held, or a replay's source, or re-cut from the source row */
int    nk_receipts(Brain *b, i64 run, Rc **out, int *kept);   /* a run's receipts: held, or re-hopped from its symbols (kept = 0) */
const char *nk_source_text(int gate, i64 src);              /* nkio: the text of a source row (the source named by its gate) */
void   replay_push(Brain *b, i64 parent, i64 source, int kind);          /* from a formula: made from the receipt being pasted */
void   pump_batch(Brain *b, int n);                        /* n hops of this brain's stack */
int    pending(Brain *b);
void   nk_export(Brain *b, sqlite3 *db);                   /* every table as real rows, for the diff */

/* mother: the one SQLite connection the formulas are pasted into; its tables are the brains' regions (nkvt.c) */
int    mother_open(Brain *main, Brain *sixth, const char **sources, int nsources, const char *srcdir);
char  *mother_paste(const char *sql);                       /* ok | rows | error: ... (caller frees) */
sqlite3 *mother_db(void);
void   nkvt_register(sqlite3 *db, Brain *main, Brain *sixth);
void   nkvt_scans(char *out, size_t cap);                 /* keyed and scanned reads per table, as JSON rows */
#endif
