# ---- C49 to C52 (the owner, 11-04 15:3x): the judge asks why, code docs as sources with paths, a source populates what is needed, the lesson we did not write ----
def file_paragraphs(path):
    # the paragraphs of a text file with the line each begins on (a sentence of a code base's docs is keyed by its path and line, C50)
    out, buf, start = [], [], 1
    try: lines = open(path, errors="replace").read().splitlines()
    except OSError: return out
    for i, l in enumerate(lines, 1):
        if l.strip():
            if not buf: start = i
            buf.append(l)
        elif buf: out.append((start, "\n".join(buf))); buf = []
    if buf: out.append((start, "\n".join(buf)))
    return out
def source_type_paths(name, root, files, limit_per_file=400):
    # C50 (the owner, 11-04: code base docs should be able to sources with paths, so the brain can start to understand code that is being handed to it, beyond just shape):
    # a code base's docs and code typed as a reference source, every sentence keyed with the file path and the line it came from, so a claim's ground names the file
    t0 = time.time(); n_typed = dupes = noise = refused = 0; by_file = {}
    for f in files:
        rel = os.path.relpath(f, root); k_file = 0
        for (ln, para) in file_paragraphs(f):
            for sent in sentences(para):
                if is_noise(sent): noise += 1; continue
                k = text_key(sent)
                if cx_get("source", name, k): dupes += 1; continue
                try: r = typed("cortex source %s : %s" % (name, sent))
                except RuntimeError: refused += 1; continue
                run = r["run"]; cx_put("source", name, k, run, clock(), json.dumps({"path": rel, "line": ln})); key_gates(name, run); key_pairs(name, run); n_typed += 1; k_file += 1
                if k_file >= limit_per_file: break
            if k_file >= limit_per_file: break
        by_file[rel] = k_file
        if n_typed and n_typed % 500 == 0: print("  %d typed, %.0f s" % (n_typed, time.time() - t0), flush=True)
    print("source %s: %d sentences typed from %d files with their paths, %d repeats, %d noise, %d refused, %.1f s" % (name, n_typed, len(by_file), dupes, noise, refused, time.time() - t0))
    return n_typed, by_file
CODE_GLOBS = ("README*", "*.md", "docs/*.md", "docs/**/*.md", "doc/*.md", "concepts/*/*.md", "*.py", "**/*.py", "*.go", "**/*.go", "*.ts", "**/*.ts", "*.rs", "**/*.rs", "*.sql", "**/*.sql")
def code_files(root, globs=None, limit=300):
    import glob
    out, seen = [], set()
    for pat in (globs or CODE_GLOBS):
        for f in sorted(glob.glob(os.path.join(root, pat), recursive=True)):
            if f in seen or not os.path.isfile(f) or "/.git/" in f or "/node_modules/" in f or "/.meta/" in f: continue
            seen.add(f); out.append(f)
            if len(out) >= limit: return out
    return out
def v_source_path(name, band, root, text, domain=None, globs=None):
    # cortex source <name> reference --path <folder> [--glob a,b] : <what it is>: the folder's docs and code typed with paths (C50)
    ensure_cx(); root = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(root): raise SystemExit("no such folder: " + root)
    if not cx_get("source", name, 0): v_source(name, band or "reference", text or ("the docs and code of %s, read %s" % (root, time.strftime("%Y-%m-%d"))), domain or ["software", "coding"])
    had = cx_get("source", name, 0); d = json.loads(had[3]); d["path"] = root; cx_put("source", name, 0, had[0], had[1], json.dumps(d)); _SRCD.pop(name, None)
    fs = code_files(root, globs)
    n, by = source_type_paths(name, root, fs)
    top = sorted(by.items(), key=lambda kv: -kv[1])[:6]
    print("source %s path %s: %d files read; most lines from %s" % (name, root, len(fs), ", ".join("%s %d" % kv for kv in top)))
    return n
def source_line_of(nm, run):
    # C50: the path and line a source's run came from, when that source was typed with paths
    row = q("SELECT value FROM main.cx WHERE kind = 'source' AND name = ? AND run = ? AND n > 0", nm, run)
    try: d = json.loads(row[0][0]) if row else {}
    except (ValueError, TypeError): d = {}
    return (d.get("path"), d.get("line")) if d.get("path") else (None, None)
