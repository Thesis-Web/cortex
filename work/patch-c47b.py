import re
src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:70]); src = src.replace(old, new)
rep("""        chk_note = ""; chk = run_check(name, nxt, cwd)   # C47: the cortex's own check, the worker never touched it
        if chk is not None:
            if chk["ok"]: chk_note = " check ok"
            else:
""", """        chk_note = ""; chk = run_check(name, nxt, cwd)   # C47: the cortex's own check, the worker never touched it
        if chk is not None:
            if chk["ok"]:
                chk_note = " check ok"
                if after != "done" and re.search(r"(?mi)^\\s*expected:\\s*met\\b", res.get("out") or ""):   # 11-04 16:3x (the lesson build): the cortex own print decides (C47); check ok and the worker's met line close the checkpoint, the check's print its part
                    close_by_check(name, nxt, chk); after = "done"; moved = True; chk_note += " (closed by the cortex own check)"
            else:
""")
rep("""def v_check_run(name, n):
    r = run_check(name, n)
    if r is None: raise SystemExit("no check on %s C%d; set one: cortex check %s %d : <command>" % (name, n, name, n))
    print("check %s C%d: %s | %d receipt lines typed" % (name, n, r["last"][:300], r["typed"]))
""", """def close_by_check(name, n, chk):
    # 11-04 16:3x: a checkpoint closed by the cortex own check: the check's last print (check ok ...) becomes its part by receipt, the state moves, the next opens
    rc = receipts_of(name, n).get("the cortex check") or {}; runs = [l["run"] for l in rc.get("lines", [])]
    if runs:
        idx = min(len(runs) - 1, max(0, int(chk.get("typed") or 1) - 1))
        add_part(name, n, runs[idx], "the cortex check printed: " + chk["last"][:200], 1.0, "check", {"receipt": 1})
    v_state(name, n, "done"); n2 = next_checkpoint(name)
    if n2 is not None and n2 != n:
        s2 = cx_get("state", name, n2)
        if not s2 or s2[3] != "working": v_state(name, n2, "working")
    print("C%d done by the cortex own check (check ok); next C%s" % (n, n2))
def v_check_run(name, n, close=False):
    r = run_check(name, n)
    if r is None: raise SystemExit("no check on %s C%d; set one: cortex check %s %d : <command>" % (name, n, name, n))
    print("check %s C%d: %s | %d receipt lines typed" % (name, n, r["last"][:300], r["typed"]))
    if close and r["ok"]: close_by_check(name, n, r)
    elif close: print("not closed: the check printed check wrong")
""")
rep("""        else: v_check_run(a[0], int(a[1]))
""", """        else: v_check_run(a[0], int(a[1]), "--close" in a)
""")
rep("""            else: left.append(w)
        if found and not left:
""", """            elif len(toks) == 1 and not w.startswith("pair: "):
                # C51: a word no source holds is asked of the brain's own dictionaries (define : word); the definitions typed as the source defined-words populate what the brain needed to know
                defs = kernel_define(toks[0])
                if defs:
                    src = "defined-words"
                    if not cx_get("source", src, 0): v_source(src, "reference", "definitions the brain fetched from its own dictionaries (wn, gcide, wikt, moby) when a question named a word no source held (C51, 11-04)", ["meaning", "language"])
                    typed_k = 0
                    for (frm, txt) in defs:
                        for sent in sentences(txt):
                            if is_noise(sent): continue
                            k = text_key(sent)
                            if cx_get("source", src, k): continue
                            try: r = typed("cortex source %s : %s" % (src, sent))
                            except RuntimeError: continue
                            cx_put("source", src, k, r["run"], clock(), json.dumps({"from": frm, "word": toks[0]})); key_gates(src, r["run"]); key_pairs(src, r["run"]); typed_k += 1
                    found.append("%s defined by %s (%d lines from %s)" % (w, src, typed_k, ",".join(sorted(set(f for f, t in defs)))))
                else: left.append(w)
            else: left.append(w)
        if found and not left:
""")
rep("""def numbers_in_prints(name, n, run, nums):
""", """def kernel_define(word):
    # the brain's own dictionaries asked: define : <word>; the def rows of the run's out mailbox (run N from wn: <text>) are the definitions
    try: r = ask("type main define : %s" % word)
    except Exception: return []
    out = []
    for row in (r.get("out") or []):
        if len(row) >= 4 and row[2] == "def":
            m = re.match(r"run \\d+ from (\\w+): (.*)", str(row[3]), re.S)
            if m: out.append((m.group(1), m.group(2)))
    return out
def numbers_in_prints(name, n, run, nums):
""")
open("cortex.py", "w").write(src); print("patched")
