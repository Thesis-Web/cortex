/* nkio.c (2026-10-30): mother (the paste and the mother() function the sources' triggers call), the egg, the socket the door talks to,
   the export of every region as rows for the diff, and the loop: a request when one arrives, a batch of each brain's stack otherwise. */
#include "nk.h"
#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>

static sqlite3 *DB; static Brain *MAINP, *SIXTHP;
#define MAINB (*MAINP)
#define SIXTHB (*SIXTHP)
sqlite3 *mother_db(void){ return DB; }
/* the sources by gate: the text of a row read back when a formula asks for a return's symbols after the cut */
static int SRC_GATE[64]; static const char *SRC_NAME[64]; static sqlite3_stmt *SRC_Q[64]; static int NSRC_MAP; static char *SRC_TEXT; static size_t SRC_CAP;
static void src_remap(void){ for(int i = 0; i < NSRC_MAP; i++){ char *q = sqlite3_mprintf("SELECT gate FROM %w.me", SRC_NAME[i]); sqlite3_stmt *st = 0; if(sqlite3_prepare_v2(DB, q, -1, &st, 0) == SQLITE_OK && sqlite3_step(st) == SQLITE_ROW) SRC_GATE[i] = sqlite3_column_int(st, 0); if(st) sqlite3_finalize(st); sqlite3_free(q); } }
const char *nk_source_text(int gate, i64 src){
  static int tried; int found = 0; for(int i = 0; i < NSRC_MAP; i++) if(SRC_GATE[i] == gate) found = 1; if(!found && !tried++){ src_remap(); } if(!found){ found = 0; for(int i = 0; i < NSRC_MAP; i++) if(SRC_GATE[i] == gate) found = 1; if(!found) return 0; } tried = 0;
  for(int i = 0; i < NSRC_MAP; i++) if(SRC_GATE[i] == gate){
    if(!SRC_Q[i]){ char *q = sqlite3_mprintf("SELECT text FROM %w.corpus WHERE id = ?", SRC_NAME[i]); sqlite3_prepare_v2(DB, q, -1, &SRC_Q[i], 0); sqlite3_free(q); if(!SRC_Q[i]) return 0; }
    sqlite3_reset(SRC_Q[i]); sqlite3_bind_int64(SRC_Q[i], 1, src); const char *t = 0;
    if(sqlite3_step(SRC_Q[i]) == SQLITE_ROW){ const unsigned char *u = sqlite3_column_text(SRC_Q[i], 0); if(u){ size_t n = strlen((const char*)u) + 1; if(n > SRC_CAP){ SRC_CAP = n * 2; SRC_TEXT = realloc(SRC_TEXT, SRC_CAP); } memcpy(SRC_TEXT, u, n); t = SRC_TEXT; } }
    sqlite3_reset(SRC_Q[i]); return t; }
  return 0;
}

/* ---- a string builder ---- */
typedef struct { char *s; size_t n, cap; } SB;
static void sb_put(SB *b, const char *s, size_t n){ if(b->n + n + 1 > b->cap){ while(b->n + n + 1 > b->cap) b->cap = b->cap ? b->cap * 2 : 256; b->s = realloc(b->s, b->cap); } memcpy(b->s + b->n, s, n); b->n += n; b->s[b->n] = 0; }
static void sb_str(SB *b, const char *s){ sb_put(b, s, strlen(s)); }
static void sb_json(SB *b, const char *s){ sb_str(b, "\""); for(; *s; s++){ unsigned char c = *s; if(c == '"' || c == '\\'){ char t[3] = {'\\', c, 0}; sb_str(b, t); } else if(c < 0x20){ char t[8]; snprintf(t, sizeof t, "\\u%04x", c); sb_str(b, t); } else sb_put(b, (const char*)&c, 1); } sb_str(b, "\""); }
static void sb_fmt(SB *b, const char *f, ...){ char t[512]; va_list ap; va_start(ap, f); vsnprintf(t, sizeof t, f, ap); va_end(ap); sb_str(b, t); }

/* ---- mother: a text pasted at SQLite's prompt; the answer is ok, the rows, or the error ---- */
typedef struct Ent { char *text; sqlite3_stmt *st; int busy; struct Ent *next; } Ent;
#define NB 8192
static Ent *bucket[NB]; static int nent;
static unsigned hsh(const char *s){ unsigned h = 5381; while(*s) h = h * 33 + (unsigned char)*s++; return h % NB; }
static Ent *get(const char *sql, char **err){
  unsigned h = hsh(sql); Ent *e; for(e = bucket[h]; e; e = e->next) if(!e->busy && strcmp(e->text, sql) == 0){ sqlite3_reset(e->st); sqlite3_clear_bindings(e->st); return e; }
  sqlite3_stmt *st = 0; const char *tail = 0;
  if(sqlite3_prepare_v3(DB, sql, -1, SQLITE_PREPARE_PERSISTENT, &st, &tail) != SQLITE_OK){ *err = sqlite3_mprintf("%s", sqlite3_errmsg(DB)); return 0; }
  if(!st){ *err = sqlite3_mprintf("nothing to run"); return 0; }
  if(tail && *tail){ sqlite3_finalize(st); return 0; }
  e = sqlite3_malloc(sizeof(Ent)); e->text = sqlite3_mprintf("%s", sql); e->st = st; e->busy = 0; e->next = bucket[h]; bucket[h] = e; nent++; return e;
}
static int rows_cb(void *p, int argc, char **argv, char **col){ SB *b = (SB*)p; if(b->n) sb_str(b, "\n"); for(int i = 0; i < argc; i++){ if(i) sb_str(b, " | "); sb_str(b, argv[i] ? argv[i] : ""); } return 0; }
static void prof_add(const char *sql0, i64 ns);
/* the statements of a paste one at a time, each timed: what sqlite3_exec does, and the profile sees inside a paste */
static int exec_timed(const char *sql, int (*cb)(void*, int, char**, char**), void *arg, char **err){
  const char *p = sql;
  while(p && *p){ sqlite3_stmt *st = 0; const char *tail = 0; i64 t0 = now_ns();
    if(sqlite3_prepare_v2(DB, p, -1, &st, &tail) != SQLITE_OK){ *err = sqlite3_mprintf("%s", sqlite3_errmsg(DB)); return SQLITE_ERROR; }
    if(!st){ p = tail; continue; }
    int rc, n = sqlite3_column_count(st);
    while((rc = sqlite3_step(st)) == SQLITE_ROW){ char *v[64]; int m = n < 64 ? n : 64; for(int i = 0; i < m; i++) v[i] = (char*)sqlite3_column_text(st, i); cb(arg, m, v, 0); }
    if(rc != SQLITE_DONE){ *err = sqlite3_mprintf("%s", sqlite3_errmsg(DB)); sqlite3_finalize(st); return SQLITE_ERROR; }
    sqlite3_finalize(st); prof_add(p, now_ns() - t0); p = tail; while(p && (*p == ' ' || *p == '\n')) p++; }
  return SQLITE_OK;
}
static char *run_text(const char *sql, int argc, sqlite3_value **argv){
  char *err = 0; SB got = {0};
  if(argc == 0 && strchr(sql, ';')){ if(exec_timed(sql, rows_cb, &got, &err) != SQLITE_OK){ char *m = sqlite3_mprintf("error: %s", err); sqlite3_free(err); free(got.s); char *r = strdup(m); sqlite3_free(m); return r; } char *r = strdup(got.n ? got.s : "ok"); free(got.s); return r; }
  if(argc == 0){ if(sqlite3_exec(DB, sql, rows_cb, &got, &err) != SQLITE_OK){ char *m = sqlite3_mprintf("error: %s", err); sqlite3_free(err); free(got.s); char *r = strdup(m); sqlite3_free(m); return r; } char *r = strdup(got.n ? got.s : "ok"); free(got.s); return r; }
  Ent *e = get(sql, &err); sqlite3_stmt *st = e ? e->st : 0;
  if(!st){ if(err){ char *m = sqlite3_mprintf("error: %s", err); sqlite3_free(err); char *r = strdup(m); sqlite3_free(m); return r; }
    if(sqlite3_exec(DB, sql, rows_cb, &got, &err) != SQLITE_OK){ char *m = sqlite3_mprintf("error: %s", err); sqlite3_free(err); free(got.s); char *r = strdup(m); sqlite3_free(m); return r; } char *r = strdup(got.n ? got.s : "ok"); free(got.s); return r; }
  for(int i = 0; i < argc; i++) sqlite3_bind_value(st, i + 1, argv[i]);
  e->busy = 1; int rc;
  while((rc = sqlite3_step(st)) == SQLITE_ROW){ int n = sqlite3_column_count(st); if(got.n) sb_str(&got, "\n"); for(int c = 0; c < n; c++){ if(c) sb_str(&got, " | "); const char *v = (const char*)sqlite3_column_text(st, c); sb_str(&got, v ? v : ""); } }
  e->busy = 0;
  if(rc != SQLITE_DONE){ char *m = sqlite3_mprintf("error: %s", sqlite3_errmsg(DB)); sqlite3_reset(st); free(got.s); char *r = strdup(m); sqlite3_free(m); return r; }
  sqlite3_reset(st); char *r = strdup(got.n ? got.s : "ok"); free(got.s); return r;
}
/* where mother's time goes, per text pasted (the owner: profile every statement before reporting a run time) */
typedef struct Prof { char *text; i64 ns, n; struct Prof *next; } Prof;
static Prof *pbucket[NB]; static int nprof;
static void prof_add(const char *sql0, i64 ns){ static char key[400]; size_t n = 0; for(const char *s = sql0; *s && n < sizeof key - 2; s++){ if(*s >= '0' && *s <= '9'){ if(n && key[n-1] == '#') continue; key[n++] = '#'; } else key[n++] = *s; } key[n] = 0; const char *sql = key; unsigned h = hsh(sql); Prof *p; for(p = pbucket[h]; p; p = p->next) if(strcmp(p->text, sql) == 0){ p->ns += ns; p->n++; return; } p = malloc(sizeof(Prof)); p->text = strdup(sql); p->ns = ns; p->n = 1; p->next = pbucket[h]; pbucket[h] = p; nprof++; }
char *mother_paste(const char *sql){ i64 t0 = now_ns(); char *r = run_text(sql, 0, 0); prof_add(sql, now_ns() - t0); return r; }
static void mergeFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv);
static void motherFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){ const char *sql = (const char*)sqlite3_value_text(argv[0]); if(!sql){ sqlite3_result_text(ctx, "error: nothing to run", -1, SQLITE_STATIC); return; } i64 t0 = now_ns(); char *r = run_text(sql, argc - 1, argv + 1); prof_add(sql, now_ns() - t0); sqlite3_result_text(ctx, r, -1, SQLITE_TRANSIENT); free(r); }
int mother_open(Brain *main, Brain *sixth, const char **sources, int nsources, const char *srcdir){
  /* the brain's own tables (rel, asked, spawned ...) are stored beside it; the neurons' tables are the regions */
  const char *mp = getenv("NK_MAP"); char *fm = (mp && *mp) ? sqlite3_mprintf("%s.main.db", mp) : 0, *fs = (mp && *mp) ? sqlite3_mprintf("%s.sixth.db", mp) : 0;
  if(sqlite3_open(fm ? fm : ":memory:", &DB) != SQLITE_OK) return -1;
  if(fm) sqlite3_exec(DB, "PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA cache_size = -60000", 0, 0, 0);
  sqlite3_exec(DB, "PRAGMA recursive_triggers = ON", 0, 0, 0);
  { char *q = sqlite3_mprintf("ATTACH '%q' AS sixth", fs ? fs : ":memory:"); sqlite3_exec(DB, q, 0, 0, 0); sqlite3_free(q); }
  if(fs) sqlite3_exec(DB, "PRAGMA sixth.journal_mode = OFF; PRAGMA sixth.synchronous = OFF; PRAGMA sixth.cache_size = -60000", 0, 0, 0);
  for(int i = 0; i < nsources; i++){ char *q = sqlite3_mprintf("ATTACH '%q/%q.db' AS %w", srcdir, sources[i], sources[i]); char *e = 0; if(sqlite3_exec(DB, q, 0, 0, &e) != SQLITE_OK){ fprintf(stderr, "attach %s: %s\n", sources[i], e); sqlite3_free(e); } sqlite3_free(q); q = sqlite3_mprintf("PRAGMA %w.journal_mode = OFF; PRAGMA %w.synchronous = OFF", sources[i], sources[i]); sqlite3_exec(DB, q, 0, 0, 0); sqlite3_free(q); }   /* a source is read; only its mailbox is written: no journal and no flush to disk on every ask */
  sqlite3_create_function_v2(DB, "mother", -1, SQLITE_UTF8, 0, motherFunc, 0, 0, 0);
  sqlite3_create_function_v2(DB, "merge", 2, SQLITE_UTF8, 0, mergeFunc, 0, 0, 0);   /* C28: merge(h, t), the hand laid neuron h into the neuron t of its word, on the main brain */
  nkvt_register(DB, main, sixth);
  for(int i = 0; i < nsources && i < 64; i++){ char *q = sqlite3_mprintf("SELECT gate FROM %w.me", sources[i]); sqlite3_stmt *st = 0; if(sqlite3_prepare_v2(DB, q, -1, &st, 0) == SQLITE_OK && sqlite3_step(st) == SQLITE_ROW){ SRC_GATE[NSRC_MAP] = sqlite3_column_int(st, 0); SRC_NAME[NSRC_MAP] = sources[i]; NSRC_MAP++; } if(st) sqlite3_finalize(st); sqlite3_free(q); }
  return 0;
}