def code_ground(name, run, limit=3):
    # C50: the pairs of a claim that a source typed with paths holds, named by file and line
    out, seen = [], set()
    pathed = [nm for (nm, band) in sources() if source_info(nm).get("path")]
    if not pathed: return out
    for (a, b) in pairs_of(run):
        k = pair_key(a, b)
        for nm in pathed:
            had = cx_get("pair", nm, k)
            if not had: continue
            first = json.loads(had[3]).get("first"); p, l = source_line_of(nm, first)
            if p and (nm, p, l) not in seen: seen.add((nm, p, l)); out.append("%s %s:%s holds %s %s" % (nm, p, l, sym_of(a), sym_of(b)))
            if len(out) >= limit: return out
    return out
def gate_of_word(w):
    rows = q("SELECT gate FROM main.label WHERE symbol = ?", w)
    return rows[0][0] if rows else None
def v_questions_ask(name):
    # C51 (the owner, 11-04: a source is not just memorized by the brain but used to populate what it feels it needs to know): every open question's words looked up in the
    # registered sources (pairs and gates); a word a source holds is answered naming the source (and the file and line when the source has paths); a question with no word left closes
    ensure_cx(); qs = open_questions(name, None, 60); srcs = [nm for (nm, b) in sources()]; closed = 0
    print("questions of %s asked of the sources: %d open" % (name, len(qs)))
    for d in qs:
        words = d.get("words") or []; found, left = [], []
        for w in words:
            if w.startswith(("no print", "no record", "against the owner", "three sources", "the record of")): left.append(w); continue
            body = w[6:] if w.startswith("pair: ") else w
            toks = [t for t in re.findall(r"[a-z][a-z0-9_']+", body.lower()) if t not in STOP]
            gates = [gate_of_word(t) for t in toks]
            holders = []
            if w.startswith("pair: ") and len(gates) == 2 and all(gates): holders = [(nm, cx_get("pair", nm, pair_key(gates[0], gates[1]))) for nm in srcs]; holders = [(nm, h) for (nm, h) in holders if h]
            elif gates and all(gates): holders = [(nm, cx_get("gate", nm, gates[0])) for nm in srcs if all(cx_get("gate", nm, g) for g in gates)]
            if holders:
                where = []
                for (nm, h) in holders[:3]:
                    first = json.loads(h[3]).get("first"); p, l = source_line_of(nm, first)
                    where.append("%s%s" % (nm, (" %s:%s" % (p, l)) if p else ""))
                found.append("%s held by %s" % (w, ", ".join(where)))
            else: left.append(w)
        if found and not left:
            answer_question(name, d["run"], "sources: " + "; ".join(found)[:300]); closed += 1
            try: record("answer", name, d["run"], "C%d run %d: %s" % (d.get("n", 0), d["run"], "; ".join(found)[:400]))
            except RuntimeError: pass
            print("  C%s run %d: closed by the sources: %s" % (d.get("n"), d["run"], "; ".join(found)[:300]))
        else: print("  C%s run %d: %s%s" % (d.get("n"), d["run"], ("held: " + "; ".join(found)[:200] + " | ") if found else "", "no source holds: " + "; ".join(left)[:240]))
    print("%d of %d questions closed by the sources; the rest wait on the owner or a new source" % (closed, len(qs)))
def numbers_in_prints(name, n, run, nums):
    # the numbers among nums that a print of this checkpoint older than the claim holds (read now, as the judge should have)
    held = set()
    for cmd, d in receipts_of(name, n).items():
        for l in d.get("lines", []):
            if l["run"] >= run: continue
            for t in numbers(line_text(l["run"])):
                if t in nums: held.add(t)
    return sorted(held)
