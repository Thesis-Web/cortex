#!/usr/bin/env python3
# test_guess_distinct.py (2026-10-31): written BEFORE the change. usage: test_guess_distinct.py PORT_CONTROL PORT_CHANGED
# PORT_CONTROL = a small kernel with the old lines. PORT_CHANGED = the same kernel with the guesser taken out of define and why.
# Both have had the same line typed and have run to the end of their chain. The test reads them and decides nothing else.
#
# The owner's words it is written from:
#   2026-10-31 night: "define is from source if you add the guesser into that you are adding the fucking guessing of basically a fucking llm"
#   Reference draft 5.6: "The lookup order is memory, then state, then sources, then a guess."
#   Reference draft 5.6: "Guesses exist from day one. They are announced and never lost ... No guess is hidden."
#   Build chain 83: "Keep guessing distinct from known execution."
#
# G1  a define lays nothing in the guessing brain: from the moment of the change, no row is added to guess.corpus or left in guess.inbox.
# G2  nothing arrives from the guessing brain into a define or a why: from the moment of the change, no new guess row, no new return from gate 15.
#     (Changed once, before anything was applied live: the first form said "stays empty", which the recipe's own earlier lines made impossible.
#     The baseline is read just before the defines are typed. The run that showed it is out/g31-last.txt, kept in RESULTS.)
# G3  the source work is the same to the row with the guesser gone: every source return, every relationship row, and for every define
#     the whole set of symbols it read (known and unknown together), compared by symbol, not by gate number or run number.
#     (Changed once, before anything was applied live. The first form also compared mother's replies, which carry gate numbers and are not
#     source work, and split known from unknown, which depends on what had been defined by that moment, so on the order of the chain. That
#     split is still read and printed, not judged. The run that showed it is g31-run1-asan.txt, kept in RESULTS.)
# G3 has its own negative control: a third kernel with one source emptied must fail it (--g3only).
# Negative control: G1 and G2 must FAIL on the control kernel. If they pass there the test proves nothing, and it says so.
import socket, json, sys

def ask(port, req, t=60):
    s = socket.create_connection(("127.0.0.1", port), timeout=t); s.settimeout(t); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())

def q(port, sql): return ask(port, "q " + sql).get("rows") or []

def guess_state(port):
    return {"corpus": q(port, "SELECT count(*) FROM guess.corpus")[0][0], "inbox": q(port, "SELECT count(*) FROM guess.inbox")[0][0],
            "guesses": q(port, "SELECT count(*) FROM guess.guesses")[0][0], "returns_from_guess": q(port, "SELECT count(*) FROM main.run WHERE kind = 3 AND arrival = 15")[0][0]}

def source_work(port):
    sym = dict(q(port, "SELECT gate, symbol FROM main.label"))
    txt = "SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM main.seq s JOIN main.label l ON l.gate = s.gate WHERE s.run = r.id ORDER BY s.pos)"
    returns = sorted((sym.get(a, "?"), sym.get(g, "?"), t or "") for a, g, t in q(port, f"SELECT r.about, r.arrival, ({txt}) FROM main.run r WHERE r.kind = 3 AND r.arrival NOT IN (4, 15)"))
    rel = sorted((sym.get(a, "?"), sym.get(b, "?"), sym.get(c, "?")) for a, b, c in q(port, "SELECT gate, kind, other FROM main.rel"))
    known, unknown = q(port, "SELECT gate FROM main.label WHERE symbol = 'known'")[0][0], q(port, "SELECT gate FROM main.label WHERE symbol = 'unknown'")[0][0]
    what = {r: int(v) for r, v in q(port, "SELECT run, value FROM main.run_sheet WHERE cell = 23") if v is not None and str(v).isdigit()}
    lists = []
    for run, cell, value in q(port, f"SELECT run, cell, value FROM main.run_sheet WHERE cell IN ({known}, {unknown}) AND value IS NOT NULL"):
        names = sorted(sym.get(int(v), "?") for v in str(value).split())
        lists.append((sym.get(what.get(run), "?"), "known" if cell == known else "unknown", tuple(names)))
    read = {}
    for name, _, names in lists: read.setdefault(name, set()).update(names)
    return {"returns": returns, "rel": rel, "read": sorted((k, tuple(sorted(v))) for k, v in read.items()), "lists": sorted(set(lists))}

def diff(a, b, name, show=3):
    sa, sb = set(a), set(b)
    if sa == sb: print(f"     {name}: {len(sa)} the same in both"); return True
    print(f"     {name}: DIFFERENT, control {len(sa)}, changed {len(sb)}; only in control {len(sa - sb)}, only in changed {len(sb - sa)}")
    for x in sorted(sa - sb, key=str)[:show]: print("       control only:", str(x)[:160])
    for x in sorted(sb - sa, key=str)[:show]: print("       changed only:", str(x)[:160])
    return False

def main():
    if sys.argv[1] == "--base":
        print(json.dumps({p: guess_state(int(p)) for p in sys.argv[2:]})); return
    if sys.argv[1] == "--g3only":
        wa, wb = source_work(int(sys.argv[2])), source_work(int(sys.argv[3]))
        r = [diff(wa[k], wb[k], k) for k in ("returns", "rel", "read")]
        print("G3 negative control:", "VACUOUS, an emptied source passes G3" if all(r) else "good, an emptied source fails G3"); sys.exit(1 if all(r) else 0)
    c, n = int(sys.argv[1]), int(sys.argv[2]); base = json.load(open(sys.argv[3]))
    def added(port):
        g, b = guess_state(port), base[str(port)]
        return {k: g[k] - b[k] for k in g if k != "inbox"} | {"inbox": g["inbox"]}
    gc, gn = added(c), added(n)
    print("added since the change: control", gc, "\n                        changed", gn)
    g1 = lambda g: g["corpus"] == 0 and g["inbox"] == 0
    g2 = lambda g: g["returns_from_guess"] == 0 and g["guesses"] == 0
    print("G1 control", "passes" if g1(gc) else "fails", "| changed", "PASS" if g1(gn) else "FAIL")
    print("G2 control", "passes" if g2(gc) else "fails", "| changed", "PASS" if g2(gn) else "FAIL")
    wc, wn = source_work(c), source_work(n)
    print("G3 the source work:")
    r = [diff(wc[k], wn[k], k) for k in ("returns", "rel", "read")]
    print("G3", "PASS" if all(r) else "FAIL")
    same = len(set(wc["lists"]) & set(wn["lists"]))
    print(f"read, not judged: known and unknown split the same way on {same} of {len(set(wc['lists']) | set(wn['lists']))} lists (the split depends on the order of the chain)")
    vacuous = g1(gc) or g2(gc)
    print("negative control:", "VACUOUS, a test that the old lines pass proves nothing" if vacuous else "good, the old lines fail G1 and G2")
    sys.exit(0 if g1(gn) and g2(gn) and all(r) and not vacuous else 1)

main()
