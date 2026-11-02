import socket,json,time
def ask(r,t=120):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows")
txt=lambda run: q(f"SELECT group_concat(symbol,'') FROM (SELECT l.symbol FROM seq s JOIN label l ON l.gate=s.gate WHERE s.run={run} ORDER BY s.pos)")[0][0]
def sheet(r):
    d=dict(q(f"SELECT (SELECT symbol FROM label WHERE gate=s.cell), s.value FROM run_sheet s WHERE s.run={r}")); return d
g=q("SELECT gate FROM label WHERE symbol='define'")[0][0]; c=q(f"SELECT call FROM dna WHERE gate={g} AND before=1 AND trigger=68")[0][0]; t=txt(c)
r0=ask("type main define : carry"); a=sheet(r0["run"])
i=t.index("BUILD INSERT OR REPLACE INTO run_sheet ( run , cell , state , value ) SELECT above , ( SELECT gate FROM label WHERE symbol = 'known' )")
j=t.rindex(" ; BUILD")
new=t[:i]+"BUILD WITH x ( g , h ) AS MATERIALIZED ( SELECT DISTINCT s.gate , EXISTS ( SELECT 1 FROM node n WHERE n.gate = s.gate AND n.source <> 15 ) FROM run r JOIN seq s ON s.run = r.id JOIN label l ON l.gate = s.gate WHERE r.kind = 3 AND r.arrival IN ( 7 , 8 , 10 , 11 , 12 , 13 , 14 , ( SELECT gate FROM label WHERE symbol = 'wikt' ) ) AND r.parent = above AND l.symbol GLOB '[A-Za-z]*' ORDER BY s.gate ) INSERT OR REPLACE INTO run_sheet ( run , cell , state , value ) SELECT above , k.gate , 1 , coalesce ( ( SELECT group_concat ( x.g , ' ' ) FROM x WHERE x.h = ( k.symbol = 'known' ) ) , '' ) FROM label k WHERE k.symbol IN ( 'known' , 'unknown' )"+t[j:]
r=ask("type main "+new); run=r.get("run"); assert run and txt(run)==new
for b in (1,5): ask(f"type main BUILD UPDATE dna SET call = {run} WHERE gate = {g} AND before = {b} AND trigger = 68 ; BUILD")
print("define shards now",q(f"SELECT before,call FROM dna WHERE gate={g} AND trigger=68 AND before IN (1,5)"),"was",c)
r1=ask("type main define : carry"); b=sheet(r1["run"])
print("old form",r0.get("seconds"),"s; new form",r1.get("seconds"),"s; refused",r1.get("refused"))
for k in ("known","unknown","what","know"):
    print(k,"same" if a.get(k)==b.get(k) else "DIFFERENT",len(str(a.get(k)).split()),len(str(b.get(k)).split()))
print("mother on the new define:",[str(o)[:120] for o in r1.get("out",[]) if 'error' in str(o)][:3])
