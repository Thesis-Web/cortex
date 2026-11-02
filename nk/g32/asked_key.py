import socket,json,time
def ask(r,t=120):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
r=ask("type sixth BUILD CREATE INDEX IF NOT EXISTS sixth.asked_unsent ON asked ( sent ) WHERE sent = 0 ; BUILD"); print("laid",str(r.get("out"))[:120])
print([x[0] for x in ask("q SELECT name FROM sixth.sqlite_master WHERE type='index'")["rows"]])
p0={x["text"]:x for x in ask("profile 30")["top"]}; s0=ask("q SELECT count(*) FROM sixth.spawned WHERE sent = 1")["rows"][0][0]; t=time.time(); time.sleep(50)
p1={x["text"]:x for x in ask("profile 30")["top"]}; s1=ask("q SELECT count(*) FROM sixth.spawned WHERE sent = 1")["rows"][0][0]; st=ask("stats"); dt=time.time()-t
print("defines a minute",round((s1-s0)/dt*60),"sent",s1,"refused",st["main"]["refused"],"pending",st["main"]["pending"])
for ds,dn,k in sorted(((x["s"]-p0.get(k,{"s":0})["s"],x["n"]-p0.get(k,{"n":0})["n"],k) for k,x in p1.items()),reverse=True)[:6]: print(round(ds,1),"s n",dn,"ms",round(ds*1000/dn,1) if dn else "-",k[:90])