/* ---- the egg: the hand-laid symbols of egg6, in their order; the regions of all of them; row 0 of the arrivals and born ---- */
static void lay_egg(Brain *b, const char *symfile){
  FILE *f = fopen(symfile, "r"); if(!f){ perror(symfile); exit(1); }
  char line[4096]; while(fgets(line, sizeof line, f)){ size_t n = strlen(line); while(n && (line[n-1] == '\n' || line[n-1] == '\r')) line[--n] = 0; if(!n) continue; char *s = line; if(strcmp(s, "<space>") == 0) s = " "; label_new(b, s); }
  fclose(f);
  for(int g = 1; g <= b->label.n; g++) neuron_of(b, g)->born = 1;
  const char *row0[] = {"heard", "said", "mother", "sixth", "main", "born", "wn", "gcide", "mw", "mwt", "moby", "map", "sqldoc", "measured", "guess"};
  for(int i = 0; i < 15; i++){ int g = label_gate(b, row0[i]); if(g) shard_lay(b, g, 0, 0, 0); }
}

/* ---- reading back through the encoder (the bottom's show_out), for the door ---- */
static void decode_run(Brain *b, i64 run, SB *o, int limit){ int n; const int *seq = nk_seq(b, run, &n); if(!seq) return; int len = 0; for(int i = 0; i < n && len < limit; i++){ const char *s = seq[i] > 0 && seq[i] <= b->label.n ? b->label.sym[seq[i]] : "?"; sb_str(o, s); len += (int)strlen(s); } }
static void out_rows(Brain *b, i64 since, SB *o, int *first){
  for(i64 i = since; i < b->nout; i++){
    Out *w = &b->out[i]; if(!*first) sb_str(o, ","); *first = 0;
    const char *cname = (w->cell > 0 && w->cell <= b->label.n) ? b->label.sym[w->cell] : "?";
    SB v = {0};
    int is_ptr = (w->cell == REPLY || w->cell == DEF || w->cell == SAY || w->cell == REMEMBER); const char *wv = val_text(b, &w->v);
    if(is_ptr && wv && atoll(wv) > 0){ i64 rr = atoll(wv); Run *x = run_of(b, rr); sb_fmt(&v, "run %lld from %s: ", (long long)rr, (x && x->arrival <= b->label.n) ? b->label.sym[x->arrival] : "?"); decode_run(b, rr, &v, 1 << 30); }   /* C27: the output is never cut (the owner, 11-04: why would we do that) */
    else if((strcmp(cname, "known") == 0 || strcmp(cname, "unknown") == 0) && wv){ const char *p = wv; int any = 0; while(*p){ while(*p == ' ') p++; if(!*p) break; int g = atoi(p); while(*p && *p != ' ') p++; if(any) sb_str(&v, " "); any = 1; sb_str(&v, (g > 0 && g <= b->label.n) ? b->label.sym[g] : "?"); } if(!any) sb_str(&v, "(none)"); }
    else sb_str(&v, wv ? wv : "");
    sb_str(o, "["); sb_json(o, b->name); sb_fmt(o, ",%lld,", (long long)w->run); sb_json(o, cname); sb_str(o, ","); sb_json(o, v.s ? v.s : ""); sb_str(o, "]"); free(v.s);
  }
}

/* ---- the loop over both brains' stacks: a batch of each in turn ---- */
static void pump_all(int batch){ pump_batch(&MAINB, batch); pump_batch(&SIXTHB, batch); }
static double now_s(void){ struct timeval tv; gettimeofday(&tv, 0); return tv.tv_sec + tv.tv_usec / 1e6; }

