/* mother(text, ...): the brain hands mother SQL text and, if it likes, the values to bind to its ? holes. She runs it at the SQL
   prompt and answers what SQLite answered: 'ok', the rows a SELECT sent back (one row per line, columns parted by " | "), or
   'error: <SQLite's reason>'. She never stops the brain: a refusal is an answer like any other. She parses nothing, decides
   nothing and carries nothing on her own: when a source brain's outbox is populated, that outbox's own trigger calls her with
   the INSERT that puts the row into the brain's secondary input. (10-23 P2: "just a router and a traverser. That's it.")
   What she keeps is only a memory of texts she has already prepared, so the same text with other values is not parsed again:
   that is speed, not a decision. NEURON_TRACE=1 prints every text she runs to stderr.
   Build: gcc -shared -fPIC -O2 -o mother.so mother.c -I.     Load: .load ./mother   */
#include "sqlite3ext.h"
SQLITE_EXTENSION_INIT1
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

static int trace = -1;
static int draining = 0;

/* the hop neuron's table (hop: id, text, p1..p6) in each attached brain holds what the brain wrote to run next. After the
   outermost text she was handed is done, mother pastes those rows at the prompt one at a time, newest first (the order the
   brain wrote them: a step a hit pushed last runs first, so a birth or a call finishes before the landing after it), until no
   brain has a row left. She picks nothing: the newest row is the brain's own order. A row that SQLite refuses is kept in
   that brain's refused table, with the reason, so the brain can read it. Nothing here runs on a timer. */
static void pump(sqlite3 *db);
#define NBUCKET 8192
typedef struct Ent { char *text; sqlite3_stmt *st; int busy; struct Ent *next; } Ent;
static Ent *bucket[NBUCKET]; static int nent = 0;

static unsigned hash(const char *s){ unsigned h = 5381; while(*s) h = h * 33 + (unsigned char)*s++; return h % NBUCKET; }

static void clear(void){
  int i; for(i = 0; i < NBUCKET; i++){ Ent *e = bucket[i]; while(e){ Ent *n = e->next; sqlite3_finalize(e->st); sqlite3_free(e->text); sqlite3_free(e); e = n; } bucket[i] = 0; }
  nent = 0;
}

/* a text already prepared is reused unless it is still running (a hop runs inside the hop before it: the same text, nested);
   then a second copy is prepared and kept too, so each nesting depth has its own */
static Ent *get(sqlite3 *db, const char *sql, char **err){
  unsigned h = hash(sql); Ent *e;
  for(e = bucket[h]; e; e = e->next) if(!e->busy && strcmp(e->text, sql) == 0){ sqlite3_reset(e->st); sqlite3_clear_bindings(e->st); return e; }
  if(nent >= 4 * NBUCKET){ int any = 0; int i; for(i = 0; i < NBUCKET && !any; i++) for(e = bucket[i]; e; e = e->next) if(e->busy) any = 1; if(!any) clear(); }
  sqlite3_stmt *st = 0; const char *tail = 0;
  if(sqlite3_prepare_v3(db, sql, -1, SQLITE_PREPARE_PERSISTENT, &st, &tail) != SQLITE_OK){ *err = sqlite3_mprintf("%s", sqlite3_errmsg(db)); return 0; }
  if(!st){ *err = sqlite3_mprintf("nothing to run"); return 0; }
  if(tail && *tail){ /* several statements: not kept; run whole below */ sqlite3_finalize(st); return 0; }
  e = sqlite3_malloc(sizeof(Ent)); e->text = sqlite3_mprintf("%s", sql); e->st = st; e->busy = 0; e->next = bucket[h]; bucket[h] = e; nent++;
  return e;
}

static int rows(void *p, int argc, char **argv, char **col){
  char **acc = (char**)p; int i;
  char *line = sqlite3_mprintf("%s", argc ? (argv[0] ? argv[0] : "") : "");
  for(i = 1; i < argc; i++){ char *t = sqlite3_mprintf("%s | %s", line, argv[i] ? argv[i] : ""); sqlite3_free(line); line = t; }
  if(*acc){ char *t = sqlite3_mprintf("%s\n%s", *acc, line); sqlite3_free(*acc); sqlite3_free(line); *acc = t; } else *acc = line;
  return 0;
}

static void answer_(sqlite3_context *ctx, char *got, char *err);
static void answer(sqlite3_context *ctx, char *got, char *err){ sqlite3 *db = sqlite3_context_db_handle(ctx); answer_(ctx, got, err); pump(db); }
static void answer_(sqlite3_context *ctx, char *got, char *err){
  if(err){ char *msg = sqlite3_mprintf("error: %s", err); if(trace) fprintf(stderr, "  sql< %s\n", msg); sqlite3_free(err); sqlite3_free(got); sqlite3_result_text(ctx, msg, -1, sqlite3_free); return; }
  if(got){ if(trace) fprintf(stderr, "  sql< %.120s\n", got); sqlite3_result_text(ctx, got, -1, sqlite3_free); return; }
  if(trace) fprintf(stderr, "  sql< ok\n");
  sqlite3_result_text(ctx, "ok", -1, SQLITE_STATIC);
}

