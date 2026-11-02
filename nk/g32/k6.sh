cd ~/nk; cp nk nk.before3
python3 - <<'PY'
s=open('nk.c').read()
# the space is the hop, not a landing (the owner, 10-30: "the space between those symbols is a hop, jump, call, spawn"; 11-01: the point everything passes through)
a="  Neuron *n = neuron_of(b, gate);\n  if(!n || !n->born){ /* a landing on a gate with no region"
b="  { int np = pos + 1; while(np <= r->nseq && r->seq[np - 1] == SPACE) np++; next = np <= r->nseq ? r->seq[np - 1] : 0; }   /* the space is the hop: the run steps from symbol to symbol */\n"+a
assert s.count(a)==1; s=s.replace(a,b)
a="  if(next != 0 && (via == 1 || had == 1)){ Hop h = {0}; h.type = HOP_LAND; h.run = run; h.pos = pos + 1; h.gate = next; h.before = via == 1 ? before : gate; h.next = (pos + 2 <= r->nseq) ? r->seq[pos + 1] : 0; h.via = 0; push(b, h); }"
b="  if(next != 0 && (via == 1 || had == 1)){ int np = pos + 1; while(np <= r->nseq && r->seq[np - 1] == SPACE) np++; int nn = np + 1; while(nn <= r->nseq && r->seq[nn - 1] == SPACE) nn++; Hop h = {0}; h.type = HOP_LAND; h.run = run; h.pos = np; h.gate = next; h.before = via == 1 ? before : gate; h.next = nn <= r->nseq ? r->seq[nn - 1] : 0; h.via = 0; push(b, h); }"
assert s.count(a)==1; s=s.replace(a,b)
open('nk.c','w').write(s)
s=open('nkio.c').read()
a='static void handle(const char *req, SB *o){\n'
b=r'''/* ---- the whole-brain page's bundle: the brain at the scale a page can hold. The DNA rows hit at least T times (T chosen so at most CAP rows go),
   the symbols those rows name, every point's definition and memory counts, the relationship rows of those points, the newest K lines with every
   run under them, their sheets, receipts and outputs. Read from the regions in C, by walking them once; the page asks for it whole. ---- */
static void do_bundle(Brain *b, int K, SB *o){
  enum { CAP = 1200000, MAXR = 120000 };
  i64 hist[65]; memset(hist, 0, sizeof hist);
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; for(int j = 0; j < n->nsh; j++){ i64 t = n->sh[j].times; int k = 0; while(t > 1 && k < 64){ t >>= 1; k++; } hist[k]++; } }
  i64 acc = 0; int T = 1; for(int k = 64; k >= 0; k--){ if(acc + hist[k] > CAP && acc > 0){ T = 1 << (k + 1); break; } acc += hist[k]; T = 1 << k; }
  char *inc = calloc(b->label.n + 2, 1);
  sb_fmt(o, "{\"T\":%d,\"dna\":[", T); int first = 1; i64 ndna = 0;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n) continue; for(int j = 0; j < n->nsh; j++){ Shard *s = &n->sh[j]; if(s->times < T) continue; if(!first) sb_str(o, ","); first = 0; ndna++; inc[g] = 1; if(s->before > 0 && s->before <= b->label.n) inc[s->before] = 1; if(s->trigger > 0 && s->trigger <= b->label.n) inc[s->trigger] = 1; sb_fmt(o, "[%d,%lld,%d,%d,%lld,%lld,%lld]", g, (long long)s->id, s->before, s->trigger, (long long)s->call, (long long)s->spawn, (long long)s->times); } }
  for(int g = 1; g <= 90 && g <= b->label.n; g++) inc[g] = 1;
  /* the newest K lines and every run under them */
  i64 *runs = malloc(sizeof(i64) * MAXR); int nr = 0; HMap seen; hmap_init(&seen, 1 << 17);
  for(int which = 0; which < 2; which++){ Mail *box = which ? b->third : b->input; i64 nbox = which ? b->nthird : b->ninput; for(i64 i = nbox - 1; i >= 0 && i >= nbox - K && nr < MAXR; i--){ i64 top = box[i].run; if(!top || hmap_get(&seen, top, 0)) continue; int head = nr; runs[nr++] = top; hmap_put(&seen, top, 0, 1); while(head < nr && nr < MAXR){ Run *r = run_of(b, runs[head++]); if(!r) continue; for(int k = 0; k < r->nkids && nr < MAXR; k++){ i64 kid = r->kids[k]; if(hmap_get(&seen, kid, 0)) continue; hmap_put(&seen, kid, 0, 1); runs[nr++] = kid; } } } }
  /* the symbols of those runs' lines, so the page decodes them */
  for(int i = 0; i < nr; i++){ int n; const int *sq = nk_seq(b, runs[i], &n); for(int k = 0; sq && k < n; k++) if(sq[k] > 0 && sq[k] <= b->label.n) inc[sq[k]] = 1; Run *r = run_of(b, runs[i]); if(r) for(int c = 0; c < r->ncells; c++){ int cg = r->cells[c].cell; if(cg > 0 && cg <= b->label.n) inc[cg] = 1; } }
  sb_str(o, "],\"rel\":["); first = 1; i64 nrel = 0;
  if(!REL_Q){ char q[64]; snprintf(q, sizeof q, "SELECT kind, other FROM %s.rel WHERE gate = ?", b->name); sqlite3_prepare_v2(DB, q, -1, &REL_Q, 0); }
  if(REL_Q) for(int g = 1; g <= b->label.n && nrel < CAP; g++){ if(!inc[g]) continue; Neuron *n = neuron_of(b, g); if(!n || !n->nnode) continue; sqlite3_bind_int(REL_Q, 1, g); int cnt = 0; while(sqlite3_step(REL_Q) == SQLITE_ROW && cnt < 40){ int kind = sqlite3_column_int(REL_Q, 0), other = sqlite3_column_int(REL_Q, 1); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%d,%d,0]", g, kind, other); nrel++; cnt++; if(kind > 0 && kind <= b->label.n) inc[kind] = 1; if(other > 0 && other <= b->label.n) inc[other] = 1; } sqlite3_reset(REL_Q); }
  sb_str(o, "],\"label\":["); first = 1; i64 nlab = 0;
  for(int g = 1; g <= b->label.n; g++){ if(!inc[g]) continue; if(!first) sb_str(o, ","); first = 0; nlab++; sb_fmt(o, "[%d,", g); sb_json(o, b->label.sym[g]); sb_str(o, "]"); }
  sb_str(o, "],\"nodes\":{"); first = 1;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->nnode) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":%d", g, n->nnode); }
  sb_str(o, "},\"mem\":{"); first = 1;
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->nmem) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%d\":%d", g, n->nmem); }
  sb_str(o, "},\"runs\":["); first = 1;
  for(int i = 0; i < nr; i++){ Run *r = run_of(b, runs[i]); if(!r) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%d,", (long long)runs[i], r->arrival); if(r->parent_set) sb_fmt(o, "%lld", (long long)r->parent); else sb_str(o, "null"); sb_fmt(o, ",%lld,%d,", (long long)r->root, r->kind); if(r->cell) sb_fmt(o, "%d", r->cell); else sb_str(o, "null"); sb_str(o, ","); if(r->about) sb_fmt(o, "%d", r->about); else sb_str(o, "null"); sb_fmt(o, ",%lld,%d]", (long long)r->at, r->nhops); }
  sb_str(o, "],\"first\":{"); first = 1;
  for(int i = 0; i < nr; i++){ int n; const int *sq = nk_seq(b, runs[i], &n); if(!sq || n < 1) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "\"%lld\":%d", (long long)runs[i], sq[0]); }
  sb_str(o, "},\"inputs\":["); first = 1;
  for(int which = 0; which < 2; which++){ Mail *box = which ? b->third : b->input; i64 nbox = which ? b->nthird : b->ninput; for(i64 i = (nbox - K > 0 ? nbox - K : 0); i < nbox; i++){ if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[\"%s\",%lld,%lld]", which ? (b->is_main ? "sixth" : "main") : "main", (long long)box[i].id, (long long)box[i].run); } }
  sb_str(o, "],\"out\":["); first = 1;
  for(i64 i = (b->nout - 4000 > 0 ? b->nout - 4000 : 0); i < b->nout; i++){ Out *w = &b->out[i]; if(!hmap_get(&seen, w->run, 0)) continue; const char *v = val_text(b, &w->v); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%lld,%d,", (long long)w->id, (long long)w->run, w->cell); if(v) sb_json(o, v); else sb_str(o, "null"); sb_str(o, "]"); }
  /* the definitions: for the included points, which sources answered (the page's defines and answers reads) */
  sb_str(o, "],\"answ\":["); first = 1;
  for(int g = 1; g <= b->label.n; g++){ if(!inc[g]) continue; Neuron *n = neuron_of(b, g); if(!n || !n->nnode) continue; int seenSrc[64]; int ns = 0; for(int j = 0; j < n->nnode; j++){ int src = n->node[j].source; int dup = 0; for(int k = 0; k < ns; k++) if(seenSrc[k] == src) dup = 1; if(dup || ns >= 64) continue; seenSrc[ns++] = src; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%d,%lld]", src, g, (long long)n->node[j].run); } }
  sb_str(o, "],\"receipts\":["); first = 1; i64 rid = 0;
  for(int i = nr - 1; i >= 0; i--){ Run *r = run_of(b, runs[i]); if(!r || !r->nrc) continue; for(int j = 0; j < r->nrc; j++){ Rc *k = &r->rcs[j]; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%lld,%d,%lld]", (long long)++rid, (long long)runs[i], k->gate, (long long)k->shard); } }
  sb_fmt(o, "],\"counts\":{\"label\":%d,\"born\":%d,\"shards\":%lld,\"runs\":%lld,\"receipts\":%lld,\"rel\":%lld,\"dna_sent\":%lld,\"label_sent\":%lld,\"runs_sent\":%d,\"defined\":%lld}}", b->label.n, b->label.n, (long long)b->shards, (long long)b->nruns, (long long)b->hops_done, (long long)nrel, (long long)ndna, (long long)nlab, nr, (long long)b->dropped_runs);
  free(inc); free(runs); free(seen.e);
}
'''+a
assert s.count(a)==1; s=s.replace(a,b)
a='  if(strcmp(req, "repair") == 0){'
b='  if(strncmp(req, "bundle ", 7) == 0){ do_bundle(&MAINB, atoi(req + 7) > 0 ? atoi(req + 7) : 400, o); return; }\n'+a
assert s.count(a)==1; s=s.replace(a,b)
open('nkio.c','w').write(s)
PY
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o /tmp/nkb nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error" | head -n 8 | cut -c1-200
[ -x /tmp/nkb ] && { echo COMPILED; rm -f /tmp/nkb; timeout 200 bash run-on-hp.sh up 2>&1 | tail -n 1 | cut -c1-90; }
python3 - <<'PY'
import socket,json,time
def ask(r,t=300):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return b
t=time.time(); b=ask("bundle 400"); d=json.loads(b.decode()); print("bundle",round(time.time()-t,1),"s",len(b)//1000000,"MB","T",d["T"],"dna",len(d["dna"]),"label",len(d["label"]),"rel",len(d["rel"]),"runs",len(d["runs"]),"receipts",len(d["receipts"]),"out",len(d["out"]),"answ",len(d["answ"]),"nodes",len(d["nodes"]),"counts",d["counts"],flush=True)
r=json.loads(ask("type main define : hinge").decode()); print("define : hinge",r.get("seconds"),"s hops",r.get("hops"),"refused",r.get("refused"),flush=True)
x=json.loads(ask(f"run main {r['run']}").decode()); import collections; c=collections.Counter(h[2] for h in x["hops"]); print("space hops in the new run:",c.get(3,0),"of",len(x["hops"]))
PY
