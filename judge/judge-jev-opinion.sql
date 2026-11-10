-- judge-jev-opinion.sql (2026-11-10, jev C7): cortex jev opinion in the judge's brain. The owner, 11-06 14:46: "you would be writing code into the judges brain,
-- different brain .. you have tried py outside the brain 10 times and failed each time"; 11-09 00:48: "it would take zero code outside the db".
-- Each source row a subjective-logic opinion (belief, disbelief, uncertainty, base rate) weighted by the trust in its source (josang-2001 :29, :31; subjective-logic :3):
-- problog's rule 103 reads the rows (for this verb a bare p is the dogmatic opinion (p, 1 - p, 0, 0.5)), discounts each by its trust and fuses them per head and
-- body (cumulative fusion); a trust 0 row is left out. One line a fused opinion, sorted by head and body: <atom> b= d= u= a= p=, p = b + a u, the projection the
-- noul of problog, mln and psl reads for an atom held by opinion rows. Lay: python3 work/jev/lay.py opinion (after the ask and problog).
-- ;; rule 401 the rows and their fused opinions: problog's rule 103, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 103 AND verb = 'problog'
-- ;; rule 402 the rows' errors: problog's rule 104, run by reference
SELECT mother(sql, ?1) FROM cx.judge_jevrule WHERE id = 104 AND verb = 'problog'
-- ;; rule 403 one line a fused opinion, sorted by head and body: <atom>[ :- <body>] b= d= u= a= p=
INSERT INTO cx.judge_jevout (ask, qi, p, line)
WITH f AS (SELECT head, body, ob, od, ou, oa, p, row_number() OVER (ORDER BY head, body) AS qi FROM cx.judge_jevclause
  WHERE ask = ?1 AND k >= 1000000 AND NOT EXISTS (SELECT 1 FROM cx.judge_jevout o WHERE o.ask = ?1 AND o.err IS NOT NULL)),
g AS (SELECT qi, p, head || CASE WHEN body <> '[]' THEN ' :- ' || (SELECT group_concat(je.value, ', ' ORDER BY CAST(je.key AS INTEGER)) FROM json_each(f.body) je) ELSE '' END AS h,
    rtrim(printf('%.12f', ob), '0') AS sb, rtrim(printf('%.12f', od), '0') AS sd, rtrim(printf('%.12f', ou), '0') AS su, rtrim(printf('%.12f', oa), '0') AS sa,
    rtrim(printf('%.12f', min(1.0, max(0.0, p))), '0') AS sp FROM f)
SELECT ?1, qi, p, h || ' b=' || CASE WHEN substr(sb, -1) = '.' THEN sb || '0' ELSE sb END || ' d=' || CASE WHEN substr(sd, -1) = '.' THEN sd || '0' ELSE sd END
  || ' u=' || CASE WHEN substr(su, -1) = '.' THEN su || '0' ELSE su END || ' a=' || CASE WHEN substr(sa, -1) = '.' THEN sa || '0' ELSE sa END
  || ' p=' || CASE WHEN substr(sp, -1) = '.' THEN sp || '0' ELSE sp END FROM g
