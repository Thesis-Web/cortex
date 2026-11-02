#!/usr/bin/env python3
# gen_egg6.py (2026-10-29): writes the hand-laid core of v6 as SQL, for one brain (main or sixth). From gen_egg5.py; what changed is marked v6.
# usage: python3 gen_egg6.py <schema> <out.sql>      schema = main | sixth
# Everything here is physics, hand laid once; the ledger says which step each statement is (CHAIN-v5 §). Numbers only:
# the encoder (label) is the only table that holds a symbol's spelling. The owner's words behind each piece are in CHAIN-v5.
import sys
SCHEMA = sys.argv[1]; OUT = sys.argv[2]
Q = SCHEMA + '.'            # top-level text handed to mother must name the database: unqualified names there mean main
TELL = 'sixth' if SCHEMA == 'main' else None    # which brain is told when a prompt's run ends (10-25 msg 41: output to sixth)

BORN_LINE = ('BUILD CREATE TABLE "newgate" ( shard INTEGER PRIMARY KEY , before INTEGER , trigger INTEGER , call INTEGER , spawn INTEGER , times INTEGER ) ; '
             'CREATE TABLE "newgate.node" ( id INTEGER PRIMARY KEY , source INTEGER , run INTEGER ) ; BUILD')
BIND_WORDS = 'BUILD UPDATE SET call = WHERE before IS NULL AND trigger ; BUILD'

def cut(s):
    """the encoder's cut: a run of letters and _ is one symbol; every digit, the space and every other character is one symbol"""
    out, i = [], 0
    L = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
    while i < len(s):
        if s[i] in L:
            j = i
            while j < len(s) and s[j] in L: j += 1
            out.append(s[i:j]); i = j
        else:
            out.append(s[i]); i += 1
    return out

# ---- the hand-laid symbols, in the order laid (gate 1 = heard)
symbols = ['heard', 'said', ' ', 'mother', 'sixth', 'main']
for w in ['wn', 'gcide', 'mw', 'mwt', 'moby', 'map', 'sqldoc', 'measured', 'guess']: symbols.append(w)
for w in ['born', 'hop', 'clock', 'me', 'above', 'newgate', 'reply', 'what', 'def', 'say', 'know', 'remember', 'shape']: symbols.append(w)
for t in cut(BORN_LINE) + cut(BIND_WORDS) + list('0123456789') + ['.', ':', '"', "'", '(', ')', ',', '-', '|', '*', '/', '+', '<', '>', '!', '?', '%', '_']:
    if t not in symbols: symbols.append(t)
gate = {s: i + 1 for i, s in enumerate(symbols)}
HEARD, SAID, SPACE, MOTHER, SIXTH, MAIN = gate['heard'], gate['said'], gate[' '], gate['mother'], gate['sixth'], gate['main']
BORN, BUILD, HOP = gate['born'], gate['BUILD'], gate['hop']
ME, ABOVE, NEWGATE, REPLY = gate['me'], gate['above'], gate['newgate'], gate['reply']

def lit(s): return "'" + s.replace("'", "''") + "'"
S = []
def T(x): S.append(x.strip())

# ---- the encoder, the one sequence, the clock
T("CREATE TABLE label (gate INTEGER PRIMARY KEY, symbol TEXT NOT NULL UNIQUE)")
for s in symbols: T(f"INSERT INTO label (gate, symbol) VALUES ({gate[s]}, {lit(s)})")
T("CREATE TABLE shards (n INTEGER NOT NULL)"); T("INSERT INTO shards VALUES (0)")
T("CREATE TABLE clock (n INTEGER NOT NULL)"); T("INSERT INTO clock VALUES (0)")

# ---- the three input mailboxes (the owner's outline 10-25 21:50, lines 10 to 12) and the out mailboxes (line 9)
T("CREATE TABLE input (id INTEGER PRIMARY KEY, text TEXT, run INTEGER)")
T("CREATE TABLE third (id INTEGER PRIMARY KEY, text TEXT, run INTEGER)")
T("CREATE TABLE secondary (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, gate INTEGER, about INTEGER, text TEXT, made INTEGER)")
T("CREATE TABLE out_mother (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, gate INTEGER, at INTEGER, text TEXT)")
T("CREATE TABLE out_user (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, value TEXT)")

