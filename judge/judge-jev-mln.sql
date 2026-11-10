-- judge-jev-mln.sql (2026-11-10, jev C6 part a): cortex jev mln in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- Weighted soft rules on top of the C5 clauses (richardson-domingos-2006-markov-logic.txt:81): the clauses' worlds as C5 (each clause in a world with its p,
-- independently; a world's model its least model), each world's weight times exp(sum of w_i n_i(x)), n_i(x) the true groundings of rule i in the world's model;
-- p(query) = the weighted worlds where it holds over all weighted worlds. A rule is <weight> <formula> (a line of the rules file, % or # a comment; or JSON: a list
-- of "<weight> <formula>" or {"w", "rule"}, or {"rules": [...]}; a state in JSON may carry "rules" too); a capitalised argument is a variable, grounded over the
-- constants of the state, the rules and the query, every assignment (two variables may bind one constant). A weight 0 rule changes nothing and is left out.
-- With soft rules the atoms the query depends on are its whole neighbourhood (the atoms a clause or a grounding ties to it, both ways); with none, as C5.
-- Rules run by reference: the ask's 1, 2, 5, 9, 10; problog's 103, 104, 108, 109, 110, 113, 114. Lay: python3 work/jev/lay.py mln (after the ask and problog).
-- ;; ddl-add
ALTER TABLE cx.judge_jevask ADD COLUMN rules TEXT
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevrl (ask INTEGER NOT NULL, i INTEGER NOT NULL, w REAL, form TEXT, err TEXT, PRIMARY KEY (ask, i))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevtp (ask INTEGER NOT NULL, qi INTEGER NOT NULL, t INTEGER NOT NULL, atom TEXT, PRIMARY KEY (ask, qi, t))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevgr (ask INTEGER NOT NULL, qi INTEGER NOT NULL, g INTEGER NOT NULL, t INTEGER NOT NULL, atom TEXT, PRIMARY KEY (ask, qi, g, t))
-- ;; rule 201 the query as typed: the ask's rule 1, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 1 AND verb = 'ask'
-- ;; rule 202 a query that is not <id>:<formula>: the ask's rule 2, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 2 AND verb = 'ask'
-- ;; rule 203 the state's clauses: problog's rule 103, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 103 AND verb = 'problog'
-- ;; rule 204 the state's errors: problog's rule 104, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 104 AND verb = 'problog'
-- ;; rule 205 the rules: <weight> <formula> a line (% or # a comment; <weight>:: <formula> also), or JSON; then the state's own "rules"; i in that order
INSERT INTO cx.judge_jevrl (ask, i, w, form, err)
WITH RECURSIVE
a AS (SELECT coalesce(rules, '') AS s, state FROM cx.judge_jevask WHERE id = ?1),
sh AS (SELECT s, CASE WHEN NOT json_valid(s) THEN 'text' WHEN json_type(s) = 'array' THEN '$' WHEN json_type(s) = 'object' AND json_type(s, '$.rules') = 'array' THEN '$.rules' ELSE 'other' END AS kind FROM a),
ln(n, rest, line) AS (SELECT 0, s || char(10), NULL FROM sh WHERE kind = 'text'
  UNION ALL SELECT n + 1, substr(rest, instr(rest, char(10)) + 1), substr(rest, 1, instr(rest, char(10)) - 1) FROM ln WHERE rest <> ''),
l1 AS (SELECT n, replace(replace(line, char(13), ''), char(9), ' ') AS x FROM ln WHERE line IS NOT NULL),
l2 AS (SELECT n, trim(CASE WHEN instr(x, '%') > 0 AND (instr(x, '#') = 0 OR instr(x, '%') < instr(x, '#')) THEN substr(x, 1, instr(x, '%') - 1)
    WHEN instr(x, '#') > 0 THEN substr(x, 1, instr(x, '#') - 1) ELSE x END) AS x FROM l1),
it AS (SELECT n AS o, 'text' AS ty, x AS v FROM l2 WHERE x <> ''
  UNION ALL SELECT 1000000 + CAST(e.key AS INTEGER), e.type, e.value FROM sh, json_each(CASE WHEN sh.kind IN ('$', '$.rules') THEN sh.s ELSE '[]' END, CASE WHEN sh.kind = '$.rules' THEN '$.rules' ELSE '$' END) e WHERE sh.kind IN ('$', '$.rules')
  UNION ALL SELECT 2000000 + CAST(e.key AS INTEGER), e.type, e.value FROM a, json_each(CASE WHEN json_valid(a.state) AND json_type(a.state) = 'object' AND json_type(a.state, '$.rules') = 'array' THEN a.state ELSE '{"rules": []}' END, '$.rules') e),
i0 AS (SELECT row_number() OVER (ORDER BY o) - 1 AS i, ty, v FROM it),
i1 AS (SELECT i, ty, v, CASE WHEN ty = 'text' THEN trim(v) END AS x FROM i0),
i2 AS (SELECT i1.*, CASE WHEN x IS NOT NULL THEN CASE WHEN instr(x, ' ') > 0 AND (instr(x, '::') = 0 OR instr(x, ' ') < instr(x, '::')) THEN instr(x, ' ') WHEN instr(x, '::') > 0 THEN instr(x, '::') ELSE 0 END END AS sp FROM i1),
i3 AS (SELECT i2.*,
    CASE WHEN ty = 'text' THEN CASE WHEN sp > 0 THEN substr(x, 1, sp - 1) END WHEN ty = 'object' THEN CAST(coalesce(json_extract(v, '$.w'), json_extract(v, '$.weight')) AS TEXT) END AS wt,
    CASE WHEN ty = 'object' THEN coalesce(json_type(v, '$.w'), json_type(v, '$.weight')) END AS wty,
    CASE WHEN ty = 'text' THEN CASE WHEN sp > 0 THEN trim(substr(x, sp)) END WHEN ty = 'object' AND coalesce(json_type(v, '$.rule'), json_type(v, '$.formula')) = 'text' THEN coalesce(json_extract(v, '$.rule'), json_extract(v, '$.formula')) END AS f0 FROM i2),
i4 AS (SELECT i, ty, v, wty, CASE WHEN substr(wt, -2) = '::' THEN substr(wt, 1, length(wt) - 2) ELSE wt END AS wt,
    trim(CASE WHEN substr(f0, 1, 2) = '::' THEN substr(f0, 3) ELSE f0 END) AS form FROM i3),
i5 AS (SELECT i4.*, CASE WHEN substr(wt, 1, 1) = '+' THEN substr(wt, 2) ELSE wt END AS w1 FROM i4),
i6 AS (SELECT i5.*, CASE WHEN substr(w1, 1, 2) = '-.' THEN '-0.' || substr(w1, 3) WHEN substr(w1, 1, 1) = '.' THEN '0' || w1 ELSE w1 END AS wj FROM i5)
SELECT ?1, i, CASE WHEN wj IS NOT NULL AND json_valid(wj) AND json_type(wj) IN ('integer', 'real') THEN CAST(wj AS REAL) END, form, CASE
    WHEN ty NOT IN ('text', 'object') THEN printf('rule %d is neither <weight> <formula> nor {"w", "rule"}', i + 1)
    WHEN ty = 'text' AND (wt IS NULL OR form IS NULL OR form = '') THEN printf('rule %d is not <weight> <formula>: %s', i + 1, json_quote(v))
    WHEN ty = 'object' AND wty IS NULL THEN printf('rule %d has no weight', i + 1)
    WHEN wj IS NULL OR NOT json_valid(wj) OR json_type(wj) NOT IN ('integer', 'real') OR (ty = 'object' AND wty NOT IN ('integer', 'real')) THEN printf('the weight of rule %d is not a number: %s', i + 1, wt)
    WHEN form IS NULL OR form = '' THEN printf('rule %d has no formula', i + 1) END
FROM i6
UNION ALL
SELECT ?1, -1, NULL, NULL, 'a rules file is one <weight> <formula> a line, or JSON: a list of rules or {"rules": [...]}' FROM sh WHERE kind = 'other'
-- ;; rule 206 the rules' errors
INSERT INTO cx.judge_jevout (ask, qi, err) SELECT ?1, CASE WHEN i < 0 THEN -999 ELSE -1000 - i END, err FROM cx.judge_jevrl WHERE ask = ?1 AND err IS NOT NULL
-- ;; rule 207 each rule's formula as a question of its own, numbered -1000 - i, so the ask's tokens and postfix read it
INSERT INTO cx.judge_jevq (ask, qi, raw, qid, form) SELECT ?1, -1000 - i, form, 'rule ' || (i + 1), form FROM cx.judge_jevrl WHERE ask = ?1 AND i >= 0 AND err IS NULL
-- ;; rule 208 the tokens of the query and of the rules: the ask's rule 5, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 5 AND verb = 'ask'
-- ;; rule 209 a query or a rule that cannot be read; a query that names a variable (a rule may)
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, t.qi, CASE WHEN t.t = '?' THEN printf('%s: cannot read %s at %s', CASE WHEN t.qi >= 0 THEN 'question ' || q.qid ELSE q.qid END, json_quote(q.form), json_quote(t.a))
  ELSE printf('question %s: an argument of %s is a variable; a question is ground', q.qid, t.a) END
FROM cx.judge_jevtok t JOIN cx.judge_jevq q ON q.ask = t.ask AND q.qi = t.qi
WHERE t.ask = ?1 AND (t.t = '?' OR (t.qi >= 0 AND t.t = 'A' AND (t.a GLOB '*([A-Z_]*' OR t.a GLOB '*,[A-Z_]*')))
-- ;; rule 210 each rule's atoms as written (its templates), numbered t in sorted order
INSERT INTO cx.judge_jevtp (ask, qi, t, atom)
SELECT ?1, qi, row_number() OVER (PARTITION BY qi ORDER BY a) - 1, a FROM (SELECT DISTINCT qi, a FROM cx.judge_jevtok WHERE ask = ?1 AND qi <= -1000 AND t = 'A' AND a IS NOT NULL)
-- ;; rule 211 the groundings are bounded: at most 4096 in one request (the rules with weight 0 not counted)
INSERT INTO cx.judge_jevout (ask, qi, err)
WITH tp AS (SELECT tp.qi, tp.atom, instr(tp.atom, '(') AS pp FROM cx.judge_jevtp tp JOIN cx.judge_jevrl r ON r.ask = ?1 AND -1000 - r.i = tp.qi AND r.err IS NULL AND r.w <> 0 WHERE tp.ask = ?1),
ta AS (SELECT tp.qi, je.value AS arg FROM tp, json_each('["' || replace(substr(tp.atom, tp.pp + 1, length(tp.atom) - tp.pp - 1), ',', '","') || '"]') je WHERE tp.pp > 0),
at AS (SELECT head AS atom FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL UNION SELECT je.value FROM cx.judge_jevclause c, json_each(c.body) je WHERE c.ask = ?1 AND c.k >= 0 AND c.err IS NULL
  UNION SELECT a FROM cx.judge_jevtok WHERE ask = ?1 AND t = 'A' AND a IS NOT NULL),
aa AS (SELECT je.value AS arg FROM at, json_each('["' || replace(substr(at.atom, instr(at.atom, '(') + 1, length(at.atom) - instr(at.atom, '(') - 1), ',', '","') || '"]') je WHERE instr(at.atom, '(') > 0),
nk AS (SELECT count(DISTINCT arg) AS n FROM aa WHERE arg NOT GLOB '[A-Z_]*'),
nv AS (SELECT qi, count(DISTINCT arg) AS n FROM ta WHERE arg GLOB '[A-Z_]*' GROUP BY qi),
ng AS (SELECT total(CASE WHEN nk.n = 0 THEN 0 ELSE power(nk.n, nv.n) END) AS g FROM nv, nk)
SELECT ?1, -998, printf('the rules have %d groundings over %d constants; the groundings are bounded at 4096', CAST(ng.g AS INTEGER), nk.n) FROM ng, nk WHERE ng.g > 4096
-- ;; rule 212 the groundings: every assignment of the constants (of the state, the rules and the query) to a rule's variables, g the assignment's number; each template's ground atom
INSERT INTO cx.judge_jevgr (ask, qi, g, t, atom)
WITH RECURSIVE
rl AS (SELECT -1000 - i AS qi FROM cx.judge_jevrl WHERE ask = ?1 AND i >= 0 AND err IS NULL AND w <> 0 AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.qi = -998)),
tp AS (SELECT tp.qi, tp.t, tp.atom, instr(tp.atom, '(') AS pp FROM cx.judge_jevtp tp JOIN rl ON rl.qi = tp.qi WHERE tp.ask = ?1),
ta AS (SELECT tp.qi, tp.t, CAST(je.key AS INTEGER) AS ai, je.value AS arg FROM tp, json_each('["' || replace(substr(tp.atom, tp.pp + 1, length(tp.atom) - tp.pp - 1), ',', '","') || '"]') je WHERE tp.pp > 0),
vs AS (SELECT qi, arg AS v, row_number() OVER (PARTITION BY qi ORDER BY arg) - 1 AS vi FROM (SELECT DISTINCT qi, arg FROM ta WHERE arg GLOB '[A-Z_]*')),
nv AS (SELECT rl.qi, (SELECT count(*) FROM vs WHERE vs.qi = rl.qi) AS n FROM rl),
at AS (SELECT head AS atom FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL UNION SELECT je.value FROM cx.judge_jevclause c, json_each(c.body) je WHERE c.ask = ?1 AND c.k >= 0 AND c.err IS NULL
  UNION SELECT a FROM cx.judge_jevtok WHERE ask = ?1 AND t = 'A' AND a IS NOT NULL),
