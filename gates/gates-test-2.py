#!/usr/bin/env python3
# gates-test-2.py (tries/39, 2026-11-02 22:3x): three checks added AFTER the first run, with their predictions written here before they ran.
# (a) 1.1b a third typing of the same line: predicted same_as = 260052 (the second typing, which ended clean), the second run memory again 2.
# (b) 3.1b the sub-run named by R sheet def cell (260091) read by id: predicted parent 260083, kind 3, cell 24, about 9492 (stone), ended 1; the node rows of stone name return runs whose parent is a define run.
# (c) 3.3b R sheet read again after thousands of the brain own runs: predicted the same 8 cells with the same values (no cell set by another run return).
import socket, json, time
PORT = 7009
def ask(req, timeout=900):
    s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout); s.sendall((req + "\n").encode()); b = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        b += d
        if b.endswith(b"\n"): break
    s.close(); t = b.decode().strip()
    try: return json.loads(t)
    except Exception: return {"raw": t[:500]}
def q(sql): return ask("q " + sql)
def say(label, obj): print("%s: %s" % (label, json.dumps(obj)[:900]), flush=True)
def short(r):
    d = {k: r[k] for k in ("run", "runs", "hits", "hops", "born", "refused", "seconds") if k in r}; d["out"] = [o[2:4] for o in r.get("out", [])][:8]; return d
print("== gates-test-2.py %s" % time.strftime("%F %T")); say("stats", ask("stats")["main"])
r3 = ask("type main zorble yint quux"); say("1.1b third typing", short(r3))
say("1.1b run R3", q("SELECT id, arrival, same_as, again, ended FROM main.run WHERE id = %d" % r3["run"]))
say("1.1b memory of R2 (260052)", q("SELECT run, again, last_run FROM main.run_memory WHERE run = 260052"))
say("1.1b memory of R1 (260026)", q("SELECT run, again, last_run FROM main.run_memory WHERE run = 260026"))
say("3.1b sub-run 260091 (R def cell)", q("SELECT id, arrival, parent, root, kind, cell, about, ended, srcgate, src FROM main.run WHERE id = 260091"))
say("3.1b label of srcgate", q("SELECT gate, symbol FROM main.label WHERE gate = (SELECT srcgate FROM main.run WHERE id = 260091)"))
nodes = q("SELECT id, source, run FROM main.node WHERE gate = 9492"); say("3.1b node rows of stone (count, first 6)", {"count": len(nodes.get("rows", [])), "first": nodes.get("rows", [])[:6]})
for row in nodes.get("rows", [])[:3]:
    say("3.1b return run %s" % row[2], q("SELECT id, arrival, parent, root, kind, cell, about, ended, srcgate FROM main.run WHERE id = %d" % row[2]))
say("3.3b sheet of R (260083) now", q("SELECT cell, state, value FROM main.run_sheet WHERE run = 260083"))
say("3.3b complete R now", q("SELECT run FROM main.complete WHERE run = 260083"))
say("3.3b cell labels", q("SELECT gate, symbol FROM main.label WHERE gate IN (19, 21, 23, 24, 26, 27, 28, 150, 155)"))
say("stats end", ask("stats")["main"]); print("== end %s" % time.strftime("%F %T"))
