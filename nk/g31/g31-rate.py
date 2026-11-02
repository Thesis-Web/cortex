import socket,json,time
def ask(r,t=120):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows")
def snap(): return time.time(), ask("stats"), {x["text"]:x for x in ask("profile 14")["top"]}, q("SELECT count(DISTINCT about) FROM main.run WHERE kind = 3")[0][0], q("SELECT count(*) FROM guess.guesses")[0][0]
t0,s0,p0,d0,g0=snap(); first=(t0,d0,s0); print(time.strftime("%H:%M:%S"),"start defined",d0,flush=True)
for w in range(3):
    time.sleep(75)
    t1,s1,p1,d1,g1=snap(); dt=t1-t0
    print(time.strftime("%H:%M:%S"),"defined",d1,"| rate",round((d1-d0)/dt*60),"a minute | guesses added",g1-g0,"| refused",s1["main"]["refused"],"pending",s1["main"]["pending"],"heap",s1.get("heap_MB"),flush=True)
    print("  pastes main",round(s1["main"]["paste_s"]-s0["main"]["paste_s"],1),"sixth",round(s1["sixth"]["paste_s"]-s0["sixth"]["paste_s"],1),"hops",round(s1["main"]["hop_s"]-s0["main"]["hop_s"],2),"of",round(dt),"s; gates +",s1["main"]["gates"]-s0["main"]["gates"],"runs +",s1["main"]["runs"]-s0["main"]["runs"],flush=True)
    rows=sorted(((x["s"]-p0.get(k,{"s":0})["s"],x["n"]-p0.get(k,{"n":0})["n"],k) for k,x in p1.items()),reverse=True)[:4]
    for ds,dn,k in rows: print("   ",round(ds,1),"s n",dn,"ms",round(ds*1000/dn,1) if dn else "-",k[:58],flush=True)
    t0,s0,p0,d0,g0=t1,s1,p1,d1,g1
print("over the window",round((d1-first[1])/(t1-first[0])*60),"a minute; heap KB a define",round((s1["heap_MB"]-first[2]["heap_MB"])*1024/max(1,d1-first[1]),1),flush=True)
print("waiting",q("SELECT sent,count(*) FROM sixth.spawned GROUP BY sent"),flush=True)
print("DONE",flush=True)
