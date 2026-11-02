#!/usr/bin/env python3
# measure-on-hp.py: the kernel's stats, its scan counts and mother's paste profile, as a markdown page (run on hp after the sixty lines)
import socket, json
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007)); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
print("# The kernel measured, 2026-10-30: after the sixty tool lines of LINES-nk.txt on hp (Debian 13, 2 cores)\n")
print("## stats (the kernel's stats request)\n\nhop_us: the time inside one hop of the kernel (a landing, a hit, an end, a replay), mother's pastes left out. paste_us: the mean time of one text pasted to mother (SQLite). hop_s and paste_s: the totals.\n")
print("```"); print(json.dumps(ask("stats"), indent=1)); print("```\n")
print("## reads by key and reads that walked a whole region (the scans request)\n\nA keyed read found its rows by gate, run, (run, cell), (gate, before, trigger), symbol, input or id. A scanned read walked the whole region: that is a formula the owner may want to change at the prompt.\n")
print("```"); [print(r) for r in ask("scans")]; print("```\n")
p = ask("profile 20")
print("## where mother's time went: %d distinct texts pasted, %.3f s in all (the profile request)\n" % (p["texts"], p["total_s"]))
print("```")
for t in p["top"]: print("%7.3f s  %5d x %9.0f us  %s" % (t["s"], t["n"], t["us"], t["text"][:160]))
print("```")
