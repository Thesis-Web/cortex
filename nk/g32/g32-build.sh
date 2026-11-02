cd ~/nk/g32 || exit 1
cp ../nk.c ../nk.h ../nkio.c ../nkvt.c . && cp ../*.h . 2>/dev/null; cp ../nk.c ../nk.h ../nkio.c ../nkvt.c .
python3 - <<'PY'
s=open('nk.h').read()
a='#include "sqlite3.h"\n'
b='''#include "sqlite3.h"
#include <stdlib.h>
#include <string.h>
/* where the brain's bytes live: nkmap.c */
int nk_map_open(const char *path, uint64_t cap); uint64_t nk_map_used(void);
void *nk_malloc(size_t); void *nk_calloc(size_t, size_t); void *nk_realloc(void *, size_t); void nk_free(void *); char *nk_strdup(const char *);
#ifndef NK_MAP_SELF
#define malloc nk_malloc
#define calloc nk_calloc
#define realloc nk_realloc
#define free nk_free
#define strdup nk_strdup
#endif
'''
assert s.count(a)==1; open('nk.h','w').write(s.replace(a,b))
s=open('nkio.c').read()
a='int main(int argc, char **argv){\n'
b='int main(int argc, char **argv){\n  if(getenv("NK_MAP") && *getenv("NK_MAP")){ if(nk_map_open(getenv("NK_MAP"), 220ULL << 30) != 0) return 1; }\n'
assert s.count(a)==1; open('nkio.c','w').write(s.replace(a,b))
PY
grep -n "include" nk.c | head -n 14 | cut -c1-70; grep -n "include" nkio.c | head -n 14 | cut -c1-60; grep -n "sb_\?free\|, free)\|(free)" nkio.c nkvt.c nk.c | head -n 8 | cut -c1-150
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -I. -o nkstored nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error|warning" | head -n 14 | cut -c1-170
cp ../nk nkheap; ls -la nkstored nkheap | cut -c24-80
