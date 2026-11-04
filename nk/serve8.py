#!/usr/bin/env python3
# serve8.py (2026-10-30): the kernel's door. The same page as v6 (the owner: "I really like the look of the one we have") served over HTTP;
# every request becomes one line to the kernel's socket: a typed line, a read of the graph, a SELECT. The door decides nothing.
# usage: python3 serve8.py <http port> <kernel port> <page.html> [lines file] [first-runs file] [bind address, default 127.0.0.1]
import time, sys, os, json, socket, re, time, http.server, urllib.parse
import queue, threading
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
LIVE = {'base': None, 'rc': [], 'runs': [], 'inputs': [], 'out': [], 'first': {}, 'label': [], 'seen': set(), 'gates': set(), 'next': 1, 'n': 0, 'memrows': []}
def bundle():
    if BUNDLE['d'] is None or time.time() - BUNDLE['at'] > 600:
        BUNDLE['d'] = ask('bundle ' + os.environ.get('NK_BUNDLE_K', '2000')); BUNDLE['at'] = time.time()
    return BUNDLE['d']
def live_add(r):
    """a line typed through this door: its runs, receipts, symbols and out rows, read from the kernel's run record, appended after the history served so far"""
    if r.get('schema') != 'main' or not r.get('run'): return
    open_set()   # tries/50: the open set exists without the bundle; a typed line the open set already laid (the run count grew) is not laid twice
    if r['run'] in LIVE['seen']: return
    x = ask('run main %d' % r['run'])
    if 'hops' not in x: return
    root = (x.get('run') or {}).get('root') or r['run']
    for t in x.get('tree', []):
        if t['id'] in LIVE['seen']: continue
        LIVE['seen'].add(t['id']); LIVE['runs'].append([t['id'], t['arrival'], t.get('parent'), root, t['kind'], t.get('cell') or None, t.get('about') or None, t['id']])
    for h in x['hops']:
        if h[1] == 0 and h[0] not in LIVE['first']: LIVE['first'][h[0]] = h[2]
        LIVE['rc'].append([LIVE['next'], h[0], h[2], h[3]]); LIVE['next'] += 1
    for g, v in (x.get('gates') or {}).items():
        g = int(g)
        if g not in LIVE['gates']: LIVE['gates'].add(g); LIVE['label'].append([g, v.get('s')])
    LIVE['n'] += 1; LIVE['inputs'].append(['main', LIVE['n'], r['run']])
    for o in r.get('out', []):
        if o[0] == 'main': LIVE['out'].append([LIVE['next'], o[1], o[2], o[3]]); LIVE['next'] += 1
    for m in (q('SELECT run, gate, shard, input FROM main.run_memory WHERE run = ?', [root]) or {}).get('rows') or []: LIVE['memrows'].append(m)   # the root's memory row, by key
OPEN_K = int(os.environ.get('NK_OPEN_K', '400')); OPEN_LOCK = threading.Lock(); OPEN = {'runs_at': -1, 'built': 0, 'adds': 0, 'rel': None, 'done': 0, 'seconds': None}
def open_set():
    """tries/50: the page's open set, the newest K lines of the main brain (typed and told) and every run under them, read by key: newest, run per root,
    run_memory by run. No whole-brain bundle. Refreshed only when the kernel's run count grew since the last read (the brain changed), never on a clock."""
    st = (ask('stats').get('main') or {}); runs = st.get('runs') or 0
    if LIVE['base'] is not None and runs == OPEN['runs_at']: return
    with OPEN_LOCK:
        if LIVE['base'] is not None and runs == OPEN['runs_at']: return
        if LIVE['base'] is None:
            LIVE['base'] = []; LIVE['next'] = 1   # the history's ids count from 1 as the bundle's did; a page open before this door restarted reads on from where it was
            n = ask('newest main %d' % OPEN_K); OPEN['built'] += 1
            lines = [('main', l) for l in n.get('lines', [])] + [('sixth', l) for l in n.get('told', [])]
        else:
            n = ask('newest main 50'); lines = [('main', l) for l in n.get('lines', [])] + [('sixth', l) for l in n.get('told', [])]
        lines = [(who, l) for who, l in lines if l.get('run') and l['run'] not in LIVE['seen']]
        lines.sort(key=lambda wl: wl[1]['run'])   # oldest first: the history replays in the order it happened
        t0 = time.time()
        for who, l in lines: open_add(who, l['id'], l['run'])
        OPEN['runs_at'] = runs
        if not OPEN['done']: OPEN['done'] = 1; OPEN['seconds'] = round(time.time() - t0, 1)
