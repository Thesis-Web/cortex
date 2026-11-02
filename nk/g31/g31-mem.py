import socket,json,time,random
def ask(r,t=200):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows")
d0=q("SELECT count(DISTINCT about) FROM main.run WHERE kind = 3")[0][0]; m0=ask("memory"); t0=time.time(); print("first read",time.strftime("%H:%M:%S"),"defined",d0,flush=True)
print("runs by kind and arrival:",flush=True)
lab=dict(q("SELECT gate,symbol FROM main.label WHERE gate < 500"))
rows=q("SELECT kind, arrival, count(*), sum(same_as IS NOT NULL) FROM main.run GROUP BY kind, arrival ORDER BY 3 DESC LIMIT 14")
for k,a,n,s in rows: print("  kind",k,"arrival",a,lab.get(a,"?"),"runs",n,"repeats",s,flush=True)
print("DNA rows, sample of 400 gates by key:",flush=True)
G=q("SELECT count(*) FROM main.label")[0][0]; random.seed(1); tot=once=0; big=[]
for g in random.sample(range(90,G),400):
    r=q(f"SELECT count(*), sum(times = 1) FROM dna WHERE gate = {g}")[0]; tot+=r[0] or 0; once+=r[1] or 0; big.append(r[0] or 0)
big.sort(); print("  rows",tot,"touched only once",once,"share",round(once/max(1,tot),3),"median per gate",big[200],"max",big[-1],flush=True)
top=q("SELECT l.symbol, n.nsh FROM main.label l JOIN (SELECT gate, count(*) AS nsh FROM dna WHERE gate IN (3,7,8,10,11,12,23,24,68) GROUP BY gate) n ON n.gate = l.gate ORDER BY 2 DESC LIMIT 6")
print("  hub gates:",top,flush=True)
time.sleep(200)
d1=q("SELECT count(DISTINCT about) FROM main.run WHERE kind = 3")[0][0]; m1=ask("memory"); dt=time.time()-t0; n=d1-d0
print("second read",time.strftime("%H:%M:%S"),"defined",d1,"added",n,"in",round(dt),"s",flush=True)
a,b=m0[0],m1[0]
for k in ("runs","receipts_kept","seq_held_runs","cells","shards"): print(" ",k,a[k],b[k],"+ a define",round((b[k]-a[k])/n,1),flush=True)
for k in sorted(k for k in a if k.endswith("_MB")): print(" ",k,a[k],b[k],"KB a define",round((b[k]-a[k])*1024/n,2),flush=True)
print("sixth:",{k:round((m1[1][k]-m0[1][k])*1024/n,2) for k in m1[1] if k.endswith("_MB") and k not in("heap_in_use_MB","heap_free_MB","sqlite_MB")},flush=True)
print("DONE",flush=True)
