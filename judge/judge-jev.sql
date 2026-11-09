-- judge-jev.sql (2026-11-09, rail C6; the owner, 11-09 00:48: the judge --> jev like needs to happen ... a grounded source to check the rail is being held).
-- Our own jev in the judge's brain: rules as rows of sql fired by a request row through the mother (judge C1), after the cells of rules 1 to 4.
-- Rule 5 reads the evidence: the cortex own check of the checkpoint (audited, its last print), the voice of the claim and its trust on the project,
-- the claim's adjacent word pairs held by the source db's rows (how many sources), and its words new to the project that no source holds.
-- Rule 6 answers the handler's seven questions (section 7) as probabilities from that evidence only, with the owner's bands (11-03 21:5x:
-- llm 0.20 to 0.80, owner 0.50 to 0.80, a reference alone 0.60, owner and source 0.85, llm and two sources 0.95); a machine print is 1.00;
-- the handler's truth table picks the verdict; every probability names the rows it came from. Beside the python judge, not deciding.
-- ;; ddl
CREATE TABLE IF NOT EXISTS judge_jev (run INTEGER NOT NULL, name TEXT NOT NULL, n INTEGER NOT NULL, completes REAL, progresses REAL, regresses REAL, supersedes REAL, off_scope REAL, invents REAL, contradicts REAL, verdict TEXT, evidence TEXT, ts INTEGER, PRIMARY KEY (run, name, n));
-- ;; ddl
ALTER TABLE judge_cell ADD COLUMN check_state TEXT;
-- ;; ddl
ALTER TABLE judge_cell ADD COLUMN voice TEXT;
-- ;; ddl
ALTER TABLE judge_cell ADD COLUMN trust REAL;
-- ;; ddl
ALTER TABLE judge_cell ADD COLUMN pairs INTEGER;
-- ;; ddl
ALTER TABLE judge_cell ADD COLUMN pairs_held INTEGER;
-- ;; ddl
ALTER TABLE judge_cell ADD COLUMN pair_sources INTEGER;
-- ;; ddl
ALTER TABLE judge_cell ADD COLUMN new_unheld INTEGER;
-- ;; rule 5 the evidence: the cortex own check, the voice and its trust, the sources that hold the pairs, the new words no source holds
UPDATE cx.judge_cell SET (check_state, voice, trust, pairs, pairs_held, pair_sources, new_unheld) = (
WITH k AS (SELECT (SELECT gate FROM main.label WHERE symbol = ':') AS colon, (SELECT gate FROM main.label WHERE symbol = ' ') AS sp),
ck AS (SELECT json_extract(value, '$.audited.ok') AS aud, json_extract(value, '$.audited.cmd') = json_extract(value, '$.cmd') AS same FROM main.cx WHERE kind = 'check' AND name = ?2 AND n = ?3),
cl AS (SELECT json_extract(value, '$.ok') AS ok FROM main.cx WHERE kind = 'checklast' AND name = ?2 AND n = ?3),
vo AS (SELECT coalesce(json_extract(value, '$.voice'), 'hand') AS v FROM main.cx WHERE kind = 'ingest' AND name = ?2 AND run = ?1 AND n > 0 LIMIT 1),
vt AS (SELECT CAST(json_extract(x.value, '$.by_project."' || ?2 || '".confirmed') AS REAL) AS cf, CAST(json_extract(x.value, '$.by_project."' || ?2 || '".false') AS REAL) AS fl FROM main.cx x WHERE x.kind = 'voice' AND x.name = coalesce((SELECT v FROM vo), 'hand') AND x.n = 0),
c0 AS (SELECT min(q.pos) AS p FROM main.seq q, k WHERE q.run = ?1 AND q.gate = k.colon),
cw AS MATERIALIZED (SELECT lower(l.symbol) AS w, s.pos AS pos, s.gate AS gate FROM main.seq s JOIN main.label l ON l.gate = s.gate, k WHERE s.run = ?1 AND s.gate <> k.sp AND s.pos > coalesce((SELECT p FROM c0), 0) AND l.symbol GLOB '[A-Za-z][A-Za-z]*' AND length(l.symbol) > 2),
cn AS MATERIALIZED (SELECT w, pos, gate, row_number() OVER (ORDER BY pos) AS i FROM cw WHERE w NOT IN ('the','and','that','this','with','from','are','was','were','for','not','but','its','has','have','had','been','into','than','then','also','only','very','just','there','here','they','them','their','will','would','can','could','should','may','might','must','when','what','which','who','how','why','where','each','every','one','two','all','any','more','most','some','such','own','same','other','new','now','out','yes')),
pr AS (SELECT a.w AS a, b.w AS b FROM cn a JOIN cn b ON b.i = a.i + 1),
ph AS MATERIALIZED (SELECT pr.a, pr.b, (SELECT count(DISTINCT w2.source) FROM cx.words w2 WHERE w2.word = pr.b AND w2.id IN (SELECT w1.id FROM cx.words w1 WHERE w1.word = pr.a)) AS srcs FROM pr),
ng AS (SELECT DISTINCT cn.w FROM cn LEFT JOIN main.cx g ON g.kind = 'gate' AND g.name = ?2 AND g.n = cn.gate WHERE NOT (g.value IS NOT NULL AND CAST(json_extract(g.value, '$.first') AS INTEGER) < ?1))
SELECT CASE WHEN (SELECT aud FROM ck) = 1 AND (SELECT same FROM ck) = 1 THEN CASE (SELECT ok FROM cl) WHEN 1 THEN 'ok' WHEN 0 THEN 'wrong' END END,
  coalesce((SELECT v FROM vo), 'hand'),
  (SELECT CASE WHEN coalesce(cf, 0) + coalesce(fl, 0) > 0 THEN coalesce(cf, 0) / (coalesce(cf, 0) + coalesce(fl, 0)) END FROM vt),
  (SELECT count(*) FROM pr), (SELECT count(*) FROM ph WHERE srcs > 0), coalesce((SELECT max(srcs) FROM ph), 0),
  (SELECT count(*) FROM ng WHERE NOT EXISTS (SELECT 1 FROM cx.words w WHERE w.word = ng.w))
) WHERE run = ?1 AND name = ?2 AND n = ?3
-- ;; rule 6 jev: the seven questions as probabilities from the evidence, the owner bands, the handler truth table
INSERT OR REPLACE INTO cx.judge_jev (run, name, n, completes, progresses, regresses, supersedes, off_scope, invents, contradicts, verdict, evidence, ts)
WITH c AS (SELECT * FROM cx.judge_cell WHERE run = ?1 AND name = ?2 AND n = ?3),
b AS (SELECT c.*,
   CASE WHEN coalesce(exp_content, 0) > 0 THEN min(1.0, coalesce(shared_content, 0) * 1.0 / exp_content) ELSE 0.0 END AS cov,
   CASE WHEN voice = 'owner' THEN max(0.5, min(0.8, coalesce(trust, 0.65))) ELSE max(0.2, min(0.8, coalesce(trust, 0.5))) END AS vb,
   CASE WHEN coalesce(pairs, 0) > 0 AND pairs_held * 2 >= pairs THEN CASE WHEN pair_sources >= 2 THEN 2 ELSE 1 END ELSE 0 END AS src
 FROM c),
