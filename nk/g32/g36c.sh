cd ~/nk/g36 || exit 1
python3 - <<'PY'
s=open('nkvt.c').read()
a="  info->idxNum = 0; info->estimatedCost = 1e9; info->estimatedRows = 1000000; return SQLITE_OK;\n"
b='''  /* no search: a read comes with its key or it does not happen. The owner, 2026-11-01: "no sweep, search table, find nothing". Clock and shards are one row */
  if(strcmp(d->name, "clock") == 0 || strcmp(d->name, "shards") == 0 || strcmp(d->name, "replay") == 0){ info->idxNum = 0; info->estimatedCost = 1; info->estimatedRows = 1; return SQLITE_OK; }
  return SQLITE_CONSTRAINT;
'''
assert s.count(a)==1; open('nkvt.c','w').write(s.replace(a,b))
s=open('nkio.c').read()
i=s.index('static void do_graph('); j=s.index('\n}\n',i)+3
print('do_graph',j-i,'chars'); s=s[:i]+s[j:]
for a in ['  else if(strncmp(req, "graph main", 10) == 0) do_graph(&MAINB, o);\n','  else if(strncmp(req, "graph sixth", 11) == 0) do_graph(&SIXTHB, o);\n']:
    assert s.count(a)==1; s=s.replace(a,'')
open('nkio.c','w').write(s)
PY
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o nkclean nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error|implicit" | head -n 8 | cut -c1-170
ls -la nkclean | cut -c24-70
cd ~/nk; grep -n "api/\|ask(\|\"q \|/full\|graph" serve8.py | cut -c1-150 | head -n 22; grep -n "fetch(\|api/" NEURON-LIGHT*.html light*.html door/*.html 2>/dev/null | cut -c1-140 | head -n 14; ls *.html | head
