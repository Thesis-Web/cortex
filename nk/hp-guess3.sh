#!/bin/bash
cd ~/nk
bash run-on-hp.sh type GUESS-LINE-nk.txt
grep -E "^\| 1 \|" out/LEDGER-GUESS-LINE-nk.md | cut -c1-300
sqlite3 sources/guess.db "SELECT substr(sql, 1, 120) FROM sqlite_master WHERE name = 'work'"
# the pristine guesser for future fresh starts gets the same trigger and the index
python3 - <<'PY'
import sqlite3, re
line = [l for l in open('GUESS-LINE-nk.txt', encoding='utf-8') if l.startswith('BUILD')][0].strip()
body = line[len('BUILD '):-len(' ; BUILD')].replace('guess.work', 'work')
db = sqlite3.connect('sources-egg/guess.db'); db.executescript(body + ';'); db.execute('CREATE INDEX IF NOT EXISTS corpus_word ON corpus (word)'); db.commit(); db.close(); print('sources-egg/guess.db: the new work trigger and the index')
PY
G0=$(sqlite3 sources/guess.db "SELECT max(id) FROM guesses")
python3 hp-rounds.py 20 3 2>&1 | grep -v "^   \|^the brain\|^a few\|^nodes\|^mutual\|^asked\|^scans\|^neurons" | cut -c1-300
echo "--- the guesses made since (word -> guess, confidence, belief):"
sqlite3 sources/guess.db "SELECT word, guess, printf('%.2f', confidence), printf('%.2f', belief) FROM guesses WHERE id > $G0 ORDER BY id" | head -30
echo "--- how many of the brain's own defines ended with a definition from a source, from the guesser, or still empty:"
python3 - <<'PY'
import socket, json
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql)["rows"]
print(q("SELECT CASE WHEN s.state = 0 THEN 'empty' ELSE coalesce((SELECT symbol FROM label WHERE gate = (SELECT arrival FROM run WHERE id = CAST(s.value AS INTEGER))), '?') END AS filled_from, count(*) FROM third t JOIN run_sheet s ON s.run = t.run AND s.cell = 24 WHERE t.run IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'define')) GROUP BY 1 ORDER BY 2 DESC"))
print("words with a definition:", q("SELECT count(DISTINCT gate) FROM node")[0][0], "| relationship rows:", q("SELECT count(*) FROM rel")[0][0], "| mutual like pairs:", q("SELECT count(*) FROM rel a JOIN rel b ON a.gate = b.other AND a.other = b.gate AND a.gate < b.gate")[0][0])
PY
