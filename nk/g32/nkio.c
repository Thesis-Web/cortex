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
#include <stdarg.h>

static sqlite3 *DB; static Brain MAINB, SIXTHB;
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
static char *run_text(const char *sql, int argc, sqlite3_value **argv){
  char *err = 0; SB got = {0};
  if(argc == 0 && strchr(sql, ';')){ if(sqlite3_exec(DB, sql, rows_cb, &got, &err) != SQLITE_OK){ char *m = sqlite3_mprintf("error: %s", err); sqlite3_free(err); free(got.s); char *r = strdup(m); sqlite3_free(m); return r; } char *r = strdup(got.n ? got.s : "ok"); free(got.s); return r; }
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
static void motherFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){ const char *sql = (const char*)sqlite3_value_text(argv[0]); if(!sql){ sqlite3_result_text(ctx, "error: nothing to run", -1, SQLITE_STATIC); return; } i64 t0 = now_ns(); char *r = run_text(sql, argc - 1, argv + 1); prof_add(sql, now_ns() - t0); sqlite3_result_text(ctx, r, -1, SQLITE_TRANSIENT); free(r); }
int mother_open(Brain *main, Brain *sixth, const char **sources, int nsources, const char *srcdir){
  if(sqlite3_open(":memory:", &DB) != SQLITE_OK) return -1;
  sqlite3_exec(DB, "PRAGMA recursive_triggers = ON", 0, 0, 0);
  sqlite3_exec(DB, "ATTACH ':memory:' AS sixth", 0, 0, 0);
  for(int i = 0; i < nsources; i++){ char *q = sqlite3_mprintf("ATTACH '%q/%q.db' AS %w", srcdir, sources[i], sources[i]); char *e = 0; if(sqlite3_exec(DB, q, 0, 0, &e) != SQLITE_OK){ fprintf(stderr, "attach %s: %s\n", sources[i], e); sqlite3_free(e); } sqlite3_free(q); }
  sqlite3_create_function_v2(DB, "mother", -1, SQLITE_UTF8, 0, motherFunc, 0, 0, 0);
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
    int is_ptr = (w->cell == REPLY || w->cell == DEF || w->cell == SAY || w->cell == REMEMBER);
    if(is_ptr && w->value && atoll(w->value) > 0){ i64 rr = atoll(w->value); Run *x = run_of(b, rr); sb_fmt(&v, "run %lld from %s: ", (long long)rr, (x && x->arrival <= b->label.n) ? b->label.sym[x->arrival] : "?"); decode_run(b, rr, &v, 160); }
    else if((strcmp(cname, "known") == 0 || strcmp(cname, "unknown") == 0) && w->value){ const char *p = w->value; int any = 0; while(*p){ while(*p == ' ') p++; if(!*p) break; int g = atoi(p); while(*p && *p != ' ') p++; if(any) sb_str(&v, " "); any = 1; sb_str(&v, (g > 0 && g <= b->label.n) ? b->label.sym[g] : "?"); } if(!any) sb_str(&v, "(none)"); }
    else sb_str(&v, w->value ? w->value : "");
    sb_str(o, "["); sb_json(o, b->name); sb_fmt(o, ",%lld,", (long long)w->run); sb_json(o, cname); sb_str(o, ","); sb_json(o, v.s ? v.s : ""); sb_str(o, "]"); free(v.s);
  }
}

/* ---- the loop over both brains' stacks: a batch of each in turn ---- */
static void pump_all(int batch){ pump_batch(&MAINB, batch); pump_batch(&SIXTHB, batch); }
static double now_s(void){ struct timeval tv; gettimeofday(&tv, 0); return tv.tv_sec + tv.tv_usec / 1e6; }

