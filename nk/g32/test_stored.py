#!/usr/bin/env python3
# test_stored.py (2026-11-01): written BEFORE the change. usage: test_stored.py CONTROL_FOLDER STORED_FOLDER CONTROL_PID STORED_PID
# CONTROL = a small kernel as it runs today, brain in the heap. STORED = the same kernel with every region in a stored file.
# Both were started with NK_WAIT_EMPTY=1 and took the same lines, so each line finished before the next, and each has exported to <folder>/exp.
#
# The owner's words it is written from:
#   2026-11-01: "why the fuck do we have to hold run records in ram????? why the fuck do we have to hold deterministic dna shards in ram?????"
#   2026-11-01: "dna live in the points dna table... each point has its own fucking dna table"
#   Reference draft 5.8: "It can be turned back on in the same state, because it is stored, not held only in RAM."
#   Reference draft 2.1: "A neuron is its own table. Its gate is its address, reached instantly"
#
# S1  the same brain: every table of both brains identical to the control's, row for row, except the run table's clock column. Where the data
#     lives may change nothing the brain does.
# S2  stored, not held: at least 90% of the brain's bytes are on disk in the stored file, not in anonymous memory. Bytes on disk from the file's
#     blocks (du), anonymous memory from /proc/PID/smaps_rollup. The control must fail this: it has no file and its brain is anonymous memory.
#     (Changed once, before anything was applied live. The first form counted resident file pages, which is low exactly when the operating system
#     has already let them go, so a brain that was out of RAM printed FAIL. That run is g32-run1.txt, kept in RESULTS.)
# S3  each point keeps its own table: dna rows by gate, and the shards of a gate found by that gate, the same as the control (part of S1, and
#     read again here by the sum of times per gate).
import sqlite3, sys, os, re

def smaps(pid):
    t = open(f"/proc/{pid}/smaps_rollup").read()
    return {k: int(re.search(rf"^{k}:\s+(\d+) kB", t, re.M).group(1)) for k in ("Rss", "Anonymous", "Pss_File", "Swap")}

def compare(a, b):
    ca, cb = sqlite3.connect(a), sqlite3.connect(b); bad = []
    names = [r[0] for r in ca.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    if set(names) != {r[0] for r in cb.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}: bad.append("tables differ")
    for t in names:
        cols = [r[1] for r in ca.execute(f'PRAGMA table_info("{t}")')]
        use = [c for c in cols if not (t == "run" and c in ("moment",))]
        sel = ", ".join(f'"{c}"' for c in use)
        ra = ca.execute(f'SELECT {sel} FROM "{t}" ORDER BY {sel}').fetchall(); rb = cb.execute(f'SELECT {sel} FROM "{t}" ORDER BY {sel}').fetchall()
        if ra != rb: bad.append(f"{t}: {len(ra)} rows and {len(rb)} rows, {len(set(ra) ^ set(rb))} differ")
    return len(names), bad

def main():
    c, s, pc, ps = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]; ok = True
    for f in ("brain.db", "sixth.db"):
        n, bad = compare(f"{c}/exp/{f}", f"{s}/exp/{f}")
        print(f"S1 {f}: {n} tables,", "every one identical" if not bad else "DIFFER: " + "; ".join(bad)); ok &= not bad
    a = sqlite3.connect(f"{c}/exp/brain.db"); b = sqlite3.connect(f"{s}/exp/brain.db")
    q = "SELECT gate, count(*), sum(times) FROM dna GROUP BY gate"
    try: same = a.execute(q).fetchall() == b.execute(q).fetchall(); print("S3 each point's table the same:", same); ok &= same
    except sqlite3.Error as e: print("S3: this export keeps the dna as tables of its own; S1 covers them:", e)
    mc, ms = smaps(pc), smaps(ps)
    disk = lambda folder: (os.stat(folder + ".map").st_blocks * 512 // 1024) if os.path.exists(folder + ".map") else 0
    dc, ds = disk(c), disk(s)
    share = lambda m, d: d / max(1, d + m["Anonymous"] + m["Swap"])
    print("control", mc, "on disk kB", dc, "share", round(share(mc, dc), 3)); print("stored ", ms, "on disk kB", ds, "share", round(share(ms, ds), 3))
    print("RAM the process holds: control", mc["Rss"], "kB, stored", ms["Rss"], "kB")
    print("S2 stored kernel:", "PASS" if share(ms, ds) >= 0.9 else "FAIL"); ok &= share(ms, ds) >= 0.9
    print("S2 negative control:", "good, the heap kernel fails it" if share(mc, dc) < 0.9 else "VACUOUS, the heap kernel passes it"); ok &= share(mc, dc) < 0.9
    print("RESULT", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)

main()
