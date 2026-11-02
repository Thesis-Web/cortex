/* nkxyz.c (2026-11-02): a point's place, x y z, and the pull of its relationships. The owner (2026-11-01 23:40): "the encoder ... assigns
   that word its meaning gate id number this number is not it's x,y,z cordinate because the points float over a stationary graph based on
   the push or the pull of relationships, the gates x,y,z number is determinate on state and time"; "each one of these relationships
   represents a mathmatical formula that connects points to eachother and pushes or pulls points away or together ... the formulas are
   reuseable and can be the same formula for a relationship like opposite or inverse, or alike"; "when a shard is used on a meaning point
   that point will likely move on the graph, unless the shard being used has the same meaning as the last one used"; "as the brain uses
   it's neurons it's like it's working a muscle and those neurons move some based on the different pulls or pushes of the relationships".
   10-24: "the stronger the relationship the harder the pull. the more relationships pulling in one direction the more it goes that way";
   "the only word with zero pull is origin".
   The formulas are the brain's own rows: formula (id, pull, rest, dx, dy, dz, mode) and pull (kind, formula): a kind names its formula,
   two kinds may name one. The place of every gate of the main brain lives in a side file beside the map (NK_MAP.xyz), as the brain's own
   SQLite tables do, and is read as the table xyz. The kernel applies the formulas at a landing, as land() counts the shard: the physics.
   A landing whose shard, before and next are those of the last use of the point is the same meaning again: no move (the hop shard
   "accepts the before and remainder as two variables", so the same shard with another before or next is another use). The law is the
   page's (17.3, page_patch5): a spring along the line toward the rest length (mode 0), a directed place rest away along (dx, dy, dz)
   (mode 1), across the origin (mode 2); the step 0.04 of the sum, capped at 6; a point never placed starts at the mean of its placed
   relations plus a unit vector of its own (4 away), or a unit from the origin when none is placed, as the page's placeNew. The place of
   the point named origin is 0, 0, 0 and is not moved. */
#define _GNU_SOURCE
#include "nk.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <math.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/time.h>

typedef struct { float x, y, z; int shard; int before, next; i64 at; i64 run; int moved; int placed; } Xyz;   /* 40 bytes a gate */
typedef struct { uint64_t magic, cap, pad[6]; } XHead;
#define XMAGIC 0x6e6b78797a0001ULL
#define XOFF 4096
static XHead *XH; static Xyz *X; static uint64_t XCAP; static int XFD = -1; static char *XBASE; static size_t XLEN;
static int ORIGIN_G = -1;

static int xmap(uint64_t cap){
  size_t len = XOFF + (size_t)cap * sizeof(Xyz);
  if(XBASE){ munmap(XBASE, XLEN); XBASE = 0; }
  if(ftruncate(XFD, (off_t)len) != 0){ perror("nkxyz: ftruncate"); return -1; }
  void *m = mmap(0, len, PROT_READ | PROT_WRITE, MAP_SHARED, XFD, 0); if(m == MAP_FAILED){ perror("nkxyz: mmap"); return -1; }
  XBASE = m; XLEN = len; XH = (XHead *)XBASE; X = (Xyz *)(XBASE + XOFF); XCAP = cap; return 0;
}
int nk_xyz_open(const char *path){
  struct stat st; int exists = stat(path, &st) == 0;
  XFD = open(path, O_RDWR | O_CREAT, 0644); if(XFD < 0){ perror("nkxyz: open"); return -1; }
  uint64_t cap = 1u << 21;
  if(exists && st.st_size >= XOFF){ XHead h; if(pread(XFD, &h, sizeof h, 0) == (ssize_t)sizeof h && h.magic == XMAGIC && h.cap) cap = h.cap; else exists = 0; }
  if(xmap(cap) != 0) return -1;
  if(!exists){ memset(XH, 0, sizeof *XH); XH->magic = XMAGIC; XH->cap = cap; }
  return exists ? 1 : 0;
}
static int xgrow(uint64_t need){ uint64_t cap = XCAP; while(cap <= need) cap *= 2; if(xmap(cap) != 0) return -1; XH->cap = cap; return 0; }
void nk_xyz_sync(void){ if(XBASE) msync(XBASE, XLEN, MS_ASYNC); }

