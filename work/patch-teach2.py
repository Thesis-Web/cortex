src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
# dupe: the inputs are the sentences typed since C30 (one run, no project in the prefix); the brain keys a repeat by the whole typed line, so older lines (typed with a prefix) are not the same line to it
rep('''    if function == "dupe":
        for (run, t) in teach_inputs(name, k):
''', '''    if function == "dupe":
        import random
        lines = q("SELECT n, run, value FROM main.cx WHERE kind = 'line' AND name = '*' AND n > 0 AND run > 0 LIMIT 600"); random.shuffle(lines); picked = []
        for (n0, run0, v0) in lines:
            t0_ = line_text(run0)
            if t0_ and len(t0_) > 20: picked.append((run0, t0_))
            if len(picked) >= k: break
        for (run, t) in picked:   # the lesson taught 11-04 20:4x: a line typed before C30 carried its project in the prefix; the brain holds it as another line, the front door as the same sentence
''')
# pairs: both sides answer the same question: which db sources hold a sentence with both words of each pair (the brain through its door, the front door by reading the db)
rep('''            pg = pair_ground(name, run); fd = {nm: c for nm, c in (pg.get("held_by") or {}).items() if nm in dbs}
            brain = brain_pairs_held(name, run)
''', '''            fd = {}
            for (a, b) in set(pairs_of(run)):
                for nm in dbs:
                    if db_lines_holding(nm, [sym_of(a), sym_of(b)], 1): fd[nm] = fd.get(nm, 0) + 1   # the front door reads the db directly; the brain asks through its inbox and lays the returns
            brain = brain_pairs_held(name, run)
''')
# known: the front door side is the words no source holds (by the source keys), beside the brain's know
rep('''            kn = brain_know(run) or "-"
            try: g = ground_cells(name, 0, run, t, set())["ground"]
            except Exception as e: g = {"none": ["(ground failed: %s)" % e]}
            none = g.get("none") or []
            words = [sym_of(x) for x in content_gates(run) if not is_value(x)]
''', '''            kn = brain_know(run) or "-"
            words = [sym_of(x) for x in content_gates(run) if not is_value(x)]; srcs = [nm for (nm, band) in sources()]
            none = [sym_of(x) for x in content_gates(run) if not is_value(x) and not any(source_holds_gate(nm, x) for nm in srcs)]
''')
# C5: when the owner retired dupe, the kernel's same_as alone decides a repeat
rep('''    fates, counts = filter_lines(name, sentences(text))
    for s, fate, why in fates:
        k = text_key(s)
''', '''    fates, counts = filter_lines(name, sentences(text))
    brain_dupe = "dupe" in retired_functions()   # teach C5: on the owner word the front door reads the brain answer alone: the kernel same_as decides a repeat
    for s, fate, why in fates:
        k = text_key(s)
        if brain_dupe and fate in ("keep", "dupe", "restated"):
            kr0 = typed("cortex ingest : %s" % s); sa = (run_row(kr0["run"]) or [0, 0])[1] or 0
            if sa:
                had = cx_get("ingest", name, text_key(s))
                if had: d1 = json.loads(had[3]) if had[3] and had[3].startswith("{") else {}; d1["times"] = ingest_text(had[3])[1] + 1; d1["last"] = kr0["run"]; cx_put("ingest", name, k, had[0], had[1], json.dumps(d1))
                out.append({"run": (had[0] if had else sa), "clock": clock(), "born": 0, "seconds": 0.0, "same_as": sa, "again": 2, "text": s})
                if not quiet: print("ingest run %d a repeat by the kernel same_as %d (dupe is held by the neuron): %s" % (had[0] if had else sa, sa, s[:100]))
                continue
            if fate == "dupe": fate = "keep"   # the brain says new; the index row is laid below
''')
open("cortex.py", "w").write(src); print("patched")