# ---- a run, its line as numbers, its sheet (the owner's own shape, ~/neuron/v4/brain.db 10-27), its receipt, its memory, the timeline
T("CREATE TABLE run (id INTEGER PRIMARY KEY, arrival INTEGER, parent INTEGER, root INTEGER, kind INTEGER, cell INTEGER, about INTEGER, at INTEGER, moment INTEGER)")
T("CREATE INDEX run_parent ON run (parent)"); T("CREATE INDEX run_root ON run (root)")
T("CREATE TABLE seq (run INTEGER, pos INTEGER, gate INTEGER, PRIMARY KEY (run, pos))")
T("CREATE TABLE run_memory (run INTEGER PRIMARY KEY, input TEXT NOT NULL, source TEXT NOT NULL, gate INTEGER, shard INTEGER, at INTEGER)")
T("CREATE TABLE run_sheet (run INTEGER REFERENCES run_memory(run), cell INTEGER, state INTEGER NOT NULL DEFAULT 0 CHECK (state IN (0, 1)), value TEXT, PRIMARY KEY (run, cell))")
T("CREATE TABLE run_receipt (id INTEGER PRIMARY KEY, run INTEGER, pos INTEGER, gate INTEGER, shard INTEGER)")
T("CREATE INDEX receipt_run ON run_receipt (run)")
T("CREATE TABLE timeline (id INTEGER PRIMARY KEY, at INTEGER, run INTEGER, key1 INTEGER, key2 INTEGER)")
T("CREATE TABLE complete (run INTEGER PRIMARY KEY)")

# ---- the hop neuron's own table, the hit it finds, a replay, a run's end, an open BUILD, the encoder's work table
T("CREATE TABLE hop (id INTEGER PRIMARY KEY, text TEXT, p1, p2, p3, p4, p5, p6)")
T("CREATE TABLE land (id INTEGER PRIMARY KEY, run INTEGER, pos INTEGER, gate INTEGER, before INTEGER, next INTEGER, via INTEGER NOT NULL DEFAULT 0)")
T("CREATE TABLE refused (id INTEGER PRIMARY KEY, text TEXT, error TEXT)")
T("CREATE TABLE hit (id INTEGER PRIMARY KEY, run INTEGER, pos INTEGER, gate INTEGER, before INTEGER, next INTEGER, via INTEGER, had INTEGER, shard INTEGER, call INTEGER, spawn INTEGER)")
T("CREATE TABLE replay (id INTEGER PRIMARY KEY, parent INTEGER, source INTEGER, kind INTEGER)")
T("CREATE TABLE ended (id INTEGER PRIMARY KEY, run INTEGER, gate INTEGER, shard INTEGER)")
T("CREATE TABLE build_span (run INTEGER PRIMARY KEY, pos INTEGER)")

# ---- every hand-laid neuron: its DNA table (the owner's sketch 10-28: shard | before | trigger | call | spawn) and its definition node
for s in symbols:
    k = gate[s]
    T(f'CREATE TABLE "{k}" (shard INTEGER PRIMARY KEY, before INTEGER, trigger INTEGER, call INTEGER, spawn INTEGER, times INTEGER)')
    T(f'CREATE TABLE "{k}.node" (id INTEGER PRIMARY KEY, source INTEGER, run INTEGER)')
# row 0 (before NULL, trigger NULL: the neuron excited directly, not arrived at along a line) for the arrivals and born, so a call can be bound to it
n = 0
for s in ['heard', 'said', 'mother', 'sixth', 'main', 'born'] + ['wn', 'gcide', 'mw', 'mwt', 'moby', 'map', 'sqldoc', 'measured', 'guess']:
    n += 1
    T(f'INSERT INTO "{gate[s]}" (shard, before, trigger, times) VALUES ({n}, NULL, NULL, 0)')
T(f"UPDATE shards SET n = {n}")

