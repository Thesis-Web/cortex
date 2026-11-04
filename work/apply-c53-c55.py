src = open("cortex.py").read(); block = open("work/c53-c55-block.py").read()
def rep(old, new, count=1):
    global src
    assert src.count(old) == count, ("anchor", src.count(old), old[:90]); src = src.replace(old, new)
rep('USAGE = """cortex <verb> ...\n', block + 'USAGE = """cortex <verb> ...\n  second <project> <run>          C53: the sixth\'s second opinion on a verdict: the guessing, the project record, the sources; a ruling and the shape the brain holds\n  dispute <project> <run> : <why>   C53: the llm disputes a verdict; the sixth rules\n  ask <project> <question>        C55: why did (run N | C n), how did (C n | run N), when did (C n), when is <day>, what next, what is <word>\n')
# the check runs with cortex on its path
rep('    try: p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=cwd, timeout=180); out = (p.stdout + ("\\n" + p.stderr if p.stderr.strip() else "")).strip()\n',
    '    try: p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=cwd, timeout=180, env=dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))); out = (p.stdout + ("\\n" + p.stderr if p.stderr.strip() else "")).strip()\n')
# C28 for db sources, by text
rep('    ing = content_gates(run)\n    for (nm, r0) in cand[:24]:\n',
    '''    for nm in srcs:   # C54: a db source has no runs; its lines are compared by text
        if source_is_db(nm):
            sc0 = source_confirms_text(nm, line_text(run), [(sym_of(a), sym_of(b)) for (a, b) in set(pairs_of(run))])
            for x in sc0["confirm"]:
                if x not in confirm: confirm.append(x)
            for d0 in sc0["disagree"]:
                if d0["source"] not in [d["source"] for d in disagree]: disagree.append(dict(d0, run=0))
    ing = content_gates(run)
    for (nm, r0) in cand[:24]:
''')
# why, quiet
rep('def v_why(name, plan=False):\n', 'def v_why(name, plan=False, quiet=False):\n')
rep('    print("why %s: %d verdicts of %d the record proves wrong%s" % (name, len(faults), len(vs), ', '    if not quiet: print("why %s: %d verdicts of %d the record proves wrong%s" % (name, len(faults), len(vs), ')
rep('    for f in faults[:30]:\n        how = WHY_RULES[f["why"]]\n', '    for f in (faults[:30] if not quiet else []):\n        how = WHY_RULES[f["why"]]\n')
# the worker's dispute line
rep('    body = re.sub(r"(?mi)^\\s*(needed|flaw):.*$", "", out)\n',
    '''    disputes = [(int(m.group(1)), m.group(2).strip()) for m in re.finditer(r"(?mi)^\\s*dispute:\\s*(?:run\\s+)?(\\d+)\\s*(.*)$", out)]
    for (dr, why) in disputes[:3]:   # C53: the worker asks for a second opinion; the sixth rules and the next hydration carries it
        try: ruling, shape = v_dispute(name, dr, why or "the worker holds it correct"); v_need(name, nxt, "the sixth on run %d: %s | %s" % (dr, ruling[:140], shape[:200]), who="sixth")
        except (SystemExit, Exception) as e: print("dispute on run %d failed: %s" % (dr, e))
    body = re.sub(r"(?mi)^\\s*(needed|flaw|dispute):.*$", "", out)
''')
# the hydration: run numbers on the refusals, and the dispute line
rep('ref.append("%s -> the number%s', 'ref.append("run %d: %s -> the number%s')
rep('% (line_text(rn)[:70], "s" if', '% (rn, line_text(rn)[:70], "s" if')
rep('    lines.append("LAWS: report only what you observed', '    if nxt is not None: lines.append("DISPUTE (C53): if a verdict called a true sentence of yours invention, hallucination or drift, add one line DISPUTE: run <run> <why> (the run numbers are in WHY THE LAST TURN DID NOT CLOSE); the sixth gives a second opinion from the guessing, the project record and the sources, and tells you the shape the brain holds so you can say it that way.")\n    lines.append("LAWS: report only what you observed')
# verbs
rep('    elif v == "sources":\n        if "--migrate" in a:', '''    elif v == "second": v_second(a[0], int(a[1]))
    elif v == "dispute":
        s8 = " ".join(a); t8 = s8.split(" : ", 1)[1] if " : " in s8 else "the worker holds it correct"; k8 = s8.split(" : ", 1)[0].split(); v_dispute(k8[0], int(k8[1]), t8)
    elif v == "ask": v_askq(a[0], " ".join(a[1:]))
    elif v == "sources":
        if "--migrate" in a:''')
open("cortex.py", "w").write(src); print("applied")
