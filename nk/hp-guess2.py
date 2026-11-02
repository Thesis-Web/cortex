#!/usr/bin/env python3
# hp-guess2.py: an index on the guesser's corpus by word (typed as a line through mother), then the guesser's measure before and after, read-only
import socket, json, time
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): r = ask("q " + sql); return r.get("rows", r)
t = time.time(); r = ask("type main BUILD CREATE INDEX IF NOT EXISTS guess.corpus_word ON corpus ( word ) ; BUILD"); print(f"index line: run {r['run']}, {r['runs']} runs, {r['seconds']:.2f} s; reply:", [o for o in r['out'] if o[2] == 'reply'])
OLD = "SELECT g.word, printf('%.2f', g.c * 1.0 / t.n) FROM (SELECT word, count(*) AS c FROM guess.corpus WHERE line IN (SELECT line FROM guess.corpus WHERE word = '{w}') AND word <> '{w}' AND word <> ' ' AND length(word) > 1 GROUP BY word ORDER BY c DESC, word LIMIT 3) g, (SELECT count(DISTINCT line) AS n FROM guess.corpus WHERE word = '{w}') t"
NEW = "SELECT g.word, printf('%.2f', g.c * 1.0 / t.n), printf('%.3f', g.c * 1.0 * g.c / (t.n * (SELECT count(*) FROM guess.corpus x WHERE x.word = g.word))) AS score FROM (SELECT word, count(*) AS c FROM guess.corpus WHERE line IN (SELECT line FROM guess.corpus WHERE word = '{w}') AND word <> '{w}' AND word GLOB '[A-Za-z]*' AND length(word) > 1 GROUP BY word) g, (SELECT count(DISTINCT line) AS n FROM guess.corpus WHERE word = '{w}') t ORDER BY score DESC, g.word LIMIT 3"
for w in ['senseid', 'keyword_label', 'lang_name', 'OCLC', 'Proto', 'whoever', 'astir', 'Webster']:
    t = time.time(); a = q(OLD.format(w=w)); b = q(NEW.format(w=w)); print(f"{w:14s} before: {a}   after: {b}   ({time.time() - t:.2f} s)")
print("corpus lines:", q("SELECT count(DISTINCT line) FROM guess.corpus")[0][0], "pairs:", q("SELECT count(*) FROM guess.corpus")[0][0])
