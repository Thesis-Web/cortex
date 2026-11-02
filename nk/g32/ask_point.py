import socket,json,sys
def ask(r,t=120):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows")
text_of=lambda run: q(f"SELECT group_concat(symbol,'') FROM (SELECT l.symbol FROM seq s JOIN label l ON l.gate=s.gate WHERE s.run={run} ORDER BY s.pos)")[0][0]
g=q("SELECT gate FROM label WHERE symbol='define'")[0][0]
c=q(f"SELECT call FROM dna WHERE gate={g} AND before=1 AND trigger=68")[0][0]; t=text_of(c)
old="( SELECT 1 FROM run k WHERE k.kind = 3 AND k.about = s.gate AND k.arrival IN ( 7 , 8 , 10 , 11 , 12 , 13 , 14 , ( SELECT gate FROM label WHERE symbol = 'wikt' ) ) )"
new="( SELECT 1 FROM node n WHERE n.gate = s.gate AND n.source <> 15 )"
assert t.count(old)==2, t.count(old)
n=t.replace(old,new); r=ask("type main "+n); run=r.get("run"); assert run
assert text_of(run)==n
for b in (1,5): ask(f"type main BUILD UPDATE dna SET call = {run} WHERE gate = {g} AND before = {b} AND trigger = 68 ; BUILD")
print("define shards",q(f"SELECT before,trigger,call FROM dna WHERE gate={g} AND trigger=68 AND before IN (1,5)"),"was",c)
r=ask("type main define : know"); print("define : know",r.get("seconds"),"s runs",r.get("runs"),"refused",r.get("refused"),[str(o)[:80] for o in r.get("out",[]) if 'kno' in str(o)][:3])