/* the formulas, read from the brain's rows; read again every two seconds so a typed change is seen */
typedef struct { int kind; float pull, rest, dx, dy, dz; int mode; } Fm;
static Fm FM[512]; static int NFM; static double FM_AT = -10;
static double xnow(void){ struct timeval tv; gettimeofday(&tv, 0); return tv.tv_sec + tv.tv_usec / 1e6; }
static void fm_load(void){
  sqlite3_stmt *st = 0; NFM = 0; FM_AT = xnow();
  if(sqlite3_prepare_v2(mother_db(), "SELECT p.kind, f.pull, f.rest, f.dx, f.dy, f.dz, f.mode FROM main.pull p JOIN main.formula f ON f.id = p.formula", -1, &st, 0) != SQLITE_OK) return;
  while(sqlite3_step(st) == SQLITE_ROW && NFM < 512){ Fm *f = &FM[NFM++]; f->kind = sqlite3_column_int(st, 0); f->pull = (float)sqlite3_column_double(st, 1); f->rest = (float)sqlite3_column_double(st, 2); f->dx = (float)sqlite3_column_double(st, 3); f->dy = (float)sqlite3_column_double(st, 4); f->dz = (float)sqlite3_column_double(st, 5); f->mode = sqlite3_column_int(st, 6); }
  sqlite3_finalize(st);
}
static Fm *fm_of(int kind){ for(int i = 0; i < NFM; i++) if(FM[i].kind == kind) return &FM[i]; return 0; }
static void unit_of(int g, float *u){ uint32_t h = (uint32_t)g * 2654435761u; double a = (h / 4294967296.0) * 2 * M_PI; uint32_t h2 = (h ^ 0x9e3779b9u) * 2246822519u; double z = (h2 / 4294967296.0) * 2 - 1, r = sqrt(1 - z * z); u[0] = (float)(r * cos(a)); u[1] = (float)(r * sin(a)); u[2] = (float)z; }

static sqlite3_stmt *RQ, *RQ2;
/* one step of the point: its relationship rows both ways, each through its kind's formula against the other point's place; the sum moves it.
   force = 0 places a point that has no place yet (at its placed relations' mean) and does not step it. Returns 1 when the point was placed or moved. */
