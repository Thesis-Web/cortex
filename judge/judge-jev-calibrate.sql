-- judge-jev-calibrate.sql (2026-11-10, jev C10): cortex jev calibrate in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- A jury of independent judge samples pooled into one p by self-consistency (wang-2023-self-consistency.txt:207; verga-2024-juries-not-judges.txt:250): a question's p
-- given as p, or as samples of true and false (the fraction true), or as a jury of p's (their mean); checked for calibration against its held-out label
-- (kadavath-2022 :1271; zheng-2023 :718): the questions bucketed by p into k equal bins (bin = min(k - 1, floor(p k))), one line a bucket that holds questions,
-- bucket=<lo-hi> n= mean_p= freq=, then ece= the sum over buckets of n/N |mean_p - freq|. The set file: JSON (a list, {"set": [...]} or {"questions": [...]}) or JSON lines,
-- each {"id", "label": true|false, "p" | "samples" | "jury" | "votes"}; the bins in the request's rules column (default 10). Lay: python3 work/jev/lay.py calibrate
-- ;; ddl
CREATE TABLE IF NOT EXISTS cx.judge_jevcal (ask INTEGER NOT NULL, k INTEGER NOT NULL, qid TEXT, p REAL, y INTEGER, bin INTEGER, err TEXT, PRIMARY KEY (ask, k))
-- ;; rule 801 the questions: each one's pooled p, its label and its bin, or why it cannot be read
INSERT INTO cx.judge_jevcal (ask, k, qid, p, y, bin, err)
WITH RECURSIVE
a AS (SELECT coalesce(state, '') AS s, CASE WHEN coalesce(rules, '') = '' THEN 10 WHEN rules GLOB '*[^0-9]*' THEN NULL ELSE CAST(rules AS INTEGER) END AS bins FROM cx.judge_jevask WHERE id = ?1),
ln(n, rest, line) AS (SELECT 0, s || char(10), NULL FROM a WHERE NOT json_valid(s)
  UNION ALL SELECT n + 1, substr(rest, instr(rest, char(10)) + 1), substr(rest, 1, instr(rest, char(10)) - 1) FROM ln WHERE rest <> ''),
jl AS (SELECT json_group_array(CASE WHEN json_valid(trim(line)) THEN json(trim(line)) ELSE trim(line) END) AS s, sum(NOT json_valid(trim(line))) AS bad FROM ln WHERE line IS NOT NULL AND trim(line) <> ''),
src AS (SELECT CASE WHEN json_valid(a.s) THEN CASE WHEN json_type(a.s) = 'array' THEN a.s WHEN json_type(a.s) = 'object' AND json_type(a.s, '$.set') = 'array' THEN json_extract(a.s, '$.set')
    WHEN json_type(a.s) = 'object' AND json_type(a.s, '$.questions') = 'array' THEN json_extract(a.s, '$.questions') END
  WHEN (SELECT bad FROM jl) = 0 THEN (SELECT s FROM jl) END AS items, a.bins FROM a),
it AS (SELECT CAST(e.key AS INTEGER) AS k, e.type AS ty, e.value AS v, src.bins FROM src, json_each(coalesce(src.items, '[]')) e),
i1 AS (SELECT k, ty, v, bins, CASE WHEN ty = 'object' AND json_type(v, '$.id') IS NOT NULL AND json_type(v, '$.id') <> 'null' THEN CAST(json_extract(v, '$.id') AS TEXT) ELSE CAST(k + 1 AS TEXT) END AS qid,
    CASE WHEN ty = 'object' THEN coalesce(json_extract(v, '$.samples'), json_extract(v, '$.jury'), json_extract(v, '$.votes')) END AS sm,
    CASE WHEN ty = 'object' THEN coalesce(json_type(v, '$.samples'), json_type(v, '$.jury'), json_type(v, '$.votes')) END AS smt,
    CASE WHEN ty = 'object' THEN json_type(v, '$.p') END AS pt, CASE WHEN ty = 'object' THEN json_type(v, '$.label') END AS lt, CASE WHEN ty = 'object' THEN json_extract(v, '$.label') END AS lv FROM it),
