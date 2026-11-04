/* nkxyz.c (2026-11-02, the restep added in the evening): a point's place, x y z, the pull of its relationships, and the history of places as
   the timeline. The owner (2026-11-01 23:40): "the encoder ... assigns that word its meaning gate id number this number is not it's x,y,z
   cordinate because the points float over a stationary graph based on the push or the pull of relationships, the gates x,y,z number is
   determinate on state and time"; "each one of these relationships represents a mathmatical formula ... the formulas are reuseable";
   "when a shard is used on a meaning point that point will likely move on the graph, unless the shard being used has the same meaning as
   the last one used"; 10-24: "the stronger the relationship the harder the pull ... the only word with zero pull is origin"; 11-02: "no
   history of places??? is that not the run reciepts in the time line? ... stepped forward or backward from end output, or beginning input
   to determine any place in time for any run, without holding a master table".
   The formulas are the brain's rows (formula, pull). The places live in a side file beside the map (NK_MAP.xyz), read as the table xyz.
   A landing whose shard, before and next are those of the point's last use is the same meaning again: no move. A move is an entry of the
   brain's timeline (at = the clock, run, key1 = -gate, key2 = the position in the run; a placement key2 = -1 - pos; a settle pass key1 = 0,
   key2 = the pass, run = the clock it began), so the receipts of the timeline are the history of places: restep walks them backward from
   the end and undoes each move exactly (the step is inverted by a fixed point: the place before is the place after minus the pull at the
   place before), and answers where a point was at any clock since the recording began. Nothing is logged beside the timeline. */
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
#define GROWT(arr, n, cap, T) do { if((n) >= (cap)){ (cap) = (cap) ? (cap) * 2 : 2; (arr) = realloc((arr), (cap) * sizeof(T)); } } while(0)

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
/* the pull on gate g standing at (px, py, pz), over the places in arr: its relationship rows both ways, each through its kind's formula
   against the other point's place, summed and capped (the page's law: a spring toward the rest length, a directed place, across the origin;
   0.04 of the sum, at most 6). mean (when given) receives the mean of the placed relations and their count: the first place of a point. */
static void force_at(Brain *b, Xyz *arr, int g, double px, double py, double pz, double *fx, double *fy, double *fz, double *mean, int *nplaced){
  sqlite3 *db = mother_db();
  if(!RQ) sqlite3_prepare_v2(db, "SELECT kind, other FROM main.rel WHERE gate = ?", -1, &RQ, 0);
  if(!RQ2) sqlite3_prepare_v2(db, "SELECT kind, gate FROM main.rel WHERE other = ?", -1, &RQ2, 0);
  double sx = 0, sy = 0, sz = 0, mx = 0, my = 0, mz = 0; int np = 0;
  for(int side = 0; side < 2; side++){ sqlite3_stmt *q = side ? RQ2 : RQ; if(!q) continue; float sg = side ? -1.0f : 1.0f;
    sqlite3_reset(q); sqlite3_bind_int(q, 1, g);
    while(sqlite3_step(q) == SQLITE_ROW){ int kind = sqlite3_column_int(q, 0), other = sqlite3_column_int(q, 1);
      if(other <= 0 || (uint64_t)other >= XCAP || other == g) continue; Xyz *o = &arr[other]; if(!o->placed) continue;
      mx += o->x; my += o->y; mz += o->z; np++;
      Fm *f = fm_of(kind); if(!f) continue;
      double vx = o->x - px, vy = o->y - py, vz = o->z - pz, L = sqrt(vx * vx + vy * vy + vz * vz); if(L < 0.01) L = 0.01;
      double sp = f->pull * (L - f->rest) / L * 0.04;
      if(f->mode == 1){ sx += -f->pull * 0.04 * ((px + f->rest * f->dx * sg) - o->x); sy += -f->pull * 0.04 * ((py + f->rest * f->dy * sg) - o->y); sz += -f->pull * 0.04 * ((pz + f->rest * f->dz * sg) - o->z); }
      else if(f->mode == 2){ sx += f->pull * 0.25 * (-o->x - px) + vx * sp; sy += f->pull * 0.25 * (-o->y - py) + vy * sp; sz += f->pull * 0.25 * (-o->z - pz) + vz * sp; }
      else { sx += vx * sp; sy += vy * sp; sz += vz * sp; } }
    sqlite3_reset(q); }
  double ml = sqrt(sx * sx + sy * sy + sz * sz); if(ml > 6){ sx *= 6 / ml; sy *= 6 / ml; sz *= 6 / ml; }
  *fx = sx; *fy = sy; *fz = sz; if(mean){ mean[0] = np ? mx / np : 0; mean[1] = np ? my / np : 0; mean[2] = np ? mz / np : 0; } if(nplaced) *nplaced = np;
}
/* a move written as a receipt of the timeline: key1 = -gate; key2 = pos for a step, -1 - pos for a placement; a settle pass: key1 = 0, key2 = the pass, run = the clock it began */
static void tl_move(Brain *b, int gate, i64 run, int pos, int placement){ GROWT(b->tl, b->ntl, b->ctl, Tl); Tl *t = &b->tl[b->ntl++]; t->at = b->clock; t->run = run; t->key1 = -gate; t->key2 = placement ? -1 - pos : pos; }
/* one step of the point in the live places: places it when it has no place (at its placed relations' mean plus a unit vector of its own, 4 away,
   or the unit vector alone), else moves it by the pull. Returns 1 when placed, 2 when moved, 0 when nothing. */
