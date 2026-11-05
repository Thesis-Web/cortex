# ---- the project lesson-senses (the owner, 11-04 21:3x: a lesson in a real doc that teaches a human; you as the teacher; the judge has the answer key you have never seen;
#      lecture, problems marked correct or incorrect, teach another way, a test graded by the judge, a quiz with edge cases). The learner is the test brain (CORTEX_LEARNER, 7010);
#      the record is the live cortex. The teacher never reads the key: the judge (this code's key_for) reads wn.db only to mark, after the brain answered. ----
LEARNER = int(os.environ.get("CORTEX_LEARNER", "7010"))
def ask_learner(req):
    s = socket.create_connection(("127.0.0.1", LEARNER), timeout=600); s.sendall((req + "\n").encode()); buf = b""
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b"\n"): break
    s.close(); return json.loads(buf.decode())
def ql(sql, *params):
    def lit(v):
        if v is None: return "NULL"
        if isinstance(v, (int, float)): return str(v)
        return "'" + str(v).replace("'", "''") + "'"
    for p in params: sql = sql.replace("?", lit(p), 1)
    r = ask_learner("q " + sql); return r.get("rows", []) if isinstance(r, dict) else []
def wn_key():
    # the judge's key: wordnet words with two or more senses whose quoted examples use the word; sentence -> sense; the teacher never prints a sense before the brain answered
    import sqlite3
    db = sqlite3.connect(os.path.join(HOME, "cortex", "nk", "sources", "wn.db")); by = {}
    for (w, i, t) in db.execute("SELECT word, id, text FROM corpus WHERE text LIKE ?", ("%\"%",)):
        m = re.match(r"(noun|verb|adj|adv|adjective|adverb)\s+(\d+):", t)
        if not m or " " in w or "_" in w or "-" in w: continue
        exs = [e for e in re.findall(r"\"([^\"]{12,90})\"", t.split(" [syn:")[0]) if re.search(r"\b%s\b" % re.escape(w), e)]
        if exs: by.setdefault(w, []).append((m.group(1) + " " + m.group(2), exs, i))
    db.close(); return {w: v for w, v in by.items() if len(v) >= 2}
def lecture_text():
    out = []
    for f in ("wiki-word-sense.json", "wiki-polysemy.json", "wiki-word-sense-disambiguation.json"):
        p = os.path.join(WORKDIR, "sources-c36", f)
        if not os.path.exists(p): continue
        try: d = json.load(open(p)); page = list(d["query"]["pages"].values())[0]; out.append((page.get("title", f), page.get("extract", "")))
        except Exception: pass
    return out
def learner_gate(word):
    rows = ql("SELECT gate FROM main.label WHERE symbol = ?", word); return rows[0][0] if rows else None
def learner_sense_of_use(word, sentence):
    # the brain's answer: the sentence typed as a use; the hit on the word's gate names the shard it landed on; the shard's sense rows name the sense (several = ambiguous, none = no answer)
    r = ask_learner("type main " + sentence); run = r.get("run") or 0; g = learner_gate(word)
    if not run or not g: return {"run": run, "shard": None, "senses": [], "texts": []}
    hits = ql("SELECT pos, gate, shard FROM main.hit WHERE run = ? AND gate = ?", run, g); shard = hits[0][2] if hits else None
    rows = ql("SELECT run FROM main.sense_shard WHERE gate = ? AND shard = ?", g, shard) if shard else []
    senses, texts = [], []
    for (srun,) in rows[:6]:
        t = ((ask_learner("run main %d" % srun).get("run") or {}).get("text") or ""); m = re.match(r"(noun|verb|adj|adv|adjective|adverb)\s+(\d+):", t)
        if m: senses.append(m.group(1) + " " + m.group(2)); texts.append(t[:80])
    return {"run": run, "shard": shard, "senses": senses, "texts": texts}
def lesson_words(k=None, fresh=False):
    had = cx_get("lessonwords", "lesson-senses", 0)
    if had and not fresh: return json.loads(had[3])
    import random
    key = wn_key(); words = random.sample(sorted(key), k or 8)
    cx_put("lessonwords", "lesson-senses", 0, 0, clock(), json.dumps(words)); return words
