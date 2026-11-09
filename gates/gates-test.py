#!/usr/bin/env python3
# gates-test.py (tries/38, 2026-11-02): types the contract's tests (GATE-0-CONTRACT.md section 4) into the scratch kernel on 7009
# and prints what came back, raw. It decides nothing.
import socket, json, sys, time, os, subprocess, signal
PORT = 7009; KDIR = os.path.expanduser("~/cortex/gates/kernel"); BRAIN = os.path.expanduser("~/cortex/gates/brain")
SOURCES = "wn gcide mwt moby map sqldoc measured guess wikt".split()
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
def gate(sym):
    r = q("SELECT gate FROM main.label WHERE symbol = '%s'" % sym); rows_ = r.get("rows", []); return rows_[0][0] if rows_ else None
def typ(line): return ask("type main " + line)
def say(label, obj):
    t = obj if isinstance(obj, str) else json.dumps(obj); print("%s: %s" % (label, t[:1200]), flush=True)
def short(r):
    if isinstance(r, dict) and "run" in r:
        d = {k: r[k] for k in ("run", "runs", "hits", "hops", "born", "refused", "seconds") if k in r}; d["out"] = [o[2:4] for o in r.get("out", [])][:8]; return d
    return r
def rows(r): return r.get("rows", []) if isinstance(r, dict) else []
print("== gates-test.py %s port %d" % (time.strftime("%F %T"), PORT)); say("stats before", ask("stats"))
print("---- gate 1 (C2)")
r1 = typ("zorble yint quux"); say("1.1 first typing", short(r1)); r2 = typ("zorble yint quux"); say("1.1 second typing", short(r2))
say("1.1 run R2", q("SELECT id, arrival, same_as, again, ended FROM main.run WHERE id = %d" % r2["run"]))
say("1.1 memory of R1", q("SELECT run, again, last_run FROM main.run_memory WHERE run = %d" % r1["run"]))
say("1.1 control run R1", q("SELECT id, same_as FROM main.run WHERE id = %d" % r1["run"]))
say("1.2 water a", q("SELECT gate FROM main.label WHERE symbol = 'water'")); say("1.2 water b", q("SELECT gate FROM main.label WHERE symbol = 'water'")); say("1.2 control nosuchsymbolqq", q("SELECT gate FROM main.label WHERE symbol = 'nosuchsymbolqq'"))
say("1.3 keyless count", q("SELECT count(*) FROM main.label")); say("1.3 control keyed read after", q("SELECT gate FROM main.label WHERE symbol = 'water'"))
say("1.4 no such table", q("SELECT * FROM main.nosuchtable"))
say("1.5 unknown request", ask("frobnicate")); say("1.5 stats answers after", "yes" if "main" in ask("stats") else "no")
r6 = typ("glorpf snarb wibble"); say("1.6 nonsense line", short(r6))
print("---- gate 2 (C3)")
gd, gcolon, gok, gsixth, gheard = gate("define"), gate(":"), gate("ok"), gate("sixth"), gate("heard")
say("2.1 gates", {"define": gd, ":": gcolon, "ok": gok, "sixth": gsixth, "heard": gheard})
say("2.1 dna rows of :", q("SELECT shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = %d" % gcolon))
say("2.1 dna rows of define", q("SELECT shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = %d" % gd))
ok0 = q("SELECT shard, before, trigger, times FROM main.dna WHERE gate = %d" % gok); say("3.3 ok rows before", ok0)
rs = typ("define : stone"); say("2.2 define : stone", short(rs)); R = rs["run"]
say("2.2 receipts of define : stone", q("SELECT pos, gate, shard FROM main.run_receipt WHERE run = %d" % R))
rd = typ("describe : stone"); say("2.2 describe : stone", short(rd))
say("2.2 receipts of describe : stone", q("SELECT pos, gate, shard FROM main.run_receipt WHERE run = %d" % rd["run"]))
rr = typ("define : rock"); say("2.2 control define : rock", short(rr))
say("2.2 receipts of define : rock", q("SELECT pos, gate, shard FROM main.run_receipt WHERE run = %d" % rr["run"]))
say("2.2 dna rows of define after", q("SELECT shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = %d" % gd))
nw = ask("newest main 12"); say("2.2b newest main runs (arrivals)", nw)
rg = typ("define : glorpfx"); say("2.3 define : glorpfx", short(rg)); gg = gate("glorpfx"); say("2.3 gate of glorpfx", gg)
say("2.3 neuron glorpfx", q("SELECT gate, born, arrived, nodes, memories, shards FROM main.neuron WHERE gate = %d" % gg))
say("2.3 node rows glorpfx", q("SELECT id, source, run FROM main.node WHERE gate = %d" % gg))
say("2.3 memory of the run", q("SELECT run, gate, shard, at, again FROM main.run_memory WHERE run = %d" % rg["run"]))
say("2.3 sheet of the run", q("SELECT cell, state, value FROM main.run_sheet WHERE run = %d" % rg["run"]))
gs = gate("stone"); say("2.3 control neuron stone", q("SELECT gate, born, arrived, nodes, memories, shards FROM main.neuron WHERE gate = %d" % gs))
print("---- gate 3 (C4) on R = define : stone")
say("3.1 run R", q("SELECT id, arrival, parent, root, kind, cell, about, ended FROM main.run WHERE id = %d" % R))
sec = q("SELECT id, run, cell, gate, about, made, src FROM main.secondary WHERE run = %d" % R); say("3.1 secondary rows of R", sec)
for row in rows(sec)[:14]:
    made = row[5]; say("3.1 sub-run %s" % made, q("SELECT id, arrival, parent, root, kind, cell, about, ended, srcgate FROM main.run WHERE id = %d" % made))
