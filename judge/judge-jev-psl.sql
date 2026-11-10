-- judge-jev-psl.sql (2026-11-10, jev C6 part b): cortex jev psl in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- Soft truth values in [0,1] under hinge-loss potentials (bach-2017-hinge-loss-mrf-psl.txt:134, :162, :172, :180): the clauses read in Lukasiewicz logic, a rule
-- <weight> <literal> and ... => <literal> or ... (or <literal> or ...; a literal an atom or not an atom) has the distance to satisfaction max(0, l(y)),
-- l = the body's truths summed - (body literals - 1) - the head's truths summed (not x is 1 - x); the state gives every atom a truth value but the query, the
-- one free atom y; truth = the y in [0,1] that minimizes the weighted total sum w_j max(0, l_j(y)): the total is linear between its breakpoints, so its minimum is at
-- 0, 1 or a breakpoint -c_j / a_j, all of them weighed (the smallest y of the least total). Rules ground as mln. Lay: python3 work/jev/lay.py psl (after ask, problog, mln).
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevlin (ask INTEGER NOT NULL, rq INTEGER NOT NULL, g INTEGER NOT NULL, w REAL, a REAL, c REAL, PRIMARY KEY (ask, rq, g))
-- ;; rule 301 the query as typed: the ask's rule 1, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 1 AND verb = 'ask'
-- ;; rule 302 a query that is not <id>:<formula>: the ask's rule 2, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 2 AND verb = 'ask'
-- ;; rule 303 the state's atoms and truth values (p::atom. or JSON, as the clauses of problog): problog's rule 103, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 103 AND verb = 'problog'
-- ;; rule 304 the state's errors: problog's rule 104, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 104 AND verb = 'problog'
-- ;; rule 305 the rules: mln's rule 205, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 205 AND verb = 'mln'
-- ;; rule 306 the rules' errors: mln's rule 206, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 206 AND verb = 'mln'
-- ;; rule 307 each rule's formula as a question of its own: mln's rule 207, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 207 AND verb = 'mln'
-- ;; rule 308 the tokens: the ask's rule 5, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 5 AND verb = 'ask'
-- ;; rule 309 a query or a rule that cannot be read; a query that names a variable: mln's rule 209, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 209 AND verb = 'mln'
-- ;; rule 310 the rules' templates: mln's rule 210, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 210 AND verb = 'mln'
-- ;; rule 311 the groundings are bounded: mln's rule 211, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 211 AND verb = 'mln'
-- ;; rule 312 the groundings: mln's rule 212, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 212 AND verb = 'mln'
-- ;; rule 313 the state is atoms with truth values: a row with a body, an atom given twice; the query is the one free atom: one atom, no truth value in the state
INSERT INTO cx.judge_jevout (ask, qi, err)
WITH qt AS (SELECT q.qi, q.qid, q.form, (SELECT count(*) FROM cx.judge_jevtok t WHERE t.ask = ?1 AND t.qi = q.qi) AS n,
    (SELECT t.a FROM cx.judge_jevtok t WHERE t.ask = ?1 AND t.qi = q.qi AND t.t = 'A' ORDER BY t.k LIMIT 1) AS a
  FROM cx.judge_jevq q WHERE q.ask = ?1 AND q.qi >= 0 AND q.form IS NOT NULL AND q.form <> '')
SELECT ?1, -1, printf('row %s has a body (%s); a psl state is atoms with truth values in [0,1]', rid, body) FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL AND body <> '[]'
UNION ALL SELECT ?1, -1, printf('the atom %s has %d truth values in the state', head, count(*)) FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL GROUP BY head HAVING count(*) > 1
UNION ALL SELECT ?1, qi, printf('question %s: the query of psl is the one free atom, not %s', qid, json_quote(form)) FROM qt WHERE n <> 1 OR a IS NULL
UNION ALL SELECT ?1, qt.qi, printf('question %s: %s is the free atom, but the state gives it a truth value', qt.qid, qt.a) FROM qt WHERE qt.n = 1 AND qt.a IS NOT NULL
  AND EXISTS (SELECT 1 FROM cx.judge_jevclause c WHERE c.ask = ?1 AND c.k >= 0 AND c.err IS NULL AND c.head = qt.a)
-- ;; rule 314 a rule is a clause: <literal> and ... => <literal> or ..., or <literal> or ...; a literal is an atom or not an atom
INSERT INTO cx.judge_jevout (ask, qi, err)
WITH sh AS (SELECT t.qi, group_concat(CASE t.t WHEN 'A' THEN 'a' WHEN '!' THEN 'n' WHEN '&' THEN '&' WHEN '|' THEN '|' WHEN '=>' THEN '>' ELSE 'x' END, '' ORDER BY t.k) AS s
  FROM cx.judge_jevtok t WHERE t.ask = ?1 AND t.qi <= -1000 GROUP BY t.qi),