aa AS (SELECT je.value AS arg FROM at, json_each('["' || replace(substr(at.atom, instr(at.atom, '(') + 1, length(at.atom) - instr(at.atom, '(') - 1), ',', '","') || '"]') je WHERE instr(at.atom, '(') > 0),
kc AS (SELECT arg AS k, row_number() OVER (ORDER BY arg) - 1 AS ki FROM (SELECT DISTINCT arg FROM aa WHERE arg NOT GLOB '[A-Z_]*')),
nk AS (SELECT count(*) AS n FROM kc),
asg(qi, vi, g, m) AS (SELECT qi, 0, 0, json_object() FROM nv
  UNION ALL SELECT asg.qi, asg.vi + 1, asg.g * (SELECT n FROM nk) + kc.ki, json_set(asg.m, '$."' || vs.v || '"', kc.k) FROM asg JOIN vs ON vs.qi = asg.qi AND vs.vi = asg.vi JOIN kc),
fin AS (SELECT asg.qi, asg.g, asg.m FROM asg JOIN nv ON nv.qi = asg.qi AND asg.vi = nv.n)
SELECT ?1, fin.qi, fin.g, tp.t, CASE WHEN tp.pp = 0 THEN tp.atom ELSE substr(tp.atom, 1, tp.pp) ||
    (SELECT group_concat(CASE WHEN ta.arg GLOB '[A-Z_]*' THEN json_extract(fin.m, '$."' || ta.arg || '"') ELSE ta.arg END, ',' ORDER BY ta.ai) FROM ta WHERE ta.qi = tp.qi AND ta.t = tp.t) || ')' END