say("3.2 sheet of R", q("SELECT cell, state, value FROM main.run_sheet WHERE run = %d" % R))
say("3.2 complete R", q("SELECT run FROM main.complete WHERE run = %d" % R))
rv = typ("define : river"); say("3.3 define : river", short(rv))
ok1 = q("SELECT shard, before, trigger, times FROM main.dna WHERE gate = %d" % gok); say("3.3 ok rows after", ok1)
d0 = {tuple(x[:3]): x[3] for x in rows(ok0)}; d1 = {tuple(x[:3]): x[3] for x in rows(ok1)}
say("3.3 ok rows that ticked (shard, before, trigger): delta", {str(k): d1[k] - d0.get(k, 0) for k in d1 if d1[k] != d0.get(k, 0)})
say("3.3 complete river", q("SELECT run FROM main.complete WHERE run = %d" % rv["run"]))
say("3.3 sheet of river", q("SELECT cell, state, value FROM main.run_sheet WHERE run = %d" % rv["run"]))
print("---- 1.7 / 2.4 the write and the disable, in the brain's REBIND form")
drows = rows(q("SELECT shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = %d" % gd))
row = next((x for x in drows if x[1] == 1 and x[2] == gcolon), None); say("2.4 the define row (before 1 = heard, trigger = :)", row)
if row:
    old = row[3]
    rx = typ("BUILD UPDATE dna SET call = 0 WHERE gate = %d AND before = 1 AND trigger = %d ; BUILD" % (gd, gcolon)); say("1.7 disable typed", short(rx))
    say("1.7 read after disable", q("SELECT shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = %d AND before = 1 AND trigger = %d" % (gd, gcolon)))
    say("1.7 control: the other rows of define", q("SELECT shard, before, trigger, call FROM main.dna WHERE gate = %d" % gd))
    rk = typ("define : rock"); say("2.4 define : rock while disabled (rock defined already)", short(rk))
    say("2.4 secondary rows while disabled", q("SELECT id, run, cell, gate FROM main.secondary WHERE run = %d" % rk["run"]))
    rk2 = typ("define : rockfall"); say("2.4 define : rockfall while disabled (a new word)", short(rk2))
    say("2.4 secondary rows rockfall", q("SELECT id, run, cell, gate FROM main.secondary WHERE run = %d" % rk2["run"]))
    gk = gate("rockfall"); say("2.4 neuron rockfall", q("SELECT gate, born, nodes FROM main.neuron WHERE gate = %d" % gk))
    ry = typ("BUILD UPDATE dna SET call = %d WHERE gate = %d AND before = 1 AND trigger = %d ; BUILD" % (old, gd, gcolon)); say("1.7 restore typed", short(ry))
    say("1.7 read after restore", q("SELECT shard, before, trigger, call, spawn, times FROM main.dna WHERE gate = %d AND before = 1 AND trigger = %d" % (gd, gcolon)))
    rw = typ("define : rock"); say("2.4 define : rock after restore", short(rw))
    say("2.4 secondary rows after restore", q("SELECT id, run, cell, gate FROM main.secondary WHERE run = %d" % rw["run"]))
    rw2 = typ("define : riverbed"); say("2.4 define : riverbed after restore (a new word)", short(rw2))
    say("2.4 secondary rows riverbed", q("SELECT id, run, cell, gate FROM main.secondary WHERE run = %d" % rw2["run"]))
    gw = gate("riverbed"); say("2.4 neuron riverbed", q("SELECT gate, born, nodes FROM main.neuron WHERE gate = %d" % gw))
