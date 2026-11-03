#!/usr/bin/env python3
# cortex.py (2026-11-02): the Cortex front door on hp2. One file, stdlib only. The brain (nk on 127.0.0.1:7007) stores; jev judges; this code
# decides by the truth table in CORTEX-HANDLER.md section 7; a worker (claude -p / codex exec) works one turn on the hydration and nothing else.
# Every Cortex record is one line typed at the brain's main prompt (a run, a clock, a memory row, a dedupe tick); main.cx is the keyed index of
# those lines (one row per kind/name/n, replaced in place), because the kernel refuses a read without a key. No log table, no timer, no sweep.
import socket, json, sys, os, re, time, hashlib, subprocess, shutil, urllib.request, urllib.error, math, difflib
PORT = int(os.environ.get("CORTEX_PORT", "7007"))
HOME = os.path.expanduser("~")
KEYFILE = os.path.join(HOME, ".config", "cortex", "typesafe.key")
JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = os.environ.get("CORTEX_JEV_MODEL", "jev-latest")
WORKDIR = os.path.join(HOME, "cortex", "work")
HANDLER = os.path.join(HOME, "cortex", "CORTEX-HANDLER.md")
THRESH = 0.7

# ---- the brain's socket ----
def ask(req):
    s = socket.create_connection(("127.0.0.1", PORT), timeout=600); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def q(sql, *params):
    # the kernel's q takes no parameters: values are quoted here (integers as is, text with '' doubling)
    def lit(v):
        if v is None: return "NULL"
        if isinstance(v, (int, float)): return str(v)
        return "'" + str(v).replace("'", "''") + "'"
    for p in params: sql = sql.replace("?", lit(p), 1)
    r = ask("q " + sql)
    if "error" in r and r.get("error"): raise RuntimeError("brain: " + r["error"] + " :: " + sql[:200])
    return r.get("rows", [])
def typed(text, prompt="main"):
    r = ask("type %s %s" % (prompt, text))
    if "error" in r: raise RuntimeError("brain refused: " + r["error"])
    return r

# ---- the keyed index beside the brain ----
def ensure_cx():
    q("CREATE TABLE IF NOT EXISTS main.cx (kind TEXT NOT NULL, name TEXT NOT NULL, n INTEGER NOT NULL, run INTEGER, at INTEGER, ts INTEGER, value TEXT, PRIMARY KEY (kind, name, n))")
def cx_put(kind, name, n, run, at, value):
    q("INSERT OR REPLACE INTO main.cx (kind, name, n, run, at, ts, value) VALUES (?, ?, ?, ?, ?, ?, ?)", kind, name, n, run, at, int(time.time()), value)
def cx_get(kind, name, n):
    rows = q("SELECT run, at, ts, value FROM main.cx WHERE kind = ? AND name = ? AND n = ?", kind, name, n)
    return rows[0] if rows else None
def cx_list(kind, name, desc=False, limit=1000):
    return q("SELECT n, run, at, ts, value FROM main.cx WHERE kind = ? AND name = ? ORDER BY n %s LIMIT %d" % ("DESC" if desc else "ASC", limit), kind, name)
def clock():
    return q("SELECT n FROM main.clock")[0][0]

