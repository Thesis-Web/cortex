#!/usr/bin/env python3
# jev.py (2026-11-09, jev C4 to C10): our own jev, stdlib only, called by cortex.py as   cortex jev <verb> ...
# The owner, 11-09 01:30: we need the jev like system .. load in the docs to build a system like jev .. i think it is a boolean based system;
# 11-09 23:xx on where it is built: stick to the outline .. proceed. The verbs are the outline's (jev C3, written by claude opus from the
# hydration of the ask: build the outline of jev):
#   ask        C4  a state file and typed questions <id>:<formula> -> one noul = p(true) per id, in the order given (typesafe-jev-docs introduction/quickstart.md:307)
#   problog    C5  the distribution semantics: every clause p::head :- body is in a world with probability p, independently; p(query) is the summed
#                  weight of the worlds whose least model holds the query (de-raedt-2007-problog.txt:23, :54)
#   mln        C6  weighted soft rules on top: a world's weight times exp(sum w_i n_i(x)), n_i(x) the true groundings of rule i (richardson-domingos-2006 :81)
#   opinion    C7  subjective logic: each row an opinion (b, d, u, a) discounted by the trust in its source, fused per atom, p = b + a u (josang-2001 :29, :31)
#   why, retract   C8  every answer keeps its reasons (the rows its p depends on) in the brain; a retracted row revises only the answers that listed it
#   verify     C9  a claim split into atomic facts, each supported, refuted or not enough info by the source rows; score = supported / facts (thorne-2018-fever, min-2023-factscore)
#   calibrate  C10 a jury's samples pooled into one p (self-consistency), checked against held-out labels: buckets and the expected calibration error (guo-2017)
# Inference is exact: the worlds of the clauses an answer depends on are enumerated, at most 2^16 of them. No model, no network.
import sys, os, re, json, math, itertools, sqlite3, difflib, time

USAGE = """cortex jev: our own jev (jev C4 to C10)
  cortex jev ask --state <file> --q <id>:<formula> [--q ...]     one line <id> noul=<p> per question, in the order given (C4); each answer's reasons kept in the brain (C8)
  cortex jev problog --clauses <file> --query <atom or formula>  p=<value>, the distribution semantics (C5)
  cortex jev mln --rules <file> --state <file> --query <atom>     p=<value>, the clauses' worlds weighted by exp(sum w_i n_i(x)) (C6); weight 0 rules change nothing
  cortex jev opinion --rows <file>                                one line <atom> b= d= u= a= p= per fused opinion (C7)
  cortex jev why <id>                                             the path:line of each row the answer <id> depends on (C8)
  cortex jev retract <row id> [--undo]                            the row leaves every state; the answers that listed it are revised (C8)
  cortex jev verify --claim <text> --source <db or file or source name>   one line <fact> label=<supported|refuted|nei> row=<path:line or none> per fact, then score= (C9)
  cortex jev calibrate --set <file> [--bins k]                    bucket=<lo-hi> n= mean_p= freq= per bucket that holds questions, then ece= (C10)
  CORTEX_PORT=7010 cortex jev <project ...> [--n k] [--seed s]    rail C6: the judge brain's jev beside the python judge (not these verbs)
files:
  a state or clauses file is JSON or ProbLog text.
    ProbLog text: one clause a line, p::head :- body1, body2.  (head. alone = p 1; % starts a comment); a row's id is r<line>, its path:line the file and line
    JSON: {"rows": [row, ...], "rules": [rule, ...]} or a list of rows or {"<atom>": p, ...}
      row: {"id": "r1", "atom": "rain", "if": ["cloudy"], "p": 0.7, "source": "s", "path": "f.txt", "line": 12}  or  {"id": "r2", "clause": "0.7::rain :- cloudy."}
      opinion row: {"id": "r3", "atom": "rain", "b": 0.6, "d": 0.1, "u": 0.3, "a": 0.5, "trust": 0.8}  (a defaults to 0.5, trust to 1)
      rule: "1.5 smokes(X) and friends(X,Y) => smokes(Y)"  or  {"w": 1.5, "rule": "..."}
  a rules file: one rule a line, <weight> <formula> (% or # starts a comment), or JSON as above
  a formula: atoms with and or not => <=> (also & , | ! ~ -> <->), parentheses, true, false; an atom is name or name(arg,...);
    a capitalised argument is a variable (rules only), grounded over the constants of the state; an atom no clause makes is false
  rows with b, d, u (or a trust) are opinions: discounted by trust, fused per atom and body (cumulative fusion), then one clause p = b + a u;
    a trust 0 row is vacuous and left out; rows with a bare p are independent clauses
  a claim: one fact a line; a one-line claim is split at ; and at sentence ends (a source row copied whole stays one fact)
  a source: a sqlite db with a corpus table (path, line, text; cx.db), a JSON list of {path, line, text} or strings, a text file (one row a line),
    or the name of a source in the cortex source db
  a set: JSON list or JSON lines, each {"id", "label": true|false, "p": x} or {"samples": [true, false, ...]} (the fraction true) or {"jury": [p, ...]} (the mean)"""

