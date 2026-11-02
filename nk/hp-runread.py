#!/usr/bin/env python3
# hp-runread.py: the light page's reads timed through the door: the newest typed line's run and a define run the sixth sent
import json, time, urllib.request
def get(path):
    t = time.time(); b = urllib.request.urlopen('http://127.0.0.1:8058' + path, timeout=120).read(); return json.loads(b), time.time() - t, len(b)
n, t, _ = get('/api/newest?schema=main&n=40'); print(f"newest: {t:.3f} s; {len(n['lines'])} typed lines, {len(n['told'])} told")
for label, rid in [('the newest typed line', n['lines'][0]['run']), ('a define the sixth sent', next(l['run'] for l in n['told'] if l['text'].startswith('define'))), ('the first define : who', 185)]:
    r, t, size = get(f'/api/run?schema=main&id={rid}')
    print(f"{label}: run {rid} '{r['run']['text'][:40]}' read in {t:.3f} s, {size/1024:.0f} KB; tree {r['tree_runs']} runs / {r['tree_hops']} hops ({r['hops_sent']} sent); {len(r['gates'])} gates touched, {len(r['names'])} named ends; cells {[(c[0], str(c[2])[:12]) for c in r['cells']][:7]}; back {[(b['depth'], b['run']) for b in r['back']]}")
s, t, _ = get('/api/stats'); print(f"stats: {t:.3f} s; main runs {s['main']['runs']}, gates {s['main']['gates']}, pending {s['main']['pending']}")