static int one_hop(sqlite3 *db, const char *schema){
  char *q = sqlite3_mprintf("SELECT id, text, p1, p2, p3, p4, p5, p6 FROM \"%w\".hop ORDER BY id DESC LIMIT 1", schema);
  sqlite3_stmt *sel = 0; int rc = sqlite3_prepare_v2(db, q, -1, &sel, 0); sqlite3_free(q);
  if(rc != SQLITE_OK){ sqlite3_finalize(sel); return -1; }   /* no hop table: not a brain */
  if(sqlite3_step(sel) != SQLITE_ROW){ sqlite3_finalize(sel); return 0; }
  sqlite3_int64 id = sqlite3_column_int64(sel, 0);
  const char *text = (const char*)sqlite3_column_text(sel, 1);
  char *txt = sqlite3_mprintf("%s", text ? text : "");
  sqlite3_value *pv[6]; int i; for(i = 0; i < 6; i++) pv[i] = sqlite3_value_dup(sqlite3_column_value(sel, 2 + i));
  sqlite3_finalize(sel);
  q = sqlite3_mprintf("DELETE FROM \"%w\".hop WHERE id = %lld", schema, id); sqlite3_exec(db, q, 0, 0, 0); sqlite3_free(q);
  if(trace) fprintf(stderr, "  hop> %.200s\n", txt);
  char *err = 0; Ent *ent = get(db, txt, &err); sqlite3_stmt *st = ent ? ent->st : 0;
  if(st){
    for(i = 0; i < 6; i++) if(sqlite3_value_type(pv[i]) != SQLITE_NULL) sqlite3_bind_value(st, i + 1, pv[i]);
    ent->busy = 1; while((rc = sqlite3_step(st)) == SQLITE_ROW){} ent->busy = 0;
    if(rc != SQLITE_DONE) err = sqlite3_mprintf("%s", sqlite3_errmsg(db));
    sqlite3_reset(st);
  }else if(!err){ if(sqlite3_exec(db, txt, 0, 0, &err) != SQLITE_OK){} }
  if(err){
    if(trace) fprintf(stderr, "  hop< error: %s\n", err);
    q = sqlite3_mprintf("INSERT INTO \"%w\".refused (text, error) VALUES (%Q, %Q)", schema, txt, err); sqlite3_exec(db, q, 0, 0, 0); sqlite3_free(q); sqlite3_free(err);
  }
  for(i = 0; i < 6; i++) sqlite3_value_free(pv[i]);
  sqlite3_free(txt);
  return 1;
}

static void pump(sqlite3 *db){
  if(draining) return;
  draining = 1;
  for(;;){
    int any = 0;
    sqlite3_stmt *dbs = 0;
    if(sqlite3_prepare_v2(db, "SELECT name FROM pragma_database_list WHERE name <> 'temp'", -1, &dbs, 0) != SQLITE_OK) break;
    char *names[64]; int n = 0;
    while(sqlite3_step(dbs) == SQLITE_ROW && n < 64) names[n++] = sqlite3_mprintf("%s", sqlite3_column_text(dbs, 0));
    sqlite3_finalize(dbs);
    int i; for(i = 0; i < n; i++){ if(one_hop(db, names[i]) == 1){ any = 1; } }
    for(i = 0; i < n; i++) sqlite3_free(names[i]);
    if(!any) break;
  }
  draining = 0;
}

static void motherFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){
  const char *sql = (const char*)sqlite3_value_text(argv[0]);
  char *err = 0, *got = 0; int i, rc;
  sqlite3 *db = sqlite3_context_db_handle(ctx);
  if(trace < 0) trace = getenv("NEURON_TRACE") ? 1 : 0;
  if(!sql){ sqlite3_result_text(ctx, "error: nothing to run", -1, SQLITE_STATIC); return; }
  if(trace) fprintf(stderr, "  sql> %.300s\n", sql);
  if(argc == 1 && strchr(sql, ';')){   /* a text of several statements: the prompt runs them in order */
    if(sqlite3_exec(db, sql, rows, &got, &err) != SQLITE_OK){ sqlite3_free(got); got = 0; }
    answer(ctx, got, err); return;
  }
  Ent *ent = get(db, sql, &err); sqlite3_stmt *st = ent ? ent->st : 0;
  if(!st){
    if(err){ answer(ctx, 0, err); return; }
    if(sqlite3_exec(db, sql, rows, &got, &err) != SQLITE_OK){ sqlite3_free(got); got = 0; }
    answer(ctx, got, err); return;
  }
  for(i = 1; i < argc; i++) sqlite3_bind_value(st, i, argv[i]);
  ent->busy = 1;
  while((rc = sqlite3_step(st)) == SQLITE_ROW){
    int n = sqlite3_column_count(st), c; char *line = sqlite3_mprintf("%s", n ? (const char*)sqlite3_column_text(st, 0) : "");
    if(!line) line = sqlite3_mprintf("");
    for(c = 1; c < n; c++){ const char *v = (const char*)sqlite3_column_text(st, c); char *t = sqlite3_mprintf("%s | %s", line, v ? v : ""); sqlite3_free(line); line = t; }
    if(got){ char *t = sqlite3_mprintf("%s\n%s", got, line); sqlite3_free(got); sqlite3_free(line); got = t; } else got = line;
  }
  if(rc != SQLITE_DONE){ err = sqlite3_mprintf("%s", sqlite3_errmsg(db)); sqlite3_free(got); got = 0; }
  sqlite3_reset(st); ent->busy = 0;
  answer(ctx, got, err);
}

#ifdef _WIN32
__declspec(dllexport)
#endif
static void forget(void *p){ clear(); }
int sqlite3_mother_init(sqlite3 *db, char **e, const sqlite3_api_routines *pApi){
  SQLITE_EXTENSION_INIT2(pApi);
  return sqlite3_create_function_v2(db, "mother", -1, SQLITE_UTF8, (void*)1, motherFunc, 0, 0, forget);
}