# ---- the encoder's cut, as one query over the characters of a line (a run of letters and _ is one symbol; a digit, the space and
# every other character is one symbol); a new symbol gets the next gate number in the order it first appears; then the line is the
# run's seq as gate numbers, and the text is let go
def CUTQ(textexpr):
    return (f"WITH RECURSIVE ch(i, c) AS (SELECT 1, substr({textexpr}, 1, 1) WHERE {textexpr} <> '' UNION ALL SELECT i + 1, substr({textexpr}, i + 1, 1) FROM ch WHERE i < length({textexpr})), "
            f"m AS (SELECT i, c, (c GLOB '[A-Za-z_]') AS w FROM ch), "
            f"st AS (SELECT i, c, w, CASE WHEN w = 0 OR i = 1 OR lag(w) OVER (ORDER BY i) = 0 THEN 1 ELSE 0 END AS start FROM m), "
            f"sym AS (SELECT i, c, sum(start) OVER (ORDER BY i ROWS UNBOUNDED PRECEDING) AS n FROM st) "
            f"SELECT n, group_concat(c, '') AS s FROM (SELECT * FROM sym ORDER BY i) GROUP BY n ORDER BY n")
def CUTSQL(run_expr, textexpr):
    return (f"INSERT INTO label (symbol) SELECT s FROM ({CUTQ(textexpr)}) WHERE s NOT IN (SELECT symbol FROM label) GROUP BY s ORDER BY min(n); "
            f"INSERT INTO seq (run, pos, gate) SELECT {run_expr}, n, (SELECT gate FROM label WHERE symbol = s) FROM ({CUTQ(textexpr)}); "
            f"INSERT INTO land (run, pos, gate, before, next, via) SELECT {run_expr}, 0, (SELECT arrival FROM run WHERE id = {run_expr}), NULL, (SELECT gate FROM seq WHERE run = {run_expr} AND pos = 1), 0 WHERE EXISTS (SELECT 1 FROM seq WHERE run = {run_expr} AND pos = 1);")

# ---- a line typed at the user's prompt: a run arriving from heard; the clock neuron is hit (its reading is the run's at); the line is cut; the text is let go
def NEWRUN(arrival, parent, kind, cell='NULL', about='NULL'):
    return (f"UPDATE clock SET n = n + 1; "
            f"INSERT INTO run (arrival, parent, root, kind, cell, about, at, moment) VALUES ({arrival}, {parent}, NULL, {kind}, {cell}, {about}, (SELECT n FROM clock), strftime('%s', 'now')); "
            f"UPDATE run SET root = coalesce((SELECT root FROM run WHERE id = {parent}), id) WHERE id = (SELECT max(id) FROM run); "
            f"INSERT OR REPLACE INTO run_sheet (run, cell, state, value) VALUES ((SELECT max(id) FROM run), {ME}, 1, (SELECT max(id) FROM run)); "
            f"INSERT OR REPLACE INTO run_sheet (run, cell, state, value) SELECT (SELECT max(id) FROM run), {ABOVE}, 1, {parent} WHERE {parent} IS NOT NULL;")
T(f"""CREATE TRIGGER input_go AFTER INSERT ON input BEGIN
  {NEWRUN(HEARD, 'NULL', 0)}
  UPDATE input SET run = (SELECT max(id) FROM run), text = NULL WHERE id = NEW.id;
  {CUTSQL('(SELECT max(id) FROM run)', 'NEW.text')}
END""")
T(f"""CREATE TRIGGER third_go AFTER INSERT ON third BEGIN
  {NEWRUN(SIXTH if SCHEMA == 'main' else MAIN, 'NULL', 0)}
  UPDATE third SET run = (SELECT max(id) FROM run), text = NULL WHERE id = NEW.id;
  {CUTSQL('(SELECT max(id) FROM run)', 'NEW.text')}
END""")
# ---- a return (mother's secondary input, with the key): a run arriving from who sent it, under the run that asked, for the cell it fills
T(f"""CREATE TRIGGER secondary_go AFTER INSERT ON secondary BEGIN
  {NEWRUN('NEW.gate', 'NEW.run', 3, 'NEW.cell', 'NEW.about')}
  UPDATE secondary SET made = (SELECT max(id) FROM run), text = NULL WHERE id = NEW.id;
  {CUTSQL('(SELECT max(id) FROM run)', 'NEW.text')}
END""")