def v_senses(cmd, k=6):
    ensure_cx(); name = "lesson-senses"
    if cmd == "plan":
        key = wn_key(); docs = lecture_text()
        print("lesson plan, word senses: the lecture from %s (%d sentences); the key held by the judge: %d words with two or more senses carrying examples, %d example sentences; the learner on port %d" % (", ".join(t for t, x in docs), sum(len(sentences(x)) for t, x in docs), len(key), sum(len(e) for v in key.values() for s, e, i in v), LEARNER))
        return
    if cmd == "lecture":
        words = lesson_words(k, fresh=True); docs = lecture_text(); n_typed = 0
        for (title, text) in docs:
            for s in sentences(text)[:k * 2]:
                if is_noise(s): continue
                try: ask_learner("type main cortex lecture %s : %s" % (name, s)); n_typed += 1
                except Exception: pass
        laid = []
        for w in words:
            r = ask_learner("type main define : %s" % w); run = r.get("run") or 0; g = learner_gate(w)
            cells = [c for c in (ask_learner("run main %d" % run).get("cells") or []) if c[0] == 187]; nsense = len((cells[0][2] or "").split()) if cells and cells[0][2] else 0
            nsh = len(ql("SELECT shard FROM main.sense_shard WHERE gate = ?", g)) if g else 0
            laid.append("%s: %d sense rows, %d sense shards" % (w, nsense, nsh))
        print("lecture: %d doc sentences spoken to the brain; the lesson words defined: %s" % (n_typed, "; ".join(laid)))
        try: record("lecture", name, None, clean("%d doc sentences; %s" % (n_typed, "; ".join(laid)[:300])))
        except RuntimeError: pass
        return
    if cmd in ("problems", "test", "quiz"):
        import random
        key = wn_key(); words = lesson_words()
        pool = words if cmd == "problems" else [w for w in sorted(key) if w not in words]
        picks = []
        for w in random.sample(pool, min(k, len(pool))):
            (sense, exs, sid) = random.choice(key[w]); picks.append((w, random.choice(exs), sense))
        if cmd == "quiz":
            picks = []
            for w in random.sample(words, min(3, len(words))):
                v = key[w]
                if len(v) >= 2: (s1, e1, i1), (s2, e2, i2) = v[0], v[1]; picks.append((w, "%s and %s" % (e1[0], e2[0]), "%s|%s" % (s1, s2)))   # two senses in one sentence
                picks.append((w, "the %s of it" % w, "?"))   # a context no example holds
        rows = []; correct = ambiguous = 0
        for (w, sentence, sense) in picks:
            a = learner_sense_of_use(w, sentence); got = a["senses"]
            if cmd == "quiz" and "|" in sense: mark = "both" if all(x in got for x in sense.split("|")) else ("one" if any(x in got for x in sense.split("|")) else "incorrect")
            elif sense == "?": mark = "no answer, honest" if not got else "answered %s on an unseen context" % ",".join(got)
            elif got == [sense]: mark = "correct"; correct += 1
            elif sense in got: mark = "ambiguous"; ambiguous += 1
            else: mark = "incorrect"
            rows.append("%s | %s | brain: %s | key: %s | %s" % (w, sentence[:60], ",".join(got) or "none (shard %s)" % a["shard"], sense, mark))
            cx_put("lessonmark", name, a["run"] or int(time.time()), a["run"] or 0, clock(), json.dumps({"cmd": cmd, "word": w, "sentence": sentence, "brain": got, "key": sense, "mark": mark, "ts": int(time.time())}))
        print("%s on %s, %d items:" % (cmd, name, len(picks)))
        for r in rows: print("  " + r)
        if cmd != "quiz": print("score: %d correct, %d ambiguous, %d incorrect of %d" % (correct, ambiguous, len(picks) - correct - ambiguous, len(picks)))
        try: record(cmd, name, None, clean("%d items: %d correct, %d ambiguous" % (len(picks), correct, ambiguous)))
        except RuntimeError: pass
        return
    if cmd == "reteach":
        # another way: for the words marked incorrect, the brain is given another context of the word (a different example of the same word, not the key's sense), then new problems on those words
        key = wn_key(); marks = [json.loads(v) for (n, run, at, ts, v) in cx_list("lessonmark", name) if json.loads(v).get("mark") == "incorrect"]
        words = sorted(set(m["word"] for m in marks))
        if not words: print("nothing to re-teach: no word marked incorrect"); return
        for w in words:
            for (sense, exs, sid) in key[w]:
                for e in exs[:2]:
                    try: ask_learner("type main " + e)
                    except Exception: pass
            try: ask_learner("type main define : %s" % w)
            except Exception: pass
        print("re-taught another way: %s (their examples spoken as uses, then defined again); now new problems on them:" % ", ".join(words))
        import random; picks = []
        for w in words:
            (sense, exs, sid) = random.choice(key[w]); picks.append((w, random.choice(exs), sense))
        correct = 0; rows = []
        for (w, sentence, sense) in picks:
            a = learner_sense_of_use(w, sentence); got = a["senses"]; mark = "correct" if got == [sense] else ("ambiguous" if sense in got else "incorrect"); correct += mark == "correct"
            rows.append("%s | %s | brain: %s | key: %s | %s" % (w, sentence[:60], ",".join(got) or "none", sense, mark))
            cx_put("lessonmark", name, a["run"] or int(time.time()), a["run"] or 0, clock(), json.dumps({"cmd": "reteach", "word": w, "sentence": sentence, "brain": got, "key": sense, "mark": mark, "ts": int(time.time())}))
        for r in rows: print("  " + r)
        print("score after re-teaching: %d correct of %d; still incorrect: %s" % (correct, len(picks), ", ".join(w for (w, s, se), r in zip(picks, rows) if r.endswith("incorrect")) or "none"))
        return
    raise SystemExit("senses plan|lecture|problems|reteach|test|quiz [--n k]")
