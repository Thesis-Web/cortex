#!/usr/bin/env python3
# hp-pullrel.py: the brain's relationship rows, and the relationship kinds its sources' returns carry in their text (WordNet's and Wiktionary's
# bracketed pointers: syn, hypernym, hyponym, similar to, antonym, holonym, meronym, derived, related ...), read from the definition rows by key
import socket, json, re, collections
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
rel = q("SELECT gate, kind, other FROM rel")
sym = dict(q("SELECT gate, symbol FROM label"))
inv = {}
for g, s in sym.items(): inv.setdefault(s, g)
nodes = q("SELECT n.gate, n.source, n.run FROM node n WHERE n.source IN (7, (SELECT gate FROM label WHERE symbol = 'wikt'))")
print("rel rows", len(rel), "| wn + wikt definition rows", len(nodes))
tagged = collections.Counter(); out = []
for i in range(0, len(nodes), 400):
    chunk = nodes[i:i+400]
    texts = dict((r, t) for (r, t) in q("SELECT s.run, group_concat(l.symbol, '') FROM (SELECT run, pos, gate FROM seq WHERE run IN (%s) ORDER BY run, pos) s JOIN label l ON l.gate = s.gate GROUP BY s.run" % ",".join(str(r) for (_, _, r) in chunk)))
    for (g, src, run) in chunk:
        t = texts.get(run, "")
        for tag, body in re.findall(r"\[([a-z][a-z ]*?): ([^\]]*)\]", t):
            words = re.findall(r"\{([^}]*)\}", body) if "{" in body else [w.strip() for w in re.split(r"[;,|]", body)]
            for w in words:
                w = re.sub(r"\(.*?\)", "", w).strip()
                if not w or " " in w or w == sym.get(g): continue
                og = inv.get(w) or inv.get(w.lower())
                if og and og != g: out.append((g, tag, og, src)); tagged[tag] += 1
print("tags found:", tagged.most_common(16))
json.dump({"rel": rel, "tagged": out, "label": {str(k): v for k, v in sym.items()}, "defined": sorted({g for (g, _, _) in nodes})}, open("out/geo2.json", "w"))
print("tagged rows", len(out), "| defined words", len({g for (g, _, _) in nodes}))
