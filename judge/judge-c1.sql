-- judge-c1.sql (2026-11-06, judge C1): the judge's brain in the cortex db behind the mother. The owner, 11-06 14:46: "you are operating something with py that
-- needs sql and boolean level code ... you would be writing code into the judges brain". The rules are rows of sql; a request row fires them through the mother,
-- which runs each on the kernel's own connection where the brain's runs and gates are served; every neuron of a line is kept (the owner, 11-05 18:21).
CREATE TABLE IF NOT EXISTS judge_ask (id INTEGER PRIMARY KEY, run INTEGER NOT NULL, name TEXT NOT NULL, n INTEGER NOT NULL, ts INTEGER);
CREATE TABLE IF NOT EXISTS judge_rule (id INTEGER PRIMARY KEY, name TEXT NOT NULL, sql TEXT NOT NULL, said TEXT, said_ask INTEGER);
CREATE TABLE IF NOT EXISTS judge_cell (run INTEGER NOT NULL, name TEXT NOT NULL, n INTEGER NOT NULL, expected INTEGER, neurons INTEGER, exp_neurons INTEGER, shared INTEGER, out_of_line INTEGER, ts INTEGER, PRIMARY KEY (run, name, n));
CREATE TABLE IF NOT EXISTS judge_verdict (run INTEGER NOT NULL, name TEXT NOT NULL, n INTEGER NOT NULL, kind TEXT, rule TEXT, ts INTEGER, PRIMARY KEY (run, name, n));
DROP TRIGGER IF EXISTS judge_go;
CREATE TRIGGER judge_go AFTER INSERT ON judge_ask BEGIN
  UPDATE judge_rule SET said = mother(sql, NEW.run, NEW.name, NEW.n), said_ask = NEW.id;
END;
INSERT OR REPLACE INTO judge_rule (id, name, sql) VALUES (1, 'the shape against the expected, by gate', '
INSERT OR REPLACE INTO cx.judge_cell (run, name, n, expected, neurons, exp_neurons, shared, out_of_line, ts)
WITH k AS (SELECT (SELECT gate FROM main.label WHERE symbol = '':'') AS colon, (SELECT gate FROM main.label WHERE symbol = '' '') AS sp),
e AS (SELECT run AS r FROM main.cx WHERE kind = ''expected'' AND name = ?2 AND n = ?3),
c AS (SELECT s.pos, s.gate FROM main.seq s, k WHERE s.run = ?1 AND s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q, k WHERE q.run = ?1 AND q.gate = k.colon)),
x AS (SELECT s.pos, s.gate FROM main.seq s, k WHERE s.run = (SELECT r FROM e) AND s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q, k WHERE q.run = (SELECT r FROM e) AND q.gate = k.colon))
SELECT ?1, ?2, ?3, (SELECT r FROM e), (SELECT count(*) FROM c), (SELECT count(*) FROM x),
  (SELECT count(DISTINCT gate) FROM c WHERE gate IN (SELECT gate FROM x)), (SELECT count(DISTINCT gate) FROM c WHERE gate NOT IN (SELECT gate FROM x)), CAST(strftime(''%s'', ''now'') AS INTEGER)');