p AS (SELECT b.*, CASE WHEN voice = 'owner' AND src >= 1 THEN 0.85 WHEN voice = 'owner' THEN vb WHEN src >= 2 THEN 0.95 WHEN src = 1 THEN max(vb, 0.60) ELSE vb END AS band FROM b),
j AS (SELECT p.*,
   round(CASE WHEN check_state = 'ok' AND cov >= 0.7 THEN 1.0 WHEN coalesce(values_n, 0) > 0 AND values_held = values_n THEN cov ELSE cov * band END, 3) AS q_completes,
   round(CASE WHEN coalesce(values_held, 0) > 0 AND coalesce(shared_content, 0) > 0 THEN 1.0 WHEN coalesce(shared_content, 0) > 0 THEN band * min(1.0, 2.0 * cov) ELSE 0.0 END, 3) AS q_progresses,
   CASE WHEN check_state = 'wrong' AND coalesce(shared_content, 0) > 0 THEN 1.0 ELSE 0.0 END AS q_regresses,
   0.0 AS q_supersedes,
   round(CASE WHEN coalesce(content, 0) > 0 THEN 1.0 - min(1.0, coalesce(shared_project, 0) * 1.0 / content) ELSE 0.0 END, 3) AS q_off,
   round(CASE WHEN coalesce(content, 0) > 0 THEN min(1.0, coalesce(new_unheld, 0) * 1.0 / content) ELSE 0.0 END, 3) AS q_invents,
   round(CASE WHEN coalesce(values_n, 0) > 0 AND coalesce(prints, 0) > 0 THEN max(0.0, (values_n - coalesce(values_held, 0) - coalesce(values_in_expected, 0)) * 1.0 / values_n) ELSE 0.0 END, 3) AS q_contra
 FROM p)
