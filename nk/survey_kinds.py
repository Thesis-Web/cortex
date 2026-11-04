#!/usr/bin/env python3
# survey_kinds.py (tries/45): which kinds of statement the kernel's runs under the newest N typed lines hold, by the page's rule
# (the write target after INTO, UPDATE or DELETE FROM names the kind; a statement with no target that reads is a read). Runs on hp
# against the door on 8058. Prints the counts per kind, the targets that fall to "another write" (sand), and one example text per kind.
import json, re, sys, urllib.request, collections
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
def get(u, t=60): return json.load(urllib.request.urlopen(u, timeout=t))
def q(sql, params=None):
    r = urllib.request.Request('http://127.0.0.1:8058/api/q', data=json.dumps({'sql': sql, 'params': params or []}).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r, timeout=120)).get('rows') or []
def kind_of(words):
    w = [s.lower() for s in words if s.strip() and s not in ('"', "'")]
    target = schema = None
    for i in range(len(w) - 1):
        if w[i] == 'into' or w[i] == 'update' or (w[i] == 'from' and i > 0 and w[i - 1] == 'delete'):
            target = w[i + 1]
            if target in ('main', 'sixth') and i + 3 < len(w) and w[i + 2] == '.': schema = target; target = w[i + 3]
            break
    if schema == 'sixth' or target == 'sixth': return 'sixth', target
    if target:
        if re.match(r'^(run_memory|memory|remember)$', target): return 'memory', target
        if re.match(r'^(third|told)$', target): return 'sixth', target
        if re.match(r'^(run_sheet|clock|timeline|sheet|state)$', target): return 'state', target
        if re.match(r'^(formula|pull|xyz|xyz_step|xyzforce|xyzbatch|dna|hop)$', target) or re.match(r'^\d+$', target): return 'formula', target
        if re.match(r'^(rel|belief|tried|relmap|catalog|meaning)$', target): return 'meaning', target
        if re.match(r'^(label|newgate|born)$', target): return 'birth', target
        return 'write', target
    if 'select' in w: return 'read', None
    return None, None
roots = [l['run'] for l in get('http://127.0.0.1:8058/api/newest?schema=main&n=%d' % N).get('lines', [])]
counts = collections.Counter(); sand = collections.Counter(); example = {}; runs_seen = 0; no_text = 0
for root in roots:
    x = get('http://127.0.0.1:8058/api/run?schema=main&id=%d' % root)
    for t in x.get('tree', []):
        rid = t['id']; runs_seen += 1
        if t.get('kind') == 0: counts['line (a typed line)'] += 1; continue
        rows = q("SELECT group_concat(symbol, ' ') FROM (SELECT l.symbol FROM main.seq s JOIN main.label l ON l.gate = s.gate WHERE s.run = %d ORDER BY s.pos)" % rid)
        text = rows[0][0] if rows and rows[0][0] else ''
        if not text: no_text += 1; counts['branch (no text read)'] += 1; continue
        words = text.replace('BUILD', ' ').split()
        k, target = kind_of(words)
        key = k or 'branch (no statement)'
        counts[key] += 1
        if k == 'write': sand[target] += 1
        example.setdefault(key, (rid, text[:140]))
print(json.dumps({'roots': len(roots), 'runs': runs_seen, 'no_text': no_text, 'kinds': dict(counts), 'sand_targets': dict(sand.most_common(12)), 'examples': example}, indent=1))
