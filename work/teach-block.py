# ---- C57 / the project teach (the owner, 11-04 18:4x: all may stay until you build the replacement correct, better until neuron builds the replacement on its own without
#      any help from you; caveat you have to teach it to do this): a lesson = a brain function the front door does outside the brain; the brain's own answer is read from
#      its runs, the front door's answer taken on the same inputs, the two printed side by side; retired only on the owner's word (cortex retire) ----
def teach_inputs(name, k, kind="ingest"):
    import random
    rows = q("SELECT n, run, value FROM main.cx WHERE kind = ? AND name = ? AND n > 0 AND run > 0 LIMIT 400", kind, name)
    random.shuffle(rows); out = []
    for (n, run, v) in rows:
        t = line_text(run)
        if t and len(t) > 20: out.append((run, t))
        if len(out) >= k: break
    return out
def brain_know(run):
    rows = q("SELECT value FROM main.run_sheet WHERE run = ? AND cell = 26", run)
    return rows[0][0] if rows else None
def source_gates():
    return {row[1]: row[0] for row in q("SELECT source, gate FROM cx.me")}
def brain_pairs_held(name, run):
    # the brain's own ask: every pair of the claim into cx.inbox under the claim's run; the returns laid under it, one per source row holding the pair; counted per source as pairs held
    gates = source_gates(); before = set(t["id"] for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3); held = {}
    for (a, b) in set(pairs_of(run)):
        w = "%s %s" % (sym_of(a), sym_of(b))
        q("INSERT INTO cx.inbox (run, cell, about, word, source) VALUES (?, 24, 0, ?, NULL)", run, w)
        time.sleep(0.05)
        kids = [t for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3 and t["id"] not in before]
        for t in kids: before.add(t["id"])
        for nm in set(gates.get(t.get("arrival")) for t in kids if gates.get(t.get("arrival"))): held[nm] = held.get(nm, 0) + 1
    return held
def v_teach(function, k=5, name="cortex"):
    ensure_cx(); rows = []; equal = 0; total = 0
    if function == "dupe":
        for (run, t) in teach_inputs(name, k):
            try: kr = typed("cortex ingest : %s" % t)["run"]
            except RuntimeError: continue
            rr = run_row(kr); brain = (rr[1] or 0) if rr else 0
            had = cx_get("ingest", name, text_key(t)); fd = had[0] if had else 0
            total += 1; eq = brain == fd and brain > 0; equal += 1 if eq else 0
            rows.append("brain same_as %d | front door first run %d | %s | %s" % (brain, fd, "equal" if eq else "differ", t[:70]))
    elif function == "pairs":
        dbs = [nm for (nm, band) in sources() if source_is_db(nm)]
        for (run, t) in teach_inputs(name, k):
            pg = pair_ground(name, run); fd = {nm: c for nm, c in (pg.get("held_by") or {}).items() if nm in dbs}
            brain = brain_pairs_held(name, run)
            total += 1; eq = brain == fd; equal += 1 if eq else 0
            rows.append("run %d: brain %s | front door %s | %s | %s" % (run, " ".join("%s %d" % kv for kv in sorted(brain.items())) or "none", " ".join("%s %d" % kv for kv in sorted(fd.items())) or "none", "equal" if eq else "differ", t[:60]))
    elif function == "known":
        pr = cx_get("project", name, 0)
        for (run, t) in teach_inputs(name, k):
            kn = brain_know(run) or "-"
            try: g = ground_cells(name, 0, run, t, set())["ground"]
            except Exception as e: g = {"none": ["(ground failed: %s)" % e]}
            none = g.get("none") or []
            words = [sym_of(x) for x in content_gates(run) if not is_value(x)]
            try: known_n, all_n = [int(x) for x in kn.split("/")]
            except Exception: known_n, all_n = 0, len(words)
            unknown_n = max(0, all_n - known_n); overlap = min(unknown_n, len(none))
            total += 1
            rows.append("run %d: brain know %s (unknown %d) | front door no ground %d: %s | overlap at most %d | %s" % (run, kn, unknown_n, len(none), ", ".join(none[:5]) or "-", overlap, t[:50]))
    else: raise SystemExit("teach dupe|pairs|known")
    print("teach %s on %s, %d inputs at random:" % (function, name, total))
    for r in rows: print("  " + r)
    if function in ("dupe", "pairs"): print("equal %d of %d" % (equal, total))
    else: print("measured %d of %d (a measure, not a replacement)" % (total, total))
    body = "lesson %s: %d inputs, %s" % (function, total, ("equal %d of %d" % (equal, total)) if function in ("dupe", "pairs") else "measured")
    try: record("lesson", "teach", None, clean(body))
    except RuntimeError: pass
    return equal, total
def v_retire(function, words):
    # the owner's word only: the front door reads the brain's answer alone for this function from now on
    ensure_cx(); cx_put("retired", "teach", text_key(function), 0, clock(), json.dumps({"function": function, "owner": words[:300], "ts": int(time.time())}))
    try: record("retire", "teach", None, clean("%s : %s" % (function, words)))
    except RuntimeError: pass
    print("retired from the front door on the owner word: %s; the brain answers it alone now" % function)
def retired_functions():
    out = []
    for (n, run, at, ts, v) in cx_list("retired", "teach"):
        try: out.append(json.loads(v).get("function"))
        except Exception: pass
    return [x for x in out if x]