FROM fin JOIN tp ON tp.qi = fin.qi
-- ;; rule 213 the atoms the query depends on, numbered ix in sorted order: with groundings its whole neighbourhood (both ways through every clause and grounding); with none, backward through the bodies as C5
INSERT INTO cx.judge_jevpa (ask, qi, atom, ix)
WITH RECURSIVE
gx AS (SELECT EXISTS (SELECT 1 FROM cx.judge_jevgr WHERE ask = ?1) AS on_),
cl AS (SELECT k, head, body FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL AND p > 0),
ca AS (SELECT 'c' || k AS grp, head AS atom FROM cl UNION SELECT 'c' || cl.k, je.value FROM cl, json_each(cl.body) je
  UNION SELECT 'g' || qi || ':' || g, atom FROM cx.judge_jevgr WHERE ask = ?1),
ed AS (SELECT cl.head AS a, je.value AS b FROM cl, json_each(cl.body) je
  UNION SELECT x.atom, y.atom FROM ca x JOIN ca y ON y.grp = x.grp AND y.atom <> x.atom, gx WHERE gx.on_),
rc(qi, atom) AS (SELECT DISTINCT qi, a FROM cx.judge_jevtok WHERE ask = ?1 AND qi >= 0 AND t = 'A' AND a IS NOT NULL
  UNION SELECT rc.qi, ed.b FROM rc JOIN ed ON ed.a = rc.atom)
