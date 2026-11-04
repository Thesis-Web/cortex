#!/usr/bin/env python3
# make_sources.py (2026-10-28): lays the eight source brains of v5 from the archived slice (tries/11 sat172.json, the real
# lines fetched 10-22/10-25), and the guessing brain. Each source is its own database: a corpus, an inbox, an outbox and its own
# trigger that does its work the moment an ask lands (10-22 rev17). The outbox's trigger hands mother the INSERT that puts each
# answer into the main brain's secondary input with the key (run, cell, who sent it, what it is about). Populated, never a timer.
# usage: python3 make_sources.py <sat172.json> <out dir> <gates: wn=7,gcide=8,...>
import json, sqlite3, sys, os
sat = json.load(open(sys.argv[1], encoding='utf-8')); out = sys.argv[2]
gates = dict(kv.split('=') for kv in sys.argv[3].split(','))
os.makedirs(out, exist_ok=True)
for name in ['wn', 'gcide', 'mw', 'mwt', 'moby', 'map', 'sqldoc', 'measured']:
    p = os.path.join(out, name + '.db')
    if os.path.exists(p): os.remove(p)
    db = sqlite3.connect(p)
    db.executescript(f"""
CREATE TABLE me (gate INTEGER NOT NULL);
INSERT INTO me VALUES ({int(gates[name])});
CREATE TABLE corpus (id INTEGER PRIMARY KEY, word TEXT NOT NULL, hw TEXT, text TEXT NOT NULL);
CREATE INDEX corpus_word ON corpus (word);
CREATE TABLE inbox (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, about INTEGER, word TEXT);
CREATE TABLE outbox (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, about INTEGER, text TEXT);
CREATE TRIGGER work AFTER INSERT ON inbox BEGIN
  INSERT INTO outbox (run, cell, about, text) SELECT NEW.run, NEW.cell, NEW.about, text FROM corpus WHERE word = NEW.word ORDER BY id;
  DELETE FROM inbox WHERE id = NEW.id;
END;
CREATE TRIGGER carry AFTER INSERT ON outbox BEGIN
  SELECT mother('INSERT INTO main.secondary (run, cell, gate, about, text) VALUES (' || NEW.run || ', ' || NEW.cell || ', ' || (SELECT gate FROM me) || ', ' || NEW.about || ', ' || quote(NEW.text) || ')');
  DELETE FROM outbox WHERE id = NEW.id;
END;""")
    rows = [(r[0], r[1], r[2]) for r in sat.get(name, []) if r[2]]
    db.executemany("INSERT INTO corpus (word, hw, text) VALUES (?, ?, ?)", rows)
    db.commit(); db.close()
    print(name, len(rows), 'lines')

# ---- the guessing brain: the simplest guesser, NOT the hand-built llm the owner described (10-28). Its corpus is rows of
# (line, word) the main brain pushes to it (the words of the return runs it has seen). Asked about a word, it answers the word that
# occurs most with it in that corpus, with a confidence = the share of lines holding the word that also hold the guess; belief is at
# most 0.5 on first use (his words 10-28). Every answer is labeled a guess by where it arrives from (its gate) and carries the number.
# Each ask is remembered with the cell and how many source returns the main brain held then (asked_returns): the sixth re-asks for an
# open cell only when more returns have come in since (10-28: "the failed choice remembered... and eliminated"; the SQL is mine).
p = os.path.join(out, 'guess.db')
if os.path.exists(p): os.remove(p)
db = sqlite3.connect(p)
db.executescript(f"""
CREATE TABLE me (gate INTEGER NOT NULL);
INSERT INTO me VALUES ({int(gates['guess'])});
CREATE TABLE corpus (line INTEGER, word TEXT, PRIMARY KEY (line, word));
CREATE TABLE inbox (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, about INTEGER, word TEXT, returns INTEGER);
CREATE TABLE outbox (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, about INTEGER, text TEXT);
CREATE TABLE guesses (id INTEGER PRIMARY KEY, word TEXT, guess TEXT, confidence REAL, belief REAL, used INTEGER NOT NULL DEFAULT 0, solved INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0, incorrect INTEGER NOT NULL DEFAULT 0, asked_by INTEGER, cell INTEGER, asked_returns INTEGER);
CREATE TRIGGER work AFTER INSERT ON inbox BEGIN
  INSERT INTO guesses (word, guess, confidence, belief, used, asked_by, cell, asked_returns)
    SELECT NEW.word, g.word, g.c * 1.0 / t.n, min(g.c * 1.0 / t.n, 0.5), 1, NEW.run, NEW.cell, NEW.returns
    FROM (SELECT word, count(*) AS c FROM corpus WHERE line IN (SELECT line FROM corpus WHERE word = NEW.word) AND word <> NEW.word AND word <> ' ' AND length(word) > 1 GROUP BY word ORDER BY c DESC, word LIMIT 1) g,
         (SELECT count(DISTINCT line) AS n FROM corpus WHERE word = NEW.word) t;
  INSERT INTO guesses (word, guess, confidence, belief, used, asked_by, cell, asked_returns) SELECT NEW.word, NULL, 0, 0, 1, NEW.run, NEW.cell, NEW.returns WHERE NOT EXISTS (SELECT 1 FROM corpus WHERE word = NEW.word);
  INSERT INTO outbox (run, cell, about, text) SELECT NEW.run, NEW.cell, NEW.about, guess || ' ' || printf('%.2f', confidence) || ' ' || printf('%.2f', belief) FROM guesses WHERE id = (SELECT max(id) FROM guesses) AND guess IS NOT NULL AND confidence > 0;
  DELETE FROM inbox WHERE id = NEW.id;
END;
CREATE TRIGGER carry AFTER INSERT ON outbox BEGIN
  SELECT mother('INSERT INTO main.secondary (run, cell, gate, about, text) VALUES (' || NEW.run || ', ' || NEW.cell || ', ' || (SELECT gate FROM me) || ', ' || NEW.about || ', ' || quote(NEW.text) || ')');
  DELETE FROM outbox WHERE id = NEW.id;
END;""")
db.commit(); db.close(); print('guess.db laid (the simplest guesser, labeled)')
