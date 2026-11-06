-- judge-c2.sql (2026-11-06, judge C2): the cells as boolean sql, two more rules. A value is an island of digit neurons (a period between two digits stays in it)
-- whose word starts with it (392g, 3.14; c28 is a name); held = a print of this checkpoint older than the claim holds the same value. New = the project held
-- no line with that gate before this claim (its gate index). Common = a gate in more than a fifth of the project's lines, measured from the record, not a word list.
ALTER TABLE judge_cell ADD COLUMN values_n INTEGER; ALTER TABLE judge_cell ADD COLUMN values_held INTEGER; ALTER TABLE judge_cell ADD COLUMN values_in_expected INTEGER; ALTER TABLE judge_cell ADD COLUMN values_out TEXT; ALTER TABLE judge_cell ADD COLUMN prints INTEGER;
ALTER TABLE judge_cell ADD COLUMN new_gates INTEGER; ALTER TABLE judge_cell ADD COLUMN same_as INTEGER; ALTER TABLE judge_cell ADD COLUMN lines INTEGER; ALTER TABLE judge_cell ADD COLUMN content INTEGER; ALTER TABLE judge_cell ADD COLUMN shared_content INTEGER; ALTER TABLE judge_cell ADD COLUMN shared_project INTEGER;
INSERT OR REPLACE INTO judge_rule (id, name, sql) VALUES (2, 'values, and the prints that hold them', '
UPDATE cx.judge_cell SET (values_n, values_held, values_in_expected, values_out, prints) = (
WITH k AS (SELECT (SELECT gate FROM main.label WHERE symbol = '':'') AS colon),
rr AS (SELECT DISTINCT CAST(json_extract(l.value, ''$.run'') AS INTEGER) AS r FROM main.cx x, json_each(x.value) c, json_each(c.value, ''$.lines'') l WHERE x.kind = ''receipts'' AND x.name = ?2 AND x.n = ?3),
src AS (SELECT ?1 AS r, 0 AS who UNION SELECT r, 1 FROM rr WHERE r < ?1 UNION SELECT run, 2 FROM main.cx WHERE kind = ''expected'' AND name = ?2 AND n = ?3),
cp AS (SELECT src.r, src.who, (SELECT min(q.pos) FROM main.seq q, k WHERE q.run = src.r AND q.gate = k.colon) AS c0 FROM src),
p AS MATERIALIZED (SELECT cp.who, s.run, s.pos, l.symbol FROM cp JOIN main.seq s ON s.run = cp.r JOIN main.label l ON l.gate = s.gate WHERE s.pos > coalesce(cp.c0, 0)),
d AS (SELECT who, run, pos, symbol, lag(symbol) OVER w AS prev, lead(symbol) OVER w AS nxt FROM p WINDOW w AS (PARTITION BY run ORDER BY pos)),
dg AS MATERIALIZED (SELECT who, run, pos, symbol, prev, pos - row_number() OVER (PARTITION BY run ORDER BY pos) AS g FROM d WHERE symbol GLOB ''[0-9]'' OR (symbol = ''.'' AND prev GLOB ''[0-9]'' AND nxt GLOB ''[0-9]'')),
v AS (SELECT who, run, g, group_concat(symbol, '''' ORDER BY pos) AS val, min(pos) AS p0 FROM dg GROUP BY who, run, g),
vv AS MATERIALIZED (SELECT v.who, v.val FROM v JOIN dg ON dg.run = v.run AND dg.pos = v.p0 WHERE dg.prev IS NULL OR dg.prev = '' '' OR (length(dg.prev) = 1 AND dg.prev NOT GLOB ''[A-Za-z]''))
SELECT (SELECT count(DISTINCT val) FROM vv WHERE who = 0), (SELECT count(DISTINCT val) FROM vv WHERE who = 0 AND val IN (SELECT val FROM vv WHERE who = 1)),
  (SELECT count(DISTINCT val) FROM vv WHERE who = 0 AND val IN (SELECT val FROM vv WHERE who = 2)),
  (SELECT group_concat(val, '','') FROM (SELECT DISTINCT val FROM vv WHERE who = 0 AND val NOT IN (SELECT val FROM vv WHERE who = 1))), (SELECT count(*) FROM src WHERE who = 1)
) WHERE run = ?1 AND name = ?2 AND n = ?3');
INSERT OR REPLACE INTO judge_rule (id, name, sql) VALUES (3, 'new to the project, common in it, and the brain own repeat', '
UPDATE cx.judge_cell SET (new_gates, same_as, lines, content, shared_content, shared_project) = (
WITH k AS (SELECT (SELECT gate FROM main.label WHERE symbol = '':'') AS colon, (SELECT gate FROM main.label WHERE symbol = '' '') AS sp),
nl AS (SELECT count(*) AS lines FROM main.cx WHERE kind = ''ingest'' AND name = ?2),
c AS MATERIALIZED (SELECT DISTINCT s.gate FROM main.seq s, k WHERE s.run = ?1 AND s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q, k WHERE q.run = ?1 AND q.gate = k.colon)),
ci AS MATERIALIZED (SELECT c.gate, g.value AS gv FROM c LEFT JOIN main.cx g ON g.kind = ''gate'' AND g.name = ?2 AND g.n = c.gate),
cc AS MATERIALIZED (SELECT gate, gv, (gv IS NOT NULL AND CAST(json_extract(gv, ''$.first'') AS INTEGER) < ?1) AS before_, (coalesce(CAST(json_extract(gv, ''$.times'') AS INTEGER), 0) * 5 > (SELECT lines FROM nl)) AS common FROM ci),
pr AS (SELECT run AS r FROM main.cx WHERE kind IN (''expected'', ''checkpoint'') AND name = ?2 AND n = ?3 UNION SELECT run FROM main.cx WHERE kind = ''project'' AND name = ?2 AND n = 0),
pg AS MATERIALIZED (SELECT DISTINCT s.gate FROM pr JOIN main.seq s ON s.run = pr.r),
eg AS MATERIALIZED (SELECT DISTINCT s.gate FROM main.cx x JOIN main.seq s ON s.run = x.run WHERE x.kind = ''expected'' AND x.name = ?2 AND x.n = ?3)
SELECT (SELECT count(*) FROM cc WHERE NOT before_), (SELECT same_as FROM main.run WHERE id = ?1), (SELECT lines FROM nl), (SELECT count(*) FROM cc WHERE NOT common),
  (SELECT count(*) FROM cc WHERE NOT common AND gate IN (SELECT gate FROM eg)), (SELECT count(*) FROM cc WHERE NOT common AND gate IN (SELECT gate FROM pg))
) WHERE run = ?1 AND name = ?2 AND n = ?3');
