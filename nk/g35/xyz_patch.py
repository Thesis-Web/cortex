#!/usr/bin/env python3
# g35/xyz_patch.py (2026-11-02): the kernel learns the place of a point (nkxyz.c). Applied on hp in ~/nk; backups *.before-g35.
#  nk.h   : the nkxyz.c functions declared.
#  nk.c   : land() moves the point by its relationships when the shard used on it has another before or next than the last use.
#  nkvt.c : the table xyz (gate, x, y, z, shard, before, next, at, run, moved), read by gate; UPDATE x, y, z sets a place.
#  nkio.c : the side file opened beside the map; the settle request (the back population); the bundle carries xyz and formula rows.
#  serve8.py : /api/graph passes xyz and formula to the page.
#  run-on-hp.sh : nkxyz.c compiled in.
import sys, os
D = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/nk')
def patch(name, pairs):
    p = os.path.join(D, name); s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (name, s.count(old), old[:80])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s); print('patched', name, len(pairs))
patch('nk.h', [
    ("Shard *hop_shard(Brain *b); i64 hop_id(Brain *b); i64 nk_shard_rows(Brain *b); void nk_count_rows(Brain *b);\n",
     "Shard *hop_shard(Brain *b); i64 hop_id(Brain *b); i64 nk_shard_rows(Brain *b); void nk_count_rows(Brain *b);\n"
     "/* the place of a point and the pull of its relationships (nkxyz.c) */\n"
     "int nk_xyz_open(const char *path); void nk_xyz_land(Brain *b, int gate, i64 shard, int before, int next, i64 run); void nk_xyz_settle(Brain *b, int passes, char *out, size_t cap); int nk_xyz_get(int gate, double *x, double *y, double *z, i64 *shard, int *before, int *next, i64 *at, i64 *run, int *moved); int nk_xyz_set(Brain *b, int gate, double x, double y, double z); void nk_xyz_sync(void);\n"),
])
patch('nk.c', [
    ("  s->times++;\n  int had = 0; if(next){ Neuron *nn = neuron_of(b, next); had = (nn && nn->born) ? 1 : 0; }\n",
     "  s->times++;\n"
     "  if(!(pos == 0 || via == 1 || gate == SPACE)) nk_xyz_land(b, gate, s->id, kb, kx, run);   /* the place: a shard used on the point with another before or next than its last use moves it by its relationships (nkxyz.c) */\n"
     "  int had = 0; if(next){ Neuron *nn = neuron_of(b, next); had = (nn && nn->born) ? 1 : 0; }\n"),
])
patch('nkvt.c', [
    ("static i64 plain_rowid(Cur *c){ return c->e + 1; }\n",
     "static i64 plain_rowid(Cur *c){ return c->e + 1; }\n"
     "/* xyz (gate, x, y, z, shard, before, next, at, run, moved): the point's place, by gate (nkxyz.c); UPDATE or INSERT of x, y, z sets it */\n"
     "static double XX, XY, XZ; static i64 XS, XAT, XRUN; static int XB, XN, XM, XOK;\n"
     "static void xyz_begin(Cur *c, int idx, sqlite3_value **argv){ c->started = 0; c->idx = idx; c->k1 = idx == 1 ? V(argv[0]) : 0; XOK = (idx == 1 && c->b->is_main) ? nk_xyz_get((int)c->k1, &XX, &XY, &XZ, &XS, &XB, &XN, &XAT, &XRUN, &XM) : 0; }\n"
     "static int xyz_vstep(Cur *c){ if(!c->started){ c->started = 1; return XOK; } return 0; }\n"
     "static void xyz_col(Cur *c, sqlite3_context *x, int col){ switch(col){ case 0: R(x, c->k1); break; case 1: sqlite3_result_double(x, XX); break; case 2: sqlite3_result_double(x, XY); break; case 3: sqlite3_result_double(x, XZ); break; case 4: R(x, XS); break; case 5: RN(x, XB); break; case 6: RN(x, XN); break; case 7: R(x, XAT); break; case 8: R(x, XRUN); break; case 9: R(x, XM); break; } }\n"
     "static i64 xyz_rowid(Cur *c){ return c->k1; }\n"
     "static int xyz_update(Brain *b, int argc, sqlite3_value **argv, sqlite3_int64 *rowid, char **err){ if(argc == 1) return SQLITE_OK; int g = (int)V(argv[2]); if(!b->is_main || g <= 0){ *err = sqlite3_mprintf(\"xyz is the main brain's, by gate\"); return SQLITE_ERROR; } nk_xyz_set(b, g, sqlite3_value_double(argv[3]), sqlite3_value_double(argv[4]), sqlite3_value_double(argv[5])); *rowid = g; return SQLITE_OK; }\n"),
    ("  {\"defwords\", \"CREATE TABLE x(gate INTEGER, word INTEGER, defined INTEGER)\", 3, 1, {{0}}, {1}, defwords_begin, defwords_step, defwords_col, defwords_rowid, 0},\n",
     "  {\"defwords\", \"CREATE TABLE x(gate INTEGER, word INTEGER, defined INTEGER)\", 3, 1, {{0}}, {1}, defwords_begin, defwords_step, defwords_col, defwords_rowid, 0},\n"
     "  {\"xyz\", \"CREATE TABLE x(gate INTEGER, x REAL, y REAL, z REAL, shard INTEGER, before INTEGER, next INTEGER, at INTEGER, run INTEGER, moved INTEGER)\", 10, 1, {{0}}, {1}, xyz_begin, xyz_vstep, xyz_col, xyz_rowid, xyz_update},   /* the point's place (nkxyz.c) */\n"),
])
patch('nkio.c', [
    ("  if(strcmp(req, \"hop\") == 0){ sb_str(o, \"[\"); do_hop(&MAINB, o); sb_str(o, \",\"); do_hop(&SIXTHB, o); sb_str(o, \"]\"); return; }\n",
     "  if(strcmp(req, \"hop\") == 0){ sb_str(o, \"[\"); do_hop(&MAINB, o); sb_str(o, \",\"); do_hop(&SIXTHB, o); sb_str(o, \"]\"); return; }\n"
     "  if(strncmp(req, \"settle\", 6) == 0){ char t[512]; nk_xyz_settle(&MAINB, atoi(req + 6) > 0 ? atoi(req + 6) : 1, t, sizeof t); sb_str(o, t); return; }   /* the places back-populated: one step of every point that holds a definition or a place, per pass */\n"),
    ("  if(attached){ Brain **root = nk_map_root(); MAINP = root[0]; SIXTHP = root[1]; }\n",
     "  { const char *mp = getenv(\"NK_MAP\"); if(mp && *mp){ char px[4096]; snprintf(px, sizeof px, \"%s.xyz\", mp); if(nk_xyz_open(px) < 0) return 1; } }   /* the places, beside the map */\n"
     "  if(attached){ Brain **root = nk_map_root(); MAINP = root[0]; SIXTHP = root[1]; }\n"),
    ("    if(STOP){ nk_map_sync(); sqlite3_close(DB);",
     "    if(STOP){ nk_xyz_sync(); nk_map_sync(); sqlite3_close(DB);"),
    ("  sb_str(o, \"},\\\"mem\\\":{\"); first = 1;\n",
     "  /* the places the brain holds for the included points, and the formulas (the kinds' pulls) it holds: the page starts from them */\n"
     "  sb_str(o, \"},\\\"xyz\\\":[\"); first = 1;\n"
     "  for(int g = 1; g <= b->label.n; g++){ if(!inc[g]) continue; double x, y, z; i64 sh, at, run; int bf, nx, mv; if(!nk_xyz_get(g, &x, &y, &z, &sh, &bf, &nx, &at, &run, &mv)) continue; if(!first) sb_str(o, \",\"); first = 0; sb_fmt(o, \"[%d,%.2f,%.2f,%.2f,%d]\", g, x, y, z, mv); }\n"
     "  sb_str(o, \"],\\\"formula\\\":[\"); first = 1;\n"
     "  { sqlite3_stmt *fq = 0; if(sqlite3_prepare_v2(DB, \"SELECT p.kind, f.pull, f.rest, f.dx, f.dy, f.dz, f.mode FROM main.pull p JOIN main.formula f ON f.id = p.formula\", -1, &fq, 0) == SQLITE_OK){ while(sqlite3_step(fq) == SQLITE_ROW){ if(!first) sb_str(o, \",\"); first = 0; sb_fmt(o, \"[%d,%g,%g,%g,%g,%g,%d]\", sqlite3_column_int(fq, 0), sqlite3_column_double(fq, 1), sqlite3_column_double(fq, 2), sqlite3_column_double(fq, 3), sqlite3_column_double(fq, 4), sqlite3_column_double(fq, 5), sqlite3_column_int(fq, 6)); } } if(fq) sqlite3_finalize(fq); }\n"
     "  sb_str(o, \"],\\\"mem\\\":{\"); first = 1;\n"),
])
patch('serve8.py', [
    ("'rel': d['rel'], 'tables': d['counts']['born'],", "'rel': d['rel'], 'xyz': d.get('xyz', []), 'formula': d.get('formula', []), 'tables': d['counts']['born'],"),
])
patch('run-on-hp.sh', [
    ("-o nk nk.c nkvt.c nkio.c nkmap.c ", "-o nk nk.c nkvt.c nkio.c nkmap.c nkxyz.c "),
])
