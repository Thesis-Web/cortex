#!/usr/bin/env python3
# cortex.py (2026-11-02): the Cortex front door on hp2. One file, stdlib only. The brain (nk on 127.0.0.1:7007) stores; jev judges; this code
# decides by the truth table in CORTEX-HANDLER.md section 7; a worker (claude -p / codex exec) works one turn on the hydration and nothing else.
# Every Cortex record is one line typed at the brain's main prompt (a run, a clock, a memory row, a dedupe tick); main.cx is the keyed index of
# those lines (one row per kind/name/n, replaced in place), because the kernel refuses a read without a key. No log table, no timer, no sweep.
import socket, json, sys, os, re, time, hashlib, subprocess, urllib.request, urllib.error
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
    # a fenced block is live output: kept, its fence marks dropped, each of its lines a sentence of its own
    text = re.sub(r"```[a-zA-Z0-9_-]*\n?(.*?)```", lambda m: "\n" + m.group(1) + "\n", text, flags=re.S)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    out = []
    for p in parts:
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
    ensure_cx(); run, at, r = record("project", name, 0, clean(scope))
    print("project %s run %d clock %d born %d" % (name, run, at, r["born"]))
def v_checkpoint(name, n, text, expected=None, kind=None):
    ensure_cx(); run, at, r = record("checkpoint", name, n, clean(text)); print("checkpoint %s %d run %d clock %d" % (name, n, run, at))
    if expected: run2, at2, _ = record("expected", name, n, clean(expected)); print("expected %s %d run %d" % (name, n, run2))
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
def v_ingest(name, text, quiet=False):
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
            cx_put("ingest", name, k, had[0], had[1], json.dumps({"t": t, "times": times}))
            out.append({"run": had[0], "clock": had[1], "born": 0, "seconds": 0.0, "same_as": had[0], "again": times, "text": s})
            if not quiet: print("ingest run %d again %d (a repeat; nothing typed): %s" % (had[0], times, s[:100]))
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
        cx_put("ingest", name, k, run, at, json.dumps({"t": s, "times": 1})); cx_put("restate", name, wordset_key(s), run, at, str(k))
        out.append({"run": run, "clock": at, "born": r["born"], "seconds": r["seconds"], "same_as": 0, "again": 1, "text": s})
        if not quiet: print("ingest run %d clock %d born %d %.3fs: %s" % (run, at, r["born"], r["seconds"], s[:100]))
    print("filter: %d sentences, kept %d, dupe %d, restated %d, noise %d, %.0f ms" % (len(fates), counts["keep"], counts["dupe"], counts["restated"], counts["noise"], (time.time() - t0) * 1000))
    return out
# ---- part-wise state (handler C12): a checkpoint's accepted state is the set of sentences accepted into it over time ----
def add_part(name, n, run, text):
    k = text_key(text); had = cx_get("part", name, k)
    if had:
        d = json.loads(had[3]); d["times"] = d.get("times", 1) + 1; cx_put("part", name, k, had[0], had[1], json.dumps(d)); return "tick %d" % d["times"]
    cx_put("part", name, k, run, clock(), json.dumps({"t": text, "n": n, "run": run, "times": 1})); return "added"
def parts_of(name, n, limit=5):
    rows = q("SELECT value FROM main.cx WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 60", name)
    return [json.loads(v) for (v,) in rows if json.loads(v).get("n") == n][:limit]
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
    return cells
def formula(cells, answers):
    # the substitution formulas over a full sheet: what the deterministic cells settle, then the judgment cells
    if cells["noise"]: return "noise", "sheet"
    if answers: return decide(answers), "jev"
    if cells["words"] >= 4 and cells["shared_scope"] == 0 and cells["shared_checkpoint"] == 0 and cells["shared_expected"] == 0: return "drift", "sheet"
    return "unsettled", "sheet"
