#!/usr/bin/env python3
# g37/restep_patch.py (2026-11-02): the restep of places. nkxyz.c is replaced whole (tries/37/nkxyz.c); here: nk.h's declarations, nk.c's
# landing passes its position, nkio.c's requests restep and moved. Applied on hp in ~/nk; backups *.before-g37.
import sys, os
D = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/nk')
def patch(name, pairs):
    p = os.path.join(D, name); s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (name, s.count(old), old[:80])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s); print('patched', name, len(pairs))
patch('nk.h', [
    ("int nk_xyz_open(const char *path); void nk_xyz_land(Brain *b, int gate, i64 shard, int before, int next, i64 run); void nk_xyz_settle(Brain *b, int passes, char *out, size_t cap);",
     "int nk_xyz_open(const char *path); void nk_xyz_land(Brain *b, int gate, i64 shard, int before, int next, i64 run, int pos); void nk_xyz_settle(Brain *b, int passes, char *out, size_t cap); void nk_xyz_restep(Brain *b, i64 clock, const int *gates, int ngates, char *out, size_t cap); void nk_xyz_moved(Brain *b, i64 clock, int limit, char *out, size_t cap); void nk_xyz_base(Brain *b, const char *path);"),
])
patch('nk.c', [
    ("nk_xyz_land(b, gate, s->id, kb, kx, run);", "nk_xyz_land(b, gate, s->id, kb, kx, run, pos);"),
])
patch('nkio.c', [
    ("  nk_count_rows(&MAINB); nk_count_rows(&SIXTHB);\n  nk_map_ready();",
     "  nk_count_rows(&MAINB); nk_count_rows(&SIXTHB);\n  { const char *mp = getenv(\"NK_MAP\"); if(mp && *mp){ char px[4096]; snprintf(px, sizeof px, \"%s.xyz\", mp); nk_xyz_base(&MAINB, px); } }   /* the beginning input of the history of places, written at the first start after the recording began */\n  nk_map_ready();"),
    ("  if(strncmp(req, \"settle\", 6) == 0){",
     "  if(strncmp(req, \"restep \", 7) == 0){ /* restep CLOCK GATE,GATE,...: the places as they stood at that clock, the beginning input replayed forward over the timeline; restep base writes the beginning input again */ char t[65536]; i64 clk = strncmp(req + 7, \"base\", 4) == 0 ? -1 : atoll(req + 7); const char *p = strchr(req + 7, ' '); int gates[512], ng = 0; while(p && *p && ng < 512){ while(*p == ' ' || *p == ',') p++; if(!*p) break; gates[ng++] = atoi(p); while(*p && *p != ',' && *p != ' ') p++; } nk_xyz_restep(&MAINB, clk, gates, ng, t, sizeof t); sb_str(o, t); return; }\n"
     "  if(strncmp(req, \"moved \", 6) == 0){ char t[1 << 20]; nk_xyz_moved(&MAINB, atoll(req + 6), 20000, t, sizeof t); sb_str(o, t); return; }   /* the points moved since a clock, with their places now */\n"
     "  if(strncmp(req, \"settle\", 6) == 0){"),
])
