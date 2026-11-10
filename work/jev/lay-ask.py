# lay-ask.py (2026-11-10, jev C4): lays judge/judge-jev-ask.sql into the judge's brain through the kernel's door (the test kernel's cx db):
# the ddl statements, then each rule as a row of cx.judge_jevrule (verb ask). usage: CORTEX_PORT=7010 python3 work/jev/lay-ask.py
#   or, to try it outside the kernel: python3 work/jev/lay-ask.py --try <scratch main db> <scratch cx db>
import os, re, sys
sys.path.insert(0, os.path.expanduser("~/cortex"))
f = os.path.expanduser("~/cortex/judge/judge-jev-ask.sql")
parts = re.split(r"^-- ;; ", open(f).read(), flags=re.M)[1:]
def flat(body): return " ".join(l.strip() for l in body.splitlines() if l.strip() and not l.strip().startswith("--"))
def lit(x): return "'" + x.replace("'", "''") + "'"
stmts = []
for p in parts:
    head, body = p.split("\n", 1); body = flat(body)
    if head.startswith("ddl"): stmts.append(("ddl", body))
    else:
        m = re.match(r"rule (\d+) (.*)", head)
        stmts.append(("rule %s" % m.group(1), "INSERT OR REPLACE INTO cx.judge_jevrule (id, verb, name, sql) VALUES (%d, 'ask', %s, %s)" % (int(m.group(1)), lit(m.group(2).strip()), lit(body))))
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
    except Exception as e: print("%s FAILED: %s :: %s" % (kind, e, s[:120])); sys.exit(1)
print("laid: %d statements" % len(stmts))
