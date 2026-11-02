cd ~/nk; cp nk nk.before2
python3 - <<'PY'
s=open('nk.c').read()
# a definition is kept whether or not the point has been walked yet
a="if(r->about && !r->same_as){ Neuron *n = neuron_of(b, r->about); if(n && n->born){ GROW(n->node, n->nnode, n->cnode, NodeRow);"
b="if(r->about && !r->same_as){ Neuron *n = neuron_of(b, r->about); if(n){ if(n->nnode == 0) b->dropped_runs++; GROW(n->node, n->nnode, n->cnode, NodeRow);"
assert s.count(a)==1; s=s.replace(a,b)
# the ok neuron: hears a cell populate on a line's sheet; marks the sheet when it is whole
a="  if(state == 1 && r->has_mem && !sheet_open(r)) complete_run(b, run);          /* sheet_fill */\n"
b='''  if(state == 1 && r->kind == 0){ int ok = label_gate(b, "ok"); if(ok && cell != ok){ Shard *o = shard_find(b, ok, cell, 0); if(!o) o = shard_lay(b, ok, cell, 0, 0); if(o) o->times++; } }   /* ok listens: a row of the ok neuron for each cell, ticked when that cell populates */
'''+a
assert s.count(a)==1; s=s.replace(a,b)
a="  Run *r = run_of(b, run); if(!r || r->complete) return; r->complete = 1;\n  if(r->kind != 0) return;\n"
b=a+'''  { int ok = label_gate(b, "ok"); if(ok) cell_set(b, run, ok, 1, "ok"); r = run_of(b, run); }   /* every cell populated: ok marks the sheet, so the brain knows */
'''
assert s.count(a)==1; s=s.replace(a,b)
open('nk.c','w').write(s)
s=open('nkvt.c').read()
a='if(strcmp(d->name, "clock") == 0 || strcmp(d->name, "shards") == 0 || strcmp(d->name, "replay") == 0){'
b='if(strcmp(d->name, "clock") == 0 || strcmp(d->name, "shards") == 0 || strcmp(d->name, "replay") == 0 || strcmp(d->name, "refused") == 0){'
assert s.count(a)==1; open('nkvt.c','w').write(s.replace(a,b))
s=open('nkio.c').read()
a='''  sb_fmt(o, "{\\"runs\\":%lld,'''
b='''  sb_fmt(o, "{\\"defined\\":%lld,", (long long)b->dropped_runs); sb_fmt(o, "\\"runs\\":%lld,'''
assert s.count(a)==1; s=s.replace(a,b)
# the one repair of the dropped definitions
a='static void handle(const char *req, SB *o){\n'
b='''static void do_repair(Brain *b, SB *o){
  i64 points = 0, rows = 0, defined = 0;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue;
    if(n->nnode == 0) for(int i = 0; i < n->nabout; i++){ Run *r = run_of(b, n->about_runs[i]); if(!r || r->kind != 3 || r->same_as || r->arrival == 15 || r->arrival == MOTHER || !r->ended) continue; if(n->nnode == 0) points++; GROW2(n->node, n->nnode, n->cnode, NodeRow); n->node[n->nnode].source = r->arrival; n->node[n->nnode].run = r - b->runs; n->nnode++; rows++; }
    if(n->nnode) defined++; }
  b->dropped_runs = defined; sb_fmt(o, "{\\"points_repaired\\":%lld,\\"node_rows\\":%lld,\\"defined\\":%lld}", (long long)points, (long long)rows, (long long)defined);
}
'''+a
assert s.count(a)==1; s=s.replace(a,b)
a='  if(strcmp(req, "memory") == 0){'
b='  if(strcmp(req, "repair") == 0){ do_repair(&MAINB, o); return; }\n'+a
assert s.count(a)==1; s=s.replace(a,b)
s=s.replace('static void do_repair(Brain *b, SB *o){','#define GROW2(arr, n, cap, T) do { if((n) >= (cap)){ (cap) = (cap) ? (cap) * 2 : 2; (arr) = realloc((arr), (cap) * sizeof(T)); } } while(0)\nstatic void do_repair(Brain *b, SB *o){',1)
# a run's read carries the points of its sheet: what it asked about, what it read
a='''  sb_fmt(o, "],\\"hops_sent\\":%d,\\"gates\\":{", n);\n'''
b='''  { int kg = label_gate(b, "known"), ug = label_gate(b, "unknown"); for(int i = 0; i < root->ncells; i++){ Cell *c = &root->cells[i]; const char *cv = val_text(b, &c->v); if(!cv) continue; if(c->cell == WHAT || c->cell == kg || c->cell == ug){ const char *q = cv; int k = 0; while(*q && k < 120){ while(*q == ' ') q++; if(!*q) break; int g = atoi(q); while(*q && *q != ' ') q++; k++; if(g > 0 && g <= b->label.n && !hmap_get(&touched, g, 0)){ hmap_put(&touched, g, 0, 1); if(ntg >= ctg){ ctg *= 2; tg = realloc(tg, sizeof(int) * ctg); } tg[ntg++] = g; } } } } }
  sb_fmt(o, "],\\"mem_gate\\":%d,\\"line\\":[", root->mem_gate); { int nl = 0; const int *ls = nk_seq(b, id, &nl); int f2 = 1; for(int i = 0; ls && i < nl && i < 40; i++){ if(ls[i] == SPACE) continue; if(!f2) sb_str(o, ","); f2 = 0; sb_fmt(o, "%d", ls[i]); } }
  sb_fmt(o, "],\\"hops_sent\\":%d,\\"gates\\":{", n);\n'''
assert s.count(a)==1; s=s.replace(a,b)
open('nkio.c','w').write(s)
PY
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o /tmp/nkcheck nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error" | head -n 8 | cut -c1-170
[ -x /tmp/nkcheck ] && echo COMPILED && rm -f /tmp/nkcheck && timeout 150 bash run-on-hp.sh up 2>&1 | tail -n 2 | cut -c1-100
python3 - <<'PY'
import socket,json,time
def ask(r,t=300):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
print("REFUSED ROWS",ask("q SELECT id, text, error FROM main.refused"),ask("q SELECT id, text, error FROM sixth.refused"),flush=True)
t=time.time(); print("repair",ask("repair"),round(time.time()-t,1),"s",flush=True)
r=ask("type main define : salt"); print("define : salt",r.get("seconds"),"s",[str(o)[:60] for o in r.get("out",[])],flush=True)
g=ask("q SELECT gate FROM main.label WHERE symbol=\'conscientization\'")["rows"][0][0]; print("conscientization nodes",ask(f"q SELECT nodes FROM main.neuron WHERE gate={g}"),"ok rows",ask("q SELECT count(*), sum(times) FROM dna WHERE gate = (SELECT gate FROM main.label WHERE symbol = \'ok\')"),flush=True)
r=ask("type sixth BUILD UPDATE sixth.spawned SET sent = 0 WHERE sent = 1 AND NOT EXISTS ( SELECT 1 FROM main.node n WHERE n.gate = sixth.spawned.gate ) ; BUILD"); print("requeue",str(r.get("out"))[:100],flush=True)
print("waiting",ask("q SELECT sent,count(*) FROM sixth.spawned GROUP BY sent"),flush=True)
r=ask("type main define : node"); print("chain started",r.get("seconds"),flush=True)
time.sleep(5); st=ask("stats"); print({k:st["main"][k] for k in ("defined","runs","refused","pending")},flush=True)
PY