# ---- a replay: the run a DNA row's call or spawn column points at runs again, under this run, arriving from said
T(f"""CREATE TRIGGER replay_go AFTER INSERT ON replay BEGIN
  {NEWRUN(SAID, 'NEW.parent', 'NEW.kind')}
  INSERT INTO seq (run, pos, gate) SELECT (SELECT max(id) FROM run), pos, gate FROM seq WHERE run = NEW.source;
  INSERT INTO hop (text, p1, p2, p3, p4, p5, p6) SELECT 'INSERT INTO {Q}land (run, pos, gate, before, next, via) VALUES (?, ?, ?, ?, ?, ?)', (SELECT max(id) FROM run), 0, {SAID}, NULL, (SELECT gate FROM seq WHERE run = (SELECT max(id) FROM run) AND pos = 1), 0 WHERE EXISTS (SELECT 1 FROM seq WHERE run = (SELECT max(id) FROM run) AND pos = 1);
END""")

# ---- the landing (a row in land): "if chard exists hits the chard, if not writes it" (10-20 01:22). The shard key is (before, trigger); the arrival hit (pos 0)
# and the born side-hit (via 1) hit row 0 (NULL, NULL). The gate's table is named by a number the trigger does not know, so each step
# is text handed to mother. The hit it finds carries the shard and its call and spawn columns.
# v6 (10-28 evening, the owner: the space neuron with "+1000 dna lines of written sql code" is a cheat; "each of those should be neurons or dna rows
# in a neuron with the label of that word"): the shard key of a landing is the nearest symbol that is not the space on either side of it, so the
# context of a word is a row in that word's own table. The space is landed on as before (10-20 01:22: the run goes to gate space) but its key
# is (NULL, NULL): one row, counted. The walk itself (pos + 1, born inline, the end) is unchanged.
KB = f"(CASE WHEN NEW.pos = 0 OR NEW.via = 1 OR NEW.gate = {SPACE} THEN NULL ELSE coalesce((SELECT gate FROM seq WHERE run = NEW.run AND pos < NEW.pos AND gate <> {SPACE} ORDER BY pos DESC LIMIT 1), (SELECT arrival FROM run WHERE id = NEW.run)) END)"
KX = f"(CASE WHEN NEW.pos = 0 OR NEW.via = 1 OR NEW.gate = {SPACE} THEN NULL ELSE (SELECT gate FROM seq WHERE run = NEW.run AND pos > NEW.pos AND gate <> {SPACE} ORDER BY pos LIMIT 1) END)"
G = f"'{Q}\"' || NEW.gate || '\"'"
T(f"""CREATE TRIGGER land_go AFTER INSERT ON land BEGIN
  SELECT mother('INSERT INTO ' || {G} || ' (shard, before, trigger, times) SELECT n + 1, ?, ?, 0 FROM {Q}shards WHERE NOT EXISTS (SELECT 1 FROM ' || {G} || ' WHERE before IS ? AND trigger IS ?)', {KB}, {KX}, {KB}, {KX});
  SELECT mother('UPDATE {Q}shards SET n = n + 1 WHERE EXISTS (SELECT 1 FROM ' || {G} || ' WHERE shard = n + 1)');
  SELECT mother('UPDATE ' || {G} || ' SET times = times + 1 WHERE before IS ? AND trigger IS ?', {KB}, {KX});
  SELECT mother('INSERT INTO {Q}hit (run, pos, gate, before, next, via, had, shard, call, spawn) SELECT ?, ?, ?, ?, ?, ?, ?, shard, call, spawn FROM ' || {G} || ' WHERE before IS ? AND trigger IS ?', NEW.run, NEW.pos, NEW.gate, NEW.before, NEW.next, NEW.via, (CASE WHEN NEW.next IS NULL THEN 0 WHEN EXISTS (SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = CAST(NEW.next AS TEXT)) THEN 1 ELSE 0 END), {KB}, {KX});
END""")

