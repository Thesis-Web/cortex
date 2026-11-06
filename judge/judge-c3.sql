-- judge-c3.sql (2026-11-06, judge C3): the verdict as boolean sql over the cells. Rule 3 now also counts the expected's content (its gates after the colon that are
-- not common in the project) and the claim's content new to the project; the shapes of the expected, checkpoint and scope are read after their colon only.
ALTER TABLE judge_cell ADD COLUMN exp_content INTEGER; ALTER TABLE judge_cell ADD COLUMN new_content INTEGER;
INSERT OR REPLACE INTO judge_rule (id, name, sql) VALUES (3, 'new to the project, common in it, and the brain own repeat', '
UPDATE cx.judge_cell SET (new_gates, same_as, lines, content, shared_content, shared_project, exp_content, new_content) = (
WITH k AS (SELECT (SELECT gate FROM main.label WHERE symbol = '':'') AS colon, (SELECT gate FROM main.label WHERE symbol = '' '') AS sp),
nl AS (SELECT count(*) AS lines FROM main.cx WHERE kind = ''ingest'' AND name = ?2),
c AS MATERIALIZED (SELECT DISTINCT s.gate FROM main.seq s, k WHERE s.run = ?1 AND s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q, k WHERE q.run = ?1 AND q.gate = k.colon)),
cc AS MATERIALIZED (SELECT c.gate, (g.value IS NOT NULL AND CAST(json_extract(g.value, ''$.first'') AS INTEGER) < ?1) AS before_, (coalesce(CAST(json_extract(g.value, ''$.times'') AS INTEGER), 0) * 5 > (SELECT lines FROM nl)) AS common FROM c LEFT JOIN main.cx g ON g.kind = ''gate'' AND g.name = ?2 AND g.n = c.gate),
pr AS (SELECT run AS r FROM main.cx WHERE kind IN (''expected'', ''checkpoint'') AND name = ?2 AND n = ?3 UNION SELECT run FROM main.cx WHERE kind = ''project'' AND name = ?2 AND n = 0),
pg AS MATERIALIZED (SELECT DISTINCT s.gate FROM pr JOIN main.seq s ON s.run = pr.r, k WHERE s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q WHERE q.run = pr.r AND q.gate = k.colon)),
ex AS (SELECT run AS r FROM main.cx WHERE kind = ''expected'' AND name = ?2 AND n = ?3),
eg AS MATERIALIZED (SELECT DISTINCT s.gate FROM ex JOIN main.seq s ON s.run = ex.r, k WHERE s.gate <> k.sp AND s.pos > (SELECT min(q.pos) FROM main.seq q WHERE q.run = ex.r AND q.gate = k.colon)),
exg AS MATERIALIZED (SELECT eg.gate, (coalesce(CAST(json_extract(g.value, ''$.times'') AS INTEGER), 0) * 5 > (SELECT lines FROM nl)) AS common FROM eg LEFT JOIN main.cx g ON g.kind = ''gate'' AND g.name = ?2 AND g.n = eg.gate)
SELECT (SELECT count(*) FROM cc WHERE NOT before_), (SELECT same_as FROM main.run WHERE id = ?1), (SELECT lines FROM nl), (SELECT count(*) FROM cc WHERE NOT common),
  (SELECT count(*) FROM cc WHERE NOT common AND gate IN (SELECT gate FROM eg)), (SELECT count(*) FROM cc WHERE NOT common AND gate IN (SELECT gate FROM pg)),
  (SELECT count(*) FROM exg WHERE NOT common), (SELECT count(*) FROM cc WHERE NOT before_ AND NOT common)
) WHERE run = ?1 AND name = ?2 AND n = ?3');
INSERT OR REPLACE INTO judge_rule (id, name, sql) VALUES (4, 'the verdict, boolean over the cells', '
INSERT OR REPLACE INTO cx.judge_verdict (run, name, n, kind, rule, ts)
SELECT run, name, n,
  CASE WHEN coalesce(same_as, 0) > 0 THEN ''dupe''
       WHEN values_n = 0 AND content > 0 AND shared_content = content THEN ''dupe''
       WHEN values_n > 0 AND values_held = values_n AND exp_content > 0 AND shared_content * 10 >= exp_content * 7 THEN ''completes''
       WHEN values_n > 0 AND prints > 0 AND values_held = 0 AND values_in_expected = 0 THEN ''hallucination''
       WHEN shared_project = 0 AND coalesce(values_held, 0) = 0 THEN ''drift''
       WHEN values_held > 0 AND shared_content > 0 THEN ''progresses''
       WHEN new_content >= 2 AND coalesce(values_held, 0) = 0 AND shared_content * 2 < content THEN ''invention''
       WHEN values_n > 0 AND prints = 0 THEN ''unsettled''
       WHEN shared_content > 0 THEN ''holds''
       ELSE ''unsettled'' END,
  CASE WHEN coalesce(same_as, 0) > 0 THEN ''the brain own repeat''
       WHEN values_n = 0 AND content > 0 AND shared_content = content THEN ''an echo of the expected, no value''
       WHEN values_n > 0 AND values_held = values_n AND exp_content > 0 AND shared_content * 10 >= exp_content * 7 THEN ''every value held by an older print, seven tenths of the expected content shared''
       WHEN values_n > 0 AND prints > 0 AND values_held = 0 AND values_in_expected = 0 THEN ''values no older print holds''
       WHEN shared_project = 0 AND coalesce(values_held, 0) = 0 THEN ''no content shared with the project''
       WHEN values_held > 0 AND shared_content > 0 THEN ''a value held by an older print, on the expected''
       WHEN new_content >= 2 AND coalesce(values_held, 0) = 0 AND shared_content * 2 < content THEN ''content new to the project, nothing held''
       WHEN values_n > 0 AND prints = 0 THEN ''values with no print to check''
       WHEN shared_content > 0 THEN ''on the expected, nothing decided''
       ELSE ''nothing decided'' END
  || printf('' | values %d held %d, content %d shared %d of %d, project %d, new %d, prints %d'', values_n, values_held, content, shared_content, exp_content, shared_project, new_content, prints),
  CAST(strftime(''%s'', ''now'') AS INTEGER)
FROM cx.judge_cell WHERE run = ?1 AND name = ?2 AND n = ?3');
