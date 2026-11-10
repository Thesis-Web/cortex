-- judge-jev-retract.sql (2026-11-10, jev C8): cortex jev retract in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- Removing a row revises only the answers that depend on it (reason-maintenance.txt:3; logic-belief-revision.txt:803): retract <row> marks the row retracted
-- (cx.judge_jevret; every later ask leaves it out), finds the ids whose newest answer lists it among its reasons (the record, cx.judge_jevans), and asks each again
-- from the record (the stored state, never the file) without the retracted rows: a request of verb ask, its answer and reasons recorded as the id's newest;
-- one line revised <id> noul=<before> -> noul=<after> each, no line for any other id. retract <row> --undo: the row is restored, and the answers its last retract
-- revised (still the newest of their ids) are their answers before again: restored <id> noul=<revised> -> noul=<before>. Lay: python3 work/jev/lay.py retract
-- ;; rule 501 the row's mark: retracted (1) or restored (--undo, 0)
INSERT OR REPLACE INTO cx.judge_jevret (rid, on_, ask, ts)
SELECT json_extract(qs, '$[0]'), CASE WHEN json_extract(qs, '$[1]') = '--undo' THEN 0 ELSE 1 END, id, ts FROM cx.judge_jevask WHERE id = ?1 AND json_type(qs, '$[0]') = 'text'
-- ;; rule 502 the ids whose newest answer lists the row among its reasons, noted before they are revised
INSERT INTO cx.judge_jevrev (ret, qid, old, new)
SELECT ?1, c.qid, c.ask, NULL FROM cx.judge_jevask r, cx.judge_jevcur c JOIN cx.judge_jevans a ON a.ask = c.ask AND a.qid = c.qid
WHERE r.id = ?1 AND json_extract(r.qs, '$[1]') IS NULL AND EXISTS (SELECT 1 FROM json_each(a.why) w WHERE json_extract(w.value, '$.id') = json_extract(r.qs, '$[0]'))
-- ;; rule 503 each asked again from the record without the retracted rows: a request of verb ask (the stored state, the question, the file's path for path:line), its pipeline run now
INSERT INTO cx.judge_jevask (verb, state, qs, ts, leave, path)
SELECT 'ask', o.state, json_array(v.qid || ':' || a.q), r.ts, o.leave, o.path FROM cx.judge_jevrev v JOIN cx.judge_jevask o ON o.id = v.old
  JOIN cx.judge_jevans a ON a.ask = v.old AND a.qid = v.qid JOIN cx.judge_jevask r ON r.id = ?1 WHERE v.ret = ?1 ORDER BY v.qid
-- ;; rule 504 the revised answer of each id
UPDATE cx.judge_jevrev SET new = (SELECT c.ask FROM cx.judge_jevcur c WHERE c.qid = judge_jevrev.qid) WHERE ret = ?1
-- ;; rule 505 one line a revised id: revised <id> noul=<before> -> noul=<after>
INSERT INTO cx.judge_jevout (ask, qi, line)
SELECT ?1, row_number() OVER (ORDER BY v.qid), CASE WHEN v.new IS NOT NULL AND v.new <> v.old AND an.noul IS NOT NULL THEN 'revised ' || v.qid || ' noul=' || ao.noul || ' -> noul=' || an.noul
  ELSE v.qid || ' not revised: the judge brain wrote no answer for it' END
FROM cx.judge_jevrev v JOIN cx.judge_jevans ao ON ao.ask = v.old AND ao.qid = v.qid LEFT JOIN cx.judge_jevans an ON an.ask = v.new AND an.qid = v.qid WHERE v.ret = ?1
-- ;; rule 506 --undo: the answers the row's last retract revised, still the newest of their ids: restored <id> noul=<revised> -> noul=<before>
INSERT INTO cx.judge_jevout (ask, qi, line)
WITH r AS (SELECT json_extract(qs, '$[0]') AS rid FROM cx.judge_jevask WHERE id = ?1 AND json_extract(qs, '$[1]') = '--undo'),
lt AS (SELECT max(x.id) AS ret FROM cx.judge_jevask x, r WHERE x.verb = 'retract' AND x.id < ?1 AND json_extract(x.qs, '$[0]') = r.rid AND json_extract(x.qs, '$[1]') IS NULL),
v AS (SELECT v.* FROM cx.judge_jevrev v, lt WHERE v.ret = lt.ret AND v.new IS NOT NULL AND v.new <> v.old AND EXISTS (SELECT 1 FROM cx.judge_jevcur c WHERE c.qid = v.qid AND c.ask = v.new))
SELECT ?1, row_number() OVER (ORDER BY v.qid), 'restored ' || v.qid || ' noul=' || an.noul || ' -> noul=' || ao.noul
FROM v JOIN cx.judge_jevans ao ON ao.ask = v.old AND ao.qid = v.qid JOIN cx.judge_jevans an ON an.ask = v.new AND an.qid = v.qid
-- ;; rule 507 --undo: those ids' newest answers are their answers before
INSERT OR REPLACE INTO cx.judge_jevcur (qid, ask, ts)
WITH r AS (SELECT json_extract(qs, '$[0]') AS rid FROM cx.judge_jevask WHERE id = ?1 AND json_extract(qs, '$[1]') = '--undo'),
lt AS (SELECT max(x.id) AS ret FROM cx.judge_jevask x, r WHERE x.verb = 'retract' AND x.id < ?1 AND json_extract(x.qs, '$[0]') = r.rid AND json_extract(x.qs, '$[1]') IS NULL),
v AS (SELECT v.* FROM cx.judge_jevrev v, lt WHERE v.ret = lt.ret AND v.new IS NOT NULL AND v.new <> v.old AND EXISTS (SELECT 1 FROM cx.judge_jevcur c WHERE c.qid = v.qid AND c.ask = v.new))
SELECT v.qid, v.old, (SELECT ts FROM cx.judge_jevask WHERE id = ?1) FROM v