say("stats before restart", ask("stats"))
print("---- 3.4 restart the scratch kernel on its file")
pids = subprocess.run(["pgrep", "-f", r"^\./nk 7009 "], capture_output=True, text=True).stdout.split(); say("3.4 scratch pid", pids)
say("3.4 cortex kernel pid before", subprocess.run(["pgrep", "-f", r"nk 7007 "], capture_output=True, text=True).stdout.split())
for p in pids: os.kill(int(p), signal.SIGTERM)
t0 = time.time()
while subprocess.run(["pgrep", "-f", r"^\./nk 7009 "], capture_output=True, text=True).stdout.strip() and time.time() - t0 < 600: time.sleep(0.5)
say("3.4 stopped after s", round(time.time() - t0, 1)); say("3.4 nk.log tail", open(BRAIN + "/nk.log").read().strip().splitlines()[-2:])
env = dict(os.environ, NK_MAP=BRAIN + "/brain.map"); log = open(BRAIN + "/nk.log", "a")
subprocess.Popen(["./nk", "7009", "egg-symbols.txt", "../sources"] + SOURCES, cwd=KDIR, env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
t0 = time.time()
while time.time() - t0 < 120:
    try: socket.create_connection(("127.0.0.1", PORT), timeout=1).close(); break
    except Exception: time.sleep(0.5)
say("3.4 started after s", round(time.time() - t0, 1)); say("3.4 stats after restart", ask("stats"))
say("3.4 cortex kernel pid after", subprocess.run(["pgrep", "-f", r"nk 7007 "], capture_output=True, text=True).stdout.split())
say("3.4 run R after restart", q("SELECT id, arrival, parent, root, kind, cell, about, ended FROM main.run WHERE id = %d" % R))
say("3.4 sheet of R after restart", q("SELECT cell, state, value FROM main.run_sheet WHERE run = %d" % R))
say("3.4 receipts of R after restart", q("SELECT pos, gate, shard FROM main.run_receipt WHERE run = %d" % R))
say("3.4 secondary of R after restart", q("SELECT id, run, cell, gate, about, made, src FROM main.secondary WHERE run = %d" % R))
say("3.4 run R2 after restart", q("SELECT id, arrival, same_as, again, ended FROM main.run WHERE id = %d" % r2["run"]))
rz = typ("define : stone"); say("3.4 define : stone after restart", short(rz))
say("3.4 secondary rows of that define", q("SELECT id, run, cell, gate FROM main.secondary WHERE run = %d" % rz["run"]))
say("3.4 run of that define", q("SELECT id, arrival, same_as, again, ended FROM main.run WHERE id = %d" % rz["run"]))
say("stats end", ask("stats")); print("== end %s" % time.strftime("%F %T"))