static FILE *JOURNAL;
int sheet_open_pub(Brain *b, i64 run);
static void do_type(Brain *b, const char *text, SB *o){
  if(JOURNAL){ fprintf(JOURNAL, "%s%s\n", b->is_main ? "" : "6> ", text); fflush(JOURNAL); }
  i64 runs0 = b->nruns, hops0 = MAINB.hops_done + SIXTHB.hops_done, gates0 = MAINB.label.n, ref0 = MAINB.refused_n + SIXTHB.refused_n, outm = MAINB.nout, outs = SIXTHB.nout;
  double t0 = now_s();
  line_in(b, 0, text);
  i64 rid = runs0 + 1;
  /* until the typed line's own run has ended and its sheet is whole, or nothing is left to run; what the line left (the sixth's sends) runs on between requests */
  for(;;){ Run *r = run_of(b, rid); if((r && r->ended && !sheet_open_pub(b, rid)) || (pending(&MAINB) == 0 && pending(&SIXTHB) == 0)) break; pump_all(64); }
  if(getenv("NK_WAIT_EMPTY")) while(pending(&MAINB) || pending(&SIXTHB)) pump_all(64);
  i64 hits = 0; for(i64 i = rid; i <= b->nruns; i++){ Run *r = run_of(b, i); if(r && (r->root == rid || i == rid)) hits += r->nhops; }
  nk_compact(&MAINB); nk_compact(&SIXTHB);
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
static void do_graph(Brain *b, SB *o){
  sb_str(o, "{\"dna\":["); int first = 1; int tables = 0;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->born) continue; tables++; for(int i = 0; i < n->nsh; i++){ Shard *s = &n->sh[i]; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%lld,", g, (long long)s->id); if(s->before) sb_fmt(o, "%d,", s->before); else sb_str(o, "null,"); if(s->trigger) sb_fmt(o, "%d,", s->trigger); else sb_str(o, "null,"); if(s->call) sb_fmt(o, "%lld,", (long long)s->call); else sb_str(o, "null,"); if(s->spawn) sb_fmt(o, "%lld,", (long long)s->spawn); else sb_str(o, "null,"); sb_fmt(o, "%lld]", (long long)s->times); } }
  sb_str(o, "],\"nodes\":{"); first = 1; for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->born) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":%d", g, n->nnode); }
  sb_str(o, "},\"mem\":{"); first = 1; for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->nmem) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":%d", g, n->nmem); }
  sb_str(o, "},\"first\":{"); first = 1; for(i64 i = 1; i <= b->nruns; i++){ Run *r = run_of(b, i); if(!r || !r->nseq || !r->seq) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%lld\":%d", (long long)i, r->seq[0]); }
  sb_fmt(o, "},\"tables\":%d,\"rel\":[", tables);
  char q[64]; snprintf(q, sizeof q, "SELECT gate, kind, other, run FROM %s.rel", b->name); sqlite3_stmt *st = 0; first = 1;
  if(sqlite3_prepare_v2(DB, q, -1, &st, 0) == SQLITE_OK){ while(sqlite3_step(st) == SQLITE_ROW){ if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%lld,%lld,%lld]", (long long)sqlite3_column_int64(st, 0), (long long)sqlite3_column_int64(st, 1), (long long)sqlite3_column_int64(st, 2), (long long)sqlite3_column_int64(st, 3)); } sqlite3_finalize(st); }
  sb_str(o, "]}");
}
static const char *EXPORT_TABLES[] = {"label", "neuron", "dna", "node", "run", "seq", "run_sheet", "run_receipt", "run_memory", "timeline", "input", "third", "secondary", "out_user", "refused", "hit", "clock", "shards", "complete", "hop"};
static const char *SRCDIR = "sources"; static const char **SRCS; static int NSRCS;
static void copy_table(sqlite3 *dst, const char *schema, const char *name, const char *ddl_cols){
  /* read the rows through mother's connection (the regions), write them as plain rows into the export */
  char *q = sqlite3_mprintf("SELECT * FROM %w.%w", schema, name); sqlite3_stmt *st = 0;
  if(sqlite3_prepare_v2(DB, q, -1, &st, 0) != SQLITE_OK){ sqlite3_free(q); return; } sqlite3_free(q);
  int n = sqlite3_column_count(st);
  SB ddl = {0}; sb_fmt(&ddl, "CREATE TABLE \"%s\" (", name); for(int i = 0; i < n; i++){ if(i) sb_str(&ddl, ", "); sb_fmt(&ddl, "\"%s\"", sqlite3_column_name(st, i)); } sb_str(&ddl, ")");
  sqlite3_exec(dst, ddl.s, 0, 0, 0); free(ddl.s);
  SB ins = {0}; sb_fmt(&ins, "INSERT INTO \"%s\" VALUES (", name); for(int i = 0; i < n; i++){ sb_str(&ins, i ? ",?" : "?"); } sb_str(&ins, ")");
  sqlite3_stmt *w = 0; sqlite3_prepare_v2(dst, ins.s, -1, &w, 0); free(ins.s);
  while(sqlite3_step(st) == SQLITE_ROW){ for(int i = 0; i < n; i++) sqlite3_bind_value(w, i + 1, sqlite3_column_value(st, i)); sqlite3_step(w); sqlite3_reset(w); sqlite3_clear_bindings(w); }
  sqlite3_finalize(w); sqlite3_finalize(st);
}
static void do_export(const char *dir, SB *o){
  const char *names[2] = {"main", "sixth"}; const char *files[2] = {"brain.db", "sixth.db"};
  { char *mk = sqlite3_mprintf("mkdir -p '%q'", dir); if(system(mk) != 0){ sb_str(o, "{\"error\":\"mkdir\"}"); sqlite3_free(mk); return; } sqlite3_free(mk); }
  for(int bi = 0; bi < 2; bi++){
    char *path = sqlite3_mprintf("%s/%s", dir, files[bi]); unlink(path);
    sqlite3 *dst = 0; if(sqlite3_open(path, &dst) != SQLITE_OK){ sb_str(o, "{\"error\":\"export open\"}"); sqlite3_free(path); return; }
    sqlite3_exec(dst, "PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; BEGIN", 0, 0, 0);
    for(size_t i = 0; i < sizeof(EXPORT_TABLES) / sizeof(EXPORT_TABLES[0]); i++) copy_table(dst, names[bi], EXPORT_TABLES[i], 0);
    /* the tables the brain laid itself in this schema (rel, asked, spawned ...): plain tables, copied as they are */
    char *q = sqlite3_mprintf("SELECT name, sql FROM %w.sqlite_master WHERE type = 'table' AND sql NOT LIKE 'CREATE VIRTUAL%%' AND name NOT LIKE 'sqlite_%%'", names[bi]); sqlite3_stmt *st = 0;
    sqlite3_exec(dst, "CREATE TABLE \"__ddl\" (name TEXT, sql TEXT)", 0, 0, 0); sqlite3_stmt *w = 0; sqlite3_prepare_v2(dst, "INSERT INTO \"__ddl\" VALUES (?, ?)", -1, &w, 0);
    if(sqlite3_prepare_v2(DB, q, -1, &st, 0) == SQLITE_OK){ while(sqlite3_step(st) == SQLITE_ROW){ copy_table(dst, names[bi], (const char*)sqlite3_column_text(st, 0), 0); sqlite3_bind_text(w, 1, (const char*)sqlite3_column_text(st, 0), -1, SQLITE_TRANSIENT); sqlite3_bind_text(w, 2, (const char*)sqlite3_column_text(st, 1), -1, SQLITE_TRANSIENT); sqlite3_step(w); sqlite3_reset(w); } sqlite3_finalize(st); } sqlite3_free(q); sqlite3_finalize(w);
    sqlite3_exec(dst, "COMMIT", 0, 0, 0); sqlite3_close(dst); sqlite3_free(path);
  }
  sb_str(o, "{\"exported\":true}");
}
static void brain_stats(Brain *b, SB *o){
  double hop_us = b->hops_run ? (b->hop_ns - b->paste_ns) / 1000.0 / b->hops_run : 0, paste_us = b->pastes ? b->paste_ns / 1000.0 / b->pastes : 0;
  sb_fmt(o, "{\"runs\":%lld,\"hops\":%lld,\"pending\":%d,\"gates\":%d,\"refused\":%lld,\"shards\":%lld,\"hop_us\":%.3f,\"pastes\":%lld,\"paste_us\":%.1f,\"hop_s\":%.3f,\"paste_s\":%.3f,\"returns\":%lld,\"return_us\":%.1f,\"return_s\":%.3f,\"receipts\":%lld,\"hops_run\":%lld,\"deduped_runs\":%lld,\"stubs\":%lld,\"receipts_dropped\":%lld}", (long long)b->nruns, (long long)b->hops_done, pending(b), b->label.n, (long long)b->refused_n, (long long)b->shards, hop_us, (long long)b->pastes, paste_us, (b->hop_ns - b->paste_ns) / 1e9, b->paste_ns / 1e9, (long long)b->secs, b->secs ? b->sec_ns / 1000.0 / b->secs : 0, b->sec_ns / 1e9, (long long)(b->hops_done - b->dropped_receipts), (long long)b->hops_run, (long long)b->deduped, (long long)b->dropped_runs, (long long)b->dropped_receipts);
}
/* the brain's own tables (rel, asked, spawned ...) back from an export, with their DDL, into mother's connection under the schema */
static void load_own_tables(const char *schema, const char *path){
  sqlite3 *src = 0; if(sqlite3_open_v2(path, &src, SQLITE_OPEN_READONLY, 0) != SQLITE_OK) return;
  sqlite3_stmt *st = 0; if(sqlite3_prepare_v2(src, "SELECT name, sql FROM \"__ddl\"", -1, &st, 0) != SQLITE_OK){ sqlite3_close(src); return; }
  while(sqlite3_step(st) == SQLITE_ROW){
    const char *name = (const char*)sqlite3_column_text(st, 0), *ddl = (const char*)sqlite3_column_text(st, 1); if(!name || !ddl) continue;
    const char *p = strstr(ddl, "TABLE "); if(!p) continue;
    char *q = sqlite3_mprintf("%.*s%w.%s", (int)(p + 6 - ddl), ddl, schema, p + 6); char *e = 0;
    if(sqlite3_exec(DB, q, 0, 0, &e) != SQLITE_OK){ fprintf(stderr, "load %s.%s: %s\n", schema, name, e); sqlite3_free(e); sqlite3_free(q); continue; } sqlite3_free(q);
    q = sqlite3_mprintf("SELECT * FROM \"%w\"", name); sqlite3_stmt *r = 0; if(sqlite3_prepare_v2(src, q, -1, &r, 0) != SQLITE_OK){ sqlite3_free(q); continue; } sqlite3_free(q);
    int n = sqlite3_column_count(r); SB ins = {0}; sb_fmt(&ins, "INSERT INTO %s.\"%s\" VALUES (", schema, name); for(int i = 0; i < n; i++) sb_str(&ins, i ? ",?" : "?"); sb_str(&ins, ")");
    sqlite3_stmt *w = 0; sqlite3_prepare_v2(DB, ins.s, -1, &w, 0); free(ins.s); i64 rows = 0;
    while(sqlite3_step(r) == SQLITE_ROW){ for(int i = 0; i < n; i++) sqlite3_bind_value(w, i + 1, sqlite3_column_value(r, i)); sqlite3_step(w); sqlite3_reset(w); sqlite3_clear_bindings(w); rows++; }
    sqlite3_finalize(w); sqlite3_finalize(r); fprintf(stderr, "load %s.%s: %lld rows\n", schema, name, (long long)rows);
  }
  sqlite3_finalize(st); sqlite3_close(src);
}
/* a snapshot: the export, the small source files beside it (the guesser's state), and how many journal lines were typed by then */
static int copy_file(const char *from, const char *to){ FILE *a = fopen(from, "rb"); if(!a) return -1; FILE *z = fopen(to, "wb"); if(!z){ fclose(a); return -1; } char buf[1 << 16]; size_t n; while((n = fread(buf, 1, sizeof buf, a)) > 0) fwrite(buf, 1, n, z); fclose(a); fclose(z); return 0; }
static void do_snapshot(const char *dir, SB *o){
  char *mk = sqlite3_mprintf("mkdir -p '%q'", dir); if(system(mk) != 0){ sb_str(o, "{\"error\":\"mkdir\"}"); sqlite3_free(mk); return; } sqlite3_free(mk);
  SB x = {0}; do_export(dir, &x); free(x.s);
  int copied = 0;
  for(int i = 0; i < NSRCS; i++){ char *from = sqlite3_mprintf("%s/%s.db", SRCDIR, SRCS[i]); FILE *f = fopen(from, "rb"); long sz = 0; if(f){ fseek(f, 0, SEEK_END); sz = ftell(f); fclose(f); } if(f && sz <= (16 << 20)){ char *to = sqlite3_mprintf("%s/%s.db", dir, SRCS[i]); if(copy_file(from, to) == 0) copied++; sqlite3_free(to); } sqlite3_free(from); }
  long typed = 0; if(getenv("NK_JOURNAL")){ FILE *j = fopen(getenv("NK_JOURNAL"), "r"); if(j){ int ch; while((ch = fgetc(j)) != EOF) if(ch == '\n') typed++; fclose(j); } }
  char *tp = sqlite3_mprintf("%s/typed-lines.txt", dir); FILE *t = fopen(tp, "w"); if(t){ fprintf(t, "%ld\n", typed); fclose(t); } sqlite3_free(tp);
  sb_fmt(o, "{\"snapshot\":\"%s\",\"typed_lines\":%ld,\"source_files\":%d,\"main_runs\":%lld,\"sixth_runs\":%lld}", dir, typed, copied, (long long)MAINB.nruns, (long long)SIXTHB.nruns);
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
  for(int i = 0; i < root->ncells; i++){ Cell *c = &root->cells[i]; if(i) sb_str(o, ","); sb_fmt(o, "[%d,%d,", c->cell, c->state); if(c->value) sb_json(o, c->value); else sb_str(o, "null"); sb_str(o, ",");
    /* the cells that name a run: me, above, reply, def, say, remember, shape (the call); what names a gate or a number and is left as it is */
    int runcell = (c->cell == ME || c->cell == ABOVE || c->cell == REPLY || c->cell == DEF || c->cell == SAY || c->cell == REMEMBER || c->cell == SHAPE);
    i64 rv = (c->value && runcell) ? atoll(c->value) : 0; Run *x = rv > 0 ? run_of(b, rv) : 0;
    if(x && strspn(c->value, "0123456789") == strlen(c->value)){ sb_fmt(o, "{\"run\":%lld,\"arrival\":%d,\"text\":", (long long)rv, x->arrival); sb_text_of(b, rv, o, 300); sb_str(o, "}"); }
    else if(c->value && (c->cell == label_gate(b, "known") || c->cell == label_gate(b, "unknown"))){ /* a list of gates: read back as symbols, the first sixty */ SB t = {0}; const char *q = c->value; int nw = 0, total = 0; while(*q){ while(*q == ' ') q++; if(!*q) break; int g = atoi(q); while(*q && *q != ' ') q++; total++; if(nw < 60 && g > 0 && g <= b->label.n){ if(nw) sb_str(&t, " "); sb_str(&t, b->label.sym[g]); nw++; } } if(total > nw) sb_fmt(&t, " … %d in all", total); sb_fmt(o, "{\"words\":%d,\"text\":", total); sb_json(o, t.s ? t.s : ""); sb_str(o, "}"); free(t.s); }
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
  for(i64 i = 1; i <= b->nruns; i++){ Run *r = &b->runs[i]; rcs_b += (i64)r->crc * sizeof(Rc); if(r->nrc) nkept++; if(r->seq && !r->seq_shared){ seq_b += ((r->nseq + 63) / 64) * 64 * sizeof(int); nseqheld++; } for(int c = 0; c < r->ncells; c++){ cells_b += sizeof(Cell) + (r->cells[c].value ? strlen(r->cells[c].value) + 1 + 16 : 0); ncells++; } cells_b += (i64)(r->ccells - r->ncells) * sizeof(Cell); kids_b += (i64)r->ckids * 8; if(r->mem_input) mem_b += strlen(r->mem_input) + 1 + 16; }
  i64 sh_b = 0, nsh = 0, nmaps_b = 0, lists_b = 0, node_b = 0;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; sh_b += (i64)n->csh * sizeof(Shard); nsh += n->nsh; nmaps_b += (i64)n->h.cap * sizeof(HEnt); lists_b += (i64)(n->cabout + n->cmem + n->chits + n->carrived) * 8; node_b += (i64)n->cnode * sizeof(NodeRow); }
  i64 label_b = (i64)b->label.cap * 8 + (i64)b->label.h.cap * sizeof(HEnt); for(int g = 1; g <= b->label.n; g++) label_b += strlen(b->label.sym[g]) + 1 + 16;
  i64 maps_b = (i64)(b->memh.cap + b->memt.cap + b->shid.cap + b->hith.cap + b->relh.cap) * sizeof(HEnt);
  i64 mail_b = (i64)b->cinput * sizeof(Mail) + (i64)b->cthird * sizeof(Mail) + (i64)b->csec * sizeof(Sec) + (i64)b->cout * sizeof(Out) + (i64)b->ctl * sizeof(Tl) + (i64)b->chit * sizeof(Hit) + (i64)b->chop * sizeof(Hop) + (i64)b->cnr * sizeof(Neuron);
  struct mallinfo2 mi = mallinfo2();
  sb_fmt(o, "{\"brain\":\"%s\",\"runs\":%lld,\"run_structs_MB\":%.1f,\"receipts_kept\":%lld,\"receipts_MB\":%.1f,\"runs_with_receipts\":%lld,\"seq_held_runs\":%lld,\"seq_MB\":%.1f,\"cells\":%lld,\"cells_MB\":%.1f,\"kids_MB\":%.1f,\"memory_text_MB\":%.1f,\"shards\":%lld,\"shards_MB\":%.1f,\"shard_maps_MB\":%.1f,\"neuron_lists_MB\":%.1f,\"nodes_MB\":%.1f,\"labels_MB\":%.1f,\"brain_maps_MB\":%.1f,\"mail_and_misc_MB\":%.1f,\"heap_in_use_MB\":%.1f,\"heap_free_MB\":%.1f,\"sqlite_MB\":%.1f}",
    b->name, (long long)b->nruns, runs_b / MB, (long long)(b->hops_done - b->dropped_receipts), rcs_b / MB, (long long)nkept, (long long)nseqheld, seq_b / MB, (long long)ncells, cells_b / MB, kids_b / MB, mem_b / MB, (long long)nsh, sh_b / MB, nmaps_b / MB, lists_b / MB, node_b / MB, label_b / MB, maps_b / MB, mail_b / MB, mi.uordblks / MB, mi.fordblks / MB, sqlite3_memory_used() / MB);
}
static void handle(const char *req, SB *o){
  if(strcmp(req, "memory") == 0){ sb_str(o, "["); do_memory(&MAINB, o); sb_str(o, ","); do_memory(&SIXTHB, o); sb_str(o, "]"); return; }
  if(strncmp(req, "profile", 7) == 0){ do_profile(o, atoi(req + 7) > 0 ? atoi(req + 7) : 15); return; }
  if(strcmp(req, "scans") == 0){ char t[4096]; nkvt_scans(t, sizeof t); sb_str(o, "["); sb_str(o, t); sb_str(o, "]"); return; }
  if(strncmp(req, "type main ", 10) == 0) do_type(&MAINB, req + 10, o);
  else if(strncmp(req, "type sixth ", 11) == 0) do_type(&SIXTHB, req + 11, o);
  else if(strncmp(req, "q ", 2) == 0) do_q(req + 2, o);
  else if(strncmp(req, "graph main", 10) == 0) do_graph(&MAINB, o);
  else if(strncmp(req, "graph sixth", 11) == 0) do_graph(&SIXTHB, o);
  else if(strncmp(req, "export ", 7) == 0) do_export(req + 7, o);
  else if(strncmp(req, "run main ", 9) == 0) do_run(&MAINB, atoll(req + 9), o);
  else if(strncmp(req, "run sixth ", 10) == 0) do_run(&SIXTHB, atoll(req + 10), o);
  else if(strncmp(req, "newest main", 11) == 0) do_newest(&MAINB, atoi(req + 11) > 0 ? atoi(req + 11) : 30, o);
  else if(strncmp(req, "newest sixth", 12) == 0) do_newest(&SIXTHB, atoi(req + 12) > 0 ? atoi(req + 12) : 30, o);
  else if(strncmp(req, "snapshot ", 9) == 0) do_snapshot(req + 9, o);
  else if(strcmp(req, "stats") == 0) do_stats(o);
  else if(strncmp(req, "pump ", 5) == 0){ int n = atoi(req + 5); for(int i = 0; i < n; i++) pump_all(64); do_stats(o); }
  else sb_str(o, "{\"error\":\"unknown request\"}");
}