# ---- the hit: the receipt row; BUILD (the span between two BUILD gates is decoded, holes filled from the sheet, handed to mother);
# the row's call and spawn replay; no next: the run ends; a next with no table: born inline (newgate on this run's sheet, a side-hit on born
# that calls the born run, then the landing); else the landing on the next gate
def CELL(run_expr, g):
    return f"(SELECT value FROM run_sheet WHERE run = {run_expr} AND cell = {g} AND state = 1)"
DECODE = ("(SELECT group_concat(piece, '') FROM (SELECT coalesce("
          + CELL('NEW.run', 's.gate') + ", "
          + CELL('(SELECT parent FROM run WHERE id = NEW.run)', 's.gate') + ", "
          + CELL('(SELECT parent FROM run WHERE id = (SELECT parent FROM run WHERE id = NEW.run))', 's.gate') + ", "
          + "l.symbol) AS piece FROM seq s JOIN label l ON l.gate = s.gate WHERE s.run = NEW.run AND s.pos > b.pos AND s.pos < NEW.pos ORDER BY s.pos))")
T(f"""CREATE TRIGGER hit_go AFTER INSERT ON hit BEGIN
  INSERT INTO run_receipt (run, pos, gate, shard) VALUES (NEW.run, NEW.pos, NEW.gate, NEW.shard);
  INSERT INTO hop (text, p1, p2, p3) SELECT 'INSERT INTO {Q}ended (run, gate, shard) VALUES (?, ?, ?)', NEW.run, NEW.gate, NEW.shard WHERE NEW.next IS NULL AND NEW.via = 0;
  INSERT INTO hop (text, p1, p2, p3, p4, p5, p6) SELECT 'INSERT INTO {Q}land (run, pos, gate, before, next, via) VALUES (?, ?, ?, ?, ?, ?)', NEW.run, NEW.pos + 1, NEW.next, (CASE WHEN NEW.via = 1 THEN NEW.before ELSE NEW.gate END), (SELECT gate FROM seq WHERE run = NEW.run AND pos = NEW.pos + 2), 0 WHERE NEW.next IS NOT NULL AND (NEW.via = 1 OR NEW.had = 1);
  INSERT OR REPLACE INTO run_sheet (run, cell, state, value) SELECT NEW.run, {NEWGATE}, 1, NEW.next WHERE NEW.next IS NOT NULL AND NEW.via = 0 AND NEW.had = 0;
  INSERT INTO hop (text, p1, p2, p3, p4, p5, p6) SELECT 'INSERT INTO {Q}land (run, pos, gate, before, next, via) VALUES (?, ?, ?, ?, ?, ?)', NEW.run, NEW.pos, {BORN}, NEW.gate, NEW.next, 1 WHERE NEW.next IS NOT NULL AND NEW.via = 0 AND NEW.had = 0;
  INSERT INTO hop (text, p1, p2, p3) SELECT 'INSERT INTO {Q}replay (parent, source, kind) VALUES (?, ?, ?)', NEW.run, NEW.spawn, 2 WHERE NEW.spawn IS NOT NULL;
  INSERT INTO hop (text, p1, p2, p3) SELECT 'INSERT INTO {Q}replay (parent, source, kind) VALUES (?, ?, ?)', NEW.run, NEW.call, 1 WHERE NEW.call IS NOT NULL;
  INSERT INTO build_span (run, pos) SELECT NEW.run, NEW.pos WHERE NEW.gate = {BUILD} AND NEW.via = 0 AND NOT EXISTS (SELECT 1 FROM build_span WHERE run = NEW.run);
  DELETE FROM build_span WHERE run = NEW.run AND NEW.gate = {BUILD} AND NEW.via = 0 AND NEW.pos > pos AND EXISTS (SELECT 1 FROM build_span WHERE run = NEW.run AND pos < NEW.pos);
  INSERT INTO out_mother (run, cell, gate, at, text) SELECT NEW.run, {REPLY}, {BUILD}, (SELECT at FROM run WHERE id = NEW.run), {DECODE} FROM (SELECT pos FROM (SELECT max(r.pos) AS pos FROM run_receipt r WHERE r.run = NEW.run AND r.gate = {BUILD} AND r.pos < NEW.pos)) b WHERE NEW.gate = {BUILD} AND NEW.via = 0 AND b.pos IS NOT NULL AND NOT EXISTS (SELECT 1 FROM build_span WHERE run = NEW.run);
END""")