def open_add(who, mail_id, run):
    x = ask('run main %d' % run)
    if 'hops' not in x: return
    root = (x.get('run') or {}).get('root') or run; OPEN['adds'] += 1
    for t in x.get('tree', []):
        if t['id'] in LIVE['seen']: continue
        LIVE['seen'].add(t['id']); LIVE['runs'].append([t['id'], t['arrival'], t.get('parent'), root, t['kind'], t.get('cell') or None, t.get('about') or None, t['id']])
    own = set(t['id'] for t in x.get('tree', []) if not t.get('same_as'))   # the runs under the line that hold their own receipts (the bundle's rule, r->nrc); a run that repeats an earlier one borrows that run's and lays none
    for h in x['hops']:
        if h[0] not in own: continue
        if h[1] == 0 and h[0] not in LIVE['first']: LIVE['first'][h[0]] = h[2]
        LIVE['rc'].append([LIVE['next'], h[0], h[2], h[3]]); LIVE['next'] += 1
    for g, v in (x.get('gates') or {}).items():
        g = int(g)
        if g not in LIVE['gates']: LIVE['gates'].add(g); LIVE['label'].append([g, v.get('s')])
    LIVE['inputs'].append([who, mail_id, run])
    ids = [t['id'] for t in x.get('tree', [])]
    if ids:   # the memory rows of every run under the line, one keyed read (the kernel answers run_memory by run)
        mr = q('SELECT run, gate, shard, input FROM main.run_memory WHERE run IN (%s)' % ','.join(str(i) for i in ids[:400]), [])
        for m in (mr or {}).get('rows') or []: LIVE['memrows'].append(m)
        if (mr or {}).get('error'): OPEN['memerr'] = mr['error']
    for c in x.get('cells') or []:   # the line's output: its root's sheet cells with a value (the owner, 10-26: output to the user comes from the same memory table)
        if c[1] == 1 and c[2] is not None: LIVE['out'].append([LIVE['next'], root, c[0], c[2]]); LIVE['next'] += 1