static int xyz_step(Brain *b, int gate, int force){
  if(!X) return 0; if((uint64_t)b->label.n + 1 >= XCAP && xgrow(b->label.n + 1) != 0) return 0;
  if(gate <= 0 || gate > b->label.n) return 0;
  if(ORIGIN_G < 0) ORIGIN_G = label_gate(b, "origin");
  Xyz *me = &X[gate];
  if(gate == ORIGIN_G){ if(!me->placed){ me->x = me->y = me->z = 0; me->placed = 1; me->moved++; return 1; } return 0; }
  if(xnow() - FM_AT > 2.0) fm_load();
  sqlite3 *db = mother_db();
  if(!RQ) sqlite3_prepare_v2(db, "SELECT kind, other FROM main.rel WHERE gate = ?", -1, &RQ, 0);
  if(!RQ2) sqlite3_prepare_v2(db, "SELECT kind, gate FROM main.rel WHERE other = ?", -1, &RQ2, 0);
  double fx = 0, fy = 0, fz = 0, mx = 0, my = 0, mz = 0; int nplaced = 0;
  for(int side = 0; side < 2; side++){ sqlite3_stmt *q = side ? RQ2 : RQ; if(!q) continue; float sg = side ? -1.0f : 1.0f;
    sqlite3_reset(q); sqlite3_bind_int(q, 1, gate);
    while(sqlite3_step(q) == SQLITE_ROW){ int kind = sqlite3_column_int(q, 0), other = sqlite3_column_int(q, 1);
      if(other <= 0 || (uint64_t)other >= XCAP || other == gate) continue; Xyz *o = &X[other]; if(!o->placed) continue;
      if(!me->placed){ mx += o->x; my += o->y; mz += o->z; nplaced++; continue; }
      Fm *f = fm_of(kind); if(!f) continue;
      double vx = o->x - me->x, vy = o->y - me->y, vz = o->z - me->z, L = sqrt(vx * vx + vy * vy + vz * vz); if(L < 0.01) L = 0.01;
      double sp = f->pull * (L - f->rest) / L * 0.04;   /* the spring along the line, toward the rest length */
      if(f->mode == 1){ fx += -f->pull * 0.04 * ((me->x + f->rest * f->dx * sg) - o->x); fy += -f->pull * 0.04 * ((me->y + f->rest * f->dy * sg) - o->y); fz += -f->pull * 0.04 * ((me->z + f->rest * f->dz * sg) - o->z); }
      else if(f->mode == 2){ fx += f->pull * 0.25 * (-o->x - me->x) + vx * sp; fy += f->pull * 0.25 * (-o->y - me->y) + vy * sp; fz += f->pull * 0.25 * (-o->z - me->z) + vz * sp; }
      else { fx += vx * sp; fy += vy * sp; fz += vz * sp; } }
    sqlite3_reset(q); }
  if(!me->placed){ float u[3]; unit_of(gate, u); if(nplaced){ me->x = (float)(mx / nplaced) + 4 * u[0]; me->y = (float)(my / nplaced) + 4 * u[1]; me->z = (float)(mz / nplaced) + 4 * u[2]; } else { me->x = u[0]; me->y = u[1]; me->z = u[2]; } me->placed = 1; return 1; }
  if(!force) return 0;
  double ml = sqrt(fx * fx + fy * fy + fz * fz); if(ml > 6){ fx *= 6 / ml; fy *= 6 / ml; fz *= 6 / ml; }
  me->x += (float)fx; me->y += (float)fy; me->z += (float)fz; return 1;
}
/* the landing: a shard used on the point with another meaning than last time moves it */
void nk_xyz_land(Brain *b, int gate, i64 shard, int before, int next, i64 run){
  if(!b->is_main || !X) return; if((uint64_t)b->label.n + 1 >= XCAP && xgrow(b->label.n + 1) != 0) return;
  if(gate <= 0 || gate > b->label.n) return; Xyz *me = &X[gate];
  if(me->placed && me->shard == (int)shard && me->before == before && me->next == next) return;
  int did = xyz_step(b, gate, 1);
  me->shard = (int)shard; me->before = before; me->next = next; me->at = b->clock; me->run = run; if(did) me->moved++;
}
/* the back population, the long way once: every point that holds a definition or a place, one step each; passes of it settle the graph */
void nk_xyz_settle(Brain *b, int passes, char *out, size_t cap){
  double t0 = xnow(); i64 placed = 0, moved = 0, points = 0; if(!X){ snprintf(out, cap, "{\"error\":\"no xyz file\"}"); return; }
  if((uint64_t)b->label.n + 1 >= XCAP && xgrow(b->label.n + 1) != 0){ snprintf(out, cap, "{\"error\":\"xyz file\"}"); return; }
  fm_load();
  for(int p = 0; p < passes; p++) for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; Xyz *me = &X[g]; if(!n->nnode && !me->placed) continue; if(p == 0) points++;
    int was = me->placed; if(xyz_step(b, g, 1)){ if(!was) placed++; else moved++; me->at = b->clock; me->moved++; } }
  nk_xyz_sync();
  snprintf(out, cap, "{\"brain\":\"%s\",\"passes\":%d,\"points\":%lld,\"placed\":%lld,\"moved\":%lld,\"formulas\":%d,\"seconds\":%.1f}", b->name, passes, (long long)points, (long long)placed, (long long)moved, NFM, xnow() - t0);
}
/* the table xyz, read by gate */
int nk_xyz_get(int gate, double *x, double *y, double *z, i64 *shard, int *before, int *next, i64 *at, i64 *run, int *moved){
  if(!X || gate <= 0 || (uint64_t)gate >= XCAP) return 0; Xyz *me = &X[gate]; if(!me->placed) return 0;
  *x = me->x; *y = me->y; *z = me->z; *shard = me->shard; *before = me->before; *next = me->next; *at = me->at; *run = me->run; *moved = me->moved; return 1;
}
int nk_xyz_set(Brain *b, int gate, double x, double y, double z){
  if(!X || gate <= 0) return 0; if((uint64_t)gate >= XCAP && xgrow(gate) != 0) return 0; Xyz *me = &X[gate]; me->x = (float)x; me->y = (float)y; me->z = (float)z; me->placed = 1; me->at = b->clock; me->moved++; return 1;
}
