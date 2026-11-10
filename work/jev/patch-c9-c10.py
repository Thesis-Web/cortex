# patch-c9-c10.py (2026-11-10, jev C9, C10): cortex jev verify types the claim and the source's rows (a db's corpus table, a JSON list, a text file's lines) and prints the
# brain's lines; cortex jev calibrate types the set file's text and the bins and prints the brain's lines
f = "/home/james/cortex/cortex.py"; s = open(f).read()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]; s = s.replace(old, new)
rep('''def jev_door():''', '''def jev_source_rows(arg):
    # jev C9: the source's rows as they stand, in source order, typed into the request (path, source, line, text); the brain reads and labels, this decides nothing
    import sqlite3
    if not os.path.isfile(arg): return None, "%s is not a file: give a source db (a corpus table with a text column), a JSON list or a text file" % arg
    with open(arg, "rb") as fh: head = fh.read(16)
    if head.startswith(b"SQLite format 3"):
        try:
            c = sqlite3.connect("file:%s?mode=ro" % arg, uri=True, timeout=30)
            cols = {r[1] for r in c.execute("PRAGMA table_info(corpus)")}
            if "text" not in cols: return None, "the source db %s has no corpus table with a text column" % arg
            n = c.execute("SELECT count(*) FROM corpus").fetchone()[0]
            if n > 20000: return None, "the source db %s holds %d rows; at most 20000 are typed into one request" % (arg, n)
            sel = ", ".join(x if x in cols else "NULL" for x in ("path", "source", "line", "text"))
            order = "id" if "id" in cols else "rowid"
            return [dict(zip(("path", "source", "line", "text"), r)) for r in c.execute("SELECT %s FROM corpus ORDER BY %s" % (sel, order))], None
        except sqlite3.Error as e: return None, "the source db %s did not open: %s" % (arg, e)
    text = jev_read(arg)
    if text is None: return None, "cannot read %s" % arg
    try: obj = json.loads(text)
    except ValueError: obj = None
    if isinstance(obj, list):
        rows = []
        for k, x in enumerate(obj):
            if isinstance(x, str): rows.append({"path": arg, "line": k + 1, "text": x})
            elif isinstance(x, dict) and x.get("text") is not None: rows.append({"path": x.get("path") or x.get("source") or arg, "line": x.get("line", k + 1), "text": str(x["text"])})
            else: return None, "source row %d of %s has no text" % (k + 1, arg)
        return rows, None
    return [{"path": arg, "line": i, "text": l} for i, l in enumerate(text.splitlines(), 1) if l.strip()], None
def v_jev_verify(a):
    # jev C9 (the owner 11-06 14:46 and 11-09 00:48, as the ask): claim verification in the judge's brain (judge/judge-jev-verify.sql): the facts, their labels against the
    # source's rows, the score; this verb only types the claim and the source's rows and prints the brain's lines; jev.py is not read
    claim, source = jev_opt(a, "--claim"), jev_opt(a, "--source")
    if claim is None or not source: print("cortex jev verify --claim <text> --source <db or file>", file=sys.stderr); return 2
    rows, err = jev_source_rows(source)
    if err: print("jev: %s" % err, file=sys.stderr); return 2
    rc, lines = jev_brain("verify", json.dumps(rows), [claim], count=False)
    if rc: return rc
    sys.stdout.write("".join("%s\\n" % l for l in lines)); return 0
def v_jev_calibrate(a):
    # jev C10 (the owner 11-06 14:46 and 11-09 00:48, as the ask): a jury pooled by self-consistency and checked for calibration in the judge's brain
    # (judge/judge-jev-calibrate.sql); this verb only types the set file's text and the bins and prints the brain's lines; jev.py is not read
    path, bins = jev_opt(a, "--set"), jev_opt(a, "--bins")
    if not path: print("cortex jev calibrate --set <file> [--bins k]", file=sys.stderr); return 2
    text = jev_read(path)
    if text is None: return 2
    rc, lines = jev_brain("calibrate", text, [], rules=bins if bins is not None else "", count=False)
    if rc: return rc
    sys.stdout.write("".join("%s\\n" % l for l in lines)); return 0
def jev_door():''')
rep('''    elif v == "jev" and a and a[0] in ("why", "retract"):''', '''    elif v == "jev" and a and a[0] == "verify":
        return v_jev_verify(a[1:])   # jev C9: the judge brain labels; jev.py is not imported
    elif v == "jev" and a and a[0] == "calibrate":
        return v_jev_calibrate(a[1:])   # jev C10: the judge brain pools and buckets; jev.py is not imported
    elif v == "jev" and a and a[0] in ("why", "retract"):''')
open(f, "w").write(s); print("cortex.py: verify, calibrate")
