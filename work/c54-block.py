# ---- C54 (the owner, 11-04 16:4x: i thought the sources were transcribed in full into mini source dbs, so they have a sql prompt the mother pasted to and hit enter): the cortex
#      sources as source dbs behind the mother. One attached db, cx.db (the kernel allows ten attachments; the sixth and the eight kernel sources hold nine, the guesser's slot
#      freed: the owner took the guesser out 10-31), holding every cortex source with its own symbol gate in cx.me; the corpus rows carry the sentence, its path and line;
#      a request is a row in cx.inbox (a word, or a pair "a b", one source or all); the work trigger answers into cx.outbox; the carry trigger hands each return to mother,
#      which lays it as a return run under the asking run with its src row; the brain keeps the pointer and re-cuts the text from the source row at read (C27). ----
CX_SCHEMA = """CREATE TABLE IF NOT EXISTS me (source TEXT PRIMARY KEY, gate INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS corpus (id INTEGER PRIMARY KEY, source TEXT NOT NULL, word TEXT NOT NULL, hw TEXT, text TEXT NOT NULL, path TEXT, line INTEGER);
CREATE INDEX IF NOT EXISTS corpus_word ON corpus (word); CREATE INDEX IF NOT EXISTS corpus_source ON corpus (source);
CREATE TABLE IF NOT EXISTS words (word TEXT NOT NULL, id INTEGER NOT NULL, source TEXT NOT NULL); CREATE INDEX IF NOT EXISTS words_word ON words (word);
CREATE TABLE IF NOT EXISTS inbox (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, about INTEGER, word TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, about INTEGER, text TEXT, src INTEGER, source TEXT);
CREATE TRIGGER IF NOT EXISTS work_word AFTER INSERT ON inbox WHEN instr(NEW.word, ' ') = 0 BEGIN
  INSERT INTO outbox (run, cell, about, text, src, source) SELECT NEW.run, NEW.cell, NEW.about, c.text, c.id, c.source FROM words w JOIN corpus c ON c.id = w.id WHERE w.word = NEW.word AND (NEW.source IS NULL OR c.source = NEW.source) ORDER BY c.id LIMIT 24;
  DELETE FROM inbox WHERE id = NEW.id; END;
CREATE TRIGGER IF NOT EXISTS work_pair AFTER INSERT ON inbox WHEN instr(NEW.word, ' ') > 0 BEGIN
  INSERT INTO outbox (run, cell, about, text, src, source) SELECT NEW.run, NEW.cell, NEW.about, c.text, c.id, c.source FROM corpus c WHERE c.id IN (SELECT id FROM words WHERE word = substr(NEW.word, 1, instr(NEW.word, ' ') - 1)) AND c.id IN (SELECT id FROM words WHERE word = substr(NEW.word, instr(NEW.word, ' ') + 1)) AND (NEW.source IS NULL OR c.source = NEW.source) ORDER BY c.id LIMIT 24;
  DELETE FROM inbox WHERE id = NEW.id; END;
CREATE TRIGGER IF NOT EXISTS carry AFTER INSERT ON outbox BEGIN
  SELECT mother('INSERT INTO main.secondary (run, cell, gate, about, text, src) VALUES (?, ?, ?, ?, ?, ?)', NEW.run, NEW.cell, (SELECT gate FROM me WHERE source = NEW.source), NEW.src, NEW.text, NEW.src);
  DELETE FROM outbox WHERE id = NEW.id; END;"""
def cx_db_path():
    d = os.environ.get("CORTEX_SRCDIR") or (os.path.join(HOME, "cortex", "nk-new", "sources") if PORT == 7010 else os.path.join(HOME, "cortex", "nk", "sources"))
    return os.path.join(d, "cx.db")
def cx_db():
    import sqlite3
    p = cx_db_path(); new = not os.path.exists(p); c = sqlite3.connect(p, timeout=60)
    if new: c.executescript(CX_SCHEMA); c.commit()
    return c
def source_symbol(name): return "src_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
def source_gate(name):
    # the source's own symbol in the brain (born once), its gate kept in cx.me so a return carries it as its arrival
    sym = source_symbol(name); rows = q("SELECT gate FROM main.label WHERE symbol = ?", sym)
    if not rows:
        try: typed(sym)
        except RuntimeError: pass
        rows = q("SELECT gate FROM main.label WHERE symbol = ?", sym)
    if not rows: raise SystemExit("the source symbol %s has no gate" % sym)
    g = rows[0][0]; q("INSERT OR REPLACE INTO cx.me (source, gate) VALUES (?, ?)", name, g); return g
