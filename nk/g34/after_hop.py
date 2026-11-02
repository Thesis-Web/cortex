import json, time, urllib.request, sys
B = "http://localhost:8058"
def post(path, obj):
    req = urllib.request.Request(B + path, data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=1800))
def get(path): return json.load(urllib.request.urlopen(B + path, timeout=1800))
st = get("/api/stats")
print("STATS main", {k: st["main"].get(k) for k in ("shards","shard_rows","runs","hops","defined","refused","pending")})
print("STATS sixth", {k: st["sixth"].get(k) for k in ("shards","shard_rows","hops","pending")})
for line in ("print : who",):
    t = time.time(); r = post("/api/type", {"line": line}); dt = time.time() - t
    print("TYPED", repr(line), {k: r.get(k) for k in ("run","runs","hits","born","seconds","refused","error")}, "wall_s", round(dt, 3))
    for o in (r.get("out") or [])[:6]: print("   out", str(o)[:200])
    run = r.get("run")
    if run:
        d = get(f"/api/run?schema=main&id={run}")
        print("   run keys", list(d.keys()))
        hops = d.get("hops") or []
        print("   receipts", len(hops))
        for h in hops[:14]: print("     ", str(h)[:160])
        print("   cells", str(d.get("cells"))[:600])
