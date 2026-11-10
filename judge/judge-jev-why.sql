-- judge-jev-why.sql (2026-11-10, jev C8): cortex jev why in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- Reason maintenance (reason-maintenance.txt:3; logic-belief-revision.txt:803): every answer of cortex jev ask is kept with its reasons in the record (cx.judge_jevans,
-- the ask's rules 13 to 15): the rows whose leaving out changes its line, with path:line. why <id> reads the record of the id's newest answer (cx.judge_jevcur), never a
-- state file: one line <path>:<line> row=<id>[ source=<s>] a reason, in the state's order, or none: the answer <id> noul=<p> depends on no row. Lay: python3 work/jev/lay.py why
-- ;; rule 601 an id with no answer in the record
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, CAST(j.key AS INTEGER), printf('no answer under the id %s (cortex jev ask keeps each answer''s reasons)', j.value)
FROM cx.judge_jevask a, json_each(a.qs) j WHERE a.id = ?1 AND NOT EXISTS (SELECT 1 FROM cx.judge_jevcur c WHERE c.qid = j.value)
-- ;; rule 602 the reasons of each id's newest answer, from the record
INSERT INTO cx.judge_jevout (ask, qi, line)
WITH q AS (SELECT CAST(j.key AS INTEGER) AS qi, j.value AS qid FROM cx.judge_jevask a, json_each(a.qs) j WHERE a.id = ?1),
an AS (SELECT q.qi, q.qid, a.noul, a.why FROM q JOIN cx.judge_jevcur c ON c.qid = q.qid JOIN cx.judge_jevans a ON a.ask = c.ask AND a.qid = c.qid
  WHERE NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL))
SELECT ?1, an.qi * 100000 + CAST(w.key AS INTEGER), coalesce(nullif(json_extract(w.value, '$.path'), ''), nullif(json_extract(w.value, '$.source'), ''), '-') || ':' || coalesce(json_extract(w.value, '$.line'), '-')
  || ' row=' || json_extract(w.value, '$.id') || CASE WHEN coalesce(json_extract(w.value, '$.source'), '') <> '' THEN ' source=' || json_extract(w.value, '$.source') ELSE '' END
FROM an, json_each(an.why) w
UNION ALL
SELECT ?1, an.qi * 100000, printf('none: the answer %s noul=%s depends on no row', an.qid, an.noul) FROM an WHERE json_array_length(an.why) = 0