def v_judge(name, n, run, text=None):
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
    if not cells["noise"]:
        try:
            resp = jev(state, JUDGE_QUESTIONS)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            raise SystemExit("jev call failed, no verdict written: %s" % e)
        if resp: answers = {k: round(v.get("noul", 0.0), 3) for k, v in resp["answers"].items()}; model = resp.get("model", JEV_MODEL)
    kind, by = formula(cells, answers); judge = model if by == "jev" else "sheet"
    p = (answers.get(kind, 0.0) if kind in answers else max(answers.values())) if answers else 0.0
    body = "%s %.3f %s" % (kind, p, judge)
    vrun, at, _ = record("verdict", name, run, body)
    part = add_part(name, n, run, text) if kind in ("completes", "progresses", "supersedes") else ""
    cx_put("verdict", name, run, vrun, at, json.dumps({"n": n, "run": run, "kind": kind, "p": p, "judge": judge, "answers": answers, "sheet": cells, "part": part, "text": text[:300]}))
    geo = cells["geometry"]
    print("verdict %s %d run %d: %s %.3f by %s in %.0f ms | sheet words %d shared scope %d checkpoint %d expected %d mark %s times %d noise %s | geometry mag %s rad %s | history %s%s" % (name, n, run, kind, p, judge, (time.time() - t0) * 1000, cells["words"], cells["shared_scope"], cells["shared_checkpoint"], cells["shared_expected"], cells["expected_mark"], cells["times"], cells["noise"] or "-", geo.get("magnitude"), geo.get("radians"), json.dumps(cells["history"]), (" | part " + part) if part else ""))
    if answers: print("  answers " + " ".join("%s=%.2f" % kv for kv in sorted(answers.items())))
    elif not cells["noise"]: print("  judgment cells empty: no jev key (typesafe.key or gateway.key in ~/.config/cortex)")
    return kind
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
        if ps: lines.append("ACCEPTED SO FAR (parts of C%d's state): " % nxt + " | ".join(p["t"][:90] for p in reversed(ps)))
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
    state = {"project": name, "scope": pr[3], "checkpoint": ck[3], "expected": ex[3] if ex else "(none)", "accepted_state": accepted_state(name, n), "last_verdicts": [json.loads(v).get("text", "")[:200] for (_, v) in q("SELECT n, value FROM main.cx WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 3", name)]}
    resp = jev(state, {"holds": {"type": "noul", "instructions": "`checkpoint` is true of the state described by `scope`, `accepted_state` and `last_verdicts`", "criteria": {"false": "the state does not show the checkpoint's statement to be true"}}})
    if not resp: raise SystemExit("judgment step needs jev; no key (typesafe.key or gateway.key in ~/.config/cortex)")
    p = resp["answers"]["holds"]["noul"]
    return "judgment by %s: the statement holds with probability %.2f. EXPECTED: %s" % (resp.get("model", JEV_MODEL), p, "met" if p >= THRESH else "not met"), p
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
        print("turn %s C%d: a judgment step, routed to jev (no model turn)" % (name, nxt))
        out, p = judgment_step(name, nxt, cx_get("checkpoint", name, nxt)); err, rc, secs = "", 0, 0.0
        print("jev answered: %s" % out)
    else:
        print("turn %s C%d [%s]: %s %s, prompt %d bytes (the hydration, nothing else)" % (name, nxt, kind, engine, model, len(h.encode())))
        out, err, rc, secs = worker(engine, model, h, cwd, act)
    print("worker rc %d in %.1fs, output %d bytes" % (rc, secs, len(out.encode())))
    if rc != 0 or not out.strip(): print("worker stderr: " + err[-800:]); raise SystemExit("worker failed, nothing ingested")
    ing = v_ingest(name, out, quiet=True); kinds = []
    for i in ing:
        if i["same_as"]: continue
        kinds.append(v_judge(name, nxt, i["run"], i["text"]))
    print("ingested %d sentences (%d repeats), verdicts: %s" % (len(ing), sum(1 for i in ing if i["same_as"]), " ".join(kinds) or "none"))
    if "completes" in kinds:
        v_state(name, nxt, "done"); n2 = next_checkpoint(name)
        if n2 is not None: v_state(name, n2, "working")
        print("C%d done; next C%s" % (nxt, n2))
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
    raw = sys.stdin.read(); last = None
    for line in raw.splitlines():
        try: d = json.loads(line)
        except ValueError: continue
        if d.get("type") != "assistant": continue
        c = d.get("message", {}).get("content")
        texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"] if isinstance(c, list) else ([c] if isinstance(c, str) else [])
        t = "\n".join(x for x in texts if x and x.strip())
        if t.strip(): last = t
    if not last: print("capture: no assistant text in the tail"); return
    name = name or project_for_cwd(cwd)
    if not name: print("capture: cwd %s belongs to no cortex project; nothing ingested" % cwd); return
    ensure_cx(); ing = v_ingest(name, last, quiet=True); new = [i for i in ing if not i["same_as"]]
    print("capture %s: %d sentences, %d new, %d repeats, last text %d bytes" % (name, len(ing), len(new), len(ing) - len(new), len(last.encode())))
    nxt = next_checkpoint(name)
    if nxt is None: return
    if jev_key():
        kinds = [v_judge(name, nxt, i["run"], i["text"]) for i in new]; print("judged against C%d: %s" % (nxt, " ".join(kinds)))
    else: print("not judged: no jev key")
def v_status(name=None):
    ensure_cx(); st = ask("stats")["main"]
    r = jev_route()
    print("brain: gates %d runs %d hops %d refused %d clock %d | jev %s | index rows %d" % (st["gates"], st["runs"], st["hops"], st["refused"], clock(), ("via " + r["via"]) if r else "NO KEY (typesafe.key or gateway.key in ~/.config/cortex)", q("SELECT count(*) FROM main.cx WHERE kind = 'checkpoint' AND name = ? AND n >= 0", name or "")[0][0] if name else -1))
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
    elif v == "status": v_status(a[0] if a else None)
    elif v == "q": print(json.dumps(ask("q " + " ".join(a)))[:4000])   # a keyed read for the builder; the kernel refuses a scan
    elif v == "freeze": v_freeze(a[0] if a else HANDLER)
    else: print(USAGE); return 2
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
