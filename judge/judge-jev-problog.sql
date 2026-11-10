-- judge-jev-problog.sql (2026-11-10, jev C5): cortex jev problog in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- The distribution semantics (de-raedt-2007-problog.txt:23, :54): every clause p::head :- body is in a world with probability p, independently; a world's model is
-- the least model of its clauses; p(query) is the summed weight of the worlds whose model holds the query. A request row in cx.judge_jevask (verb problog) carries the
-- clauses file's text and the query typed as query:<formula>; the trigger judge_jevgo (judge-jev-ask.sql) hands each rule row of the verb to the mother in id order.
-- The ask's rules 1, 2, 5, 6, 9, 10 (the question, its tokens, its postfix) are run by reference, stored once; the rest are this verb's own rows. Only the clauses the
-- query depends on (backward through the bodies) count; p = 0 clauses are in no world, p = 1 clauses in every world; at most 16 uncertain clauses (2^16 worlds).
-- The least model of every world at once: 64 worlds a word (clause u < 6 a fixed pattern, u >= 6 the word's own bit), the clauses run as a little program
-- (load the clause's word, and each body atom's word, or into the head's word): the facts once, then the clauses with a body one pass for each head they have
-- (a pass that changes some world adds a head to it); then the query's postfix over the
-- model's words. Negation in a body, annotated disjunctions, soft rules (C6) and opinions (C7) are refused, named. Lay: python3 work/jev/lay.py problog (after the ask).
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevclause (ask INTEGER NOT NULL, k INTEGER NOT NULL, rid TEXT, head TEXT, body TEXT, p REAL, err TEXT, PRIMARY KEY (ask, k))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevpa (ask INTEGER NOT NULL, qi INTEGER NOT NULL, atom TEXT NOT NULL, ix INTEGER, PRIMARY KEY (ask, qi, atom))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevpc (ask INTEGER NOT NULL, qi INTEGER NOT NULL, j INTEGER NOT NULL, head INTEGER, body TEXT, u INTEGER, p REAL, PRIMARY KEY (ask, qi, j))
-- ;; rule 101 the query as typed: the ask's rule 1, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 1 AND verb = 'ask'
-- ;; rule 102 a query that is not <id>:<formula>: the ask's rule 2, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 2 AND verb = 'ask'
-- ;; rule 103 the clauses: ProbLog text (one clause a line, p::head :- b1, b2., % a comment, the row id r<line>) or JSON (rows, {"rows": [...]}, {"<atom>": p}; a row {"id", "atom" or "head", "if" or "body", "p"} or {"clause": "..."})
INSERT INTO cx.judge_jevclause (ask, k, rid, head, body, p, err)
WITH RECURSIVE
a AS (SELECT coalesce(state, '') AS s FROM cx.judge_jevask WHERE id = ?1),
sh AS (SELECT s, CASE WHEN NOT json_valid(s) THEN 'text'
    WHEN json_type(s) = 'object' AND EXISTS (SELECT 1 FROM json_each(a.s)) AND NOT EXISTS (SELECT 1 FROM json_each(a.s) e WHERE e.type NOT IN ('integer', 'real')) THEN 'dict'
    WHEN json_type(s) = 'array' THEN '$'
    WHEN json_type(s) = 'object' AND json_type(s, '$.rows') = 'array' THEN '$.rows'
    WHEN json_type(s) = 'object' AND json_type(s, '$.rows') IS NULL AND json_type(s, '$.clauses') = 'array' THEN '$.clauses'
    ELSE 'other' END AS kind,
  CASE WHEN json_valid(s) AND json_type(s) = 'object' AND json_type(s, '$.rules') = 'array' THEN json_array_length(s, '$.rules') ELSE 0 END AS nrules FROM a),
ln(n, rest, line) AS (SELECT 0, s || char(10), NULL FROM sh WHERE kind = 'text'
  UNION ALL SELECT n + 1, substr(rest, instr(rest, char(10)) + 1), substr(rest, 1, instr(rest, char(10)) - 1) FROM ln WHERE rest <> ''),
tl AS (SELECT n AS lineno, trim(replace(CASE WHEN instr(line, '%') > 0 THEN substr(line, 1, instr(line, '%') - 1) ELSE line END, char(13), ''), ' ' || char(9)) AS cl FROM ln WHERE line IS NOT NULL),
rr AS (SELECT row_number() OVER (ORDER BY lineno) - 1 AS k, 'r' || lineno AS rid0, 'text' AS ty, NULL AS v, cl FROM tl WHERE cl <> ''
  UNION ALL
  SELECT CAST(e.key AS INTEGER), NULL, e.type, CASE WHEN e.type = 'object' THEN e.value END,
    CASE WHEN e.type = 'text' THEN e.value WHEN e.type = 'object' AND json_type(e.value, '$.clause') = 'text' THEN json_extract(e.value, '$.clause') END
  FROM sh, json_each(CASE WHEN sh.kind IN ('$', '$.rows', '$.clauses') THEN sh.s ELSE '[]' END, CASE WHEN sh.kind IN ('$', '$.rows', '$.clauses') THEN sh.kind ELSE '$' END) e
  WHERE sh.kind IN ('$', '$.rows', '$.clauses')
  UNION ALL
  SELECT row_number() OVER () - 1, NULL, 'object', json_object('atom', e.key, 'p', e.value), NULL FROM sh, json_each(CASE WHEN sh.kind = 'dict' THEN sh.s ELSE '{}' END) e WHERE sh.kind = 'dict'),
r1 AS (SELECT k, ty, v, cl,
    coalesce(rid0, CASE WHEN v IS NOT NULL AND json_type(v, '$.id') IS NOT NULL AND json_type(v, '$.id') <> 'null' THEN CAST(json_extract(v, '$.id') AS TEXT) END, 'r' || (k + 1)) AS rid,
    CASE WHEN cl IS NOT NULL THEN trim(cl, ' ' || char(9, 10, 13)) END AS c0 FROM rr),
r2 AS (SELECT r1.*, CASE WHEN substr(c0, -1) = '.' THEN rtrim(substr(c0, 1, length(c0) - 1), ' ' || char(9, 10, 13)) ELSE c0 END AS c1 FROM r1),
r3 AS (SELECT r2.*, instr(c1, '::') AS dc FROM r2),
r4 AS (SELECT r3.*, CASE WHEN dc > 0 THEN substr(c1, dc + 2) ELSE c1 END AS c2, CASE WHEN dc > 0 THEN trim(substr(c1, 1, dc - 1), ' ' || char(9)) ELSE '1' END AS ptxt FROM r3),
r5 AS (SELECT r4.*, instr(c2, ':-') AS bc FROM r4),
r6 AS (SELECT k, ty, v, cl, rid, c1, ptxt,
    CASE WHEN cl IS NOT NULL THEN trim(CASE WHEN bc > 0 THEN substr(c2, 1, bc - 1) ELSE c2 END, ' ' || char(9, 10, 13))
         WHEN v IS NOT NULL THEN coalesce(json_extract(v, '$.atom'), json_extract(v, '$.head')) END AS htxt,
    CASE WHEN cl IS NOT NULL THEN CASE WHEN bc > 0 THEN substr(c2, bc + 2) ELSE '' END
         WHEN v IS NULL THEN ''
         WHEN json_type(v, '$.if') = 'array' THEN (SELECT group_concat(e.value, ',') FROM json_each(v, '$.if') e)
         WHEN json_type(v, '$.if') = 'text' THEN json_extract(v, '$.if')
         WHEN json_type(v, '$.body') = 'array' THEN (SELECT group_concat(e.value, ',') FROM json_each(v, '$.body') e)
         WHEN json_type(v, '$.body') = 'text' THEN json_extract(v, '$.body')
         ELSE '' END AS btxt,
    CASE WHEN cl IS NULL AND v IS NOT NULL THEN json_type(v, '$.p') END AS ptype,
    CASE WHEN cl IS NULL AND v IS NOT NULL THEN json_extract(v, '$.p') END AS pv,
    CASE WHEN dc > 0 AND substr(trim(substr(c1, 1, dc - 1), ' ' || char(9)), 1, 1) = '.' THEN '0' || trim(substr(c1, 1, dc - 1), ' ' || char(9)) ELSE trim(substr(c1, 1, dc - 1), ' ' || char(9)) END AS pj FROM r5),
r7 AS (SELECT r6.*, CASE WHEN cl IS NOT NULL THEN CAST(ptxt AS REAL) WHEN ptype IS NULL THEN 1.0 WHEN ptype IN ('integer', 'real') THEN pv END AS p,
    replace(replace(replace(replace(htxt, ' ', ''), char(9), ''), char(10), ''), char(13), '') AS head FROM r6),
bt AS (SELECT k, btxt AS b, length(btxt) AS n FROM r7 WHERE btxt IS NOT NULL AND btxt <> ''),
nums(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM nums WHERE i < (SELECT coalesce(max(n), 0) FROM bt)),
bcs AS (SELECT bt.k, nums.i, substr(bt.b, nums.i, 1) AS ch FROM bt JOIN nums ON nums.i <= bt.n),
bd AS (SELECT k, i, ch, sum(CASE ch WHEN '(' THEN 1 WHEN ')' THEN -1 ELSE 0 END) OVER (PARTITION BY k ORDER BY i ROWS UNBOUNDED PRECEDING) AS d FROM bcs),
cut AS (SELECT k, 0 AS i FROM bt UNION ALL SELECT k, i FROM bd WHERE ch = ',' AND d = 0 UNION ALL SELECT k, n + 1 FROM bt),
cu AS (SELECT k, i, lead(i) OVER (PARTITION BY k ORDER BY i) AS i2 FROM cut),
bp0 AS (SELECT cu.k, cu.i AS pos, trim(substr(bt.b, cu.i + 1, cu.i2 - cu.i - 1), ' ' || char(9, 10, 13)) AS raw FROM cu JOIN bt ON bt.k = cu.k WHERE cu.i2 IS NOT NULL),
bp AS (SELECT k, pos, raw, replace(replace(replace(replace(raw, ' ', ''), char(9), ''), char(10), ''), char(13), '') AS x FROM bp0 WHERE raw <> ''),
at AS (SELECT k, -1 AS pos, head AS x, htxt AS raw, 'the atom of row ' AS what FROM r7 WHERE head IS NOT NULL AND head <> ''
  UNION ALL SELECT k, pos, x, raw, 'a body atom of row ' FROM bp),
ae AS (SELECT k, pos, x, raw, what, instr(x, '(') AS pp,
    CASE WHEN instr(trim(raw, ' ' || char(9, 10, 13)), '(') > 0 THEN substr(trim(raw, ' ' || char(9, 10, 13)), 1, instr(trim(raw, ' ' || char(9, 10, 13)), '(') - 1) ELSE trim(raw, ' ' || char(9, 10, 13)) END AS nm FROM at),
af AS (SELECT k, pos, x, CASE
    WHEN what <> 'the atom of row ' AND (substr(raw, 1, 2) = '\+' OR lower(substr(raw, 1, 4)) IN ('not ', 'not(')) THEN 'is a negation; negation in a clause body is not built: ' || raw
    WHEN nm GLOB '*[' || ' ' || char(9, 10, 13) || ']*'
      OR (pp = 0 AND (x GLOB '*[^A-Za-z0-9_]*' OR lower(x) IN ('and', 'or', 'not', 'true', 'false')))
      OR (pp > 0 AND (pp = 1 OR substr(x, 1, pp - 1) GLOB '*[^A-Za-z0-9_]*' OR lower(substr(x, 1, pp - 1)) IN ('and', 'or', 'not', 'true', 'false') OR substr(x, -1) <> ')'
        OR length(x) <= pp + 1 OR substr(x, pp + 1, length(x) - pp - 1) GLOB '*[^A-Za-z0-9_.''+,-]*' OR substr(x, pp + 1, 1) = ',' OR substr(x, -2, 1) = ','
        OR instr(x, ',,') > 0)) THEN 'is not one atom: ' || json_quote(raw)
    WHEN x GLOB '*([A-Z_]*' OR x GLOB '*,[A-Z_]*' THEN 'has a variable; a clause is ground here: ' || x END AS e, what FROM ae),
ke AS (SELECT k, what, e FROM (SELECT k, what, e, row_number() OVER (PARTITION BY k ORDER BY pos) AS rk FROM af WHERE e IS NOT NULL) WHERE rk = 1)
SELECT ?1, r.k, r.rid, r.head,
  (SELECT json_group_array(x) FROM (SELECT x FROM bp WHERE bp.k = r.k ORDER BY pos)), r.p, CASE
    WHEN r.ty NOT IN ('object', 'text') THEN printf('row %d is neither an object nor a clause', r.k + 1)
    WHEN r.v IS NOT NULL AND (json_type(r.v, '$.b') IS NOT NULL OR json_type(r.v, '$.d') IS NOT NULL OR json_type(r.v, '$.u') IS NOT NULL OR json_type(r.v, '$.trust') IS NOT NULL)
      THEN printf('row %s is an opinion (b, d, u, trust): opinions are jev C7, not built in the judge brain yet', r.rid)
    WHEN r.cl IS NOT NULL AND instr(r.c1, ';') > 0 THEN printf('row %s: an annotated disjunction is not built: %s', r.rid, r.cl)
    WHEN r.cl IS NOT NULL AND instr(r.c1, '::') > 0 AND (r.ptxt = '' OR substr(r.ptxt, 1, 1) IN ('-', '+') OR NOT json_valid(r.pj) OR json_type(r.pj) NOT IN ('integer', 'real'))
      THEN printf('the probability of %s is not a number', json_quote(r.cl))
    WHEN r.head IS NULL OR r.head = '' THEN printf('row %s has no atom', r.rid)
    WHEN r.p IS NULL THEN printf('p of row %s is not a number: %s', r.rid, r.pv)
    WHEN r.p < 0 OR r.p > 1 THEN printf('p of row %s = %s is outside 0 to 1', r.rid, r.p)
    WHEN ke.e IS NOT NULL THEN ke.what || r.rid || ' ' || ke.e END
FROM r7 r LEFT JOIN ke ON ke.k = r.k
UNION ALL
SELECT ?1, -1, NULL, NULL, NULL, NULL, 'a clauses file is ProbLog text (one clause a line) or JSON: a list of rows, {"rows": [...]} or {"<atom>": p}' FROM sh WHERE kind = 'other'
UNION ALL
SELECT ?1, -2, NULL, NULL, NULL, NULL, 'the file holds soft rules: weighted rules are jev C6, not built in the judge brain yet' FROM sh WHERE kind IN ('$.rows', '$.clauses') AND nrules > 0
-- ;; rule 104 the clauses' errors and a row id given twice
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, -1, e FROM (SELECT err AS e FROM cx.judge_jevclause WHERE ask = ?1 AND err IS NOT NULL
  UNION ALL SELECT printf('the row id %s is twice in the clauses', rid) FROM cx.judge_jevclause WHERE ask = ?1 AND rid IS NOT NULL GROUP BY rid HAVING count(*) > 1)
-- ;; rule 105 the tokens of the query: the ask's rule 5, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 5 AND verb = 'ask'
-- ;; rule 106 a query that cannot be read, or that names a variable: the ask's rule 6, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 6 AND verb = 'ask'
-- ;; rule 107 the atoms the query depends on: its own atoms, then backward through the bodies of the clauses (p > 0) whose head is one of them; numbered ix in sorted order
INSERT INTO cx.judge_jevpa (ask, qi, atom, ix)
WITH RECURSIVE
cl AS (SELECT head, body FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL AND p > 0),
cb AS (SELECT cl.head, je.value AS b FROM cl, json_each(cl.body) je),
rc(qi, atom) AS (SELECT DISTINCT qi, a FROM cx.judge_jevtok WHERE ask = ?1 AND t = 'A' AND a IS NOT NULL
  UNION SELECT rc.qi, cb.b FROM rc JOIN cb ON cb.head = rc.atom)
SELECT ?1, qi, atom, row_number() OVER (PARTITION BY qi ORDER BY atom) - 1 FROM rc
-- ;; rule 108 the clauses the query depends on (p > 0, head among its atoms), in file order: head and body as atom numbers; u numbers the uncertain ones (p < 1), a p = 1 clause is in every world
INSERT INTO cx.judge_jevpc (ask, qi, j, head, body, u, p)
WITH cl AS (SELECT k, head, body, p FROM cx.judge_jevclause WHERE ask = ?1 AND k >= 0 AND err IS NULL AND p > 0),
pc AS (SELECT pa.qi, cl.k, pa.ix AS h, cl.body, cl.p FROM cl JOIN cx.judge_jevpa pa ON pa.ask = ?1 AND pa.atom = cl.head)
SELECT ?1, pc.qi, row_number() OVER w, pc.h,
  (SELECT json_group_array(pb.ix) FROM json_each(pc.body) je JOIN cx.judge_jevpa pb ON pb.ask = ?1 AND pb.qi = pc.qi AND pb.atom = je.value),
  CASE WHEN pc.p < 1 THEN sum(pc.p < 1) OVER w - 1 END, pc.p
FROM pc WINDOW w AS (PARTITION BY pc.qi ORDER BY pc.k)
-- ;; rule 109 the leaves of the query for the ask's postfix: an atom some clause can make is the model's word b<ix>; an atom no clause makes is false
INSERT INTO cx.judge_jevqa (ask, qi, atom, pf, u)
SELECT DISTINCT ?1, t.qi, t.a, NULL, (SELECT pa.ix FROM cx.judge_jevpa pa WHERE pa.ask = ?1 AND pa.qi = t.qi AND pa.atom = t.a
    AND EXISTS (SELECT 1 FROM cx.judge_jevpc pc WHERE pc.ask = ?1 AND pc.qi = t.qi AND pc.head = pa.ix))
FROM cx.judge_jevtok t WHERE t.ask = ?1 AND t.t = 'A' AND t.a IS NOT NULL
-- ;; rule 110 exact inference is bounded: at most 16 uncertain clauses in one answer
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, q.qi, printf('the query depends on %d uncertain clauses; exact inference is bounded at 16', count(*))
FROM cx.judge_jevpc pc JOIN cx.judge_jevq q ON q.ask = pc.ask AND q.qi = pc.qi WHERE pc.ask = ?1 AND pc.u IS NOT NULL GROUP BY q.qi HAVING count(*) > 16
-- ;; rule 111 the query in postfix: the ask's rule 9, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 9 AND verb = 'ask'
-- ;; rule 112 a query that does not parse: the ask's rule 10, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 10 AND verb = 'ask'
-- ;; rule 113 the answer: every world's least model as words (load, and the body, or into the head; the facts once, then the clauses with a body one pass for each of their heads), the query's postfix over the model's words, p = the summed weight of the worlds where it holds
INSERT INTO cx.judge_jevout (ask, qi, p, line)
WITH RECURSIVE
ok AS (SELECT x.qi, x.rpn,
    (SELECT count(*) FROM cx.judge_jevpc pc WHERE pc.ask = ?1 AND pc.qi = x.qi AND pc.u IS NOT NULL) AS nv,
    (SELECT count(DISTINCT pc.head) FROM cx.judge_jevpc pc WHERE pc.ask = ?1 AND pc.qi = x.qi AND json_array_length(pc.body) > 0) AS nh,
    (SELECT json_group_array(0) FROM cx.judge_jevpa pa WHERE pa.ask = ?1 AND pa.qi = x.qi) AS m0
  FROM cx.judge_jevx x WHERE x.ask = ?1 AND x.rpn IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
cs AS (SELECT pc.qi, pc.j, pc.head, pc.body, pc.u, json_array_length(pc.body) AS nb FROM cx.judge_jevpc pc WHERE pc.ask = ?1 AND pc.qi IN (SELECT qi FROM ok)),
ci AS (SELECT qi, j, nb, 0 AS s, 'L' AS op, u AS arg FROM cs
  UNION ALL SELECT cs.qi, cs.j, cs.nb, CAST(je.key AS INTEGER) + 1, 'A', je.value FROM cs, json_each(cs.body) je
  UNION ALL SELECT qi, j, nb, nb + 1, 'O', head FROM cs),
rn(r) AS (SELECT 0 UNION ALL SELECT r + 1 FROM rn WHERE r < (SELECT coalesce(max(nh), 0) FROM ok)),
prog AS MATERIALIZED (SELECT ci.qi, row_number() OVER (PARTITION BY ci.qi ORDER BY rn.r, ci.j, ci.s) AS n, ci.op, ci.arg FROM ci JOIN ok ON ok.qi = ci.qi
  JOIN rn ON (ci.nb = 0 AND rn.r = 0) OR (ci.nb > 0 AND rn.r BETWEEN 1 AND ok.nh)),
np AS (SELECT ok.qi, (SELECT count(*) FROM prog WHERE prog.qi = ok.qi) AS n FROM ok),
pat(u, b) AS (VALUES (0, 0xAAAAAAAAAAAAAAAA), (1, 0xCCCCCCCCCCCCCCCC), (2, 0xF0F0F0F0F0F0F0F0), (3, 0xFF00FF00FF00FF00), (4, 0xFFFF0000FFFF0000), (5, 0xFFFFFFFF00000000)),
ch(qi, c, nc) AS (SELECT qi, 0, CASE WHEN nv > 6 THEN 1 << (nv - 6) ELSE 1 END FROM ok UNION ALL SELECT qi, c + 1, nc FROM ch WHERE c + 1 < nc),
mv(qi, c, n, acc, m) AS (SELECT ch.qi, ch.c, 1, 0, ok.m0 FROM ch JOIN ok ON ok.qi = ch.qi
  UNION ALL
  SELECT mv.qi, mv.c, mv.n + 1,
    CASE p.op WHEN 'L' THEN CASE WHEN p.arg IS NULL THEN -1 WHEN p.arg < 6 THEN (SELECT b FROM pat WHERE pat.u = p.arg) ELSE -((mv.c >> (p.arg - 6)) & 1) END
              WHEN 'A' THEN mv.acc & json_extract(mv.m, '$[' || p.arg || ']')
              ELSE mv.acc END,
    CASE WHEN p.op = 'O' THEN json_set(mv.m, '$[' || p.arg || ']', json_extract(mv.m, '$[' || p.arg || ']') | mv.acc) ELSE mv.m END
  FROM mv JOIN prog p ON p.qi = mv.qi AND p.n = mv.n),
fm AS MATERIALIZED (SELECT mv.qi, mv.c, mv.m FROM mv JOIN np ON np.qi = mv.qi WHERE mv.n = np.n + 1),
it AS (SELECT ok.qi, CAST(je.key AS INTEGER) + 1 AS j, je.value AS v FROM ok, json_each(ok.rpn) je),
nit AS (SELECT qi, count(*) AS n FROM it GROUP BY qi),
ev(qi, c, m, j, st) AS (SELECT qi, c, m, 1, '[]' FROM fm
  UNION ALL
  SELECT ev.qi, ev.c, ev.m, ev.j + 1, CASE
    WHEN it.v = '1' THEN json_insert(ev.st, '$[#]', -1)
    WHEN it.v = '0' THEN json_insert(ev.st, '$[#]', 0)
    WHEN substr(it.v, 1, 1) = 'b' THEN json_insert(ev.st, '$[#]', json_extract(ev.m, '$[' || substr(it.v, 2) || ']'))
    WHEN it.v = '!' THEN json_insert(json_remove(ev.st, '$[#-1]'), '$[#]', ~json_extract(ev.st, '$[#-1]'))
    ELSE json_insert(json_remove(json_remove(ev.st, '$[#-1]'), '$[#-1]'), '$[#]', CASE it.v
      WHEN '&' THEN json_extract(ev.st, '$[#-2]') & json_extract(ev.st, '$[#-1]')
      WHEN '|' THEN json_extract(ev.st, '$[#-2]') | json_extract(ev.st, '$[#-1]')
      WHEN '=>' THEN (~json_extract(ev.st, '$[#-2]')) | json_extract(ev.st, '$[#-1]')
      ELSE (json_extract(ev.st, '$[#-2]') & json_extract(ev.st, '$[#-1]')) | ((~json_extract(ev.st, '$[#-2]')) & (~json_extract(ev.st, '$[#-1]'))) END) END
  FROM ev JOIN it ON it.qi = ev.qi AND it.j = ev.j),
res AS MATERIALIZED (SELECT ev.qi, ev.c, json_extract(ev.st, '$[0]') AS r FROM ev JOIN nit ON nit.qi = ev.qi WHERE ev.j = nit.n + 1),
bits(v) AS (VALUES (0), (1)),
wd(qi, i, m, w) AS (SELECT qi, 0, 0, 1.0 FROM ok
  UNION ALL
  SELECT wd.qi, wd.i + 1, wd.m + (bits.v << wd.i), wd.w * CASE bits.v WHEN 1 THEN pc.p ELSE 1.0 - pc.p END
  FROM wd JOIN cx.judge_jevpc pc ON pc.ask = ?1 AND pc.qi = wd.qi AND pc.u = wd.i JOIN bits),
tot AS (SELECT wd.qi, total(wd.w) AS p FROM wd JOIN ok ON ok.qi = wd.qi AND wd.i = ok.nv JOIN res ON res.qi = wd.qi AND res.c = (wd.m >> 6)
  WHERE ((res.r >> (wd.m & 63)) & 1) = 1 GROUP BY wd.qi),
fp AS (SELECT ok.qi, coalesce(tot.p, 0.0) AS p, rtrim(printf('%.12f', min(1.0, max(0.0, coalesce(tot.p, 0.0)))), '0') AS s FROM ok LEFT JOIN tot ON tot.qi = ok.qi)
SELECT ?1, fp.qi, fp.p, 'p=' || CASE WHEN substr(fp.s, -1) = '.' THEN fp.s || '0' ELSE fp.s END FROM fp
