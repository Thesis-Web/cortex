import socket,json,time,subprocess,sys
def ask(r,t=60):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
last=None; same=0; t0=time.time()
while True:
    if not subprocess.run(["pgrep","-x","nk"],capture_output=True).stdout: print(time.strftime("%H:%M:%S"),"KERNEL GONE"); break
    try:
        st=ask("stats"); sent=ask("q SELECT count(*) FROM sixth.spawned WHERE sent = 1")["rows"][0][0]
    except Exception as e: print(time.strftime("%H:%M:%S"),"no answer",e,flush=True); time.sleep(30); continue
    runs=st["main"]["runs"]; same=same+1 if runs==last else 0; last=runs
    if sent>=1000000: print(time.strftime("%H:%M:%S"),"REACHED",sent,"refused",st["main"]["refused"]); break
    if same>=10: print(time.strftime("%H:%M:%S"),"STALLED at",sent,"runs",runs,"refused",st["main"]["refused"]); break
    if st["main"]["refused"]>25: print(time.strftime("%H:%M:%S"),"REFUSALS",st["main"]["refused"],"at",sent); break
    time.sleep(30)
