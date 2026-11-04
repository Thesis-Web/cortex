# keyed_reads.py (tries/45): the doors answer by key: a few keyed rows, timed, on the hub (8056) and the kernel (hp:8058 through ssh is not used; the kernel's door is read from its own box). Prints JSON lines.
import json, time, urllib.request, sys
host = sys.argv[1]
def q(sql, params):
    r = urllib.request.Request(host + '/api/q', data=json.dumps({'sql': sql, 'params': params}).encode(), headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter(); j = json.load(urllib.request.urlopen(r, timeout=120)); return round((time.perf_counter() - t0) * 1000, 1), len(j.get('rows') or []), j.get('error')
reads = [
  ('labels by gate', 'SELECT l.gate, l.symbol FROM main.label l WHERE l.gate IN (1,2,3,4,5,6,15,16,19,20)', []),
  ('places by gate', 'SELECT x.gate, x.x, x.y, x.z, x.moved FROM main.xyz x WHERE x.gate IN (1,2,3,4,5,6,15,16,19,20)', []),
  ('rel rows by gate', 'SELECT gate, kind, other, run FROM main.rel WHERE gate IN (1,2,3,4,5,6,15,16,19,20)', []),
  ('runs by id', 'SELECT r.id, r.arrival, r.parent, r.root, r.kind FROM main.run r WHERE r.id IN (%s)' % ','.join(str(i) for i in range(int(sys.argv[2]) - 9, int(sys.argv[2]) + 1)), []),
  ('receipts by run', 'SELECT id, run, pos, gate, shard FROM main.run_receipt WHERE run IN (%s)' % ','.join(str(i) for i in range(int(sys.argv[2]) - 4, int(sys.argv[2]) + 1)), []),
]
for name, sql, params in reads:
    try: ms, n, err = q(sql, params); print(json.dumps({'door': host, 'read': name, 'ms': ms, 'rows': n, 'error': err}))
    except Exception as e: print(json.dumps({'door': host, 'read': name, 'error': str(e)[:120]}))
