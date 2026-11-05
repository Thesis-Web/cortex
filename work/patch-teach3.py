src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('''            had = cx_get("ingest", name, text_key(t)); fd = had[0] if had else 0
''', '''            held = cx_get("line", "*", text_key(t)); fd = held[0] if held else 0   # C30: the sentence's one run, whichever project typed it first
''')
rep('''    gates = source_gates(); before = set(t["id"] for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3); held = {}
    for (a, b) in set(pairs_of(run)):
        w = "%s %s" % (sym_of(a), sym_of(b))
        q("INSERT INTO cx.inbox (run, cell, about, word, source) VALUES (?, 24, 0, ?, NULL)", run, w)
        time.sleep(0.05)
        kids = [t for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3 and t["id"] not in before]
        for t in kids: before.add(t["id"])
        for nm in set(gates.get(t.get("arrival")) for t in kids if gates.get(t.get("arrival"))): held[nm] = held.get(nm, 0) + 1
    return held
''', '''    gates = source_gates(); before = set(t["id"] for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3); held = {}
    dbs = [nm for (nm, band) in sources() if source_is_db(nm)]
    for (a, b) in set(pairs_of(run)):
        w = "%s %s" % (sym_of(a), sym_of(b))
        for nm in dbs: q("INSERT INTO cx.inbox (run, cell, about, word, source) VALUES (?, 24, 0, ?, ?)", run, w, nm)   # one ask per source: the trigger answers at most 24 rows per ask, so a common pair is not starved by the first sources
        time.sleep(0.05)
        kids = [t for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3 and t["id"] not in before]
        for t in kids: before.add(t["id"])
        for nm in set(gates.get(t.get("arrival")) for t in kids if gates.get(t.get("arrival"))): held[nm] = held.get(nm, 0) + 1
    return held
''')
open("cortex.py", "w").write(src); print("patched")