static int xyz_step(Brain *b, int gate, int force){
  if(!X) return 0; if((uint64_t)b->label.n + 1 >= XCAP && xgrow(b->label.n + 1) != 0) return 0;
  if(gate <= 0 || gate > b->label.n) return 0;
  if(ORIGIN_G < 0) ORIGIN_G = label_gate(b, "origin");
  Xyz *me = &X[gate];
  if(gate == ORIGIN_G){ if(!me->placed){ me->x = me->y = me->z = 0; me->placed = 1; return 1; } return 0; }
  if(xnow() - FM_AT > 2.0) fm_load();
  double fx, fy, fz, mean[3]; int np;
  force_at(b, X, gate, me->x, me->y, me->z, &fx, &fy, &fz, mean, &np);
  if(!me->placed){ float u[3]; unit_of(gate, u); if(np){ me->x = (float)mean[0] + 4 * u[0]; me->y = (float)mean[1] + 4 * u[1]; me->z = (float)mean[2] + 4 * u[2]; } else { me->x = u[0]; me->y = u[1]; me->z = u[2]; } me->placed = 1; return 1; }
  if(!force) return 0;
  me->x += (float)fx; me->y += (float)fy; me->z += (float)fz; return 2;
}
/* the landing: a shard used on the point with another meaning than last time moves it; the move is a receipt of the timeline */
void nk_xyz_land(Brain *b, int gate, i64 shard, int before, int next, i64 run, int pos){
  if(!b->is_main || !X) return; if((uint64_t)b->label.n + 1 >= XCAP && xgrow(b->label.n + 1) != 0) return;
  if(gate <= 0 || gate > b->label.n) return; Xyz *me = &X[gate];
  if(me->placed && me->shard == (int)shard && me->before == before && me->next == next) return;
  int did = xyz_step(b, gate, 1);
  me->shard = (int)shard; me->before = before; me->next = next; me->at = b->clock; me->run = run; if(did){ me->moved++; tl_move(b, gate, run, pos, did == 1); }
}
/* the back population, the long way once: every point that holds a definition or a place, one step each per pass; a pass is one receipt of the
   timeline (its placements are receipts of their own, so the pass can be undone exactly: the placed points were not stepped in it) */
void nk_xyz_settle(Brain *b, int passes, char *out, size_t cap){
  double t0 = xnow(); i64 placed = 0, moved = 0, points = 0; if(!X){ snprintf(out, cap, "{\"error\":\"no xyz file\"}"); return; }
  if((uint64_t)b->label.n + 1 >= XCAP && xgrow(b->label.n + 1) != 0){ snprintf(out, cap, "{\"error\":\"xyz file\"}"); return; }
  fm_load();
  for(int p = 0; p < passes; p++){ i64 began = ++b->clock;
    for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; Xyz *me = &X[g]; if(!n->nnode && !me->placed) continue; if(p == 0) points++;
      int did = xyz_step(b, g, 1); if(did == 1){ placed++; me->at = b->clock; me->moved++; tl_move(b, g, 0, 0, 1); } else if(did == 2){ moved++; me->at = b->clock; me->moved++; } }
    b->clock++; GROWT(b->tl, b->ntl, b->ctl, Tl); Tl *t = &b->tl[b->ntl++]; t->at = b->clock; t->run = began; t->key1 = 0; t->key2 = p + 1; }
  nk_xyz_sync();
  snprintf(out, cap, "{\"brain\":\"%s\",\"passes\":%d,\"points\":%lld,\"placed\":%lld,\"moved\":%lld,\"formulas\":%d,\"seconds\":%.1f}", b->name, passes, (long long)points, (long long)placed, (long long)moved, NFM, xnow() - t0);
}
/* the beginning input: the places as they stood when the history began, kept beside the places file (NK_MAP.xyz.0) with the clock of that
   moment in its header; written at the kernel's start when it is missing, and again by "restep base" (the owner, 10-30: "stepping back is
   re-stepping, deterministic, from the last snapshot"). A step backward from the end output is not unique: a step capped at six units that
   crosses the point's balance has two pre-images (measured: water undone to 5.6, 14.0 instead of 1.07, 2.94), so the history is re-stepped
   forward from the beginning input, exactly, in the order the timeline holds it. */
