cd ~/nk
python3 - <<'PY'
s=open('nkio.c').read()
a="  for(int i = 0; i < nr; i++){ int n; const int *sq = nk_seq(b, runs[i], &n); for(int k = 0; sq && k < n; k++)"
b="  for(int i = 0; i < nr; i++){ Run *rr = run_of(b, runs[i]); int n = rr && rr->seq ? rr->nseq : 0; const int *sq = rr ? rr->seq : 0; for(int k = 0; sq && k < n; k++)"
assert s.count(a)==1; s=s.replace(a,b)
a="  for(int i = 0; i < nr; i++){ int n; const int *sq = nk_seq(b, runs[i], &n); if(!sq || n < 1) continue; if(!first) sb_str(o, \",\"); first = 0; sb_fmt(o, \"\\\"%lld\\\":%d\", (long long)runs[i], sq[0]); }"
b="  for(int i = 0; i < nr; i++){ Run *rr = run_of(b, runs[i]); const int *sq = rr ? rr->seq : 0; int n = sq ? rr->nseq : 0; if(!sq || n < 1) continue; if(!first) sb_str(o, \",\"); first = 0; sb_fmt(o, \"\\\"%lld\\\":%d\", (long long)runs[i], sq[0]); }"
assert s.count(a)==1, 'first'; s=s.replace(a,b)
open('nkio.c','w').write(s)
# the door: the whole-brain page's reads answered from the bundle
s=open('serve8.py').read()
if 'BUNDLE' not in s:
    a="def q(sql, params=None): return ask('q ' + bind(sql, params))\n"
    b=a+'''BUNDLE = {'at': 0, 'd': None}
def bundle():
    if BUNDLE['d'] is None or time.time() - BUNDLE['at'] > 30: BUNDLE['d'] = ask('bundle 400'); BUNDLE['at'] = time.time()
    return BUNDLE['d']
def from_bundle(sql, params):
    """the whole-brain page asks for the brain whole; the kernel answers the brain at the scale a page can hold (bundle): these are its reads"""
    d = bundle(); s = sql.strip()
    if s.startswith('SELECT gate, symbol FROM main.label'): return {'cols': ['gate', 'symbol'], 'rows': d['label']}
    if s.startswith('SELECT id, arrival, parent, root, kind, cell, about, at FROM main.run'): return {'cols': [], 'rows': [r[:8] for r in d['runs']]}
    if s.startswith("SELECT 'main', id, run FROM main.input"): return {'cols': [], 'rows': d['inputs']}
    if s.startswith('SELECT id, run, cell, value FROM main.out_user'): return {'cols': [], 'rows': d['out']}
    if s.startswith('SELECT (SELECT count(*) FROM main.label)'):
        st = ask('stats'); m = st['main']; x = st['sixth']; c = d['counts']
        return {'cols': [], 'rows': [[c['label'], c['born'], 0, c['shards'], c['runs'], c['receipts'], 0, 0, 0, m['refused'], m['pending'], 0, 0, c['rel'], 0, x['runs'], 0, x['refused'], m['returns']]]}
    if s.startswith('SELECT r.about, s.gate, min(r.id)'): return {'cols': [], 'rows': [[a[1], a[1], a[2]] for a in d['answ']]}
    if s.startswith('SELECT arrival, about, min(id) FROM main.run'): return {'cols': [], 'rows': d['answ']}
    if s.startswith('SELECT run, count(*) FROM main.run_receipt'): return {'cols': [], 'rows': [[r[0], r[8]] for r in d['runs']]}
    if s.startswith('SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ?'):
        last = int(params[0]) if params else 0; return {'cols': [], 'rows': [r for r in d['receipts'] if r[0] > last]}
    return None
'''
    assert s.count(a)==1; s=s.replace(a,b)
    a="                params = d.get('params') or []\n"
    b=a+"                fb = from_bundle(sql, params)\n                if fb is not None: return self.send(200, fb)\n"
    assert s.count(a)==1; s=s.replace(a,b)
    a="            if u.path == '/api/graph': return self.send(200, ask('graph ' + (qs.get('schema', ['main'])[0])))"
    b="            if u.path == '/api/graph':\n                d = bundle(); return self.send(200, {'dna': d['dna'], 'nodes': d['nodes'], 'rel': d['rel'], 'tables': d['counts']['born'], 'mem': d['mem'], 'first': d['first'], 'T': d['T'], 'dna_sent': d['counts']['dna_sent']})"
    assert s.count(a)==1; s=s.replace(a,b)
    if 'import time' not in s.split('\n')[0:12].__str__(): s=s.replace('import ', 'import time, ', 1)
    open('serve8.py','w').write(s); print('door: bundle reads')
PY
python3 -c "import ast; ast.parse(open('serve8.py').read()); print('serve8 parses')"
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o /tmp/nkb nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error" | head -n 5 | cut -c1-200
[ -x /tmp/nkb ] && { rm -f /tmp/nkb; timeout 200 bash run-on-hp.sh up 2>&1 | tail -n 1 | cut -c1-80; }
python3 - <<'PY'
import socket,json,time,urllib.request
def ask(r,t=300):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return b
t=time.time(); b=ask("bundle 400"); print("bundle",round(time.time()-t,1),"s",len(b)//1000000,"MB",flush=True)
t=time.time(); n=len(urllib.request.urlopen("http://127.0.0.1:8058/api/graph?schema=main",timeout=300).read()); print("/api/graph",round(time.time()-t,1),"s",n//1000000,"MB",flush=True)
r=urllib.request.Request("http://127.0.0.1:8058/api/q",data=json.dumps({"sql":"SELECT gate, symbol FROM main.label ORDER BY gate"}).encode(),headers={"Content-Type":"application/json"}); print("label rows",len(json.load(urllib.request.urlopen(r,timeout=120))["rows"]))
PY
