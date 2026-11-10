-- judge-jev-verify.sql (2026-11-10, jev C9): cortex jev verify in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- Claim verification (thorne-2018-fever.txt:16; min-2023-factscore.txt:56; citation_check.md:9): the claim split into atomic facts (one a line; a one-line claim cut at ;
-- and at sentence ends, then a span of parts that is one source row, copied or changed a little, is one fact again), each fact checked against the source rows,
-- never against a correct answer: supported (the row's words, or the row holds the fact's 8 or more words in order), refuted (a row holding 70% of its words says the
-- opposite: a negation, another number, another word in the same place), else nei (not enough info); one line <fact> label= row=<path:line or none> a fact,
-- then score=<supported / facts>. The request carries the claim (qs) and the source's rows as typed by the verb from the source (state: [{path, source, line, text}]).
-- Words: lower case [a-z0-9]+ joined by ' . , inside. Lay: python3 work/jev/lay.py verify
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevtx (ask INTEGER NOT NULL, kind TEXT NOT NULL, i INTEGER NOT NULL, wh TEXT, text TEXT, PRIMARY KEY (ask, kind, i))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevtt (ask INTEGER NOT NULL, kind TEXT NOT NULL, i INTEGER NOT NULL, toks TEXT, n INTEGER, PRIMARY KEY (ask, kind, i))
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevvf (ask INTEGER NOT NULL, f INTEGER NOT NULL, text TEXT, toks TEXT, n INTEGER, PRIMARY KEY (ask, f))
-- ;; rule 701 the texts: the source's rows (kind r, in source order, each with its path:line) and the claim's parts (kind p: its lines, or a one-line claim cut at ; and at sentence ends; kind l marks a claim of several lines)
INSERT INTO cx.judge_jevtx (ask, kind, i, wh, text)
WITH RECURSIVE
a AS (SELECT state, json_extract(qs, '$[0]') AS claim FROM cx.judge_jevask WHERE id = ?1),
rr AS (SELECT CAST(e.key AS INTEGER) AS i, e.value AS v FROM a, json_each(CASE WHEN json_valid(a.state) AND json_type(a.state) = 'array' THEN a.state ELSE '[]' END) e),
ln(n, rest, line) AS (SELECT 0, replace(coalesce(claim, ''), char(13), '') || char(10), NULL FROM a
  UNION ALL SELECT n + 1, substr(rest, instr(rest, char(10)) + 1), substr(rest, 1, instr(rest, char(10)) - 1) FROM ln WHERE rest <> ''),
ls AS (SELECT row_number() OVER (ORDER BY n) AS i, trim(line, ' ' || char(9)) AS t FROM ln WHERE line IS NOT NULL AND trim(line, ' ' || char(9)) <> ''),
one AS (SELECT t AS s, length(t) AS n FROM ls WHERE (SELECT count(*) FROM ls) = 1),
nums(k) AS (SELECT 1 UNION ALL SELECT k + 1 FROM nums WHERE k < (SELECT coalesce(max(n), 0) FROM one)),
ch AS (SELECT nums.k, substr(one.s, nums.k, 1) AS c FROM one JOIN nums ON nums.k <= one.n),
c2 AS (SELECT k, c, CASE WHEN lag(c) OVER (ORDER BY k) = ';' OR (lag(c) OVER (ORDER BY k) IN ('.', '!', '?') AND c IN (' ', char(9))) THEN 1 ELSE 0 END AS cut FROM ch),
c3 AS (SELECT k, c, sum(cut) OVER (ORDER BY k ROWS UNBOUNDED PRECEDING) AS pi FROM c2),
pt AS (SELECT pi, trim(group_concat(CASE WHEN c = ';' THEN '' ELSE c END, '' ORDER BY k), ' ' || char(9)) AS t FROM c3 GROUP BY pi)
SELECT ?1, 'r', i, coalesce(nullif(CAST(json_extract(v, '$.path') AS TEXT), ''), nullif(CAST(json_extract(v, '$.source') AS TEXT), ''), '-') || ':' || coalesce(CAST(json_extract(v, '$.line') AS TEXT), '-'),
  CAST(json_extract(v, '$.text') AS TEXT) FROM rr WHERE json_type(v, '$.text') IS NOT NULL