static char XBASE_PATH[4096]; static i64 XBASE_CLOCK = -1;
static int base_write(Brain *b){
  int fd = open(XBASE_PATH, O_RDWR | O_CREAT | O_TRUNC, 0644); if(fd < 0) return -1;
  XHead h; memset(&h, 0, sizeof h); h.magic = XMAGIC; h.cap = XCAP; h.pad[0] = (uint64_t)b->clock;
  if(pwrite(fd, &h, sizeof h, 0) != (ssize_t)sizeof h){ close(fd); return -1; }
  size_t bytes = (size_t)XCAP * sizeof(Xyz); if(pwrite(fd, X, bytes, XOFF) != (ssize_t)bytes){ close(fd); return -1; }
  close(fd); XBASE_CLOCK = b->clock; return 0;
}
void nk_xyz_base(Brain *b, const char *path){
  snprintf(XBASE_PATH, sizeof XBASE_PATH, "%s.0", path); struct stat st;
  if(stat(XBASE_PATH, &st) == 0 && st.st_size >= XOFF){ XHead h; int fd = open(XBASE_PATH, O_RDONLY); if(fd >= 0){ if(pread(fd, &h, sizeof h, 0) == (ssize_t)sizeof h && h.magic == XMAGIC) XBASE_CLOCK = (i64)h.pad[0]; close(fd); } if(XBASE_CLOCK >= 0) return; }
  if(base_write(b) == 0) fprintf(stderr, "nkxyz: the history of places begins at clock %lld (%s)\n", (long long)b->clock, XBASE_PATH);
}
/* one forward step of gate g over the places in arr (the same law as the live step), as it happened then */
static void replay_step(Brain *b, Xyz *arr, int g, int placement){
  Xyz *me = &arr[g]; double fx, fy, fz, mean[3]; int np;
  if(g == ORIGIN_G){ me->x = me->y = me->z = 0; me->placed = 1; return; }
  force_at(b, arr, g, me->x, me->y, me->z, &fx, &fy, &fz, mean, &np);
  if(placement || !me->placed){ float u[3]; unit_of(g, u); if(np){ me->x = (float)mean[0] + 4 * u[0]; me->y = (float)mean[1] + 4 * u[1]; me->z = (float)mean[2] + 4 * u[2]; } else { me->x = u[0]; me->y = u[1]; me->z = u[2]; } me->placed = 1; return; }
  me->x += (float)fx; me->y += (float)fy; me->z += (float)fz;
}
/* restep CLOCK GATE,...: the places as they stood at that clock: the beginning input replayed forward over the timeline's move receipts up to it.
   restep base: the beginning input written again as the places now. The live places are not touched. */