SELECT ?1, qi, atom, row_number() OVER (PARTITION BY qi ORDER BY atom) - 1 FROM rc
-- ;; rule 214 the clauses the query depends on: problog's rule 108, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 108 AND verb = 'problog'
-- ;; rule 215 the leaves of the query: problog's rule 109, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 109 AND verb = 'problog'
-- ;; rule 216 the leaves of each rule: template t is b<t>, its ground atom read per grounding
INSERT OR REPLACE INTO cx.judge_jevqa (ask, qi, atom, pf, u) SELECT ?1, qi, atom, NULL, t FROM cx.judge_jevtp WHERE ask = ?1
-- ;; rule 217 at most 16 uncertain clauses: problog's rule 110, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 110 AND verb = 'problog'
-- ;; rule 218 the query and the rules in postfix: the ask's rule 9, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 9 AND verb = 'ask'
-- ;; rule 219 a query or a rule that does not parse: the ask's rule 10, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 10 AND verb = 'ask'
-- ;; rule 220 every world's least model as words: problog's rule 113, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 113 AND verb = 'problog'
-- ;; rule 221 the query's truth in every world as words: problog's rule 114, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 114 AND verb = 'problog'
-- ;; rule 222 the answer of each question: each grounding's truth as words over the question's model words, each world's energy sum w_i n_i(x), p = sum P(x) exp(E(x)) where the question holds over sum P(x) exp(E(x)) (one line p= a question; the ask's child carries several, jev C8)
INSERT INTO cx.judge_jevout (ask, qi, p, line)
WITH RECURSIVE
ok AS MATERIALIZED (SELECT x.qi, (SELECT count(*) FROM cx.judge_jevpc pc WHERE pc.ask = ?1 AND pc.qi = x.qi AND pc.u IS NOT NULL) AS nv
  FROM cx.judge_jevx x WHERE x.ask = ?1 AND x.qi >= 0 AND x.rpn IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
rl AS MATERIALIZED (SELECT -1000 - r.i AS rq, r.w, x.rpn FROM cx.judge_jevrl r JOIN cx.judge_jevx x ON x.ask = ?1 AND x.qi = -1000 - r.i
  WHERE r.ask = ?1 AND r.i >= 0 AND r.err IS NULL AND r.w <> 0 AND x.rpn IS NOT NULL AND EXISTS (SELECT 1 FROM ok)),
fm AS MATERIALIZED (SELECT m.qi, m.c, m.m FROM cx.judge_jevm m JOIN ok ON ok.qi = m.qi WHERE m.ask = ?1),
lf AS MATERIALIZED (SELECT ok.qi, gr.qi AS rq, gr.g, gr.t, pa.ix FROM cx.judge_jevgr gr JOIN ok LEFT JOIN cx.judge_jevpa pa ON pa.ask = ?1 AND pa.qi = ok.qi AND pa.atom = gr.atom WHERE gr.ask = ?1),
gs AS (SELECT DISTINCT qi, rq, g FROM lf),
it AS MATERIALIZED (SELECT rl.rq, CAST(je.key AS INTEGER) + 1 AS j, je.value AS v FROM rl, json_each(rl.rpn) je),
nit AS (SELECT rq, count(*) AS n FROM it GROUP BY rq),
ev(qi, rq, g, c, m, j, st) AS (SELECT gs.qi, gs.rq, gs.g, fm.c, fm.m, 1, '[]' FROM gs JOIN rl ON rl.rq = gs.rq JOIN fm ON fm.qi = gs.qi
  UNION ALL
  SELECT ev.qi, ev.rq, ev.g, ev.c, ev.m, ev.j + 1, CASE
    WHEN it.v = '1' THEN json_insert(ev.st, '$[#]', -1)
    WHEN it.v = '0' THEN json_insert(ev.st, '$[#]', 0)
    WHEN substr(it.v, 1, 1) = 'b' THEN json_insert(ev.st, '$[#]', coalesce(json_extract(ev.m, '$[' || (SELECT lf.ix FROM lf WHERE lf.qi = ev.qi AND lf.rq = ev.rq AND lf.g = ev.g AND lf.t = CAST(substr(it.v, 2) AS INTEGER)) || ']'), 0))
    WHEN it.v = '!' THEN json_insert(json_remove(ev.st, '$[#-1]'), '$[#]', ~json_extract(ev.st, '$[#-1]'))
    ELSE json_insert(json_remove(json_remove(ev.st, '$[#-1]'), '$[#-1]'), '$[#]', CASE it.v
      WHEN '&' THEN json_extract(ev.st, '$[#-2]') & json_extract(ev.st, '$[#-1]')
      WHEN '|' THEN json_extract(ev.st, '$[#-2]') | json_extract(ev.st, '$[#-1]')
      WHEN '=>' THEN (~json_extract(ev.st, '$[#-2]')) | json_extract(ev.st, '$[#-1]')
      ELSE (json_extract(ev.st, '$[#-2]') & json_extract(ev.st, '$[#-1]')) | ((~json_extract(ev.st, '$[#-2]')) & (~json_extract(ev.st, '$[#-1]'))) END) END
  FROM ev JOIN it ON it.rq = ev.rq AND it.j = ev.j),
gw AS MATERIALIZED (SELECT ev.qi, ev.rq, ev.g, ev.c, json_extract(ev.st, '$[0]') AS r FROM ev JOIN nit ON nit.rq = ev.rq WHERE ev.j = nit.n + 1),
qr AS MATERIALIZED (SELECT r.qi, r.c, r.r FROM cx.judge_jevr r JOIN ok ON ok.qi = r.qi WHERE r.ask = ?1),
bits(v) AS (VALUES (0), (1)),
wd(qi, i, m, w) AS (SELECT qi, 0, 0, 1.0 FROM ok
  UNION ALL
  SELECT wd.qi, wd.i + 1, wd.m + (bits.v << wd.i), wd.w * CASE bits.v WHEN 1 THEN pc.p ELSE 1.0 - pc.p END
  FROM wd JOIN cx.judge_jevpc pc ON pc.ask = ?1 AND pc.qi = wd.qi AND pc.u = wd.i JOIN bits),
en AS MATERIALIZED (SELECT wd.qi, wd.m, wd.w, (SELECT total(rl.w * ((gw.r >> (wd.m & 63)) & 1)) FROM gw JOIN rl ON rl.rq = gw.rq WHERE gw.qi = wd.qi AND gw.c = (wd.m >> 6)) AS e
  FROM wd JOIN ok ON ok.qi = wd.qi AND wd.i = ok.nv),
mx AS (SELECT qi, max(e) AS e FROM en GROUP BY qi),
sm AS (SELECT en.qi, total(en.w * exp(en.e - mx.e)) AS den, total(CASE WHEN ((qr.r >> (en.m & 63)) & 1) = 1 THEN en.w * exp(en.e - mx.e) ELSE 0.0 END) AS num
  FROM en JOIN mx ON mx.qi = en.qi JOIN qr ON qr.qi = en.qi AND qr.c = (en.m >> 6) GROUP BY en.qi),
fp AS (SELECT ok.qi, CASE WHEN sm.den > 0 THEN sm.num / sm.den END AS p FROM ok JOIN sm ON sm.qi = ok.qi),
fs AS (SELECT qi, p, rtrim(printf('%.12f', min(1.0, max(0.0, p))), '0') AS s FROM fp WHERE p IS NOT NULL)
SELECT ?1, qi, p, 'p=' || CASE WHEN substr(s, -1) = '.' THEN s || '0' ELSE s END FROM fs
