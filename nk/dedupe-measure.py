#!/usr/bin/env python3
# dedupe-measure.py <export brain.db>: how much of the receipt table is exact repetition of an earlier identical run (same symbols, same shards)
import sqlite3, sys, time, collections
db = sqlite3.connect(sys.argv[1]); t = time.time()
first = {}; rep = set(); runs_ended = 0
for run, inp in db.execute("SELECT run, input FROM run_memory ORDER BY run"):
    runs_ended += 1
    if inp in first: rep.add(run)
    else: first[inp] = run
rc = dict(db.execute("SELECT run, count(*) FROM run_receipt GROUP BY run"))
sq = dict(db.execute("SELECT run, count(*) FROM seq GROUP BY run"))
tot_rc = sum(rc.values()); rep_rc = sum(rc.get(r, 0) for r in rep); tot_sq = sum(sq.values()); rep_sq = sum(sq.get(r, 0) for r in rep)
print(f"runs that ended {runs_ended}; distinct lines {len(first)}; runs that repeat an earlier identical line {len(rep)} ({100 * len(rep) / runs_ended:.0f}%)")
print(f"receipts in all {tot_rc}; held by repeated runs {rep_rc} ({100 * rep_rc / tot_rc:.0f}%); seq rows in all {tot_sq}; held by repeated runs {rep_sq} ({100 * rep_sq / tot_sq:.0f}%)")
# do two identical runs hit the same shards? check the ten most repeated lines, first instance against the last
cnt = collections.Counter(); 
for run, inp in db.execute("SELECT run, input FROM run_memory"): cnt[inp] += 1
same = diff = 0; examples = []
for inp, n in cnt.most_common(10):
    runs = [r for (r,) in db.execute("SELECT run FROM run_memory WHERE input = ? ORDER BY run", (inp,))]
    a = [tuple(x) for x in db.execute("SELECT pos, gate, shard FROM run_receipt WHERE run = ? ORDER BY id", (runs[0],))]
    b = [tuple(x) for x in db.execute("SELECT pos, gate, shard FROM run_receipt WHERE run = ? ORDER BY id", (runs[-1],))]
    text = ''.join(s for (s,) in db.execute("SELECT l.symbol FROM seq s JOIN label l ON l.gate = s.gate WHERE s.run = ? ORDER BY s.pos", (runs[0],)))
    if a == b: same += 1
    else: diff += 1
    examples.append((n, text[:50], len(a), 'same shards' if a == b else f'DIFFERENT ({len(a)} vs {len(b)} hops)'))
print(f"the ten most repeated lines: first and last instance hit the same shards in {same} of 10")
for e in examples: print("  ", e)
print(f"({time.time() - t:.0f} s)")
