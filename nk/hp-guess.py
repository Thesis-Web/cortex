#!/usr/bin/env python3
# hp-guess.py: the guesser's measure, before and after. Before: the word that keeps the most company with the asked word (its share of the
# asked word's lines). After (mine): how exclusively the two keep company, c*c / (lines of the asked word * lines of the guess), letters only.
import socket, json
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): r = ask("q " + sql); return r.get("rows", r)
OLD = "SELECT g.word, printf('%.2f', g.c * 1.0 / t.n) FROM (SELECT word, count(*) AS c FROM guess.corpus WHERE line IN (SELECT line FROM guess.corpus WHERE word = '{w}') AND word <> '{w}' AND word <> ' ' AND length(word) > 1 GROUP BY word ORDER BY c DESC, word LIMIT 3) g, (SELECT count(DISTINCT line) AS n FROM guess.corpus WHERE word = '{w}') t"
NEW = "SELECT g.word, printf('%.2f', g.c * 1.0 / t.n), printf('%.3f', g.c * 1.0 * g.c / (t.n * (SELECT count(*) FROM guess.corpus x WHERE x.word = g.word))) AS score FROM (SELECT word, count(*) AS c FROM guess.corpus WHERE line IN (SELECT line FROM guess.corpus WHERE word = '{w}') AND word <> '{w}' AND word GLOB '[A-Za-z]*' AND length(word) > 1 GROUP BY word) g, (SELECT count(DISTINCT line) AS n FROM guess.corpus WHERE word = '{w}') t ORDER BY score DESC, g.word LIMIT 3"
for w in ['senseid', 'keyword_label', 'lang_name', 'OCLC', 'Proto', 'whoever', 'astir']:
    print(f"{w:14s} before: {q(OLD.format(w=w))}   after: {q(NEW.format(w=w))}")
print("corpus lines:", q("SELECT count(DISTINCT line) FROM guess.corpus")[0][0], "pairs:", q("SELECT count(*) FROM guess.corpus")[0][0])
