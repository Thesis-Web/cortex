# ---- C53 (the owner, 11-04 16:4x: a second police officer like the sixth to catch the things the judge misses; the llm asks for a second opinion; the sixth steps in and
#      calls the guessing, or the brain data on the topic, or the sources, or all three, to help the judge make a better ruling, or to inform the llm the data might not be
#      wrong but the way you shaped the data is: say the same thing in a more correct way). The ruling is typed on the sixth prompt, the sixth's own record. ----
def nearest_shape(name, n, run):
    # the line the brain holds nearest to the claim: the expected of C n or one of its parts, by shared content gates
    cg = set(g for g in content_gates(run) if not is_value(g)); best = (0, None, None)
    cands = []
    ex = cx_get("expected", name, n)
    if ex and ex[0]: cands.append(("the expected of C%s" % n, ex[0]))
    for p in parts_of(name, n): cands.append(("a part of C%s" % n, p["run"]))
    for (label, r0) in cands:
        og = set(g for g in content_gates(r0) if not is_value(g)); shared = len(cg & og)
        if shared > best[0]: best = (shared, label, r0)
    return best
def v_second(name, run, reason=None):
    ensure_cx(); row = q("SELECT value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n = ?", name, run)
    if not row: raise SystemExit("run %d has no verdict on %s" % (run, name))
    d = jload(row[0][0]); n = d.get("n"); kind, by, sh = d.get("kind"), d.get("judge"), d.get("sheet") or {}; text = line_text(run)
    print("second opinion on %s run %d (%s %.2f by %s): %s" % (name, run, kind, d.get("p") or 0, by, text[:120]))
    if reason: print("  the dispute: %s" % reason[:200])
    # read 1, the guessing: the brain's own define of the words no ground holds (the sixth's define row calls the recall define)
    none = [w for w in ((sh.get("ground") or {}).get("none") or []) if not w.startswith("pair")][:3]; guessed = []
    for w in none:
        defs = kernel_define(w)
        if defs: guessed.append("%s = %s: %s" % (w, defs[0][0], defs[0][1][:80]))
    r1 = "; ".join(guessed) if guessed else ("every word has ground, nothing to guess" if not none else "no definition in the dictionaries for " + ", ".join(none))
    print("  1 the guessing (the brain's own define): " + r1)
    # read 2, the project record
    pg = pair_ground(name, run); mem = pg.get("memory") or {}; held_mem = max(mem.values()) if mem else 0; np_ = pg.get("pairs") or 0
    shared, label, r0 = nearest_shape(name, n, run); shape_line = line_text(r0)[:160] if r0 else ""
    r2 = "%d of %d pairs held by the record (%s); nearest shape %s, %d gates shared: %s" % (held_mem, np_, " ".join("%s %d" % kv for kv in sorted(mem.items(), key=lambda kv: -kv[1])[:3]) or "none", label or "none", shared, shape_line[:100])
    print("  2 the project record: " + r2)
    # read 3, the sources
    held = pg.get("held_by") or {}; top = sorted(held.items(), key=lambda kv: -kv[1])[:4]; found = []
    for nm, cnt in top:
        if source_is_db(nm):
            for (a, b) in pairs_of(run)[:16]:
                rows = db_lines_holding(nm, [sym_of(a), sym_of(b)], 1)
                if rows: found.append("%s %s:%s %s" % (nm, rows[0][2] or "-", rows[0][3] or "-", rows[0][1][:70])); break
    r3 = "%s hold %s of %d pairs%s" % (", ".join("%s %d" % kv for kv in top) or "no source", "/".join(str(c) for nm, c in top) or "0", np_, ("; " + "; ".join(found)) if found else "")
    print("  3 the sources: " + r3)
    # the ruling: a machine print the judge read is not overruled; data a source or the record holds moves an off rail verdict to unsettled
    src_half = bool(top) and top[0][1] * 2 >= np_ > 0; mem_half = np_ > 0 and held_mem * 2 >= np_; moved = False
    if kind in ("invention", "hallucination", "drift") and by == "receipt" and sh.get("numbers_out"): ruling = "the judge stands: no print holds %s, and a source cannot stand in for the machine's print; pipe the print, then say it again" % ", ".join(sh["numbers_out"][:4])
    elif kind in ("invention", "hallucination", "drift") and (src_half or mem_half): ruling = "the data is held by %s: the verdict moves to unsettled by the sixth; the judge's call stays as history" % ("the sources " + ", ".join(nm for nm, c in top[:2]) if src_half else "the project record"); moved = True
    elif kind in ("invention", "hallucination", "drift"): ruling = "the judge stands: neither a source nor the record holds the data; the words with no ground: %s" % (", ".join(none) or "-")
    else: ruling = "the verdict was %s by %s; nothing to overrule, but the shape below is the one the brain holds" % (kind, by)
    shape = ("the brain holds this shape (%s): %s | your values: %s" % (label, shape_line, ", ".join(sh.get("numbers") or []) or "none")) if r0 else "no shape held yet for C%s" % n
    print("  ruling: " + ruling); print("  say it this way: " + shape)
    body = "run %d: %s | %s" % (run, ruling[:200], shape[:200])
    try: srun = ask("type sixth cortex second %s %d : %s" % (name, run, clean(body))).get("run") or 0
    except Exception: srun = 0
    cx_put("second", name, run, srun, clock(), json.dumps({"n": n, "ruling": ruling, "shape": shape, "reads": [r1[:300], r2[:300], r3[:300]], "moved": moved, "reason": (reason or "")[:300], "ts": int(time.time()), "sixth_run": srun}))
    if moved:
        v_judge(name, n, run, answers_given={"unsettled": 0.7}, judge_name="sixth")
    print("  the ruling typed on the sixth as run %d" % srun)
    return ruling, shape
