cd ~/nk
python3 - <<'PY'
s=open('nkio.c').read()
a='''  if(REL_Q) for(int g = 1; g <= b->label.n && nrel < CAP; g++){ if(!inc[g]) continue; Neuron *n = neuron_of(b, g); if(!n || !n->nnode) continue; sqlite3_bind_int(REL_Q, 1, g); int cnt = 0; while(sqlite3_step(REL_Q) == SQLITE_ROW && cnt < 40){ int kind = sqlite3_column_int(REL_Q, 0), other = sqlite3_column_int(REL_Q, 1); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%d,%d,0]", g, kind, other); nrel++; cnt++; if(kind > 0 && kind <= b->label.n) inc[kind] = 1; if(other > 0 && other <= b->label.n) inc[other] = 1; } sqlite3_reset(REL_Q); }'''
b='''  { /* the relationship rows of the included points, in one pass over the brain's own rel table (the page asks for the brain whole) */
    static sqlite3_stmt *ALLREL; if(!ALLREL){ char q[64]; snprintf(q, sizeof q, "SELECT gate, kind, other FROM %s.rel", b->name); sqlite3_prepare_v2(DB, q, -1, &ALLREL, 0); }
    if(ALLREL){ while(sqlite3_step(ALLREL) == SQLITE_ROW && nrel < CAP){ int g = sqlite3_column_int(ALLREL, 0); if(g <= 0 || g > b->label.n || !inc[g]) continue; int kind = sqlite3_column_int(ALLREL, 1), other = sqlite3_column_int(ALLREL, 2); if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%d,%d,0]", g, kind, other); nrel++; if(kind > 0 && kind <= b->label.n) inc[kind] = 1; if(other > 0 && other <= b->label.n) inc[other] = 1; } sqlite3_reset(ALLREL); } }'''
assert s.count(a)==1; s=s.replace(a,b); open('nkio.c','w').write(s)
s=open('serve8.py').read()
a="if BUNDLE['d'] is None or time.time() - BUNDLE['at'] > 30:"; b="if BUNDLE['d'] is None or time.time() - BUNDLE['at'] > 600:"
assert s.count(a)==1; open('serve8.py','w').write(s.replace(a,b))
PY
gcc -O2 -Wall -Wno-unused-function -Wno-unused-parameter -Wno-unused-variable -I. -o /tmp/nkb nk.c nkvt.c nkio.c nkmap.c -L/usr/lib/x86_64-linux-gnu -l:libsqlite3.so.0 -lpthread -lm -ldl 2>&1 | grep -E "error" | head -n 5 | cut -c1-200
[ -x /tmp/nkb ] && { rm -f /tmp/nkb; timeout 200 bash run-on-hp.sh up 2>&1 | tail -n 1 | cut -c1-80; }
python3 - <<'PY'
import socket,json,time
def ask(r,t=300):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return b
t=time.time(); b=ask("bundle 400"); d=json.loads(b.decode()); print("bundle",round(time.time()-t,1),"s",len(b)//1000000,"MB rel",len(d["rel"]),"label",len(d["label"]),flush=True)
t=time.time(); b=ask("bundle 400"); print("bundle again",round(time.time()-t,1),"s",flush=True)
PY