def source_is_db(nm):
    try: return bool(source_info(nm).get("db"))
    except Exception: return False
def source_holds_gate(nm, g):
    if source_is_db(nm): return cx_get("sword", nm, text_key(sym_of(g)))
    return cx_get("gate", nm, g)
def source_holds_pair(nm, a, b):
    if source_is_db(nm): return cx_get("spair", nm, text_key("%s %s" % (sym_of(a), sym_of(b))))
    return cx_get("pair", nm, pair_key(a, b))
def source_db_type(name, items, quiet=False):
    # items: (sentence, path, line); the sentences into cx.db (corpus and words), the word and pair keys into the index; nothing typed into the brain
    t0 = time.time(); c = cx_db(); cur = c.cursor(); n_typed = dupes = noise = 0; words_seen, pairs_seen = {}, {}
    for (sent, path, line) in items:
        if is_noise(sent): noise += 1; continue
        k = text_key(sent)
        if cx_get("source", name, k): dupes += 1; continue
        cw = [w for w in re.findall(r"[a-z][a-z0-9_']+", sent.lower()) if w not in STOP]
        if not cw: noise += 1; continue
        cur.execute("INSERT INTO corpus (source, word, text, path, line) VALUES (?, ?, ?, ?, ?)", (name, cw[0], sent, path, line)); sid = cur.lastrowid
        cur.executemany("INSERT INTO words (word, id, source) VALUES (?, ?, ?)", [(w, sid, name) for w in sorted(set(cw))])
        cx_put("source", name, k, 0, clock(), json.dumps({"db": sid, "path": path, "line": line}) if path else json.dumps({"db": sid}))
        for w in set(cw): words_seen[w] = words_seen.get(w, 0) + 1
        for (a, b) in zip(cw, cw[1:]): pairs_seen["%s %s" % (a, b)] = pairs_seen.get("%s %s" % (a, b), 0) + 1
        n_typed += 1
        if n_typed % 2000 == 0:
            c.commit()
            if not quiet: print("  %d into the db, %.0f s" % (n_typed, time.time() - t0), flush=True)
    c.commit(); c.close()
    for w, cnt in words_seen.items():
        k = text_key(w); had = cx_get("sword", name, k); d = json.loads(had[3]) if had else {"n": 0}; d["n"] = d.get("n", 0) + cnt; cx_put("sword", name, k, 0, 0, json.dumps(d))
    for pr, cnt in pairs_seen.items():
        k = text_key(pr); had = cx_get("spair", name, k); d = json.loads(had[3]) if had else {"n": 0}; d["n"] = d.get("n", 0) + cnt; cx_put("spair", name, k, 0, 0, json.dumps(d))
    had = cx_get("source", name, 0); d = json.loads(had[3]); d["db"] = True; d["db_lines"] = d.get("db_lines", 0) + n_typed; cx_put("source", name, 0, had[0], had[1], json.dumps(d)); _SRCD.pop(name, None)
    g = source_gate(name)
    if not quiet: print("source %s into cx.db: %d sentences, %d words keyed, %d pairs keyed, %d repeats, %d noise, gate %d, %.1f s; the brain run count did not grow" % (name, n_typed, len(words_seen), len(pairs_seen), dupes, noise, g, time.time() - t0))
    return n_typed
def v_source_db(name, band, text, domain, path=None, globs=None, from_brain=False, raw=None):
    ensure_cx()
    if not cx_get("source", name, 0):
        if not text: raise SystemExit("register the source first: cortex source %s owner|reference --db : <what it is>" % name)
        v_source(name, band or "reference", text, domain or ["software"])
    items = []
    if from_brain:
        # the migration: a source typed as lines into the brain replayed from its runs into cx.db; the typed runs stay as history
        rows = q("SELECT n, run, value FROM main.cx WHERE kind = 'source' AND name = ? AND n > 0 AND run > 0 LIMIT 400000", name)
        for (n, run, v) in rows:
            try: d = json.loads(v) if v and v.startswith("{") else {}
            except ValueError: d = {}
            if d.get("db"): continue
            t = line_text(run)
            if t: items.append((t, d.get("path"), d.get("line")))
            if len(items) % 5000 == 0 and items: print("  %d replayed" % len(items), flush=True)
        print("source %s: %d lines replayed from the brain" % (name, len(items)))
    elif path:
        root = os.path.abspath(os.path.expanduser(path)); had = cx_get("source", name, 0); d = json.loads(had[3]); d["path"] = root; cx_put("source", name, 0, had[0], had[1], json.dumps(d)); _SRCD.pop(name, None)
        for f in code_files(root, globs):
            rel = os.path.relpath(f, root)
            for (ln, para) in file_paragraphs(f):
                plines = [x.lower() for x in para.splitlines()]
                for sent in sentences(para):
                    head = sent.lower()[:25]; off = next((i for i, x in enumerate(plines) if head in x), 0); items.append((sent, rel, ln + off))
    else:
        for sent in sentences(raw if raw is not None else sys.stdin.read()): items.append((sent, None, None))
    return source_db_type(name, items)