WHY_RULES = {
    "a true line convicted": ("the owner accepted or marked this run as a part after the judge called it off rail", "the shape or receipt rule that convicted it is too strong for this shape", "narrow the rule in sheet_cells or formula so the re-judge of this run is not hallucination, invention or drift; add the case to the marks and relearn"),
    "a false line accepted": ("the owner rejected or marked this run after the judge made it a part", "the shape or receipt rule that accepted it is too loose", "tighten the rule so the re-judge of this run is not completes or progresses"),
    "a close the check undid": ("the cortex own check printed check wrong after this verdict closed the checkpoint", "the judge closed on the worker's words and prints while the check on numbers of its own failed", "a completes by receipt must not close a checkpoint that has a check until the check prints check ok"),
    "asked and convicted at once": ("the sheet asked for a print it lacked and the formula convicted the same line", "a missing print is a question, not a verdict (C35.3), but the formula ran the receipt conviction anyway", "when measure_missing or print_missing is set, the verdict is unsettled with the question, never hallucination by receipt"),
    "a number held by a print was called out": ("the number the verdict called out is in a print of this checkpoint older than the claim", "the receipt cells read the newest lines of each print only, or the number was cut from the typed receipt line", "the receipt cells must read every typed line of the checkpoint's prints older than the claim"),
}
def v_why(name, plan=False):
    # C49 (the owner, 11-04 15:3x: the sixth should see the trust drop the incorrect judgement and ask why did this happen, how did it happen, can it be fixed, do we have a plan,
    # then the cortex can register its own plan, ask the headless to build it): the verdicts of this project the record itself proves wrong, each with the cells that decided it
    # and the rule; --plan registers the cortex's own plan on the project cortex-self (a clone of the front door, built by the headless against the test brain on port 7010)
    ensure_cx(); faults = []
    vs = [(run, jload(v), ts) for (run, v, ts) in q("SELECT n, value, ts FROM main.cx WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 400", name)]
    parts = {}
    for (k, v) in q("SELECT n, value FROM main.cx WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 400", name):
        d = jload(v); parts.setdefault(d.get("run"), []).append(d)
    marks = {}
    for (k, v) in q("SELECT n, value FROM main.cx WHERE kind = 'mark' AND name = ? AND n > 0 LIMIT 400", name): marks[k] = jload(v)
    checks = {}
    for (n0, r0, a0, t0, v0) in cx_list("checklast", name): checks[n0] = jload(v0)
    for (run, d, vts) in vs:
        kind, by, n, sh = d.get("kind"), d.get("judge"), d.get("n"), d.get("sheet") or {}
        ps = parts.get(run, []); owner_in = any(p.get("by") == "owner" for p in ps); rejected = any(p.get("rejected_by") for p in ps)
        mk = (marks.get(run) or {}).get("kind"); why = None; cells = ""
        if kind in ("hallucination", "invention", "drift") and (owner_in or mk in ("completes", "progresses")): why = "a true line convicted"; cells = "numbers out %s, words out %s" % (",".join(sh.get("numbers_out") or []) or "-", ",".join((sh.get("words_out") or [])[:6]) or "-")
        elif kind in ("completes", "progresses", "supersedes") and (rejected or mk in ("drift", "invention", "hallucination", "noise")): why = "a false line accepted"; cells = "shape expected %.2f, numbers in %s" % (sh.get("shape_expected") or 0, ",".join(sh.get("numbers_in") or []) or "-")
        elif kind == "completes" and by in ("shape", "receipt") and checks.get(n) and not checks[n].get("ok") and checks[n].get("ts", 0) > (vts or 0): why = "a close the check undid"; cells = "the check printed: %s" % (checks[n].get("last") or "")[:120]
        elif kind in ("hallucination", "invention", "drift") and by == "receipt" and (sh.get("measure_missing") or sh.get("print_missing")): why = "asked and convicted at once"; cells = "measure missing %s, print missing %s, numbers out %s" % (",".join(sh.get("measure_missing") or []) or "-", ",".join(sh.get("print_missing") or []) or "-", ",".join(sh.get("numbers_out") or []) or "-")
        elif kind == "hallucination" and by == "receipt" and sh.get("numbers_out"):
            held = numbers_in_prints(name, n, run, set(sh["numbers_out"]))
            if held and set(held) >= set(sh["numbers_out"]): why = "a number held by a print was called out"; cells = "numbers out %s, held by a print older than the claim: %s" % (",".join(sh["numbers_out"]), ",".join(held))
        if why: faults.append({"run": run, "n": n, "kind": kind, "by": by, "why": why, "cells": cells, "text": line_text(run)[:140], "ts": vts})
    kinds = {}
    for f in faults: kinds[f["why"]] = kinds.get(f["why"], 0) + 1
    print("why %s: %d verdicts of %d the record proves wrong%s" % (name, len(faults), len(vs), (": " + ", ".join("%s %d" % kv for kv in sorted(kinds.items(), key=lambda kv: -kv[1]))) if kinds else ""))
    for f in faults[:30]:
        how = WHY_RULES[f["why"]]
        print("  run %d C%d %s by %s [%s]: %s\n    why: %s | cells: %s\n    how: %s | fix: %s" % (f["run"], f["n"], f["kind"], f["by"], time.strftime("%m-%d %H:%M", time.localtime(f["ts"] or 0)), f["text"], how[0], f["cells"], how[1], how[2]))
    if not plan or not faults: return faults
    # the plan: one checkpoint per fault kind on cortex-self, the clone of the front door the headless builds against the test brain
    self_repo = os.path.join(WORKDIR, "self")
    if not os.path.isdir(os.path.join(self_repo, ".git")):
        subprocess.run(["git", "clone", "-q", os.path.join(HOME, "cortex"), self_repo], check=True); print("cloned the front door to %s" % self_repo)
    if not cx_get("project", "cortex-self", 0):
        v_project("cortex-self", "the front door's own code, cortex.py, fixed by the headless on the clone %s against the test brain on port 7010 (CORTEX_PORT=7010 python3 cortex.py ...), never the live brain on 7007; each checkpoint is a judge fault the cortex found itself (cortex why); a fix the check proves is carried to the live front door by the liaison with git (the owner, 11-04 15:3x: the cortex can register its own plan, ask the headless to build it, later maybe it just builds it itself)" % self_repo)
    cx_put("repo", "cortex-self", 0, 0, clock(), json.dumps({"path": self_repo, "ts": int(time.time())}))
    existing = {n0 for (n0, r0, a0, t0, x0) in cx_list("checkpoint", "cortex-self")}; nn = (max(existing) + 1) if existing else 1
    seen_kinds = set()
    for (n0, r0, a0, t0, x0) in cx_list("checkpoint", "cortex-self"):
        for wk in WHY_RULES:
            if wk in (x0 or ""): seen_kinds.add(wk)
    for f in faults:
        if f["why"] in seen_kinds: continue
        seen_kinds.add(f["why"]); how = WHY_RULES[f["why"]]
        wrong = {"a true line convicted": "hallucination|invention|drift", "asked and convicted at once": "hallucination|invention|drift", "a number held by a print was called out": "hallucination", "a false line accepted": "completes|progresses|supersedes", "a close the check undid": "completes"}[f["why"]]
        text = "judge fault, %s (the cortex own why, C49): %s; cells: %s; the rule: %s; fix: %s; first seen on %s C%d run %d: %s. Change cortex.py of this clone only; run it as CORTEX_PORT=7010 python3 cortex.py judge %s %d %d against the test brain; never port 7007; name the cause in a comment with the date" % (f["why"], how[0], f["cells"], how[1], how[2], name, f["n"], f["run"], f["text"][:100], name, f["n"], f["run"])
        exp = "CORTEX_PORT=7010 python3 cortex.py judge %s %d %d prints a verdict line whose kind is not %s" % (name, f["n"], f["run"], wrong.replace("|", " or "))
        v_checkpoint("cortex-self", nn, text, exp)
        chk = "cd %s && CORTEX_PORT=7010 timeout 300 python3 cortex.py judge %s %d %d 2>&1 | grep '^verdict' | grep -vqE ' (%s) ' && echo 'check ok: the re-judge of run %d is no longer %s' || echo 'check wrong: the re-judge of run %d still prints %s'" % (self_repo, name, f["n"], f["run"], wrong, f["run"], wrong.replace("|", "/"), f["run"], wrong.replace("|", "/"))
        v_check_set("cortex-self", nn, chk); nn += 1
    print("plan registered on cortex-self (%d checkpoints); the test brain must hold the runs: cortex self refresh; then cortex build cortex-self --box 20 --turns 4" % (nn - 1))
    return faults