SELECT run, name, n, q_completes, q_progresses, q_regresses, q_supersedes, q_off, q_invents, q_contra,
  CASE WHEN coalesce(same_as, 0) > 0 THEN 'dupe' WHEN q_completes >= 0.7 THEN 'completes' WHEN q_off >= 0.7 THEN 'drift' WHEN q_invents >= 0.7 THEN 'invention' WHEN q_contra >= 0.7 THEN 'hallucination'
       WHEN q_supersedes >= 0.7 THEN 'supersedes' WHEN q_progresses >= 0.7 THEN 'progresses' WHEN q_regresses >= 0.7 THEN 'regresses' ELSE 'unsettled' END,
  'completes: ' || CASE WHEN check_state = 'ok' AND cov >= 0.7 THEN printf('the cortex own check (check %s C%d) audited, its last print ok, the expected covered %.2f', name, n, cov)
         WHEN coalesce(values_n, 0) > 0 AND values_held = values_n THEN printf('every value held by an older print (receipts %s C%d), the expected covered %.2f', name, n, cov)
         ELSE printf('the voice band %.2f times the expected covered %.2f', band, cov) END
  || '; progresses: ' || CASE WHEN coalesce(values_held, 0) > 0 AND coalesce(shared_content, 0) > 0 THEN printf('a value held by an older print (receipts %s C%d)', name, n) ELSE printf('the voice band %.2f', band) END
  || '; regresses: ' || CASE WHEN check_state = 'wrong' THEN printf('the cortex own check (check %s C%d), its last print wrong', name, n) ELSE 'no check print wrong' END
  || '; supersedes: no cell reads a newer print of the same thing yet'
  || printf('; off scope: the record, content %d shared with the project %d', coalesce(content, 0), coalesce(shared_project, 0))
  || printf('; invents: the source db, %d of %d content words new to the project and held by no source', coalesce(new_unheld, 0), coalesce(content, 0))
  || printf('; contradicts: the receipts, values %d held %d in the expected %d, prints %d', coalesce(values_n, 0), coalesce(values_held, 0), coalesce(values_in_expected, 0), coalesce(prints, 0))
  || printf(' | voice %s trust %s band %.2f; pairs %d held by a source %d, most sources on one pair %d', coalesce(voice, '-'), CASE WHEN trust IS NULL THEN '-' ELSE printf('%.2f', trust) END, band, coalesce(pairs, 0), coalesce(pairs_held, 0), coalesce(pair_sources, 0)),
  CAST(strftime('%s', 'now') AS INTEGER)
FROM j
