import socket,json,time,re
def ask(r,t=120):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows")
pid=int(open('/proc/self/status').read() and __import__('subprocess').run(["pgrep","-x","nk"],capture_output=True,text=True).stdout.split()[0])
def ram():
    t=open(f"/proc/{pid}/smaps_rollup").read(); return {k:int(re.search(rf"^{k}:\s+(\d+) kB",t,re.M).group(1))//1024 for k in ("Rss","Anonymous","Swap")}
def snap(): return time.time(), ask("stats"), q("SELECT count(*) FROM sixth.spawned WHERE sent = 1")[0][0], {x["text"]:x for x in ask("profile 14")["top"]}
t0,s0,d0,p0=snap(); start=(t0,d0,s0); print(time.strftime("%H:%M:%S"),"sent",d0,"RAM MB",ram(),flush=True)
for w in range(3):
    time.sleep(60)
    t1,s1,d1,p1=snap(); dt=t1-t0
    print(time.strftime("%H:%M:%S"),"sent",d1,"| defines a minute",round((d1-d0)/dt*60),"| refused",s1["main"]["refused"],"pending",s1["main"]["pending"],"hops +",s1["main"]["hops"]-s0["main"]["hops"],"runs +",s1["main"]["runs"]-s0["main"]["runs"],"gates +",s1["main"]["gates"]-s0["main"]["gates"],"DNA rows +",s1["main"]["shards"]-s0["main"]["shards"],"| RAM MB",ram(),flush=True)
    print("  pastes main",round(s1["main"]["paste_s"]-s0["main"]["paste_s"],1),"sixth",round(s1["sixth"]["paste_s"]-s0["sixth"]["paste_s"],1),"hop_s",round(s1["main"]["hop_s"]-s0["main"]["hop_s"],2),"of",round(dt),flush=True)
    rows=sorted(((x["s"]-p0.get(k,{"s":0})["s"],x["n"]-p0.get(k,{"n":0})["n"],k) for k,x in p1.items()),reverse=True)[:5]
    for ds,dn,k in rows: print("   ",round(ds,1),"s n",dn,"ms",round(ds*1000/dn,1) if dn else "-",k[:70],flush=True)
    t0,s0,d0,p0=t1,s1,d1,p1
print("over the window",round((d1-start[1])/(t1-start[0])*60),"defines a minute",flush=True)
print("waiting",q("SELECT count(*) FROM sixth.spawned WHERE sent = 0"),"sent",q("SELECT count(*) FROM sixth.spawned WHERE sent = 1"),flush=True)
print("DONE",flush=True)
