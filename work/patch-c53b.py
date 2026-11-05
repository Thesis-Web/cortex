src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('''    # read 1, the guessing: the brain's own define of the words no ground holds (the sixth's define row calls the recall define)
    none = [w for w in ((sh.get("ground") or {}).get("none") or []) if not w.startswith("pair")][:3]; guessed = []
    for w in none:
        defs = kernel_define(w)
        if defs: guessed.append("%s = %s: %s" % (w, defs[0][0], defs[0][1][:80]))
    r1 = "; ".join(guessed) if guessed else ("every word has ground, nothing to guess" if not none else "no definition in the dictionaries for " + ", ".join(none))
    print("  1 the guessing (the brain's own define): " + r1)
''', '''    # read 1, the guessing brain (the owner, 11-02, neuron run 263885: "it is another neuron brain taught to be the guessing brain"; 10-23: it makes guesses of what a word
    # meaning should be, with time and state, and back-props when the sixth returns the word wrong with reasons): NOT BUILT (neuron C13 recorded the design; the kernel's
    # guesser was taken out 10-31). This read is empty until it exists; the dictionaries are sources, read 3, not the guessing (the owner, 11-04 18:xx: ask the cortex for the prose)
    none = [w for w in ((sh.get("ground") or {}).get("none") or []) if not w.startswith("pair")][:3]
    try: gb = line_text(263885)[:150]
    except Exception: gb = ""
    r1 = "not built (neuron C13 holds the design: %s); the words with no ground it would guess at: %s" % (gb or "the owner 11-02", ", ".join(none) or "none")
    print("  1 the guessing brain: " + r1)
''')
rep('''    r3 = "%s hold %s of %d pairs%s" % (", ".join("%s %d" % kv for kv in top) or "no source", "/".join(str(c) for nm, c in top) or "0", np_, ("; " + "; ".join(found)) if found else "")
    print("  3 the sources: " + r3)
''', '''    defs = []
    for w in none[:2]:
        d0 = kernel_define(w)
        if d0: defs.append("%s = %s: %s" % (w, d0[0][0], d0[0][1][:70]))
    r3 = "%s hold %s of %d pairs%s%s" % (", ".join("%s %d" % kv for kv in top) or "no source", "/".join(str(c) for nm, c in top) or "0", np_, ("; " + "; ".join(found)) if found else "", ("; the kernel's dictionaries: " + "; ".join(defs)) if defs else "")
    print("  3 the sources (the dbs and the kernel's dictionaries): " + r3)
''')
open("cortex.py", "w").write(src); print("patched")