BUNDLE_PREFIXES = ('SELECT gate, symbol FROM main.label', 'SELECT id, arrival, parent, root, kind, cell, about, at FROM main.run', "SELECT 'main', id, run FROM main.input", 'SELECT id, run, cell, value FROM main.out_user', 'SELECT (SELECT count(*) FROM main.label)', 'SELECT r.about, s.gate, min(r.id)', 'SELECT arrival, about, min(id) FROM main.run', 'SELECT run, count(*) FROM main.run_receipt', 'SELECT run, gate, shard, input FROM main.run_memory', 'SELECT m.run, m.gate, m.shard, m.input FROM main.run_memory m JOIN main.run r', 'SELECT gate, x, y, z, moved FROM main.xyz', 'SELECT p.kind, f.pull, f.rest, f.dx, f.dy, f.dz, f.mode FROM main.pull p', "SELECT 'told', t.run,", 'SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ?')
def from_bundle(sql, params):
    """the whole-brain page asks for the brain whole; the kernel answers the brain at the scale a page can hold (bundle): these are its reads.
    tries/45: the bundle is built only when one of those reads arrives; a keyed read never loads the brain whole into the door"""
    s = sql.strip()
    if not s.startswith(BUNDLE_PREFIXES): return None
    if s.startswith(("SELECT 'main', id, run FROM main.input", 'SELECT id, run, cell, value FROM main.out_user', 'SELECT (SELECT count(*) FROM main.label)', 'SELECT run, gate, shard, input FROM main.run_memory', 'SELECT m.run, m.gate, m.shard, m.input FROM main.run_memory m JOIN main.run r', 'SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ?')):
        open_set()   # tries/50: by key, never the whole brain
        if s.startswith("SELECT 'main', id, run FROM main.input"): return {'cols': [], 'rows': list(LIVE['inputs'])}
        if s.startswith('SELECT id, run, cell, value FROM main.out_user'): return {'cols': [], 'rows': list(LIVE['out'])}
        if s.startswith('SELECT (SELECT count(*) FROM main.label)'):
            st = ask('stats'); m = st['main']; x = st['sixth']
            if OPEN['rel'] is None: OPEN['rel'] = ((q('SELECT count(*) FROM main.rel') or {}).get('rows') or [[0]])[0][0]   # once per door: a count over the brain's own rel table
            return {'cols': [], 'rows': [[m['gates'], m['defined'], 0, m['shard_rows'], m['runs'], m['receipts'], 0, 0, 0, m['refused'], m['pending'], 0, 0, OPEN['rel'], 0, x['runs'], 0, x['refused'], m['returns']]]}
        if s.startswith('SELECT run, gate, shard, input FROM main.run_memory'): return {'cols': [], 'rows': list(LIVE['memrows'])}
        if s.startswith('SELECT m.run, m.gate, m.shard, m.input FROM main.run_memory m JOIN main.run r'):
            root = int(params[0]) if params else 0; roots = {r[0]: r[3] for r in LIVE['runs']}; return {'cols': [], 'rows': [m for m in LIVE['memrows'] if m[0] == root or roots.get(m[0]) == root]}
        last = int(params[0]) if params else 0; return {'cols': [], 'rows': [r for r in LIVE['rc'] if r[0] > last]}
    if s.startswith('SELECT p.kind, f.pull, f.rest, f.dx, f.dy, f.dz, f.mode FROM main.pull p'): return None   # the brain's own formula and pull tables answer by themselves (38 rows)
    if s.startswith("SELECT 'told', t.run,"):
        rows = []
        for who, key in (('told', 'sixth'), ('asked main', 'main')):
            n = ask('newest ' + key + ' 400')
            for l in n.get('told', []): rows.append([who, l['run'], l['text'], None])
        return {'cols': [], 'rows': rows}
    OPEN.setdefault('bundle_by', []).append(s[:90])
    d = bundle()
    if s.startswith('SELECT gate, symbol FROM main.label'): return {'cols': ['gate', 'symbol'], 'rows': d['label'] + LIVE['label']}
    if s.startswith('SELECT id, arrival, parent, root, kind, cell, about, at FROM main.run'):
        bs = set(r[0] for r in d['runs']); return {'cols': [], 'rows': [r[:8] for r in d['runs']] + [r for r in LIVE['runs'] if r[0] not in bs]}
    if s.startswith("SELECT 'main', id, run FROM main.input"): return {'cols': [], 'rows': d['inputs'] + LIVE['inputs']}
    if s.startswith('SELECT id, run, cell, value FROM main.out_user'): return {'cols': [], 'rows': d['out'] + LIVE['out']}
    if s.startswith('SELECT (SELECT count(*) FROM main.label)'):
        st = ask('stats'); m = st['main']; x = st['sixth']; c = d['counts']
        return {'cols': [], 'rows': [[c['label'], c['born'], 0, c['shards'], c['runs'], c['receipts'], 0, 0, 0, m['refused'], m['pending'], 0, 0, c['rel'], 0, x['runs'], 0, x['refused'], m['returns']]]}
    if s.startswith('SELECT r.about, s.gate, min(r.id)'): return {'cols': [], 'rows': d.get('defw', [])}   # a point to the words of its definition
    if s.startswith('SELECT arrival, about, min(id) FROM main.run'): return {'cols': [], 'rows': d['answ']}
    if s.startswith('SELECT run, count(*) FROM main.run_receipt'): return {'cols': [], 'rows': [[r[0], r[8]] for r in d['runs']]}
    if s.startswith('SELECT run, gate, shard, input FROM main.run_memory'): return {'cols': [], 'rows': d['memrows']}
    if s.startswith('SELECT m.run, m.gate, m.shard, m.input FROM main.run_memory m JOIN main.run r'):
        root = int(params[0]) if params else 0; roots = {r[0]: r[3] for r in d['runs']}; return {'cols': [], 'rows': [m for m in d['memrows'] if m[0] == root or roots.get(m[0]) == root]}
    if s.startswith('SELECT gate, x, y, z, moved FROM main.xyz'): return {'cols': [], 'rows': d.get('xyz', [])}   # the places of the included points (the xyz table is read by gate; the bundle carries them)
    if s.startswith('SELECT p.kind, f.pull, f.rest, f.dx, f.dy, f.dz, f.mode FROM main.pull p'): return {'cols': [], 'rows': d.get('formula', [])}
    if s.startswith('SELECT id, run, gate, shard FROM main.run_receipt WHERE id > ?'):
        last = int(params[0]) if params else 0; return {'cols': [], 'rows': [r for r in (LIVE['base'] if LIVE['base'] is not None else d['receipts']) if r[0] > last] + [r for r in LIVE['rc'] if r[0] > last]}
    return None