# ---- lines into the brain ----
def clean(text):
    # lowercase (BUILD is the brain's build mark; a lowercase line never opens a span), one space, no control characters
    t = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    t = "".join(c if c >= " " else " " for c in t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t
def sentences(text):
    # a fenced block is live output and belongs to the sentence that introduced it: its lines are joined onto that sentence (the owner: the
    # observation is the sentence's evidence, not a sentence of its own); a block with nothing before it stands alone
    text = re.sub(r"```[a-zA-Z0-9_-]*\n?(.*?)```", lambda m: "\n\x01" + " ; ".join(l.strip() for l in m.group(1).splitlines() if l.strip()) + "\n", text, flags=re.S)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    merged = []
    for p in parts:
        if p.startswith("\x01"):
            body = p[1:].strip()
            if merged and body: merged[-1] = merged[-1].rstrip(":").rstrip() + ": " + body
            elif body: merged.append(body)
        else: merged.append(p)
    out = []
    for p in merged:
        p = clean(p)
        if len(p) < 3: continue
        while len(p) > 700:
            cut = p.rfind(" ", 0, 700); cut = cut if cut > 100 else 700
            out.append(p[:cut]); p = p[cut:].strip()
        if p: out.append(p)
    return out
# ---- the ingest filter (handler C10): a context whole, checked line by line; dupes, restatements and noise are dropped before anything is typed ----
STOP = set("the a an of to in on at for and or but if then than so as is are was were be been being am do does did has have had it its this that these those with by from into over under about not no yes i you he she we they me my our your their his her them us will would can could should may might must very just also only there here".split())
def content_words(s):
    return set(w for w in re.findall(r"[a-z][a-z0-9']{2,}", s.lower()) if w not in STOP)
NOISE_START = ("$ ", "> ", "❯", "#!", "{", "}", "[", "]", "|", "<", "```", "diff --git", "index ", "+++", "---", "traceback", "file \"")
def is_noise(s):
    # why a line is not a sentence of the state: a command, a path, code, data, or too few words; None when it is a sentence
    t = s.strip()
    if any(t.startswith(p) for p in NOISE_START): return "command-or-markup"
    if "://" in t: return "url"
    toks = t.split(); filey = [x for x in toks if "/" in x or re.match(r"^[\w.-]+\.(txt|py|sh|md|db|json|log|html|c|h|so|map|jsonl|service)$", x)]
    if toks and (toks[0] in filey or len(filey) >= 2): return "path"
    if re.search(r"\b(jq|curl|ssh|grep|sed|awk|python3|bash|git|sudo|systemctl|cortex)\s+-", t) or t.endswith(("{", "}", ";", "\\")): return "code"
    nonspace = [c for c in t if not c.isspace()]
    if not nonspace: return "empty"
    letters = sum(c.isalpha() for c in nonspace)
    if letters / len(nonspace) < 0.6: return "symbols"
    if len(content_words(t)) < 2: return "too-few-words"
    return None
def wordset_key(s):
    return int(hashlib.sha256(" ".join(sorted(content_words(s))).encode()).hexdigest()[:15], 16)
def filter_lines(name, sents):
    # each sentence gets one fate: keep, dupe (exact repeat), restated (same words, or its words inside an earlier sentence of this batch), noise
    out, seen_sets, seen_keys, counts = [], [], set(), {"keep": 0, "dupe": 0, "restated": 0, "noise": 0}
    for s in sents:
        why = is_noise(s)
        if why: counts["noise"] += 1; out.append((s, "noise", why)); continue
        k = text_key(s)
        if k in seen_keys: counts["dupe"] += 1; out.append((s, "dupe", "batch")); continue
        if cx_get("ingest", name, k): counts["dupe"] += 1; out.append((s, "dupe", "")); continue
        seen_keys.add(k)
        cw = content_words(s); wk = wordset_key(s)
        if cx_get("restate", name, wk) or (len(cw) >= 3 and any(cw <= e for e in seen_sets)): counts["restated"] += 1; out.append((s, "restated", "")); continue
        seen_sets.append(cw); counts["keep"] += 1; out.append((s, "keep", ""))
    return out, counts
def record(kind, name, n, body):
    # one Cortex line typed at the main prompt; its run and the brain's clock go into the index
    line = "cortex %s %s%s : %s" % (kind, name, (" %d" % n) if n is not None else "", body)
    r = typed(line)
    run = r["run"]; at = clock()
    cx_put(kind, name, n if n is not None else run, run, at, body)
    return run, at, r
def run_row(run):
    rows = q("SELECT id, same_as, again, ended, at, arrival FROM main.run WHERE id = ?", run)
    return rows[0] if rows else None

# ---- geometry: the ingest's placed words against the scope's placed words ----
def gates_of(run):
    return [g for (g,) in q("SELECT gate FROM main.seq WHERE run = ? ORDER BY pos", run)]
def xyz_of(gates):
    pts = []
    for g in sorted(set(gates)):
        if g <= 90: continue   # the egg's own symbols are not the project's words
        rows = q("SELECT x, y, z FROM main.xyz WHERE gate = ?", g)
        if rows and any(abs(v) > 1e-9 for v in rows[0]): pts.append(rows[0])
    return pts
def centroid(pts):
    if not pts: return None
    n = len(pts); return tuple(sum(p[i] for p in pts) / n for i in range(3))
def geometry(scope_run, ingest_run):
    sg, ig = gates_of(scope_run), gates_of(ingest_run)
    sp, ip = xyz_of(sg), xyz_of(ig)
    sc, ic = centroid(sp), centroid(ip)
    out = {"scope_words": len(set(g for g in sg if g > 90)), "scope_placed": len(sp), "ingest_words": len(set(g for g in ig if g > 90)), "ingest_placed": len(ip)}
    if sc and ic:
        import math
        d = tuple(ic[i] - sc[i] for i in range(3)); mag = math.sqrt(sum(v * v for v in d))
        ns, ni = math.sqrt(sum(v * v for v in sc)), math.sqrt(sum(v * v for v in ic))
        cosang = (sum(sc[i] * ic[i] for i in range(3)) / (ns * ni)) if ns > 1e-9 and ni > 1e-9 else 1.0
        out["magnitude"] = round(mag, 3); out["radians"] = round(math.acos(max(-1.0, min(1.0, cosang))), 4)
    shared = set(g for g in sg if g > 90) & set(g for g in ig if g > 90)
    out["shared_words"] = len(shared)
    return out

# ---- jev ----
GATEWAY_KEYFILE = os.path.join(HOME, ".config", "cortex", "gateway.key")   # a Vercel AI Gateway key: Jev through the gateway's TypeSafe-compatible endpoint
GATEWAY_URL = "https://ai-gateway.vercel.sh/typesafe/v1/systemone"; GATEWAY_MODEL = "typesafe-ai/jev"
def _readkey(path):
    try:
        k = open(path).read().strip(); return k or None
    except OSError: return None
def jev_route():
    # which door to jev: the owner's TypeSafe key (direct) or a Vercel AI Gateway key (same request, other base URL); None when neither exists
    k = _readkey(KEYFILE)
    if k: return {"url": JEV_URL, "model": JEV_MODEL, "key": k, "via": "typesafe"}
    k = _readkey(GATEWAY_KEYFILE)
    if k: return {"url": GATEWAY_URL, "model": GATEWAY_MODEL, "key": k, "via": "vercel-gateway"}
    return None
def jev_key(): return jev_route() is not None
def jev(state, questions):
    r = jev_route()
    if not r: return None
    body = json.dumps({"model": r["model"], "state": state, "questions": questions}).encode()
    req = urllib.request.Request(r["url"], data=body, headers={"Authorization": "Bearer " + r["key"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp: return json.loads(resp.read().decode())
JUDGE_QUESTIONS = {
    "completes":   {"type": "noul", "instructions": "`ingest` reports that `expected` was observed as live output", "criteria": {"true": "the ingest states the expected output happened and shows or names what was observed", "false": "the ingest describes work, intent or a plan, or the expected output is not reported as observed"}},
    "progresses":  {"type": "noul", "instructions": "`ingest` brings `checkpoint` closer to `expected` than `accepted_state` does", "criteria": {"false": "the ingest adds nothing toward the expected output beyond the accepted state"}},
    "regresses":   {"type": "noul", "instructions": "`ingest` is further from `expected` than `accepted_state`", "criteria": {"false": "the ingest is at least as close to the expected output as the accepted state"}},
    "supersedes":  {"type": "noul", "instructions": "`ingest` states a newer fact about the same thing `accepted_state` describes", "criteria": {"false": "the ingest is about something else, or repeats the accepted state"}},
    "off_scope":   {"type": "noul", "instructions": "`ingest` is about something outside `scope`", "criteria": {"false": "the ingest is about the project described by the scope"}},
    "invents":     {"type": "noul", "instructions": "`ingest` names a result, thing or term that neither `scope`, `checkpoint`, `expected` nor `accepted_state` mention, and does not present it as an observed output", "criteria": {"false": "every thing the ingest names is in the scope or state, or is presented as something observed"}},
    "contradicts": {"type": "noul", "instructions": "`ingest` contradicts `accepted_state` without naming an observation", "criteria": {"false": "the ingest agrees with the accepted state, or names an observation for the difference"}},
}

# ---- the graph cells (the guessing brain's first job, deterministic): the expected output covered by the ingest's words and their relationship rows ----
OBS = re.compile(r"\d|`|\"|\b(printed|prints|returned|returns|output|shows|showed|ran|run|answered|exit|listed|lists)\b")
def gate_of(word):
    rows = q("SELECT gate FROM main.label WHERE symbol = ?", word); return rows[0][0] if rows else 0
def related(word):
    # the gates a word reaches in the brain by key: its relationship rows and the words of its own definition (the kernel's defwords table)
    g = gate_of(word)
    if not g: return set()
    out = set(o for (o,) in q("SELECT other FROM main.rel WHERE gate = ?", g)) | {g}
    try: out |= set(w for (w,) in q("SELECT word FROM main.defwords WHERE gate = ?", g))
    except RuntimeError: pass
    return out
def coverage(target_words, ingest_words):
    # the share of the target's content words present in the ingest, or related to an ingest word by a row the brain holds (keyed reads only)
    if not target_words: return 0.0, 0
    ing = set()
    for w in ingest_words: ing |= related(w)
    covered = by_rel = 0
    for t in target_words:
        if t in ingest_words: covered += 1
        elif gate_of(t) in ing: covered += 1; by_rel += 1
    return round(covered / len(target_words), 3), by_rel
# ---- the shape (the owner, 2026-11-03): an ingest is a run; its gates in order are its shape; the project rides in the shape; a number is its digit
#      gates; prior state against new ingest is two shapes compared, keyed by run; what is out of line is the judge's question ----
_SHAPE, _SYM, _COLON = {}, {}, []
def shape_of(run):
    if run not in _SHAPE: _SHAPE[run] = [g for (g,) in q("SELECT gate FROM main.seq WHERE run = ? ORDER BY pos", run)]
    return _SHAPE[run]
def sym_of(g):
    if g not in _SYM:
        rows = q("SELECT symbol FROM main.label WHERE gate = ?", g); _SYM[g] = rows[0][0] if rows else ""
    return _SYM[g]
def content_gates(run):
    # the gates after the line's prefix (cortex <kind> <name> [n] :) that carry content, in order: words not in STOP, and digits (value gates)
    if not _COLON: _COLON.append(gate_of(":"))
    gs = shape_of(run); i = gs.index(_COLON[0]) + 1 if _COLON[0] in gs else 0
    out = []
    for g in gs[i:]:
        s = sym_of(g)
        if s and (s.isdigit() or (len(s) >= 2 and s not in STOP and any(c.isalpha() for c in s))): out.append(g)
    return out
def is_value(g): return sym_of(g).isdigit()
def seq_diff(a, b):
    # the gates out of line between two shapes: replaced, inserted or deleted in the alignment of the two gate lists
    oa, ob = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal": oa += a[i1:i2]; ob += b[j1:j2]
    return oa, ob
TIME_WORDS = set("again now then later today tonight yesterday am pm".split())
def shape_cells(name, n, run, pr, ck, ex, parts):
    ing = content_gates(run)
    cells = {"shape_gates": len(ing), "shape_values": sum(1 for g in ing if is_value(g)), "shape_expected": 0.0, "shape_shared_project": 0, "values_out": 0, "words_out": [], "echo": False, "new_to_project": [], "supersedes_run": 0, "same_as": 0}
    if not ing: return cells
    rr = run_row(run); cells["same_as"] = (rr[1] or 0) if rr else 0
    words = set(g for g in ing if not is_value(g))
    proj = set()
    for row in (pr, ck, ex):
        if row: proj |= set(g for g in content_gates(row[0]) if not is_value(g))
    cells["shape_shared_project"] = len(words & proj)
    if ex:
        E = content_gates(ex[0]); Es = set(E)
        if Es:
            cells["shape_expected"] = round(len(set(ing) & Es) / len(Es), 3)
            _, out = seq_diff(E, ing)
            cells["values_out"] = sum(1 for g in out if is_value(g))
            cells["words_out"] = sorted(set(sym_of(g) for g in out if not is_value(g)))
            cells["echo"] = (not out) and cells["shape_expected"] >= 0.9
    new = []
    for g in words:
        k = cx_get("gate", name, g)
        if not k or int(json.loads(k[3]).get("first", run)) >= run: new.append(sym_of(g))
    cells["new_to_project"] = sorted(new)
    for p in parts:
        if not p.get("run") or p["run"] >= run: continue          # a shape supersedes only an older part
        P = content_gates(p["run"])
        if not P: continue
        oa, ob = seq_diff(P, ing); diff = oa + ob
        if diff and any(is_value(g) for g in diff) and all(is_value(g) or sym_of(g) in TIME_WORDS for g in diff): cells["supersedes_run"] = p["run"]; break
    return cells
def key_gates(name, run):
    # the (project, gate) key: the first run of this project that crossed the gate and how many times since (the owner: the project's metadata on the gate)
    for g in set(content_gates(run)):
        had = cx_get("gate", name, g)
        if had:
            d = json.loads(had[3]); d["times"] = d.get("times", 1) + 1; d["last"] = run; cx_put("gate", name, g, had[0], had[1], json.dumps(d))
        else: cx_put("gate", name, g, run, clock(), json.dumps({"first": run, "times": 1, "last": run}))
CLAUDE_BIN = shutil.which("claude") or (os.path.expanduser("~/.local/bin/claude") if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else None)
JUDGE_MODEL = os.environ.get("CORTEX_JUDGE_MODEL", "haiku")
JUDGE_PROMPT = """You are a judge. Below is a STATE (json) and numbered SENTENCES. For every sentence give, for each of these seven statements, the probability from 0 to 1 that the statement is true of that sentence read against the state:
completes: the sentence reports that `expected` was observed as live output (not a plan, not intent).
progresses: the sentence brings `checkpoint` closer to `expected` than `accepted_state` does.
regresses: the sentence is further from `expected` than `accepted_state`.
supersedes: the sentence states a newer fact about the same thing `accepted_state` describes.
off_scope: the sentence is about something outside `scope`.
invents: the sentence names a result, thing or term that scope, checkpoint, expected and accepted_state never mention, and does not present it as observed.
contradicts: the sentence contradicts `accepted_state` without naming an observation.
Answer with one JSON object only, no prose: {"<number>": {"completes": p, "progresses": p, "regresses": p, "supersedes": p, "off_scope": p, "invents": p, "contradicts": p}, ...}
STATE:
%s
SENTENCES:
%s
"""
def claude_judge(state, items):
    # the subscription model as the judge (already paid): one call for a whole batch, a JSON of probabilities back; a failure is an error, never a verdict
    if not CLAUDE_BIN: raise RuntimeError("no claude on this machine")
    prompt = JUDGE_PROMPT % (json.dumps(state), "\n".join("%d: %s" % (r, t) for r, t in items))
    p = subprocess.run([CLAUDE_BIN, "-p", "--model", JUDGE_MODEL, "--output-format", "text"], input=prompt, capture_output=True, text=True, timeout=600)
    m = re.search(r"\{.*\}", p.stdout, flags=re.S)
    if p.returncode != 0 or not m: raise RuntimeError("claude judge gave no JSON (rc %d): %s" % (p.returncode, (p.stderr or p.stdout)[-300:]))
    d = json.loads(m.group(0)); out = {}
    for r, t in items:
        a = d.get(str(r), {}); out[r] = {k: round(float(a.get(k, 0.0)), 3) for k in JUDGE_QUESTIONS}
    return out
HOLDS_PROMPT = """You are a judge. Below is the STATE of a project (json): its scope, the sentences accepted as its state so far (accepted_parts_of_the_project), and the last verdicts. Answer one question: what is the probability, from 0 to 1, that this STATEMENT is true given only that state?
STATEMENT: %s
Answer with one JSON object only, no prose: {"holds": p}
STATE:
%s
"""
def claude_holds(state, statement):
    if not CLAUDE_BIN: raise RuntimeError("no claude on this machine")
    p = subprocess.run([CLAUDE_BIN, "-p", "--model", JUDGE_MODEL, "--output-format", "text"], input=HOLDS_PROMPT % (statement, json.dumps(state)), capture_output=True, text=True, timeout=600)
    m = re.search(r"\{.*\}", p.stdout, flags=re.S)
    if p.returncode != 0 or not m: raise RuntimeError("claude holds gave no JSON (rc %d): %s" % (p.returncode, (p.stderr or p.stdout)[-300:]))
    return round(float(json.loads(m.group(0)).get("holds", 0.0)), 3)
def judge_route():
    # the judge for what the sheet leaves unsettled: jev when a key exists, else the subscription model, else none
    f = os.environ.get("CORTEX_JUDGE")
    if f in ("none", "graph"): return None
    if f != "claude" and jev_route(): return "jev"
    if CLAUDE_BIN: return "claude"
    return None
def judge_batch(state, items):
    # items: [(run, text)]; returns {run: answers}, the judge's name
    r = judge_route()
    if r == "jev":
        out = {}; model = JEV_MODEL
        for run, t in items:
            resp = jev(dict(state, ingest=t), JUDGE_QUESTIONS); out[run] = {k: round(v.get("noul", 0.0), 3) for k, v in resp["answers"].items()}; model = resp.get("model", JEV_MODEL)
        return out, "jev:" + model
    if r == "claude": return claude_judge(state, items), "claude:%s (subscription)" % JUDGE_MODEL
    return {}, None
# ---- our own judge (the owner, 11-03): not a language model; a few learned weights over the sheet's cells answering the seven questions as probabilities;
#      the marks are the labeled set (the owner is the checker); training is build time, an answer is a dot product ----
FEATS = ("words", "shared_scope", "shared_checkpoint", "shared_expected", "new_words", "known_words", "coverage_expected", "observed", "mark_met", "times", "shape_gates", "shape_expected", "shape_shared_project", "values_out", "n_words_out", "n_new", "echo")
LOGS = set(("words", "shared_scope", "shared_checkpoint", "shared_expected", "new_words", "known_words", "times", "shape_gates", "shape_shared_project", "values_out", "n_words_out", "n_new"))
LABEL_Q = {"completes": "completes", "progresses": "progresses", "regresses": "regresses", "supersedes": "supersedes", "drift": "off_scope", "invention": "invents", "hallucination": "contradicts"}
MARKS = set(LABEL_Q) | {"dupe", "noise", "unsettled"}
def feats(cells):
    c = dict(cells); c["mark_met"] = 1.0 if cells.get("expected_mark") == "met" else 0.0; c["n_words_out"] = len(cells.get("words_out", [])); c["n_new"] = len(cells.get("new_to_project", []))
    x = [1.0]
    for f in FEATS:
        v = float(c.get(f, 0) or 0); x.append(math.log1p(v) if f in LOGS else v)
    return x
def sigmoid(z): return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
def weights():
    row = cx_get("weights", "judge", 0); return json.loads(row[3]) if row else None
def learned_answers(cells, W=None):
    W = W or weights()
    if not W: return None
    x = feats(cells); return {k: round(sigmoid(sum(a * b for a, b in zip(W["w"].get(k, []), x))), 3) for k in JUDGE_QUESTIONS}
def train_logistic(X, Y, iters=300, lr=0.5, l2=0.01):
    d = len(X[0]); w = [0.0] * d; n = float(len(X))
    for _ in range(iters):
        g = [0.0] * d
        for x, y in zip(X, Y):
            e = sigmoid(sum(a * b for a, b in zip(w, x))) - y
            for j in range(d): g[j] += e * x[j]
        for j in range(d): w[j] -= lr * (g[j] / n + l2 * w[j])
    return w
def decide(a):
    # the truth table (handler section 7), in code
    if a.get("completes", 0) >= THRESH: return "completes"
    if a.get("off_scope", 0) >= THRESH: return "drift"
    if a.get("invents", 0) >= THRESH: return "invention"
    if a.get("contradicts", 0) >= THRESH: return "hallucination"
    if a.get("supersedes", 0) >= THRESH: return "supersedes"
    if a.get("progresses", 0) >= THRESH: return "progresses"
    if a.get("regresses", 0) >= THRESH: return "regresses"
    return "unsettled"

# ---- the verbs ----
def v_project(name, scope):
    ensure_cx(); run, at, r = record("project", name, 0, clean(scope)); key_gates(name, run)
    print("project %s run %d clock %d born %d" % (name, run, at, r["born"]))
def v_checkpoint(name, n, text, expected=None, kind=None):
    ensure_cx(); run, at, r = record("checkpoint", name, n, clean(text)); key_gates(name, run); print("checkpoint %s %d run %d clock %d" % (name, n, run, at))
    if expected: run2, at2, _ = record("expected", name, n, clean(expected)); key_gates(name, run2); print("expected %s %d run %d" % (name, n, run2))
    if kind: record("kind", name, n, kind); print("kind %s %d %s" % (name, n, kind))
    if not cx_get("state", name, n): v_state(name, n, "open")
def v_state(name, n, state):
    ensure_cx(); assert state in ("open", "working", "done"), state
    run, at, _ = record("state", name, n, state); print("state %s %d %s run %d clock %d" % (name, n, state, run, at))
def text_key(s):
    # the index key of an ingest: the first 60 bits of the sentence's sha256; a repeat finds its first run here and is a tick, never a second line
    return int(hashlib.sha256(s.encode()).hexdigest()[:15], 16)
def ingest_text(value):
    # an ingest's index value is JSON {"t": sentence, "times": n}; an older plain value is the sentence itself
    try:
        d = json.loads(value); return d.get("t", ""), int(d.get("times", 1))
    except (ValueError, TypeError, AttributeError): return value, 1
def v_ingest(name, text, quiet=False, repeat_to_kernel=True):
    ensure_cx(); out = []; t0 = time.time()
    fates, counts = filter_lines(name, sentences(text))
    for s, fate, why in fates:
        k = text_key(s)
        if fate == "noise":
            if not quiet: print("dropped (%s): %s" % (why, s[:80]))
            continue
        if fate == "dupe":
            had = cx_get("ingest", name, k)
            if not had:
                if not quiet: print("dropped (repeated in this batch): %s" % s[:80])
                continue
            t, times = ingest_text(had[3]); times += 1
            kr = typed("cortex ingest %s : %s" % (name, s)) if repeat_to_kernel else None   # the kernel ticks its own counter: same_as the first run, no second memory row (the owner, 11-03)
            cx_put("ingest", name, k, had[0], had[1], json.dumps({"t": t, "times": times}))
            out.append({"run": had[0], "clock": had[1], "born": 0, "seconds": 0.0, "same_as": had[0], "again": times, "text": s})
            if not quiet: print("ingest run %d again %d (a repeat%s): %s" % (had[0], times, (", kernel run %d same_as %s" % (kr["run"], (run_row(kr["run"]) or [0, 0])[1])) if kr else "; nothing typed", s[:100]))
            continue
        if fate == "restated":
            had = cx_get("restate", name, wordset_key(s))
            if had:
                first = cx_get("ingest", name, int(had[3]))
                if first:
                    t, times = ingest_text(first[3]); cx_put("ingest", name, int(had[3]), first[0], first[1], json.dumps({"t": t, "times": times + 1}))
            if not quiet: print("dropped (restated%s): %s" % ((" run %d" % had[0]) if had else " in this batch", s[:80]))
            continue
        line = "cortex ingest %s : %s" % (name, s); r = typed(line); run = r["run"]; at = clock()
        cx_put("ingest", name, k, run, at, json.dumps({"t": s, "times": 1})); cx_put("restate", name, wordset_key(s), run, at, str(k)); key_gates(name, run)
        out.append({"run": run, "clock": at, "born": r["born"], "seconds": r["seconds"], "same_as": 0, "again": 1, "text": s})
        if not quiet: print("ingest run %d clock %d born %d %.3fs: %s" % (run, at, r["born"], r["seconds"], s[:100]))
    print("filter: %d sentences, kept %d, dupe %d, restated %d, noise %d, %.0f ms" % (len(fates), counts["keep"], counts["dupe"], counts["restated"], counts["noise"], (time.time() - t0) * 1000))
    return out
# ---- part-wise state (handler C12): a checkpoint's accepted state is the set of sentences accepted into it over time ----
def add_part(name, n, run, text, p=None, by=None):
    k = text_key(text); had = cx_get("part", name, k)
    if had:
        d = json.loads(had[3])
        if d.get("rejected_by") == "owner": return "refused (rejected by the owner)"
        d["times"] = d.get("times", 1) + 1; d.pop("rejected_by", None)   # accepted again: back in the state (a superseded part stays superseded)
        cx_put("part", name, k, had[0], had[1], json.dumps(d)); return "tick %d" % d["times"]
    cx_put("part", name, k, run, clock(), json.dumps({"t": text, "n": n, "run": run, "times": 1, "p": p, "by": by, "ts": int(time.time())})); return "added"
def retire_part(name, n, old_run, new_run, why):
    # a part leaves the accepted state: superseded_by a newer value, or rejected_by a re-judgment; the row stays as history
    for (ts, v) in q("SELECT ts, value FROM main.cx WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 200", name):
        d = json.loads(v)
        if d.get("run") == old_run and d.get("n") == n and (new_run == "owner" or not d.get(why)):
            d[why] = new_run; cx_put("part", name, text_key(d["t"]), d["run"], clock(), json.dumps(d)); return True
    return False
def parts_of(name, n, limit=5, history=False):
    out = []
    for (ts, v) in q("SELECT ts, value FROM main.cx WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 200", name):
        d = json.loads(v)
        if d.get("n") != n: continue
        if not history and (d.get("superseded_by") or d.get("rejected_by")): continue
        d.setdefault("ts", ts); out.append(d)
    return out[:limit]
def accepted_state(name, n):
    ps = parts_of(name, n)
    return " | ".join(p["t"] for p in reversed(ps)) if ps else "(nothing accepted yet)"
# ---- the judge as a run data sheet (handler C11): deterministic cells first, judgment cells when a judge exists, then the formula ----
def sheet_cells(name, n, run, text, pr, ck, ex):
    cw = content_words(text)
    cells = {"words": len(cw), "shared_scope": len(cw & content_words(pr[3])), "shared_checkpoint": len(cw & content_words(ck[3])), "shared_expected": len(cw & content_words(ex[3])) if ex else 0,
             "expected_mark": "met" if re.search(r"expected: ?met", text) else ("not met" if re.search(r"expected: ?not met", text) else "none"),
             "noise": is_noise(text) or "", "geometry": geometry(pr[0], run)}
    hist = {}
    for (v,) in q("SELECT value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 20", name):
        k = json.loads(v).get("kind"); hist[k] = hist.get(k, 0) + 1
    cells["history"] = hist
    had = cx_get("ingest", name, text_key(text)); cells["times"] = ingest_text(had[3])[1] if had else 1
    # the diff cell (the owner: "classifies what is duped information, new information"): the ingest's words against the accepted state's words
    known = set()
    parts = parts_of(name, n, 1000)
    for p in parts: known |= content_words(p["t"])
    base = content_words(pr[3]) | content_words(ck[3]) | (content_words(ex[3]) if ex else set())
    cells["new_words"] = len(cw - known - base); cells["known_words"] = len(cw & (known | base))
    cov, by_rel = coverage(content_words(ex[3]) if ex else set(), cw); cells["coverage_expected"] = cov; cells["by_relation"] = by_rel
    cells["observed"] = bool(OBS.search(text))
    cells.update(shape_cells(name, n, run, pr, ck, ex, parts))
    return cells
def formula(cells, answers):
    # the substitution formulas over a full sheet, in order: what the shape settles, then the deterministic word cells, then the judgment cells
    if cells["noise"]: return "noise", "sheet"
    if cells.get("same_as"): return "dupe", "shape"                                   # the kernel's own repeat of an earlier run
    if cells.get("echo"): return "dupe", "shape"                                      # the expected sentence's own shape with nothing out of line: words, no observation
    if cells.get("supersedes_run"): return "supersedes", "shape"                      # the same shape as an accepted part, only value or time gates out of line
    if cells.get("shape_gates", 0) >= 4 and cells["shape_shared_project"] == 0: return "drift", "shape"   # no word gate shared with the scope, checkpoint or expected
    if cells["words"] >= 4 and cells["shared_scope"] == 0 and cells["shared_checkpoint"] == 0 and cells["shared_expected"] == 0 and not cells["observed"]: return "drift", "sheet"
    if cells.get("shape_gates") and cells["shape_expected"] >= 0.7 and cells["values_out"] >= 1 and len(cells["new_to_project"]) <= 1: return "completes", "shape"   # the expected's shape plus a value out of line
    if cells["words"] >= 4 and cells["new_words"] == 0 and cells["known_words"] >= 3 and not cells["observed"]: return "dupe", "sheet"   # a restatement with nothing new and nothing observed
    if answers: return decide(answers), "judgment"
    return "unsettled", "sheet"
def v_judge(name, n, run, text=None, answers_given=None, judge_name=None):
    ensure_cx()
    pr = cx_get("project", name, 0); ck = cx_get("checkpoint", name, n); ex = cx_get("expected", name, n)
    if not pr or not ck: raise SystemExit("no such project/checkpoint: %s %s" % (name, n))
    if text is None:
        rows = q("SELECT value FROM main.cx WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", name, run)
        if not rows: raise SystemExit("ingest run %s is not in the index" % run)
        text = ingest_text(rows[0][0])[0]
    t0 = time.time(); cells = sheet_cells(name, n, run, text, pr, ck, ex)
    state = {"project": name, "scope": pr[3], "checkpoint": ck[3], "expected": ex[3] if ex else "(none)", "accepted_state": accepted_state(name, n), "ingest": text}
    answers, model = {}, None
    kind, by = formula(cells, {})
    if kind == "unsettled":
        if answers_given is not None: answers, model = answers_given, judge_name
        else:
            la = learned_answers(cells); lv = (weights() or {}).get("v", 0)
            if la is not None and decide(la) != "unsettled": answers, model = la, "learned v%d" % lv
            elif judge_route():
                try: got, model = judge_batch(state, [(run, text)]); answers = got.get(run, {})
                except (urllib.error.URLError, urllib.error.HTTPError, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
                    raise SystemExit("judge call failed, no verdict written: %s" % e)
            elif la is not None: answers, model = la, "learned v%d (abstained)" % lv
    if answers: kind, by = formula(cells, answers)
    judge = model if (by == "judgment" and model) else by
    if answers and by == "judgment": p = answers.get(kind, 0.0) if kind in answers else max(answers.values())
    elif by == "shape": p = cells["shape_expected"] if kind == "completes" else 1.0
    else: p = 1.0 if kind in ("noise", "drift", "dupe") else 0.0
    body = "%s %.3f %s" % (kind, p, judge)
    vrun, at, _ = record("verdict", name, run, body)
    accepting = kind in ("completes", "progresses", "supersedes")
    part = add_part(name, n, run, text, p, judge) if accepting else ("rejected" if retire_part(name, n, run, vrun, "rejected_by") else "")
    if kind == "supersedes" and cells.get("supersedes_run") and retire_part(name, n, cells["supersedes_run"], run, "superseded_by"): part += " | retired the part of run %d" % cells["supersedes_run"]
    moved = ""
    if kind == "completes" and p >= THRESH and by != "shape": moved = " | a judgment cell's completes does not move the state: the shape or the owner's accept does"
    if kind == "completes" and p >= THRESH and by == "shape":
        st = cx_get("state", name, n)
        if not st or st[3] != "done":
            v_state(name, n, "done"); n2 = next_checkpoint(name)
            if n2 is not None and n2 != n:
                s2 = cx_get("state", name, n2)
                if not s2 or s2[3] != "working": v_state(name, n2, "working")
            moved = " | C%d done by this verdict; next C%s" % (n, n2)
    cx_put("verdict", name, run, vrun, at, json.dumps({"n": n, "run": run, "kind": kind, "p": p, "judge": judge, "answers": answers, "sheet": cells, "part": part, "text": text[:300]}))
    geo = cells["geometry"]
    print("verdict %s %d run %d: %s %.3f by %s in %.0f ms | shape gates %d expected %.2f shared project %d values out %d words out %s new to project %s supersedes %s same_as %s echo %s | words %d shared scope %d checkpoint %d expected %d new %d known %d coverage %.2f observed %s mark %s times %d | geometry mag %s rad %s%s" % (name, n, run, kind, p, judge, (time.time() - t0) * 1000, cells["shape_gates"], cells["shape_expected"], cells["shape_shared_project"], cells["values_out"], ",".join(cells["words_out"]) or "-", ",".join(cells["new_to_project"]) or "-", cells["supersedes_run"] or "-", cells["same_as"] or "-", cells["echo"], cells["words"], cells["shared_scope"], cells["shared_checkpoint"], cells["shared_expected"], cells["new_words"], cells["known_words"], cells["coverage_expected"], cells["observed"], cells["expected_mark"], cells["times"], geo.get("magnitude"), geo.get("radians"), (" | part " + part) if part else ""))
    if moved: print(" " + moved.strip(" |"))
    if answers: print("  answers " + " ".join("%s=%.2f" % kv for kv in sorted(answers.items())))
    elif kind == "unsettled": print("  judgment cells empty: no weights learned yet (cortex learn) and no model judge")
    return kind
def judge_many(name, n, items):
    # the sheet and the shape for every sentence first; the learned weights for what they leave; one model call for the batch still unsettled; then every verdict written
    pr = cx_get("project", name, 0); ck = cx_get("checkpoint", name, n); ex = cx_get("expected", name, n)
    if not pr or not ck or not items: return []
    state = {"project": name, "scope": pr[3], "checkpoint": ck[3], "expected": ex[3] if ex else "(none)", "accepted_state": accepted_state(name, n)}
    W = weights(); given, pending = {}, []
    for i in items:
        cells = sheet_cells(name, n, i["run"], i["text"], pr, ck, ex)
        if formula(cells, {})[0] != "unsettled": continue
        la = learned_answers(cells, W)
        if la is not None and decide(la) != "unsettled": given[i["run"]] = (la, "learned v%d" % W.get("v", 0))
        else: pending.append((i["run"], i["text"]))
    got, model = {}, None
    if pending and judge_route():
        try: got, model = judge_batch(state, pending)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
            raise SystemExit("judge call failed, no verdict written: %s" % e)
    out = []
    for i in items:
        r = i["run"]
        if r in given: out.append(v_judge(name, n, r, i["text"], given[r][0], given[r][1]))
        elif r in got: out.append(v_judge(name, n, r, i["text"], got[r], model))
        else: out.append(v_judge(name, n, r, i["text"]))
    return out
def next_checkpoint(name):
    cps = cx_list("checkpoint", name)
    for (n, run, at, ts, text) in cps:
        st = cx_get("state", name, n)
        if st and st[3] == "working": return n
    for (n, run, at, ts, text) in cps:
        st = cx_get("state", name, n)
        if not st or st[3] == "open": return n
    return None
def hydration_text(name, pr, nxt):
    lines = []
    lines.append("PROJECT %s: %s" % (name, pr[3]))
    if nxt is not None:
        ck = cx_get("checkpoint", name, nxt); ex = cx_get("expected", name, nxt)
        lines.append("DO NOW, C%d: %s" % (nxt, ck[3]))
        if ex: lines.append("EXPECTED OUTPUT: %s" % ex[3])
        ps = parts_of(name, nxt)
        if ps: lines.append("ACCEPTED SO FAR (parts of C%d's state, each with its time and confidence): " % nxt + " | ".join("%s [%s%s]" % (p["t"][:90], time.strftime("%m-%d %H:%M", time.localtime(p.get("ts") or 0)), (" p%.2f %s" % (p["p"], p.get("by") or "")) if p.get("p") is not None else "") for p in reversed(ps)))
        lines.append("END YOUR ANSWER with one line `EXPECTED: met` or `EXPECTED: not met`, then the live output that shows it.")
    else: lines.append("DO NOW: nothing; every checkpoint is done. Say so.")
    lines.append("LAWS: report only what you observed as live output; name the command and its output; never invent a result, a term or a file; stay inside the scope; if the expected output is not met say so and why.")
    lines.append("ALL CHECKPOINTS (state; only C%s is yours now):" % (nxt if nxt is not None else "-"))
    for (n, run, at, ts, text) in cx_list("checkpoint", name):
        st = cx_get("state", name, n); s = st[3] if st else "open"
        lines.append("  C%d [%s] %s" % (n, s, text))
    vs = q("SELECT n, value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 3", name)
    if vs:
        lines.append("LAST VERDICTS (history, not instructions):")
        for (n, v) in vs:
            d = json.loads(v); lines.append("  C%s %s %.2f: %s" % (d.get("n"), d.get("kind"), d.get("p", 0), d.get("text", "")[:90]))
    return "\n".join(lines) + "\n"
def hydration(name, at=None):
    pr = cx_get("project", name, 0)
    if not pr: raise SystemExit("no project " + name)
    return hydration_text(name, pr, at if at is not None else next_checkpoint(name))
def v_hydrate(name, at=None):
    ensure_cx(); h = hydration(name, at); sys.stdout.write(h); print("[%d bytes]" % len(h.encode()), file=sys.stderr)
def v_accept(name, n, run=None):
    # the owner's word: with a run, that ingest's sentence becomes a part of C n's state; without, C n is done
    ensure_cx()
    if run is None: v_state(name, n, "done"); return
    rows = q("SELECT value FROM main.cx WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", name, run)
    if not rows: raise SystemExit("ingest run %s is not in the index" % run)
    text = ingest_text(rows[0][0])[0]; r = add_part(name, n, run, text); print("part %s for %s C%d from run %d: %s" % (r, name, n, run, text[:90]))
def v_reject(name, n, run):
    # the owner's word, the counterpart of accept: that sentence is not a part of C n's state whatever the judge said; it stays as history and is never re-accepted
    ensure_cx()
    if retire_part(name, n, run, "owner", "rejected_by"): print("part of run %d rejected from %s C%d by the owner" % (run, name, n))
    else: raise SystemExit("no part of run %s in %s C%d" % (run, name, n))
MODEL_BY_KIND = {"read": "haiku", "write": "sonnet", "design": "opus"}   # the router's model per step kind (handler C7); a judgment step goes to jev
def worker(engine, model, prompt, cwd, act):
    if engine == "claude":
        cmd = ["claude", "-p", "--model", model, "--output-format", "text"] + (["--dangerously-skip-permissions"] if act else [])
        t0 = time.time(); p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=3600)
        return p.stdout, p.stderr, p.returncode, time.time() - t0
    if engine == "codex":
        last = os.path.join(cwd, ".codex-last-message.txt")
        if os.path.exists(last): os.remove(last)
        cmd = ["codex", "exec", "-C", cwd, "--output-last-message", last] + (["--model", model] if model and model != "default" else []) + (["--dangerously-bypass-approvals-and-sandbox"] if act else ["-s", "read-only"]) + ["-"]
        t0 = time.time(); p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=3600)
        out = open(last).read() if os.path.exists(last) else p.stdout
        return out, p.stderr, p.returncode, time.time() - t0
    raise SystemExit("engine must be claude or codex")
def judgment_step(name, n, ck):
    # the router: a judgment step is one jev question over the project's state; no model turn. The answer is ingested and judged like any output.
    pr = cx_get("project", name, 0); ex = cx_get("expected", name, n)
    part_texts = [json.loads(v).get("t", "") for (v,) in q("SELECT value FROM main.cx WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 200", name)]
    state = {"project": name, "scope": pr[3], "checkpoint": ck[3], "expected": ex[3] if ex else "(none)", "accepted_state": accepted_state(name, n), "accepted_parts_of_the_project": part_texts[:20], "last_verdicts": [json.loads(v).get("text", "")[:200] for (_, v) in q("SELECT n, value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 3", name)]}
    allparts = set()
    for t in part_texts: allparts |= content_words(t)
    cov, by_rel = coverage(content_words(ck[3]), allparts)
    if cov >= 0.7: return "judgment by graph: the statement holds with probability %.2f (%d words by relationship), no model asked. EXPECTED: met" % (cov, by_rel), cov
    r = judge_route()
    if r == "jev":
        resp = jev(state, {"holds": {"type": "noul", "instructions": "`checkpoint` is true of the state described by `scope`, `accepted_state` and `last_verdicts`", "criteria": {"false": "the state does not show the checkpoint's statement to be true"}}})
        p = resp["answers"]["holds"]["noul"]; who = "jev:" + resp.get("model", JEV_MODEL)
    elif r == "claude":
        p = claude_holds(state, ck[3]); who = "claude:%s (subscription)" % JUDGE_MODEL
    else: raise SystemExit("judgment step: the graph covered %.2f and no judge is set" % cov)
    return "judgment by %s: the statement holds with probability %.2f. EXPECTED: %s" % (who, p, "met" if p >= THRESH else "not met"), p
def v_turn(name, engine="claude", model=None, act=False, at=None):
    ensure_cx(); nxt = at if at is not None else next_checkpoint(name)
    if nxt is None: print("nothing to do: every checkpoint of %s is done" % name); return
    if not cx_get("checkpoint", name, nxt): raise SystemExit("no checkpoint %s %d" % (name, nxt))
    st = cx_get("state", name, nxt)
    if not st or st[3] != "working": v_state(name, nxt, "working")
    kind = cx_get("kind", name, nxt); kind = kind[3] if kind else "write"
    if model is None: model = MODEL_BY_KIND.get(kind, "sonnet") if engine == "claude" else "default"
    h = hydration(name, nxt); cwd = os.path.join(WORKDIR, name); os.makedirs(cwd, exist_ok=True)
    if kind == "judgment":
        print("turn %s C%d: a judgment step, routed to the judge (no worker)" % (name, nxt))
        out, p = judgment_step(name, nxt, cx_get("checkpoint", name, nxt)); err, rc, secs = "", 0, 0.0
        print("the judge answered: %s" % out)
        run_ = v_ingest(name, out, quiet=True)
        if p >= THRESH:
            r0 = run_[0]["run"] if run_ else 0; add_part(name, nxt, r0, out[:300], p, "judgment")
            if out.startswith("judgment by graph"):
                v_state(name, nxt, "done"); n2 = next_checkpoint(name)
                if n2 is not None: v_state(name, n2, "working")
                print("C%d done by the judgment (%.2f); next C%s" % (nxt, p, n2))
            else: print("C%d holds %.2f by a model; the state waits for the owner's accept" % (nxt, p))
        else: print("C%d stays working: the judgment was %.2f" % (nxt, p))
        return
    else:
        print("turn %s C%d [%s]: %s %s, prompt %d bytes (the hydration, nothing else)" % (name, nxt, kind, engine, model, len(h.encode())))
        out, err, rc, secs = worker(engine, model, h, cwd, act)
    print("worker rc %d in %.1fs, output %d bytes" % (rc, secs, len(out.encode())))
    if rc != 0 or not out.strip(): print("worker stderr: " + err[-800:]); raise SystemExit("worker failed, nothing ingested")
    ing = v_ingest(name, out, quiet=True); kinds = judge_many(name, nxt, [i for i in ing if not i["same_as"]])
    print("ingested %d sentences (%d repeats), verdicts: %s" % (len(ing), sum(1 for i in ing if i["same_as"]), " ".join(kinds) or "none"))
    st_now = cx_get("state", name, nxt)
    if st_now and st_now[3] == "done": print("C%d done by its verdict; next C%s" % (nxt, next_checkpoint(name)))
    elif "completes" in kinds: print("C%d has a completes from a judgment cell, not from the shape: the state waits for the shape or the owner's accept" % nxt)
    elif kinds and all(k in ("drift", "invention", "hallucination") for k in kinds): print("C%d stays working: the output was off rail (%s); the next hydration carries these verdicts" % (nxt, ",".join(sorted(set(kinds)))))
    else: print("C%d stays working" % nxt)
    print("--- worker output (first 1200 bytes) ---"); print(out[:1200])
def project_for_cwd(cwd):
    # which project a hub session's turn belongs to, by its working folder; a folder of no project is not captured
    if not cwd: return None
    if "/neuron" in cwd.lower(): return "neuron"
    if cwd.rstrip("/") == "/home/exnulla": return "cortex"
    return None
def v_capture(cwd=None, name=None):
    # the hub's Stop hook pipes the tail of a transcript here: the last assistant text is ingested and, when jev has a key, judged
    # every assistant text in the tail, in order (the final message lands after the Stop hook runs, so it is caught at the next Stop; repeats tick)
    raw = sys.stdin.read(); texts_all = []
    for line in raw.splitlines():
        try: d = json.loads(line)
        except ValueError: continue
        if d.get("type") != "assistant": continue
        c = d.get("message", {}).get("content")
        texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"] if isinstance(c, list) else ([c] if isinstance(c, str) else [])
        t = "\n".join(x for x in texts if x and x.strip())
        if t.strip(): texts_all.append(t)
    if not texts_all: print("capture: no assistant text in the tail"); return
    name = name or project_for_cwd(cwd)
    if not name: print("capture: cwd %s belongs to no cortex project; nothing ingested" % cwd); return
    ensure_cx(); last = "\n".join(texts_all); ing = v_ingest(name, last, quiet=True, repeat_to_kernel=False); new = [i for i in ing if not i["same_as"]]
    print("capture %s: %d texts, %d sentences, %d new, %d repeats, %d bytes" % (name, len(texts_all), len(ing), len(new), len(ing) - len(new), len(last.encode())))
    nxt = next_checkpoint(name)
    if nxt is None: return
    try:
        kinds = judge_many(name, nxt, new[-20:]); print("judged against C%d: %s" % (nxt, " ".join(kinds)))
    except SystemExit as e: print("not judged: %s" % e)
# ---- the owner's input output formula (2026-11-02): before/after + progression = diff output + before and after states + progression
#      = expected completed output contract: satisfied parts and the remainder not satisfied. A snapshot per report; the next report diffs it. ----
def snapshot(name):
    vs = {}
    for (v,) in q("SELECT value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n", name):
        d = json.loads(v); vs.setdefault(d.get("n"), {}); vs[d.get("n")][d.get("kind")] = vs[d.get("n")].get(d.get("kind"), 0) + 1
    cps = {}
    for (n, run, at, ts, text) in cx_list("checkpoint", name):
        st = cx_get("state", name, n); ex = cx_get("expected", name, n)
        cps[str(n)] = {"state": st[3] if st else "open", "parts": len(parts_of(name, n, 1000)), "verdicts": vs.get(n, {}), "text": text, "expected": ex[3] if ex else ""}
    ing = q("SELECT count(*) FROM main.cx WHERE kind = 'ingest' AND name = ? AND n > 0", name)[0][0]
    return {"clock": clock(), "ts": int(time.time()), "checkpoints": cps, "ingests": ing, "verdicts": sum(sum(x.values()) for x in vs.values())}
def v_formula(name):
    ensure_cx(); now = snapshot(name)
    prev_rows = q("SELECT value FROM main.cx WHERE kind = 'formula' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 1", name)
    prev = json.loads(prev_rows[0][0]) if prev_rows else None
    cps = now["checkpoints"]; N = len(cps); done = [n for n, c in cps.items() if c["state"] == "done"]
    print("INPUT OUTPUT FORMULA %s: before/after + progression = diff output + before and after states + progression = expected completed output contract" % name)
    if prev:
        pd = [n for n, c in prev["checkpoints"].items() if c["state"] == "done"]
        print("BEFORE (clock %d, %s): %d checkpoints, %d done, %d ingests, %d verdicts, %d parts" % (prev["clock"], time.strftime("%Y-%m-%d %H:%M", time.localtime(prev["ts"])), len(prev["checkpoints"]), len(pd), prev["ingests"], prev["verdicts"], sum(c["parts"] for c in prev["checkpoints"].values())))
    else: print("BEFORE: (first formula for %s; this report is the before of the next one)" % name)
    print("AFTER  (clock %d, %s): %d checkpoints, %d done, %d ingests, %d verdicts, %d parts" % (now["clock"], time.strftime("%Y-%m-%d %H:%M", time.localtime(now["ts"])), N, len(done), now["ingests"], now["verdicts"], sum(c["parts"] for c in cps.values())))
    if prev:
        moves = []
        for n, c in cps.items():
            p = prev["checkpoints"].get(n)
            if not p: moves.append("C%s new [%s]" % (n, c["state"])); continue
            if p["state"] != c["state"]: moves.append("C%s %s->%s" % (n, p["state"], c["state"]))
            if c["parts"] != p["parts"]: moves.append("C%s parts %d->%d" % (n, p["parts"], c["parts"]))
            dv = sum(c["verdicts"].values()) - sum(p["verdicts"].values())
            if dv: moves.append("C%s verdicts +%d" % (n, dv))
        print("PROGRESSION (diff): ingests %+d, verdicts %+d, done %+d; %s" % (now["ingests"] - prev["ingests"], now["verdicts"] - prev["verdicts"], len(done) - len(pd), "; ".join(moves) if moves else "no checkpoint moved"))
    print("CONTRACT, SATISFIED (%d of %d):" % (len(done), N))
    for n in done:
        ps = parts_of(name, int(n), 1)
        print("  C%s done: %s | part: %s" % (n, cps[n]["expected"][:100] or cps[n]["text"][:100], ps[0]["t"][:110] if ps else "(no part recorded)"))
    rem = [n for n in cps if n not in done]
    print("CONTRACT, REMAINDER (%d of %d):" % (len(rem), N))
    for n in rem:
        c = cps[n]; miss = []
        if c["parts"] == 0: miss.append("no accepted part")
        if not c["verdicts"].get("completes"): miss.append("no completes verdict")
        print("  C%s [%s] expected: %s | missing: %s" % (n, c["state"], c["expected"][:110] or "(none)", ", ".join(miss)))
    cx_put("formula", name, now["clock"], 0, now["clock"], json.dumps(now))
def v_mark(name, run, kind, why=""):
    # the labeled set: the owner's (or the known-truth) word on what a judged sentence was; cortex learn trains the weights on these
    ensure_cx()
    if kind not in MARKS: raise SystemExit("a mark is one of: " + " ".join(sorted(MARKS)))
    v = cx_get("verdict", name, run)
    if not v: raise SystemExit("no verdict for run %s in %s; judge it first so the mark knows its checkpoint" % (run, name))
    n = json.loads(v[3]).get("n"); cx_put("mark", name, run, run, clock(), json.dumps({"kind": kind, "n": n, "why": why, "ts": int(time.time())}))
    print("mark %s run %d C%s: %s" % (name, run, n, kind))
def key_project(nm):
    # the (project, gate) key for every line of the project not keyed yet, in run order (build time, once per line)
    had = cx_get("keyed", nm, 0); upto = int(json.loads(had[3]).get("upto", 0)) if had else 0
    runs = set()
    for kind in ("project", "checkpoint", "expected", "ingest"):
        for (n, run, at, ts, value) in cx_list(kind, nm, limit=5000):
            if run and run > upto: runs.add(run)
    for run in sorted(runs): key_gates(nm, run)
    if runs: cx_put("keyed", nm, 0, max(runs), clock(), json.dumps({"upto": max(runs), "runs": len(runs), "ts": int(time.time())}))
    return len(runs)
def v_learn(names=None, key_only=False):
    ensure_cx(); t0 = time.time()
    names = names or sorted(set(r[0] for r in q("SELECT name FROM main.cx WHERE kind = 'project' AND name >= '' AND n = 0")))
    for nm in names: print("key %s: %d lines keyed in %.1f s" % (nm, key_project(nm), time.time() - t0))
    if key_only: return
    rows = []
    for nm in names:
        pr = cx_get("project", nm, 0)
        for (n, run, at, ts, value) in cx_list("mark", nm, limit=5000):
            d = json.loads(value); ck = cx_get("checkpoint", nm, d["n"]); ex = cx_get("expected", nm, d["n"])
            ing = q("SELECT value FROM main.cx WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", nm, run)
            if not ing or not ck or not pr: continue
            rows.append((feats(sheet_cells(nm, d["n"], run, ingest_text(ing[0][0])[0], pr, ck, ex)), d["kind"], nm, run))
    if len(rows) < 6: print("learn: %d marks; at least 6 are needed" % len(rows)); return
    def fit(train): return {k: train_logistic([r[0] for r in train], [1.0 if LABEL_Q.get(r[1]) == k else 0.0 for r in train]) for k in JUDGE_QUESTIONS}
    hits, wrong = 0, []
    for i in range(len(rows)):
        W = {"w": fit(rows[:i] + rows[i + 1:])}; got = decide(learned_answers_x(rows[i][0], W)); want = rows[i][1] if rows[i][1] in LABEL_Q else "unsettled"
        if got == want: hits += 1
        else: wrong.append("%s run %d: marked %s, learned %s" % (rows[i][2], rows[i][3], rows[i][1], got))
    v = (weights() or {}).get("v", 0) + 1
    rec = {"v": v, "w": fit(rows), "feats": list(FEATS), "rows": len(rows), "loo": round(hits / len(rows), 3), "ts": int(time.time())}
    cx_put("weights", "judge", 0, 0, clock(), json.dumps(rec)); cx_put("weights", "judge", v, 0, clock(), json.dumps(rec))
    print("learn: weights v%d from %d marks; leave-one-out verdict accuracy %.2f (%d of %d) in %.1f s" % (v, len(rows), hits / len(rows), hits, len(rows), time.time() - t0))
    for w in wrong: print("   missed: " + w)
def learned_answers_x(x, W): return {k: round(sigmoid(sum(a * b for a, b in zip(W["w"].get(k, []), x))), 3) for k in JUDGE_QUESTIONS}
def v_status(name=None):
    ensure_cx(); st = ask("stats")["main"]
    r = judge_route()
    print("brain: gates %d runs %d hops %d refused %d clock %d | judge: shape, learned v%s, then %s | index rows %d" % (st["gates"], st["runs"], st["hops"], st["refused"], clock(), (weights() or {}).get("v", 0), ("jev via " + jev_route()["via"]) if r == "jev" else ("claude:%s (subscription)" % JUDGE_MODEL if r == "claude" else "none"), q("SELECT count(*) FROM main.cx WHERE kind = 'checkpoint' AND name = ? AND n >= 0", name or "")[0][0] if name else -1))
    fr = cx_get("freeze", "handler", 0)
    if fr:
        try: now = hashlib.sha256(open(HANDLER, "rb").read()).hexdigest()
        except OSError: now = "(file missing)"
        print("freeze: brain %s file %s %s" % (fr[3][:16], now[:16], "EQUAL" if now == fr[3] else "DIFFERENT"))
    names = [name] if name else sorted(set(r[0] for r in q("SELECT name FROM main.cx WHERE kind = 'project' AND name >= '' AND n = 0")))
    for nm in names:
        pr = cx_get("project", nm, 0)
        if not pr: print("no project", nm); continue
        print("project %s (run %d): %s" % (nm, pr[0], pr[3][:120]))
        nxt = next_checkpoint(nm)
        for (n, run, at, ts, text) in cx_list("checkpoint", nm):
            s = cx_get("state", nm, n); print("  C%d [%s]%s %s" % (n, s[3] if s else "open", " NEXT" if n == nxt else "", text[:110]))
        for (n, v) in q("SELECT n, value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 3", nm):
            d = json.loads(v); print("  verdict run %d C%s %s %.2f (%s): %s" % (n, d.get("n"), d.get("kind"), d.get("p", 0), d.get("judge"), d.get("text", "")[:70]))
def v_freeze(path):
    ensure_cx(); sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    run, at, _ = record("freeze", "handler", 0, sha); os.chmod(path, 0o444)
    print("frozen %s sha256 %s run %d clock %d (file now read-only)" % (path, sha, run, at))

USAGE = """cortex <verb> ...
  project <name> : <scope>                 the project's scope line
  checkpoint <name> <n> : <text> [|| <expected>] [--kind read|write|design|judgment]
  state <name> <n> open|working|done
  ingest <name> <text | ->                 sentences typed as cortex ingest lines (- reads stdin)
  judge <name> <n> <run>                   verdict on an ingested run against checkpoint n
  hydrate <name> [--at n]                  the next worker's whole prompt
  turn <name> [--engine claude|codex] [--model m] [--act]   hydrate, one worker turn, ingest, judge, move
  status [<name>]
  freeze <path>                            sha of the handler into the brain; file read-only
  accept <name> <n> [run]                  the owner's word: with a run, that sentence is a part of C n's state; without, C n is done
  reject <name> <n> <run>                  the owner's word: that sentence is not a part of C n's state, whatever the judge said
  mark <name> <run> <kind> [: <why>]       the labeled set: what that judged sentence was (completes progresses regresses supersedes drift invention hallucination dupe noise unsettled)
  learn [<name> ...] [--key]               the (project, gate) key for every line, then the judge's weights from the marks (leave-one-out accuracy printed); --key keys only
"""
def main(argv):
    if not argv: print(USAGE); return 2
    v, a = argv[0], argv[1:]
    def split_colon(parts):
        s = " ".join(parts)
        if " : " not in s: raise SystemExit("expected ' : ' between the key and the text")
        k, t = s.split(" : ", 1); return k.split(), t
    if v == "project": k, t = split_colon(a); v_project(k[0], t)
    elif v == "checkpoint":
        kind = None
        if "--kind" in a: i = a.index("--kind"); kind = a[i + 1]; a = a[:i] + a[i + 2:]
        k, t = split_colon(a); exp = None
        if " || " in t: t, exp = t.split(" || ", 1)
        v_checkpoint(k[0], int(k[1]), t, exp, kind)
    elif v == "state": v_state(a[0], int(a[1]), a[2])
    elif v == "accept": v_accept(a[0], int(a[1]), int(a[2]) if len(a) > 2 else None)
    elif v == "reject": v_reject(a[0], int(a[1]), int(a[2]))
    elif v == "ingest": v_ingest(a[0], sys.stdin.read() if a[1:] == ["-"] else " ".join(a[1:]))
    elif v == "judge": v_judge(a[0], int(a[1]), int(a[2]))
    elif v == "hydrate": v_hydrate(a[0], int(a[a.index("--at") + 1]) if "--at" in a else None)
    elif v == "turn":
        engine, model, act, at = "claude", None, False, None
        if "--engine" in a: engine = a[a.index("--engine") + 1]
        if "--model" in a: model = a[a.index("--model") + 1]
        if "--at" in a: at = int(a[a.index("--at") + 1])
        if "--act" in a: act = True
        v_turn(a[0], engine, model, act, at)
    elif v == "capture":
        def opt(flag):
            i = a.index(flag) if flag in a else -1
            return a[i + 1] if i >= 0 and i + 1 < len(a) and not a[i + 1].startswith("--") else None
        v_capture(opt("--cwd"), opt("--name"))
    elif v == "mark":
        s = " ".join(a); why = ""
        if " : " in s: s, why = s.split(" : ", 1)
        k = s.split(); v_mark(k[0], int(k[1]), k[2], why)
    elif v == "learn": v_learn([x for x in a if not x.startswith("--")] or None, key_only="--key" in a)
    elif v == "status": v_status(a[0] if a else None)
    elif v == "formula": v_formula(a[0])
    elif v == "q": print(json.dumps(ask("q " + " ".join(a)))[:4000])   # a keyed read for the builder; the kernel refuses a scan
    elif v == "freeze": v_freeze(a[0] if a else HANDLER)
    else: print(USAGE); return 2
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
