src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('''            st = cx_get("states", name, n)
            if st: print("  states: " + " -> ".join("%s %s" % (h.get("state"), time.strftime("%m-%d %H:%M", time.localtime(h.get("ts") or 0))) for h in jload(st[3])[-6:]))
''', '''            hist = state_hist(name, n)
            if hist: print("  states: " + " -> ".join("%s %s" % (h.get("state"), time.strftime("%m-%d %H:%M", time.localtime(h.get("ts") or 0))) for h in hist[-6:]))
''')
rep('''            n = int(m_c.group(1)); st = cx_get("states", name, n)
            if st: print("when C%d: " % n + " -> ".join("%s at %s" % (h.get("state"), time.strftime("%m-%d %H:%M", time.localtime(h.get("ts") or 0))) for h in jload(st[3])))
            else:
                s0 = cx_get("state", name, n); print("when C%d: %s since %s (no history yet; cortex states --backfill)" % (n, s0[3] if s0 else "open", time.strftime("%m-%d %H:%M", time.localtime(s0[2])) if s0 else "-"))
''', '''            n = int(m_c.group(1)); hist = state_hist(name, n)
            if hist: print("when C%d: " % n + " -> ".join("%s at %s" % (h.get("state"), time.strftime("%m-%d %H:%M", time.localtime(h.get("ts") or 0))) for h in hist))
            else:
                s0 = cx_get("state", name, n); print("when C%d: %s since %s (no history yet; cortex states --backfill)" % (n, s0[3] if s0 else "open", time.strftime("%m-%d %H:%M", time.localtime(s0[2])) if s0 else "-"))
''')
rep('def v_askq(name, qtext):\n', '''def state_hist(name, n):
    # the state history of a checkpoint as a list (the row holds a list, or a dict with the list under hist or history); the state row itself when the history is empty
    st = cx_get("states", name, n); hist = []
    if st:
        h = jload(st[3]); hist = h if isinstance(h, list) else ((h.get("hist") or h.get("history") or []) if isinstance(h, dict) else [])
    if not hist:
        s0 = cx_get("state", name, n)
        if s0: hist = [{"state": s0[3], "run": s0[0], "at": s0[1], "ts": s0[2]}]
    return hist
def v_askq(name, qtext):
''')
open("cortex.py", "w").write(src); print("patched")
