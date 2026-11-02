#!/usr/bin/env python3
# hp-teach1.py: read what the teach lines did, step back once, then the owner's thirteen defines, the sixth's collection, and the brain's first own defines
import socket, json, subprocess, time
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): r = ask("q " + sql); return r.get("rows", r)
def text(schema, run): r = q(f"SELECT group_concat(symbol, '') FROM (SELECT l.symbol FROM {schema}.seq s JOIN {schema}.label l ON l.gate = s.gate WHERE s.run = {run} ORDER BY s.pos)"); return r[0][0] if r and r[0][0] else ''
def typeit(line, show=6):
    schema, t = ('sixth', line[3:]) if line.startswith('6> ') else ('main', line)
    r = ask(f"type {schema} {t}"); print(f"> {line[:70]}  ->  run {r['run']}: {r['runs']} runs, {r['hits']} hits, {r['born']} born, {r['seconds']:.2f} s")
    for o in r['out'][:show]: print("     ", o[0], o[1], o[2] + ':', str(o[3])[:160].replace('\n', ' / '))
    return r
print("== mother's error replies among the teach runs (main runs > 1072), by text")
for (run, n) in q("SELECT min(id), count(*) FROM run WHERE kind = 3 AND arrival = 4 AND id > 1072 AND id IN (SELECT run FROM seq WHERE pos = 1 AND gate = (SELECT gate FROM label WHERE symbol = 'error')) GROUP BY (SELECT group_concat(gate, ' ') FROM (SELECT gate FROM seq WHERE run = run.id ORDER BY pos))"):
    print(f"   x{n}: {text('main', run)[:140]}")
print("== the sixth's error replies among its teach runs (> 228)")
for (run, n) in q("SELECT min(id), count(*) FROM sixth.run WHERE kind = 3 AND arrival = 4 AND id > 228 AND id IN (SELECT run FROM sixth.seq WHERE pos = 1 AND gate = (SELECT gate FROM sixth.label WHERE symbol = 'error')) GROUP BY (SELECT group_concat(gate, ' ') FROM (SELECT gate FROM sixth.seq WHERE run = run.id ORDER BY pos))"):
    print(f"   x{n}: {text('sixth', run)[:140]}")
print("\n== step back from a return of the first define : who (run 196, a source return) and from the define run itself (185)")
typeit("step back : 196"); typeit("step back : 185")
print("\n== the owner's thirteen defines over the full sources")
t0 = time.time(); subprocess.run(["bash", "run-on-hp.sh", "type", "DEFINES-1.txt"], stdout=subprocess.DEVNULL); print(f"   typed in {time.time() - t0:.1f} s")
rows = q("SELECT i.run, (SELECT value FROM run_sheet WHERE run = i.run AND cell = 23), (SELECT value FROM run_sheet WHERE run = i.run AND cell = (SELECT gate FROM label WHERE symbol = 'known')), (SELECT value FROM run_sheet WHERE run = i.run AND cell = (SELECT gate FROM label WHERE symbol = 'unknown')), (SELECT count(*) FROM run r WHERE r.parent = i.run AND r.kind = 3 AND r.arrival IN (7,8,10,11,12,13,14,443)) FROM input i WHERE i.id > (SELECT count(*) FROM input) - 13 ORDER BY i.id")
sym = dict(q("SELECT gate, symbol FROM label"))
for (run, what, known, unknown, returns) in rows:
    k = known.split() if known else []; u = unknown.split() if unknown else []
    print(f"   run {run} define : {sym.get(int(what), what) if what else '?'}: {returns} returns; known {len(k)}; unknown {len(u)}: {' '.join(sym.get(int(g), g) for g in u[:14])}{' …' if len(u) > 14 else ''}")
print("\n== what the sixth collected and asked")
print("   spawned (unknown gates waiting), most shared first:", [(sym.get(g, g), sh) for (g, sh) in q("SELECT gate, shared FROM sixth.spawned WHERE sent = 0 ORDER BY shared DESC, id LIMIT 20")], "| waiting:", q("SELECT count(*) FROM sixth.spawned WHERE sent = 0")[0][0])
print("   asked (why) rows:", q("SELECT count(*) FROM sixth.asked")[0][0], "| why lines in main.third:", q("SELECT count(*) FROM third")[0][0], "| guesses:", q("SELECT word, guess, confidence, belief FROM guess.guesses ORDER BY id DESC LIMIT 5"))
print("\n== the brain defines its three most-shared unknowns")
r = typeit("define unknown : 3", show=8)
new = q(f"SELECT t.run, (SELECT value FROM run_sheet WHERE run = t.run AND cell = 23) FROM third t WHERE t.run > {r['run']} ORDER BY t.id")
for (run, what) in new:
    k = q(f"SELECT value FROM run_sheet WHERE run = {run} AND cell = (SELECT gate FROM label WHERE symbol = 'known')"); u = q(f"SELECT value FROM run_sheet WHERE run = {run} AND cell = (SELECT gate FROM label WHERE symbol = 'unknown')")
    kk = k[0][0].split() if k and k[0][0] else []; uu = u[0][0].split() if u and u[0][0] else []
    print(f"   the sixth's define run {run}: {sym.get(int(what), what) if what else '?'}: known {len(kk)}, unknown {len(uu)}: {' '.join(sym.get(int(g), g) for g in uu[:12])}")
print("\n== scans and the slowest pastes now")
print("  ", ask("scans"))
p = ask("profile 6"); [print(f"   {t['s']:7.3f} s {t['n']:5d} x {t['us']:9.0f} us  {t['text'][:120]}") for t in p['top']]
print("   stats:", {k: v for k, v in ask("stats")['main'].items() if k in ('runs', 'hops', 'gates', 'shards', 'hop_us', 'paste_us')})
