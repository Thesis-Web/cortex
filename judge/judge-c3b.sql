-- judge-c3b.sql (2026-11-06, judge C3): the judge's own memory replaces the front door's gate index (which skips small words): judge_gate counts, for every
-- project and for all (*), the lines each neuron appears in and its first run, every neuron counted. Common = a neuron in more than a tenth of all lines; a digit
-- is a value, never content. Order: a claim whose values no print can check is unsettled before invention (nothing can call it made up).
INSERT OR REPLACE INTO judge_rule (id, name, sql) VALUES (3, 'new to the project, common in all lines, and the brain own repeat', '
UPDATE cx.judge_cell SET (new_gates, same_as, lines, content, shared_content, shared_project, exp_content, new_content) = (
WITH k AS (SELECT (SELECT gate FROM main.label WHERE symbol = '':'') AS colon, (SELECT gate FROM main.label WHERE symbol = '' '') AS sp),
al AS (SELECT lines FROM cx.judge_lines WHERE name = ''*''),
c AS MATERIALIZED (SELECT DISTINCT s.gate FROM main.seq s, k WHERE s.run = ?1 AND s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q, k WHERE q.run = ?1 AND q.gate = k.colon)),
cc AS MATERIALIZED (SELECT c.gate, coalesce(pg_.first < ?1, 0) AS before_, (coalesce(ag.lines, 0) * 10 > (SELECT lines FROM al) OR l.symbol GLOB ''[0-9]'') AS common
  FROM c JOIN main.label l ON l.gate = c.gate LEFT JOIN cx.judge_gate pg_ ON pg_.name = ?2 AND pg_.gate = c.gate LEFT JOIN cx.judge_gate ag ON ag.name = ''*'' AND ag.gate = c.gate),
pr AS (SELECT run AS r FROM main.cx WHERE kind IN (''expected'', ''checkpoint'') AND name = ?2 AND n = ?3 UNION SELECT run FROM main.cx WHERE kind = ''project'' AND name = ?2 AND n = 0),
pg AS MATERIALIZED (SELECT DISTINCT s.gate FROM pr JOIN main.seq s ON s.run = pr.r, k WHERE s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q WHERE q.run = pr.r AND q.gate = k.colon)),
ex AS (SELECT run AS r FROM main.cx WHERE kind = ''expected'' AND name = ?2 AND n = ?3),
eg AS MATERIALIZED (SELECT DISTINCT s.gate FROM ex JOIN main.seq s ON s.run = ex.r, k WHERE s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q WHERE q.run = ex.r AND q.gate = k.colon)),
exg AS MATERIALIZED (SELECT eg.gate, (coalesce(ag.lines, 0) * 10 > (SELECT lines FROM al) OR l.symbol GLOB ''[0-9]'') AS common FROM eg JOIN main.label l ON l.gate = eg.gate LEFT JOIN cx.judge_gate ag ON ag.name = ''*'' AND ag.gate = eg.gate)
SELECT (SELECT count(*) FROM cc WHERE NOT before_), (SELECT same_as FROM main.run WHERE id = ?1), (SELECT lines FROM cx.judge_lines WHERE name = ?2), (SELECT count(*) FROM cc WHERE NOT common),
  (SELECT count(*) FROM cc WHERE NOT common AND gate IN (SELECT gate FROM eg)), (SELECT count(*) FROM cc WHERE NOT common AND gate IN (SELECT gate FROM pg)),
  (SELECT count(*) FROM exg WHERE NOT common), (SELECT count(*) FROM cc WHERE NOT before_ AND NOT common)
) WHERE run = ?1 AND name = ?2 AND n = ?3');
UPDATE judge_rule SET sql = replace(replace(sql,
 '       WHEN new_content >= 2 AND coalesce(values_held, 0) = 0 AND shared_content * 2 < content THEN ''invention''
       WHEN values_n > 0 AND prints = 0 THEN ''unsettled''',
 '       WHEN values_n > 0 AND prints = 0 THEN ''unsettled''
       WHEN new_content >= 2 AND coalesce(values_held, 0) = 0 AND shared_content * 2 < content THEN ''invention'''),
 '       WHEN new_content >= 2 AND coalesce(values_held, 0) = 0 AND shared_content * 2 < content THEN ''content new to the project, nothing held''
       WHEN values_n > 0 AND prints = 0 THEN ''values with no print to check''',
 '       WHEN values_n > 0 AND prints = 0 THEN ''values with no print to check''
       WHEN new_content >= 2 AND coalesce(values_held, 0) = 0 AND shared_content * 2 < content THEN ''content new to the project, nothing held''') WHERE id = 4;
