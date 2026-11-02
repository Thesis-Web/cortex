import socket,json,re,collections
def ask(r,t=60):
    s=socket.create_connection(("127.0.0.1",7007),timeout=t); s.settimeout(t); s.sendall((r+"\n").encode()); b=b""
    while not b.endswith(b"\n"): b+=s.recv(1<<20)
    s.close(); return json.loads(b.decode())
q=lambda s: ask("q "+s).get("rows") or []
Q=lambda w: w.replace("'","''")
top=q("SELECT max(id) FROM sixth.spawned")[0][0]
syms=[]
for lo in range(1,top,top//40):
    syms+=q(f"SELECT l.symbol, p.gate FROM sixth.spawned p JOIN main.label l ON l.gate = p.gate WHERE p.id BETWEEN {lo} AND {lo+120} AND p.sent = 1 AND NOT EXISTS ( SELECT 1 FROM main.node n WHERE n.gate = p.gate )")
print("undefined sampled",len(syms))
print("sources schema", q("SELECT sql FROM wikt.sqlite_master WHERE name='corpus'"), q("SELECT name FROM wikt.sqlite_master WHERE type='index'"))
cat=collections.Counter(); ex=collections.defaultdict(list)
SRC=['wn','gcide','mwt','moby','wikt']
def has(w):
    for s in SRC:
        if q(f"SELECT 1 FROM {s}.corpus WHERE word = '{Q(w)}' LIMIT 1"): return s
    return None
for w,g in syms:
    k=None
    if has(w): k='IN A SOURCE, exact, but no node'
    elif w!=w.lower() and has(w.lower()): k='in a source lowercase'
    else:
        for suf,rep in (('ies','y'),('es',''),('s',''),('ed',''),('ed','e'),('ing',''),('ing','e'),('ly',''),('er',''),('est',''),('ness',''),('al','')):
            if w.lower().endswith(suf) and len(w)>len(suf)+2 and has(w.lower()[:-len(suf)]+rep): k='a form: base is in a source'; break
    if not k:
        if not re.search('[aeiouyAEIOUY]',w) or len(w)<=2: k='fragment: no vowel or under 3 letters'
        elif w[0].isupper(): k='capitalized, in no source'
        else: k='lowercase word, in no source'
    cat[k]+=1
    if len(ex[k])<14: ex[k].append(w)
for k,v in cat.most_common(): print(v,round(100*v/len(syms),1),'%',k,ex[k])
print("counts",{s:q(f"SELECT count(*) FROM {s}.corpus")[0][0] for s in ('wn','moby')})