RUNS = []
SUBS = []; HOLD = {}; TOLD = {'clock': 0, 'runs': 0}; TELL_LOCK = threading.Lock()   # tries/43: the open page streams, what each tab holds, what was told last
def tell(why):
    """tries/43 (2026-11-03; the owner: "a timer and a sweep... both which just won't work in a system like this"): the door tells the page.
    After a line the door passed, the moves since the clock last told (the timeline's move receipts, from the kernel's moved verb) and the
    run count go to every open page stream; the page reads the runs that ended by their ids and glides the points moved. The kernel is asked
    here only because the door itself just passed a line; never on a clock. The kernel's own pending work ending a run after the line
    returned, and a line typed on the kernel's socket without this door, are not told: that is the kernel's own tell, on the owner's word."""
    if not SUBS: return
    with TELL_LOCK:
        try: m = ask('moved ' + str(TOLD['clock'])); st = ask('stats')
        except Exception: return
        runs = (st.get('main') or {}).get('runs') or 0
        ev = {'moves': [[r[0], r[1], r[2], r[3], r[4], 0] for r in (m.get('moved') or [])], 'passes': m.get('passes') or 0, 'runs': runs, 'runs_before': TOLD['runs'], 'clock': m.get('clock'), 'why': why}
        TOLD['clock'] = m.get('clock') or TOLD['clock']; TOLD['runs'] = runs
    for s in list(SUBS):
        try: s.put_nowait(ev)
        except queue.Full:
            try: SUBS.remove(s)
            except ValueError: pass
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
                st = ask('stats'); return self.send(200, {'brain': 'nk main', 'sixth': 'nk sixth', 'sources': 'attached', 'sqlite': 'nk', 'started': STARTED, 'ready': True, 'error': None, 'busy': None, 'queued': 0, 'version': 'nk', 'stats': st, 'open': {'k': OPEN_K, 'built': OPEN['built'], 'roots': OPEN['adds'], 'receipts': len(LIVE['rc']), 'inputs': len(LIVE['inputs']), 'memrows': len(LIVE['memrows']), 'memerr': OPEN.get('memerr'), 'done': OPEN['done'], 'seconds': OPEN['seconds'], 'bundle_by': OPEN.get('bundle_by', [])[:5], 'bundle_held': BUNDLE['d'] is not None}})
            if u.path == '/api/moved': return self.send(200, ask('moved ' + str(int(qs.get('since', ['0'])[0]))))
            if u.path == '/api/stream': return self.stream(qs)   # tries/43: the door tells the page   # the points the brain moved since a clock (the timeline's move receipts)
            if u.path == '/api/graph':
                if qs.get('fresh', ['0'])[0] == '1': BUNDLE['d'] = None
                d = bundle(); return self.send(200, {'dna': d['dna'] + d['hit_dna'], 'nodes': d['nodes'], 'rel': d['rel'], 'xyz': d.get('xyz', []), 'formula': d.get('formula', []), 'clock': ((q('SELECT n FROM main.clock') or {}).get('rows') or [[0]])[0][0], 'tables': d['counts']['born'], 'mem': d['mem'], 'first': dict(d['first'], **{str(k): v for k, v in LIVE['first'].items()}), 'T': d['T'], 'dna_sent': d['counts']['dna_sent']})
            if u.path == '/api/lines': return self.send(200, read_lines())
            if u.path == '/api/job':
                j = JOBS.get(int(qs.get('id', ['0'])[0])); return self.send(200, j) if j else self.send(404, {'error': 'no such job'})
            return self.send(404, {'error': 'no such path'})
        except Exception as e: return self.send(500, {'error': str(e)})
    def stream(self, qs):
        """tries/43: one open response per tab (server-sent events); tell() puts an event here after every line this door passed. No timer:
        this response waits on the queue. A tab that stopped reading is dropped at the next write."""
        tab = (qs.get('tab') or [''])[0]; sq = queue.Queue(maxsize=4096)
        if not SUBS:
            try:
                TOLD['runs'] = (ask('stats').get('main') or {}).get('runs') or 0
                if TOLD['clock'] == 0: TOLD['clock'] = ((q('SELECT n FROM main.clock') or {}).get('rows') or [[0]])[0][0] or 0   # the first stream begins at the clock now
            except Exception: pass
        SUBS.append(sq)
        self.send_response(200); self.send_header('Content-Type', 'text/event-stream; charset=utf-8'); self.send_header('Cache-Control', 'no-store'); self.send_header('Access-Control-Allow-Origin', '*'); self.end_headers()
        try:
            self.wfile.write(('data: ' + json.dumps({'hello': 'the kernel door tells', 'clock': TOLD['clock'], 'runs': TOLD['runs']}) + '\n\n').encode()); self.wfile.flush()
            while True:
                ev = sq.get(); hold = HOLD.get(tab) if tab else None
                moves = ev['moves'] if hold is None else [mv for mv in ev['moves'] if mv[0] in hold]
                if not moves and not ev['passes'] and ev['runs'] <= ev['runs_before']: continue
                self.wfile.write(('data: ' + json.dumps(dict(ev, moves=moves)) + '\n\n').encode()); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError): pass
        finally:
            try: SUBS.remove(sq)
            except ValueError: pass
            if tab: HOLD.pop(tab, None)
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try: d = self.body()
        except Exception as e: return self.send(400, {'error': 'bad json: ' + str(e)})
        if u.path == '/api/hold':   # tries/43: the gates a tab holds (its zoom); kept at the door, nothing asked of the kernel
            tab = str(d.get('tab') or ''); s = HOLD.setdefault(tab, set())
            if d.get('gates') is not None: s.clear(); s.update(int(g) for g in d['gates'])
            s.update(int(g) for g in (d.get('add') or []))
            return self.send(200, {'tab': tab, 'held': len(s)})
        try:
            if u.path == '/api/type':
                line = str(d.get('line') or '').strip()
                if not line: return self.send(400, {'error': 'an empty line'})
                if d.get('prompt') == 'sixth' and not line.startswith('6> '): line = '6> ' + line
                if not RUNS and LINES and os.path.exists(LINES): match_runs([l.rstrip('\n') for l in open(LINES, encoding='utf-8')])
                line = fill(line); schema, text = ('sixth', line[3:]) if line.startswith('6> ') else ('main', line)
                t = time.time(); r = ask(f'type {schema} {text}'); RUNS.append(r.get('run')); live_add(r)   # the page reads the brain again after its line: this run, its receipts and symbols are appended to what it reads
                JOBN[0] += 1; j = {'id': JOBN[0], 'kind': 'type', 'done': True, 'result': r, 'error': r.get('error'), 'progress': None, 'elapsed': time.time() - t, 'line': line}
                JOBS[j['id']] = j; tell('type'); return self.send(200, j)   # tries/43: the brain changed by this line: the page streams are told now
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
    threading.Thread(target=open_set, daemon=True).start()   # tries/50: the open set read by key at the door's start, so the first page open does not wait on it
    print('kernel', KPORT, 'page', PAGE, 'bound to', BIND, 'open http://localhost:%d/' % PORT, flush=True)
    srv.serve_forever()
