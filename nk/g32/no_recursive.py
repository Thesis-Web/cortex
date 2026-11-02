import socket,json,re,time
def ask(r,t=120):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows")
txt=lambda run: q(f"SELECT group_concat(symbol,'') FROM (SELECT l.symbol FROM sixth.seq s JOIN sixth.label l ON l.gate=s.gate WHERE s.run={run} ORDER BY s.pos)")[0][0]
g=q("SELECT gate FROM sixth.label WHERE symbol='seen'")[0][0]; c=q(f"SELECT call FROM sixth.dna WHERE gate={g} AND before=6 AND trigger=68")[0][0]; t=txt(c)
a="s.run IN ( WITH RECURSIVE t ( id ) AS ( SELECT what UNION ALL SELECT k.id FROM main.run k JOIN t ON k.parent = t.id ) SELECT id FROM t )"
assert t.count(a)==2; n=t.replace(a,"s.run = what")
pre="s.run IN ( WITH RECURSIVE t ( id ) AS ( SELECT ( SELECT CASE WHEN"; post=" END ) UNION ALL SELECT k.id FROM main.run k JOIN t ON k.parent = t.id ) SELECT id FROM t )"
assert n.count(pre)==2 and n.count(post)==2
n=n.replace(pre,"s.run = ( SELECT CASE WHEN").replace(post," END )")
assert "RECURSIVE" not in n
r=ask("type sixth "+n); run=r.get("run"); print("laid",run,str(r.get("out"))[:160]); assert run and txt(run)==n
r=ask(f"type sixth BUILD UPDATE sixth.dna SET call = {run} WHERE gate = {g} AND before = 6 AND trigger = 68 ; BUILD"); print(str(r.get("out"))[:150])
print("seen shard",q(f"SELECT call FROM sixth.dna WHERE gate={g} AND before=6 AND trigger=68"),"was",c)