int sheet_open_pub(Brain *b, i64 run);
static void mergeFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){ char out[512]; int h = sqlite3_value_int(argv[0]), t = sqlite3_value_int(argv[1]); nk_merge(&MAINB, h, t, out, sizeof out); sqlite3_result_text(ctx, out, -1, SQLITE_TRANSIENT); }
/* C27 back population (the owner, 11-04: yes to the back population of splits): every held definition row re-read from its source and every symbol given a gate under the encoder as it stands */
static void do_relabel(Brain *b, SB *o){
  double t0 = now_s(); int n0 = b->label.n; i64 points = 0, rows = 0, texts = 0, missing = 0, born = 0;
  for(int g = 1; g <= n0; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->nnode) continue; points++;
    for(int i = 0; i < n->nnode; i++){ Run *r = run_of(b, n->node[i].run); rows++; if(!r || !r->src || !r->srcgate){ missing++; continue; } const char *t = nk_source_text(r->srcgate, r->src); if(!t){ missing++; continue; } texts++; born += nk_learn_text(b, t); } }
  sb_fmt(o, "{\"points\":%lld,\"node_rows\":%lld,\"texts\":%lld,\"missing\":%lld,\"labels_before\":%d,\"labels_after\":%d,\"born\":%lld,\"seconds\":%.1f}", (long long)points, (long long)rows, (long long)texts, (long long)missing, n0, b->label.n, (long long)born, now_s() - t0);
}
static void do_type(Brain *b, const char *text, SB *o){
  i64 runs0 = b->nruns, hops0 = MAINB.hops_done + SIXTHB.hops_done, gates0 = MAINB.label.n, ref0 = MAINB.refused_n + SIXTHB.refused_n, outm = MAINB.nout, outs = SIXTHB.nout;
  double t0 = now_s();
  line_in(b, 0, text);
  i64 rid = runs0 + 1;
  /* until the typed line's own run has ended and its sheet is whole, or nothing is left to run; what the line left (the sixth's sends) runs on between requests */
  for(;;){ Run *r = run_of(b, rid); if((r && r->ended && !sheet_open_pub(b, rid)) || (pending(&MAINB) == 0 && pending(&SIXTHB) == 0)) break; pump_all(64); }
  if(getenv("NK_WAIT_EMPTY")) while(pending(&MAINB) || pending(&SIXTHB)) pump_all(64);
  i64 hits = 0; for(i64 i = rid; i <= b->nruns; i++){ Run *r = run_of(b, i); if(r && (r->root == rid || i == rid)) hits += r->nhops; }
  sb_fmt(o, "{\"schema\":\"%s\",\"run\":%lld,\"runs\":%lld,\"hits\":%lld,\"hops\":%lld,\"born\":%lld,\"refused\":%lld,\"seconds\":%.3f,\"out\":[", b->name, (long long)rid, (long long)(b->nruns - runs0), (long long)hits, (long long)(MAINB.hops_done + SIXTHB.hops_done - hops0), (long long)(MAINB.label.n - gates0), (long long)(MAINB.refused_n + SIXTHB.refused_n - ref0), now_s() - t0);
  int first = 1; out_rows(&MAINB, outm, o, &first); out_rows(&SIXTHB, outs, o, &first); sb_str(o, "]}");
}
static void do_q(const char *sql, SB *o){
  sqlite3_stmt *st = 0; if(sqlite3_prepare_v2(DB, sql, -1, &st, 0) != SQLITE_OK){ sb_str(o, "{\"error\":"); sb_json(o, sqlite3_errmsg(DB)); sb_str(o, "}"); return; }
  int n = sqlite3_column_count(st); sb_str(o, "{\"cols\":["); for(int i = 0; i < n; i++){ if(i) sb_str(o, ","); sb_json(o, sqlite3_column_name(st, i)); } sb_str(o, "],\"rows\":[");
  int first = 1, rc;
  while((rc = sqlite3_step(st)) == SQLITE_ROW){ if(!first) sb_str(o, ","); first = 0; sb_str(o, "["); for(int i = 0; i < n; i++){ if(i) sb_str(o, ","); int t = sqlite3_column_type(st, i); if(t == SQLITE_NULL) sb_str(o, "null"); else if(t == SQLITE_INTEGER) sb_fmt(o, "%lld", (long long)sqlite3_column_int64(st, i)); else if(t == SQLITE_FLOAT) sb_fmt(o, "%g", sqlite3_column_double(st, i)); else sb_json(o, (const char*)sqlite3_column_text(st, i)); } sb_str(o, "]"); }
  sb_str(o, "]"); if(rc != SQLITE_DONE){ sb_str(o, ",\"error\":"); sb_json(o, sqlite3_errmsg(DB)); } sb_str(o, "}"); sqlite3_finalize(st);
}
static const char *SRCDIR = "sources"; static const char **SRCS; static int NSRCS;
static void brain_stats(Brain *b, SB *o){
  double hop_us = b->hops_run ? (b->hop_ns - b->paste_ns) / 1000.0 / b->hops_run : 0, paste_us = b->pastes ? b->paste_ns / 1000.0 / b->pastes : 0;
  sb_fmt(o, "{\"defined\":%lld,", (long long)b->dropped_runs); sb_fmt(o, "\"runs\":%lld,\"hops\":%lld,\"pending\":%d,\"gates\":%d,\"refused\":%lld,\"shards\":%lld,\"shard_rows\":%lld,\"hop_us\":%.3f,\"pastes\":%lld,\"paste_us\":%.1f,\"hop_s\":%.3f,\"paste_s\":%.3f,\"returns\":%lld,\"return_us\":%.1f,\"return_s\":%.3f,\"receipts\":%lld,\"hops_run\":%lld,\"deduped_runs\":%lld,\"stubs\":%lld,\"receipts_dropped\":%lld}", (long long)b->nruns, (long long)b->hops_done, pending(b), b->label.n, (long long)b->refused_n, (long long)b->shards, (long long)nk_shard_rows(b), hop_us, (long long)b->pastes, paste_us, (b->hop_ns - b->paste_ns) / 1e9, b->paste_ns / 1e9, (long long)b->secs, b->secs ? b->sec_ns / 1000.0 / b->secs : 0, b->sec_ns / 1e9, (long long)(b->hops_done - b->dropped_receipts), (long long)b->hops_run, (long long)b->deduped, (long long)b->dropped_runs, (long long)b->dropped_receipts);
}
static void do_stats(SB *o){ struct mallinfo2 mi = mallinfo2(); sb_str(o, "{\"main\":"); brain_stats(&MAINB, o); sb_str(o, ",\"sixth\":"); brain_stats(&SIXTHB, o); sb_fmt(o, ",\"heap_MB\":%.0f}", (mi.uordblks + mi.hblkhd) / 1048576.0); }

static int prof_cmp(const void *a, const void *b){ const Prof *x = *(Prof* const*)a, *y = *(Prof* const*)b; return y->ns > x->ns ? 1 : (y->ns < x->ns ? -1 : 0); }
static void do_profile(SB *o, int top){
  Prof **all = malloc(sizeof(Prof*) * (nprof ? nprof : 1)); int n = 0; for(int i = 0; i < NB; i++) for(Prof *p = pbucket[i]; p; p = p->next) all[n++] = p;
  qsort(all, n, sizeof(Prof*), prof_cmp); i64 total = 0; for(int i = 0; i < n; i++) total += all[i]->ns;
  sb_fmt(o, "{\"texts\":%d,\"total_s\":%.3f,\"top\":[", n, total / 1e9);
  for(int i = 0; i < n && i < top; i++){ if(i) sb_str(o, ","); sb_fmt(o, "{\"s\":%.3f,\"n\":%lld,\"us\":%.0f,\"text\":", all[i]->ns / 1e9, (long long)all[i]->n, all[i]->ns / 1000.0 / all[i]->n); char t[200]; snprintf(t, sizeof t, "%.190s", all[i]->text); sb_json(o, t); sb_str(o, "}"); }
  sb_str(o, "]}"); free(all);
}