UNION ALL SELECT ?1, 'p', row_number() OVER (ORDER BY pi), NULL, t FROM pt WHERE t <> ''
UNION ALL SELECT ?1, 'l', i, NULL, t FROM ls WHERE (SELECT count(*) FROM ls) > 1
-- ;; rule 702 the words of every text: lower case runs of [a-z0-9], a ' . or , inside a run when a letter or digit is on both sides
INSERT INTO cx.judge_jevtt (ask, kind, i, toks, n)
WITH RECURSIVE
tx AS (SELECT kind, i, lower(replace(text, '’', '''')) AS s, length(text) AS n FROM cx.judge_jevtx WHERE ask = ?1),
nums(k) AS (SELECT 1 UNION ALL SELECT k + 1 FROM nums WHERE k < (SELECT coalesce(max(n), 0) FROM tx)),
ch AS (SELECT tx.kind, tx.i, nums.k, substr(tx.s, nums.k, 1) AS c FROM tx JOIN nums ON nums.k <= tx.n),
c1 AS (SELECT kind, i, k, c, (c GLOB '[a-z0-9]') AS al FROM ch),
c2 AS (SELECT kind, i, k, c, al, lag(al, 1, 0) OVER w AS pal, lead(al, 1, 0) OVER w AS nal FROM c1 WINDOW w AS (PARTITION BY kind, i ORDER BY k)),
c3 AS (SELECT kind, i, k, c, (al OR (c IN ('''', '.', ',') AND pal AND nal)) AS t FROM c2),
c4 AS (SELECT kind, i, k, c, t, lag(t, 1, 0) OVER (PARTITION BY kind, i ORDER BY k) AS pt FROM c3),
c5 AS (SELECT kind, i, k, c, t, sum(t AND NOT pt) OVER (PARTITION BY kind, i ORDER BY k ROWS UNBOUNDED PRECEDING) AS tk FROM c4),
tok AS (SELECT kind, i, tk, group_concat(c, '' ORDER BY k) AS w FROM c5 WHERE t GROUP BY kind, i, tk)
SELECT ?1, tx.kind, tx.i, coalesce((SELECT json_group_array(w ORDER BY tk) FROM tok WHERE tok.kind = tx.kind AND tok.i = tx.i), '[]'),
  (SELECT count(*) FROM tok WHERE tok.kind = tx.kind AND tok.i = tx.i) FROM tx
-- ;; rule 703 the facts: a claim of several lines, one a line; a one-line claim's parts left to right, the longest span of up to 6 parts that is one source row (its words) or near one (a row and the span sharing 80% of each one's words) one fact, else one part; a fact with no word is left out
INSERT INTO cx.judge_jevvf (ask, f, text, toks, n)
WITH RECURSIVE
pp AS (SELECT p.i, x.text, p.toks, p.n FROM cx.judge_jevtt p JOIN cx.judge_jevtx x ON x.ask = ?1 AND x.kind = 'p' AND x.i = p.i WHERE p.ask = ?1 AND p.kind = 'p'),
m AS (SELECT count(*) AS m FROM pp),
rw AS MATERIALIZED (SELECT i, toks, n FROM cx.judge_jevtt WHERE ask = ?1 AND kind = 'r'),
rc AS MATERIALIZED (SELECT rw.i, je.value AS w, count(*) AS c FROM rw, json_each(rw.toks) je GROUP BY rw.i, je.value),
sp AS (SELECT a.i, b.i + 1 AS j, (SELECT group_concat(x.text, ' ') FROM (SELECT text FROM pp p3 WHERE p3.i BETWEEN a.i AND b.i ORDER BY p3.i) x) AS text,
    (SELECT json_group_array(je.value) FROM (SELECT p3.i, je.key, je.value FROM pp p3, json_each(p3.toks) je WHERE p3.i BETWEEN a.i AND b.i ORDER BY p3.i, je.key) je) AS toks
  FROM pp a JOIN pp b ON b.i BETWEEN a.i + 1 AND a.i + 5),
sc AS MATERIALIZED (SELECT sp.i, sp.j, je.value AS w, count(*) AS c FROM sp, json_each(sp.toks) je GROUP BY sp.i, sp.j, je.value),
sn AS (SELECT sp.i, sp.j, json_array_length(sp.toks) AS n FROM sp),
ok AS (SELECT sp.i, sp.j FROM sp JOIN sn ON sn.i = sp.i AND sn.j = sp.j WHERE sn.n > 0 AND (EXISTS (SELECT 1 FROM rw WHERE rw.toks = sp.toks)
    OR EXISTS (SELECT 1 FROM rw WHERE rw.n > 0 AND (SELECT total(min(sc.c, rc.c)) FROM sc JOIN rc ON rc.w = sc.w AND rc.i = rw.i WHERE sc.i = sp.i AND sc.j = sp.j) >= 0.8 * max(sn.n, rw.n)))),
g(i, j) AS (SELECT 1, coalesce((SELECT max(ok.j) FROM ok WHERE ok.i = 1), 2) FROM m WHERE m.m > 0
  UNION ALL SELECT g.j, coalesce((SELECT max(ok.j) FROM ok WHERE ok.i = g.j), g.j + 1) FROM g, m WHERE g.j <= m.m),
fa AS (SELECT g.i, (SELECT group_concat(x.text, ' ') FROM (SELECT text FROM pp p3 WHERE p3.i >= g.i AND p3.i < g.j ORDER BY p3.i) x) AS text,
    (SELECT json_group_array(je.value) FROM (SELECT p3.i, je.key, je.value FROM pp p3, json_each(p3.toks) je WHERE p3.i >= g.i AND p3.i < g.j ORDER BY p3.i, je.key) je) AS toks FROM g)
SELECT ?1, row_number() OVER (ORDER BY i), text, toks, json_array_length(toks) FROM fa WHERE json_array_length(toks) > 0
UNION ALL
SELECT ?1, x.i, x.text, t.toks, t.n FROM cx.judge_jevtx x JOIN cx.judge_jevtt t ON t.ask = ?1 AND t.kind = 'l' AND t.i = x.i WHERE x.ask = ?1 AND x.kind = 'l'
-- ;; rule 704 a claim with no fact, a source with no row
INSERT INTO cx.judge_jevout (ask, qi, err)
SELECT ?1, -1, 'the claim holds no fact' WHERE NOT EXISTS (SELECT 1 FROM cx.judge_jevvf WHERE ask = ?1)
UNION ALL SELECT ?1, -2, 'the source holds no row with text' WHERE NOT EXISTS (SELECT 1 FROM cx.judge_jevtx WHERE ask = ?1 AND kind = 'r')
-- ;; rule 705 each fact's label against the rows: supported (a row's words, or for 8 words or more a row holding them in order: the first such row), else the row sharing the most of both one's words; at 70% or more refuted when the words that differ hold a negation on one side only, other numbers, or as many other words in the same length; else nei; then score=
INSERT INTO cx.judge_jevout (ask, qi, p, line)
WITH ok AS (SELECT 1 AS z WHERE NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
fv AS MATERIALIZED (SELECT f, text, toks, n FROM cx.judge_jevvf, ok WHERE ask = ?1),
rw AS MATERIALIZED (SELECT t.i, t.toks, t.n, x.wh, ' ' || (SELECT group_concat(je.value, ' ' ORDER BY CAST(je.key AS INTEGER)) FROM json_each(t.toks) je) || ' ' AS js
  FROM cx.judge_jevtt t JOIN cx.judge_jevtx x ON x.ask = ?1 AND x.kind = 'r' AND x.i = t.i WHERE t.ask = ?1 AND t.kind = 'r'),
rc AS MATERIALIZED (SELECT rw.i, je.value AS w, count(*) AS c FROM rw, json_each(rw.toks) je GROUP BY rw.i, je.value),
fc AS MATERIALIZED (SELECT fv.f, je.value AS w, count(*) AS c FROM fv, json_each(fv.toks) je GROUP BY fv.f, je.value),
sm AS MATERIALIZED (SELECT fc.f, rc.i, total(min(fc.c, rc.c)) AS same FROM fc JOIN rc ON rc.w = fc.w GROUP BY fc.f, rc.i),
ex AS (SELECT fv.f, (SELECT rw.wh FROM rw WHERE rw.toks = fv.toks ORDER BY rw.i LIMIT 1) AS wh FROM fv),
ct AS (SELECT fv.f, (SELECT rw.wh FROM rw JOIN sm ON sm.f = fv.f AND sm.i = rw.i WHERE fv.n >= 8
    AND instr(rw.js, ' ' || (SELECT group_concat(je.value, ' ' ORDER BY CAST(je.key AS INTEGER)) FROM json_each(fv.toks) je) || ' ') > 0 ORDER BY sm.same DESC, rw.i LIMIT 1) AS wh FROM fv),
scs AS (SELECT sm.f, sm.i, sm.same, min(sm.same / fv.n, sm.same / max(1, rw.n)) AS sc, row_number() OVER (PARTITION BY sm.f ORDER BY min(sm.same / fv.n, sm.same / max(1, rw.n)) DESC, sm.same DESC, sm.i) AS rk
  FROM sm JOIN fv ON fv.f = sm.f JOIN rw ON rw.i = sm.i),
bs AS (SELECT fv.f, (SELECT scs.i FROM scs WHERE scs.f = fv.f AND scs.rk = 1) AS bi FROM fv),
bd AS (SELECT bs.f, bs.bi, rw.wh, rw.n AS rn, fv.n AS fn, sm.same, min(sm.same / fv.n, sm.same / max(1, rw.n)) AS sc FROM bs JOIN fv ON fv.f = bs.f JOIN rw ON rw.i = bs.bi JOIN sm ON sm.f = bs.f AND sm.i = bs.bi),
neg(w) AS (VALUES ('not'), ('no'), ('never'), ('cannot'), ('nor'), ('none'), ('nobody'), ('nothing'), ('neither'), ('without'), ('nowhere')),
fx AS (SELECT bd.f, fc.w, fc.c - coalesce((SELECT rc.c FROM rc WHERE rc.i = bd.bi AND rc.w = fc.w), 0) AS c FROM bd JOIN fc ON fc.f = bd.f),
rx AS (SELECT bd.f, rc.w, rc.c - coalesce((SELECT fc.c FROM fc WHERE fc.f = bd.f AND fc.w = rc.w), 0) AS c FROM bd JOIN rc ON rc.i = bd.bi),
df AS (SELECT bd.f,
    (SELECT total(c) FROM fx WHERE fx.f = bd.f AND c > 0 AND (w IN (SELECT w FROM neg) OR w LIKE '%n''t')) AS nfn, (SELECT total(c) FROM rx WHERE rx.f = bd.f AND c > 0 AND (w IN (SELECT w FROM neg) OR w LIKE '%n''t')) AS nrn,
    (SELECT group_concat(w || '*' || c, ' ' ORDER BY w) FROM fx WHERE fx.f = bd.f AND c > 0 AND w GLOB '[0-9]*') AS nfs, (SELECT group_concat(w || '*' || c, ' ' ORDER BY w) FROM rx WHERE rx.f = bd.f AND c > 0 AND w GLOB '[0-9]*') AS nrs,
    (SELECT total(c) FROM fx WHERE fx.f = bd.f AND c > 0) AS nf, (SELECT total(c) FROM rx WHERE rx.f = bd.f AND c > 0) AS nr FROM bd WHERE bd.sc >= 0.7),
lb AS (SELECT fv.f, fv.text, CASE WHEN ex.wh IS NOT NULL OR ct.wh IS NOT NULL THEN 'supported'
      WHEN df.f IS NOT NULL AND (CAST(df.nfn AS INTEGER) % 2 <> CAST(df.nrn AS INTEGER) % 2 OR (df.nfs IS NOT NULL AND df.nrs IS NOT NULL AND df.nfs <> df.nrs)
        OR (df.nf >= 1 AND df.nf = df.nr AND bd.fn = bd.rn)) THEN 'refuted' ELSE 'nei' END AS label,
    coalesce(ex.wh, ct.wh, CASE WHEN df.f IS NOT NULL THEN bd.wh END) AS wh FROM fv JOIN ex ON ex.f = fv.f JOIN ct ON ct.f = fv.f LEFT JOIN bd ON bd.f = fv.f LEFT JOIN df ON df.f = fv.f),
lt AS (SELECT f, text, label, CASE WHEN label = 'nei' THEN NULL ELSE wh END AS wh,
    trim(replace(replace(replace(replace(replace(replace(replace(text, char(9), ' '), char(10), ' '), char(13), ' '), '     ', ' '), '    ', ' '), '   ', ' '), '  ', ' ')) AS t1 FROM lb),
sc AS (SELECT CAST(sum(label = 'supported') AS REAL) / count(*) AS s FROM lt),
fs AS (SELECT s, rtrim(printf('%.12f', s), '0') AS t FROM sc)
SELECT ?1, f, NULL, replace(replace(t1, '  ', ' '), '  ', ' ') || ' label=' || label || ' row=' || coalesce(wh, 'none') FROM lt
UNION ALL SELECT ?1, 1000000, fs.s, 'score=' || CASE WHEN substr(fs.t, -1) = '.' THEN fs.t || '0' ELSE fs.t END FROM fs WHERE EXISTS (SELECT 1 FROM lt)