def v_dispute(name, run, reason):
    ensure_cx(); record("dispute", name, run, clean(reason)[:400]); return v_second(name, run, reason)
# ---- C55 (the owner, 11-04 16:4x: why did, why does, how did, how does, when did, when is, when does, what should be done next): the question word routes to the record ----
def v_askq(name, qtext):
    ensure_cx(); t = qtext.lower().strip().rstrip("?"); reads = []
    m_run = re.search(r"\brun\s+(\d+)", t); m_c = re.search(r"\bc\s?(\d+)\b", t)
    if t.startswith("why"):
        if m_run:
            run = int(m_run.group(1)); row = q("SELECT value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n = ?", name, run)
            if not row: print("run %d has no verdict on %s" % (run, name)); return
            d = jload(row[0][0]); sh = d.get("sheet") or {}
            print("why run %d got %s by %s (C%s): numbers out %s | words out %s | no ground for %s | measure missing %s | shape of the expected %.2f | sources confirm %d disagree %d" % (run, d.get("kind"), d.get("judge"), d.get("n"), ",".join(sh.get("numbers_out") or []) or "-", ",".join((sh.get("words_out") or [])[:8]) or "-", ",".join((sh.get("ground") or {}).get("none") or []) or "-", ",".join(sh.get("measure_missing") or []) or "-", sh.get("shape_expected") or 0, len((sh.get("sources") or {}).get("confirm") or []), len((sh.get("sources") or {}).get("disagree") or [])))
            for f in v_why(name, quiet=True):
                if f["run"] == run: print("  and the record proves it wrong: %s | %s" % (f["why"], f["cells"]))
            sec = cx_get("second", name, run)
            if sec: print("  the sixth ruled: %s" % jload(sec[3]).get("ruling", "")[:200])
            reads = ["the verdict row", "cortex why", "the sixth's record"]
        elif m_c:
            n = int(m_c.group(1)); vs = [(r, jload(v)) for (r, v) in q("SELECT n, value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 300", name)]
            mine = [(r, d) for (r, d) in vs if d.get("n") == n][:8]
            print("why C%d stands as it does: %d verdicts; the newest: %s" % (n, len(mine), " | ".join("run %d %s by %s" % (r, d.get("kind"), d.get("judge")) for (r, d) in mine[:5])))
            for f in v_why(name, quiet=True):
                if f["n"] == n: print("  the record proves run %d wrong: %s" % (f["run"], f["why"]))
            reads = ["the verdict rows of C%d" % n, "cortex why"]
        else:
            fs = v_why(name, quiet=True); print("why, over %s: %d verdicts the record proves wrong: %s" % (name, len(fs), "; ".join("run %d %s" % (f["run"], f["why"]) for f in fs[:6]) or "none")); reads = ["cortex why"]
    elif t.startswith("how"):
        if m_c:
            n = int(m_c.group(1)); sched = [v for (k, r, a, ts, v) in cx_list("schedule", name) if (" C%d " % n) in (v or "")]
            print("how C%d moved: %d build turns%s" % (n, len(sched), (": " + " | ".join(s[:110] for s in sched[-4:])) if sched else ""))
            for p in parts_of(name, n)[:6]: print("  part by %s p%.2f: %s" % (p.get("by") or "-", p.get("p") or 0, line_text(p["run"])[:100]))
            st = cx_get("states", name, n)
            if st: print("  states: " + " -> ".join("%s %s" % (h.get("state"), time.strftime("%m-%d %H:%M", time.localtime(h.get("ts") or 0))) for h in jload(st[3])[-6:]))
            reads = ["the schedule lines", "the parts of C%d" % n, "the state history"]
        elif m_run:
            run = int(m_run.group(1)); x = ask("run main %d" % run); r = x.get("run") or {}; kids = x.get("tree") or []
            print("how run %d went: arrival %s, kind %s, %s hops, ended %s, %d runs in its tree (%d returns), text: %s" % (run, r.get("arrival"), r.get("kind"), r.get("hops"), r.get("ended"), len(kids), sum(1 for k in kids if k.get("kind") == 3), (r.get("text") or "")[:100]))
            reads = ["run main %d" % run]
        else: print("how: name a checkpoint (C n) or a run (run N)")
    elif t.startswith("when"):
        if m_c:
            n = int(m_c.group(1)); st = cx_get("states", name, n)
            if st: print("when C%d: " % n + " -> ".join("%s at %s" % (h.get("state"), time.strftime("%m-%d %H:%M", time.localtime(h.get("ts") or 0))) for h in jload(st[3])))
            else:
                s0 = cx_get("state", name, n); print("when C%d: %s since %s (no history yet; cortex states --backfill)" % (n, s0[3] if s0 else "open", time.strftime("%m-%d %H:%M", time.localtime(s0[2])) if s0 else "-"))
            reads = ["the state history of C%d" % n]
        else:
            words = [w for w in t.split()[1:] if w not in ("was", "is", "did", "does", "the", "state", "of", name)]
            v_at(name, words or ["today"]); reads = ["cortex at"]
    elif "next" in t:
        nw = next_work(name); print("what next on %s: " % name + ("C%d.%d %s" % nw if nw else "nothing of the front door's; the rest wait on the kernel or the owner")); reads = ["the remainder"]
    elif t.startswith("what is") or t.startswith("what does") or t.startswith("what are"):
        w = re.sub(r"^what (is|does|are)( an?| the)? ", "", t).split(" mean")[0].strip(); toks_ = [x for x in re.findall(r"[a-z][a-z0-9_']+", w) if x not in STOP]
        defs = kernel_define(toks_[0]) if toks_ else []
        print("what is %s: %s" % (w, ("; ".join("%s: %s" % (f, d0[:90]) for f, d0 in defs[:3])) if defs else "no definition in the brain's dictionaries"))
        for (nm, band) in sources():
            if source_is_db(nm):
                for (sid, txt, p, l) in db_lines_holding(nm, toks_[:2], 1): print("  %s %s:%s %s" % (nm, p or "-", l or "-", txt[:110]))
        reads = ["define", "the source dbs"]
    else: print("not routed yet: ask why did/does (run N or C n), how did (C n or run N), when did (C n) or when is (a day), what next, what is <word>")
    if reads: print("  reads: " + ", ".join(reads))
