/* nkmap.c (2026-11-01). The owner: "run the fucking learning run in fucking ram ... from then on ... ram doesn't ever have to touch that point cpu
   does, because the fucking data lives on disk"; "snap shot is invention of yours that should not be there... ever". Reference draft 5.8: "It
   can be turned back on in the same state, because it is stored, not held only in RAM." The brain's bytes live in one stored file, mapped at
   the same address every time. A run writes to its pages in RAM; the operating system puts them on disk and lets them go; a point not being
   hit takes no RAM. Starting the kernel on an existing file IS the brain coming back: there is nothing to save and nothing to load. Nothing
   here knows what a run or a shard is. Without NK_MAP these fall through to the C library. One thread, so no locks. */
#define _GNU_SOURCE
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>

enum { NCLASS = 76, HDR = 16 };
#define BIG (2u << 20)                 /* a freed block this large gives its pages back to the disk */
#define ADDR ((void *)0x200000000000)  /* the same address every time: the pointers inside are the file's own */
#define MAGIC 0x6e6b6d6170ULL
typedef struct { uint64_t magic, used, cap, layout, ready; void *root; void *free_[NCLASS]; } Head;
static char *base; static Head *H;

static inline uint64_t class_size(int c){ return (c & 1 ? 48ULL : 32ULL) << (c / 2); }
static inline int class_of(uint64_t need){ int c = 0; while(class_size(c) < need) c++; return c; }
static inline int inside(const void *p){ return base && (const char *)p >= base && (const char *)p < base + H->cap; }
static inline uint64_t usable(const void *p){ return class_size((int)((const uint64_t *)p)[-2]) - HDR; }

/* 1 = the brain that was in this file, as it was; 0 = a new file; -1 = it cannot be used */
int nk_map_open(const char *path, uint64_t cap, uint64_t layout){
  struct stat st; int exists = stat(path, &st) == 0;
  int fd = open(path, exists ? O_RDWR : (O_RDWR | O_CREAT | O_EXCL), 0644);
  if(fd < 0){ perror("nk_map_open"); return -1; }
  if(exists) cap = (uint64_t)st.st_size; else if(ftruncate(fd, (off_t)cap) != 0){ perror("nk_map_open: ftruncate"); return -1; }
  void *m = mmap(ADDR, cap, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_FIXED_NOREPLACE, fd, 0);
  if(m == MAP_FAILED){ perror("nk_map_open: mmap"); return -1; }
  close(fd); base = m; H = (Head *)base;
  if(exists){
    if(H->magic != MAGIC || H->layout != layout){ fprintf(stderr, "nkmap: %s was written by a kernel with another layout\n", path); return -1; }
    if(!H->ready){ fprintf(stderr, "nkmap: %s was never finished; refusing it\n", path); return -1; }
    return 1;
  }
  H->magic = MAGIC; H->cap = cap; H->layout = layout; H->ready = 0; H->root = 0; H->used = (sizeof(Head) + 4095) & ~4095ULL;
  return 0;
}
uint64_t nk_map_used(void){ return H ? H->used : 0; }
void *nk_map_root(void){ return H ? H->root : 0; }
void nk_map_set_root(void *p){ if(H) H->root = p; }
void nk_map_ready(void){ if(H) H->ready = 1; }
void nk_map_sync(void){ if(H) msync(base, H->used, MS_SYNC); }

static void *take(size_t size, int *fresh){
  int c = class_of((uint64_t)size + HDR); void *p = H->free_[c]; uint64_t cs = class_size(c);
  if(p){ H->free_[c] = *(void **)p; *fresh = 0; return p; }
  uint64_t at = H->used; if(cs >= BIG) at = (at + 4095) & ~4095ULL;
  if(at + cs > H->cap){ fprintf(stderr, "nkmap: the stored file is full at %llu bytes\n", (unsigned long long)at); abort(); }
  H->used = at + cs; uint64_t *h = (uint64_t *)(base + at); h[0] = (uint64_t)c; h[1] = 0; *fresh = 1; return base + at + HDR;
}
void *nk_malloc(size_t size){ if(!base) return malloc(size); int f; return take(size, &f); }
void *nk_calloc(size_t n, size_t s){ if(!base) return calloc(n, s); int f; size_t t = n * s; void *p = take(t, &f); if(!f) memset(p, 0, t); return p; }
void nk_free(void *p){
  if(!p) return;
  if(!inside(p)){ free(p); return; }
  int c = (int)((uint64_t *)p)[-2]; uint64_t cs = class_size(c);
  if(cs >= BIG){ char *from = (char *)(((uintptr_t)p + 8 + 4095) & ~(uintptr_t)4095), *to = (char *)(((uintptr_t)p - HDR + cs) & ~(uintptr_t)4095); if(to > from) madvise(from, (size_t)(to - from), MADV_REMOVE); }
  *(void **)p = H->free_[c]; H->free_[c] = p;
}
void *nk_realloc(void *p, size_t size){
  if(!base) return realloc(p, size);
  if(!p) return nk_malloc(size);
  if(!inside(p)) return realloc(p, size);
  uint64_t have = usable(p); if(size <= have) return p;
  void *q = nk_malloc(size); memcpy(q, p, have); nk_free(p); return q;
}
char *nk_strdup(const char *s){ if(!base) return strdup(s); size_t n = strlen(s) + 1; char *q = nk_malloc(n); memcpy(q, s, n); return q; }
