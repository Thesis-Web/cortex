cd ~/nk; python3 - <<'PY'
s=open("nkio.c").read()
a='''  if(argc == 0 && strchr(sql, ';')){ if(sqlite3_exec(DB, sql, rows_cb, &got, &err) != SQLITE_OK){'''
b='''  if(argc == 0 && strchr(sql, ';')){ if(exec_timed(sql, rows_cb, &got, &err) != SQLITE_OK){'''
assert s.count(a)==1; s=s.replace(a,b)
i=s.index("static char *run_text(") if "static char *run_text(" in s else s.index("char *run_text(")
fn='''static void prof_add(const char *sql0, i64 ns);
/* the statements of a paste one at a time, each timed: what sqlite3_exec does, and the profile sees inside a paste */
static int exec_timed(const char *sql, int (*cb)(void*, int, char**, char**), void *arg, char **err){
  const char *p = sql;
  while(p && *p){ sqlite3_stmt *st = 0; const char *tail = 0; i64 t0 = now_ns();
    if(sqlite3_prepare_v2(DB, p, -1, &st, &tail) != SQLITE_OK){ *err = sqlite3_mprintf("%s", sqlite3_errmsg(DB)); return SQLITE_ERROR; }
    if(!st){ p = tail; continue; }
    int rc, n = sqlite3_column_count(st);
    while((rc = sqlite3_step(st)) == SQLITE_ROW){ char *v[64]; int m = n < 64 ? n : 64; for(int i = 0; i < m; i++) v[i] = (char*)sqlite3_column_text(st, i); cb(arg, m, v, 0); }
    if(rc != SQLITE_DONE){ *err = sqlite3_mprintf("%s", sqlite3_errmsg(DB)); sqlite3_finalize(st); return SQLITE_ERROR; }
    sqlite3_finalize(st); prof_add(p, now_ns() - t0); p = tail; while(p && (*p == ' ' || *p == '\\n')) p++; }
  return SQLITE_OK;
}
'''
s=s[:i]+fn+s[i:]
open("nkio.c","w").write(s)
PY
grep -n "now_ns" nk.h nkio.c | head -n 3 | cut -c1-110
timeout 100 bash run-on-hp.sh up 2>&1 | tail -n 2 | cut -c1-110
python3 - <<'PY'
import socket,json,time
def ask(r,t=60):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
time.sleep(5); p0={x["text"]:x for x in ask("profile 30")["top"]}; s0=ask("q SELECT count(*) FROM sixth.spawned WHERE sent = 1")["rows"][0][0]; t=time.time(); time.sleep(50)
p1={x["text"]:x for x in ask("profile 30")["top"]}; s1=ask("q SELECT count(*) FROM sixth.spawned WHERE sent = 1")["rows"][0][0]; st=ask("stats"); dt=time.time()-t
print("defines a minute",round((s1-s0)/dt*60),"refused",st["main"]["refused"],"pending",st["main"]["pending"])
for ds,dn,k in sorted(((x["s"]-p0.get(k,{"s":0})["s"],x["n"]-p0.get(k,{"n":0})["n"],k) for k,x in p1.items()),reverse=True)[:9]: print(round(ds,1),"s n",dn,"ms",round(ds*1000/dn,1) if dn else "-",k[:96])
PY
