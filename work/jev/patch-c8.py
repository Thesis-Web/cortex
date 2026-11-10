# patch-c8.py (2026-11-10, jev C8): the ask types the state file's path (path:line of text rows); cortex jev why and retract type a request row and print the brain's lines
f = "/home/james/cortex/cortex.py"; s = open(f).read()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]; s = s.replace(old, new)
rep('''def jev_brain(verb, text, qs, rules=None, count=True):''', '''def jev_brain(verb, text, qs, rules=None, count=True, path=None):''')
rep('''    if rules is None: r = ask("q INSERT INTO cx.judge_jevask (verb, state, qs, ts) VALUES (%s, %s, %s, %d) RETURNING id" % (lit(verb), lit(text), lit(json.dumps(qs)), int(time.time())))
    else: r = ask("q INSERT INTO cx.judge_jevask (verb, state, qs, ts, rules) VALUES (%s, %s, %s, %d, %s) RETURNING id" % (lit(verb), lit(text), lit(json.dumps(qs)), int(time.time()), lit(rules)))''',
'''    cols, vals = ["verb", "state", "qs", "ts"], [lit(verb), lit(text), lit(json.dumps(qs)), "%d" % int(time.time())]
    if rules is not None: cols.append("rules"); vals.append(lit(rules))
    if path is not None: cols.append("path"); vals.append(lit(path))
    r = ask("q INSERT INTO cx.judge_jevask (%s) VALUES (%s) RETURNING id" % (", ".join(cols), ", ".join(vals)))''')
rep('''    rc, lines = jev_brain("ask", text, qs)''', '''    rc, lines = jev_brain("ask", text, qs, path=os.path.abspath(state))   # jev C8: the path:line of a text state's rows''')
rep('''def jev_door():''', '''def v_jev_reason(verb, a):
    # jev C8 (the owner 11-06 14:46 and 11-09 00:48, as the ask): reason maintenance in the judge's brain. why <id>: the record of the id's newest answer, the rows its line
    # depends on with path:line (judge/judge-jev-why.sql); retract <row> [--undo]: the answers whose reasons list the row asked again from the record, without it
    # (judge/judge-jev-retract.sql). This verb only types the request row and prints the brain's lines; jev.py is not read
    args = [x for x in a if not x.startswith("--")]
    if not args: print("cortex jev why <id>" if verb == "why" else "cortex jev retract <row id> [--undo]", file=sys.stderr); return 2
    qs = args if verb == "why" else [args[0]] + (["--undo"] if "--undo" in a else [])
    rc, lines = jev_brain(verb, "", qs, count=False)
    if rc: return rc
    sys.stdout.write("".join("%s\\n" % l for l in lines)); return 0
def jev_door():''')
rep('''    elif v == "jev" and a and a[0] == "opinion":''', '''    elif v == "jev" and a and a[0] in ("why", "retract"):
        return v_jev_reason(a[0], a[1:])   # jev C8: the judge brain answers from its record; jev.py is not imported
    elif v == "jev" and a and a[0] == "opinion":''')
rep('''  jev why <id> | jev retract <row id> [--undo]   jev C8: the path:line of the rows an answer depends on; a retracted row revises only the answers that listed it''',
    '''  jev why <id> | jev retract <row id> [--undo]   jev C8: the path:line of the rows an answer depends on; a retracted row revises only the answers that listed it, asked again from the record in the judge brain''')
open(f, "w").write(s); print("cortex.py: why, retract, the ask's path")
