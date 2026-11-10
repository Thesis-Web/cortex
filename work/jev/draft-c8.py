# draft-c8.py (2026-11-10, jev C8): writes the C8 drafts of judge-jev-ask.sql and judge-jev-problog.sql into work/jev/draft (the judge files are not touched)
import os
os.chdir(os.path.expanduser("~/cortex"))
s = open("judge/judge-jev-ask.sql").read()
def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90]); s = s.replace(old, new)
rep("-- soft rules C6, opinions C7: refused with their checkpoint named, not built here. Pattern: judge/judge-c1.sql and judge/judge-jev.sql (rail C6).",
"""-- soft rules C6, opinions C7: refused with their checkpoint named, not built here. Pattern: judge/judge-c1.sql and judge/judge-jev.sql (rail C6).
-- jev C8 (11-10): a state that is not facts alone (ProbLog text, a clause with a body, an opinion, soft rules) is answered by a child request of verb mln (rule 0,
-- the C5 to C7 rules) whose lines rule 12 copies; every answer keeps its reasons (rules 13 to 15): for each row that can matter, the same request without that row
-- runs now (the kernel's recursive triggers), and the rows whose leaving out changes the answer's line are its reasons, with path:line, one record row
-- (cx.judge_jevans) an answer; cx.judge_jevcur holds each id's newest answer; rows retracted (cx.judge_jevret) are left out of every ask (rule -1).""")
ddl = """-- ;; ddl-add
ALTER TABLE cx.judge_jevask ADD COLUMN parent INTEGER
-- ;; ddl-add
ALTER TABLE cx.judge_jevask ADD COLUMN leave TEXT
-- ;; ddl-add
ALTER TABLE cx.judge_jevask ADD COLUMN path TEXT
-- ;; ddl-add
ALTER TABLE cx.judge_jevask ADD COLUMN nowhy INTEGER
-- ;; ddl-add
ALTER TABLE cx.judge_jevask ADD COLUMN whyof INTEGER
-- ;; ddl-add
ALTER TABLE cx.judge_jevask ADD COLUMN whyrow TEXT
-- ;; ddl
CREATE INDEX IF NOT EXISTS cx.judge_jevask_parent ON judge_jevask (parent)
-- ;; ddl
CREATE INDEX IF NOT EXISTS cx.judge_jevask_whyof ON judge_jevask (whyof)
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevans (ask INTEGER NOT NULL, qid TEXT NOT NULL, q TEXT, line TEXT, noul TEXT, why TEXT, ts INTEGER, PRIMARY KEY (ask, qid))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevcur (qid TEXT PRIMARY KEY, ask INTEGER NOT NULL, ts INTEGER)
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevret (rid TEXT PRIMARY KEY, on_ INTEGER NOT NULL, ask INTEGER, ts INTEGER)
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevrev (ret INTEGER NOT NULL, qid TEXT NOT NULL, old INTEGER, new INTEGER, PRIMARY KEY (ret, qid))
-- ;; ddl
DROP TRIGGER IF EXISTS cx.judge_jevgo"""
rep("-- ;; ddl\nDROP TRIGGER IF EXISTS cx.judge_jevgo", ddl)
rule0 = """-- ;; rule -1 the rows this request leaves out (jev C8): its own leave and every row retracted now
UPDATE cx.judge_jevask SET leave = (SELECT json_group_array(rid) FROM (SELECT value AS rid FROM json_each(coalesce((SELECT leave FROM cx.judge_jevask WHERE id = ?1), '[]'))
  UNION SELECT rid FROM cx.judge_jevret WHERE on_ = 1)) WHERE id = ?1
-- ;; rule 0 a state that is not facts alone (ProbLog text, a clause with a body, an opinion, soft rules: jev C5 to C7) is answered by the clauses' worlds: a child request of verb mln, the same state, questions and leave, its pipeline run now
INSERT INTO cx.judge_jevask (verb, state, qs, ts, parent, leave, path, nowhy)
SELECT 'mln', a.state, a.qs, a.ts, a.id, a.leave, a.path, 1 FROM cx.judge_jevask a
WHERE a.id = ?1 AND CASE WHEN NOT json_valid(coalesce(a.state, '')) THEN 1
  WHEN json_type(a.state) = 'object' AND json_type(a.state, '$.rules') = 'array' AND json_array_length(a.state, '$.rules') > 0 THEN 1
  WHEN EXISTS (SELECT 1 FROM json_each(CASE WHEN json_type(a.state) = 'array' THEN a.state WHEN json_type(a.state) = 'object' AND json_type(a.state, '$.rows') = 'array' THEN json_extract(a.state, '$.rows')
      WHEN json_type(a.state) = 'object' AND json_type(a.state, '$.rows') IS NULL AND json_type(a.state, '$.clauses') = 'array' THEN json_extract(a.state, '$.clauses') ELSE '[]' END) e
    WHERE (e.type = 'text' AND instr(e.value, ':-') > 0)
       OR (e.type = 'object' AND ((json_type(e.value, '$.clause') = 'text' AND instr(json_extract(e.value, '$.clause'), ':-') > 0)
          OR CASE json_type(e.value, '$.if') WHEN 'array' THEN json_array_length(e.value, '$.if') WHEN 'text' THEN length(json_extract(e.value, '$.if')) ELSE 0 END > 0
          OR CASE json_type(e.value, '$.body') WHEN 'array' THEN json_array_length(e.value, '$.body') WHEN 'text' THEN length(json_extract(e.value, '$.body')) ELSE 0 END > 0
          OR json_type(e.value, '$.b') IS NOT NULL OR json_type(e.value, '$.d') IS NOT NULL OR json_type(e.value, '$.u') IS NOT NULL OR json_type(e.value, '$.trust') IS NOT NULL))) THEN 1
  ELSE 0 END = 1
-- ;; rule 1 """
rep("-- ;; rule 1 ", rule0)
rep("""INSERT INTO cx.judge_jevfact (ask, k, rid, atom, p, err)
WITH a AS (SELECT state AS s FROM cx.judge_jevask WHERE id = ?1),""",
"""INSERT INTO cx.judge_jevfact (ask, k, rid, atom, p, err)
WITH a AS (SELECT state AS s FROM cx.judge_jevask WHERE id = ?1 AND NOT EXISTS (SELECT 1 FROM cx.judge_jevask c WHERE c.parent = ?1)),
lv AS (SELECT value AS rid FROM json_each(coalesce((SELECT leave FROM cx.judge_jevask WHERE id = ?1), '[]'))),""")
rep("\nFROM r5\n", "\nFROM r5 WHERE rid NOT IN (SELECT rid FROM lv)\n")
rep("\nFROM dr\n", "\nFROM dr WHERE 'r' || (k + 1) NOT IN (SELECT rid FROM lv)\n")
rep("""ok AS (SELECT x.qi, x.nu, x.rpn FROM cx.judge_jevx x WHERE x.ask = ?1 AND x.rpn IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),""",
"""ok AS (SELECT x.qi, x.nu, x.rpn FROM cx.judge_jevx x WHERE x.ask = ?1 AND x.rpn IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)
  AND NOT EXISTS (SELECT 1 FROM cx.judge_jevask c WHERE c.parent = ?1)),""")
s = s.rstrip("\n") + "\n" + open("work/jev/draft/ask-c8-tail.sql").read()
open("work/jev/draft/judge-jev-ask-c8.sql", "w").write(s); print("ask c8 draft")
p = open("judge/judge-jev-problog.sql").read()
old = "r8 AS (SELECT r.*, coalesce(bj.body, '[]') AS body, ke.what AS kwhat, ke.e AS kerr,"
assert p.count(old) == 1
p = p.replace(old, "lv AS (SELECT value AS rid FROM json_each(coalesce((SELECT leave FROM cx.judge_jevask WHERE id = ?1), '[]'))),\n" + old)
old = "  FROM r7 r LEFT JOIN ke ON ke.k = r.k LEFT JOIN bj ON bj.k = r.k),"
assert p.count(old) == 1
p = p.replace(old, "  FROM r7 r LEFT JOIN ke ON ke.k = r.k LEFT JOIN bj ON bj.k = r.k WHERE r.rid NOT IN (SELECT rid FROM lv)),")
open("work/jev/draft/judge-jev-problog-c8.sql", "w").write(p); print("problog c8 draft")