/* ---- the light page: a run and the part of the graph it touched, in one answer, every find by key ---- */
static void sb_text_of(Brain *b, i64 run, SB *o, int limit){ int n; const int *seq = nk_seq(b, run, &n); if(!seq){ sb_str(o, "\"\""); return; } SB t = {0}; int len = 0; for(int i = 0; i < n && len < limit; i++){ const char *s = seq[i] > 0 && seq[i] <= b->label.n ? b->label.sym[seq[i]] : "?"; sb_str(&t, s); len += (int)strlen(s); } if(n && len >= limit) sb_str(&t, "…"); sb_json(o, t.s ? t.s : ""); free(t.s); }
static sqlite3_stmt *REL_Q;
static void do_run(Brain *b, i64 id, SB *o){
  Run *root = run_of(b, id); if(!root){ sb_str(o, "{\"error\":\"no such run\"}"); return; }
  /* the tree under the run, breadth first, by the kids lists; capped so the answer stays small */
  enum { MAXRUNS = 600, MAXHOPS = 30000 };
  i64 *tree = malloc(sizeof(i64) * MAXRUNS); int nt = 0, qi = 0; tree[nt++] = id;
  while(qi < nt && nt < MAXRUNS){ Run *r = run_of(b, tree[qi++]); for(int i = 0; i < r->nkids && nt < MAXRUNS; i++) tree[nt++] = r->kids[i]; }
  sb_fmt(o, "{\"schema\":\"%s\",\"run\":{\"id\":%lld,\"arrival\":%d,\"parent\":", b->name, (long long)id, root->arrival); if(root->parent_set) sb_fmt(o, "%lld", (long long)root->parent); else sb_str(o, "null");
  sb_fmt(o, ",\"root\":%lld,\"kind\":%d,\"cell\":%d,\"about\":%d,\"at\":%lld,\"from_run\":%lld,\"from_ord\":%d,\"ended\":%d,\"complete\":%d,\"hops\":%d,\"same_as\":%lld,\"again\":%lld,\"kept\":%d,\"text\":", (long long)root->root, root->kind, root->cell, root->about, (long long)root->at, (long long)root->from_run, root->from_ord, root->ended, root->complete, root->nhops, (long long)root->same_as, (long long)root->again, root->kept); sb_text_of(b, id, o, 400);
  sb_str(o, "},\"tree\":["); int tot = 0;
  for(int i = 0; i < nt; i++){ Run *r = run_of(b, tree[i]); if(i) sb_str(o, ","); sb_fmt(o, "{\"id\":%lld,\"parent\":", (long long)tree[i]); if(r->parent_set) sb_fmt(o, "%lld", (long long)r->parent); else sb_str(o, "null"); sb_fmt(o, ",\"arrival\":%d,\"kind\":%d,\"cell\":%d,\"about\":%d,\"hops\":%d,\"ended\":%d,\"same_as\":%lld,\"kept\":%d,\"text\":", r->arrival, r->kind, r->cell, r->about, r->nhops, r->ended, (long long)r->same_as, r->kept); sb_text_of(b, tree[i], o, 120); sb_str(o, "}"); tot += r->nhops; }
  sb_fmt(o, "],\"tree_runs\":%d,\"tree_hops\":%d,\"hops\":[", nt, tot);
  /* the hops of the tree in the order they happened: every run's receipt indices are ascending, so a merge by receipt index gives the order */
  int *cur = calloc(nt, sizeof(int)); int first = 1, n = 0; HMap touched; hmap_init(&touched, 1024); HMap hitsh; hmap_init(&hitsh, 4096); int *tg = malloc(sizeof(int) * 4096); int ntg = 0, ctg = 4096;
  /* the hops of the tree, run by run in the order the runs were made; a repeated run shows the receipts of the run it repeats under its own number */
  for(int i = 0; i < nt && n < MAXHOPS; i++){ Rc *rcs; int kept; int nr = nk_receipts(b, tree[i], &rcs, &kept);
    for(int j = 0; j < nr && n < MAXHOPS; j++){ Rc *k = &rcs[j]; n++; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%d,%d,%lld,%d,%d]", (long long)tree[i], k->pos, k->gate, (long long)k->shard, k->via, kept ? j : -j);
      hmap_put(&hitsh, k->gate, k->shard, 1);
      if(!hmap_get(&touched, k->gate, 0)){ hmap_put(&touched, k->gate, 0, 1); if(ntg >= ctg){ ctg *= 2; tg = realloc(tg, sizeof(int) * ctg); } tg[ntg++] = k->gate; } } }
  { int kg = label_gate(b, "known"), ug = label_gate(b, "unknown"); for(int i = 0; i < root->ncells; i++){ Cell *c = &root->cells[i]; const char *cv = val_text(b, &c->v); if(!cv) continue; if(c->cell == WHAT || c->cell == kg || c->cell == ug){ const char *q = cv; int k = 0; while(*q && k < 120){ while(*q == ' ') q++; if(!*q) break; int g = atoi(q); while(*q && *q != ' ') q++; k++; if(g > 0 && g <= b->label.n && !hmap_get(&touched, g, 0)){ hmap_put(&touched, g, 0, 1); if(ntg >= ctg){ ctg *= 2; tg = realloc(tg, sizeof(int) * ctg); } tg[ntg++] = g; } } } } }
  sb_fmt(o, "],\"mem_gate\":%d,\"line\":[", root->mem_gate); { int nl = 0; const int *ls = nk_seq(b, id, &nl); int f2 = 1; for(int i = 0; ls && i < nl && i < 40; i++){ if(ls[i] == SPACE) continue; if(!f2) sb_str(o, ","); f2 = 0; sb_fmt(o, "%d", ls[i]); } }
  sb_fmt(o, "],\"hops_sent\":%d,\"gates\":{", n);
  /* every gate the hops touched: its symbol, its shards (the lines of the drawing), its definition rows, its memories, its relationship rows */
  if(!REL_Q){ char q[64]; snprintf(q, sizeof q, "SELECT kind, other FROM %s.rel WHERE gate = ?", b->name); sqlite3_prepare_v2(DB, q, -1, &REL_Q, 0); }
  for(int i = 0; i < ntg; i++){ int g = tg[i]; Neuron *nn = neuron_of(b, g); if(i) sb_str(o, ","); sb_fmt(o, "\"%d\":{\"s\":", g); sb_json(o, b->label.sym[g]); sb_fmt(o, ",\"born\":%d,\"nodes\":%d,\"mem\":%d,\"nshards\":%d,\"shards\":[", nn ? nn->born : 0, nn ? nn->nnode : 0, nn ? nn->nmem : 0, nn ? nn->nsh : 0);
    int ns = 0; if(nn) for(int j = 0; j < nn->nsh; j++){ Shard *s = &nn->sh[j]; if(!hmap_get(&hitsh, g, s->id)) continue; if(ns++) sb_str(o, ","); sb_fmt(o, "[%lld,%d,%d,%lld,%lld,%lld]", (long long)s->id, s->before, s->trigger, (long long)s->call, (long long)s->spawn, (long long)s->times); }
    sb_str(o, "],\"rel\":["); int nr = 0;
    if(REL_Q){ sqlite3_bind_int(REL_Q, 1, g); while(sqlite3_step(REL_Q) == SQLITE_ROW && nr < 24){ if(nr) sb_str(o, ","); sb_fmt(o, "[%d,%d]", sqlite3_column_int(REL_Q, 0), sqlite3_column_int(REL_Q, 1)); nr++; } sqlite3_reset(REL_Q); }
    sb_str(o, "]}"); }
  /* the symbols of the gates the shards and relationship rows point at, so every drawn line has two named ends */
  sb_str(o, "},\"names\":{"); HMap named; hmap_init(&named, 2048); first = 1;
  for(int i = 0; i < ntg; i++){ Neuron *nn = neuron_of(b, tg[i]); if(!nn) continue; int cand[4]; for(int j = 0; j < nn->nsh; j++){ if(!hmap_get(&hitsh, tg[i], nn->sh[j].id)) continue; cand[0] = nn->sh[j].before; cand[1] = nn->sh[j].trigger; for(int c = 0; c < 2; c++){ int g = cand[c]; if(g > 0 && g <= b->label.n && !hmap_get(&touched, g, 0) && !hmap_get(&named, g, 0)){ hmap_put(&named, g, 0, 1); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":", g); sb_json(o, b->label.sym[g]); } } }
    if(REL_Q){ sqlite3_bind_int(REL_Q, 1, tg[i]); int nr = 0; while(sqlite3_step(REL_Q) == SQLITE_ROW && nr++ < 24){ int gs[2] = { sqlite3_column_int(REL_Q, 1), sqlite3_column_int(REL_Q, 0) }; for(int c = 0; c < 2; c++){ int g = gs[c]; if(g > 0 && g <= b->label.n && !hmap_get(&touched, g, 0) && !hmap_get(&named, g, 0)){ hmap_put(&named, g, 0, 1); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":", g); sb_json(o, b->label.sym[g]); } } } sqlite3_reset(REL_Q); } }
  for(int i = 0; i < root->ncells; i++){ int g = root->cells[i].cell; if(g > 0 && g <= b->label.n && !hmap_get(&touched, g, 0) && !hmap_get(&named, g, 0)){ hmap_put(&named, g, 0, 1); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":", g); sb_json(o, b->label.sym[g]); } }
  /* the cells of the run, a run-valued cell read back as that run's text */
  sb_str(o, "},\"cells\":[");
  for(int i = 0; i < root->ncells; i++){ Cell *c = &root->cells[i]; const char *cv = val_text(b, &c->v); if(i) sb_str(o, ","); sb_fmt(o, "[%d,%d,", c->cell, c->state); if(cv) sb_json(o, cv); else sb_str(o, "null"); sb_str(o, ",");
    /* the cells that name a run: me, above, reply, def, say, remember, shape (the call); what names a gate or a number and is left as it is */
    int runcell = (c->cell == ME || c->cell == ABOVE || c->cell == REPLY || c->cell == DEF || c->cell == SAY || c->cell == REMEMBER || c->cell == SHAPE);
    i64 rv = (cv && runcell) ? atoll(cv) : 0; Run *x = rv > 0 ? run_of(b, rv) : 0;
    if(x && strspn(cv, "0123456789") == strlen(cv)){ sb_fmt(o, "{\"run\":%lld,\"arrival\":%d,\"text\":", (long long)rv, x->arrival); sb_text_of(b, rv, o, 1 << 30); sb_str(o, "}"); }   /* C27: a say, def or reply cell read back whole */
    else if(cv && (c->cell == label_gate(b, "known") || c->cell == label_gate(b, "unknown"))){ /* a list of gates: read back as symbols, the first sixty */ SB t = {0}; const char *q = cv; int nw = 0, total = 0; while(*q){ while(*q == ' ') q++; if(!*q) break; int g = atoi(q); while(*q && *q != ' ') q++; total++; if(nw < 60 && g > 0 && g <= b->label.n){ if(nw) sb_str(&t, " "); sb_str(&t, b->label.sym[g]); nw++; } } if(total > nw) sb_fmt(&t, " … %d in all", total); sb_fmt(o, "{\"words\":%d,\"text\":", total); sb_json(o, t.s ? t.s : ""); sb_str(o, "}"); free(t.s); }
    else sb_str(o, "null");
    sb_str(o, "]"); }
  /* step back: from this run to the line that started it, through the receipt each was made from */
  sb_str(o, "],\"back\":["); first = 1; i64 cur_run = id; int depth = 0;
  while(cur_run && depth < 64){ Run *r = run_of(b, cur_run); if(!r) break; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "{\"depth\":%d,\"run\":%lld,\"arrival\":%d,\"cell\":%d,\"text\":", depth, (long long)cur_run, r->arrival, r->cell); sb_text_of(b, cur_run, o, 100);
    if(r->from_run > 0){ Rc *frcs; int fk; int fn = nk_receipts(b, r->from_run, &frcs, &fk); if(r->from_ord >= 0 && r->from_ord < fn){ Rc *k = &frcs[r->from_ord]; sb_fmt(o, ",\"hit\":{\"run\":%lld,\"ord\":%d,\"pos\":%d,\"gate\":%d,\"shard\":%lld,\"via\":%d,\"kept\":%d}", (long long)r->from_run, r->from_ord, k->pos, k->gate, (long long)k->shard, k->via, fk); } }
    sb_str(o, "}"); if(!r->parent_set) break; cur_run = r->parent; depth++; }
  sb_str(o, "]}");
  free(tree); free(cur); free(tg); free(touched.e); free(named.e); free(hitsh.e);
}
static void do_newest(Brain *b, int n, SB *o){
  sb_fmt(o, "{\"schema\":\"%s\",\"lines\":[", b->name); int first = 1;
  for(i64 i = b->ninput - 1; i >= 0 && i >= b->ninput - n; i--){ Mail *m = &b->input[i]; Run *r = run_of(b, m->run); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "{\"id\":%lld,\"run\":%lld,\"from\":\"heard\",\"ended\":%d,\"hops\":%d,\"text\":", (long long)m->id, (long long)m->run, r ? r->ended : 0, r ? r->nhops : 0); sb_text_of(b, m->run, o, 120); sb_str(o, "}"); }
  sb_str(o, "],\"told\":["); first = 1;
  for(i64 i = b->nthird - 1; i >= 0 && i >= b->nthird - n; i--){ Mail *m = &b->third[i]; Run *r = run_of(b, m->run); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "{\"id\":%lld,\"run\":%lld,\"from\":\"%s\",\"ended\":%d,\"hops\":%d,\"text\":", (long long)m->id, (long long)m->run, b->is_main ? "sixth" : "main", r ? r->ended : 0, r ? r->nhops : 0); sb_text_of(b, m->run, o, 120); sb_str(o, "}"); }
  sb_fmt(o, "],\"inputs\":%lld,\"told_n\":%lld}", (long long)b->ninput, (long long)b->nthird);
}
/* where the memory is: every region summed from its own sizes, and the heap and SQLite as they report themselves */
static void do_memory(Brain *b, SB *o){
  double MB = 1024.0 * 1024.0; i64 runs_b = (i64)b->cruns * sizeof(Run), rcs_b = 0, seq_b = 0, cells_b = 0, kids_b = 0, mem_b = 0, nkept = 0, nseqheld = 0, ncells = 0;
  for(i64 i = 1; i <= b->nruns; i++){ Run *r = &b->runs[i]; rcs_b += (i64)r->crc * sizeof(Rc); if(r->nrc) nkept++; if(r->seq && !r->seq_shared){ seq_b += ((r->nseq + 63) / 64) * 64 * sizeof(int); nseqheld++; } for(int c = 0; c < r->ncells; c++){ cells_b += sizeof(Cell) + (r->cells[c].v.kind >= 2 ? (i64)r->cells[c].v.n * 4 + 16 : 0); ncells++; } cells_b += (i64)(r->ccells - r->ncells) * sizeof(Cell); kids_b += (i64)r->ckids * 8; }
  i64 sh_b = 0, nsh = 0, nmaps_b = 0, lists_b = 0, node_b = 0;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; sh_b += (i64)n->csh * sizeof(Shard); nsh += n->nsh; nmaps_b += (i64)n->h.cap * sizeof(HEnt); lists_b += (i64)(n->cabout + n->cmem + n->chits + n->carrived) * 8; node_b += (i64)n->cnode * sizeof(NodeRow); }
  i64 label_b = (i64)b->label.cap * 8 + (i64)b->label.h.cap * sizeof(HEnt); for(int g = 1; g <= b->label.n; g++) label_b += strlen(b->label.sym[g]) + 1 + 16;
  i64 maps_b = (i64)(b->memh.cap + b->memt.cap + b->shid.cap + b->hith.cap + b->relh.cap) * sizeof(HEnt);
  i64 mail_b = (i64)b->cinput * sizeof(Mail) + (i64)b->cthird * sizeof(Mail) + (i64)b->csec * sizeof(Sec) + (i64)b->cout * sizeof(Out) + (i64)b->ctl * sizeof(Tl) + (i64)b->chit * sizeof(Hit) + (i64)b->chop * sizeof(Hop) + (i64)b->cnr * sizeof(Neuron);
  struct mallinfo2 mi = mallinfo2();
  sb_fmt(o, "{\"brain\":\"%s\",\"runs\":%lld,\"run_structs_MB\":%.1f,\"receipts_kept\":%lld,\"receipts_MB\":%.1f,\"runs_with_receipts\":%lld,\"seq_held_runs\":%lld,\"seq_MB\":%.1f,\"cells\":%lld,\"cells_MB\":%.1f,\"kids_MB\":%.1f,\"memory_text_MB\":%.1f,\"shards\":%lld,\"shards_MB\":%.1f,\"shard_maps_MB\":%.1f,\"neuron_lists_MB\":%.1f,\"nodes_MB\":%.1f,\"labels_MB\":%.1f,\"brain_maps_MB\":%.1f,\"mail_and_misc_MB\":%.1f,\"heap_in_use_MB\":%.1f,\"heap_free_MB\":%.1f,\"sqlite_MB\":%.1f}",
    b->name, (long long)b->nruns, runs_b / MB, (long long)(b->hops_done - b->dropped_receipts), rcs_b / MB, (long long)nkept, (long long)nseqheld, seq_b / MB, (long long)ncells, cells_b / MB, kids_b / MB, mem_b / MB, (long long)nsh, sh_b / MB, nmaps_b / MB, lists_b / MB, node_b / MB, label_b / MB, maps_b / MB, mail_b / MB, mi.uordblks / MB, mi.fordblks / MB, sqlite3_memory_used() / MB);
}
#define GROW2(arr, n, cap, T) do { if((n) >= (cap)){ (cap) = (cap) ? (cap) * 2 : 2; (arr) = realloc((arr), (cap) * sizeof(T)); } } while(0)
static void do_repair(Brain *b, SB *o){
  i64 points = 0, rows = 0, defined = 0;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue;
    if(n->nnode == 0) for(int i = 0; i < n->nabout; i++){ Run *r = run_of(b, n->about_runs[i]); if(!r || r->kind != 3 || r->same_as || r->arrival == 15 || r->arrival == MOTHER || !r->ended) continue; if(n->nnode == 0) points++; GROW2(n->node, n->nnode, n->cnode, NodeRow); n->node[n->nnode].source = r->arrival; n->node[n->nnode].run = r - b->runs; n->nnode++; rows++; }
    if(n->nnode) defined++; }
  b->dropped_runs = defined; sb_fmt(o, "{\"points_repaired\":%lld,\"node_rows\":%lld,\"defined\":%lld}", (long long)points, (long long)rows, (long long)defined);
}
/* ---- the hop laid as one shard: the back population. The owner (2026-11-01): "you do not have to log every different hop as a dna shard ...
   it means the trigger to go the hop meaning points to the same shard of dna for all points"; "it does require or can require back population of
   existing dna shard triggers". Every row that only recorded a pass (no call, no spawn) folds into the hop shard: its times go there, the row goes,
   and every receipt, memory row and firing that named it now names the hop shard. Kept: a row with a call or a spawn, the egg's row 0 of the
   core, the ok neuron's rows (its marks), the hop shard itself. A pass over the brain, once. ---- */
