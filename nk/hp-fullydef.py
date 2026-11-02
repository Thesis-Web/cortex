#!/usr/bin/env python3
# hp-fullydef.py: which definition rows are fully known (every letter-symbol in them a point with definition rows of its own), and a first
# meaning test on them: does a point's definition predict its like-relations? (the symbols of the definition, their like-partners, against the point's)
import socket, json, re, collections, time
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
t = time.time()
defined = {g for (g,) in q("SELECT DISTINCT gate FROM node")}
sym = dict(q("SELECT gate, symbol FROM label WHERE gate IN (SELECT DISTINCT gate FROM node)"))
print("points with definition rows:", len(defined))
# the definition rows of the defined points, each as its symbols
rows = q("SELECT n.gate, n.source, n.run FROM node n WHERE n.source IN (7, 8, 11, (SELECT gate FROM label WHERE symbol = 'wikt'))")
full = []; part = collections.Counter(); total = 0
for i in range(0, len(rows), 300):
    chunk = rows[i:i+300]
    seqs = collections.defaultdict(list)
    for r, g in q("SELECT run, gate FROM seq WHERE run IN (%s) ORDER BY run, pos" % ",".join(str(r) for (_, _, r) in chunk)): seqs[r].append(g)
    for (g, src, r) in chunk:
        gs = seqs.get(r, [])
        total += 1
        # a symbol counts if it is letters; known if it has definition rows
        need = [x for x in gs if x not in defined and x > 80]
        if not need: full.append((g, src, r, gs))
        part[min(len(need), 20)] += 1
print(f"definition rows read {total}: fully known {len(full)} ({100*len(full)/max(1,total):.1f}%); rows by how many symbols still undefined (0..20+): {sorted(part.items())[:12]}  [{time.time()-t:.0f} s]")
# the fully known rows: which sources, how long
bysrc = collections.Counter(src for (_, src, _, _) in full); print("fully known rows by source:", {sym.get(k, k) if k in sym else k: v for k, v in bysrc.items()}, "| median symbols", sorted(len(gs) for (_, _, _, gs) in full)[len(full)//2] if full else 0)
labels = dict(q("SELECT gate, symbol FROM label WHERE gate IN (%s)" % ",".join(str(x) for x in set(x for (_, _, _, gs) in full[:400] for x in gs) | {g for (g, _, _, _) in full[:400]})))
for (g, src, r, gs) in full[:8]: print("  ", labels.get(g), "<-", "".join(labels.get(x, '?') for x in gs)[:110])
# the meaning test: the definition's content symbols' like-partners against the point's own like-partners
like = collections.defaultdict(set)
for a, b in q("SELECT gate, other FROM rel WHERE kind = (SELECT gate FROM label WHERE symbol = 'like')"): like[a].add(b); like[b].add(a)
hits = []; n_tested = 0
for (g, src, r, gs) in full:
    if not like.get(g): continue
    content = [x for x in set(gs) if x > 80 and x != g and len(labels.get(x, labels.setdefault(x, ''))) > 2]
    if not content: continue
    pred = collections.Counter()
    for x in content:
        for y in like.get(x, ()): 
            if y != g: pred[y] += 1
    if not pred: continue
    top = {y for y, _ in pred.most_common(20)}; actual = like[g]
    hits.append((len(top & actual) / max(1, len(top)), len(top & actual) / max(1, len(actual)), len(actual))); n_tested += 1
if hits:
    import statistics
    print(f"meaning test on {n_tested} fully known rows: of the 20 likes predicted from the definition's symbols, a median {statistics.median(h[0] for h in hits)*100:.0f}% are the point's real likes; those cover a median {statistics.median(h[1] for h in hits)*100:.0f}% of its likes; points have a median {statistics.median(h[2] for h in hits):.0f} likes")