def test_kernel(cmd):
    # the test system beside the live one (the owner, 11-04: or maybe into a test system): the cascade kernel on port 7010 over a copy of the live brain
    B = os.path.join(HOME, "cortex", "brain"); T = os.path.join(HOME, "cortex", "brain-test"); NK = os.path.join(HOME, "cortex", "nk-new")
    def up(port):
        try: socket.create_connection(("127.0.0.1", port), timeout=1).close(); return True
        except OSError: return False
    def stop_test():
        subprocess.run(["pkill", "-f", "nk 7010 "]);
        for i in range(300):
            if not up(7010): return
            time.sleep(1)
    def start_test():
        os.makedirs(T, exist_ok=True)
        subprocess.Popen("cd %s && NK_MAP=%s/brain.map nohup ./nk 7010 egg-symbols.txt sources wn gcide mwt moby map sqldoc measured guess wikt > %s/nk.log 2>&1 < /dev/null &" % (NK, T, T), shell=True)
        for i in range(600):
            if up(7010): return True
            time.sleep(1)
        return False
    if cmd == "stop": stop_test(); print("test kernel on 7010 stopped")
    elif cmd == "start": print("test kernel on 7010 %s" % ("up" if start_test() else "did not come up"))
    elif cmd == "refresh":
        t0 = time.time(); stop_test()
        subprocess.run(["systemctl", "--user", "stop", "cortex-page", "cortex-nk"], check=True)
        for i in range(600):
            if subprocess.run(["pgrep", "-x", "nk"], capture_output=True).returncode != 0: break
            time.sleep(1)
        t1 = time.time(); os.makedirs(T, exist_ok=True)
        for f in os.listdir(T):
            if f.startswith("brain.map"): os.remove(os.path.join(T, f))
        subprocess.run(["cp", "--sparse=always", os.path.join(B, "brain.map"), os.path.join(T, "brain.map")], check=True)
        for f in ("brain.map.main.db", "brain.map.sixth.db", "brain.map.xyz"):
            if os.path.exists(os.path.join(B, f)): shutil.copy(os.path.join(B, f), os.path.join(T, f))
        t2 = time.time(); subprocess.run(["systemctl", "--user", "start", "cortex-nk", "cortex-page"], check=True)
        for i in range(300):
            if up(PORT): break
            time.sleep(1)
        ok = start_test()
        print("test brain refreshed from the live brain: live stopped %.0f s, copy %.0f s, live up again, test kernel on 7010 %s (%.0f s in all); the live clock %d" % (t1 - t0, t2 - t1, "up" if ok else "did not come up", time.time() - t0, clock()))
    else: print("cortex self start|stop|refresh")
