import socket,json,time
def ask(r,t=60):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows",ask("q "+s))
U=q("SELECT gate FROM main.label WHERE symbol='unknown'")[0][0]; K=q("SELECT gate FROM main.label WHERE symbol='known'")[0][0]
n=ask("newest main 12"); L=[x for x in n["lines"] if str(x.get("text","")).startswith("define")][:8]
print(str(n["lines"][0])[:200])
ls=[]
for x in L:
    r=x.get("run"); u=q(f"SELECT value FROM main.run_sheet WHERE run={r} AND cell={U}"); k=q(f"SELECT value FROM main.run_sheet WHERE run={r} AND cell={K}")
    lu=len(str(u[0][0]).split()) if u and u[0][0] else 0; lk=len(str(k[0][0]).split()) if k and k[0][0] else 0; ls.append((x.get("text")[:24],lu,lk))
print(ls)
r=max(L,key=lambda x:0).get("run"); r=L[0]["run"]
def T(name,sql):
    t=time.perf_counter(); o=ask("q "+sql); print(f"{(time.perf_counter()-t)*1000:8.2f} ms  {name}  {str(o.get('rows',o))[:70]}",flush=True)
base=f"FROM main.run_sheet s , json_each ( '[' || replace ( s.value , ' ' , ',' ) || ']' ) j WHERE s.run = {r} AND s.cell = {U} AND s.value <> ''"
T("list length",f"SELECT count(*) {base}")
T("+ node test",f"SELECT count(*) {base} AND NOT EXISTS ( SELECT 1 FROM main.node n WHERE n.gate = CAST ( j.value AS INTEGER ) )")
T("+ symbol read",f"SELECT count(*), sum(( SELECT symbol FROM main.label WHERE gate = CAST ( j.value AS INTEGER ) ) GLOB '[A-Z]*') {base}")
T("+ lower read",f"SELECT count(*), sum(( SELECT gate FROM main.label WHERE symbol = lower ( ( SELECT symbol FROM main.label WHERE gate = CAST ( j.value AS INTEGER ) ) ) ) IS NOT NULL) {base}")
T("next to send","SELECT p.id FROM sixth.spawned p WHERE p.sent = 0 ORDER BY p.shared DESC , p.id LIMIT 1")
T("spawned test",f"SELECT count(*) {base} AND EXISTS ( SELECT 1 FROM sixth.spawned p WHERE p.gate = CAST ( j.value AS INTEGER ) )")
T("asked test",f"SELECT count(*) FROM main.run_sheet s WHERE s.run = {r} AND s.state = 0")
print(q("SELECT name FROM sixth.sqlite_master WHERE type='index'"))
