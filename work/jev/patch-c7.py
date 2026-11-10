# patch-c7.py (2026-11-10, jev C7): cortex jev opinion types a request row and prints the brain's lines; jev_brain counts lines only for questions
f = "/home/james/cortex/cortex.py"; s = open(f).read()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]; s = s.replace(old, new)
rep('''def jev_brain(verb, text, qs, rules=None):''', '''def jev_brain(verb, text, qs, rules=None, count=True):''')
rep('''    if len(rows) != len(qs): print("jev: the judge brain wrote %d answers for %d questions (request %d)" % (len(rows), len(qs), rid), file=sys.stderr); return 1, None''',
    '''    if count and len(rows) != len(qs): print("jev: the judge brain wrote %d answers for %d questions (request %d)" % (len(rows), len(qs), rid), file=sys.stderr); return 1, None''')
rep('''def jev_door():''', '''def v_jev_opinion(a):
    # jev C7 (the owner 11-06 14:46 and 11-09 00:48, as the ask): each source row a subjective-logic opinion weighted by the trust in its source, fused per atom in the
    # judge's brain (problog's rule 103 discounts and fuses; judge/judge-jev-opinion.sql prints); this verb only types the request row and prints; jev.py is not read
    path = jev_opt(a, "--rows")
    if not path: print("cortex jev opinion --rows <file>", file=sys.stderr); return 2
    text = jev_read(path)
    if text is None: return 2
    rc, lines = jev_brain("opinion", text, [], count=False)
    if rc: return rc
    sys.stdout.write("".join("%s\\n" % l for l in lines)); return 0
def jev_door():''')
rep('''    elif v == "jev" and a and a[0] in ("mln", "psl"):''', '''    elif v == "jev" and a and a[0] == "opinion":
        return v_jev_opinion(a[1:])   # jev C7: the judge brain answers; jev.py is not imported
    elif v == "jev" and a and a[0] in ("mln", "psl"):''')
rep('''  jev opinion --rows <file>                  jev C7: <atom> b= d= u= a= p= per fused opinion (trust discounted, cumulative fusion, p = b + a u)''',
    '''  jev opinion --rows <file>                  jev C7: <atom> b= d= u= a= p= per fused opinion (trust discounted, cumulative fusion, p = b + a u), in the judge brain; problog, mln, psl read opinion rows fused''')
open(f, "w").write(s); print("cortex.py: opinion verb")