LESSON_DOC_GLOBS = ("docs/*.md", "concepts/*/introduction.md", "concepts/*/about.md")
def lesson_tests_count(lang, path):
    try: t = open(path, errors="replace").read()
    except OSError: return 0
    return len(re.findall(r"(?m)^\s*def test_", t)) if lang == "python" else len(re.findall(r"(?m)^func Test", t))
def v_lesson(name, track, ladder=None, picks=None):
    # C52 (the owner, 11-04 15:3x: find docs that are teaching docs for the codebases, and see if it can learn from a lesson that we did not write; a beginner to senior style lesson
    # progression, with checkpoints, tests, answer key held by the judge): a public teaching track (exercism) becomes an outline: one checkpoint per exercise in difficulty order, the
    # lesson's own instructions as the text, the tests passing as the expected, and the cortex check holding the answer key (the tests' shas and the exemplar, outside the repo)
    ensure_cx(); track = os.path.abspath(os.path.expanduser(track))
    cfg = json.load(open(os.path.join(track, "config.json"))); lang = (cfg.get("language") or os.path.basename(track)).lower()
    if lang not in ("python", "go"): raise SystemExit("the lesson runner knows python and go tracks today; this track says " + lang)
    practice = [e for e in cfg["exercises"]["practice"] if e.get("status", "active") != "deprecated"]
    chosen = []
    if picks: chosen = [e for s in picks for e in practice if e["slug"] == s]
    else:
        for dd in (ladder or [1, 2, 3, 4, 5, 6]):
            for e in practice:
                if e.get("difficulty") == dd and e not in chosen: chosen.append(e); break
    if not chosen: raise SystemExit("no exercises chosen")
    repo = os.path.join(WORKDIR, name); keys = os.path.join(WORKDIR, "keys", name); os.makedirs(repo, exist_ok=True); os.makedirs(keys, exist_ok=True); os.chmod(os.path.join(WORKDIR, "keys"), 0o700)
    if not cx_get("project", name, 0):
        v_project(name, "a lesson we did not write: the exercism %s track (%s, MIT), %d exercises from difficulty %d to %d, each a checkpoint: make its tests pass by changing the stub only; the tests and the answer key are held by the cortex, which runs the tests itself on its own copy after every turn (the owner, 11-04 15:3x: a beginner to senior style lesson progression, with checkpoints, tests, answer key held by the judge)" % (lang, track, len(chosen), min(e["difficulty"] for e in chosen), max(e["difficulty"] for e in chosen)))
    cx_put("repo", name, 0, 0, clock(), json.dumps({"path": repo, "ts": int(time.time()), "track": track, "lesson": lang}))
    src = name + "-lesson"
    if not cx_get("source", src, 0):
        v_source(src, "reference", "the exercism %s track's own teaching docs (docs/*.md, concepts/*/introduction.md, about.md) and the chosen exercises' instructions, read %s" % (lang, time.strftime("%Y-%m-%d")), ["software", "coding"])
        had = cx_get("source", src, 0); d = json.loads(had[3]); d["path"] = track; cx_put("source", src, 0, had[0], had[1], json.dumps(d)); _SRCD.pop(src, None)
        fs = code_files(track, LESSON_DOC_GLOBS, limit=120) + [f for e in chosen for f in code_files(os.path.join(track, "exercises", "practice", e["slug"], ".docs"), ("*.md",), limit=4)]
        source_type_paths(src, track, fs)
    existing = {n0 for (n0, r0, a0, t0, x0) in cx_list("checkpoint", name)}; n = (max(existing) + 1) if existing else 1
    done_slugs = set()
    for (n0, r0, a0, t0, x0) in cx_list("checkpoint", name):
        m = re.search(r"lesson (\S+), difficulty", x0 or "")
        if m: done_slugs.add(m.group(1))
    got = []
    for e in chosen:
        slug = e["slug"]
        if slug in done_slugs: print("C for %s exists already; not re-typed" % slug); continue
        exd = os.path.join(track, "exercises", "practice", slug); meta = json.load(open(os.path.join(exd, ".meta", "config.json")))
        sol = meta["files"]["solution"]; tests = meta["files"]["test"]; example = meta["files"]["example"]
        dest = os.path.join(repo, slug); os.makedirs(dest, exist_ok=True)
        for f in sol + tests + (["go.mod"] if lang == "go" else []):
            if os.path.exists(os.path.join(exd, f)): os.makedirs(os.path.dirname(os.path.join(dest, f)), exist_ok=True); shutil.copy(os.path.join(exd, f), os.path.join(dest, f))
        docs = []
        for dn in ("introduction.md", "instructions.md", "instructions.append.md"):
            p = os.path.join(exd, ".docs", dn)
            if os.path.exists(p): docs.append(open(p, errors="replace").read())
        open(os.path.join(dest, "INSTRUCTIONS.md"), "w").write("\n\n".join(docs))
        kd = os.path.join(keys, slug); os.makedirs(kd, exist_ok=True); shas = {}
        for f in tests: shutil.copy(os.path.join(exd, f), os.path.join(kd, os.path.basename(f))); shas[f] = hashlib.sha256(open(os.path.join(exd, f), "rb").read()).hexdigest()
        if lang == "go" and os.path.exists(os.path.join(exd, "go.mod")): shutil.copy(os.path.join(exd, "go.mod"), kd)
        for f, s in zip(example, sol): shutil.copy(os.path.join(exd, f), os.path.join(kd, "example-" + os.path.basename(s)))
        ntests = sum(lesson_tests_count(lang, os.path.join(exd, f)) for f in tests)
        json.dump({"lang": lang, "slug": slug, "solution": sol, "tests": tests, "shas": shas, "ntests": ntests, "difficulty": e.get("difficulty"), "track": track}, open(os.path.join(kd, "key.json"), "w"))
        # the key proven once: the exemplar against the tests on the cortex own copy
        p = subprocess.run(["python3", os.path.join(WORKDIR, "checks", "lesson.py"), name, slug, "--key"], capture_output=True, text=True, timeout=300); keyline = (p.stdout.strip().splitlines() or ["(no print)"])[-1]
        blurb = (e.get("blurb") or meta.get("blurb") or "").strip()
        text = "lesson %s, difficulty %d of 9 (exercism %s, a lesson we did not write): %s The lesson own instructions are in %s/INSTRUCTIONS.md of this repo (%d lines); the stub %s and the tests %s are beside it. Make the tests pass by changing the stub only; never change the tests; the cortex runs the tests itself on its own copy with numbers of its own" % (slug, e.get("difficulty", 0), lang, blurb, slug, sum(1 for _ in open(os.path.join(dest, "INSTRUCTIONS.md"))), ", ".join(sol), ", ".join(tests))
        exp = ("cd %s && python3 -m pytest -q %s prints %d passed" % (slug, " ".join(tests), ntests)) if lang == "python" else ("cd %s && go test ./... prints ok" % slug)
        v_checkpoint(name, n, text, exp); v_check_set(name, n, "python3 %s/checks/lesson.py %s %s" % (WORKDIR, name, slug))
        print("  C%d %s difficulty %d: %d tests, key: %s" % (n, slug, e.get("difficulty", 0), ntests, keyline[:120])); got.append(n); n += 1
    print("lesson %s: %d checkpoints registered from %s in difficulty order (%s); the keys in %s; read them with cortex status %s, then cortex build %s --box 30 --turns 12" % (name, len(got), track, " ".join("C%d" % x for x in got), keys, name, name))