static void do_hop(Brain *b, SB *o){
  double t0 = now_s(); int ok = label_gate(b, "ok"); Shard *hop = hop_shard(b); i64 hid = hop->id;
  i64 rows0 = 0, kept = 0, folded = 0, moved = 0, rcs = 0, mems = 0, evs = 0;
  free(b->shid.e); b->shid.e = 0; hmap_init(&b->shid, 1 << 16);
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->nsh) continue; rows0 += n->nsh;
    int k = 0;
    for(int j = 0; j < n->nsh; j++){ Shard *s = &n->sh[j];
      int keep = s->call || s->spawn || g == ok || s->id == hid || (s->before == 0 && s->trigger == 0 && g <= 90);
      if(keep){ if(k != j) n->sh[k] = *s; k++; } else { moved += s->times; folded++; } }
    n->nsh = k;
    free(n->h.e); n->h.e = 0; n->h.n = 0; n->h.cap = 0;
    if(k){ size_t hc = 8; while(hc * 7 < (size_t)(k + 1) * 10) hc <<= 1; hmap_init(&n->h, hc); for(int j = 0; j < k; j++){ hmap_put(&n->h, n->sh[j].before, n->sh[j].trigger, j + 1); hmap_put(&b->shid, g, n->sh[j].id, j + 1); } }
    if(k == 0){ free(n->sh); n->sh = 0; n->csh = 0; }
    else if(n->csh > k * 2 + 8){ Shard *ns = malloc(sizeof(Shard) * (k + 2)); memcpy(ns, n->sh, sizeof(Shard) * k); free(n->sh); n->sh = ns; n->csh = k + 2; }
    kept += k; }
  hop->times += moved;
  for(i64 i = 1; i <= b->nruns; i++){ Run *r = &b->runs[i];
    if(r->rcs) for(int j = 0; j < r->nrc; j++){ Rc *c = &r->rcs[j]; if(c->shard == hid) continue; if(!hmap_get(&b->shid, c->gate, c->shard)){ c->shard = hid; rcs++; } }
    if(r->has_mem && r->mem_shard && r->mem_shard != hid && !hmap_get(&b->shid, r->mem_gate, r->mem_shard)){ r->mem_shard = hid; mems++; }
    if(r->ev) for(int j = 0; j < r->nev; j++){ Ev *e = &r->ev[j]; if(e->shard != hid && !hmap_get(&b->shid, e->gate, e->shard)){ e->shard = hid; evs++; } } }
  nk_count_rows(b);
  sb_fmt(o, "{\"brain\":\"%s\",\"rows_before\":%lld,\"rows_kept\":%lld,\"rows_folded\":%lld,\"times_moved\":%lld,\"hop_shard\":%lld,\"hop_times\":%lld,\"receipts_repointed\":%lld,\"memory_rows_repointed\":%lld,\"firings_repointed\":%lld,\"seconds\":%.1f}",
    b->name, (long long)rows0, (long long)kept, (long long)folded, (long long)moved, (long long)hid, (long long)hop->times, (long long)rcs, (long long)mems, (long long)evs, now_s() - t0);
}
/* ---- the whole-brain page's bundle: the brain at the scale a page can hold. The DNA rows hit at least T times (T chosen so at most CAP rows go),
   the symbols those rows name, every point's definition and memory counts, the relationship rows of those points, the newest K lines with every
   run under them, their sheets, receipts and outputs. Read from the regions in C, by walking them once; the page asks for it whole. ---- */

