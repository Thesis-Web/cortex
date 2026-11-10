-- ;; rule 12 a request answered by its child: the child's answers as this request's lines <id> noul=<p>, its errors once, its rules' failures
INSERT INTO cx.judge_jevout (ask, qi, p, line, err)
WITH ch AS (SELECT id FROM cx.judge_jevask WHERE parent = ?1)
SELECT ?1, o.qi, o.p, CASE WHEN o.err IS NULL THEN q.qid || ' noul=' || substr(o.line, 3) END, o.err
FROM ch JOIN cx.judge_jevout o ON o.ask = ch.id LEFT JOIN cx.judge_jevq q ON q.ask = ?1 AND q.qi = o.qi
WHERE (o.err IS NULL AND q.qid IS NOT NULL) OR (o.err IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout p WHERE p.ask = ?1 AND p.err = o.err))
UNION ALL
SELECT ?1, -990, NULL, NULL, printf('the clauses'' worlds (request %d), rule %d: %s', ch.id, s.rule, s.said) FROM ch JOIN cx.judge_jevsaid s ON s.ask = ch.id WHERE s.said LIKE 'error%'
-- ;; rule 13 the reasons of each answer (jev C8): for every row of the state that can matter (p > 0, an opinion with trust > 0), the same request without that row, its pipeline run now (a request with no reasons of its own)
INSERT INTO cx.judge_jevask (verb, state, qs, ts, leave, path, nowhy, whyof, whyrow)
WITH me AS MATERIALIZED (SELECT * FROM cx.judge_jevask WHERE id = ?1 AND coalesce(nowhy, 0) = 0 AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
cand AS MATERIALIZED (SELECT rid, min(k) AS k FROM (
    SELECT rid, k FROM cx.judge_jevfact WHERE ask = ?1 AND k >= 0 AND err IS NULL AND rid IS NOT NULL AND p > 0
    UNION ALL SELECT c.rid, c.k FROM cx.judge_jevask ch JOIN cx.judge_jevclause c ON c.ask = ch.id
      WHERE ch.parent = ?1 AND c.k >= 0 AND c.k < 1000000 AND c.err IS NULL AND c.rid IS NOT NULL AND (c.p > 0 OR (c.p IS NULL AND c.ot > 0))) GROUP BY rid)
SELECT 'ask', me.state, me.qs, me.ts, json_insert(coalesce(me.leave, '[]'), '$[#]', cand.rid), me.path, 1, ?1, cand.rid FROM me, cand ORDER BY cand.k
-- ;; rule 14 the record (jev C8): each answer and its reasons in one row of cx.judge_jevans, the reasons the rows whose leaving out changes its line, each with its path:line (a text state: the file and the line; a JSON row: its path, line, source)
INSERT OR REPLACE INTO cx.judge_jevans (ask, qid, q, line, noul, why, ts)
WITH RECURSIVE
me AS MATERIALIZED (SELECT * FROM cx.judge_jevask WHERE id = ?1 AND coalesce(nowhy, 0) = 0 AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
ln AS (SELECT o.qi, o.line FROM cx.judge_jevout o JOIN me WHERE o.ask = ?1 AND o.err IS NULL AND o.line IS NOT NULL),
sub AS MATERIALIZED (SELECT s.id, s.whyrow FROM cx.judge_jevask s JOIN me WHERE s.whyof = ?1),
chg AS (SELECT ln.qi, sub.whyrow AS rid FROM ln JOIN sub WHERE NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = sub.id AND o.qi = ln.qi AND o.err IS NULL AND o.line = ln.line)),
sk AS (SELECT coalesce(state, '') AS s, path, CASE WHEN NOT json_valid(coalesce(state, '')) THEN 'text'
    WHEN json_type(state) = 'object' AND EXISTS (SELECT 1 FROM json_each(me.state)) AND NOT EXISTS (SELECT 1 FROM json_each(me.state) e WHERE e.type NOT IN ('integer', 'real')) THEN 'dict'
    WHEN json_type(state) = 'array' THEN '$' WHEN json_type(state) = 'object' AND json_type(state, '$.rows') = 'array' THEN '$.rows'
    WHEN json_type(state) = 'object' AND json_type(state, '$.rows') IS NULL AND json_type(state, '$.clauses') = 'array' THEN '$.clauses' ELSE 'other' END AS kind FROM me),
tx(n, rest, line) AS (SELECT 0, s || char(10), NULL FROM sk WHERE kind = 'text'
  UNION ALL SELECT n + 1, substr(rest, instr(rest, char(10)) + 1), substr(rest, 1, instr(rest, char(10)) - 1) FROM tx WHERE rest <> ''),
tl AS (SELECT n AS lineno, trim(replace(CASE WHEN instr(line, '%') > 0 THEN substr(line, 1, instr(line, '%') - 1) ELSE line END, char(13), ''), ' ' || char(9)) AS cl FROM tx WHERE line IS NOT NULL),
meta AS (SELECT 'r' || lineno AS rid, (SELECT path FROM sk) AS path, lineno AS line, NULL AS source, lineno AS ord FROM tl WHERE cl <> ''
  UNION ALL
  SELECT coalesce(CASE WHEN e.type = 'object' AND json_type(e.value, '$.id') IS NOT NULL AND json_type(e.value, '$.id') <> 'null' THEN CAST(json_extract(e.value, '$.id') AS TEXT) END, 'r' || (CAST(e.key AS INTEGER) + 1)),
    CASE WHEN e.type = 'object' THEN json_extract(e.value, '$.path') END, CASE WHEN e.type = 'object' THEN json_extract(e.value, '$.line') END,
    CASE WHEN e.type = 'object' THEN json_extract(e.value, '$.source') END, CAST(e.key AS INTEGER)
  FROM sk, json_each(CASE WHEN sk.kind IN ('$', '$.rows', '$.clauses') THEN sk.s ELSE '[]' END, CASE WHEN sk.kind IN ('$.rows', '$.clauses') THEN sk.kind ELSE '$' END) e WHERE sk.kind IN ('$', '$.rows', '$.clauses')
  UNION ALL
  SELECT 'r' || row_number() OVER (), NULL, NULL, NULL, row_number() OVER () FROM sk, json_each(CASE WHEN sk.kind = 'dict' THEN sk.s ELSE '{}' END) e WHERE sk.kind = 'dict')
SELECT ?1, q.qid, q.form, ln.line, substr(ln.line, instr(ln.line, ' noul=') + 6),
  coalesce((SELECT json_group_array(json_object('id', m.rid, 'path', m.path, 'line', m.line, 'source', m.source) ORDER BY m.ord) FROM chg JOIN meta m ON m.rid = chg.rid WHERE chg.qi = ln.qi), '[]'), me.ts
FROM ln JOIN cx.judge_jevq q ON q.ask = ?1 AND q.qi = ln.qi JOIN me
-- ;; rule 15 the newest answer of each id is this request's
INSERT OR REPLACE INTO cx.judge_jevcur (qid, ask, ts) SELECT qid, ask, ts FROM cx.judge_jevans WHERE ask = ?1
