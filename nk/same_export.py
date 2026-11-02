#!/usr/bin/env python3
# same_export.py A B: two exports of a brain (brain.db or sixth.db), every table compared row for row (text and ordering by every column)
import sqlite3, sys, hashlib
a, b = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
ta = {r[0] for r in a.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}; tb = {r[0] for r in b.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
if ta != tb: print('tables differ: only A', sorted(ta - tb), 'only B', sorted(tb - ta))
same = diff = 0
for t in sorted(ta & tb):
    ca = [r[1] for r in a.execute(f'PRAGMA table_info("{t}")')]; cb = [r[1] for r in b.execute(f'PRAGMA table_info("{t}")')]
    if ca != cb: print(f'{t}: columns differ', ca, cb); diff += 1; continue
    skip = {'moment'} if t == 'run' else set()      # moment is the wall clock of the run's birth: kept as it was in the snapshot, so it agrees; left in
    cols = ', '.join(f'"{x}"' for x in ca)
    def h(db): 
        m = hashlib.sha256(); n = 0
        for r in db.execute(f'SELECT {cols} FROM "{t}" ORDER BY {cols}'): m.update(repr(r).encode()); n += 1
        return m.hexdigest(), n
    (ha, na), (hb, nb) = h(a), h(b)
    if ha == hb: same += 1
    else:
        diff += 1; ra = set(a.execute(f'SELECT {cols} FROM "{t}"')); rb = set(b.execute(f'SELECT {cols} FROM "{t}"'))
        print(f'{t}: {na} vs {nb} rows; only A {len(ra - rb)}, only B {len(rb - ra)}; e.g. {sorted(ra - rb, key=str)[:2]} | {sorted(rb - ra, key=str)[:2]}')
print(f'{same} tables identical, {diff} differ')