int main(int argc, char **argv){
  if(getenv("NK_MAP") && *getenv("NK_MAP")){ if(nk_map_open(getenv("NK_MAP"), 220ULL << 30) != 0) return 1; }
  if(argc < 4){ fprintf(stderr, "usage: nk <port> <symbols file> <sources dir> [source names...]\n"); return 1; }
  int port = atoi(argv[1]);
  if(getenv("NK_JOURNAL")){ JOURNAL = fopen(getenv("NK_JOURNAL"), "a"); if(!JOURNAL) perror(getenv("NK_JOURNAL")); }
  brain_init(&MAINB, "main", 1); brain_init(&SIXTHB, "sixth", 0); MAINB.tell = &SIXTHB;
  const char *load = getenv("NK_LOAD"); char *lp_main = 0, *lp_sixth = 0;
  if(load){ lp_main = sqlite3_mprintf("%s/brain.db", load); lp_sixth = sqlite3_mprintf("%s/sixth.db", load); if(nk_load(&MAINB, lp_main) != 0 || nk_load(&SIXTHB, lp_sixth) != 0){ fprintf(stderr, "the snapshot did not load whole; stopping rather than running a brain with holes\n"); return 1; } }
  else { lay_egg(&MAINB, argv[2]); lay_egg(&SIXTHB, argv[2]); }
  const char *defaults[] = {"wn", "gcide", "mw", "mwt", "moby", "map", "sqldoc", "measured", "guess"};
  const char **srcs = argc > 4 ? (const char**)argv + 4 : defaults; int nsrc = argc > 4 ? argc - 4 : 9; SRCDIR = argv[3]; SRCS = srcs; NSRCS = nsrc;
  if(mother_open(&MAINB, &SIXTHB, srcs, nsrc, argv[3]) != 0){ fprintf(stderr, "mother could not open\n"); return 1; }
  if(load){ load_own_tables("main", lp_main); load_own_tables("sixth", lp_sixth); sqlite3_free(lp_main); sqlite3_free(lp_sixth); }
  int s = socket(AF_INET, SOCK_STREAM, 0); int one = 1; setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
  struct sockaddr_in a = {0}; a.sin_family = AF_INET; a.sin_port = htons(port); a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  if(bind(s, (struct sockaddr*)&a, sizeof a) < 0 || listen(s, 8) < 0){ perror("listen"); return 1; }
  fprintf(stderr, "nk: %d symbols laid in each brain, listening on 127.0.0.1:%d\n", MAINB.label.n, port);
  for(;;){
    int busy = pending(&MAINB) || pending(&SIXTHB);
    struct pollfd p = {s, POLLIN, 0}; int timeout = busy ? 0 : -1;
    int r = poll(&p, 1, timeout);
    if(r <= 0){ if(busy){ pump_all(256); nk_compact(&MAINB); nk_compact(&SIXTHB); } continue; }
    int c = accept(s, 0, 0); if(c < 0) continue;
    SB req = {0}; char buf[65536]; ssize_t n;
    while((n = read(c, buf, sizeof buf)) > 0){ sb_put(&req, buf, n); if(memchr(buf, '\n', n)) break; }
    if(req.s){ char *nl = strchr(req.s, '\n'); if(nl) *nl = 0; SB o = {0}; handle(req.s, &o); sb_str(&o, "\n"); size_t off = 0; while(off < o.n){ ssize_t w = write(c, o.s + off, o.n - off); if(w <= 0) break; off += w; } free(o.s); }
    free(req.s); close(c);
  }
}