def db_rows_of(name, sids):
    if not sids: return {}
    c = cx_db(); out = {}
    for (sid, text, path, line, src) in c.execute("SELECT id, text, path, line, source FROM corpus WHERE id IN (%s)" % ",".join(str(int(s)) for s in sids)): out[sid] = (text, path, line, src)
    c.close(); return out
def v_ask_source(name, word, run=None):
    # cortex ask-source <name|all> <word or 'a b'> [--run R]: the request written into cx.inbox under run R; the returns read back as the return runs under R, each with its src row
    ensure_cx(); c = cx_db(); c.close()
    if run is None:
        r = typed("cortex ask %s : %s" % (name, word)); run = r["run"]
    gates = {row[1]: row[0] for row in q("SELECT source, gate FROM cx.me")}
    before = set(t["id"] for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3)
    q("INSERT INTO cx.inbox (run, cell, about, word, source) VALUES (?, 24, 0, ?, %s)" % ("NULL" if name == "all" else "?"), *( [run, word] if name == "all" else [run, word, name]))
    time.sleep(0.3)
    kids = [t for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3 and t["id"] not in before]   # the return runs: arrival = the source's gate, about = the src row (the cortex contract; the kernel's define puts the asked gate there)
    made = {t["id"]: int(t.get("about") or 0) for t in kids}
    got = db_rows_of(name, [v for v in made.values() if v])
    print("ask-source %s %r under run %d: %d returns laid as return runs (the brain keeps the pointer, the text re-cut from the source row at read)" % (name, word, run, len(kids)))
    out = []
    for t in kids[:12]:
        sid = made.get(t["id"]); meta = got.get(sid) if sid else None
        line = "return run %d arrival %s (%s) src %s %s: %s" % (t["id"], t.get("arrival"), gates.get(t.get("arrival"), "?"), sid, ("%s:%s" % (meta[1], meta[2])) if meta and meta[1] else "", (t.get("text") or (meta[0] if meta else ""))[:140]); out.append(line); print("  " + line)
    return out
def v_source_migrate_all(box_min=120):
    # every reference source typed as lines moved into cx.db (the owner sources stay as lines: the designer's record in the brain); one source at a time, a line per source
    t0 = time.time(); done = []
    for (nm, band) in sources():
        if band != "reference" or source_is_db(nm): continue
        if time.time() - t0 > box_min * 60: print("box of %d min reached" % box_min); break
        n = v_source_db(nm, None, None, None, from_brain=True); done.append((nm, n))
    print("migrated %d sources into cx.db in %.0f s: %s" % (len(done), time.time() - t0, ", ".join("%s %d" % x for x in done)))

def db_lines_holding(nm, words, limit=3):
    # the corpus rows of a db source holding every word given (a word or a pair), with path and line
    c = cx_db(); ws = [w for w in words if w]
    if not ws: c.close(); return []
    sql = "SELECT c.id, c.text, c.path, c.line FROM corpus c WHERE c.source = ? " + " ".join("AND c.id IN (SELECT id FROM words WHERE word = ?)" for w in ws) + " ORDER BY c.id LIMIT %d" % limit
    rows = list(c.execute(sql, [nm] + ws)); c.close(); return rows
def source_confirms_text(nm, text, pairs_words):
    # C28 for a db source: the corpus rows sharing at least half of the claim's pairs, compared word for word: the same words = confirm; the same but a value or a negation = disagree
    cand = {}
    for (a, b) in pairs_words:
        for (sid, t, p, l) in db_lines_holding(nm, [a, b], 6): cand[sid] = t
    cw = content_words(text) | set(numbers(text)); out = {"confirm": [], "disagree": []}
    for sid, t in list(cand.items())[:40]:
        tw = content_words(t) | set(numbers(t)); diff = (cw ^ tw)
        if not diff: out["confirm"].append(nm)
        elif diff and all(re.match(r"^\d", x) or x in NEG_WORDS or x in TIME_WORDS for x in diff) and len(cw & tw) >= max(3, len(cw) // 2): out["disagree"].append({"source": nm, "line": t[:160], "differs": sorted(diff)})
    return out