MAXV = 16        # exact inference: an answer's uncertain clauses, 2^16 worlds at most
MAXG = 20000     # the groundings of one rule

class JevError(Exception): pass

def fmt(x):
    s = ("%.12f" % x).rstrip("0")
    if s.endswith("."): s += "0"
    return "0.0" if s == "-0.0" else s
def fmtp(p): return fmt(min(1.0, max(0.0, p)))
def num(v, what, lo=0.0, hi=1.0):
    if isinstance(v, bool): raise JevError("%s is not a number: %r" % (what, v))
    try: x = float(v)
    except (TypeError, ValueError): raise JevError("%s is not a number: %r" % (what, v))
    if not math.isfinite(x) or (lo is not None and x < lo) or (hi is not None and x > hi):
        raise JevError("%s = %r is outside %s to %s" % (what, v, lo, hi))
    return x
def read_file(path):
    try:
        with open(path, encoding="utf-8") as f: return f.read()
    except OSError as e: raise JevError("cannot read %s: %s" % (path, e.strerror))

# ---- formulas: atoms, and, or, not, implies, iff ----
NAME = re.compile(r"[A-Za-z0-9_]+")
ARG = re.compile(r"[A-Za-z0-9_.'+-]+")
KW = {"and": ("op", "&"), "or": ("op", "|"), "not": ("op", "!"), "true": ("T",), "false": ("F",)}
def tokens(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace(): i += 1; continue
        hit = next((op for lit, op in (("<=>", "<=>"), ("<->", "<=>"), ("=>", "=>"), ("->", "=>"), ("\\+", "!")) if s.startswith(lit, i)), None)
        if hit:
            out.append(("op", hit)); i += 3 if hit == "<=>" else 2; continue
        if c in "!~": out.append(("op", "!")); i += 1; continue
        if c in "&^,": out.append(("op", "&")); i += 1; continue
        if c == "|": out.append(("op", "|")); i += 1; continue
        if c in "()": out.append(("op", c)); i += 1; continue
        m = NAME.match(s, i)
        if not m: raise JevError("cannot read %r at %r" % (s, s[i:i + 12]))
        name, i = m.group(0), m.end()
        if name.lower() in KW: out.append(KW[name.lower()]); continue
        args = ()
        if i < n and s[i] == "(":
            j = s.find(")", i)
            if j < 0: raise JevError("an atom with no ) in %r" % s)
            args = tuple(x.strip() for x in s[i + 1:j].split(","))
            if not all(ARG.fullmatch(x) for x in args): raise JevError("cannot read the arguments of %s in %r" % (name, s))
            i = j + 1
        out.append(("atom", name, args))
    return out
def parse(s):
    toks = tokens(s); pos = [0]
    if not toks: raise JevError("an empty formula")
    def peek(): return toks[pos[0]] if pos[0] < len(toks) else ("end",)
    def isop(t, x): return t[0] == "op" and t[1] == x
    def take(): t = peek(); pos[0] += 1; return t
    def iff():
        l = imp()
        while isop(peek(), "<=>"): take(); l = ("<=>", l, imp())
        return l
    def imp():
        l = orx()
        if isop(peek(), "=>"): take(); return ("=>", l, imp())
        return l
    def orx():
        l = andx()
        while isop(peek(), "|"): take(); l = ("|", l, andx())
        return l
    def andx():
        l = un()
        while isop(peek(), "&"): take(); l = ("&", l, un())
        return l
    def un():
        t = take()
        if isop(t, "!"): return ("!", un())
        if isop(t, "("):
            e = iff()
            if not isop(take(), ")"): raise JevError("a ( with no ) in %r" % s)
            return e
        if t[0] in ("T", "F", "atom"): return t
        raise JevError("cannot read %r: %s where an atom was expected" % (s, t[1] if len(t) > 1 else "the end"))
    e = iff()
    if pos[0] != len(toks): raise JevError("cannot read %r past %s" % (s, toks[pos[0]][1]))
    return e
def is_var(x): return x[:1].isupper() or x[:1] == "_"
def akey(name, args, sub=None):
    if sub: args = tuple(sub.get(x, x) for x in args)
    return name + ("(" + ",".join(args) + ")" if args else "")
def walk(e):
    if e[0] == "atom": yield e
    elif e[0] not in ("T", "F"):
        for x in e[1:]: yield from walk(x)
def atoms_of(e, sub=None): return {akey(t[1], t[2], sub) for t in walk(e)}
def vars_of(e): return sorted({x for t in walk(e) for x in t[2] if is_var(x)})
def compile_(e, bit, sub=None):
    # the formula as a function of a world, a bit mask of its true atoms
    k = e[0]
    if k == "atom":
        b = bit[akey(e[1], e[2], sub)]; return lambda m: (m >> b) & 1 == 1
    if k == "T": return lambda m: True
    if k == "F": return lambda m: False
    if k == "!":
        f = compile_(e[1], bit, sub); return lambda m: not f(m)
    l, r = compile_(e[1], bit, sub), compile_(e[2], bit, sub)
    if k == "&": return lambda m: l(m) and r(m)
    if k == "|": return lambda m: l(m) or r(m)
    if k == "=>": return lambda m: (not l(m)) or r(m)
    return lambda m: l(m) == r(m)
def norm_atom(s, what="an atom"):
    t = tokens(str(s))
    if len(t) != 1 or t[0][0] != "atom": raise JevError("%s is not one atom: %r" % (what, s))
    if any(is_var(x) for x in t[0][2]): raise JevError("%s %r has a variable; a clause is ground here (write its ground instances)" % (what, s))
    return akey(t[0][1], t[0][2])

# ---- rows and clauses ----
PROB = re.compile(r"^\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*::\s*")
def split_top(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(": depth += 1
        elif ch == ")": depth -= 1
        if ch == "," and depth == 0: out.append(cur); cur = ""
        else: cur += ch
    out.append(cur); return [x.strip() for x in out if x.strip()]
def parse_clause(t):
    s = t.strip()
    if s.endswith("."): s = s[:-1].rstrip()
    p, m = 1.0, PROB.match(s)
    if m: p = num(m.group(1), "the probability of %r" % t); s = s[m.end():]
    if ";" in s: raise JevError("an annotated disjunction is not built: %r" % t)
    head, sep, body = s.partition(":-")
    lits = split_top(body) if sep else []
    for x in lits:
        if x.startswith("\\+") or x.lower().startswith("not ") or x.lower().startswith("not("): raise JevError("negation in a clause body is not built: %r" % t)
    return p, norm_atom(head.strip(), "the head of %r" % t), tuple(norm_atom(x, "a body atom of %r" % t) for x in lits)
class Row:
    __slots__ = ("id", "head", "body", "p", "op", "trust", "source", "path", "line")
def row_of(r, k, path=None, lineno=None):
    if isinstance(r, str): r = {"clause": r}
    if not isinstance(r, dict): raise JevError("row %d is neither an object nor a clause: %r" % (k + 1, r))
    x = Row()
    x.id = str(r["id"]) if r.get("id") is not None else "r%d" % (lineno or k + 1)
    x.source = r.get("source"); x.path = r.get("path", path); x.line = r.get("line", lineno)
    if r.get("clause") is not None: p, x.head, x.body = parse_clause(str(r["clause"]))
    else:
        h = r.get("atom", r.get("head"))
        if h is None: raise JevError("row %s has no atom" % x.id)
        x.head = norm_atom(h, "the atom of row %s" % x.id)
        body = r.get("if", r.get("body")) or []
        if isinstance(body, str): body = split_top(body)
        x.body = tuple(norm_atom(b, "a body atom of row %s" % x.id) for b in body)
        p = r.get("p", 1.0)
    x.p = num(p, "p of row %s" % x.id)
    x.trust = num(r.get("trust", 1.0), "trust of row %s" % x.id)
    if any(k2 in r for k2 in ("b", "d", "u")):
        b, d, u = (num(r.get(k2, 0.0), "%s of row %s" % (k2, x.id)) for k2 in ("b", "d", "u"))
        s = b + d + u
        if abs(s - 1.0) > 1e-6: raise JevError("row %s: b + d + u = %s, an opinion needs 1" % (x.id, fmt(s)))
        x.op = (b / s, d / s, u / s, num(r.get("a", 0.5), "a of row %s" % x.id))
    elif "trust" in r: x.op = (x.p, 1.0 - x.p, 0.0, num(r.get("a", 0.5), "a of row %s" % x.id))   # a bare p with a trust: a dogmatic opinion, discounted
    else: x.op = None
    return x
WRULE = re.compile(r"^\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*(?:::)?\s+(.+?)\s*$")
def rule_of(x, k):
    if isinstance(x, str):
        m = WRULE.match(x)
        if not m: raise JevError("rule %d is not <weight> <formula>: %r" % (k + 1, x))
        w, f = m.group(1), m.group(2)
    elif isinstance(x, dict) and ("w" in x or "weight" in x): w, f = x.get("w", x.get("weight")), x.get("rule", x.get("formula"))
    else: raise JevError("rule %d is neither <weight> <formula> nor {w, rule}: %r" % (k + 1, x))
    if f is None: raise JevError("rule %d has no formula" % (k + 1))
    return (num(w, "the weight of rule %d" % (k + 1), None, None), parse(str(f)))
def rules_of(xs):
    if not isinstance(xs, list): raise JevError("the rules are a list")
    return [rule_of(x, k) for k, x in enumerate(xs)]
def load_rules(path):
    text = read_file(path)
    try: obj = json.loads(text)
    except ValueError: obj = None
    if obj is None: return rules_of([s for s in (re.split(r"[%#]", l, 1)[0].strip() for l in text.splitlines()) if s])
    return rules_of(obj.get("rules", []) if isinstance(obj, dict) else obj)
def load_state(path):
    text = read_file(path)
    try: obj = json.loads(text)
    except ValueError: obj = None
    rows, rules = [], []
    if obj is None:
        for i, line in enumerate(text.splitlines(), 1):
            s = line.split("%", 1)[0].strip()
            if s: rows.append(row_of({"clause": s}, len(rows), path, i))
    elif isinstance(obj, dict) and obj and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in obj.values()):
        rows = [row_of({"atom": a, "p": v}, k) for k, (a, v) in enumerate(obj.items())]
    else:
        rs = obj if isinstance(obj, list) else (obj.get("rows", obj.get("clauses")) if isinstance(obj, dict) else None)
        if not isinstance(rs, list): raise JevError("%s: a state is a list of rows or {\"rows\": [...]}" % path)
        rows = [row_of(r, k) for k, r in enumerate(rs)]
        if isinstance(obj, dict): rules = rules_of(obj.get("rules") or [])
    seen = set()
    for r in rows:
        if r.id in seen: raise JevError("the row id %s is twice in %s" % (r.id, path))
        seen.add(r.id)
    return rows, rules

# ---- subjective logic (C7) ----
def fuse(rs):
    # each row's opinion discounted by its trust t (b' = t b, d' = t d, u' = 1 - t (b + d)), then cumulative fusion: evidence adds (r = 2b/u, s = 2d/u),
    # dogmatic opinions (u = 0) average; the base rate weighted by 1 - u; p = b + a u
    ops = []
    for r in rs:
        b, d, u, a = r.op; t = r.trust
        ops.append((t * b, t * d, max(0.0, 1.0 - t * (b + d)), a, t))
    dog = [o for o in ops if o[2] <= 0.0]
    if dog: b, d, u = sum(o[0] for o in dog) / len(dog), sum(o[1] for o in dog) / len(dog), 0.0
    else:
        R = sum(2.0 * o[0] / o[2] for o in ops); S = sum(2.0 * o[1] / o[2] for o in ops); z = 2.0 + R + S
        b, d, u = R / z, S / z, 2.0 / z
    wa = sum(1.0 - o[2] for o in ops)
    a = sum(o[3] * (1.0 - o[2]) for o in ops) / wa if wa > 0.0 else sum(o[3] * o[4] for o in ops) / sum(o[4] for o in ops)
    return b, d, u, a, b + a * u
class Clause:
    __slots__ = ("head", "body", "p", "rows")
    def __init__(self, head, body, p, rows): self.head, self.body, self.p, self.rows = head, body, p, rows
def opinion_groups(rows):
    # the opinion rows of one head and body, in the order of their first trusted row; a trust 0 row is vacuous and carries nothing, not even its base rate
    groups = {}
    for r in rows:
        if r.op is None or r.trust <= 0.0: continue
        groups.setdefault((r.head, r.body), []).append(r)
    return groups
def clauses_of(rows):
    groups, out, done = opinion_groups(rows), [], set()
    for r in rows:
        if r.op is None: out.append(Clause(r.head, r.body, r.p, (r,)))
        elif r.trust > 0.0 and (r.head, r.body) not in done:
            key = (r.head, r.body); done.add(key); rs = groups[key]
            out.append(Clause(key[0], key[1], fuse(rs)[4], tuple(rs)))
    return out

# ---- inference (C5, C6) ----
def ground(rules, rows):
    consts = set()
    for r in rows:
        for a in (r.head,) + r.body:
            if "(" in a: consts.update(x for x in a[a.index("(") + 1:-1].split(",") if x)
    for (w, e) in rules:
        for t in walk(e): consts.update(x for x in t[2] if not is_var(x))
    consts, out = sorted(consts), []
    for (w, e) in rules:
        if w == 0.0: continue   # exp(0 n) = 1 in every world
        vs = vars_of(e)
        if not vs: out.append((w, e, None, tuple(sorted(atoms_of(e))))); continue
        if not consts: continue
        if len(consts) ** len(vs) > MAXG: raise JevError("a rule with %d variables over %d constants has more than %d groundings" % (len(vs), len(consts), MAXG))
        for combo in itertools.product(consts, repeat=len(vs)):
            sub = dict(zip(vs, combo)); out.append((w, e, sub, tuple(sorted(atoms_of(e, sub)))))
    return out
def infer(clauses, grounds, f, fatoms):
    # p(f): the clauses f depends on (backward through the bodies; with soft rules every atom a grounding or a clause ties to them), each in a world with
    # its p independently; a world is its least model; its weight times exp(the summed weights of its true groundings); exact by enumeration
    seen, todo = set(fatoms), list(fatoms)
    gs = [g for g in grounds if g[3]]
    if gs:
        nb = {}
        for atoms in [(c.head,) + c.body for c in clauses] + [g[3] for g in gs]:
            for x in atoms: nb.setdefault(x, set()).update(atoms)
        while todo:
            for x in sorted(nb.get(todo.pop(), ())):
                if x not in seen: seen.add(x); todo.append(x)
        gs = [g for g in gs if g[3][0] in seen]
    else:
        heads = {}
        for c in clauses: heads.setdefault(c.head, []).append(c)
        while todo:
            for c in heads.get(todo.pop(), ()):
                for x in c.body:
                    if x not in seen: seen.add(x); todo.append(x)
    cs = [c for c in clauses if c.head in seen and c.p > 0.0]
    bit = {a: i for i, a in enumerate(sorted(seen))}
    fn = compile_(f, bit)
    if not gs and all(not c.body for c in cs):
        pf = {}   # facts only: an atom is false when none of its clauses is in the world
        for c in cs: pf[c.head] = pf.get(c.head, 1.0) * (1.0 - c.p)
        base = sum(1 << bit[a] for a in sorted(pf) if pf[a] <= 0.0)
        unc = [a for a in sorted(pf) if 0.0 < pf[a] < 1.0]
        if len(unc) > MAXV: raise JevError("the answer depends on %d uncertain atoms; exact inference is bounded at %d" % (len(unc), MAXV))
        tot = 0.0
        for mask in range(1 << len(unc)):
            w, m = 1.0, base
            for i, a in enumerate(unc):
                if mask >> i & 1: w *= 1.0 - pf[a]; m |= 1 << bit[a]
                else: w *= pf[a]
            if fn(m): tot += w
        return tot, seen
    fixed = [c for c in cs if c.p >= 1.0]; var = [c for c in cs if c.p < 1.0]
    if len(var) > MAXV: raise JevError("the answer depends on %d uncertain clauses; exact inference is bounded at %d" % (len(var), MAXV))
    order = fixed + var; nf = len(fixed)
    hb = [1 << bit[c.head] for c in order]; bb = [sum(1 << bit[x] for x in set(c.body)) for c in order]
    gf = [(w, compile_(e, bit, sub)) for (w, e, sub, atoms) in gs]
    ws, ts, es = [], [], []
    for mask in range(1 << len(var)):
        w = 1.0
        for i, c in enumerate(var): w *= c.p if mask >> i & 1 else 1.0 - c.p
        on = list(range(nf)) + [nf + i for i in range(len(var)) if mask >> i & 1]
        m = 0
        while True:   # the least model of the clauses in this world
            m0 = m
            for j in on:
                if m & bb[j] == bb[j]: m |= hb[j]
            if m == m0: break
        ws.append(w); ts.append(fn(m))
        if gf: es.append(sum(wt for (wt, g) in gf if g(m)))
    if not gf: return sum(w for w, t in zip(ws, ts) if t), seen
    emax = max(es); num_, den = 0.0, 0.0
    for w, e, t in zip(ws, es, ts):
        x = w * math.exp(e - emax); den += x
        if t: num_ += x
    if den <= 0.0: raise JevError("no world has weight")
    return num_ / den, seen
def answer(rows, rules, f, fatoms): return infer(clauses_of(rows), ground(rules, rows), f, fatoms)
def why_rows(rows, rules, f, fatoms, p, seen):
    # the rows the answer depends on: those whose removal changes the printed p (the same computation a fresh ask makes after a retract)
    sp, anyvar = fmtp(p), any(vars_of(e) for (w, e) in rules if w)
    out = []
    for r in rows:
        if not (anyvar or r.head in seen) or (r.op is not None and r.trust <= 0.0): continue
        if fmtp(answer([x for x in rows if x is not r], rules, f, fatoms)[0]) != sp: out.append(r)
    return out
def question(form, what):
    f = parse(form)
    vs = vars_of(f)
    if vs: raise JevError("%s: %s is a variable; a question is ground" % (what, vs[0]))
    return f, atoms_of(f)

# ---- the verbs ----
def opt(a, flag):
    i = a.index(flag) if flag in a else -1
    return a[i + 1] if 0 <= i < len(a) - 1 else None
def opts(a, flag): return [a[i + 1] for i in range(len(a) - 1) if a[i] == flag]
def rowref(r): return {"id": r.id, "source": r.source, "path": r.path, "line": r.line}
def where(r):
    return "%s:%s" % (r.get("path") or r.get("source") or "-", r.get("line") if r.get("line") is not None else "-")
def answers(state, forms, door):
    rows, rules = load_state(state)
    gone = door["retracted"]([r.id for r in rows]); live = [r for r in rows if r.id not in gone]
    out = []
    for (qid, form) in forms:
        f, fa = question(form, "question " + qid)
        p, seen = answer(live, rules, f, fa)
        out.append((qid, {"q": form, "state": os.path.abspath(state), "noul": fmtp(p), "rows": [rowref(r) for r in why_rows(live, rules, f, fa, p, seen)], "ts": int(time.time())}))
    return out
def v_ask(a, door):
    state, qs = opt(a, "--state"), opts(a, "--q")
    if not state or not qs: raise JevError("cortex jev ask --state <file> --q <id>:<formula> [--q ...]")
    forms = []
    for item in qs:
        qid, sep, form = item.partition(":")
        qid, form = qid.strip(), form.strip()
        if form.lower().startswith("noul:"): form = form[5:].strip()   # the question's type; noul (p of true) is the type built
        if not sep or not qid or not form: raise JevError("a question is <id>:<formula>, not %r" % item)
        forms.append((qid, form))
    recs = answers(state, forms, door)
    door["record"](recs)
    sys.stdout.write("".join("%s noul=%s\n" % (qid, d["noul"]) for qid, d in recs))
def v_problog(a):
    path, query = opt(a, "--clauses"), opt(a, "--query")
    if not path or not query: raise JevError("cortex jev problog --clauses <file> --query <atom>")
    rows, _ = load_state(path); f, fa = question(query, "the query")
    print("p=" + fmtp(answer(rows, [], f, fa)[0]))
def v_mln(a):
    rpath, spath, query = opt(a, "--rules"), opt(a, "--state"), opt(a, "--query")
    if not rpath or not spath or not query: raise JevError("cortex jev mln --rules <file> --state <file> --query <atom>")
    rows, srules = load_state(spath); f, fa = question(query, "the query")
    print("p=" + fmtp(answer(rows, srules + load_rules(rpath), f, fa)[0]))
def v_opinion(a):
    path = opt(a, "--rows")
    if not path: raise JevError("cortex jev opinion --rows <file>")
    rows, _ = load_state(path)
    for r in rows:
        if r.op is None: r.op = (r.p, 1.0 - r.p, 0.0, 0.5)   # every source row gets an opinion: a bare p is a dogmatic one
    groups = opinion_groups(rows)
    for key in sorted(groups, key=lambda k: (k[0], k[1])):
        b, d, u, a_, p = fuse(groups[key])
        print("%s b=%s d=%s u=%s a=%s p=%s" % (key[0] + (" :- " + ", ".join(key[1]) if key[1] else ""), fmt(b), fmt(d), fmt(u), fmt(a_), fmtp(p)))
def v_why(a, door):
    if not a: raise JevError("cortex jev why <id>")
    v = door["get"]("jevwhy", a[0])
    if v is None: raise JevError("no answer under the id %s (cortex jev ask keeps each answer's reasons)" % a[0])
    d = json.loads(v)
    if not d["rows"]: print("none: the answer %s noul=%s depends on no row" % (a[0], d["noul"])); return
    for r in d["rows"]: print("%s row=%s%s" % (where(r), r["id"], (" source=%s" % r["source"]) if r.get("source") else ""))
def v_retract(a, door):
    if not a: raise JevError("cortex jev retract <row id> [--undo]")
    rid, undo = a[0], "--undo" in a
    door["put"]("jevretract", rid, json.dumps({"retracted": not undo, "ts": int(time.time())}))
    revised = 0
    for qid in json.loads(door["get"]("jevdep", rid) or "[]"):
        v = door["get"]("jevwhy", qid)
        if not v: continue
        d = json.loads(v)
        if not undo and not any(r["id"] == rid for r in d["rows"]): continue   # its answer no longer lists the row
        try: rec = answers(d["state"], [(qid, d["q"])], door)
        except JevError as e: print("%s not revised: %s" % (qid, e)); continue
        door["record"](rec); revised += 1
        print("revised %s noul=%s -> noul=%s" % (qid, d["noul"], rec[0][1]["noul"]))
    print("%s row %s: %d answers listed it and were revised; no other answer is touched" % ("restored" if undo else "retracted", rid, revised))

# ---- claim verification (C9) ----
STOPV = set("a an the of to in on at by for with and or is are was were be been being it its this that these those as from into than then so such".split())
NEG = {"not", "no", "never", "cannot", "nor", "none", "nobody", "nothing", "neither", "without", "nowhere"}
def vtoks(s): return re.findall(r"[a-z0-9]+(?:['.,][a-z0-9]+)*", s.lower().replace("’", "'"))
def rwords(s): return sorted({w for w in re.findall(r"[a-z]{2,}|[0-9]+", s.lower()) if w not in STOPV})
def is_neg(t): return t in NEG or t.endswith("n't")
def is_num(t): return t[:1].isdigit()
class MemSrc:
    def __init__(self, items):   # items: (where, text), in source order
        self.items, self.exact, self.inv = items, {}, {}
        for i, (w, t) in enumerate(items):
            self.exact.setdefault(tuple(vtoks(t)), i)
            for x in rwords(t): self.inv.setdefault(x, []).append(i)
    def is_row(self, text): return tuple(vtoks(text)) in self.exact
    def cands(self, text):
        hit = {}
        for x in rwords(text):
            for i in self.inv.get(x, ())[:5000]: hit[i] = hit.get(i, 0) + 1
        ex = self.exact.get(tuple(vtoks(text)))
        ids = ([ex] if ex is not None else []) + [i for i in sorted(hit, key=lambda i: (-hit[i], i))[:40] if i != ex]
        return [self.items[i] for i in ids]
class DbSrc:
    def __init__(self, path, source=None):
        try:
            self.c = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=30)
            tabs = {r[0] for r in self.c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        except sqlite3.Error as e: raise JevError("the source db %s did not open: %s" % (path, e))
        if "corpus" not in tabs: raise JevError("the source db %s has no corpus table" % path)
        cols = {r[1] for r in self.c.execute("PRAGMA table_info(corpus)")}
        if "text" not in cols: raise JevError("the corpus table of %s has no text column" % path)
        self.sf, self.sa = (" AND source = ?", (source,)) if source else ("", ())
        if source and not self.c.execute("SELECT 1 FROM corpus WHERE source = ? LIMIT 1", (source,)).fetchone(): raise JevError("no source %s in %s" % (source, path))
        sel = ", ".join(x if x in cols else "NULL" for x in ("source", "path", "line"))
        self.sel = "SELECT id, %s, text FROM corpus" % sel
        self.mem = None
        if "words" not in tabs:
            self.mem = MemSrc([(self.where(r), r[4]) for r in self.c.execute(self.sel + " WHERE 1 = 1" + self.sf + " ORDER BY id", self.sa)])
    def where(self, r): return "%s:%s" % (r[2] or r[1] or "-", r[3] if r[3] is not None else "-")
    def is_row(self, text):
        if self.mem: return self.mem.is_row(text)
        t = tuple(vtoks(text)); return any(tuple(vtoks(x)) == t for (_, x) in self.cands(text)[:3])
    def cands(self, text):
        if self.mem: return self.mem.cands(text)
        rows = list(self.c.execute(self.sel + " WHERE text = ?" + self.sf + " ORDER BY id LIMIT 5", (text.strip(),) + self.sa))
        cnt = sorted((self.c.execute("SELECT count(*) FROM words WHERE word = ?" + self.sf, (w,) + self.sa).fetchone()[0], w) for w in rwords(text))
        hit = {}
        for n, w in [x for x in cnt if x[0] > 0][:6]:
            for (i,) in self.c.execute("SELECT id FROM words WHERE word = ?" + self.sf + " LIMIT 5000", (w,) + self.sa): hit[i] = hit.get(i, 0) + 1
        have = {r[0] for r in rows}
        for i in sorted(hit, key=lambda i: (-hit[i], i))[:40]:
            if i not in have: rows += list(self.c.execute(self.sel + " WHERE id = ?", (i,)))
        return [(self.where(r), r[4]) for r in rows]
def open_source(arg, door):
    if os.path.isfile(arg):
        with open(arg, "rb") as fh: head = fh.read(16)
        if head.startswith(b"SQLite format 3"): return DbSrc(arg)
        text = read_file(arg)
        try: obj = json.loads(text)
        except ValueError: obj = None
        if isinstance(obj, list):
            items = []
            for k, x in enumerate(obj):
                if isinstance(x, str): items.append(("%s:%d" % (arg, k + 1), x))
                elif isinstance(x, dict) and x.get("text") is not None: items.append(("%s:%s" % (x.get("path") or x.get("source") or arg, x.get("line", k + 1)), str(x["text"])))
                else: raise JevError("source row %d of %s has no text" % (k + 1, arg))
            return MemSrc(items)
        return MemSrc([("%s:%d" % (arg, i), l) for i, l in enumerate(text.splitlines(), 1) if l.strip()])
    db = door["cxdb"]()
    if not os.path.isfile(db): raise JevError("%s is not a file and there is no cortex source db at %s" % (arg, db))
    return DbSrc(db, arg)
def contains(big, small):
    n = len(small)
    return any(big[i:i + n] == small for i in range(len(big) - n + 1))
def label_fact(fact, src):
    ft = vtoks(fact)
    if not ft: return "nei", None
    cands = [(w, vtoks(t)) for (w, t) in src.cands(fact)]
    for (w, rt) in cands:
        if rt == ft: return "supported", w
    if len(ft) >= 8:
        for (w, rt) in cands:
            if contains(rt, ft): return "supported", w
    best = None
    for (w, rt) in cands:
        sm = difflib.SequenceMatcher(None, ft, rt, autojunk=False)
        same = sum(b.size for b in sm.get_matching_blocks())
        score = (min(same / len(ft), same / max(1, len(rt))), same)
        if best is None or score > best[0]: best = (score, w, sm, rt)
    if best and best[0][0] >= 0.7:
        sm, rt = best[2], best[3]; fx, rx, swaps = [], [], 0
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal": continue
            fx += ft[i1:i2]; rx += rt[j1:j2]
            if op == "replace" and i2 - i1 == 1 and j2 - j1 == 1: swaps += 1
        if sum(map(is_neg, fx)) % 2 != sum(map(is_neg, rx)) % 2: return "refuted", best[1]   # the row says the opposite
        nf, nr = [t for t in fx if is_num(t)], [t for t in rx if is_num(t)]
        if nf and nr and nf != nr: return "refuted", best[1]   # the row holds another number there
        if swaps and len(fx) == swaps and len(rx) == swaps: return "refuted", best[1]   # the row holds another word there, the rest the same
    return "nei", None
def near_row(text, src):
    # the share of the text's words a single source row holds in order (and of the row's words the text holds): a near copy of one row is near 1
    ft, best = vtoks(text), 0.0
    if not ft: return 0.0
    for (w, t) in src.cands(text)[:12]:
        rt = vtoks(t); same = sum(b.size for b in difflib.SequenceMatcher(None, ft, rt, autojunk=False).get_matching_blocks())
        best = max(best, min(same / len(ft), same / max(1, len(rt))))
    return best
def facts_of(claim, src):
    lines = [l.strip() for l in claim.splitlines() if l.strip()]
    if len(lines) != 1: return lines
    parts = [x.strip() for x in re.split(r"\s*;\s*|(?<=[.!?])\s+", lines[0]) if x.strip()]
    out, i = [], 0
    while i < len(parts):   # cut at every sentence end, then a span that is one source row, copied or changed a little, is one fact again
        j = min(len(parts), i + 6)
        while j > i + 1 and not (src.is_row(" ".join(parts[i:j])) or near_row(" ".join(parts[i:j]), src) >= 0.8): j -= 1
        out.append(" ".join(parts[i:j])); i = j
    return [x for x in out if vtoks(x)]
def v_verify(a, door):
    claim, source = opt(a, "--claim"), opt(a, "--source")
    if claim is None or not source: raise JevError("cortex jev verify --claim <text> --source <db or file or source name>")
    src = open_source(source, door); facts = facts_of(claim, src)
    if not facts: raise JevError("the claim holds no fact")
    sup = 0
    for fact in facts:
        lab, w = label_fact(fact, src); sup += lab == "supported"
        print("%s label=%s row=%s" % (re.sub(r"\s+", " ", fact), lab, w or "none"))
    print("score=%s" % fmt(sup / len(facts)))

# ---- calibration (C10) ----
def to_label(v, what):
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)) and v in (0, 1): return bool(v)
    if isinstance(v, str) and v.strip().lower() in ("true", "false", "yes", "no", "1", "0"): return v.strip().lower() in ("true", "yes", "1")
    raise JevError("%s: the label %r is not true or false" % (what, v))