s2 AS (SELECT qi, replace(s, 'na', 'a') AS s, instr(replace(s, 'na', 'a'), '>') AS gt FROM sh)
SELECT ?1, s2.qi, printf('%s: a psl rule is a clause, <literal> and ... => <literal> or ..., or <literal> or ... (a literal an atom or not an atom), not %s', q.qid, json_quote(q.form))
FROM s2 JOIN cx.judge_jevq q ON q.ask = ?1 AND q.qi = s2.qi
WHERE NOT (CASE WHEN s2.gt > 0 THEN s2.gt > 1 AND s2.gt < length(s2.s) AND replace(substr(s2.s, 1, s2.gt - 1) || '&', 'a&', '') = '' AND replace(substr(s2.s, s2.gt + 1) || '|', 'a|', '') = ''
               ELSE replace(s2.s || '|', 'a|', '') = '' END)
-- ;; rule 315 every ground atom of a rule but the query has a truth value in the state; only the query is free
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT DISTINCT ?1, -997, printf('the atom %s of rule %d has no truth value in the state; only the query is free', gr.atom, -1000 - gr.qi + 1)
FROM cx.judge_jevgr gr WHERE gr.ask = ?1
  AND gr.atom NOT IN (SELECT head FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL)
  AND gr.atom NOT IN (SELECT a FROM cx.judge_jevtok WHERE ask = ?1 AND qi >= 0 AND t = 'A' AND a IS NOT NULL)
-- ;; rule 316 each ground rule's linear form l(y) = a y + c: body literals added, head literals taken away, minus (body literals - 1); a literal's truth y, 1 - y, v or 1 - v
INSERT INTO cx.judge_jevlin (ask, rq, g, w, a, c)
WITH ok AS (SELECT 1 AS z WHERE NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
qa AS (SELECT a AS atom FROM cx.judge_jevtok WHERE ask = ?1 AND qi >= 0 AND t = 'A' AND a IS NOT NULL ORDER BY qi, k LIMIT 1),
sv AS (SELECT head AS atom, p AS v FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL),
tk AS (SELECT t.qi, t.k, t.t, t.a FROM cx.judge_jevtok t WHERE t.ask = ?1 AND t.qi <= -1000),
gt AS (SELECT qi, min(k) AS k FROM tk WHERE t = '=>' GROUP BY qi),
li AS (SELECT tk.qi, tk.k, CASE WHEN gt.k IS NOT NULL AND tk.k < gt.k THEN 1 ELSE -1 END AS sg,
    EXISTS (SELECT 1 FROM tk t2 WHERE t2.qi = tk.qi AND t2.k = tk.k - 1 AND t2.t = '!') AS neg, tp.t AS tt
  FROM tk LEFT JOIN gt ON gt.qi = tk.qi JOIN cx.judge_jevtp tp ON tp.ask = ?1 AND tp.qi = tk.qi AND tp.atom = tk.a WHERE tk.t = 'A'),
nb AS (SELECT qi, sum(sg = 1) AS m FROM li GROUP BY qi),
rl AS (SELECT -1000 - i AS rq, w FROM cx.judge_jevrl WHERE ask = ?1 AND i >= 0 AND err IS NULL AND w <> 0),
gl AS (SELECT li.qi AS rq, gr.g, li.sg, li.neg, gr.atom = (SELECT atom FROM qa) AS fr, sv.v
  FROM li JOIN rl ON rl.rq = li.qi JOIN cx.judge_jevgr gr ON gr.ask = ?1 AND gr.qi = li.qi AND gr.t = li.tt LEFT JOIN sv ON sv.atom = gr.atom)
SELECT ?1, gl.rq, gl.g, rl.w,
  total(gl.sg * CASE WHEN gl.fr THEN CASE WHEN gl.neg THEN -1 ELSE 1 END ELSE 0 END),
  total(gl.sg * CASE WHEN gl.fr THEN CASE WHEN gl.neg THEN 1 ELSE 0 END WHEN gl.neg THEN 1.0 - gl.v ELSE gl.v END) - (nb.m - 1)
FROM gl JOIN rl ON rl.rq = gl.rq JOIN nb ON nb.qi = gl.rq JOIN ok GROUP BY gl.rq, gl.g
-- ;; rule 317 the answer: the weighted total at 0, at 1 and at every breakpoint in between; truth = the y of the least total (the smallest such y)
INSERT INTO cx.judge_jevout (ask, qi, p, line)
WITH ok AS (SELECT q.qi FROM cx.judge_jevq q WHERE q.ask = ?1 AND q.qi >= 0 AND q.form IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
ln AS MATERIALIZED (SELECT w, a, c FROM cx.judge_jevlin WHERE ask = ?1),
cd AS (SELECT 0.0 AS y UNION SELECT 1.0 UNION SELECT -c / a FROM ln WHERE a <> 0 AND -c / a > 0 AND -c / a < 1),
fy AS (SELECT cd.y, (SELECT total(ln.w * max(0.0, ln.a * cd.y + ln.c)) FROM ln) AS f FROM cd),
best AS (SELECT y FROM fy ORDER BY f, y LIMIT 1),
fs AS (SELECT ok.qi, best.y, rtrim(printf('%.12f', min(1.0, max(0.0, best.y))), '0') AS s FROM ok, best)
SELECT ?1, qi, y, 'truth=' || CASE WHEN substr(s, -1) = '.' THEN s || '0' ELSE s END FROM fs
