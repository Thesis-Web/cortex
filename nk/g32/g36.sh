mkdir -p ~/nk/g36 && cd ~/nk/g36 || exit 1
cp ../g35/nk.c ../g35/nk.h ../g35/nkio.c ../g35/nkvt.c ../g35/nkmap.c ../sqlite3.h .
python3 - <<'PY'
import re
s=open('nkio.c').read()
def cut(s,a,b):
    i=s.index(a); j=s.index(b,i); return s[:i]+s[j:]
s=cut(s,'static const char *EXPORT_TABLES[]','static const char *SRCDIR')
s=cut(s,'static void copy_table(','static void brain_stats(')
s=cut(s,"/* the brain's own tables (rel, asked, spawned ...) back from an export",'static void do_stats(')
for a in ['  else if(strncmp(req, "export ", 7) == 0) do_export(req + 7, o);\n','  else if(strncmp(req, "snapshot ", 9) == 0) do_snapshot(req + 9, o);\n']:
    assert s.count(a)==1,a; s=s.replace(a,'')
a='  if(JOURNAL){ fprintf(JOURNAL, "%s%s\\n", b->is_main ? "" : "6> ", text); fflush(JOURNAL); }\n'
assert s.count(a)==1; s=s.replace(a,'')
a='static FILE *JOURNAL;\n'; assert s.count(a)==1; s=s.replace(a,'')
a='  if(getenv("NK_JOURNAL")){ JOURNAL = fopen(getenv("NK_JOURNAL"), "a"); if(!JOURNAL) perror(getenv("NK_JOURNAL")); }\n'
assert s.count(a)==1; s=s.replace(a,'')
i=s.index('  const char *load = getenv("NK_LOAD");'); j=s.index('  else if(!attached){ lay_egg(&MAINB, argv[2]);')
s=s[:i]+'  if(!attached){ lay_egg(&MAINB, argv[2]); lay_egg(&SIXTHB, argv[2]); }\n'+s[s.index('\n',j)+1:]
a='  if(load){ load_own_tables("main", lp_main); load_own_tables("sixth", lp_sixth); sqlite3_free(lp_main); sqlite3_free(lp_sixth); }\n'
assert s.count(a)==1; s=s.replace(a,'')
open('nkio.c','w').write(s)
s=open('nk.c').read()
i=s.index('/* ---------------- a brain back from its export'); j=s.index('\n}\n', s.index('int nk_load(Brain *b, const char *path){'))+3
# the load runs to the end of its function; find the real end by the next top-level item
m=re.compile(r'^\}\n', re.M); k=None
for x in m.finditer(s, s.index('int nk_load(Brain *b, const char *path){')):
    k=x.end(); break
print('load function ends at', k, 'of', len(s), 'after it:', repr(s[k:k+80]))
s=s[:i]+s[k:]
open('nk.c','w').write(s)
s=open('nk.h').read(); s=re.sub(r'\n[^\n]*nk_load\(Brain[^\n]*','',s); open('nk.h','w').write(s)
PY
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o nkclean nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error|implicit" | head -n 12 | cut -c1-170
ls -la nkclean | cut -c24-70; wc -l nk.c nkio.c nkvt.c nkmap.c | tail -n 5; grep -n "snapshot\|export\|NK_LOAD\|JOURNAL\|journal" nk.c nkio.c | cut -c1-120 | head; grep -n "\"/api/\|snapshot\|export" ../serve8.py | cut -c1-120 | head -n 14
