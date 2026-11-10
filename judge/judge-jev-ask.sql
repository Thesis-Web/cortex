-- judge-jev-ask.sql (2026-11-10, jev C4): cortex jev ask in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- A request row in cx.judge_jevask carries the variables (the state file's text, the questions as typed); its trigger hands each rule row of the verb
-- to the mother in id order with the request id as ?1; the answer is read back as rows of cx.judge_jevout (one line <id> noul=<p> per question, in
-- the order given, or an error row). The state's atoms are independent facts with p = 1 - prod(1 - p_i) over their rows; a question is a boolean
-- formula (and or not => <=>, & | ! ~ , ^ -> <-> \+, parentheses, true, false); p(question) is the summed weight of the worlds of its uncertain atoms
-- where it holds, exact, at most 2^16 worlds, the formula run as 64-bit boolean words over the worlds, 64 worlds a word. Clauses with bodies are jev C5,
-- soft rules C6, opinions C7: refused with their checkpoint named, not built here. Pattern: judge/judge-c1.sql and judge/judge-jev.sql (rail C6).
-- jev C8 (11-10): a state that is not facts alone (ProbLog text, a clause with a body, an opinion, soft rules) is answered by a child request of verb mln (rule 0,
-- the C5 to C7 rules) whose lines rule 12 copies; every answer keeps its reasons (rules 13 to 15): for each row that can matter, the same request without that row
-- runs now (the kernel's recursive triggers), and the rows whose leaving out changes the answer's line are its reasons, with path:line, one record row
-- (cx.judge_jevans) an answer; cx.judge_jevcur holds each id's newest answer; rows retracted (cx.judge_jevret) are left out of every ask (rule -1).
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevask (id INTEGER PRIMARY KEY, verb TEXT NOT NULL, state TEXT, qs TEXT, ts INTEGER)
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevrule (id INTEGER PRIMARY KEY, verb TEXT NOT NULL, name TEXT NOT NULL, sql TEXT NOT NULL)
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevsaid (ask INTEGER NOT NULL, rule INTEGER NOT NULL, said TEXT, PRIMARY KEY (ask, rule))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevq (ask INTEGER NOT NULL, qi INTEGER NOT NULL, raw TEXT, qid TEXT, form TEXT, PRIMARY KEY (ask, qi))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevfact (ask INTEGER NOT NULL, k INTEGER NOT NULL, rid TEXT, atom TEXT, p REAL, err TEXT, PRIMARY KEY (ask, k))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevtok (ask INTEGER NOT NULL, qi INTEGER NOT NULL, k INTEGER NOT NULL, t TEXT, a TEXT, PRIMARY KEY (ask, qi, k))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevqa (ask INTEGER NOT NULL, qi INTEGER NOT NULL, atom TEXT NOT NULL, pf REAL, u INTEGER, PRIMARY KEY (ask, qi, atom))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevx (ask INTEGER NOT NULL, qi INTEGER NOT NULL, nu INTEGER, rpn TEXT, err TEXT, PRIMARY KEY (ask, qi))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevout (ask INTEGER NOT NULL, qi INTEGER NOT NULL, p REAL, line TEXT, err TEXT)
-- ;; ddl
CREATE INDEX IF NOT EXISTS cx.judge_jevout_ask ON judge_jevout (ask, qi)
-- ;; ddl-add
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
DROP TRIGGER IF EXISTS cx.judge_jevgo
-- ;; ddl
CREATE TRIGGER cx.judge_jevgo AFTER INSERT ON judge_jevask BEGIN INSERT OR REPLACE INTO judge_jevsaid (ask, rule, said) SELECT NEW.id, r.id, mother(r.sql, NEW.id) FROM judge_jevrule r WHERE r.verb = NEW.verb ORDER BY r.id; END
-- ;; rule -1 the rows this request leaves out (jev C8): its own leave and every row retracted now
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
-- ;; rule 1 the questions as typed: <id>:<formula>, a leading noul: is the type built
INSERT INTO cx.judge_jevq (ask, qi, raw, qid, form)
SELECT ?1, CAST(j.key AS INTEGER), j.value,
  CASE WHEN instr(j.value, ':') > 0 THEN trim(substr(j.value, 1, instr(j.value, ':') - 1), ' ' || char(9, 10, 13)) END,
  CASE WHEN instr(j.value, ':') = 0 THEN NULL
       WHEN lower(substr(trim(substr(j.value, instr(j.value, ':') + 1), ' ' || char(9, 10, 13)), 1, 5)) = 'noul:' THEN trim(substr(trim(substr(j.value, instr(j.value, ':') + 1), ' ' || char(9, 10, 13)), 6), ' ' || char(9, 10, 13))
       ELSE trim(substr(j.value, instr(j.value, ':') + 1), ' ' || char(9, 10, 13)) END
FROM cx.judge_jevask a, json_each(a.qs) j WHERE a.id = ?1
-- ;; rule 2 a question that is not <id>:<formula>
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, qi, printf('a question is <id>:<formula>, not %s', json_quote(raw)) FROM cx.judge_jevq WHERE ask = ?1 AND (qid IS NULL OR qid = '' OR form IS NULL OR form = '')
-- ;; rule 3 the state's rows: JSON {"<atom>": p}, a list of rows, or {"rows": [...]}; a row {"id", "atom" or "head", "p"} or a fact clause "p::atom."
INSERT INTO cx.judge_jevfact (ask, k, rid, atom, p, err)
WITH a AS (SELECT state AS s FROM cx.judge_jevask WHERE id = ?1 AND NOT EXISTS (SELECT 1 FROM cx.judge_jevask c WHERE c.parent = ?1)),
lv AS (SELECT value AS rid FROM json_each(coalesce((SELECT leave FROM cx.judge_jevask WHERE id = ?1), '[]'))),
sh AS (SELECT s, CASE WHEN NOT json_valid(s) THEN 'text'
    WHEN json_type(s) = 'object' AND EXISTS (SELECT 1 FROM json_each(a.s)) AND NOT EXISTS (SELECT 1 FROM json_each(a.s) e WHERE e.type NOT IN ('integer', 'real')) THEN 'dict'
    WHEN json_type(s) = 'array' THEN '$'
    WHEN json_type(s) = 'object' AND json_type(s, '$.rows') = 'array' THEN '$.rows'
    WHEN json_type(s) = 'object' AND json_type(s, '$.rows') IS NULL AND json_type(s, '$.clauses') = 'array' THEN '$.clauses'
    ELSE 'other' END AS kind,
  CASE WHEN json_valid(s) AND json_type(s) = 'object' AND json_type(s, '$.rules') = 'array' THEN json_array_length(s, '$.rules') ELSE 0 END AS nrules FROM a),
dr AS (SELECT row_number() OVER () - 1 AS k, e.key AS raw, e.value AS p FROM sh, json_each(CASE WHEN sh.kind = 'dict' THEN sh.s ELSE '{}' END) e WHERE sh.kind = 'dict'),
rr AS (SELECT CAST(e.key AS INTEGER) AS k, e.type AS ty, CASE WHEN e.type = 'object' THEN e.value END AS v,
    CASE WHEN e.type = 'text' THEN e.value WHEN e.type = 'object' THEN json_extract(e.value, '$.clause') END AS cl
  FROM sh, json_each(CASE WHEN sh.kind IN ('$', '$.rows', '$.clauses') THEN sh.s ELSE '[]' END, CASE WHEN sh.kind IN ('$', '$.rows', '$.clauses') THEN sh.kind ELSE '$' END) e WHERE sh.kind IN ('$', '$.rows', '$.clauses')),
r1 AS (SELECT k, ty, v, cl,
    CASE WHEN v IS NOT NULL AND json_type(v, '$.id') IS NOT NULL AND json_type(v, '$.id') <> 'null' THEN CAST(json_extract(v, '$.id') AS TEXT) ELSE 'r' || (k + 1) END AS rid,
    CASE WHEN cl IS NOT NULL THEN trim(cl, ' ' || char(9, 10, 13)) END AS c0 FROM rr),
r2 AS (SELECT r1.*, CASE WHEN substr(c0, -1) = '.' THEN rtrim(substr(c0, 1, length(c0) - 1), ' ' || char(9, 10, 13)) ELSE c0 END AS c1 FROM r1),
r3 AS (SELECT r2.*, instr(c1, '::') AS dc FROM r2),
r4 AS (SELECT r3.*,
    CASE WHEN cl IS NOT NULL THEN trim(CASE WHEN dc > 0 THEN substr(c1, dc + 2) ELSE c1 END, ' ' || char(9, 10, 13)) ELSE coalesce(json_extract(v, '$.atom'), json_extract(v, '$.head')) END AS raw,
    CASE WHEN cl IS NOT NULL THEN CASE WHEN dc > 0 THEN trim(substr(c1, 1, dc - 1), ' ' || char(9, 10, 13)) ELSE '1' END END AS ptxt,
    CASE WHEN cl IS NULL AND v IS NOT NULL THEN json_type(v, '$.p') END AS ptype,
    CASE WHEN cl IS NULL AND v IS NOT NULL THEN json_extract(v, '$.p') END AS pv FROM r3),
r5 AS (SELECT r4.*, CASE WHEN cl IS NOT NULL THEN CAST(ptxt AS REAL) WHEN ptype IS NULL THEN 1.0 ELSE pv END AS p,
    replace(replace(replace(replace(raw, ' ', ''), char(9), ''), char(10), ''), char(13), '') AS atom FROM r4)
SELECT ?1, k, rid, atom, p, CASE
    WHEN ty NOT IN ('object', 'text') THEN printf('row %d is neither an object nor a clause', k + 1)
    WHEN cl IS NOT NULL AND instr(c1, ':-') > 0 THEN printf('row %s is a clause with a body (%s): clauses are jev C5, not built in the judge brain yet', rid, cl)
    WHEN cl IS NOT NULL AND instr(c1, ';') > 0 THEN printf('row %s: an annotated disjunction is not built: %s', rid, cl)
    WHEN cl IS NOT NULL AND (ptxt = '' OR ptxt GLOB '*[^0-9.eE+-]*') THEN printf('the probability of %s is not a number', json_quote(cl))
    WHEN raw IS NULL THEN printf('row %s has no atom', rid)
    WHEN v IS NOT NULL AND ((json_type(v, '$.if') IS NOT NULL AND json_type(v, '$.if') <> 'null' AND coalesce(json_array_length(v, '$.if'), length(json_extract(v, '$.if'))) > 0)
                         OR (json_type(v, '$.body') IS NOT NULL AND json_type(v, '$.body') <> 'null' AND coalesce(json_array_length(v, '$.body'), length(json_extract(v, '$.body'))) > 0))
      THEN printf('row %s has a body: clauses are jev C5, not built in the judge brain yet', rid)
    WHEN v IS NOT NULL AND (json_type(v, '$.b') IS NOT NULL OR json_type(v, '$.d') IS NOT NULL OR json_type(v, '$.u') IS NOT NULL OR json_type(v, '$.trust') IS NOT NULL)
      THEN printf('row %s is an opinion (b, d, u, trust): opinions are jev C7, not built in the judge brain yet', rid)
    WHEN cl IS NULL AND ptype IS NOT NULL AND ptype NOT IN ('integer', 'real') THEN printf('p of row %s is not a number: %s', rid, pv)
    WHEN p < 0 OR p > 1 THEN printf('p of row %s = %s is outside 0 to 1', rid, p)
    WHEN atom = '' OR atom GLOB '*[^A-Za-z0-9_(),.''+-]*' OR lower(atom) IN ('and', 'or', 'not', 'true', 'false') OR substr(atom, 1, 1) IN ('(', ')', ',')
         OR (instr(atom, '(') > 0 AND substr(atom, -1) <> ')') OR (instr(atom, ')') > 0 AND instr(atom, '(') = 0) THEN printf('the atom of row %s is not one atom: %s', rid, json_quote(raw))
    WHEN atom GLOB '*([A-Z_]*' OR atom GLOB '*,[A-Z_]*' THEN printf('the atom %s of row %s has a variable; a clause is ground here', atom, rid) END
FROM r5 WHERE rid NOT IN (SELECT rid FROM lv)
UNION ALL
SELECT ?1, k, 'r' || (k + 1), replace(replace(replace(replace(raw, ' ', ''), char(9), ''), char(10), ''), char(13), ''), p,
  CASE WHEN p < 0 OR p > 1 THEN printf('p of row r%d = %s is outside 0 to 1', k + 1, p)
       WHEN replace(raw, ' ', '') = '' OR replace(raw, ' ', '') GLOB '*[^A-Za-z0-9_(),.''+-]*' OR lower(raw) IN ('and', 'or', 'not', 'true', 'false') THEN printf('%s is not one atom', json_quote(raw))
       WHEN replace(raw, ' ', '') GLOB '*([A-Z_]*' OR replace(raw, ' ', '') GLOB '*,[A-Z_]*' THEN printf('the atom %s has a variable; a clause is ground here', raw) END
FROM dr WHERE 'r' || (k + 1) NOT IN (SELECT rid FROM lv)
UNION ALL
SELECT ?1, -1, NULL, NULL, NULL, CASE kind WHEN 'text' THEN 'the state is not JSON: a state in ProbLog text is clauses (jev C5, not built in the judge brain yet); give it as JSON rows {"atom": <atom>, "p": <p>} or {"<atom>": <p>}'
  ELSE 'a state is a list of rows or {"rows": [...]}' END FROM sh WHERE kind IN ('text', 'other')
UNION ALL
SELECT ?1, -2, NULL, NULL, NULL, 'the state holds soft rules: weighted rules are jev C6, not built in the judge brain yet' FROM sh
WHERE kind IN ('$.rows', '$.clauses') AND nrules > 0
-- ;; rule 4 the state's errors and a row id given twice
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, -1, e FROM (SELECT err AS e FROM cx.judge_jevfact WHERE ask = ?1 AND err IS NOT NULL
  UNION ALL SELECT printf('the row id %s is twice in the state', rid) FROM cx.judge_jevfact WHERE ask = ?1 AND rid IS NOT NULL GROUP BY rid HAVING count(*) > 1)
-- ;; rule 5 the tokens of each question, read one at a time from where the last one ended
INSERT INTO cx.judge_jevtok (ask, qi, k, t, a)
WITH RECURSIVE
qq AS (SELECT qi, form AS s, length(form) AS n FROM cx.judge_jevq WHERE ask = ?1 AND qid IS NOT NULL AND qid <> '' AND form IS NOT NULL AND form <> ''),
nums(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM nums WHERE i < (SELECT max(n) FROM qq)),
p0 AS (SELECT qq.qi, nums.i, qq.s, qq.n, substr(qq.s, nums.i, 1) AS c1, substr(qq.s, nums.i, 2) AS c2, substr(qq.s, nums.i, 3) AS c3,
    length(substr(qq.s, nums.i)) - length(ltrim(substr(qq.s, nums.i), 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')) AS L
  FROM qq JOIN nums ON nums.i <= qq.n),
p1 AS (SELECT p0.*, substr(s, i, L) AS nm, lower(substr(s, i, L)) AS kw, i + L AS e, instr(substr(s, i + L), ')') AS cp FROM p0),
p2 AS (SELECT p1.*,
    CASE WHEN c1 IN (' ', char(9), char(10), char(13)) THEN 1 WHEN c3 IN ('<=>', '<->') THEN 3 WHEN c2 IN ('=>', '->', '\+') THEN 2
         WHEN c1 IN ('!', '~', '&', '^', ',', '|', '(', ')') THEN 1 WHEN L = 0 THEN 0 WHEN kw IN ('and', 'or', 'not', 'true', 'false') THEN L
         WHEN substr(s, e, 1) = '(' THEN CASE WHEN cp = 0 THEN 0 ELSE L + cp END ELSE L END AS tl,
    CASE WHEN c1 IN (' ', char(9), char(10), char(13)) THEN NULL WHEN c3 IN ('<=>', '<->') THEN '<=>' WHEN c2 IN ('=>', '->') THEN '=>' WHEN c2 = '\+' THEN '!'
         WHEN c1 IN ('!', '~') THEN '!' WHEN c1 IN ('&', '^', ',') THEN '&' WHEN c1 IN ('|', '(', ')') THEN c1 WHEN L = 0 THEN '?'
         WHEN kw = 'and' THEN '&' WHEN kw = 'or' THEN '|' WHEN kw = 'not' THEN '!' WHEN kw = 'true' THEN 'T' WHEN kw = 'false' THEN 'F'
         WHEN substr(s, e, 1) = '(' AND cp = 0 THEN '?' ELSE 'A' END AS t FROM p1),
p3 AS (SELECT qi, i, n, tl, t, CASE WHEN t = '?' THEN substr(s, i, 12)
    WHEN t = 'A' AND substr(s, e, 1) = '(' THEN nm || '(' || replace(replace(replace(replace(substr(s, e + 1, cp - 2), ' ', ''), char(9), ''), char(10), ''), char(13), '') || ')'
    WHEN t = 'A' THEN nm END AS a FROM p2),
lx(qi, i) AS (SELECT qi, 1 FROM qq UNION ALL SELECT lx.qi, lx.i + p.tl FROM lx JOIN p3 p ON p.qi = lx.qi AND p.i = lx.i WHERE p.tl > 0 AND lx.i + p.tl <= p.n)
SELECT ?1, lx.qi, row_number() OVER (PARTITION BY lx.qi ORDER BY lx.i), p.t, p.a FROM lx JOIN p3 p ON p.qi = lx.qi AND p.i = lx.i WHERE p.t IS NOT NULL
-- ;; rule 6 a question that cannot be read, or that names a variable
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, t.qi, CASE WHEN t.t = '?' THEN printf('question %s: cannot read %s at %s', q.qid, json_quote(q.form), json_quote(t.a))
  ELSE printf('question %s: an argument of %s is a variable; a question is ground', q.qid, t.a) END
FROM cx.judge_jevtok t JOIN cx.judge_jevq q ON q.ask = t.ask AND q.qi = t.qi
WHERE t.ask = ?1 AND (t.t = '?' OR (t.t = 'A' AND (t.a GLOB '*([A-Z_]*' OR t.a GLOB '*,[A-Z_]*')))
-- ;; rule 7 the atoms of each question: pf = the product of (1 - p) over the atom's rows with p > 0 in row order; uncertain when 0 < pf < 1, numbered u in sorted order
INSERT INTO cx.judge_jevqa (ask, qi, atom, pf, u)
WITH RECURSIVE
f AS (SELECT k, atom, p, row_number() OVER (PARTITION BY atom ORDER BY k) AS j FROM cx.judge_jevfact WHERE ask = ?1 AND k >= 0 AND err IS NULL AND p > 0),
pp(atom, j, v) AS (SELECT atom, 1, 1.0 - p FROM f WHERE j = 1 UNION ALL SELECT pp.atom, f.j, pp.v * (1.0 - f.p) FROM pp JOIN f ON f.atom = pp.atom AND f.j = pp.j + 1),
pa AS (SELECT pp.atom, pp.v FROM pp JOIN (SELECT atom, max(j) AS mj FROM f GROUP BY atom) z ON z.atom = pp.atom AND z.mj = pp.j),
qa AS (SELECT DISTINCT qi, a AS atom FROM cx.judge_jevtok WHERE ask = ?1 AND t = 'A'),
qv AS (SELECT qa.qi, qa.atom, pa.v AS pf FROM qa LEFT JOIN pa ON pa.atom = qa.atom)
SELECT ?1, qi, atom, pf, CASE WHEN pf > 0 AND pf < 1 THEN (SELECT count(*) FROM qv q2 WHERE q2.qi = qv.qi AND q2.pf > 0 AND q2.pf < 1 AND q2.atom < qv.atom) END FROM qv
-- ;; rule 8 exact inference is bounded: at most 16 uncertain atoms in one answer
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, q.qi, printf('question %s: the answer depends on %d uncertain atoms; exact inference is bounded at 16', q.qid, count(*))
FROM cx.judge_jevqa qa JOIN cx.judge_jevq q ON q.ask = qa.ask AND q.qi = qa.qi WHERE qa.ask = ?1 AND qa.u IS NOT NULL GROUP BY q.qi, q.qid HAVING count(*) > 16
-- ;; rule 9 each formula in postfix (precedence not 5, and 4, or 3, => 2 right, <=> 1), each atom a leaf: b<u> uncertain, 1 certain, 0 no row; every operator with its operands
INSERT INTO cx.judge_jevx (ask, qi, nu, rpn, err)
WITH RECURSIVE
gq AS (SELECT q.qi, q.qid, q.form FROM cx.judge_jevq q WHERE q.ask = ?1 AND q.qid IS NOT NULL AND q.qid <> '' AND q.form IS NOT NULL AND q.form <> ''
  AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.qi = q.qi AND o.err IS NOT NULL)),
tk AS (SELECT t.qi, t.k, t.t, CASE t.t WHEN 'T' THEN '1' WHEN 'F' THEN '0' WHEN 'A' THEN (SELECT CASE WHEN qa.u IS NOT NULL THEN 'b' || qa.u WHEN qa.pf IS NOT NULL AND qa.pf <= 0 THEN '1' ELSE '0' END
    FROM cx.judge_jevqa qa WHERE qa.ask = ?1 AND qa.qi = t.qi AND qa.atom = t.a) END AS leaf FROM cx.judge_jevtok t WHERE t.ask = ?1 AND t.qi IN (SELECT qi FROM gq)),
mx AS (SELECT gq.qi, (SELECT count(*) FROM tk WHERE tk.qi = gq.qi) AS m FROM gq),
pr(o, p, r) AS (VALUES ('!', 5, 1), ('&', 4, 0), ('|', 3, 0), ('=>', 2, 1), ('<=>', 1, 0)),
sy(qi, k, m, oq, st, err) AS (
  SELECT qi, 1, m, '[]', '[]', CASE WHEN m = 0 THEN 'an empty formula' END FROM mx
  UNION ALL
  SELECT sy.qi,
    CASE WHEN tk.t IN ('A', 'T', 'F', '(', '!') THEN sy.k + 1
         WHEN json_extract(sy.st, '$[#-1]') IS NOT NULL AND json_extract(sy.st, '$[#-1]') <> '(' AND (tk.t IS NULL OR tk.t = ')'
              OR (SELECT p FROM pr WHERE o = json_extract(sy.st, '$[#-1]')) > (SELECT p FROM pr WHERE o = tk.t)
              OR ((SELECT p FROM pr WHERE o = json_extract(sy.st, '$[#-1]')) = (SELECT p FROM pr WHERE o = tk.t) AND (SELECT r FROM pr WHERE o = tk.t) = 0)) THEN sy.k
         ELSE sy.k + 1 END,
    sy.m,
    CASE WHEN tk.t IN ('A', 'T', 'F') THEN json_insert(sy.oq, '$[#]', tk.leaf)
         WHEN tk.t IN ('(', '!') THEN sy.oq
         WHEN json_extract(sy.st, '$[#-1]') IS NOT NULL AND json_extract(sy.st, '$[#-1]') <> '(' AND (tk.t IS NULL OR tk.t = ')'
              OR (SELECT p FROM pr WHERE o = json_extract(sy.st, '$[#-1]')) > (SELECT p FROM pr WHERE o = tk.t)
              OR ((SELECT p FROM pr WHERE o = json_extract(sy.st, '$[#-1]')) = (SELECT p FROM pr WHERE o = tk.t) AND (SELECT r FROM pr WHERE o = tk.t) = 0)) THEN json_insert(sy.oq, '$[#]', json_extract(sy.st, '$[#-1]'))
         ELSE sy.oq END,
    CASE WHEN tk.t IN ('A', 'T', 'F') THEN sy.st
         WHEN tk.t IN ('(', '!') THEN json_insert(sy.st, '$[#]', tk.t)
         WHEN json_extract(sy.st, '$[#-1]') IS NOT NULL AND json_extract(sy.st, '$[#-1]') <> '(' AND (tk.t IS NULL OR tk.t = ')'
              OR (SELECT p FROM pr WHERE o = json_extract(sy.st, '$[#-1]')) > (SELECT p FROM pr WHERE o = tk.t)
              OR ((SELECT p FROM pr WHERE o = json_extract(sy.st, '$[#-1]')) = (SELECT p FROM pr WHERE o = tk.t) AND (SELECT r FROM pr WHERE o = tk.t) = 0)) THEN json_remove(sy.st, '$[#-1]')
         WHEN tk.t = ')' THEN json_remove(sy.st, '$[#-1]')
         WHEN tk.t IS NOT NULL THEN json_insert(sy.st, '$[#]', tk.t)
         ELSE sy.st END,
    CASE WHEN tk.t = ')' AND json_extract(sy.st, '$[#-1]') IS NULL THEN 'a ) with no (' WHEN tk.t IS NULL AND json_extract(sy.st, '$[#-1]') = '(' THEN 'a ( with no )' END
  FROM sy LEFT JOIN tk ON tk.qi = sy.qi AND tk.k = sy.k
  WHERE sy.err IS NULL AND (sy.k <= sy.m OR json_array_length(sy.st) > 0)),
fin AS (SELECT qi, oq, err FROM sy WHERE err IS NOT NULL OR (k > m AND json_array_length(st) = 0)),
dv AS (SELECT fin.qi, CAST(je.key AS INTEGER) AS j, CASE WHEN je.value IN ('&', '|', '=>', '<=>') THEN -1 WHEN je.value = '!' THEN 0 ELSE 1 END AS d FROM fin, json_each(fin.oq) je WHERE fin.err IS NULL),
dd AS (SELECT qi, d, sum(d) OVER (PARTITION BY qi ORDER BY j) AS run FROM dv),
ar AS (SELECT qi, min(run) AS mn, sum(d) AS tot FROM dd GROUP BY qi)
SELECT ?1, gq.qi, (SELECT count(*) FROM cx.judge_jevqa qa WHERE qa.ask = ?1 AND qa.qi = gq.qi AND qa.u IS NOT NULL),
  CASE WHEN fin.err IS NULL AND ar.mn >= 1 AND ar.tot = 1 THEN fin.oq END,
  CASE WHEN fin.qi IS NULL THEN printf('question %s: cannot read %s', gq.qid, json_quote(gq.form))
       WHEN fin.err IS NOT NULL THEN printf('question %s: %s in %s', gq.qid, fin.err, json_quote(gq.form))
       WHEN ar.mn IS NULL OR ar.mn < 1 OR ar.tot <> 1 THEN printf('question %s: cannot read %s', gq.qid, json_quote(gq.form)) END
FROM gq LEFT JOIN fin ON fin.qi = gq.qi LEFT JOIN ar ON ar.qi = gq.qi
-- ;; rule 10 a formula that does not parse
INSERT INTO cx.judge_jevout (ask, qi, err) SELECT ?1, qi, err FROM cx.judge_jevx WHERE ask = ?1 AND err IS NOT NULL
-- ;; rule 11 the answers: the formula run over 64 worlds a word (atom u < 6 a fixed pattern, u >= 6 the word's own bit), the worlds weighted in u order, p = the weight where it holds
INSERT INTO cx.judge_jevout (ask, qi, p, line)
WITH RECURSIVE
ok AS (SELECT x.qi, x.nu, x.rpn FROM cx.judge_jevx x WHERE x.ask = ?1 AND x.rpn IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)
  AND NOT EXISTS (SELECT 1 FROM cx.judge_jevask c WHERE c.parent = ?1)),
it AS (SELECT ok.qi, CAST(je.key AS INTEGER) + 1 AS j, je.value AS v FROM ok, json_each(ok.rpn) je),
nit AS (SELECT qi, count(*) AS n FROM it GROUP BY qi),
pat(u, b) AS (VALUES (0, 0xAAAAAAAAAAAAAAAA), (1, 0xCCCCCCCCCCCCCCCC), (2, 0xF0F0F0F0F0F0F0F0), (3, 0xFF00FF00FF00FF00), (4, 0xFFFF0000FFFF0000), (5, 0xFFFFFFFF00000000)),
ch(qi, c, nc) AS (SELECT qi, 0, CASE WHEN nu > 6 THEN 1 << (nu - 6) ELSE 1 END FROM ok UNION ALL SELECT qi, c + 1, nc FROM ch WHERE c + 1 < nc),
ev(qi, c, j, st) AS (SELECT qi, c, 1, '[]' FROM ch
  UNION ALL
  SELECT ev.qi, ev.c, ev.j + 1, CASE
    WHEN it.v = '1' THEN json_insert(ev.st, '$[#]', -1)
    WHEN it.v = '0' THEN json_insert(ev.st, '$[#]', 0)
    WHEN substr(it.v, 1, 1) = 'b' THEN json_insert(ev.st, '$[#]', CASE WHEN CAST(substr(it.v, 2) AS INTEGER) < 6 THEN (SELECT b FROM pat WHERE u = CAST(substr(it.v, 2) AS INTEGER))
                                                                 ELSE -((ev.c >> (CAST(substr(it.v, 2) AS INTEGER) - 6)) & 1) END)
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
  SELECT wd.qi, wd.i + 1, wd.m + (bits.v << wd.i), wd.w * CASE bits.v WHEN 1 THEN 1.0 - qa.pf ELSE qa.pf END
  FROM wd JOIN cx.judge_jevqa qa ON qa.ask = ?1 AND qa.qi = wd.qi AND qa.u = wd.i JOIN bits),
tot AS (SELECT wd.qi, total(wd.w) AS p FROM wd JOIN ok ON ok.qi = wd.qi AND wd.i = ok.nu JOIN res ON res.qi = wd.qi AND res.c = (wd.m >> 6)
  WHERE ((res.r >> (wd.m & 63)) & 1) = 1 GROUP BY wd.qi),
fm AS (SELECT ok.qi, coalesce(tot.p, 0.0) AS p, rtrim(printf('%.12f', min(1.0, max(0.0, coalesce(tot.p, 0.0)))), '0') AS s FROM ok LEFT JOIN tot ON tot.qi = ok.qi)
SELECT ?1, fm.qi, fm.p, q.qid || ' noul=' || CASE WHEN substr(fm.s, -1) = '.' THEN fm.s || '0' ELSE fm.s END FROM fm JOIN cx.judge_jevq q ON q.ask = ?1 AND q.qi = fm.qi
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
