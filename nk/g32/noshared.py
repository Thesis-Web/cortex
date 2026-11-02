import socket,json,time
def ask(r,t=120):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows")
txt=lambda run: q(f"SELECT group_concat(symbol,'') FROM (SELECT l.symbol FROM sixth.seq s JOIN sixth.label l ON l.gate=s.gate WHERE s.run={run} ORDER BY s.pos)")[0][0]
g=q("SELECT gate FROM sixth.label WHERE symbol='seen'")[0][0]; c=q(f"SELECT call FROM sixth.dna WHERE gate={g} AND before=6 AND trigger=68")[0][0]; t=txt(c)
a="UPDATE sixth.spawned SET shared = shared + 1 WHERE gate IN ( SELECT DISTINCT CAST ( j.value AS INTEGER ) FROM main.run_sheet s , json_each ( '[' || replace ( s.value , ' ' , ',' ) || ']' ) j WHERE s.run = what AND s.cell = ( SELECT gate FROM main.label WHERE symbol = 'unknown' ) AND s.value <> '' ) ; "
assert t.count(a)==1; n=t.replace(a,"")
r=ask("type sixth "+n); run=r.get("run"); assert run and txt(run)==n
ask(f"type sixth BUILD UPDATE sixth.dna SET call = {run} WHERE gate = {g} AND before = 6 AND trigger = 68 ; BUILD")
print("hp seen",q(f"SELECT call FROM sixth.dna WHERE gate={g} AND before=6 AND trigger=68"),"was",c)
s0=q("SELECT count(*) FROM sixth.spawned WHERE sent = 1")[0][0]; t0=time.time(); time.sleep(60); s1=q("SELECT count(*) FROM sixth.spawned WHERE sent = 1")[0][0]; st=ask("stats")
print("hp defines a minute",round((s1-s0)/(time.time()-t0)*60),"sent",s1,"refused",st["main"]["refused"],"pending",st["main"]["pending"])
