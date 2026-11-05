src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('''def source_holds_gate(nm, g):
    if source_is_db(nm): return cx_get("sword", nm, text_key(sym_of(g)))
    return cx_get("gate", nm, g)
def source_holds_pair(nm, a, b):
    if source_is_db(nm): return cx_get("spair", nm, text_key("%s %s" % (sym_of(a), sym_of(b))))
    return cx_get("pair", nm, pair_key(a, b))
''', '''def source_holds_gate(nm, g):
    # the owner, 11-04 18:4x: all may stay until the replacement is built correct: a source grounds by its typed keys or by its db keys, both
    return cx_get("gate", nm, g) or (source_is_db(nm) and cx_get("sword", nm, text_key(sym_of(g)))) or None
def source_holds_pair(nm, a, b):
    return cx_get("pair", nm, pair_key(a, b)) or (source_is_db(nm) and cx_get("spair", nm, text_key("%s %s" % (sym_of(a), sym_of(b))))) or None
def cx_db_k(c):
    cols = [r[1] for r in c.execute("PRAGMA table_info(corpus)")]
    if "k" not in cols: c.execute("ALTER TABLE corpus ADD COLUMN k INTEGER"); c.execute("CREATE INDEX IF NOT EXISTS corpus_k ON corpus (k)"); c.commit()
''')
rep('''    t0 = time.time(); c = cx_db(); cur = c.cursor(); n_typed = dupes = noise = 0; words_seen, pairs_seen = {}, {}
    for (sent, path, line) in items:
        if is_noise(sent): noise += 1; continue
        k = text_key(sent); had = cx_get("source", name, k)
        if had and (not replace or '"db"' in (had[3] or "")): dupes += 1; continue   # a typed row is replaced by the migration; a db row is a repeat
''', '''    t0 = time.time(); c = cx_db(); cx_db_k(c); cur = c.cursor(); n_typed = dupes = noise = 0; words_seen, pairs_seen = {}, {}
    for (sent, path, line) in items:
        if is_noise(sent): noise += 1; continue
        k = text_key(sent)
        if cur.execute("SELECT 1 FROM corpus WHERE k = ? AND source = ? LIMIT 1", (k, name)).fetchone(): dupes += 1; continue   # the db itself says repeat; a typed row of the same sentence stays as it is (the owner, 11-04 18:4x: all may stay until the replacement is built correct)
''')
rep('''        cur.execute("INSERT INTO corpus (source, word, text, path, line) VALUES (?, ?, ?, ?, ?)", (name, cw[0], sent, path, line)); sid = cur.lastrowid
        cur.executemany("INSERT INTO words (word, id, source) VALUES (?, ?, ?)", [(w, sid, name) for w in sorted(set(cw))])
        cx_put("source", name, k, 0, clock(), json.dumps({"db": sid, "path": path, "line": line}) if path else json.dumps({"db": sid}))
''', '''        cur.execute("INSERT INTO corpus (source, word, text, path, line, k) VALUES (?, ?, ?, ?, ?, ?)", (name, cw[0], sent, path, line, k)); sid = cur.lastrowid
        cur.executemany("INSERT INTO words (word, id, source) VALUES (?, ?, ?)", [(w, sid, name) for w in sorted(set(cw))])
        if not cx_get("source", name, k): cx_put("source", name, k, 0, clock(), json.dumps({"db": sid, "path": path, "line": line}) if path else json.dumps({"db": sid}))   # a typed row keeps its run; the db row stands beside it
''')
rep('''    had = cx_get("source", name, 0); d = json.loads(had[3]); d["db"] = True; d["db_lines"] = d.get("db_lines", 0) + n_typed; cx_put("source", name, 0, had[0], had[1], json.dumps(d)); _SRCD.pop(name, None)
''', '''    had = cx_get("source", name, 0); d = json.loads(had[3]); c2 = cx_db(); held = c2.execute("SELECT count(*) FROM corpus WHERE source = ?", (name,)).fetchone()[0]; c2.close()
    if held: d["db"] = True; d["db_lines"] = held
    else: d.pop("db", None); d.pop("db_lines", None)   # a source with nothing in the db is not a db source
    cx_put("source", name, 0, had[0], had[1], json.dumps(d)); _SRCD.pop(name, None)
''')
open("cortex.py", "w").write(src); print("patched")
