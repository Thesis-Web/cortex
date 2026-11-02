cd ~/nk
python3 - <<'PY'
s=open('nkio.c').read()
# the shards of the receipts sent, and the memory rows of the runs sent
a='  sb_str(o, "],\\"receipts\\":["); first = 1; i64 rid = 0;\n'
b='''  sb_str(o, "],\\"memrows\\":["); first = 1;
  for(int i = 0; i < nr; i++){ Run *r = run_of(b, runs[i]); if(!r || !r->has_mem || r->same_as || !r->seq) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%lld,%d,%lld,\\"", (long long)runs[i], r->mem_gate, (long long)r->mem_shard); for(int k = 0; k < r->nseq && k < 60; k++) sb_fmt(o, k ? " %d" : "%d", r->seq[k]); sb_str(o, "\\"]"); }
  sb_str(o, "],\\"hit_dna\\":["); first = 1; { HMap hs; hmap_init(&hs, 1 << 16);
  for(int i = nr - 1; i >= 0; i--){ Run *r = run_of(b, runs[i]); if(!r || !r->nrc) continue; for(int j = 0; j < r->nrc; j++){ Rc *k = &r->rcs[j]; if(hmap_get(&hs, k->gate, k->shard)) continue; hmap_put(&hs, k->gate, k->shard, 1); Shard *sh = shard_by_id(b, k->gate, k->shard); if(!sh || sh->times >= T) continue; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%lld,%d,%d,%lld,%lld,%lld]", k->gate, (long long)sh->id, sh->before, sh->trigger, (long long)sh->call, (long long)sh->spawn, (long long)sh->times); if(sh->before > 0 && sh->before <= b->label.n) inc[sh->before] = 1; if(sh->trigger > 0 && sh->trigger <= b->label.n) inc[sh->trigger] = 1; } } free(hs.e); }
'''+a
assert s.count(a)==1; s=s.replace(a,b)
# the label list must come after hit_dna names its ends: move the label emission to the end
i=s.index('  sb_str(o, "],\\"label\\":["); first = 1; i64 nlab = 0;'); j=s.index('  sb_str(o, "],\\"nodes\\":{");', i)
lab=s[i:j]; s=s[:i]+s[j:]
a='  sb_fmt(o, "],\\"counts\\":{\\"label\\":%d'
assert s.count(a)==1; s=s.replace(a, lab.replace('sb_str(o, "],\\"label\\":[")','sb_str(o, "],\\"label\\":[")')+a)
open('nkio.c','w').write(s)
s=open('serve8.py').read()
a="    if s.startswith('SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ?'):"
b='''    if s.startswith('SELECT run, gate, shard, input FROM main.run_memory'): return {'cols': [], 'rows': d['memrows']}
    if s.startswith("SELECT 'told', t.run,"):
        rows = []
        for who, key in (('told', 'sixth'), ('asked main', 'main')):
            n = ask('newest ' + key + ' 400')
            for l in n.get('told', []): rows.append([who, l['run'], l['text'], None])
        return {'cols': [], 'rows': rows}
'''+a
assert s.count(a)==1; s=s.replace(a,b)
a="                d = bundle(); return self.send(200, {'dna': d['dna'],"
b="                d = bundle(); return self.send(200, {'dna': d['dna'] + d['hit_dna'],"
assert s.count(a)==1; s=s.replace(a,b)
a="                return self.send(200, q(sql, params))\n"
b="                r = q(sql, params)\n                if 'rows' not in r: r = {'cols': [], 'rows': [], 'error': r.get('error')}   # a read the kernel refuses (no key) is an empty answer to the page, with the reason\n                return self.send(200, r)\n"
assert s.count(a)==1; s=s.replace(a,b)
open('serve8.py','w').write(s); print('door mapped')
PY
python3 -c "import ast; ast.parse(open('serve8.py').read()); print('serve8 parses')"
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o /tmp/nkb nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error" | head -n 5 | cut -c1-200
[ -x /tmp/nkb ] && { rm -f /tmp/nkb; timeout 200 bash run-on-hp.sh up 2>&1 | tail -n 1 | cut -c1-80; }
python3 - <<'PY'
import socket,json,time
def ask(r,t=300):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return b
t=time.time(); b=ask("bundle 400"); d=json.loads(b.decode()); print("bundle",round(time.time()-t,1),"s",len(b)//1000000,"MB memrows",len(d["memrows"]),"hit_dna",len(d["hit_dna"]),"label",len(d["label"]),flush=True)
PY
