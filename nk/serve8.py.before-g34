#!/usr/bin/env python3
# serve8.py (2026-10-30): the kernel's door. The same page as v6 (the owner: "I really like the look of the one we have") served over HTTP;
# every request becomes one line to the kernel's socket: a typed line, a read of the graph, a SELECT. The door decides nothing.
# usage: python3 serve8.py <http port> <kernel port> <page.html> [lines file] [first-runs file] [bind address, default 127.0.0.1]
import time, sys, os, json, socket, re, time, http.server, urllib.parse
PORT, KPORT, PAGE = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
LIGHT = os.path.join(os.path.dirname(os.path.abspath(PAGE)), 'NEURON-POINT-OF-CONNECTION-nk-light-2026-10-30.html')
LINES = sys.argv[4] if len(sys.argv) > 4 else None; FIRST = sys.argv[5] if len(sys.argv) > 5 else None; BIND = sys.argv[6] if len(sys.argv) > 6 else '127.0.0.1'
STARTED = time.time(); JOBS = {}; JOBN = [0]; HISTORY_CAP = int(os.environ.get('NK_HISTORY_CAP', '50000'))
def ask(req):
    s = socket.create_connection(('127.0.0.1', KPORT)); s.sendall((req + '\n').encode()); buf = b''
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b'\n'): break
    s.close(); return json.loads(buf.decode())
def lit(v):
    if v is None: return 'NULL'
    if isinstance(v, bool): return '1' if v else '0'
    if isinstance(v, (int, float)): return repr(v)
    return "'" + str(v).replace("'", "''") + "'"
def bind(sql, params):
    # the page sends a SELECT with ? holes and their values; the kernel's socket takes one text, so the door fills the holes (outside quotes) with literals
    if not params: return sql
    out = []; k = 0; inq = False
    for ch in sql:
        if ch == "'": inq = not inq
        if ch == '?' and not inq and k < len(params): out.append(lit(params[k])); k += 1
        else: out.append(ch)
    return ''.join(out)
def q(sql, params=None): return ask('q ' + bind(sql, params))
BUNDLE = {'at': 0, 'd': None}
def bundle():
    if BUNDLE['d'] is None or time.time() - BUNDLE['at'] > 600: BUNDLE['d'] = ask('bundle 400'); BUNDLE['at'] = time.time()
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
    if s.startswith('SELECT run, gate, shard, input FROM main.run_memory'): return {'cols': [], 'rows': d['memrows']}
    if s.startswith("SELECT 'told', t.run,"):
        rows = []
        for who, key in (('told', 'sixth'), ('asked main', 'main')):
            n = ask('newest ' + key + ' 400')
            for l in n.get('told', []): rows.append([who, l['run'], l['text'], None])
        return {'cols': [], 'rows': rows}
    if s.startswith('SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ?'):
        last = int(params[0]) if params else 0; return {'cols': [], 'rows': [r for r in d['receipts'] if r[0] > last]}
    return None
RUNS = []
def fill(line):
    def r(m):
        k = int(m.group(1)); return str(RUNS[k - 1]) if 0 < k <= len(RUNS) and RUNS[k - 1] else m.group(0)
    line = re.sub(r'\{run:(\d+)\}', r, line)
    def g(m):
        schema = 'sixth' if m.group(1) == '6' else 'main'
        rows = q(f"SELECT gate FROM {schema}.label WHERE symbol = '{m.group(2)}'")['rows']
        return str(rows[0][0]) if rows else m.group(0)
    return re.sub(r'\{gate(6?):([^}]+)\}', g, line)
def decode(schema, run):
    rows = q(f"SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM {schema}.seq s JOIN {schema}.label l ON l.gate = s.gate WHERE s.run = {run} ORDER BY s.pos)")['rows']
    return rows[0][0] if rows and rows[0][0] is not None else ''
def match_runs(lines):
    RUNS.clear(); seen = {}; typed = {}
    for schema in ('main', 'sixth'):
        # the typed lines from the kernel's mailbox read (newest first): a read of the whole input table has no key and the kernel refuses it
        n = ask('newest ' + schema + ' 5000')
        typed[schema] = [(l['run'], l['text']) for l in reversed(n.get('lines', []))]
    for l in lines:
        if not l.strip() or l.startswith('#'): continue
        l = fill(l); schema, text = ('sixth', l[3:]) if l.startswith('6> ') else ('main', l)
        n = seen.get((schema, text), 0); seen[(schema, text)] = n + 1
        hits = [run for (run, t) in typed[schema] if t == text]
        RUNS.append(hits[n] if n < len(hits) else None)
    return list(RUNS)