i2 AS (SELECT i1.*,
    CASE WHEN pt IS NOT NULL THEN CASE WHEN pt IN ('integer', 'real') THEN json_extract(v, '$.p') END
      WHEN smt = 'array' AND json_array_length(sm) > 0 AND NOT EXISTS (SELECT 1 FROM json_each(sm) x WHERE x.type NOT IN ('true', 'false'))
        THEN (SELECT CAST(sum(x.type = 'true') AS REAL) / count(*) FROM json_each(sm) x)
      WHEN smt = 'array' AND json_array_length(sm) > 0 AND NOT EXISTS (SELECT 1 FROM json_each(sm) x WHERE x.type NOT IN ('integer', 'real') OR x.value < 0 OR x.value > 1)
        THEN (SELECT total(x.value) / count(*) FROM json_each(sm) x) END AS p,
    CASE WHEN lt = 'true' THEN 1 WHEN lt = 'false' THEN 0 WHEN lt IN ('integer', 'real') AND lv IN (0, 1) THEN CAST(lv AS INTEGER)
      WHEN lt = 'text' AND lower(trim(lv)) IN ('true', 'yes', '1') THEN 1 WHEN lt = 'text' AND lower(trim(lv)) IN ('false', 'no', '0') THEN 0 END AS y FROM i1)
SELECT ?1, k, qid, p, y, CASE WHEN p IS NOT NULL AND p >= 0 AND p <= 1 AND bins >= 1 THEN min(bins - 1, CAST(p * bins AS INTEGER)) END, CASE
    WHEN bins IS NULL OR bins < 1 THEN '--bins is a whole number, at least 1'
    WHEN ty <> 'object' THEN printf('question %d is not an object', k + 1)
    WHEN pt IS NULL AND (smt IS NULL OR smt <> 'array' OR json_array_length(sm) = 0) THEN printf('question %s has no p and no samples', qid)
    WHEN p IS NULL THEN printf('question %s: its p or its samples are not numbers in 0 to 1 or true and false', qid)
    WHEN p < 0 OR p > 1 THEN printf('question %s: p = %s is outside 0 to 1', qid, p)
    WHEN y IS NULL THEN printf('question %s: the label %s is not true or false', qid, coalesce(json_quote(lv), 'null')) END
FROM i2
UNION ALL
SELECT ?1, -1, NULL, NULL, NULL, NULL, 'the set is neither JSON nor JSON lines, or holds no labelled question' FROM src WHERE items IS NULL OR json_array_length(items) = 0
-- ;; rule 802 the set's errors
INSERT INTO cx.judge_jevout (ask, qi, err) SELECT ?1, k, err FROM cx.judge_jevcal WHERE ask = ?1 AND err IS NOT NULL
-- ;; rule 803 one line a bucket that holds questions, in bin order: bucket=<lo-hi> n= mean_p= freq=; then ece=
INSERT INTO cx.judge_jevout (ask, qi, p, line)
WITH ok AS (SELECT 1 AS z WHERE NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
bn AS (SELECT CASE WHEN coalesce(rules, '') = '' THEN 10 ELSE CAST(rules AS INTEGER) END AS bins FROM cx.judge_jevask WHERE id = ?1),
q AS (SELECT p, y, bin FROM cx.judge_jevcal, ok WHERE ask = ?1 AND k >= 0),
b AS (SELECT bin, count(*) AS n, total(p) / count(*) AS mp, CAST(sum(y) AS REAL) / count(*) AS fq FROM q GROUP BY bin),
nn AS (SELECT count(*) AS n FROM q),
fm AS (SELECT b.bin, b.n, b.mp, b.fq, rtrim(printf('%.12f', CAST(b.bin AS REAL) / bn.bins), '0') AS lo, rtrim(printf('%.12f', CAST(b.bin + 1 AS REAL) / bn.bins), '0') AS hi,
    rtrim(printf('%.12f', b.mp), '0') AS smp, rtrim(printf('%.12f', b.fq), '0') AS sfq FROM b, bn),
ec AS (SELECT total(CAST(b.n AS REAL) / nn.n * abs(b.mp - b.fq)) AS e FROM b, nn WHERE nn.n > 0),
fe AS (SELECT e, rtrim(printf('%.12f', min(1.0, max(0.0, e))), '0') AS s FROM ec)
SELECT ?1, fm.bin, NULL, 'bucket=' || CASE WHEN substr(lo, -1) = '.' THEN lo || '0' ELSE lo END || '-' || CASE WHEN substr(hi, -1) = '.' THEN hi || '0' ELSE hi END
  || ' n=' || fm.n || ' mean_p=' || CASE WHEN substr(smp, -1) = '.' THEN smp || '0' ELSE smp END || ' freq=' || CASE WHEN substr(sfq, -1) = '.' THEN sfq || '0' ELSE sfq END FROM fm
UNION ALL
SELECT ?1, 1000000, fe.e, 'ece=' || CASE WHEN substr(fe.s, -1) = '.' THEN fe.s || '0' ELSE fe.s END FROM fe, nn WHERE nn.n > 0