void nk_xyz_restep(Brain *b, i64 clock, const int *gates, int ngates, char *out, size_t cap){
  double t0 = xnow(); if(!X){ snprintf(out, cap, "{\"error\":\"no xyz file\"}"); return; }
  if(clock < 0){ if(base_write(b) == 0) snprintf(out, cap, "{\"base\":\"written\",\"clock\":%lld}", (long long)b->clock); else snprintf(out, cap, "{\"error\":\"the beginning file could not be written\"}"); return; }
  if(XBASE_CLOCK < 0){ snprintf(out, cap, "{\"error\":\"no beginning input: the history has not begun\"}"); return; }
  if(ORIGIN_G < 0) ORIGIN_G = label_gate(b, "origin");
  size_t bytes = (size_t)XCAP * sizeof(Xyz); Xyz *Y = malloc(bytes); if(!Y){ snprintf(out, cap, "{\"error\":\"no memory for the places\"}"); return; }
  int fd = open(XBASE_PATH, O_RDONLY); if(fd < 0 || pread(fd, Y, bytes, XOFF) < 0){ if(fd >= 0) close(fd); free(Y); snprintf(out, cap, "{\"error\":\"the beginning file could not be read\"}"); return; } close(fd);
  fm_load(); i64 moves = 0, placements = 0, passes = 0, first = -1, last = -1;
  i64 i = 0; while(i < b->ntl && b->tl[i].at <= XBASE_CLOCK) i++;   /* the entries before the beginning (run entries carry their run's clock; a move entry the clock it happened) */
  for(; i < b->ntl; i++){ Tl *t = &b->tl[i]; if(t->key1 > 0) continue; if(t->at > clock) break; if(t->at <= XBASE_CLOCK) continue;
    if(first < 0) first = t->at; last = t->at;
    if(t->key1 < 0){ int g = -t->key1; if(g <= 0 || (uint64_t)g >= XCAP) continue; if(t->key2 < 0){ replay_step(b, Y, g, 1); placements++; } else { replay_step(b, Y, g, 0); moves++; } }
    else if(t->key2 > 0){ passes++; i64 began = t->run;
      for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; if(!n->nnode && !Y[g].placed) continue; if(g == ORIGIN_G){ Y[g].placed = 1; continue; }
        int placed_in_pass = 0; for(i64 j = i - 1; j >= 0 && b->tl[j].at >= began; j--){ if(b->tl[j].key1 == -g && b->tl[j].key2 < 0){ placed_in_pass = 1; break; } }
        if(!placed_in_pass && Y[g].placed) replay_step(b, Y, g, 0); } } }
  size_t n = snprintf(out, cap, "{\"brain\":\"%s\",\"clock\":%lld,\"history_begins_at\":%lld,\"first_replayed_at\":%lld,\"last_replayed_at\":%lld,\"moves\":%lld,\"placements\":%lld,\"passes\":%lld,\"places\":[", b->name, (long long)clock, (long long)XBASE_CLOCK, (long long)first, (long long)last, (long long)moves, (long long)placements, (long long)passes);
  for(int k = 0; k < ngates && n < cap - 200; k++){ int g = gates[k]; if(g <= 0 || (uint64_t)g >= XCAP) continue; Xyz *y = &Y[g], *x = &X[g];
    n += snprintf(out + n, cap - n, "%s{\"gate\":%d,\"placed\":%d,\"x\":%.3f,\"y\":%.3f,\"z\":%.3f,\"now\":[%.3f,%.3f,%.3f],\"moved_now\":%d}", k ? "," : "", g, y->placed, y->x, y->y, y->z, x->x, x->y, x->z, x->moved); }
  snprintf(out + n, cap - n, "],\"seconds\":%.3f}", xnow() - t0); free(Y);
}
/* moved CLOCK: the points moved since that clock, newest first, each once, with their places now (for the page's live drawing) */
void nk_xyz_moved(Brain *b, i64 clock, int limit, char *out, size_t cap){
  size_t n = snprintf(out, cap, "{\"clock\":%lld,\"moved\":[", (long long)b->clock); int k = 0; i64 passes = 0;
  for(i64 i = b->ntl - 1; i >= 0 && k < limit && n < cap - 120; i--){ Tl *t = &b->tl[i]; if(t->key1 > 0) continue; if(t->at <= clock) break; if(t->key1 == 0){ if(t->key2 > 0) passes++; continue; } int g = -t->key1; if(g <= 0 || (uint64_t)g >= XCAP) continue; Xyz *x = &X[g]; n += snprintf(out + n, cap - n, "%s[%d,%.2f,%.2f,%.2f,%lld]", k ? "," : "", g, x->x, x->y, x->z, (long long)t->at); k++; }
  snprintf(out + n, cap - n, "],\"passes\":%lld}", (long long)passes);   /* a settle pass moved every placed point: the reader re-reads them all */
}
/* the table xyz, read by gate */
int nk_xyz_get(int gate, double *x, double *y, double *z, i64 *shard, int *before, int *next, i64 *at, i64 *run, int *moved){
  if(!X || gate <= 0 || (uint64_t)gate >= XCAP) return 0; Xyz *me = &X[gate]; if(!me->placed) return 0;
  *x = me->x; *y = me->y; *z = me->z; *shard = me->shard; *before = me->before; *next = me->next; *at = me->at; *run = me->run; *moved = me->moved; return 1;
}
int nk_xyz_set(Brain *b, int gate, double x, double y, double z){
  if(!X || gate <= 0) return 0; if((uint64_t)gate >= XCAP && xgrow(gate) != 0) return 0; Xyz *me = &X[gate]; me->x = (float)x; me->y = (float)y; me->z = (float)z; me->placed = 1; me->at = b->clock; me->moved++; return 1;
}