def read_lines():
    out = []
    for which, path in (('tools', LINES), ('first', FIRST)):
        if not path or not os.path.exists(path): continue
        raw = [l.rstrip('\n') for l in open(path, encoding='utf-8')]
        runs = match_runs(raw) if which == 'tools' else None
        k = 0; note = []
        for l in raw:
            if not l.strip(): note = []; continue
            if l.startswith('#'): note.append(l[1:].strip()); continue
            k += 1
            try: filled = fill(l)
            except Exception: filled = l
            out.append({'file': which, 'k': k, 'note': ' '.join(note), 'raw': l, 'line': filled, 'run': (runs[k - 1] if runs and k - 1 < len(runs) else None)}); note = []
    return {'lines': out}
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *a): pass
    def send(self, code, obj, ctype='application/json'):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, default=str).encode()
        self.send_response(code); self.send_header('Content-Type', ctype + ('' if isinstance(obj, bytes) and not ctype.startswith('text') else '; charset=utf-8'))
        self.send_header('Content-Length', str(len(body))); self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)
    def body(self):
        n = int(self.headers.get('Content-Length') or 0); return json.loads(self.rfile.read(n) or b'{}')
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); qs = urllib.parse.parse_qs(u.query)
        try:
            if u.path in ('/', '/index.html', '/light'): return self.send(200, open(LIGHT if os.path.exists(LIGHT) else PAGE, 'rb').read(), 'text/html')
            if u.path == '/full': return self.send(200, open(PAGE, 'rb').read(), 'text/html')
            if u.path == '/api/stats': return self.send(200, ask('stats'))
            if u.path == '/api/newest': return self.send(200, ask('newest ' + (qs.get('schema', ['main'])[0]) + ' ' + str(int(qs.get('n', ['30'])[0]))))
            if u.path == '/api/run': return self.send(200, ask('run ' + (qs.get('schema', ['main'])[0]) + ' ' + str(int(qs.get('id', ['0'])[0]))))
            if u.path == '/api/info':
                st = ask('stats'); return self.send(200, {'brain': 'nk main', 'sixth': 'nk sixth', 'sources': 'attached', 'sqlite': 'nk', 'started': STARTED, 'ready': True, 'error': None, 'busy': None, 'queued': 0, 'version': 'nk', 'stats': st})
            if u.path == '/api/graph':
                d = bundle(); return self.send(200, {'dna': d['dna'] + d['hit_dna'], 'nodes': d['nodes'], 'rel': d['rel'], 'tables': d['counts']['born'], 'mem': d['mem'], 'first': d['first'], 'T': d['T'], 'dna_sent': d['counts']['dna_sent']})
            if u.path == '/api/lines': return self.send(200, read_lines())
            if u.path == '/api/job':
                j = JOBS.get(int(qs.get('id', ['0'])[0])); return self.send(200, j) if j else self.send(404, {'error': 'no such job'})
            return self.send(404, {'error': 'no such path'})
        except Exception as e: return self.send(500, {'error': str(e)})
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try: d = self.body()
        except Exception as e: return self.send(400, {'error': 'bad json: ' + str(e)})
        try:
            if u.path == '/api/type':
                line = str(d.get('line') or '').strip()
                if not line: return self.send(400, {'error': 'an empty line'})
                if d.get('prompt') == 'sixth' and not line.startswith('6> '): line = '6> ' + line
                if not RUNS and LINES and os.path.exists(LINES): match_runs([l.rstrip('\n') for l in open(LINES, encoding='utf-8')])
                line = fill(line); schema, text = ('sixth', line[3:]) if line.startswith('6> ') else ('main', line)
                t = time.time(); r = ask(f'type {schema} {text}'); RUNS.append(r.get('run'))
                JOBN[0] += 1; j = {'id': JOBN[0], 'kind': 'type', 'done': True, 'result': r, 'error': r.get('error'), 'progress': None, 'elapsed': time.time() - t, 'line': line}
                JOBS[j['id']] = j; return self.send(200, j)
            if u.path == '/api/q':
                sql = str(d.get('sql') or '').strip()
                if not sql.upper().startswith(('SELECT', 'WITH', 'PRAGMA TABLE_INFO', 'PRAGMA DATABASE_LIST')): return self.send(400, {'error': 'only a SELECT is read through this door'})
                params = d.get('params') or []
                fb = from_bundle(sql, params)
                if fb is not None: return self.send(200, fb)
                # the page's history read asks for every receipt after the last it saw; on a brain of millions this door answers the newest HISTORY_CAP
                if sql.startswith('SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ?') and params:
                    top = q('SELECT max(id) FROM main.run_receipt')['rows'][0][0] or 0
                    if top - int(params[0]) > HISTORY_CAP: params = [top - HISTORY_CAP]
                r = q(sql, params)
                if 'rows' not in r: r = {'cols': [], 'rows': [], 'error': r.get('error')}   # a read the kernel refuses (no key) is an empty answer to the page, with the reason
                return self.send(200, r)
            if u.path == '/api/fresh': return self.send(400, {'error': "the kernel's door lays no eggs; start the kernel again"})
            return self.send(404, {'error': 'no such path'})
        except Exception as e: return self.send(500, {'error': str(e)})
if __name__ == '__main__':
    srv = http.server.ThreadingHTTPServer((BIND, PORT), H); srv.daemon_threads = True
    print('kernel', KPORT, 'page', PAGE, 'bound to', BIND, 'open http://localhost:%d/' % PORT, flush=True)
    srv.serve_forever()