def pooled(x, what):
    if "p" in x: return num(x["p"], "%s: p" % what)
    s = x.get("samples", x.get("jury", x.get("votes")))
    if not isinstance(s, list) or not s: raise JevError("%s has no p and no samples" % what)
    if all(isinstance(v, bool) for v in s): return sum(1 for v in s if v) / len(s)   # self-consistency: the fraction of the samples that say true
    return sum(num(v, "%s: a sample" % what) for v in s) / len(s)   # a jury of p's: their mean
def v_calibrate(a):
    path = opt(a, "--set"); bins = int(opt(a, "--bins") or 10)
    if not path: raise JevError("cortex jev calibrate --set <file> [--bins k]")
    if bins < 1: raise JevError("--bins is at least 1")
    text = read_file(path)
    try: items = json.loads(text)
    except ValueError:
        try: items = [json.loads(l) for l in text.splitlines() if l.strip()]
        except ValueError: raise JevError("%s is neither JSON nor JSON lines" % path)
    if isinstance(items, dict): items = items.get("set", items.get("questions"))
    if not isinstance(items, list) or not items: raise JevError("%s holds no labelled question" % path)
    bk = {}
    for k, x in enumerate(items):
        if not isinstance(x, dict): raise JevError("question %d is not an object" % (k + 1))
        what = "question %s" % x.get("id", k + 1)
        p, y = pooled(x, what), to_label(x.get("label"), what)
        i = min(bins - 1, int(math.floor(p * bins)))
        s = bk.setdefault(i, [0, 0.0, 0]); s[0] += 1; s[1] += p; s[2] += y
    n_all, ece = len(items), 0.0
    for i in sorted(bk):
        n, sp, t = bk[i]; mp, fq = sp / n, t / n
        ece += n / n_all * abs(mp - fq)
        print("bucket=%s-%s n=%d mean_p=%s freq=%s" % (fmt(i / bins), fmt((i + 1) / bins), n, fmt(mp), fmt(fq)))
    print("ece=%s" % fmtp(ece))

VERBS = ("ask", "problog", "mln", "opinion", "why", "retract", "verify", "calibrate", "help")
def main(argv, door):
    v, a = argv[0], argv[1:]
    try:
        if v == "ask": v_ask(a, door)
        elif v == "problog": v_problog(a)
        elif v == "mln": v_mln(a)
        elif v == "opinion": v_opinion(a)
        elif v == "why": v_why(a, door)
        elif v == "retract": v_retract(a, door)
        elif v == "verify": v_verify(a, door)
        elif v == "calibrate": v_calibrate(a)
        else: print(USAGE)
    except JevError as e:
        print("jev: %s" % e, file=sys.stderr); return 2
    return 0