/* rels N: the relationship rows of the next N defined points, laid from their definition rows (WordNet's and Wiktionary's bracketed markers,
   mapped by main.relmap), for points that hold no relationship row beyond like/opposite/capitalized yet. A cursor keeps the place between calls. */
static int RELS_G = 1;
static void do_rels(Brain *b, int npoints, SB *o){
  double t0 = now_s(); int wikt = label_gate(b, "wikt"), like = label_gate(b, "like"), opp = label_gate(b, "opposite"), capd = label_gate(b, "capitalized");
  enum { LB = 143, RB = 147, LC = 173, RC = 177, COLON = 68, SEMI = 45, COMMA = 38 };
  char *mk[128]; int mkind[128]; int nmk = 0;
  { sqlite3_stmt *m = 0; sqlite3_prepare_v2(DB, "SELECT marker, kind FROM main.relmap", -1, &m, 0);
    while(m && sqlite3_step(m) == SQLITE_ROW && nmk < 128){ const char *a = (const char*)sqlite3_column_text(m, 0), *k = (const char*)sqlite3_column_text(m, 1); int kg = k ? label_gate(b, k) : 0; if(a && kg){ mk[nmk] = strdup(a); mkind[nmk] = kg; nmk++; } }
    if(m) sqlite3_finalize(m); }
  if(!nmk){ sb_str(o, "{\"error\":\"main.relmap holds no marker the encoder knows\"}"); return; }
  static sqlite3_stmt *HAS, *INS; if(!HAS) sqlite3_prepare_v2(DB, "SELECT 1 FROM main.rel WHERE gate = ? AND kind NOT IN (?, ?, ?) LIMIT 1", -1, &HAS, 0);
  if(!INS) sqlite3_prepare_v2(DB, "INSERT OR IGNORE INTO main.rel (gate, kind, other, run) VALUES (?, ?, ?, ?)", -1, &INS, 0);
  i64 points = 0, skipped = 0, returns = 0, rows = 0; int g = RELS_G; char marker[256];
  for(; g <= b->label.n && points < npoints; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->nnode) continue; points++;
    sqlite3_reset(HAS); sqlite3_bind_int(HAS, 1, g); sqlite3_bind_int(HAS, 2, like); sqlite3_bind_int(HAS, 3, opp); sqlite3_bind_int(HAS, 4, capd);
    if(sqlite3_step(HAS) == SQLITE_ROW){ skipped++; continue; }
    for(int j = 0; j < n->nnode; j++){ i64 run = n->node[j].run; Run *r = run_of(b, run); if(!r || !(r->arrival == 7 || r->arrival == wikt)) continue;
      int ns; const int *sq = nk_seq(b, run, &ns); if(!sq || ns < 4) continue; returns++;
      for(int i = 0; i < ns; i++){ if(sq[i] != LB) continue;
        int c = -1, e = -1; for(int k = i + 1; k < ns; k++){ if(sq[k] == COLON || sq[k] == RB){ c = k; break; } } if(c < 0 || sq[c] != COLON) continue;
        for(int k = c + 1; k < ns; k++){ if(sq[k] == RB){ e = k; break; } if(sq[k] == LB) break; } if(e < 0) continue;
        int ml = 0; marker[0] = 0; for(int k = i + 1; k < c; k++){ if(sq[k] == SPACE || sq[k] <= 0 || sq[k] > b->label.n) continue; const char *w = b->label.sym[sq[k]]; int wl = (int)strlen(w); if(ml + wl + 2 >= (int)sizeof marker) break; if(ml) marker[ml++] = ' '; memcpy(marker + ml, w, wl); ml += wl; marker[ml] = 0; }
        int kind = 0; for(int k = 0; k < nmk; k++) if(strcmp(mk[k], marker) == 0){ kind = mkind[k]; break; } if(!kind) continue;
        for(int t = c + 1; t < e; t++){ int x = sq[t]; if(x <= 0 || x > b->label.n || x == r->about) continue; unsigned char c0 = (unsigned char)b->label.sym[x][0]; if(!((c0 >= 'A' && c0 <= 'Z') || (c0 >= 'a' && c0 <= 'z'))) continue;
          int pv = t - 1; while(pv > i && sq[pv] == SPACE) pv--; int nx = t + 1; while(nx < e && sq[nx] == SPACE) nx++;
          int pg = sq[pv], ng = sq[nx]; if(!(pg == LC || pg == COLON || pg == SEMI || pg == COMMA)) continue; if(!(ng == RC || ng == SEMI || ng == RB || ng == COMMA)) continue;
          sqlite3_reset(INS); sqlite3_bind_int(INS, 1, r->about); sqlite3_bind_int(INS, 2, kind); sqlite3_bind_int(INS, 3, x); sqlite3_bind_int64(INS, 4, run); if(sqlite3_step(INS) == SQLITE_DONE) rows += sqlite3_changes(DB); } } } }
  RELS_G = g; for(int k = 0; k < nmk; k++) free(mk[k]);
  sb_fmt(o, "{\"brain\":\"%s\",\"from_gate\":%d,\"next_gate\":%d,\"gates\":%d,\"done\":%s,\"points\":%lld,\"already_had\":%lld,\"returns_read\":%lld,\"rows_laid\":%lld,\"markers\":%d,\"seconds\":%.1f}", b->name, RELS_G - (int)(g - RELS_G), g, b->label.n, g > b->label.n ? "true" : "false", (long long)points, (long long)skipped, (long long)returns, (long long)rows, nmk, now_s() - t0);
}
static void do_bundle(Brain *b, int K, SB *o){
  enum { CAP = 1200000, MAXR = 120000 };
  i64 hist[65]; memset(hist, 0, sizeof hist);
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; for(int j = 0; j < n->nsh; j++){ i64 t = n->sh[j].times; int k = 0; while(t > 1 && k < 64){ t >>= 1; k++; } hist[k]++; } }
  i64 acc = 0; int T = 1; for(int k = 64; k >= 0; k--){ if(acc + hist[k] > CAP && acc > 0){ T = 1 << (k + 1); break; } acc += hist[k]; T = 1 << k; }
  char *inc = calloc(b->label.n + 2, 1);
  sb_fmt(o, "{\"T\":%d,\"dna\":[", T); int first = 1; i64 ndna = 0;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; for(int j = 0; j < n->nsh; j++){ Shard *s = &n->sh[j]; if(s->times < T) continue; if(!first) sb_str(o, ","); first = 0; ndna++; inc[g] = 1; if(s->before > 0 && s->before <= b->label.n) inc[s->before] = 1; if(s->trigger > 0 && s->trigger <= b->label.n) inc[s->trigger] = 1; sb_fmt(o, "[%d,%lld,%d,%d,%lld,%lld,%lld]", g, (long long)s->id, s->before, s->trigger, (long long)s->call, (long long)s->spawn, (long long)s->times); } }
  for(int g = 1; g <= 90 && g <= b->label.n; g++) inc[g] = 1;
  /* the newest K lines and every run under them */
  i64 *runs = malloc(sizeof(i64) * MAXR); int nr = 0; HMap seen; hmap_init(&seen, 1 << 17);
  for(int which = 0; which < 2; which++){ Mail *box = which ? b->third : b->input; i64 nbox = which ? b->nthird : b->ninput; for(i64 i = nbox - 1; i >= 0 && i >= nbox - K && nr < MAXR; i--){ i64 top = box[i].run; if(!top || hmap_get(&seen, top, 0)) continue; int head = nr; runs[nr++] = top; hmap_put(&seen, top, 0, 1); while(head < nr && nr < MAXR){ Run *r = run_of(b, runs[head++]); if(!r) continue; for(int k = 0; k < r->nkids && nr < MAXR; k++){ i64 kid = r->kids[k]; if(hmap_get(&seen, kid, 0)) continue; hmap_put(&seen, kid, 0, 1); runs[nr++] = kid; } } } }
  /* the symbols of those runs' lines, so the page decodes them */
  for(int i = 0; i < nr; i++){ Run *rr = run_of(b, runs[i]); int n = rr && rr->seq ? rr->nseq : 0; const int *sq = rr ? rr->seq : 0; for(int k = 0; sq && k < n; k++) if(sq[k] > 0 && sq[k] <= b->label.n) inc[sq[k]] = 1; Run *r = run_of(b, runs[i]); if(r) for(int c = 0; c < r->ncells; c++){ int cg = r->cells[c].cell; if(cg > 0 && cg <= b->label.n) inc[cg] = 1; } }
  sb_str(o, "],\"rel\":["); first = 1; i64 nrel = 0;
  if(!REL_Q){ char q[64]; snprintf(q, sizeof q, "SELECT kind, other FROM %s.rel WHERE gate = ?", b->name); sqlite3_prepare_v2(DB, q, -1, &REL_Q, 0); }
  { /* the relationship rows of the included points, in one pass over the brain's own rel table (the page asks for the brain whole) */
    static sqlite3_stmt *ALLREL; if(!ALLREL){ char q[64]; snprintf(q, sizeof q, "SELECT gate, kind, other, run FROM %s.rel", b->name); sqlite3_prepare_v2(DB, q, -1, &ALLREL, 0); }
    if(ALLREL){ while(sqlite3_step(ALLREL) == SQLITE_ROW && nrel < CAP){ int g = sqlite3_column_int(ALLREL, 0); if(g <= 0 || g > b->label.n || !inc[g]) continue; int kind = sqlite3_column_int(ALLREL, 1), other = sqlite3_column_int(ALLREL, 2); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%d,%d,%lld]", g, kind, other, (long long)sqlite3_column_int64(ALLREL, 3)); nrel++; if(kind > 0 && kind <= b->label.n) inc[kind] = 1; if(other > 0 && other <= b->label.n) inc[other] = 1; } sqlite3_reset(ALLREL); } }
  sb_str(o, "],\"runs\":["); first = 1;
  for(int i = 0; i < nr; i++){ Run *r = run_of(b, runs[i]); if(!r) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%d,", (long long)runs[i], r->arrival); if(r->parent_set) sb_fmt(o, "%lld", (long long)r->parent); else sb_str(o, "null"); sb_fmt(o, ",%lld,%d,", (long long)r->root, r->kind); if(r->cell) sb_fmt(o, "%d", r->cell); else sb_str(o, "null"); sb_str(o, ","); if(r->about) sb_fmt(o, "%d", r->about); else sb_str(o, "null"); sb_fmt(o, ",%lld,%d]", (long long)r->at, r->nhops); }
  sb_str(o, "],\"first\":{"); first = 1;
  for(int i = 0; i < nr; i++){ Run *rr = run_of(b, runs[i]); const int *sq = rr ? rr->seq : 0; int n = sq ? rr->nseq : 0; if(!sq || n < 1) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%lld\":%d", (long long)runs[i], sq[0]); }
  sb_str(o, "},\"inputs\":["); first = 1;
  for(int which = 0; which < 2; which++){ Mail *box = which ? b->third : b->input; i64 nbox = which ? b->nthird : b->ninput; for(i64 i = (nbox - K > 0 ? nbox - K : 0); i < nbox; i++){ if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[\"%s\",%lld,%lld]", which ? (b->is_main ? "sixth" : "main") : "main", (long long)box[i].id, (long long)box[i].run); } }
  sb_str(o, "],\"out\":["); first = 1;
  for(i64 i = (b->nout - 4000 > 0 ? b->nout - 4000 : 0); i < b->nout; i++){ Out *w = &b->out[i]; if(!hmap_get(&seen, w->run, 0)) continue; const char *v = val_text(b, &w->v); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%lld,%d,", (long long)w->id, (long long)w->run, w->cell); if(v) sb_json(o, v); else sb_str(o, "null"); sb_str(o, "]"); }
  /* the definitions: for the included points, which sources answered (the page's defines and answers reads) */
  sb_str(o, "],\"answ\":["); first = 1;
  for(int g = 1; g <= b->label.n; g++){ if(!inc[g]) continue; Neuron *n = neuron_of(b, g); if(!n || !n->nnode) continue; int seenSrc[64]; int ns = 0; for(int j = 0; j < n->nnode; j++){ int src = n->node[j].source; int dup = 0; for(int k = 0; k < ns; k++) if(seenSrc[k] == src) dup = 1; if(dup || ns >= 64) continue; seenSrc[ns++] = src; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%d,%lld]", src, g, (long long)n->node[j].run); } }
  /* the definition words of the newest lines' points: each point's node rows, their returns read back through the encoder (the page's
     definition lines, "a symbol to the words of the lines its sources returned") */
  sb_str(o, "],\"defw\":["); first = 1; { HMap dw; hmap_init(&dw, 1 << 16); int lines = 0;
    for(int i = 0; i < nr && lines < 400; i++){ Run *r = run_of(b, runs[i]); if(!r || r->kind != 0) continue; lines++; const char *w = cell_get(b, runs[i], WHAT); if(!w) continue; int g = atoi(w); Neuron *n = (g > 0 && g <= b->label.n) ? neuron_of(b, g) : 0; if(!n || !n->nnode) continue;
      for(int j = 0; j < n->nnode && j < 300; j++){ i64 rr = n->node[j].run; int ns; const int *sq = nk_seq(b, rr, &ns);
        for(int k = 0; sq && k < ns; k++){ int x = sq[k]; if(x <= 0 || x > b->label.n || x == g) continue; unsigned char c0 = (unsigned char)b->label.sym[x][0]; if(!((c0 >= 'A' && c0 <= 'Z') || (c0 >= 'a' && c0 <= 'z'))) continue; if(hmap_get(&dw, g, x)) continue; hmap_put(&dw, g, x, rr); inc[x] = 1; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%d,%lld]", g, x, (long long)rr); } } }
    free(dw.e); }
  sb_str(o, "],\"memrows\":["); first = 1;
  for(int i = 0; i < nr; i++){ Run *r = run_of(b, runs[i]); if(!r || !r->has_mem || r->same_as || !r->seq) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%d,%lld,\"", (long long)runs[i], r->mem_gate, (long long)r->mem_shard); for(int k = 0; k < r->nseq && k < 60; k++) sb_fmt(o, k ? " %d" : "%d", r->seq[k]); sb_str(o, "\"]"); }
  sb_str(o, "],\"hit_dna\":["); first = 1; { HMap hs; hmap_init(&hs, 1 << 16);
  for(int i = nr - 1; i >= 0; i--){ Run *r = run_of(b, runs[i]); if(!r || !r->nrc) continue; for(int j = 0; j < r->nrc; j++){ Rc *k = &r->rcs[j]; if(hmap_get(&hs, k->gate, k->shard)) continue; hmap_put(&hs, k->gate, k->shard, 1); Shard *sh = shard_by_id(b, k->gate, k->shard); if(!sh || sh->times >= T) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%lld,%d,%d,%lld,%lld,%lld]", k->gate, (long long)sh->id, sh->before, sh->trigger, (long long)sh->call, (long long)sh->spawn, (long long)sh->times); if(sh->before > 0 && sh->before <= b->label.n) inc[sh->before] = 1; if(sh->trigger > 0 && sh->trigger <= b->label.n) inc[sh->trigger] = 1; } } free(hs.e); }
  sb_str(o, "],\"receipts\":["); first = 1; i64 rid = 0;
  for(int i = nr - 1; i >= 0; i--){ Run *r = run_of(b, runs[i]); if(!r || !r->nrc) continue; for(int j = 0; j < r->nrc; j++){ Rc *k = &r->rcs[j]; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%lld,%d,%lld]", (long long)++rid, (long long)runs[i], k->gate, (long long)k->shard); } }
  /* the definition-row and memory counts of the included points only (the page colours and lists by them), once the included set is final */
  sb_str(o, "],\"nodes\":{"); first = 1;
  for(int g = 1; g <= b->label.n; g++){ if(!inc[g]) continue; Neuron *n = neuron_of(b, g); if(!n || !n->nnode) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":%d", g, n->nnode); }
  /* the places the brain holds for the included points, and the formulas (the kinds' pulls) it holds: the page starts from them */
  sb_str(o, "},\"xyz\":["); first = 1;
  for(int g = 1; g <= b->label.n; g++){ if(!inc[g]) continue; double x, y, z; i64 sh, at, run; int bf, nx, mv; if(!nk_xyz_get(g, &x, &y, &z, &sh, &bf, &nx, &at, &run, &mv)) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%.2f,%.2f,%.2f,%d]", g, x, y, z, mv); }
  sb_str(o, "],\"formula\":["); first = 1;
  { sqlite3_stmt *fq = 0; if(sqlite3_prepare_v2(DB, "SELECT p.kind, f.pull, f.rest, f.dx, f.dy, f.dz, f.mode FROM main.pull p JOIN main.formula f ON f.id = p.formula", -1, &fq, 0) == SQLITE_OK){ while(sqlite3_step(fq) == SQLITE_ROW){ if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%g,%g,%g,%g,%g,%d]", sqlite3_column_int(fq, 0), sqlite3_column_double(fq, 1), sqlite3_column_double(fq, 2), sqlite3_column_double(fq, 3), sqlite3_column_double(fq, 4), sqlite3_column_double(fq, 5), sqlite3_column_int(fq, 6)); } } if(fq) sqlite3_finalize(fq); }
  sb_str(o, "],\"mem\":{"); first = 1;
  for(int g = 1; g <= b->label.n; g++){ if(!inc[g]) continue; Neuron *n = neuron_of(b, g); if(!n || !n->nmem) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":%d", g, n->nmem); }
  sb_str(o, "},\"label\":["); first = 1; i64 nlab = 0;
  for(int g = 1; g <= b->label.n; g++){ if(!inc[g]) continue; if(!first) sb_str(o, ","); first = 0; nlab++; sb_fmt(o, "[%d,", g); sb_json(o, b->label.sym[g]); sb_str(o, "]"); }
  sb_fmt(o, "],\"counts\":{\"label\":%d,\"born\":%d,\"shards\":%lld,\"runs\":%lld,\"receipts\":%lld,\"rel\":%lld,\"dna_sent\":%lld,\"label_sent\":%lld,\"runs_sent\":%d,\"defined\":%lld}}", b->label.n, b->label.n, (long long)nk_shard_rows(b), (long long)b->nruns, (long long)b->hops_done, (long long)nrel, (long long)ndna, (long long)nlab, nr, (long long)b->dropped_runs);
  free(inc); free(runs); free(seen.e);
}
static void handle(const char *req, SB *o){
  if(strncmp(req, "bundle ", 7) == 0){ do_bundle(&MAINB, atoi(req + 7) > 0 ? atoi(req + 7) : 400, o); return; }
  if(strcmp(req, "repair") == 0){ do_repair(&MAINB, o); return; }
  if(strncmp(req, "rels", 4) == 0){ int n = atoi(req + 4); do_rels(&MAINB, n > 0 ? n : 20000, o); return; }
  if(strcmp(req, "hop") == 0){ sb_str(o, "["); do_hop(&MAINB, o); sb_str(o, ","); do_hop(&SIXTHB, o); sb_str(o, "]"); return; }
  if(strncmp(req, "restep ", 7) == 0){ /* restep CLOCK GATE,GATE,...: the places as they stood at that clock, the beginning input replayed forward over the timeline; restep base writes the beginning input again */ char t[65536]; i64 clk = strncmp(req + 7, "base", 4) == 0 ? -1 : atoll(req + 7); const char *p = strchr(req + 7, ' '); int gates[512], ng = 0; while(p && *p && ng < 512){ while(*p == ' ' || *p == ',') p++; if(!*p) break; gates[ng++] = atoi(p); while(*p && *p != ',' && *p != ' ') p++; } nk_xyz_restep(&MAINB, clk, gates, ng, t, sizeof t); sb_str(o, t); return; }
  if(strncmp(req, "moved ", 6) == 0){ char t[1 << 20]; nk_xyz_moved(&MAINB, atoll(req + 6), 20000, t, sizeof t); sb_str(o, t); return; }   /* the points moved since a clock, with their places now */
  if(strncmp(req, "settle", 6) == 0){ char t[512]; nk_xyz_settle(&MAINB, atoi(req + 6) > 0 ? atoi(req + 6) : 1, t, sizeof t); sb_str(o, t); return; }   /* the places back-populated: one step of every point that holds a definition or a place, per pass */
  if(strcmp(req, "relabel") == 0){ do_relabel(&MAINB, o); return; }   /* C27 back population */
  if(strcmp(req, "memory") == 0){ sb_str(o, "["); do_memory(&MAINB, o); sb_str(o, ","); do_memory(&SIXTHB, o); sb_str(o, "]"); return; }
  if(strncmp(req, "profile", 7) == 0){ do_profile(o, atoi(req + 7) > 0 ? atoi(req + 7) : 15); return; }
  if(strcmp(req, "scans") == 0){ char t[4096]; nkvt_scans(t, sizeof t); sb_str(o, "["); sb_str(o, t); sb_str(o, "]"); return; }
  if(strncmp(req, "type main ", 10) == 0) do_type(&MAINB, req + 10, o);
  else if(strncmp(req, "type sixth ", 11) == 0) do_type(&SIXTHB, req + 11, o);
  else if(strncmp(req, "q ", 2) == 0) do_q(req + 2, o);
  else if(strncmp(req, "run main ", 9) == 0) do_run(&MAINB, atoll(req + 9), o);
  else if(strncmp(req, "run sixth ", 10) == 0) do_run(&SIXTHB, atoll(req + 10), o);
  else if(strncmp(req, "newest main", 11) == 0) do_newest(&MAINB, atoi(req + 11) > 0 ? atoi(req + 11) : 30, o);
  else if(strncmp(req, "newest sixth", 12) == 0) do_newest(&SIXTHB, atoi(req + 12) > 0 ? atoi(req + 12) : 30, o);
  else if(strcmp(req, "stats") == 0) do_stats(o);
  else if(strncmp(req, "pump ", 5) == 0){ int n = atoi(req + 5); for(int i = 0; i < n; i++) pump_all(64); do_stats(o); }
  else sb_str(o, "{\"error\":\"unknown request\"}");
}

static volatile sig_atomic_t STOP; static void on_stop(int n){ STOP = 1; }
int main(int argc, char **argv){
  int attached = 0; { const char *mp = getenv("NK_MAP"); if(mp && *mp){ attached = nk_map_open(mp, 400ULL << 30, ((uint64_t)sizeof(Run) << 40) ^ ((uint64_t)sizeof(Brain) << 20) ^ sizeof(Cell)); if(attached < 0) return 1; } }
  signal(SIGTERM, on_stop);
  if(argc < 4){ fprintf(stderr, "usage: nk <port> <symbols file> <sources dir> [source names...]\n"); return 1; }
  int port = atoi(argv[1]);
  { const char *mp = getenv("NK_MAP"); if(mp && *mp){ char px[4096]; snprintf(px, sizeof px, "%s.xyz", mp); if(nk_xyz_open(px) < 0) return 1; } }   /* the places, beside the map */
  if(attached){ Brain **root = nk_map_root(); MAINP = root[0]; SIXTHP = root[1]; }
  else { Brain **root = malloc(sizeof(Brain *) * 2); MAINP = root[0] = calloc(1, sizeof(Brain)); SIXTHP = root[1] = calloc(1, sizeof(Brain)); nk_map_set_root(root); brain_init(&MAINB, "main", 1); brain_init(&SIXTHB, "sixth", 0); }
  MAINB.name = "main"; SIXTHB.name = "sixth"; MAINB.tell = &SIXTHB;
  if(!attached){ lay_egg(&MAINB, argv[2]); lay_egg(&SIXTHB, argv[2]); }
  const char *defaults[] = {"wn", "gcide", "mw", "mwt", "moby", "map", "sqldoc", "measured", "guess"};
  const char **srcs = argc > 4 ? (const char**)argv + 4 : defaults; int nsrc = argc > 4 ? argc - 4 : 9; SRCDIR = argv[3]; SRCS = srcs; NSRCS = nsrc;
  if(mother_open(&MAINB, &SIXTHB, srcs, nsrc, argv[3]) != 0){ fprintf(stderr, "mother could not open\n"); return 1; }
  nk_count_rows(&MAINB); nk_count_rows(&SIXTHB);
  { const char *mp = getenv("NK_MAP"); if(mp && *mp){ char px[4096]; snprintf(px, sizeof px, "%s.xyz", mp); nk_xyz_base(&MAINB, px); } }   /* the beginning input of the history of places, written at the first start after the recording began */
  nk_map_ready();
  int s = socket(AF_INET, SOCK_STREAM, 0); int one = 1; setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
  struct sockaddr_in a = {0}; a.sin_family = AF_INET; a.sin_port = htons(port); a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  if(bind(s, (struct sockaddr*)&a, sizeof a) < 0 || listen(s, 8) < 0){ perror("listen"); return 1; }
  fprintf(stderr, "nk: %d symbols laid in each brain, listening on 127.0.0.1:%d\n", MAINB.label.n, port);
  for(;;){
    if(STOP){ nk_xyz_sync(); nk_map_sync(); sqlite3_close(DB); fprintf(stderr, "nk: stopped; the brain is in its file\n"); return 0; }
    int busy = pending(&MAINB) || pending(&SIXTHB);
    struct pollfd p = {s, POLLIN, 0}; int timeout = busy ? 0 : -1;
    int r = poll(&p, 1, timeout);
    if(r <= 0){ if(busy) pump_all(256); continue; }
    int c = accept(s, 0, 0); if(c < 0) continue;
    SB req = {0}; char buf[65536]; ssize_t n;
    while((n = read(c, buf, sizeof buf)) > 0){ sb_put(&req, buf, n); if(memchr(buf, '\n', n)) break; }
    if(req.s){ char *nl = strchr(req.s, '\n'); if(nl) *nl = 0; SB o = {0}; handle(req.s, &o); sb_str(&o, "\n"); size_t off = 0; while(off < o.n){ ssize_t w = write(c, o.s + off, o.n - off); if(w <= 0) break; off += w; } free(o.s); }
    free(req.s); close(c);
  }
}