# ---- the out mailbox to mother: she runs the text; her answer comes back as secondary input with the key (arriving from mother); the text is let go
T(f"""CREATE TRIGGER out_mother_go AFTER INSERT ON out_mother BEGIN
  INSERT INTO secondary (run, cell, gate, about, text) VALUES (NEW.run, NEW.cell, {MOTHER}, NULL, mother(NEW.text));
  UPDATE out_mother SET text = NULL WHERE id = NEW.id;
END""")

# ---- the end of a run: the shard with no remainder writes the memory (the sheet lives with it); a return fills the cell it was asked for
# and lands a row in the definition node of the gate it is about (the newborn's first memory); the memory writes the timeline and stops;
# a prompt's run that ended is told to the sixth through mother
T(f"""CREATE TRIGGER ended_go AFTER INSERT ON ended BEGIN
  INSERT INTO run_memory (run, input, source, gate, shard, at) VALUES (NEW.run, coalesce((SELECT group_concat(gate, ' ') FROM (SELECT gate FROM seq WHERE run = NEW.run ORDER BY pos)), ''), (SELECT arrival FROM run WHERE id = NEW.run), NEW.gate, NEW.shard, (SELECT at FROM run WHERE id = NEW.run));
  INSERT OR REPLACE INTO run_sheet (run, cell, state, value) SELECT parent, cell, 1, NEW.run FROM run WHERE id = NEW.run AND cell IS NOT NULL AND parent IS NOT NULL;
  SELECT mother('INSERT INTO {Q}"' || about || '.node" (source, run) VALUES (?, ?)', arrival, NEW.run) FROM run WHERE id = NEW.run AND about IS NOT NULL;
  INSERT OR IGNORE INTO complete (run) SELECT NEW.run WHERE NOT EXISTS (SELECT 1 FROM run_sheet WHERE run = NEW.run AND state = 0);
END""")
TELLSQL = (f"  SELECT mother('INSERT INTO {TELL}.third (text) VALUES (?)', 'seen : ' || NEW.run) WHERE (SELECT kind FROM run WHERE id = NEW.run) = 0;\n" if TELL else "")
T(f"""CREATE TRIGGER memory_go AFTER INSERT ON run_memory BEGIN
  INSERT INTO timeline (at, run, key1, key2) VALUES (NEW.at, NEW.run, (SELECT gate FROM seq WHERE run = NEW.run AND pos = 1), (SELECT gate FROM seq WHERE run = NEW.run ORDER BY pos DESC LIMIT 1));
{TELLSQL}END""")
# ---- a cell fills after the run ended: when no declared cell is empty the run is complete; a complete run's cells go to the user's out mailbox
T("""CREATE TRIGGER sheet_fill AFTER INSERT ON run_sheet WHEN NEW.state = 1 BEGIN
  INSERT OR IGNORE INTO complete (run) SELECT NEW.run WHERE EXISTS (SELECT 1 FROM run_memory WHERE run = NEW.run) AND NOT EXISTS (SELECT 1 FROM run_sheet WHERE run = NEW.run AND state = 0);
END""")
T("""CREATE TRIGGER complete_go AFTER INSERT ON complete BEGIN
  INSERT INTO out_user (run, cell, value) SELECT run, cell, value FROM run_sheet WHERE run = NEW.run AND (SELECT kind FROM run WHERE id = NEW.run) = 0 ORDER BY cell;
END""")

open(OUT, 'w').write(';\n'.join(S) + ';\n')
print(len(S), 'statements;', len(symbols), 'hand-laid neurons; gates:', {k: gate[k] for k in ['heard','said',' ','mother','sixth','main','born','hop','BUILD','me','above','newgate','reply','what','def','say','know','remember','shape','wn','guess']})
