#!/usr/bin/env python3
# g37/restep_check.py (2026-11-02): run on hp beside the kernel. Two lines move water, a settle pass moves everything; restep is asked for
# water's place at the clocks between, and compared with the places read live at those moments.
import socket, json, time
def ask(req):
    s = socket.create_connection(("127.0.0.1", 7007), timeout=3600); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask("q " + sql).get("rows")
def place(w): g = q("SELECT gate FROM label WHERE symbol = '%s'" % w)[0][0]; return g, list(q("SELECT round(x,3), round(y,3), round(z,3), moved FROM xyz WHERE gate = %d" % g)[0])
c0 = q("SELECT n FROM clock")[0][0]; g, p0 = place("water"); print("clock", c0, "water", p0)
ask("type main water runs downhill"); c1 = q("SELECT n FROM clock")[0][0]; g, p1 = place("water"); print("after line 1 (clock %d): water" % c1, p1)
ask("type main cold water freezes"); c2 = q("SELECT n FROM clock")[0][0]; g, p2 = place("water"); print("after line 2 (clock %d): water" % c2, p2)
def rs(clock, label, want):
    t0 = time.time(); r = ask("restep %d %d" % (clock, g))
    if "error" in r: print("restep to %s: %s" % (label, r)); return
    pl = r["places"][0]; got = [round(pl["x"], 3), round(pl["y"], 3), round(pl["z"], 3)]
    print("restep to %s (clock %d): %s, want %s, diff %s; moves %d placements %d passes %d, begins %d, %.2f s" % (label, clock, got, want[:3], [round(got[i] - want[i], 4) for i in range(3)], r["moves"], r["placements"], r["passes"], r["history_begins_at"], time.time() - t0))
rs(c0, "before line 1", p0); rs(c1, "after line 1", p1); rs(c2, "after line 2", p2)
st = ask("settle 1"); c3 = q("SELECT n FROM clock")[0][0]; g, p3 = place("water"); print("settle 1:", {k: st[k] for k in ("points", "moved", "seconds")}, "water", p3)
rs(c2, "after line 2, before the pass", p2); rs(c3, "after the pass", p3)
m = ask("moved %d" % c2); print("moved since the clock of line 2:", len(m["moved"]), "points listed (the pass moved them all; the list is capped at 20000)")
b = ask("restep base"); print("restep base:", b); rs(c3, "after the pass, from the new beginning", p3)
