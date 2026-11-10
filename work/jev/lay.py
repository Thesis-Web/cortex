# lay.py (2026-11-10, jev C5): lays judge/judge-jev-<verb>.sql into the judge brain through the kernel door, the cx db of the kernel on CORTEX_PORT (7007 live,
# 7010 test): the ddl statements, then each rule as a row of cx.judge_jevrule with that verb (lay-ask.py with the verb named; the ask first: its trigger fires every verb).
# usage: [CORTEX_PORT=7010] python3 work/jev/lay.py <verb>     or, outside the kernel: python3 work/jev/lay.py <verb> --try <scratch main db> <scratch cx db>
import os, re, sys
sys.path.insert(0, os.path.expanduser("~/cortex"))
verb = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "ask"
f = sys.argv[sys.argv.index("--sql") + 1] if "--sql" in sys.argv else os.path.expanduser("~/cortex/judge/judge-jev-%s.sql" % verb)
parts = re.split(r"^-- ;; ", open(f).read(), flags=re.M)[1:]
def flat(body): return " ".join(l.strip() for l in body.splitlines() if l.strip() and not l.strip().startswith("--"))
def lit(x): return "'" + x.replace("'", "''") + "'"
stmts = []
for p in parts:
    head, body = p.split("\n", 1); body = flat(body)
    if head.startswith("ddl-add"): stmts.append(("ddl-add", body))
    elif head.startswith("ddl"): stmts.append(("ddl", body))
    else:
        m = re.match(r"rule (-?\d+) (.*)", head)
        stmts.append(("rule %s" % m.group(1), "INSERT OR REPLACE INTO cx.judge_jevrule (id, verb, name, sql) VALUES (%d, %s, %s, %s)" % (int(m.group(1)), lit(verb), lit(m.group(2).strip()), lit(body))))
if "--try" in sys.argv:
    import sqlite3
    i = sys.argv.index("--try"); c = sqlite3.connect(sys.argv[i + 1], isolation_level=None); c.execute("ATTACH ? AS cx", (sys.argv[i + 2],))
    def mother(sql, *args):
        try:
            cur = c.cursor(); rows = cur.execute(sql, args).fetchall()
            return "\n".join(" | ".join("" if v is None else str(v) for v in r) for r in rows) or "ok"
        except Exception as e: return "error: %s" % e
    c.create_function("mother", -1, mother)
    run = lambda s: c.execute(s).fetchall()
else:
    import cortex
    run = lambda s: cortex.q(s)
for kind, s in stmts:
    try: run(s); print("%s ok: %s" % (kind, s[:80]))
    except Exception as e:
        if kind == "ddl-add" and "duplicate column" in str(e): print("ddl-add already laid: %s" % s[:80]); continue
        print("%s FAILED: %s :: %s" % (kind, e, s[:120])); sys.exit(1)
print("laid %s: %d statements" % (verb, len(stmts)))
