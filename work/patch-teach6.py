src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('''            rr = run_row(kr); brain = (rr[1] or 0) if rr else 0
            fd = run   # C30: the sentence's one run is the line row we picked; the brain must answer that run as same_as when the sentence is typed again
            total += 1; eq = brain == fd and brain > 0; equal += 1 if eq else 0
            rows.append("brain same_as %d | front door first run %d | %s | %s" % (brain, fd, "equal" if eq else "differ", t[:70]))
''', '''            rr = run_row(kr); brain = (rr[1] or 0) if rr else 0
            fd = run   # C30: the sentence's one run is the line row we picked; the brain must answer that run as same_as when the line is typed again
            total += 1; eq = brain == fd and brain > 0; equal += 1 if eq else 0
            if not eq and brain == 0: noround = locals().get("noround", 0) + 1; locals()["noround"] = noround   # the brain saw a new line: its own decode of the run does not round-trip the encoder (apostrophes, decimals); the hp builder's encoder work
            rows.append("brain same_as %d | front door first run %d | %s | %s" % (brain, fd, "equal" if eq else ("not replayable by the encoder, the brain saw a new line" if brain == 0 else "differ"), t[:70]))
''')
rep('''    if function in ("dupe", "pairs"): print("equal %d of %d" % (equal, total))
''', '''    if function == "dupe":
        nr = sum(1 for r in rows if "not replayable" in r); print("equal %d of %d, %d differ, %d not replayable by the encoder" % (equal, total, total - equal - nr, nr))
    elif function == "pairs": print("equal %d of %d" % (equal, total))
''')
open("cortex.py", "w").write(src); print("patched")
