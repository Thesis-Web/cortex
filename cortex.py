#!/usr/bin/env python3
# cortex.py (2026-11-02): the Cortex front door on hp2. One file, stdlib only. The brain (nk on 127.0.0.1:7007) stores; jev judges; this code
# decides by the truth table in CORTEX-HANDLER.md section 7; a worker (claude -p / codex exec) works one turn on the hydration and nothing else.
# Every Cortex record is a line typed at the brain's main prompt under its key line (typemark): the encoder files it at its arrival in the project's
# tree (key up, receipt down, a repeat one more time cell: nk.c, 11-11); the door reads the tree by key. No index table, no log table, no timer, no sweep.
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

# ---- the record in the brain (the door plan, 2026-11-10; the owner 11-03: storage is inside the graph; 11-10: a repeat is a cell changed, like a file tree) ----
# No index table. A project is a tree of memories the encoder files at every line's arrival under a key (the kernel's typemark door, nk.c 11-11):
# the project line is the root (its receipt cell lists its keys), a key line `<kind> <name> [n]` points up (key) and down (receipt), and a record
# line under a key carries the keys it was recorded under (key) and when (time), one entry per arrival (the ten newest per key: the hippocampus).
# The door types a record as `typemark main <key line> @<time> | <line>` and, the first time, the key under its project line (file_line);
# it reads the tree by key with q (run_memory by the line's gates, run_sheet by run and cell, seq and label to decode) and decides nothing.
TEXT_KINDS = ("project", "checkpoint", "expected")
LINE_KINDS = ("project", "checkpoint", "expected", "state", "ingest", "receipt", "need", "prove", "schedule", "question", "remainder", "source")
DERIVED = ("restate", "line", "receipts", "voice", "vgate", "paired", "keyed", "pair", "spair", "sword", "gate", "states", "jevwhy", "jevdep", "jevretract")
FACT_EXCLUDE = ("sheet.receipt_cmds", "sheet.receipt_newest", "sheet.ground.by_source", "sheet.pair_ground.held_by", "ground.by_source")
_GATE, _TEXT, _MEM, _CELL, _KEYS, _RECS, _ROWS, _NAMES = {}, {}, {}, {}, {}, {}, {}, {}
def forget():
    # after a write: what the door held of the tree in this process is read again
    _MEM.clear(); _CELL.clear(); _KEYS.clear(); _RECS.clear(); _ROWS.clear(); _NAMES.clear(); _SAID.clear()
def kernel_cut(text):
    # the kernel's own cut (nk.c letter_len): a word is a run of letters or underscores in any script; every other character is a symbol of its own
    out, cur = [], ""
    for ch in text:
        o = ord(ch)
        if (ch.isalpha() or ch == "_") if o < 0x80 else (not (0x80 <= o <= 0xBF) and not (0x2000 <= o <= 0x207F)): cur += ch
        else:
            if cur: out.append(cur); cur = ""
            out.append(ch)
    if cur: out.append(cur)
    return out
def gate_sym(s):
    if s not in _GATE:
        rows = q("SELECT gate FROM main.label WHERE symbol = ?", s); _GATE[s] = rows[0][0] if rows else 0
    return _GATE[s]
def gates_text(text):
    gs = [gate_sym(s) for s in kernel_cut(text)]
    return None if (not gs or 0 in gs) else " ".join(str(g) for g in gs)
def mem_of_text(text):
    # the newest memory whose line is exactly this text (run_memory by the line's gates, a keyed read); 0 when no line of these words was ever heard
    if text not in _MEM:
        gs = gates_text(text); rows = q("SELECT run FROM main.run_memory WHERE input = ?", gs) if gs else []
        _MEM[text] = rows[0][0] if rows else 0
    return _MEM[text]
def cell_list(run, cell):
    # a list cell of a memory's sheet (key, receipt, time, the index lists): the numbers it holds, in order
    k = (run, cell)
    if k not in _CELL:
        rows = q("SELECT value FROM main.run_sheet WHERE run = ? AND cell = ? AND state = 1", run, cell)
        v = rows[0][0] if rows and rows[0][0] is not None else ""
        _CELL[k] = [int(x) for x in str(v).split() if x.lstrip("-").isdigit()]
    return _CELL[k]
def decode(run):
    # a memory's line read back through the label (the owner, 11-03: words do not live in the brain; the space is a gate too, so the replay is exact)
    if run not in _TEXT:
        rows = q("SELECT group_concat(symbol, '') FROM (SELECT l.symbol AS symbol FROM main.seq s JOIN main.label l ON l.gate = s.gate WHERE s.run = ? ORDER BY s.pos)", run)
        _TEXT[run] = (rows[0][0] or "") if rows else ""
    return _TEXT[run]
def typemark(marker, text, ts=None):
    r = ask("typemark main %s%s | %s" % (marker, (" @%d" % int(ts)) if ts else "", text))
    if "error" in r: raise RuntimeError("brain refused: " + r["error"])
    return r
_FILED = set()
def file_line(kind, name, n, line, ts=None, root=None, value=None, kl=None):
    # one record through the encoder: the line under its key line. The key line is heard as the marker, so it is always a memory of its own; the first
    # time, the key is filed under its project line and the project under the root of roots (project projects, project sources). A repeat of the
    # line under the key is one more time in its cells; a line that is a learned line with a few other values is that memory's arrival (its number
    # is the memory + arrival * 2^32 and reads back as its own line).
    kl = kl or key_line(kind, name, key_n(kind, n, value)); pl = "project " + (root or name); under = "project sources" if kind == "source" else "project projects"
    r = typemark(kl, line, ts); forget()
    if kl != pl and (pl, kl) not in _FILED:
        p = mem_of_text(pl)
        if not p or p not in cell_list(r["marker"], gate_sym("key")): typemark(pl, kl, ts); forget()
        _FILED.add((pl, kl))
    if (under, pl) not in _FILED:
        p, u = mem_of_text(pl), mem_of_text(under)
        if p and (not u or u not in cell_list(p, gate_sym("key"))): typemark(under, pl, ts); forget()
        _FILED.add((under, pl))
    return r
def key_n(kind, n, value=None):
    # the N of a key: a checkpoint or hand-back number (0 < n < 100000); else the value's own n; else none
    if n is not None and 0 < n < 100000: return n
    if isinstance(value, dict) and isinstance(value.get("n"), int) and 0 < value["n"] < 100000: return value["n"]
    return None
def key_line(kind, name, n): return "%s %s%s" % (kind, name, (" %d" % n) if n is not None else "")
def safe_line(text):
    # one line, the span mark never opened by a value (BUILD is the brain's build mark)
    return re.sub(r"\s+", " ", str(text).replace("BUILD", "build")).strip()
def record(kind, name, n, body, root=None, ts=None):
    # one record: the line under its key (file_line); a repeat of a sentence makes no new memory, only one more entry in its key and time cells
    # (the owner, 11-10: a repeat is a cell changed)
    line = safe_line(body)
    if isinstance(n, int) and n >= 100000 and kind not in ("ingest", "receipt", "source", "verdict"): line = fact_line(kind, {"_n": n, "value": line})   # the record's own number (a run), which the key line does not carry
    r = file_line(kind, name, n, line, ts, root)
    return (r.get("same_as") or r.get("run")), clock(), r
def prune(v, path=""):
    # the fields the plan does not keep (copies of other records, counts derived from the sources) are left out
    if isinstance(v, dict): return {k: prune(x, (path + "." + str(k)).lstrip(".")) for k, x in v.items() if (path + "." + str(k)).lstrip(".") not in FACT_EXCLUDE}
    return v
def fact_line(kind, value):
    # a record whose value had fields: one line through the encoder, the kind word then the value as it is (one line of JSON: the types are
    # exact and the line reads back as it was typed; starting with the kind word it never begins with a tool word)
    return kind + " " + json.dumps(prune(value), ensure_ascii=False)
def cx_put(kind, name, n, run, at, value, ts=None):
    # a value with fields becomes a fact line under the key; a plain value was the line itself (typed by record); a derived kind is never typed
    if kind in DERIVED or kind in ("ingest", "receipt"): return
    if isinstance(value, str) and value and value[:1] in "{[":
        try: d = json.loads(value)
        except ValueError: return
        if d == {}: return
        if kind == "source" and isinstance(d, dict) and "db" in d and not d.get("band"): return   # a db row: cx.db holds it with its path and line
        if isinstance(d, dict) and isinstance(n, int) and key_n(kind, n) is None and "_n" not in d: d = dict(d, _n=n)   # the record's own number, when the key line does not carry it
        if kind == "source" and n == 0 and isinstance(d, dict): file_line(kind, name, n, fact_line(kind, d), ts, kl="project " + name); return   # a source's own description: a record of its root
        file_line(kind, name, n, fact_line(kind, d), ts, value=d if isinstance(d, dict) else None)
    elif kind not in LINE_KINDS and value not in (None, ""):
        file_line(kind, name, n, fact_line(kind, str(value)), ts)
def parse_fact(kind, text):
    # the value of a fact line: what follows the kind word, read as it was written; a line that is not one gives None
    if not text.startswith(kind + " ") or text[len(kind) + 1:len(kind) + 2] not in ("{", "[", '"'): return None
    try: return json.loads(text[len(kind) + 1:])
    except ValueError: return None
def root_of(name): return mem_of_text("project " + name)
KEY_RE = re.compile(r"^([a-z]+) (\S+)(?: (\d+))?$")
VOICE_RE = re.compile(r"^(voice|guess) (\S+)(?: (\S+))?$")
_SAID = {}
def said_of(name):
    # (memory, time) -> who said it, and the set that were guesses: read from the voice and guess keys of the project
    if name not in _SAID:
        who, guess = {}, set()
        for (kd, x), k in keys_of(name)[0].items():
            if kd not in ("voice", "guess"): continue
            for (m, text, times) in records_of(k):
                for t in times:
                    if kd == "voice": who[(text, t)] = x
                    else: guess.add((text, t))
        _SAID[name] = (who, guess)
    return _SAID[name]
def keys_of(name):
    # the project's keys from its root's receipt: (kind, n) -> the key memory; a line in the receipt that is not a key is the project's own record
    if name not in _KEYS:
        d, extra = {}, []; root = root_of(name)
        for (k, t, _times) in (records_of(root) if root else []):
            m = KEY_RE.match(t); vm = VOICE_RE.match(t)
            if vm and vm.group(2) == name: d[(vm.group(1), vm.group(3))] = k   # voice <name> <who>, guess <name>: who said a line of the project, and that it was a guess
            elif m and m.group(2) == name and m.group(1) != "project": d[(m.group(1), int(m.group(3)) if m.group(3) else None)] = k
            elif re.match(r"^project \S+$", t): continue   # a root listed under this root (project projects, project sources)
            else: extra.append(k)
        _KEYS[name] = (d, extra)
    return _KEYS[name]
def ints(v): return [int(x) for x in str(v).split() if x.lstrip("-").isdigit()] if v is not None else []
def records_of(keyrun):
    # the memories under a key, each with the times it was recorded under it (one per arrival kept), in the order they were filed. One read: the
    # key's receipt cell, and for each memory in it its key and time cells and its line through the label (every find inside is by key)
    if keyrun not in _RECS:
        out = []; kc, tc, fc, rc = gate_sym("key"), gate_sym("time"), gate_sym("formula"), gate_sym("receipt")
        cell = lambda run, c: "( SELECT value FROM main.run_sheet WHERE run = %s AND cell = %d AND state = 1 )" % (run, c)
        sql = ("WITH rs ( i , run ) AS ( SELECT j.key , CAST ( j.value AS INTEGER ) FROM json_each ( '[' || replace ( coalesce ( %s , '' ) , ' ' , ',' ) || ']' ) j ) "
               "SELECT rs.run , %s , %s , %s , ( SELECT group_concat ( symbol , '' ) FROM ( SELECT l.symbol AS symbol FROM main.seq s JOIN main.label l ON l.gate = s.gate WHERE s.run = rs.run ORDER BY s.pos ) ) FROM rs ORDER BY rs.i"
               % (cell(keyrun, rc), cell("rs.run", kc), cell("rs.run", tc), cell("rs.run", fc) if fc else "NULL")) if rc and kc and tc else None
        for (m, kv, tv, fv, text) in (q(sql) if sql else []):
            ks, ts = ints(kv), ints(tv); text = text or ""; _TEXT[m] = text
            idx = [i for i, k in enumerate(ks) if k == keyrun and i < len(ts)]
            if fv is not None:
                # a formula: each arrival under this key is its own line (the learned line with that arrival's values), read back by the arrival's number
                by = {}
                for i in idx:
                    h = m | ((i + 1) << 32); t = decode(h); e = by.setdefault(t, [m if t == text else h, []]); e[1].append(ts[i])
                for t, (h, times) in by.items(): out.append((h, t, times))
            else: out.append((m, text, [ts[i] for i in idx] or [0]))
        _RECS[keyrun] = out
    return _RECS[keyrun]
def NK_MEM(run): return run & 0xffffffff   # the memory of a record's number (an arrival of a formula is the memory + arrival * 2^32)
def old_line(kind, name, text):
    # the old typed form of a record line, `cortex <kind> [<name>] [<n>] : <body>`: (its number or None, its body); a bare line is itself
    m = re.match(r"^cortex %s(?: %s)?(?: (\d+))? : (.*)$" % (re.escape(kind), re.escape(name)), text, re.S)
    return ((int(m.group(1)) if m.group(1) else None), m.group(2)) if m else (None, text)
def body_of(kind, name, text): return old_line(kind, name, text)[1]
MANY = ("schedule", "ask", "lesson", "retire", "lecture", "plan", "problems", "reteach", "test", "quiz")   # kinds whose every line is a record of its own under one key
def identity(kind, n, body, d, ln=None):
    # the old index's n of a record: a text hash for a sentence; a record with fields carries its own number (_n) when its key line does not; else
    # the key's n; else the number the old typed line names; a kind whose every line is its own record: the line's text hash; else 0 (one record)
    if kind in ("ingest", "receipt", "source"): return text_key(body) if body else 0
    if isinstance(d, dict) and "_n" in d: return int(d["_n"])
    if n is not None: return n
    if d is None and ln is not None: return ln
    if d is None and kind in MANY: return text_key(body) if body else 0
    return 0
def rows_under(kind, name, items, extra):
    # the records of the kind under these keys (and, for a project or a source, the root's own records) as the old index gave them: identity -> (n, run, at, ts, value)
    rows = {}; groups = [(n, records_of(krun)) for (n, krun) in items]
    if kind == "project" and extra: groups.append((0, [(m, decode(m), [0]) for m in extra if parse_fact("source", decode(m)) is None]))
    if kind == "source" and extra: groups.append((0, [(m, decode(m), cell_list(m, gate_sym("time")) or [0]) for m in extra if isinstance(parse_fact("source", decode(m)), dict)]))   # a source's own description: a record of its root
    for (n, recs) in groups:
        for (m, text, times) in recs:
            d = parse_fact(kind, text) if kind not in TEXT_KINDS else None
            ln, body = (None, None) if d is not None else old_line(kind, name, text)
            if kind == "project" and d is not None: continue
            ident = identity(kind, n, body, d, ln)
            ts = max(times) if times else 0
            if d is not None:
                value = d if isinstance(d, str) else d["value"] if (isinstance(d, dict) and set(d) == {"_n", "value"}) else json.dumps({k: v for k, v in d.items() if k != "_n"} if isinstance(d, dict) else d)
                row = (ident, m, m, ts, value)
                prev = rows.get(("f", ident))
                if not prev or (ts, NK_MEM(m)) >= (prev[3], NK_MEM(prev[1])): rows[("f", ident)] = row
            else:
                if kind == "ingest":
                    who, gs = said_of(name); value = json.dumps({"t": body, "times": len(times), "voice": who.get((text, ts), "hand"), "guess": bool(GUESS.search(body)) or (text, ts) in gs})
                elif kind in ("question", "need", "remainder") : value = None   # the line of a kind whose record is its fact line: the fact row carries it
                else: value = body
                if value is None: continue
                row = (ident, m, m, ts, value)
                prev = rows.get(("t", ident))
                if not prev or (ts, NK_MEM(m)) >= (prev[3], NK_MEM(prev[1])): rows[("t", ident)] = row
    if kind not in LINE_KINDS and any(k[0] == "f" for k in rows): rows = {k: v for k, v in rows.items() if k[0] == "f"}
    return rows
def cx_rows(kind, name):
    # every record of the kind under the project as the old index gave it: (n, run, at, ts, value); a kind with fields gives its newest fact line per identity, a sentence its text and times
    key = (kind, name)
    if key not in _ROWS:
        keys, extra = keys_of(name)
        items = [(n, k) for (kd, n), k in keys.items() if kd == kind]
        if kind == "project": items = []
        _ROWS[key] = sorted(rows_under(kind, name, items, extra).values(), key=lambda r: (r[3], r[1]))
    return _ROWS[key]
def row_of(kind, name, n):
    # one record by the old index's (kind, name, n), found by its key when the key line names it (the address, not a search of the kind): (run, at, ts, value)
    keys, extra = keys_of(name); want = n if n is not None else 0
    if kind == "source" and want == 0:
        for r in rows_under(kind, name, [], extra).values():
            if r[0] == 0: return r[1:]
    k = keys.get((kind, n)) if n else None
    if k is not None:
        for r in rows_under(kind, name, [(n, k)], None).values():
            if r[0] == want: return r[1:]
    for r in reversed(cx_rows(kind, name)):
        if r[0] == want: return r[1:]
    return None
_VOICES = {}
_IDX = {}
def tree_count():
    # the record tree's size in one keyed read: the roots under project projects, their keys, the distinct records under the keys (what the old index rows counted)
    pr = mem_of_text("project projects")
    if not pr: return (0, 0, 0)
    rc = gate_sym("receipt")
    lst = lambda run: "'[' || replace ( coalesce ( ( SELECT value FROM main.run_sheet WHERE run = %s AND cell = %d AND state = 1 ) , '' ) , ' ' , ',' ) || ']'" % (run, rc)
    sql = ("WITH ps ( run ) AS ( SELECT CAST ( j.value AS INTEGER ) FROM json_each ( %s ) j ) , ks ( run ) AS ( SELECT CAST ( j.value AS INTEGER ) FROM ps , json_each ( %s ) j ) "
           "SELECT ( SELECT count ( * ) FROM ps ) , ( SELECT count ( * ) FROM ks ) , ( SELECT count ( DISTINCT j.value ) FROM ks , json_each ( %s ) j )") % (lst(pr), lst("ps.run"), lst("ks.run"))
    try: r = q(sql); return tuple(int(x or 0) for x in r[0]) if r else (0, 0, 0)
    except RuntimeError: return (0, 0, 0)
INDEX_KINDS = ("checkpoint", "expected", "ingest", "receipt", "source")
def index_of(name):
    # the judge's word index read from the brain itself: the project's record runs are the tree (root receipt -> keys -> their receipts), their
    # gates are the kernel's own seq; the content gates after the line's prefix (words not in STOP, negations kept, digits as values), per gate
    # the lines holding it with the first and last, per adjacent word pair the lines and the first (what the old index kept as rows)
    if name in _IDX: return _IDX[name]
    root = root_of(name); gates, pairs = {}, {}
    if root:
        rc = gate_sym("receipt"); colon = gate_of(":")
        stop = " , ".join("'%s'" % w for w in sorted(STOP) if w not in NEG_WORDS)
        ks = [k for (kd, n), k in keys_of(name)[0].items() if kd in INDEX_KINDS]   # the keys whose lines the old index kept by word: the sentences, not the fact lines
        if not ks: _IDX[name] = (gates, pairs); return _IDX[name]
        tree = ("WITH ks ( run ) AS ( VALUES %s ) , "
                "rs ( run ) AS ( SELECT DISTINCT CAST ( j.value AS INTEGER ) FROM ks , json_each ( '[' || replace ( coalesce ( ( SELECT value FROM main.run_sheet WHERE run = ks.run AND cell = %d AND state = 1 ) , '' ) , ' ' , ',' ) || ']' ) j ) , "
                "cp ( run , cpos ) AS ( SELECT q.run , min ( q.pos ) FROM rs JOIN main.seq q ON q.run = rs.run WHERE q.gate = %d GROUP BY q.run ) , "
                "c ( run , pos , gate , s ) AS ( SELECT q.run , q.pos , q.gate , l.symbol FROM rs JOIN main.seq q ON q.run = rs.run JOIN main.label l ON l.gate = q.gate LEFT JOIN cp ON cp.run = q.run WHERE q.pos > coalesce ( cp.cpos , 0 ) AND ( ( l.symbol GLOB '[0-9]*' AND l.symbol NOT GLOB '*[^0-9]*' ) OR ( length ( l.symbol ) >= 2 AND l.symbol GLOB '*[A-Za-z]*' AND l.symbol NOT IN ( %s ) ) ) )") % (" , ".join("( %d )" % k for k in ks), rc, colon, stop)
        try:
            for (g, n, first, last) in q(tree + " SELECT gate , count ( DISTINCT run ) , min ( run ) , max ( run ) FROM c GROUP BY gate"): gates[g] = (n, first, last)
            for (x, y, n, first) in q(tree + " , w ( run , pos , gate ) AS ( SELECT run , pos , gate FROM c WHERE NOT ( s GLOB '[0-9]*' AND s NOT GLOB '*[^0-9]*' ) ) , p ( run , a , b ) AS ( SELECT run , gate , lead ( gate ) OVER ( PARTITION BY run ORDER BY pos ) FROM w ) SELECT a , b , count ( DISTINCT run ) , min ( run ) FROM p WHERE b IS NOT NULL GROUP BY a , b"): pairs[(x, y)] = (n, first)
        except RuntimeError as e: sys.stderr.write("index of %s not read: %s\n" % (name, str(e)[:120]))
    _IDX[name] = (gates, pairs); return _IDX[name]
def index_row(name, g, pair=False):
    # the old gate and pair rows (first, times, last; a, b, first, times), read from the brain by index_of
    gates, pairs = index_of(name)
    if pair:
        a, b = g >> 20, g & 1048575; r = pairs.get((a, b))
        if not r: return None
        n, first = r; return (first, first, 0, json.dumps({"a": a, "b": b, "first": first, "times": n}))
    r = gates.get(g)
    if not r: return None
    n, first, last = r; return (first, first, 0, json.dumps({"first": first, "times": n, "last": last}))
def cx_list(kind, name, desc=False, limit=1000):
    rows = sorted(cx_rows(kind, name), key=lambda r: r[0], reverse=desc)
    return rows[:limit]
def cx_names(kind):
    # the names that hold the kind: the project roots (under project projects) or the source roots (under project sources), each read by key
    if kind not in _NAMES:
        out = []
        root = root_of("sources" if kind == "source" else "projects")
        for k in (cell_list(root, gate_sym("receipt")) if root else []):
            m = re.match(r"^project (\S+)$", decode(k))
            if m and (kind == "source" or kind == "project" or any(kd == kind for (kd, n) in keys_of(m.group(1))[0])): out.append(m.group(1))
        _NAMES[kind] = sorted(set(out))
    return _NAMES[kind]
def states_row(name, n):
    # the history of a checkpoint's state: every record under state <name> <n> in time order (the plan: every run in its history is recorded under the key)
    keys, extra = keys_of(name); krun = keys.get(("state", n))
    if not krun: return None
    hist = []
    for (m, text, times) in records_of(krun):
        for t in times: hist.append({"state": body_of("state", name, text), "run": m, "at": m, "ts": t})
    hist.sort(key=lambda h: (h["ts"], h["run"]))
    return (hist[-1]["run"], hist[-1]["at"], hist[-1]["ts"], json.dumps(hist)) if hist else None
def clock():
    return q("SELECT n FROM main.clock")[0][0]
def cxq(sql, *params):
    # the old index's reads answered from the tree: SELECT <cols> FROM record WHERE kind .. AND name .. [AND n|run|ts ..] [ORDER BY ..] [LIMIT ..]; a write is nothing (the neuron files)
    ps = list(params); m = re.match(r"SELECT (.+?) FROM record WHERE (.+?)(?: ORDER BY (\w+)( DESC| ASC)?)?(?: LIMIT (\S+))?$", sql.strip(), re.S)
    if not m: return []
    def val(tok):
        tok = tok.strip()
        if tok == "?": return ps.pop(0)
        if tok.startswith("'"): return tok.strip("'")
        return int(tok)
    cols = [c.strip() for c in m.group(1).split(",")]; f = {}
    for c in [c.strip() for c in m.group(2).split(" AND ")]:
        cm = re.match(r"(\w+)\s*(>=|<=|=|>|<|IN)\s*(.+)$", c)
        if not cm: continue
        k, op, v = cm.groups()
        if op == "IN": f[(k, "IN")] = [x.strip().strip("'") for x in v.strip("()").split(",")]
        else: f[(k, op)] = val(v)
    order, desc, limit = m.group(3), (m.group(4) or "").strip() == "DESC", m.group(5)
    limit = (ps.pop(0) if limit == "?" else int(limit)) if limit else None
    kinds = f.get(("kind", "IN")) or [f[("kind", "=")]]
    names = [f[("name", "=")]] if ("name", "=") in f else cx_names(kinds[0])
    out = []
    for kind in kinds:
        for nm in names:
            one = None
            if ("n", "=") in f and kind not in DERIVED:
                r1 = row_of(kind, nm, f[("n", "=")]); one = [((f[("n", "=")],) + tuple(r1))] if r1 else []
            for (n, run, at, ts, value) in (one if one is not None else cx_rows(kind, nm)):
                ok = True
                for (k, op), v in f.items():
                    if k in ("kind", "name"): continue
                    x = {"n": n, "run": run, "at": at, "ts": ts}[k]
                    ok = ok and {"=": x == v, ">": x > v, "<": x < v, ">=": x >= v, "<=": x <= v}[op]
                if ok: out.append({"n": n, "run": run, "at": at, "ts": ts, "value": value, "name": nm})
    if order: out.sort(key=lambda r: (r[order], r["run"]), reverse=desc)
    if limit is not None: out = out[:limit]
    if cols == ["count(*)"]: return [(len(out),)]
    return [tuple(r[c] for c in cols) for r in out]
_VOICES = {}
def voice_table():
    # C25, C31 as a reading of the record: every voice's claims, confirmed, false, guesses (and per project, per word) from the newest verdict of each judged run; nothing stored
    if "t" not in _VOICES:
        V, G = {}, {}
        for nm in projects():
            newest = {}
            for (run, m, at, ts, v) in cx_rows("verdict", nm):
                d = jload(v); newest[run] = (ts, d)
            for run, (ts, d) in newest.items():
                vc = d.get("voice", "hand"); by = d.get("judge") if d.get("judge") in ("receipt", "shape", "sources") else "judgment"
                oc = outcome_of(d.get("kind"), by, bool(d.get("guess")))
                t = V.setdefault(vc, {"claims": 0, "confirmed": 0, "false": 0, "guesses": 0, "by_project": {}}); t["claims"] += 1
                bp = t["by_project"].setdefault(nm, {"claims": 0, "confirmed": 0, "false": 0, "guesses": 0}); bp["claims"] += 1
                if oc: t[oc] += 1; bp[oc] += 1
                if oc in ("confirmed", "false"):
                    for g in set(x for x in content_gates(run) if not is_value(x)):
                        e = G.setdefault((vc, g), {"confirmed": 0, "false": 0}); e[oc] += 1
        _VOICES["t"] = (V, G)
    return _VOICES["t"]
def cx_get(kind, name, n):
    if kind == "states": return states_row(name, n)
    if kind == "gate": return index_row(name, n)
    if kind == "pair": return index_row(name, n, pair=True)
    if kind == "voice":
        V, G = voice_table(); d = V.get(name); return (0, 0, 0, json.dumps(d)) if d else None
    if kind == "vgate":
        V, G = voice_table(); e = G.get((name, n)); return (0, 0, 0, json.dumps(e)) if e else None
    if kind == "receipts": return (0, 0, 0, json.dumps(receipts_tree(name, n)))
    if kind == "restate":
        if ("restate", name) not in _ROWS:
            _ROWS[("restate", name)] = {wordset_key(jload(value).get("t", "")): (run, at, ts, str(k)) for (k, run, at, ts, value) in cx_rows("ingest", name)}
        return _ROWS[("restate", name)].get(n)
    if kind in DERIVED: return None
    return row_of(kind, name, n)   # (run, at, ts, value), as the old index answered
def receipts_tree(name, n):
    # the prints of a checkpoint from the tree: every record under receipt <name> <n>, grouped by its command (the part before =>); per command the
    # newest print's lines first, each print's lines in the order they were typed (a line printed again stays with its first print), the newest
    # print and sixty lines before it
    keys, extra = keys_of(name); krun = keys.get(("receipt", n)); rc = {}
    if not krun: return rc
    by = {}
    for i, (m, text, times) in enumerate(records_of(krun)):
        body = body_of("receipt", name, text); cmd = body.split(" => ", 1)[0] if " => " in body else "command"
        by.setdefault(cmd, []).append((min(times), i, m))
    for cmd, ls in by.items():
        newest = max(t for (t, i, m) in ls); ls.sort(key=lambda x: (-x[0], x[1]))
        got = [x for x in ls if x[0] == newest]; old = [x for x in ls if x[0] != newest][:60]
        rc[cmd] = {"ts": newest, "lines": [{"run": m} for (t, i, m) in got + old]}
    return rc

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
    text = re.sub(r"\*\*|__|~~", "", text)                                   # emphasis marks are markup, not words (C10.1)
    text = re.sub(r"(?m)^[ \t]*(?:#{1,6}|[-*\u2022]|\d{1,2}[.)])[ \t]+", "", text)   # a heading or bullet mark in front of a sentence
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
NEG_WORDS = set("not no never none nothing nor cannot without".split())
def content_words(s):
    return set(w for w in re.findall(r"[a-z][a-z0-9']{2,}", s.lower()) if w not in STOP)
NOISE_START = ("$ ", "> ", "❯", "#!", "{", "}", "[", "]", "|", "<", "```", "diff --git", "index ", "+++", "---", "traceback", "file \"")
def is_noise(s):
    # why a line is not a sentence of the state: a command, a path, code, data, or too few words; None when it is a sentence
    t = s.strip()
    if any(t.startswith(p) for p in NOISE_START): return "command-or-markup"
    if "://" in t: return "url"
    toks = t.split(); filey = [x for x in toks if ("/" in x and re.search(r"\w/|/\w", x)) or re.match(r"^[\w.-]+\.(txt|py|sh|md|db|json|log|html|c|h|so|map|jsonl|service)$", x)]
    if toks and toks[0] in filey: return "path"
    if len(filey) >= 2 and len(content_words(" ".join(x for x in toks if x not in filey))) < 4: return "path"   # C10.1: a sentence that names two paths among its words is a sentence
    if (re.search(r"\b(jq|curl|ssh|grep|sed|awk|python3|bash|git|sudo|systemctl|cortex)\s+-", t) or t.endswith(("{", "}", ";", "\\"))) and not (len(content_words(t)) >= 6 and OBS.search(t)): return "code"   # C10.4 (11-04 23:5x): a prose claim that names its command with a flag (cortex questions cortex --answered printed ...) is a sentence; a bare command line is code
    nonspace = [c for c in t if not c.isspace()]
    if not nonspace: return "empty"
    letters = sum(c.isalpha() for c in nonspace)
    if letters / len(nonspace) < 0.6 and not (len(content_words(t)) >= 2 and re.search(r"\d", t) and letters / len(nonspace) >= 0.3): return "symbols"   # C10.3: a line mostly of numbers that names two words is an observation (the hp builder, 11-04)
    if len(content_words(t)) < 2: return "too-few-words"
    return None
def wordset_key(s):
    return int(hashlib.sha256(" ".join(sorted(content_words(s) | set(numbers(s, clock=True)))).encode()).hexdigest()[:15], 16)
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
def run_words(run):
    # C59 (the owner, 11-05 18:21: ' is a neuron, . is a neuron, - is a neuron, " is a neuron; why does it need to split the run? those are just runs inside a run):
    # the words of a typed line as the encoder laid them, each word the gates between two space neurons, every piece kept (marks, digits, one-letter pieces); gates, no text
    if not _COLON: _COLON.append(gate_of(":"))
    gs = shape_of(run); i = gs.index(_COLON[0]) + 1 if _COLON[0] in gs else 0
    out, cur = [], []
    for g in gs[i:] + [None]:
        if g is None or not (sym_of(g) or "").strip():
            if cur: out.append(tuple(cur)); cur = []
        else: cur.append(g)
    return out
_ENC_DROPPED = {}
def enc_cells(run, others):
    # C59 side by side, not deciding until the owner retires the cut: the line's neurons and its words (runs inside the run) against the other runs (expected, checkpoint, scope);
    # the neurons the regex cut (content_words) throws away; counts in the cell, the dropped symbols only printed (C17: no text in the index)
    W = run_words(run); P = [g for w in W for g in w]; c = {"neurons": len(P), "words": len(W)}
    for k, r in others.items():
        if not r: continue
        ow = run_words(r); c["shared_" + k] = len(set(P) & set(g for w in ow for g in w)); c["words_" + k] = len(set(W) & set(ow))
    fd = content_words("".join(sym_of(g) for g in shape_of(run))); lost = []
    for w in W:
        whole = "".join(sym_of(g) for g in w).lower(); carried = [f for f in fd if f in whole]
        lost += [sym_of(g) for g in w if not any(sym_of(g).lower() in f for f in carried)]
    c["cut_drops"] = len(lost); _ENC_DROPPED[run] = lost
    return c
def content_gates(run):
    # the gates after the line's prefix (cortex <kind> <name> [n] :) that carry content, in order: words not in STOP, and digits (value gates)
    if not _COLON: _COLON.append(gate_of(":"))
    gs = shape_of(run); i = gs.index(_COLON[0]) + 1 if _COLON[0] in gs else 0
    out = []
    for g in gs[i:]:
        s = sym_of(g)
        if s and (s.isdigit() or (len(s) >= 2 and (s not in STOP or s in NEG_WORDS) and any(c.isalpha() for c in s))): out.append(g)   # C26: a negation changes the meaning, it stays in the shape
    return out
def is_value(g): return sym_of(g).isdigit()
_TXT = {}
def line_text(run):
    # the sentence of a run, replayed from its gates (the owner, 11-03: words do not live in the brain; the space is a gate too, so the replay is exact); the body after the typed prefix
    if run not in _TXT:
        r = "".join(sym_of(g) for g in shape_of(run)); _TXT[run] = r.split(" : ", 1)[1] if " : " in r else r
    return _TXT[run]
def receipt_line(l): return line_text(l["run"]).split(" => ", 1)[-1]
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
def pair_key(a, b): return (a << 20) ^ b if a < (1 << 40) else int(hashlib.sha256(("%d,%d" % (a, b)).encode()).hexdigest()[:15], 16)
def pairs_of(run):
    # the adjacent content-gate pairs of a run (words only, digits left out): the hops a reader of the sentence takes between meanings
    ws = [g for g in content_gates(run) if not is_value(g)]
    return list(zip(ws, ws[1:]))
def pair_ground(name, run):
    # per pair of the claim: the sources and projects that hold it; the pairs held nowhere are where the run leaves known ground
    held, memory, none = {}, {}, []
    srcn = [nm for (nm, band) in sources()]; routed = [nm for (nm, band) in routed_sources(name)]; pjs = [pj for pj in projects()]
    for (a, b) in pairs_of(run):
        k = pair_key(a, b)
        who = [nm for nm in srcn if source_holds_pair(nm, a, b)]   # C54: a db source by its pair key
        for nm in who: held[nm] = held.get(nm, 0) + 1
        for pj in pjs:
            had = cx_get("pair", pj, k)
            if had and not (pj == name and json.loads(had[3]).get("first") == run): memory[pj] = memory.get(pj, 0) + 1
        if not who: none.append("%s %s" % (sym_of(a), sym_of(b)))   # held by no source; a project's own ingests are memory, a model's words, never ground
    np_ = len(pairs_of(run))
    agree = sorted([nm for nm, c in held.items() if nm in routed and np_ and c * 2 >= np_])   # C36: agreement is counted over the routed sources   # a source agrees with a claim when it holds at least half of its pairs (C24: the belief row weighs sources agreeing)
    return {"pairs": np_, "held_by": held, "memory": memory, "none": none, "agree": agree, "sources": len(routed), "routed": len(routed) < len(srcn)}
def owner_conflict(run):
    # C26: the owner's lines that share this claim's pairs; one that differs only by a value or a negation is a contradiction to ask about, never a verdict (the owner can be wrong by error)
    owners = [nm for (nm, band) in sources() if band == "owner"]
    if not owners: return None
    cand = {}
    for (a, b) in set(pairs_of(run)):
        for nm in owners:
            had = cx_get("pair", nm, pair_key(a, b))
            if had: cand[int(json.loads(had[3]).get("first", 0))] = nm
    ing = content_gates(run)
    for (r0, nm) in list(cand.items())[:12]:
        if not r0 or r0 == run: continue
        O = content_gates(r0)
        if not O or len(O) < 4: continue
        oa, ob = seq_diff(O, ing); diff = oa + ob
        if not diff: continue
        if value_or_negation_diff(diff):
            return {"source": nm, "run": r0, "line": line_text(r0)[:160], "differs": sorted(set(sym_of(g) for g in diff))}
    return None
def value_or_negation_diff(diff):
    # the two shapes differ only by values (runs of digit gates), time words, or one negation: the same statement with another value or its denial
    if not diff or not all(is_value(g) or sym_of(g) in TIME_WORDS or sym_of(g) in NEG_WORDS for g in diff): return False
    negs = sum(1 for g in diff if sym_of(g) in NEG_WORDS)
    return (negs <= 1) and (negs == 1 or any(is_value(g) for g in diff))
def source_check(run):
    # C28: every source's lines that share this claim's pairs; a near-identical line confirms, one that differs only by a value or a negation disagrees; the sources judge the claim and each other
    confirm, disagree, seen = [], [], set()
    srcs = [nm for (nm, band) in sources()]
    cand = []
    for (a, b) in set(pairs_of(run)):
        for nm in srcs:
            if source_is_db(nm): continue   # a source the db holds is compared by its db lines below (its typed lines are the same sentences)
            had = cx_get("pair", nm, pair_key(a, b))
            if had:
                r0 = int(json.loads(had[3]).get("first", 0))
                if r0 and r0 != run and (nm, r0) not in seen: seen.add((nm, r0)); cand.append((nm, r0))
    for nm in srcs:   # C54: a db source has no runs; its lines are compared by text
        if source_is_db(nm):
            sc0 = source_confirms_text(nm, line_text(run), [(sym_of(a), sym_of(b)) for (a, b) in set(pairs_of(run))])
            for x in sc0["confirm"]:
                if x not in confirm: confirm.append(x)
            for d0 in sc0["disagree"]:
                if d0["source"] not in [d["source"] for d in disagree]: disagree.append(dict(d0, run=0))
    ing = content_gates(run)
    for (nm, r0) in cand[:24]:
        O = content_gates(r0)
        if not O or len(O) < 4: continue
        oa, ob = seq_diff(O, ing); diff = oa + ob
        if not diff:
            if nm not in confirm: confirm.append(nm)
        elif value_or_negation_diff(diff):
            if nm not in [d["source"] for d in disagree]: disagree.append({"source": nm, "run": r0, "line": line_text(r0)[:140], "differs": sorted(set(sym_of(g) for g in diff))})
    return {"confirm": confirm, "disagree": disagree}
# ---- C16 (the owner, 11-03): the grounds. the receipt is the machine's own print piped in; the owner's words and reference material are sources, projects of typed lines;
#      every content gate of a claim is checked against them; a value is settled against the receipt; a gate with no ground is a question the cortex asks, not a guess ----
BANDS = ("owner", "reference")
NUM = re.compile(r"(?<![\w.])\d[\w.%]*")   # a value starts a token: c10.1, c18 and run401 are labels, not values (C17.2)
def numbers(text, clock=False):
    # the value tokens of a sentence (393g, 300, 9%); times and dates (13:19, 11-03) are not values unless the claim is about a clock (C34)
    t = text.lower()
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)   # 2,188 is one number
    t = re.sub(r"\b(\d+)m(\d+(?:\.\d+)?)s\b", lambda m: "%s min %s s" % (m.group(1), m.group(2)), t)   # C35.4: the shell's time print 0m6.114s is 0 min and 6.114 s (the hp builder, 11-04 05:0x)
    t = re.sub(r"(?<![\w.])\d[\w.]*(?:-[\w.]+)+", lambda m: " " if re.search(r"[a-z]", m.group(0)) else m.group(0), t)   # C35.1: 48-2026-11-03-cortex-unattended is a name; 0.20-0.80 stays two values
    if not clock: t = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}-\d{2}\b", " ", t)
    else: t = re.sub(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\b", lambda m: " %s:%s " % (m.group(1), m.group(2)), t)
    t = re.sub(r"`(\d[\w.%]*)`", r" \1 ", t)   # C44c: a backticked number (`6`, `3.0`, `82mb`) is a value; a backticked command is not
    t = re.sub(r"`([a-z_]+=)(\d[\w.%]*)`", r" \1 \2 ", t)   # C47b: a backticked name=number (`exit=2`) carries its value
    t = re.sub(r"`[^`]*`", " ", t); t = re.sub(r"(?<!\S)--?[a-z][\w-]*[ =]\d+(\.\d+)?", " ", t); t = re.sub(r"(?:^|[\s:;])\$ [^;`]*", " ", t)   # C44b: a quoted shell command ($ python3 sum.py 1 2 3) is a command, its digits are arguments   # C22: a command in backticks or a flag's argument (--at 1, -m 300) is not a value
    return [y for y in (x.strip("'\"()[]{}").rstrip(".,;:") for x in (NUM_CLOCK if clock else NUM).findall(t)) if y and VALUE_TOKEN.match(y)]   # quotes and brackets around a number are punctuation
NUM_CLOCK = re.compile(r"(?<![\w.])\d[\w.%:]*")
VALUE_TOKEN = re.compile(r"^(\d+(\.\d+)?[a-z%]{0,3}|\d{1,2}:\d{2}(:\d{2})?)$")   # C35.1: a value is digits, a decimal, a short unit or a clock; 60e27de and 7c20c611 are names, not values
SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9}
UNITS = {"ms": ("t", 1.0), "s": ("t", 1e3), "sec": ("t", 1e3), "secs": ("t", 1e3), "min": ("t", 6e4), "mins": ("t", 6e4), "h": ("t", 3.6e6), "hr": ("t", 3.6e6), "hrs": ("t", 3.6e6),
         "b": ("z", 1.0), "kb": ("z", 1e3), "k": ("z", 1e3), "mb": ("z", 1e6), "m": ("z", 1e6), "gb": ("z", 1e9), "g": ("z", 1e9), "tb": ("z", 1e12), "t": ("z", 1e12)}   # C35: a unit is meaning: the same quantity in another unit is the same value
def num_value(tok, text=""):
    m = re.match(r"^(\d+(?:\.\d+)?)([a-z%]*)$", tok)
    if not m: return None, "", 1.0
    v, unit, scale = float(m.group(1)), m.group(2), 1.0
    if text:
        mm = re.search(r"\b" + re.escape(tok) + r"\s+(thousand|million|billion)\b", text.lower())
        if mm: scale = SCALE[mm.group(1)]; v *= scale; unit = ""
        if not unit:
            mu = re.search(r"\b" + re.escape(tok) + r"\s*(ms|secs?|s|mins?|hrs?|h|kb|mb|gb|tb|b)\b", text.lower())
            if mu: unit = mu.group(1)
    if unit in UNITS: kind, mult = UNITS[unit]; return v * mult, kind, scale * mult
    return v, unit, scale
def rounding_of(tok, printed, text="", ptext=None):
    # the claim's number is a shorter form of a printed one: same unit, fewer kept digits, within half a unit of the last kept digit at the claim's scale (71 for 71.3, 1.8 million for 1796202; 392 is not a rounding of 393)
    v, u, scale = num_value(tok, text)
    if v is None: return None
    dec = len(tok.split(".")[1]) if "." in tok else 0; tol = 0.5 * scale * 10 ** (-dec)
    for pt in printed:
        w, pu, _ = num_value(pt, ptext.get(pt, "") if isinstance(ptext, dict) else "")
        if w is None or (u and pu and u != pu) or w == v: continue
        if len(pt.replace(".", "")) <= len(tok.replace(".", "")) and scale == 1.0: continue   # the print is not longer than the claim: not a rounding
        if abs(w - v) <= tol: return pt
    return None
def same_quantity(tok, printed, text, ptext):
    # C35: the claim's number equals a printed one once both carry their units (11.7 s is 11700 ms; 82 mb is a rounding of 82164 kb)
    v, u, _ = num_value(tok, text)
    if v is None or u not in ("t", "z"): return None
    for pt in printed:
        w, pu, _ = num_value(pt, ptext.get(pt, ""))
        if pu == u and w is not None and abs(w - v) <= 0.5 * (10 ** -(len(tok.split(".")[1]) if "." in tok else 0)) * (v / float(re.match(r"^(\d+(?:\.\d+)?)", tok).group(1)) if float(re.match(r"^(\d+(?:\.\d+)?)", tok).group(1)) else 1): return pt
    return None
CMD_NOISE = set("ssh echo cat bash python3 hp2 tail head cut sed grep awk then done for do fi if else while read printf true false tee sort uniq wc tr xargs".split())
def toks(s):
    return set(w for w in re.findall(r"[a-z][a-z0-9_.-]*", s.lower()) if len(w) >= 2 and w not in STOP and w not in CMD_NOISE)
def is_self_print(cmd):
    return cmd.startswith("cortex ") or "/cortex " in cmd or cmd.startswith("cortex")
_PJ = []
def projects():
    if not _PJ: _PJ.extend(sorted(set(r[0] for r in cxq("SELECT name FROM record WHERE kind = 'project' AND name >= '' AND n = 0"))))
    return _PJ
_SRC = []
def sources():
    if not _SRC:
        for (nm, v) in cxq("SELECT name, value FROM record WHERE kind = 'source' AND n = 0 AND name >= ''"):
            try:
                d = json.loads(v)
                if d.get("retired"): continue   # the owner, 11-04 18:2x: a source typed in breach of the code block grounds nothing; its runs stay as history
                _SRC.append((nm, d.get("band", "reference")))
            except ValueError: pass
        _SRC.append(None)
    return [x for x in _SRC if x]
MEASURES_DEFAULT = {"clock": "date", "tonight": "date", "today": "date", "o'clock": "date",
                    "mem": "free -m", "memory": "free -m", "swap": "free -m",
                    "disk": "df -h /", "avail": "df -h /", "filesystem": "df -h /", "df": "df -h /",
                    "load": "uptime", "uptime": "uptime",
                    "gates": "cortex status", "runs": "cortex status", "hops": "cortex status", "checkpoints": "cortex formula", "ingests": "cortex formula", "verdicts": "cortex formula", "voices": "cortex status", "trust": "cortex status"}
MEASURES_PROJECT = {"neuron": {"runs": "api/info", "gates": "api/info", "hops": "api/info", "defined": "api/info", "refused": "api/info", "queued": "api/info", "points": "api/info", "checkpoints": "cortex formula", "ingests": "cortex formula", "verdicts": "cortex formula", "trust": "cortex status", "voices": "cortex status"}}
def measures(name=None):
    # C34.2 (the hp builder, 11-04 04:4x: the word runs in a neuron sentence made the judge ask for a cortex status print; the two vocabularies collide): a project's own measures first, kept as data
    if name:
        hadp = cx_get("measures", name, 0)
        if hadp:
            try: base = dict(measures()); base.update(json.loads(hadp[3])); return base
            except ValueError: pass
        elif name in MEASURES_PROJECT:
            cx_put("measures", name, 0, 0, clock(), json.dumps(MEASURES_PROJECT[name])); base = dict(measures()); base.update(MEASURES_PROJECT[name]); return base
    had = cx_get("measures", "judge", 0)
    if had:
        try: return json.loads(had[3])
        except ValueError: pass
    cx_put("measures", "judge", 0, 0, clock(), json.dumps(MEASURES_DEFAULT)); return dict(MEASURES_DEFAULT)
DESIGNS_DEFAULT = {"projects": ["cortex", "neuron"], "words": ["neuron", "nexus", "thesis coin", "cortex"],
                   "note": "C37 (the owner, 11-04 03:5x): many of my designs have never been done before in that way; there is no box to classify it against until enough of my design exists to have a grounding reference; the designs are fluid, time and state keep the other attempts"}
def designs():
    had = cx_get("designs", "judge", 0)
    if had:
        try: return json.loads(had[3])
        except ValueError: pass
    cx_put("designs", "judge", 0, 0, clock(), json.dumps(DESIGNS_DEFAULT)); return dict(DESIGNS_DEFAULT)
def own_design(name): return name in (designs().get("projects") or [])
ROUTES_DEFAULT = {"cortex": ["meaning", "belief", "software", "neural", "language", "logic"], "neuron": ["neural", "meaning", "language", "memory", "software", "logic", "encyclopedia"], "audit": ["software"], "probe": ["software"],
                  "note": "C36 (the owner, 11-04 03:5x: adding more sources and the routes for them): a project routes to the domains its claims are about; a source carries its domains; agreement counts the routed sources; an owner source is always routed"}
def routes():
    had = cx_get("routes", "judge", 0)
    if had:
        try: return json.loads(had[3])
        except ValueError: pass
    cx_put("routes", "judge", 0, 0, clock(), json.dumps(ROUTES_DEFAULT)); return dict(ROUTES_DEFAULT)
_SRCD = {}
def source_info(nm):
    if nm not in _SRCD:
        had = cx_get("source", nm, 0)
        try: _SRCD[nm] = json.loads(had[3]) if had else {}
        except ValueError: _SRCD[nm] = {}
    return _SRCD[nm]
def routed_sources(name):
    # C36: the sources whose domains the project routes to, and every owner source; every source when no reference is routed
    want = set(routes().get(name) or [])
    rs = [(nm, b) for (nm, b) in sources() if b == "owner" or (want & set(source_info(nm).get("domain") or []))]
    return rs if any(b == "reference" for (nm, b) in rs) else sources()
def v_sources():
    print("%-44s %-9s %-26s %7s  %s" % ("source", "band", "domains", "lines", "what, where from, as of"))
    for (nm, b) in sources():
        d = source_info(nm); cnt = cxq("SELECT count(*) FROM record WHERE kind = 'source' AND name = ? AND n > 0", nm)[0][0]
        if d.get("db") and not cnt: cnt = (q("SELECT count(DISTINCT k) FROM cx.corpus WHERE source = ?", nm) or [[0]])[0][0]   # a source held only by the db: its lines are the db's
        print("%-44s %-9s %-26s %7d  %s%s%s" % (nm, b, ",".join(d.get("domain") or []) or "-", cnt, (d.get("text") or "")[:100], (" | path " + d["path"]) if d.get("path") else "", (" | db %d lines" % d.get("db_lines", 0)) if d.get("db") else ""))
    dom, nb = {}, {"reference": 0, "owner": 0}
    for (nm, b) in sources():
        nb[b] = nb.get(b, 0) + 1
        for d0 in (source_info(nm).get("domain") or []): dom[d0] = dom.get(d0, 0) + 1
    print("sources: %d (%d reference, %d owner) | per domain: %s" % (len(sources()), nb.get("reference", 0), nb.get("owner", 0), ", ".join("%s %d" % kv for kv in sorted(dom.items(), key=lambda kv: -kv[1]))))
    R = routes(); print("routes: " + "; ".join("%s -> %s" % (k, ",".join(v)) for k, v in R.items() if k != "note") + " | a project routes to domains; agreement counts the routed sources (C36)")
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WD_ABBR = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6}
WHEN_RE = r"\b(?:(?:last |this )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|(?:last |this )(?:mon|tues|tue|wed|thurs|thur|thu|fri|sat|sun))\b"
def windows_of(text, ts):
    # C38 (the owner, 11-04): a weekday, yesterday, today, a date or a clock time in a claim names a window of the graph's own time, resolved against the claim's own time
    import datetime
    low = text.lower(); d0 = datetime.datetime.fromtimestamp(ts); day0 = d0.replace(hour=0, minute=0, second=0, microsecond=0); out = []
    def day(dt, label):
        a = int(dt.timestamp())
        for i, (l0, a0, b0) in enumerate(out):
            if a0 == a: out[i] = (l0 if label in l0 else l0 + ", " + label, a0, b0); return
        out.append((label, a, a + 86399))
    for m in re.finditer(WHEN_RE, low):
        w = m.group(0).split()[-1]; idx = WEEKDAYS.index(w) if w in WEEKDAYS else WD_ABBR[w]; back = (day0.weekday() - idx) % 7 or 7
        day(day0 - datetime.timedelta(days=back), m.group(0).strip())
    if re.search(r"\byesterday\b|\blast night\b", low): day(day0 - datetime.timedelta(days=1), "yesterday")
    if re.search(r"\btoday\b|\btonight\b|\bthis morning\b|\bthis afternoon\b|\bthis evening\b", low): day(day0, "today")
    if re.search(r"\blast week\b", low):
        a = day0 - datetime.timedelta(days=day0.weekday() + 7); out.append(("last week", int(a.timestamp()), int(a.timestamp()) + 7 * 86400 - 1))
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", low):
        try: day(datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))), m.group(0))
        except ValueError: pass
    for m in re.finditer(r"(?<![\d-])(\d{1,2})-(\d{2})(?![\d-])", low):
        try:
            dt = datetime.datetime(d0.year, int(m.group(1)), int(m.group(2)))
            if dt > d0: dt = dt.replace(year=d0.year - 1)
            day(dt, m.group(0))
        except ValueError: pass
    return out[:4]
def timeline_lines(name, t0, t1, limit=400):
    return cxq("SELECT n, run, ts, value FROM record WHERE kind = 'ingest' AND name = ? AND n > 0 AND ts >= ? AND ts <= ? ORDER BY ts LIMIT ?", name, t0, t1, limit)
def timeline_cells(name, run, text, ts):
    # C38: for each window the claim names, the project's own record in it: how many of the claim's words and pairs those lines hold
    wins = windows_of(text, ts or int(time.time()))
    if not wins: return None
    words = set(g for g in content_gates(run) if not is_value(g)); prs = set(pairs_of(run)); out = []
    for (label, t0, t1) in wins:
        rows = [r for r in timeline_lines(name, t0, t1) if r[1] != run]
        held_w, held_p, best = set(), set(), []
        for (k, r0, ts0, v) in rows:
            gs = [g for g in content_gates(r0) if not is_value(g)]; gset = set(gs); hw = words & gset
            if hw: held_w |= hw; best.append((len(hw), r0))
            if prs: held_p |= prs & set(zip(gs, gs[1:]))
        best.sort(reverse=True)
        out.append({"when": label, "t0": t0, "t1": t1, "lines": len(rows), "words": len(words), "words_held": len(held_w), "pairs": len(prs), "pairs_held": len(held_p), "missing": sorted(sym_of(g) for g in words - held_w)[:8], "best": [r0 for (_, r0) in best[:3]]})
    return out
def v_at(name, words):
    # C38 (the owner, 11-04: last tuesday what was the state of neuron): the state of a project at a time of the graph's own, and the lines that held a word
    pr = cx_get("project", name, 0)
    if not pr: raise SystemExit("no project " + name)
    text = " ".join(words); now = int(time.time()); wins = windows_of(text, now)
    rest = re.sub(WHEN_RE + r"|\byesterday\b|\btoday\b|\btonight\b|\blast week\b|\b\d{4}-\d{2}-\d{2}\b|(?<![\d-])\d{1,2}-\d{2}(?![\d-])", " ", text.lower())
    terms = [w for w in re.findall(r"[a-z][a-z0-9']+", rest) if w not in STOP]
    if not wins and not terms: raise SystemExit("cortex at <project> <when> [word]: a weekday, yesterday, today, a date, or a word")
    if not wins: wins = [("all time", 0, now)]
    for (label, t0, t1) in wins:
        print("AT %s, %s (%s to %s):" % (name, label, time.strftime("%Y-%m-%d %H:%M", time.localtime(t0)) if t0 else "the first line", time.strftime("%Y-%m-%d %H:%M", time.localtime(t1))))
        snaps = cxq("SELECT value FROM record WHERE kind = 'formula' AND name = ? AND n > 0 AND ts <= ? ORDER BY n DESC LIMIT 1", name, t1)
        if snaps:
            sn = json.loads(snaps[0][0]); cps = sn["checkpoints"]
            done = sorted(int(k) for k, c in cps.items() if c["state"] == "done"); work = sorted(int(k) for k, c in cps.items() if c["state"] == "working"); opn = sorted(int(k) for k, c in cps.items() if c["state"] == "open")
            print("  as of the formula snapshot %s: %d checkpoints, %d done%s%s; %d ingests, %d verdicts" % (time.strftime("%m-%d %H:%M", time.localtime(sn["ts"])), len(cps), len(done), ("; working " + " ".join("C%d" % x for x in work)) if work else "", ("; open " + " ".join("C%d" % x for x in opn)) if opn else "", sn["ingests"], sn["verdicts"]))
        else:
            regd = [n for (n, run, at, ts, text0) in cx_list("checkpoint", name) if ts <= t1]
            print("  no formula snapshot before then; %d checkpoints registered by then" % len(regd))
        by_state, changes = {}, []   # C42: the state at the window's end from each checkpoint's own history, and the changes inside the window
        for (cn, crun, cat, cts, ctext) in cx_list("checkpoint", name):
            h = state_at(name, cn, t1)
            if h: by_state.setdefault(h["state"], []).append(cn)
            had_h = cx_get("states", name, cn)
            if had_h:
                for e in json.loads(had_h[3]):
                    if t0 <= e.get("ts", 0) <= t1: changes.append((e.get("ts", 0), cn, e["state"], e.get("from") or ""))
        if by_state or changes:
            print("  states from the history at the window end: " + "; ".join("%s %s" % (k, " ".join("C%d" % x for x in v)) for k, v in sorted(by_state.items())) + (" | changes in the window: " + ", ".join("C%d %s %s%s" % (cn, st, time.strftime("%m-%d %H:%M", time.localtime(ts0)), " (snapshot)" if fr else "") for (ts0, cn, st, fr) in sorted(changes)[:30]) if changes else " | no state change in the window") + " (C42)")
        rows = timeline_lines(name, t0, t1, 1200); voices = {}
        for (k, r0, ts0, v) in rows:
            try: vc = json.loads(v).get("voice", "hand") if v and v.startswith("{") else "hand"
            except ValueError: vc = "hand"
            voices[vc] = voices.get(vc, 0) + 1
        vk = {}
        for (v,) in cxq("SELECT value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 AND ts >= ? AND ts <= ?", name, t0, t1):
            d = json.loads(v); vk[d.get("kind")] = vk.get(d.get("kind"), 0) + 1
        qs = cxq("SELECT count(*) FROM record WHERE kind = 'question' AND name = ? AND n > 0 AND ts >= ? AND ts <= ?", name, t0, t1)[0][0]
        pa = [json.loads(v) for (v,) in cxq("SELECT value FROM record WHERE kind = 'part' AND name = ? AND n > 0 AND ts >= ? AND ts <= ?", name, t0, t1)]
        acc = [p for p in pa if not (p.get("superseded_by") or p.get("rejected_by"))]; ret = [p for p in pa if p.get("superseded_by") or p.get("rejected_by")]
        print("  lines typed: %d (%s); verdicts: %s; questions asked: %d; parts accepted then and still standing: %d; parts of that time since retired: %d" % (len(rows), ", ".join("%s %d" % kv for kv in sorted(voices.items(), key=lambda kv: -kv[1])) or "none", ", ".join("%s %d" % kv for kv in sorted(vk.items(), key=lambda kv: -kv[1])) or "none", qs, len(acc), len(ret)))
        for p in ret[:6]: print("    retired: C%s run %d (%s) %s: %s" % (p.get("n"), p.get("run"), time.strftime("%m-%d %H:%M", time.localtime(p.get("ts", 0))), ("superseded by run %s" % p["superseded_by"]) if p.get("superseded_by") else "rejected by the owner", line_text(p["run"])[:80]))
        if terms:
            gs = [g for g in (gate_of(w) for w in terms) if g]
            if not gs: print("  word %s: no gate in the brain" % " ".join(terms)); continue
            for g in gs:
                had = cx_get("gate", name, g); d = json.loads(had[3]) if had else None
                print("  word %s in %s: %s" % (sym_of(g), name, ("first run %d, last run %d, %d times" % (d["first"], d["last"], d["times"])) if d else "never"))
            hit = [(ts0, r0) for (k, r0, ts0, v) in rows if all(g in set(content_gates(r0)) for g in gs)]
            print("  lines holding %s in this window: %d of %d read" % (" ".join(sym_of(g) for g in gs), len(hit), len(rows)))
            for (ts0, r0) in hit[-12:]:
                vd = cx_get("verdict", name, r0); d = json.loads(vd[3]) if vd else {}; pt = cx_get("part", name, text_key(line_text(r0))); pd = json.loads(pt[3]) if pt else None
                st = "-" if not pd else ("rejected" if pd.get("rejected_by") == "owner" else ("retired" if (pd.get("superseded_by") or pd.get("rejected_by")) else "part"))
                print("    %s run %d %s %s: %s" % (time.strftime("%m-%d %H:%M", time.localtime(ts0)), r0, (d.get("kind") or "unjudged") if d else "unjudged", st, line_text(r0)[:100]))
def rebuild_voices():
    # the voice rows and the per-word rows recomputed from the newest verdict of every judged run (after a re-judge or a rule change)
    _VOICES.clear(); V, G = voice_table()
    print("voices read from the tree: %d voices over %d verdicts (nothing stored: the verdict lines are the record)" % (len(V), sum(d["claims"] for d in V.values())))
def measure_of(text, name=None):
    # C34: the words of a claim that name a measure, and the prints that settle them (the owner: if date and today had actions, meaning, this would be possible)
    M = measures(name); ws = set(re.findall(r"[a-z][a-z']+", text.lower())); hit = {}
    for w in ws:
        if w in M: hit.setdefault(M[w], []).append(w)
    return hit
def receipts_of(name, n):
    return receipts_tree(name, n)
_SPECN = {}
def spec_numbers(spec):
    # the numbers a project's spec source states, read from its replayed lines (a number is digit gates in the brain, so the gate key cannot hold it whole)
    if spec not in _SPECN:
        out = set()
        for (k, run) in cxq("SELECT n, run FROM record WHERE kind = ? AND name = ? AND n > 0 LIMIT 400", "source", spec):
            if run: out |= set(numbers(line_text(run)))
        _SPECN[spec] = out
    return _SPECN[spec]
def jload(v):
    try: return json.loads(v) if v and v.startswith("{") else {}
    except (ValueError, TypeError): return {}
def ground_cells(name, n, run, text, new_syms):
    # per word gate: which ground holds it (receipt, owner, reference, the project's own memory, none); per number: did the machine print it
    meas = measure_of(text, name); is_clock = "date" in meas
    cells = {"receipt_runs": 0, "receipt_cmds": [], "receipt_before_claim": False, "receipt_newest": "", "receipt_named": False, "numbers_in_ext": [], "numbers": numbers(text, clock=is_clock), "numbers_in": [], "numbers_out": [], "measures": meas, "measure_missing": [], "ground": {"receipt": 0, "owner": 0, "reference": 0, "memory": 0, "none": []}}
    rc = receipts_of(name, n); rnums, rnums_ext, rwords, older = set(), set(), set(), 0; ct = toks(text); ptext = {}; rnums_newer, ptext_newer = set(), {}
    at = run; had_row = cx_get("ingest", name, text_key(text))
    try: at = max(run, int((json.loads(had_row[3]) if had_row and had_row[3] and had_row[3].startswith("{") else {}).get("last") or 0))   # C33d: a claim made again is judged at its newest tick
    except (ValueError, TypeError): at = run
    cells["claim_at"] = at
    for cmd, d in rc.items():
        cells["receipt_cmds"].append(cmd)
        lines_older = [l for l in d.get("lines", []) if l["run"] < at]   # C33b (C33d: at is the claim's newest tick): only a print older than the claim judges it; a later print on the same checkpoint is a label, never a switch
        if lines_older and ((toks(cmd) & ct) or any(toks(cmd) & toks(m0) for m0 in meas)): cells["receipt_named"] = True   # C22: the claim names this print's command, or a measure that print settles (C34)
        cells["receipt_runs"] += len(d.get("lines", [])); older += len(lines_older)
        for l in d.get("lines", []):
            if l["run"] > at:   # C33c: a print newer than the claim never judges it, but the claim can be made again against it
                rl2 = receipt_line(l); nn2 = set(numbers(rl2, clock=is_clock)); rnums_newer |= nn2
                for x in nn2: ptext_newer.setdefault(x, rl2)
        for l in lines_older:
            rl = receipt_line(l); nn = set(numbers(rl, clock=is_clock)); rnums |= nn
            for x in nn: ptext.setdefault(x, rl)
            if not is_self_print(cmd): rnums_ext |= nn   # a cortex print of its own verdicts and parts is circular ground for a sentence about them
            rwords |= set(g for g in content_gates(l["run"]) if not is_value(g))
    if meas:
        cells["measure_missing"] = sorted(m0 for m0 in meas if not any(toks(m0) & toks(c0) for c0 in rc.keys()))   # the measures named with no print of them on this checkpoint
        if cells["measure_missing"] and cells.get("numbers_out"):
            mw = set(w for m0 in cells["measure_missing"] for w in meas[m0]); low = text.lower(); unchecked = []
            for t0 in list(cells["numbers_out"]):
                i = low.find(t0)
                before = set(re.findall(r"[a-z][a-z']+", low[max(0, i - 40):i])) if i >= 0 else set()
                if before & mw: unchecked.append(t0); cells["numbers_out"].remove(t0)   # C35b: this number belongs to the missing print; it is unchecked, not false
            cells["numbers_unchecked"] = unchecked
    if cells["receipt_runs"]:
        cells["receipt_before_claim"] = older > 0   # at least one print the claim could have read
        cells["numbers_in"] = [t for t in cells["numbers"] if t in rnums]; cells["numbers_out"] = [t for t in cells["numbers"] if t not in rnums]
        spec = name + "-repo"   # C47b: the numbers the project's own spec states (the repo source, the owner's voice) are ground; the worker may describe its input
        if cx_get("source", spec, 0) and cells["numbers_out"]:
            held = [t for t in cells["numbers_out"] if t in spec_numbers(spec)]
            if held: cells["numbers_out"] = [t for t in cells["numbers_out"] if t not in held]; cells["numbers_spec"] = held
        cells["numbers_in_ext"] = [t for t in cells["numbers"] if t in rnums_ext]
        cells["numbers_rounded"] = {}
        for t in list(cells["numbers_out"]):
            pt = rounding_of(t, rnums, text, ptext) or same_quantity(t, rnums, text, ptext)
            if pt: cells["numbers_rounded"][t] = pt; cells["numbers_out"].remove(t); cells["numbers_in"].append(t); (cells["numbers_in_ext"].append(t) if (rounding_of(t, rnums_ext, text, ptext) or same_quantity(t, rnums_ext, text, ptext)) else None)   # C22b, C35: a rounding or the same quantity in another unit is the printed value
        cells["numbers_in_newer"] = [t for t in cells["numbers_out"] if t in rnums_newer or rounding_of(t, rnums_newer, text, ptext_newer) or same_quantity(t, rnums_newer, text, ptext_newer)]   # C33c
        cells["receipt_newest"] = " ; ".join("%s => %s" % (cmd, " / ".join(receipt_line(l)[:60] for l in d.get("lines", [])[1:3] or d.get("lines", [])[:1])) for cmd, d in rc.items())
    g = cells["ground"]; new = set(new_syms)
    for w in set(x for x in content_gates(run) if not is_value(x)):
        sym = sym_of(w); held = False
        if w in rwords: g["receipt"] += 1; held = True
        for (src, band) in sources():
            if band in BANDS and source_holds_gate(src, w): g[band] += 1; held = True; g.setdefault("by_source", {}); g["by_source"][src] = g["by_source"].get(src, 0) + 1   # C54: a db source by its word key
        if sym not in new or any(cx_get("gate", pj, w) for pj in projects() if pj != name): g["memory"] += 1; held = True
        if not held: g["none"].append(sym)
    g["none"] = sorted(set(g["none"]))
    return cells
def ground_str(g):
    if not g: return "no ground"
    items = ["%s %d" % (k, g[k]) for k in ("receipt", "owner", "reference", "memory", "timeline") if g.get(k)]
    if g.get("by_source") and len(g["by_source"]) > 1: items.append("(" + " ".join("%s %d" % kv for kv in sorted(g["by_source"].items(), key=lambda kv: -kv[1])[:4]) + ")")
    if g.get("none"): items.append("none: " + ",".join(g["none"]))
    if g.get("of"): items.append("agreement %d of %d" % (g.get("agree", 0), g["of"]))
    if g.get("belief") is not None: items.append("belief %.2f" % g["belief"])
    return " ".join(items) or "no ground"
def v_receipt(name, n, cmd):
    # the machine's own print, piped in (df -h / | cortex receipt audit 1 df -h /): typed as receipt lines and kept as the checkpoint's ground; a model's hand never retypes it
    if not cx_get("checkpoint", name, n): raise SystemExit("no such checkpoint: %s %d" % (name, n))
    lines = [clean(l) for l in sys.stdin.read().splitlines() if clean(l)]
    if not lines: raise SystemExit("receipt: nothing on stdin; pipe the command's output in")
    rc = receipts_of(name, n); got = []; t0 = time.time()
    for l in lines[:80]:
        body = "%s => %s" % (cmd, l)
        try: run, at, r = record("receipt", name, n, body)
        except RuntimeError as e: print("receipt line refused: %s" % e); continue
        got.append({"run": run})
    rc = receipts_of(name, n)   # the newest print first; the older prints of the same command stay on the checkpoint (C47d), so an older claim keeps the print it was made against
    for x in got: print("receipt run %d %s C%d: %s => %s" % (x["run"], name, n, cmd, receipt_line(x)[:100]))
    print("receipt: %d lines typed in %.0f ms; %s C%d has receipts of: %s" % (len(got), (time.time() - t0) * 1000, name, n, ", ".join(sorted(rc))))
def type_receipt(name, n, cmd, lines):
    # a print typed as receipt lines of a checkpoint from a string (the cortex's own check, C47); the same ground as cortex receipt
    rc = receipts_of(name, n); got = []
    for l in [clean(x) for x in lines if clean(x)][:40]:
        body = "%s => %s" % (cmd, l)
        if cx_get("receipt", name, text_key(body)): continue
        try: run, at, r = record("receipt", name, n, body)
        except RuntimeError: continue
        got.append({"run": run})
    return len(got)
def v_check_set(name, n, cmd):
    if not cx_get("checkpoint", name, n): raise SystemExit("no such checkpoint: %s %d" % (name, n))
    cx_put("check", name, n, 0, clock(), json.dumps({"cmd": cmd, "ts": int(time.time())})); print("check of %s C%d: %s" % (name, n, cmd))
def run_check(name, n, cwd=None):
    # C47 (the owner, 11-04: test whether the cortex can hold the line and demand it done correctly, not just done): the cortex's own check run after a turn, in the repo, its print typed as a receipt the worker never touched
    had = cx_get("check", name, n)
    if not had: return None
    cmd = json.loads(had[3]).get("cmd"); cwd = cwd or repo_of(name) or os.path.join(WORKDIR, name)
    try: p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=cwd, timeout=180, env=dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))); out = (p.stdout + ("\n" + p.stderr if p.stderr.strip() else "")).strip()
    except subprocess.TimeoutExpired: out = "check wrong: the check command ran past 180 s"
    lines = [l for l in out.splitlines() if l.strip()] or ["check wrong: the check printed nothing"]
    last = lines[-1]; ok = last.lower().startswith("check ok")
    typed_n = type_receipt(name, n, "the cortex check", lines[-12:])
    cx_put("checklast", name, n, 0, clock(), json.dumps({"ok": ok, "last": last[:400], "ts": int(time.time()), "cmd": cmd}))
    return {"ok": ok, "last": last, "lines": lines, "typed": typed_n}
def close_by_check(name, n, chk):
    # 11-04 16:3x: a checkpoint closed by the cortex own check: the check's last print (check ok ...) becomes its part by receipt, the state moves, the next opens
    rc = receipts_of(name, n).get("the cortex check") or {}; runs = [l["run"] for l in rc.get("lines", [])]
    if runs:
        idx = min(len(runs) - 1, max(0, int(chk.get("typed") or 1) - 1))
        add_part(name, n, runs[idx], "the cortex check printed: " + chk["last"][:200], 1.0, "check", {"receipt": 1})
    if RAIL and not check_audited(name, n):
        print("C%d: check ok, but this check was not written by the exec and audited by another maker (rail C2, C3): not closed" % n); return False
    _CLOSING[0] = True
    try: v_state(name, n, "done")
    finally: _CLOSING[0] = False
    n2 = next_checkpoint(name)
    if n2 is not None and n2 != n:
        s2 = cx_get("state", name, n2)
        if not s2 or s2[3] != "working": v_state(name, n2, "working")
    print("C%d done by the cortex own check (check ok); next C%s" % (n, n2)); return True
def v_check_run(name, n, close=False):
    r = run_check(name, n)
    if r is None: raise SystemExit("no check on %s C%d; set one: cortex check %s %d : <command>" % (name, n, name, n))
    print("check %s C%d: %s | %d receipt lines typed" % (name, n, r["last"][:300], r["typed"]))
    if close and r["ok"]: close_by_check(name, n, r)
    elif close: print("not closed: the check printed check wrong")
# ---- the rail (the owner, 11-09 00:48: ok do it .. you have claude exec on the backside of the cortex .. this could be used to build the tests, or the expected output, and to audit .. thus you are not checking your own work) ----
# C1 only the cortex own check closes a checkpoint; C2 a claude exec turn writes the check, a library program plus variables, never the worker or the liaison;
# C3 a codex exec turn breaks copies of the work without seeing the check, and the check must catch every break and pass the real work twice on fresh inputs;
# C5 a check's citations are read from the source db; C7 a program stored once, a row of variables per checkpoint
RAIL = os.environ.get("CORTEX_RAIL", "on") != "off"
_CLOSING = [False]
CHECKLIB = os.path.join(WORKDIR, "checks", "lib")
RAILDIR = os.path.join(WORKDIR, "rail", "scratch")
AUTHOR_MODEL = os.environ.get("CORTEX_AUTHOR_MODEL", "sonnet")
AUDIT_ENGINE = os.environ.get("CORTEX_AUDIT_ENGINE", "codex")
def met_waits(name, n, why):
    # rail C1: the expected met by <why>; the checkpoint stays working; only the cortex own check closes it
    st = cx_get("state", name, n)
    if st and st[3] == "done": return ""
    if not st or st[3] != "working": v_state(name, n, "working")
    had = cx_get("met", name, n)
    try: m = json.loads(had[3]) if had else []
    except ValueError: m = []
    m.append({"why": why[:200], "ts": int(time.time())}); cx_put("met", name, n, 0, clock(), json.dumps(m[-20:]))
    return " | C%d met by %s; it stays working until the cortex own check prints check ok (rail C1)%s" % (n, why, "" if check_audited(name, n) else "; no audited check yet")
def check_of(name, n):
    had = cx_get("check", name, n)
    try: return json.loads(had[3]) if had else None
    except ValueError: return None
def check_for(name, n):
    # rail C4.1: what a check is written for: the runs of the checkpoint line and its expected line as they stand now
    ck, ex = cx_get("checkpoint", name, n), cx_get("expected", name, n)
    return {"checkpoint": ck[0] if ck else None, "expected": ex[0] if ex else None}
def check_stale(name, n, d=None):
    # rail C4.1: the checkpoint or its expected typed again since the check was written and audited; the check no longer speaks for them.
    # a check written before 11-10 carries no binding: the index rows' times against its audit's time decide
    d = d if d is not None else (check_of(name, n) or {}); a = d.get("audited") or {}
    if not d: return None
    now = check_for(name, n); was = a.get("for") or d.get("for")
    if was: return None if was == now else "the checkpoint or its expected was typed again since the check was written (runs %s, now %s)" % (was, now)
    t = a.get("ts") or d.get("ts") or 0
    for kind in ("checkpoint", "expected"):
        r = cx_get(kind, name, n)
        if r and int(r[2] or 0) > int(t): return "the %s of C%d was typed again (run %d) after the check was audited" % (kind, n, r[0])
    return None
def check_audited(name, n):
    d = check_of(name, n) or {}; a = d.get("audited") or {}
    return bool(a.get("ok")) and a.get("cmd") == d.get("cmd") and not check_stale(name, n, d)
def work_root(name):
    w = repo_of(name) or os.path.join(WORKDIR, name)
    if not os.path.isdir(w): os.makedirs(w, exist_ok=True)   # a work that lives elsewhere (the neuron on hp) gets an empty folder here, so its check runs (rail C4)
    return w
def is_cortex_work(name): return os.path.realpath(work_root(name)) == os.path.realpath(os.path.join(HOME, "cortex"))
def work_copy(name, dst):
    # a copy of the work for the author or the auditor: the git files of the cortex (not the kernel's sources), or the folder's files up to 20 MB each
    src = work_root(name)
    if os.path.exists(dst): shutil.rmtree(dst)
    os.makedirs(dst)
    if not os.path.isdir(src): return dst
    if is_cortex_work(name):
        files = [f for f in subprocess.run(["git", "ls-files"], cwd=src, capture_output=True, text=True).stdout.split("\n") if f and not f.startswith(("nk/", "__pycache__", "brain"))]
    else:
        files = []
        for root, dirs, fs in os.walk(src):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv", "mutants", ".pytest_cache", "target")]
            for f in fs:
                p = os.path.join(root, f)
                try:
                    if os.path.isfile(p) and os.path.getsize(p) <= 20 * 1024 * 1024: files.append(os.path.relpath(p, src))
                except OSError: pass
            if len(files) > 6000: break
    for f in files:
        d = os.path.join(dst, f); os.makedirs(os.path.dirname(d), exist_ok=True)
        try: shutil.copy2(os.path.join(src, f), d)
        except (IsADirectoryError, FileNotFoundError, PermissionError): pass
    return dst
def lib_listing():
    os.makedirs(CHECKLIB, exist_ok=True); out = []
    for f in sorted(os.listdir(CHECKLIB)):
        p = os.path.join(CHECKLIB, f)
        if not os.path.isfile(p): continue
        head = open(p, errors="replace").read(1200).splitlines()
        out.append("- %s: %s" % (f, " ".join(l.lstrip("#").strip() for l in head[:6] if l.startswith("#"))[:400]))
    return "\n".join(out) or "(empty: you write the first program)"
def prog_cmd(name, prog, vars_):
    import shlex
    p = os.path.join(CHECKLIB, prog); pre = "CORTEX_PORT=7010 " if is_cortex_work(name) else ""
    return pre + ("python3 " if prog.endswith(".py") else "bash ") + shlex.quote(p) + " " + shlex.quote(json.dumps(vars_))
def check_print(cmd, cwd):
    # the check run without typing anything: its last line decides, its inputs line is kept
    try:
        p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, cwd=cwd, timeout=240, env=dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")))
        out = (p.stdout + ("\n" + p.stderr if p.stderr.strip() else "")).strip()
    except subprocess.TimeoutExpired: out = "check wrong: the check ran past 240 s"
    lines = [l for l in out.splitlines() if l.strip()] or ["check wrong: the check printed nothing"]
    oks = [l for l in lines if l.lower().startswith(("check ok", "check wrong"))]
    inp = next((l for l in lines if l.lower().startswith("inputs:")), "")
    return {"ok": lines[-1].lower().startswith("check ok"), "last": (oks[-1] if oks else lines[-1])[:400], "inputs": inp[:400]}
def last_json(text, keys):
    dec = json.JSONDecoder(); t = text or ""
    for m in reversed(list(re.finditer(r"\{", t))):
        try: obj, _ = dec.raw_decode(t[m.start():])
        except ValueError: continue
        if isinstance(obj, dict) and any(k in obj for k in keys): return obj
    return None
def cites_not_held(cites):
    # rail C5: every cited row read from the source db; a row that does not hold the cited words refuses the check
    import sqlite3
    bad = []
    if not cites: return bad
    if not isinstance(cites, list): return ["cites is not a list"]
    try: c = sqlite3.connect("file:%s?mode=ro" % cx_db_path(), uri=True, timeout=30)
    except sqlite3.Error as e: return ["the source db did not open: %s" % e]
    for ct in cites[:12]:
        if not isinstance(ct, dict): bad.append("a citation that is not a row: %r" % (ct,)); continue
        try: ln = int(ct.get("line"))
        except (TypeError, ValueError): bad.append("a citation with no line: %r" % (ct,)); continue
        rows = c.execute("SELECT text FROM corpus WHERE source = ? AND line = ?" + (" AND path = ?" if ct.get("path") else ""), (ct.get("source"), ln) + ((ct.get("path"),) if ct.get("path") else ())).fetchall()
        want = [w for w in re.findall(r"[a-z0-9_]+", str(ct.get("words", "")).lower()) if w not in STOP]
        if not rows: bad.append("no row %s %s:%s" % (ct.get("source"), ct.get("path"), ln)); continue
        txt = " ".join(r[0] for r in rows).lower(); miss = [w for w in want if w not in txt]
        if miss or not want: bad.append("row %s %s:%s does not hold %s" % (ct.get("source"), ct.get("path"), ln, ", ".join(miss) or "any cited words"))
    c.close(); return bad
def v_look(words, source=None):
    # rail C5: read only; the rows of the source db that hold a word or a pair
    import sqlite3
    ws = [w.lower() for w in words if w.strip()][:2]
    if not ws: raise SystemExit("look <word> [<word>] [--source s]")
    c = sqlite3.connect("file:%s?mode=ro" % cx_db_path(), uri=True, timeout=30); sf = " AND c.source = ?" if source else ""; extra = (source,) if source else ()
    if len(ws) == 1: rows = c.execute("SELECT c.source, c.path, c.line, c.text FROM words w JOIN corpus c ON c.id = w.id WHERE w.word = ?" + sf + " LIMIT 15", (ws[0],) + extra).fetchall()
    else: rows = c.execute("SELECT c.source, c.path, c.line, c.text FROM words a JOIN words b ON a.id = b.id JOIN corpus c ON c.id = a.id WHERE a.word = ? AND b.word = ?" + sf + " LIMIT 15", (ws[0], ws[1]) + extra).fetchall()
    for (s, p, l, t) in rows: print("%s %s:%s: %s" % (s, p or "-", l, t[:300]))
    print("%d rows (the first 15 at most)" % len(rows)); c.close()
AUTHOR_PROMPT = """You write the cortex's own check for one checkpoint. You are not the worker who builds this project and not the liaison who talks to the owner; you write the test the work must pass. Only the check you leave counts.

PROJECT {NAME}: {SCOPE}
CHECKPOINT C{N}: {CK}
EXPECTED OUTPUT: {EX}
{REPORTED}
This folder is a copy of the work. The cortex will run your check with its working folder set to the real work, and also to broken copies another model makes without seeing your check: your check must pass the real work and fail every broken copy.

THE CHECK LIBRARY ({LIB}) holds check programs stored once, each taking its variables as one JSON argument (read a program before you use it):
{LISTING}

Rules:
1. Use a library program with your own variables when one fits. Write a new program only when none fits, and write it so other checkpoints can use it with other variables: everything particular to this checkpoint comes in through the variables. Save it as ./new-programs/<short_name>.py (python3, standard library only) or .sh; its first lines are # comments saying what it checks and which variables it takes.
2. The check makes its own inputs each run (random values, a fresh temp file, a random pick among the cases) and prints one line starting "inputs:" naming them. Its LAST line starts "check ok:" or "check wrong:" and says what it saw.
3. It checks the EXPECTED OUTPUT by running the work itself (the program, the commands, the verbs) from the working folder with relative paths, never an absolute path to the real work, never by reading what a worker or the record said was done. It never changes the work; temp files it makes it removes. If the work lives outside this folder (a service on a port, another machine, a url), take where it lives in the variable "target": the cortex points target at nothing to see your check print check wrong.
4. {EXTRA}
5. Any behaviour you rely on beyond the EXPECTED OUTPUT itself (what a command prints, a flag, a format, a library call) is cited from a source row you looked up: run   cortex look <word> [<second word>]   (it prints source path:line: text) and put each citation in "cites" as {"source": ..., "path": ..., "line": ..., "words": "<the words of that row you rely on>"}. Cite only rows you saw; the cortex reads every cited row and refuses a check whose row does not hold its words. No citation is needed for what the EXPECTED OUTPUT says itself.
6. Run your check here on this copy before you answer.

Your LAST message is ONE JSON object and nothing after it:
{"program": "<library file name, or new-programs/<name>.py>", "vars": {...}, "cites": [...], "why": "<one line: which wrong versions it catches>"}
or, when no print a machine can make shows this checkpoint's expected output:
{"no_check": "<why, and what the checkpoint would have to say for a machine to check it>"}
or, when the work in this copy does not meet the EXPECTED OUTPUT and your check is right, the check object with one more key:
"work_wrong": "<what the work does instead, as your check printed it>"
"""
MUTANT_PROMPT = """You test a check by breaking the work it checks. You never see the check: do not look for it, for any cortex check or test, or for anything outside this folder.

PROJECT {NAME}: {SCOPE}
CHECKPOINT C{N}: {CK}
EXPECTED OUTPUT: {EX}

This folder is a copy of the work. Make up to three broken versions, the kind a careless or gaming worker would leave: each fails the EXPECTED OUTPUT AS WRITTEN (never a requirement it does not state: no formatting, quoting or wording it does not ask for) in a different, small, plausible way (an off by one, a special case hardcoded for the example, a missing error path, an output format slightly off, a test or data file edited so it passes, a value printed but not computed). Not a crash on start unless that is a real mistake a worker makes. When the work in this folder is a program that talks to a running service (a kernel, a server), break the program in this folder so it prints or sends the wrong thing; an empty list only when nothing in this folder takes part in the expected output.
For each: make ./mutants/m<k>/ a full copy of this folder (everything except ./mutants) with your one change, and write ./mutants/m<k>.txt saying in one line what is wrong in it.
{REPORT}
Your LAST message is ONE JSON object and nothing after it:
{"mutants": [{"dir": "mutants/m1", "wrong": "<one line>"}]{REPORTKEY}}
"""
def fill(t, **kw):
    for k, v in kw.items(): t = t.replace("{" + k + "}", str(v))
    return t
def v_author(name, n, model=None, feedback=None):
    # rail C2: a claude exec turn writes the check of C n on a copy of the work; the cortex installs a new program once, reads the citations, stores the check row
    pr = cx_get("project", name, 0); ck = cx_get("checkpoint", name, n); ex = cx_get("expected", name, n)
    if not ck: raise SystemExit("no checkpoint %s %d" % (name, n))
    model = model or AUTHOR_MODEL; scratch = work_copy(name, os.path.join(RAILDIR, "%s-C%d-author" % (name, n)))
    report = not repo_of(name) and not os.path.isdir(os.path.join(WORKDIR, name, ".git")) and name in ("audit", "probe")
    reported = ""
    if report: reported = "REPORTED (the accepted parts of C%d: for a report this is the thing under test; pass the reported values to your check as variables, never trust them): %s\n" % (n, " | ".join(line_text(p["run"])[:200] for p in parts_of(name, n, 6) if p.get("run")) or "(none)")
    if is_cortex_work(name): extra = "This project's work is the cortex front door itself (cortex.py in this folder) over a brain. Run it as   CORTEX_PORT=7010 python3 cortex.py <verb> ...   from the working folder (the test brain on port 7010; the cortex also sets CORTEX_PORT=7010 for your check). Never use port 7007, the live brain, and never the cortex command on the PATH for the work (it runs the live file; it is only for look). The test brain is a copy of the live one from some days ago: the check reads what the verb prints now on inputs it chooses, not today's run numbers."
    elif report: extra = "This project's work is a report about this machine: the check prints the value fresh and compares it with the reported value, which it takes in the variable \"reported\" (only there; the auditor will change only that variable to wrong reports); a value that moves with time (uptime, free memory, free space) is compared with a tolerance you state, or answer no_check."
    else: extra = "Nothing outside the working folder and your temp files is yours to change."
    prompt = fill(AUTHOR_PROMPT, NAME=name, SCOPE=(pr[3] if pr else "")[:1500], N=n, CK=ck[3], EX=ex[3] if ex else "(none: answer no_check unless the checkpoint text itself names a print)", REPORTED=reported, LIB=CHECKLIB, LISTING=lib_listing(), EXTRA=extra)
    if feedback: prompt += "\nYOUR LAST CHECK OF THIS CHECKPOINT WAS REFUSED: %s\nWrite it again so that this is no longer true (or answer work_wrong or no_check if that is the truth). If a broken version the auditor made is not wrong against the EXPECTED OUTPUT as written, answer instead {\"not_wrong\": \"<which version and why the expected output does not make it wrong>\"}: the owner decides between you and the auditor.\n" % feedback[:1500]
    out, err, rc, secs = worker("claude", model, prompt, scratch, True)
    obj = last_json(out, ("program", "no_check", "not_wrong"))
    if not obj: return {"status": "no answer", "why": "the author gave no JSON object (rc %d): %s" % (rc, (out or err or "")[-300:])}
    if obj.get("not_wrong"): return {"status": "not_wrong", "why": str(obj["not_wrong"])[:600]}
    if obj.get("no_check"): record("checkauthor", name, n, clean("the author claude %s answered no check for C%d: %s" % (model, n, str(obj["no_check"])[:400]))); return {"status": "no_check", "why": str(obj["no_check"])[:600]}
    prog = str(obj.get("program") or ""); vars_ = obj.get("vars") if isinstance(obj.get("vars"), dict) else {}; cites = obj.get("cites") or vars_.get("cites") or []
    installed = None
    if prog.startswith("new-programs/"):
        srcp = os.path.normpath(os.path.join(scratch, prog))
        if not srcp.startswith(scratch) or not os.path.isfile(srcp): return {"status": "refused", "why": "the new program %s is not in the copy" % prog}
        body = open(srcp, errors="replace").read(); prev = (check_of(name, n) or {}).get("installed")   # the program this checkpoint's own last check installed: a rewrite replaces it in place
        for f in sorted(os.listdir(CHECKLIB)):
            if f == prev: continue
            other = open(os.path.join(CHECKLIB, f), errors="replace").read()
            r0 = difflib.SequenceMatcher(None, body, other, autojunk=True).ratio() if abs(len(body) - len(other)) < max(len(body), len(other)) * 0.5 else 0.0
            if r0 >= 0.8: return {"status": "refused", "why": "the new program is %.0f%% the library's %s: use that program with your variables (rail C7: a program is stored once)" % (r0 * 100, f)}
        base = re.sub(r"[^a-z0-9_.-]", "_", os.path.basename(prog).lower()); stem, ext = os.path.splitext(base); k = 2
        if prev and os.path.isfile(os.path.join(CHECKLIB, prev)): base = prev
        else:
            while os.path.exists(os.path.join(CHECKLIB, base)): base = "%s-%d%s" % (stem, k, ext); k += 1
        shutil.copy(srcp, os.path.join(CHECKLIB, base)); prog = installed = base
    if not prog or "/" in prog or not os.path.isfile(os.path.join(CHECKLIB, prog)): return {"status": "refused", "why": "no program %r in the library" % prog}
    bad = cites_not_held(cites)
    if bad: return {"status": "refused", "why": "citations not held by their rows (rail C5): " + "; ".join(bad)[:500]}
    cmd = prog_cmd(name, prog, vars_)
    d = {"cmd": cmd, "program": prog, "vars": vars_, "cites": cites, "why": str(obj.get("why") or "")[:300], "author": "claude:%s" % model, "secs": round(secs), "ts": int(time.time()), "audited": None, "installed": installed, "work_wrong": str(obj.get("work_wrong") or "")[:400] or None, "for": check_for(name, n)}
    cx_put("check", name, n, 0, clock(), json.dumps(d))
    record("checkauthor", name, n, clean("the check of C%d was written by claude %s in %d s with the library program %s%s; it catches: %s" % (n, model, secs, prog, " (new)" if installed else "", d["why"][:200])))
    return {"status": "written", "cmd": cmd, "program": prog, "installed": installed, "cites": len(cites), "work_wrong": d["work_wrong"]}
def v_audit_check(name, n, model=None):
    # rail C3: the check on the real work twice (fresh inputs), then on the broken copies another maker made without seeing it; every copy caught or refused
    d = check_of(name, n)
    if not d: raise SystemExit("no check on %s C%d" % (name, n))
    pr = cx_get("project", name, 0); ck = cx_get("checkpoint", name, n); ex = cx_get("expected", name, n)
    cmd = d["cmd"]; real = work_root(name); probs, killed, survived, maker = [], [], [], None
    r1 = check_print(cmd, real); r2 = check_print(cmd, real)
    if not (r1["ok"] and r2["ok"]): probs.append("your check printed check wrong on the real work: %s (if the work does not meet the expected output, answer with work_wrong)" % (r2 if r1["ok"] else r1)["last"][:300])
    if not r1["inputs"]: probs.append("the check printed no inputs: line")
    elif r1["inputs"] == r2["inputs"]: probs.append("the same inputs twice (%s): the check makes no fresh inputs" % r1["inputs"][:150])
    if not probs:
        scratch = work_copy(name, os.path.join(RAILDIR, "%s-C%d-audit" % (name, n)))
        report = bool(d.get("vars")) and name in ("audit", "probe")
        rep_t = ("This work is a report of values about this machine, the reported value now: %s. Instead of folders, give up to three plausible wrong reports, each as the variable reported only: {\"vars\": {\"reported\": <a wrong report>}}." % json.dumps(d["vars"].get("reported"))[:300]) if report else ""
        prompt = fill(MUTANT_PROMPT, NAME=name, SCOPE=(pr[3] if pr else "")[:1500], N=n, CK=ck[3], EX=ex[3] if ex else "(none)", REPORT=rep_t, REPORTKEY=', "value_mutants": [{"vars": {}, "wrong": "<one line>"}]' if report else "")
        for eng, mdl in ((AUDIT_ENGINE, model or "default"), ("claude", "opus")):
            try: out, err, rc, secs = worker(eng, mdl, prompt, scratch, True)
            except subprocess.TimeoutExpired: out, err, rc, secs = "", "timeout", 1, 0
            obj = last_json(out, ("mutants", "value_mutants")) or {}
            if obj.get("mutants") or obj.get("value_mutants"): maker = "%s:%s" % (eng, mdl); break
        for m in (obj.get("mutants") or [])[:3]:
            dp = os.path.normpath(os.path.join(scratch, str(m.get("dir", ""))))
            if not dp.startswith(scratch + os.sep) or not os.path.isdir(dp): continue
            r = check_print(cmd, dp); (survived if r["ok"] else killed).append("%s (%s): %s" % (m.get("dir"), str(m.get("wrong"))[:140], r["last"][:160]))
        for vm in (obj.get("value_mutants") or [])[:3]:
            if "reported" not in (vm.get("vars") or {}): continue   # a value mutant changes only the reported value, never the check's own variables
            v2 = dict(d.get("vars") or {}); v2["reported"] = vm["vars"]["reported"]; r = check_print(prog_cmd(name, d["program"], v2), real)
            (survived if r["ok"] else killed).append("values %s (%s): %s" % (json.dumps(vm.get("vars"))[:120], str(vm.get("wrong"))[:120], r["last"][:160]))
        # the cortex's own broken version, no model in it: the work absent (an empty folder, and for the cortex's own work a port where no brain answers); the check must print check wrong
        import tempfile
        nd = tempfile.mkdtemp(prefix="rail-absent-"); v0 = dict(d.get("vars") or {}); how = "an empty folder"
        if report: v0["reported"] = ""; how = "an empty report"
        elif "target" in v0: v0["target"] = "127.0.0.1:9"; how = "the target pointed at nothing"
        cmd0 = (prog_cmd(name, d["program"], v0) if os.path.isfile(os.path.join(CHECKLIB, d.get("program") or "-")) else cmd).replace("CORTEX_PORT=7010", "CORTEX_PORT=7099")
        r0 = check_print(cmd0, real if report else nd); shutil.rmtree(nd, ignore_errors=True)
        (survived if r0["ok"] else killed).append("the work absent (%s%s): %s" % (how, ", no brain on the port" if "CORTEX_PORT=7010" in cmd else "", r0["last"][:160]))
        if not maker and not killed and not survived: probs.append("audit failed: no maker made a broken version (%s)" % ((out or err or "")[-200:]))   # the work absent passing the check is a refusal, not a failed audit
        for s in survived: probs.append("a broken version passed your check: %s" % s)
        if not probs: shutil.rmtree(scratch, ignore_errors=True)
    ok = not probs and bool(killed)
    d["audited"] = {"ok": ok, "by": maker or "the work absent only", "strength": "mutants" if maker and len(killed) > 1 else "absent only", "killed": killed, "survived": survived, "real": [r1["last"], r2["last"]], "inputs": [r1["inputs"], r2["inputs"]], "problems": probs, "cmd": cmd, "ts": int(time.time()), "for": d.get("for") or check_for(name, n)}
    cx_put("check", name, n, 0, clock(), json.dumps(d))
    record("checkaudit", name, n, clean("the check of C%d audited by %s: %d broken versions caught, %d passed; on the real work %s and %s%s" % (n, maker or "no maker", len(killed), len(survived), r1["last"][:120], r2["last"][:120], ("; refused: " + "; ".join(probs)[:300]) if probs else "")))
    return {"ok": ok, "by": maker, "killed": killed, "survived": survived, "real": [r1["last"], r2["last"]], "inputs": [r1["inputs"], r2["inputs"]], "problems": probs}
def prove_check(name, n, model=None):
    # rail C2, C3: write and audit the check of C n; audited | work wrong | no check | refused | audit failed, and why
    fb, why = None, ""
    prev = (check_of(name, n) or {}).get("audited") or {}
    if prev and not prev.get("ok") and prev.get("problems") and not any(str(x).startswith("audit failed") for x in prev["problems"]):
        fb = why = "; ".join(prev["problems"])[:1200]   # jev 11-09: a check its last audit refused is written again with the refusal, never audited again as it was (fresh mutants could miss its hole by luck)
    stale = check_stale(name, n)
    if stale and not fb:   # rail C4.1: a check written for an older checkpoint or expected is written again for the one standing now, never audited again as it was
        fb = why = "your last check of this checkpoint is void: %s; write the check for the CHECKPOINT and EXPECTED OUTPUT as they stand now, every part of the expected" % stale
    for attempt in (1, 2):
        d = check_of(name, n) or {}
        if attempt == 2 or fb or not str(d.get("author") or "").startswith(("claude", "codex")):
            a = v_author(name, n, model, fb)
            if a["status"] == "no_check": return "no check", a["why"]
            if a["status"] == "not_wrong": return "disputed", "the author says a broken version of the auditor is not wrong: %s | the auditor: %s" % (a["why"][:300], (fb or "")[:300])
            if a["status"] != "written": fb = why = a.get("why") or "no answer"; continue
            if a.get("work_wrong"):
                r = check_print(check_of(name, n)["cmd"], work_root(name))
                if not r["ok"]: return "work wrong", "%s | the check printed: %s" % (a["work_wrong"], r["last"][:200])
                fb = why = "you said work_wrong but your check printed check ok on the real work: %s" % r["last"][:200]; continue
        au = v_audit_check(name, n)
        if au["ok"]: return "audited", ""
        if any(p.startswith("audit failed") for p in au["problems"]): return "audit failed", "; ".join(au["problems"])[:400]
        fb = why = "; ".join(au["problems"])[:1200]
    return "refused", why
def v_prove(name, n=None, done_only=False, box_min=None, model=None):
    # rail C4: each checkpoint (or the done ones) gets a check written and audited, then run: check ok keeps or closes, check wrong reopens, no check hands back
    t0 = time.time()
    try: sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError): pass
    tally = {}
    for (k, run, at, ts, text) in cx_list("checkpoint", name):
        if n is not None and k != n: continue
        if box_min and time.time() - t0 > box_min * 60: print("prove %s: the box of %d min ran out before C%d" % (name, box_min, k)); break
        st = (cx_get("state", name, k) or (0, 0, 0, "open"))[3]
        if done_only and st != "done": continue
        if st == "done": tally["done before"] = tally.get("done before", 0) + 1
        res, why = ("audited", "") if check_audited(name, k) else prove_check(name, k, model)
        if res == "audited":
            why = "audited by " + str(((check_of(name, k) or {}).get("audited") or {}).get("strength") or "")
            r = run_check(name, k)
            if r and r["ok"]:
                out = "kept" if st == "done" else ("closed" if close_by_check(name, k, r) is not False else "still open")
            else:
                out = "reopened" if st == "done" else "still open"
                if st == "done": v_state(name, k, "working")
                v_need(name, k, "the cortex own check printed: %s" % (r or {}).get("last", "nothing")[:260], who="cortex check"); why = (r or {}).get("last", "")
        elif res == "work wrong":
            out = "reopened" if st == "done" else "still open"
            if st == "done": v_state(name, k, "working")
            v_need(name, k, "the check written by the exec printed on the work: %s" % why[:260], who="cortex check")
        elif res == "audit failed": out = "audit failed (state left as it was)"
        elif res == "disputed":
            out = "disputed, handed back (state left as it was)"
            handback(name, k, "the author and the auditor disagree: %s" % why[:400], {"engine": "claude"})
        else:
            out = "handed back, " + res
            if st == "done": v_state(name, k, "working")
            handback(name, k, ("not yet a checkpoint, no machine print can show its expected: %s" if res == "no check" else "the check could not be written and audited: %s") % why[:300], {"engine": "claude"})
        tally[out] = tally.get(out, 0) + 1
        line = "prove %s C%d (was %s): %s%s" % (name, k, st, out, (" | " + why[:200]) if why else "")
        print(line)
        try: record("prove", name, k, clean(line))
        except Exception as e: print("  (the prove line was not typed: %s)" % e)
    print("prove %s: %s in %.0f s" % (name, ", ".join("%s %d" % kv for kv in tally.items()) or "nothing to prove", time.time() - t0))
    return tally
JEV_VERBS = ("ask", "problog", "mln", "opinion", "why", "retract", "verify", "calibrate", "help")
def jev_brain(verb, text, qs, rules=None, count=True, path=None):
    # jev C4, C5: a request row typed in the judge's brain (cx.judge_jevask: the verb, the file's text, the questions as typed); its trigger runs the verb's rule rows
    # through the mother; the rows the brain wrote for it are read back. Nothing here decides. Returns (rc, lines).
    def lit(x): return "'" + str(x).replace("'", "''").replace("\r", "' || char(13) || '").replace("\n", "' || char(10) || '") + "'"   # the door reads one line
    if not q("SELECT count(*) FROM cx.sqlite_master WHERE type = 'trigger' AND name = 'judge_jevgo'")[0][0] or not q("SELECT count(*) FROM cx.judge_jevrule WHERE verb = %s" % lit(verb))[0][0]:
        print("jev: the judge brain on port %d holds no %s (lay it: CORTEX_PORT=%d python3 work/jev/lay.py %s)" % (PORT, verb, PORT, verb), file=sys.stderr); return 1, None
    cols, vals = ["verb", "state", "qs", "ts"], [lit(verb), lit(text), lit(json.dumps(qs)), "%d" % int(time.time())]
    if rules is not None: cols.append("rules"); vals.append(lit(rules))
    if path is not None: cols.append("path"); vals.append(lit(path))
    r = ask("q INSERT INTO cx.judge_jevask (%s) VALUES (%s) RETURNING id" % (", ".join(cols), ", ".join(vals)))
    if r.get("error") or not r.get("rows"): print("jev: the judge brain: %s" % (r.get("error") or "no request row"), file=sys.stderr); return 1, None
    rid = int(r["rows"][0][0])
    bad = q("SELECT rule, said FROM cx.judge_jevsaid WHERE ask = %d AND said LIKE 'error%%' ORDER BY rule" % rid)
    errs = q("SELECT err FROM cx.judge_jevout WHERE ask = %d AND err IS NOT NULL ORDER BY qi, rowid" % rid)
    for (k, said) in bad: print("jev: the judge brain, request %d, rule %d: %s" % (rid, k, said), file=sys.stderr)
    for (e,) in errs: print("jev: %s" % e, file=sys.stderr)
    if bad: return 1, None
    if errs: return 2, None
    rows = q("SELECT qi, line FROM cx.judge_jevout WHERE ask = %d AND err IS NULL ORDER BY qi" % rid)
    if count and len(rows) != len(qs): print("jev: the judge brain wrote %d answers for %d questions (request %d)" % (len(rows), len(qs), rid), file=sys.stderr); return 1, None
    return 0, [l for (k, l) in rows]
def jev_opt(a, f):
    i = a.index(f) if f in a else -1
    return a[i + 1] if 0 <= i < len(a) - 1 else None
def jev_read(path):
    try:
        with open(path, encoding="utf-8") as fh: return fh.read()
    except OSError as e: print("jev: cannot read %s: %s" % (path, e.strerror), file=sys.stderr); return None
def v_jev_ask(a):
    # jev C4 (re-typed 11-10 on the owner's words, 11-06 14:46: you would be writing code into the judges brain, different brain; 11-09 00:48: it would take
    # zero code outside the db): the ask lives in the judge's brain, judge/judge-jev-ask.sql laid as rows of cx.judge_jevrule (work/jev/lay.py ask) on the live kernel
    # and the test kernel (the owner 11-10: we build live and use what we build .. if the test passed then it should be deployed);
    # this verb only types the request row (the state file's text and the questions as typed) and prints the rows the brain wrote for it; jev.py is not read
    state, qs = jev_opt(a, "--state"), [a[i + 1] for i in range(len(a) - 1) if a[i] == "--q"]
    if not state or not qs: print("cortex jev ask --state <file> --q <id>:<formula> [--q ...]", file=sys.stderr); return 2
    text = jev_read(state)
    if text is None: return 2
    rc, lines = jev_brain("ask", text, qs, path=os.path.abspath(state))   # jev C8: the path:line of a text state's rows
    if rc: return rc
    sys.stdout.write("".join("%s\n" % l for l in lines)); return 0
def v_jev_problog(a):
    # jev C5 (the owner 11-06 14:46 and 11-09 00:48, as the ask): the distribution semantics in the judge's brain, judge/judge-jev-problog.sql laid as rows of
    # cx.judge_jevrule (verb problog; the ask's rules for the question, its tokens and its postfix run by reference, stored once): the clauses the query depends on,
    # every world's least model, p = the summed weight of the worlds where the query holds; this verb only types the request row and prints p=; jev.py is not read
    path, query = jev_opt(a, "--clauses"), jev_opt(a, "--query")
    if not path or not query or not query.strip(): print("cortex jev problog --clauses <file> --query <atom or formula>", file=sys.stderr); return 2
    text = jev_read(path)
    if text is None: return 2
    rc, lines = jev_brain("problog", text, ["query:" + query])
    if rc: return rc
    sys.stdout.write("".join("%s\n" % l for l in lines)); return 0
def v_jev_soft(verb, a):
    # jev C6 (the owner 11-06 14:46 and 11-09 00:48, as the ask): weighted soft rules in the judge's brain. mln (judge/judge-jev-mln.sql): the C5 clauses' worlds
    # weighted by exp(sum w_i n_i(x)), p= of the query; psl (judge/judge-jev-psl.sql): the rules read in Lukasiewicz logic, truth= of the one free atom, the y in
    # [0,1] of the least weighted total of max(0, l_j(y)). This verb only types the request row (the state, the rules, the query) and prints the line; jev.py is not read
    rpath, spath, query = jev_opt(a, "--rules"), jev_opt(a, "--state"), jev_opt(a, "--query")
    if not rpath or not spath or not query or not query.strip():
        print("cortex jev %s --rules <file> --state <file> --query <%s>" % (verb, "atom or formula" if verb == "mln" else "the free atom"), file=sys.stderr); return 2
    rules, text = jev_read(rpath), jev_read(spath)
    if rules is None or text is None: return 2
    rc, lines = jev_brain(verb, text, ["query:" + query], rules)
    if rc: return rc
    sys.stdout.write("".join("%s\n" % l for l in lines)); return 0
def v_jev_opinion(a):
    # jev C7 (the owner 11-06 14:46 and 11-09 00:48, as the ask): each source row a subjective-logic opinion weighted by the trust in its source, fused per atom in the
    # judge's brain (problog's rule 103 discounts and fuses; judge/judge-jev-opinion.sql prints); this verb only types the request row and prints; jev.py is not read
    path = jev_opt(a, "--rows")
    if not path: print("cortex jev opinion --rows <file>", file=sys.stderr); return 2
    text = jev_read(path)
    if text is None: return 2
    rc, lines = jev_brain("opinion", text, [], count=False)
    if rc: return rc
    sys.stdout.write("".join("%s\n" % l for l in lines)); return 0
def v_jev_reason(verb, a):
    # jev C8 (the owner 11-06 14:46 and 11-09 00:48, as the ask): reason maintenance in the judge's brain. why <id>: the record of the id's newest answer, the rows its line
    # depends on with path:line (judge/judge-jev-why.sql); retract <row> [--undo]: the answers whose reasons list the row asked again from the record, without it
    # (judge/judge-jev-retract.sql). This verb only types the request row and prints the brain's lines; jev.py is not read
    args = [x for x in a if not x.startswith("--")]
    if not args: print("cortex jev why <id>" if verb == "why" else "cortex jev retract <row id> [--undo]", file=sys.stderr); return 2
    qs = args if verb == "why" else [args[0]] + (["--undo"] if "--undo" in a else [])
    rc, lines = jev_brain(verb, "", qs, count=False)
    if rc: return rc
    sys.stdout.write("".join("%s\n" % l for l in lines)); return 0
def jev_source_rows(arg):
    # jev C9: the source's rows as they stand, in source order, typed into the request (path, source, line, text); the brain reads and labels, this decides nothing
    import sqlite3
    if not os.path.isfile(arg): return None, "%s is not a file: give a source db (a corpus table with a text column), a JSON list or a text file" % arg
    with open(arg, "rb") as fh: head = fh.read(16)
    if head.startswith(b"SQLite format 3"):
        try:
            c = sqlite3.connect("file:%s?mode=ro" % arg, uri=True, timeout=30)
            cols = {r[1] for r in c.execute("PRAGMA table_info(corpus)")}
            if "text" not in cols: return None, "the source db %s has no corpus table with a text column" % arg
            n = c.execute("SELECT count(*) FROM corpus").fetchone()[0]
            if n > 20000: return None, "the source db %s holds %d rows; at most 20000 are typed into one request" % (arg, n)
            sel = ", ".join(x if x in cols else "NULL" for x in ("path", "source", "line", "text"))
            order = "id" if "id" in cols else "rowid"
            return [dict(zip(("path", "source", "line", "text"), r)) for r in c.execute("SELECT %s FROM corpus ORDER BY %s" % (sel, order))], None
        except sqlite3.Error as e: return None, "the source db %s did not open: %s" % (arg, e)
    text = jev_read(arg)
    if text is None: return None, "cannot read %s" % arg
    try: obj = json.loads(text)
    except ValueError: obj = None
    if isinstance(obj, list):
        rows = []
        for k, x in enumerate(obj):
            if isinstance(x, str): rows.append({"path": arg, "line": k + 1, "text": x})
            elif isinstance(x, dict) and x.get("text") is not None: rows.append({"path": x.get("path") or x.get("source") or arg, "line": x.get("line", k + 1), "text": str(x["text"])})
            else: return None, "source row %d of %s has no text" % (k + 1, arg)
        return rows, None
    return [{"path": arg, "line": i, "text": l} for i, l in enumerate(text.splitlines(), 1) if l.strip()], None
def v_jev_verify(a):
    # jev C9 (the owner 11-06 14:46 and 11-09 00:48, as the ask): claim verification in the judge's brain (judge/judge-jev-verify.sql): the facts, their labels against the
    # source's rows, the score; this verb only types the claim and the source's rows and prints the brain's lines; jev.py is not read
    claim, source = jev_opt(a, "--claim"), jev_opt(a, "--source")
    if claim is None or not source: print("cortex jev verify --claim <text> --source <db or file>", file=sys.stderr); return 2
    rows, err = jev_source_rows(source)
    if err: print("jev: %s" % err, file=sys.stderr); return 2
    rc, lines = jev_brain("verify", json.dumps(rows), [claim], count=False)
    if rc: return rc
    sys.stdout.write("".join("%s\n" % l for l in lines)); return 0
def v_jev_calibrate(a):
    # jev C10 (the owner 11-06 14:46 and 11-09 00:48, as the ask): a jury pooled by self-consistency and checked for calibration in the judge's brain
    # (judge/judge-jev-calibrate.sql); this verb only types the set file's text and the bins and prints the brain's lines; jev.py is not read
    path, bins = jev_opt(a, "--set"), jev_opt(a, "--bins")
    if not path: print("cortex jev calibrate --set <file> [--bins k]", file=sys.stderr); return 2
    text = jev_read(path)
    if text is None: return 2
    rc, lines = jev_brain("calibrate", text, [], rules=bins if bins is not None else "", count=False)
    if rc: return rc
    sys.stdout.write("".join("%s\n" % l for l in lines)); return 0
def jev_door():
    # jev C8: the reasons of each answer and the retracted rows (jevwhy by question id, jevdep and jevretract by row id); dead since the 11-10 clear (the door plan, section 7)
    ready = []
    def lit(x): return "'" + str(x).replace("'", "''") + "'"
    def door_q(sql):
        if not ready: ready.append(1)
        r = ask("q " + sql)
        if r.get("error"): raise RuntimeError("brain: " + r["error"])
        return r.get("rows") or []
    def get(kind, name):
        rows = cxq("SELECT value FROM record WHERE kind = %s AND name = %s AND n = 0" % (lit(kind), lit(name)))
        return rows[0][0] if rows else None
    def put(kind, name, value):
        return   # jev C8's reasons: dead since the 11-10 clear (the door plan, section 7); nothing is written outside the encoder
    def retracted(ids):
        out, ids = set(), list(ids)
        for i in range(0, len(ids), 200):
            ch = ids[i:i + 200]
            for (nm, v) in cxq("SELECT name, value FROM record WHERE kind = 'jevretract' AND n = 0 AND name IN (%s)" % ", ".join(lit(x) for x in ch)):
                try:
                    if json.loads(v).get("retracted"): out.add(nm)
                except (ValueError, AttributeError): pass
        return out
    def record(recs):
        deps = {}
        for qid, d in recs:
            put("jevwhy", qid, json.dumps(d))
            for r in d["rows"]: deps.setdefault(r["id"], []).append(qid)
        for rid, qs in deps.items():
            try: old = json.loads(get("jevdep", rid) or "[]")
            except ValueError: old = []
            put("jevdep", rid, json.dumps(sorted(set(old) | set(qs))))
    return {"get": get, "put": put, "retracted": retracted, "record": record, "cxdb": cx_db_path}
def v_jev(names, k=8, seed=None):
    # rail C6 (the owner, 11-09: the judge --> jev like needs to happen): our own jev lives in the judge brain as rows of sql (judge/judge-jev.sql) on the test kernel;
    # a request row fires rules 1 to 6 through the mother; this verb only asks and prints, beside the python judge's verdict; nothing here decides
    import random
    if PORT != 7010: raise SystemExit("the judge brain lives on the test kernel: CORTEX_PORT=7010 cortex jev <project ...> [--n k] [--seed s]")
    pool = []
    for nm in names:
        for (n0, run0, at0, ts0, v0) in cx_list("verdict", nm):
            try: d0 = json.loads(v0)
            except (ValueError, TypeError): continue
            if isinstance(d0, dict) and d0.get("kind") and d0.get("n") is not None: pool.append((nm, n0, d0))
    rnd = random.Random(seed); pick = rnd.sample(pool, min(k, len(pool)))
    same = llm_only = llm_over = 0; t0 = time.time()
    for (nm, run, d0) in pick:
        cn = int(d0["n"])   # the judge brain's ask row is not written here: rail C6 stays on the test kernel until its check passes; nothing is written outside the encoder
        rows = q("SELECT completes, progresses, regresses, supersedes, off_scope, invents, contradicts, verdict, evidence FROM cx.judge_jev WHERE run = ? AND name = ? AND n = ?", run, nm, cn)
        cell = q("SELECT voice, check_state, values_held, pair_sources, pairs_held, pairs FROM cx.judge_cell WHERE run = ? AND name = ? AND n = ?", run, nm, cn)
        errs = [r for r in q("SELECT id, said FROM cx.judge_rule WHERE id IN (1, 2, 3, 4, 5, 6)") if str(r[1] or "").startswith("error")]
        if not rows: print("run %d %s C%d: the judge brain wrote no jev row%s" % (run, nm, cn, (" | " + "; ".join("rule %s: %s" % (i, s[:160]) for i, s in errs)) if errs else "")); continue
        c_, p_, r_, s_, o_, i_, x_, verdict, ev = rows[0]
        if verdict == d0["kind"]: same += 1
        if cell and cell[0][0] != "owner" and cell[0][1] is None and not cell[0][2] and not (cell[0][3] >= 2 and cell[0][4] * 2 >= max(1, cell[0][5])):
            llm_only += 1
            if max(c_, p_) > 0.8: llm_over += 1
        print("run %d %s C%d | python: %s %.2f (%s) | jev: %s | completes %.2f progresses %.2f regresses %.2f supersedes %.2f off scope %.2f invents %.2f contradicts %.2f" % (run, nm, cn, d0["kind"], float(d0.get("p") or 0), d0.get("judge"), verdict, c_, p_, r_, s_, o_, i_, x_))
        print("    evidence: %s" % ev)
        print("    sentence: %s" % line_text(run)[:220])
        if errs: print("    rule errors: " + "; ".join("rule %s: %s" % (i, s[:160]) for i, s in errs))
    print("jev beside the python judge: %d claims, the same verdict on %d; %d held only by an llm voice, of them above 0.80 on completes or progresses: %d; %.0f s" % (len(pick), same, llm_only, llm_over, time.time() - t0))
def v_source(name, band=None, text=None, domain=None):
    if band is None and text is None and domain is not None:   # C36: cortex source <name> --domain a,b sets the domains of a registered source
        had = cx_get("source", name, 0)
        if not had: raise SystemExit("no source " + name)
        d = json.loads(had[3]); d["domain"] = domain; cx_put("source", name, 0, had[0], had[1], json.dumps(d)); _SRCD.pop(name, None); print("source %s domains: %s" % (name, ",".join(domain))); return
    # a source is a project of typed lines: cortex source <name> owner|reference : <what it is, where from, as of>; then cortex source <name> - types its lines from stdin (build time, no judge)
    if band:
        if band not in BANDS: raise SystemExit("a source band is owner or reference (a receipt comes from cortex receipt)")
        cx_put("source", name, 0, 0, 0, json.dumps({"band": band, "text": text, "ts": int(time.time()), "domain": domain or []}))
        print("source %s (%s%s) run %d: %s" % (name, band, (", " + ",".join(domain)) if domain else "", run, text[:120])); return
    if not cx_get("source", name, 0): raise SystemExit("register the source first: cortex source %s owner|reference : <what it is, where from, as of>" % name)
    source_type(name, sys.stdin.read())
CODE_EXT = (".py", ".c", ".h", ".ts", ".tsx", ".js", ".rs", ".go", ".sql", ".sh", ".java", ".cpp", ".cc", ".rb", ".php", ".cs", ".swift", ".kt", ".lua", ".pl")
CODE_HEAD = re.compile(r"^\s*(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|const|let|var|function|fn|pub|struct|impl|package|func|print|#include|using|namespace|async|await|yield|lambda|switch|case|break|continue|static|void|int|char|float|double|bool|self\.|this\.)\b")
def is_code_line(l):
    t = l.strip()
    if not t: return False
    if is_noise(t) in ("code", "command-or-markup", "symbols"): return True
    if CODE_HEAD.match(t): return True
    return bool(re.search(r"[=(){}\[\];]", t)) and len(content_words(t)) <= 3
def code_share(raw):
    ls = [l for l in raw.splitlines() if l.strip()]
    if not ls: return 0.0
    return sum(1 for l in ls if is_code_line(l)) / len(ls)
def hard_block_code(raw, where):
    # the owner, 11-04 18:2x: a hard block for the hub builder and the neuron builder: code written into the neuron as words is never ingested; code lives outside the brain as a source db
    if code_share(raw) >= 0.3: raise SystemExit("hard block (the owner, 11-04 18:2x): code never enters the brain as words (%s: %.0f%% code lines); type it as a source db: cortex source <name> reference --db ..." % (where, code_share(raw) * 100))
def source_type(name, raw):
    raw = re.sub(r"```.*?```", " ", raw, flags=re.S)   # the owner, 11-04: fenced code never enters the brain as words
    hard_block_code(raw, "the text of source " + name)
    t0 = time.time(); n_typed = dupes = noise = refused = 0
    for sent in sentences(raw):
        if is_noise(sent): noise += 1; continue
        k = text_key(sent)
        if cx_get("source", name, k): dupes += 1; continue
        try: run, at, r = record("source", name, None, sent)
        except RuntimeError: refused += 1; continue
        n_typed += 1   # the words are not stored again (the owner, 11-03: words do not live in the brain); the run's gates replay the sentence
        if n_typed % 500 == 0: print("  %d typed, %.0f s" % (n_typed, time.time() - t0), flush=True)
    print("source %s: %d sentences typed, %d repeats, %d noise, %d refused, %.1f s" % (name, n_typed, dupes, noise, refused, time.time() - t0)); return n_typed
def ask_question(name, n, run, words, vrun):
    # the meaning question: the words of a claim that no receipt, owner line, reference or project line holds; asked once, recorded, answered by the owner (mark, accept, reject) or by a source
    if cx_get("question", name, run): return
    body = "C%d run %d: %s" % (n, run, ", ".join(words))
    try: qrun = record("question", name, n, body)[0]
    except RuntimeError: qrun = 0
    cx_put("question", name, run, qrun, clock(), json.dumps({"n": n, "words": words, "ts": int(time.time()), "verdict_run": vrun, "answered": None}))
    print("  question asked, no ground for: %s | answer: cortex mark %s %d <kind>, accept or reject it, or type a source that holds the words" % (", ".join(words), name, run))
def answer_question(name, run, how, found=None):
    had = cx_get("question", name, run)
    if not had: return
    d = json.loads(had[3])
    if d.get("answered"): return
    d["answered"] = how; d["answered_ts"] = int(time.time())
    if found is not None: d["found"] = found[:40]   # C51.1: pointers to the lines found (source and row id, or run), no text; re-read by cortex questions --answered
    cx_put("question", name, run, had[0], had[1], json.dumps(d))
def open_questions(name, n=None, limit=20):
    out = []
    for (run, v) in cxq("SELECT n, value FROM record WHERE kind = 'question' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 300", name):
        d = json.loads(v)
        if d.get("answered") or (n is not None and d.get("n") != n): continue
        d["run"] = run; out.append(d)
    return out[:limit]
def v_questions(name, n=None, prune=False):
    qs = open_questions(name, n, 300)
    if prune:   # C40: a question asked of a sentence that is not a candidate for state is retired
        gone = 0
        for d in list(qs):
            vd = cx_get("verdict", name, d["run"]); vk = json.loads(vd[3]).get("kind") if vd else None
            if vk in ("drift", "noise", "dupe") or not candidate(name, d.get("n") or 0, line_text(d["run"])): answer_question(name, d["run"], "retired: %s (C40)" % ("not a candidate" if vk not in ("drift", "noise", "dupe") else "its verdict was " + vk)); gone += 1
        qs = open_questions(name, n, 300); print("pruned %d questions of %s that were not candidates for state (C40)" % (gone, name))
    for d in qs: print("C%s run %d (%s): %s" % (d["n"], d["run"], time.strftime("%m-%d %H:%M", time.localtime(d["ts"])), ", ".join(d["words"])))
    print("%d open questions of %s%s. answer: cortex mark %s <run> <kind> [: why] | cortex accept|reject %s <n> <run> | cortex source <src> - with text that holds the words" % (len(qs), name, (" at C%d" % n) if n is not None else "", name, name))
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
MARKS = set(LABEL_Q) | {"dupe", "noise", "unsettled", "holds", "guess"}
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
    run, at, r = record("project", name, 0, clean(scope))
    print("project %s run %d clock %d%s" % (name, run, at, " (a repeat of the scope line)" if r.get("same_as") else ""))
def v_checkpoint(name, n, text, expected=None, kind=None):
    run, at, r = record("checkpoint", name, n, clean(text)); print("checkpoint %s %d run %d clock %d" % (name, n, run, at))
    if expected: run2, at2, _ = record("expected", name, n, clean(expected)); print("expected %s %d run %d" % (name, n, run2))
    if kind: record("kind", name, n, kind); print("kind %s %d %s" % (name, n, kind))
    if not cx_get("state", name, n): v_state(name, n, "open")
def v_state(name, n, state):
    assert state in ("open", "working", "done"), state
    if state == "done" and RAIL and not _CLOSING[0]:   # rail C1 (the owner, 11-09: ok do it): only the cortex own check closes a checkpoint
        print(("state %s %d: done refused, " % (name, n)) + (met_waits(name, n, "the state verb").strip(" |") or "already done")); return
    run, at, _ = record("state", name, n, state); print("state %s %d %s run %d clock %d" % (name, n, state, run, at))
def state_at(name, n, t1):
    had = cx_get("states", name, n)
    if not had: return None
    hist = [h for h in json.loads(had[3]) if h.get("ts", 0) <= t1]
    return hist[-1] if hist else None
def text_key(s):
    # the index key of an ingest: the first 60 bits of the sentence's sha256; a repeat finds its first run here and is a tick, never a second line
    return int(hashlib.sha256(s.encode()).hexdigest()[:15], 16)
def ingest_text(value):
    # an ingest's index value is JSON {"t": sentence, "times": n}; an older plain value is the sentence itself
    try:
        d = json.loads(value); return d.get("t", ""), int(d.get("times", 1))
    except (ValueError, TypeError, AttributeError): return value, 1
VOICE = ["hand"]   # who is speaking into the cortex: the hand (a builder's or the owner's ingest), or a session seen by the capture (hub:<session>)
GUESS = re.compile(r"\b(i am guessing|i guess|my guess|a guess|guessing here|i think|maybe|perhaps|probably|not sure|likely|for example|an example|example|e\.g\.|hypothesis|hypothetically|should be able to)\b")
GUESS_PARA = set()   # C33: the sentences of a paragraph that says it is guessing or gives an example; filled by v_ingest per text, read per sentence
def v_ingest(name, text, quiet=False, repeat_to_kernel=True):
    # every sentence of the text under the project's ingest key, through the encoder (the door plan, D7): a new sentence is one memory; a repeat
    # makes no memory, the neuron appends one more key and time (the owner, 11-10: a repeat is a cell changed); noise and restatements are dropped before anything is typed
    out = []; t0 = time.time()
    GUESS_PARA.clear()
    for para in re.split(r"\n\s*\n|\n", text):
        if GUESS.search(para.lower()):
            for s0 in sentences(para): GUESS_PARA.add(text_key(s0))
    fates, counts = filter_lines(name, sentences(text))
    for s, fate, why in fates:
        k = text_key(s)
        if fate == "noise":
            if not quiet: print("dropped (%s): %s" % (why, s[:80]))
            continue
        if fate == "restated":
            if not quiet: print("dropped (restated): %s" % s[:80])
            continue
        if fate == "dupe" and why == "batch":
            had = cx_get("ingest", name, k)
            if had: out.append({"run": had[0], "clock": had[1], "born": 0, "seconds": 0.0, "same_as": had[0], "again": ingest_text(had[3])[1], "text": s})
            if not quiet: print("dropped (repeated in this batch): %s" % s[:80])
            continue
        now_ts = int(time.time())
        try:
            run, at, r = record("ingest", name, None, s, ts=now_ts)
            if VOICE[0] != "hand": file_line("voice", name, None, safe_line(s), now_ts, kl="voice %s %s" % (name, VOICE[0]))
            if k in GUESS_PARA and not GUESS.search(s): file_line("guess", name, None, safe_line(s), now_ts, kl="guess %s" % name)
        except RuntimeError as e:
            if not quiet: print("refused: %s" % e)
            continue
        sa = r.get("same_as") or 0
        out.append({"run": run, "clock": at, "born": 0, "seconds": r.get("seconds", 0.0), "same_as": sa, "again": ((r.get("again") or 0) + 1) if sa else 1, "text": s})
        if not quiet: print("ingest run %d %s%.3fs: %s" % (run, ("a repeat (the memory %d gets one more key and time), " % sa) if sa else "new, ", r.get("seconds", 0.0), s[:100]))
    print("filter: %d sentences, kept %d, dupe %d, restated %d, noise %d, %.0f ms" % (len(fates), counts["keep"], counts["dupe"], counts["restated"], counts["noise"], (time.time() - t0) * 1000))
    return out
# ---- part-wise state (handler C12): a checkpoint's accepted state is the set of sentences accepted into it over time ----
def add_part(name, n, run, text, p=None, by=None, ground=None):
    k = text_key(text); had = cx_get("part", name, k)
    if had:
        d = json.loads(had[3])
        if d.get("rejected_by") == "owner": return "refused (rejected by the owner)"
        d["times"] = d.get("times", 1) + 1; d.pop("rejected_by", None)   # accepted again: back in the state (a superseded part stays superseded)
        if p is not None and d.get("p") is None: d["p"], d["by"] = p, by      # a part judged before C15 gets its confidence and judge on its next judgment
        if ground and not d.get("ground"): d["ground"] = ground               # and its ground (C16)
        cx_put("part", name, k, had[0], had[1], json.dumps(d)); return "tick %d" % d["times"]
    cx_put("part", name, k, run, clock(), json.dumps({"n": n, "run": run, "times": 1, "p": p, "by": by, "ground": ground, "ts": int(time.time())})); return "added"
def retire_part(name, n, old_run, new_run, why):
    # a part leaves the accepted state: superseded_by a newer value, or rejected_by a re-judgment; the row stays as history
    for (k, ts, v) in cxq("SELECT n, ts, value FROM record WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 200", name):
        d = json.loads(v)
        if d.get("run") == old_run and d.get("n") == n and (new_run == "owner" or not d.get(why)):
            d[why] = new_run; cx_put("part", name, k, d["run"], clock(), json.dumps(d)); return True
    return False
def parts_of(name, n, limit=5, history=False):
    out = []
    for (ts, v) in cxq("SELECT ts, value FROM record WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 200", name):
        d = json.loads(v)
        if d.get("n") != n: continue
        if not history and (d.get("superseded_by") or d.get("rejected_by")): continue
        d.setdefault("ts", ts); out.append(d)
    return out[:limit]
def accepted_state(name, n):
    ps = parts_of(name, n)
    return " | ".join(line_text(p["run"]) for p in reversed(ps)) if ps else "(nothing accepted yet)"
# ---- the judge as a run data sheet (handler C11): deterministic cells first, judgment cells when a judge exists, then the formula ----
def sheet_cells(name, n, run, text, pr, ck, ex):
    cw = content_words(text)
    cells = {"words": len(cw), "shared_scope": len(cw & content_words(pr[3])), "shared_checkpoint": len(cw & content_words(ck[3])), "shared_expected": len(cw & content_words(ex[3])) if ex else 0,
             "expected_mark": "met" if re.search(r"expected: ?met", text) else ("not met" if re.search(r"expected: ?not met", text) else "none"),
             "noise": is_noise(text) or "", "geometry": geometry(pr[0], run)}
    hist = {}
    for (v,) in cxq("SELECT value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 20", name):
        k = json.loads(v).get("kind"); hist[k] = hist.get(k, 0) + 1
    cells["history"] = hist
    had = cx_get("ingest", name, text_key(text)); cells["times"] = ingest_text(had[3])[1] if had else 1
    # the diff cell (the owner: "classifies what is duped information, new information"): the ingest's words against the accepted state's words
    known = set()
    parts = parts_of(name, n, 1000)
    for p in parts: known |= content_words(line_text(p["run"]))
    base = content_words(pr[3]) | content_words(ck[3]) | (content_words(ex[3]) if ex else set())
    cells["new_words"] = len(cw - known - base); cells["known_words"] = len(cw & (known | base))
    cov, by_rel = coverage(content_words(ex[3]) if ex else set(), cw); cells["coverage_expected"] = cov; cells["by_relation"] = by_rel
    cells["observed"] = bool(OBS.search(text))
    cells.update(shape_cells(name, n, run, pr, ck, ex, parts))
    cells.update(ground_cells(name, n, run, text, cells["new_to_project"]))
    try: cells["enc"] = enc_cells(run, {"expected": ex[0] if ex else None, "checkpoint": ck[0] if ck else None, "scope": pr[0] if pr else None})   # C59, side by side
    except Exception as e: cells["enc"] = {"error": str(e)[:80]}
    cells["pair_ground"] = pair_ground(name, run)
    cells["owner_conflict"] = owner_conflict(run)
    cells["sources"] = source_check(run)
    iv = cxq("SELECT value FROM record WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", name, run)
    try: ivd = json.loads(iv[0][0]) if iv and iv[0][0].startswith("{") else {}
    except (ValueError, TypeError): ivd = {}
    cells["voice"] = ivd.get("voice", "hand"); cells["designer"] = own_design(name) and cells["voice"] == "owner"   # C37
    had_i = cx_get("ingest", name, text_key(text)); cells["timeline"] = timeline_cells(name, run, text, had_i[2] if had_i else None)   # C38
    for tl in (cells["timeline"] or []):
        if tl["words_held"]: cells["ground"]["timeline"] = max(cells["ground"].get("timeline", 0), tl["words_held"])
    return cells
def formula(cells, answers):
    # the substitution formulas over a full sheet, in order: what the shape settles, then the deterministic word cells, then the judgment cells
    if cells["noise"]: return "noise", "sheet"
    if cells.get("same_as"): return "dupe", "shape"                                   # the kernel's own repeat of an earlier run
    if cells.get("echo"): return "dupe", "shape"                                      # the expected sentence's own shape with nothing out of line: words, no observation
    sc = cells.get("sources") or {}
    if len(sc.get("disagree", [])) >= 3 and not sc.get("confirm") and not cells.get("designer"): return "hallucination", "sources"   # C37: never for the designer on their own design, that is a question   # C28 (the owner): a statement proven false by three or more sources
    rb = cells.get("receipt_before_claim")
    about = cells.get("receipt_named") or cells.get("numbers_in_ext") or cells.get("shape_expected", 0) >= 0.5   # C22: the claim is about this print: names its command, cites its values, or states the expected
    if rb and cells.get("numbers_out") and cells.get("measure_missing"): cells["print_missing"] = list(cells["numbers_out"]); return "unsettled", "sheet"   # 2026-11-04 (cortex why c49, run 2186007): the sheet asked for a print it lacked (measure_missing) and the receipt conviction ran on the same line; a missing print is a question, not a verdict (C35.3)
    if rb and cells.get("numbers_out") and (cells.get("receipt_named") or cells.get("numbers_in_ext")): return "hallucination", "receipt"   # C35.3: convicted only against a print it names or cites
    if rb and cells.get("numbers_out") and about: cells["print_missing"] = list(cells["numbers_out"]); return "unsettled", "sheet"   # C35.3: the expected shape with numbers no print holds: ask for the print, never convict   # a value the machine never printed, said after the print, by a claim about that print (C35b: a number beside a missing measure's word was set aside as unchecked)
    if cells.get("supersedes_run"): return "supersedes", ("receipt" if rb and cells.get("numbers_in") and not cells.get("numbers_out") else "shape")   # the same shape as an accepted part, only value or time gates out of line
    if cells.get("shape_gates", 0) >= 4 and cells["shape_shared_project"] == 0: return "drift", "shape"   # no word gate shared with the scope, checkpoint or expected
    if cells["words"] >= 4 and cells["shared_scope"] == 0 and cells["shared_checkpoint"] == 0 and cells["shared_expected"] == 0 and not cells["observed"]: return "drift", "sheet"
    if cells.get("receipt_runs") and cells.get("numbers_in") and not cells.get("numbers_out") and cells["shape_expected"] >= 0.7: return "completes", "receipt"   # the expected's shape and every value printed by the machine (a later print confirming an earlier claim counts)
    if cells.get("shape_gates") and cells["shape_expected"] >= 0.7 and cells["values_out"] >= 1 and len(cells["new_to_project"]) <= 1 and not rb: return "completes", "shape"   # the expected's shape plus a value out of line, no print older than the claim to check it against
    if cells["words"] >= 4 and cells["new_words"] == 0 and cells["known_words"] >= 3 and not cells["observed"]: return "dupe", "sheet"   # a restatement with nothing new and nothing observed
    if rb and cells.get("numbers_in") and not cells.get("numbers_out") and cells["ground"]["receipt"] >= 2 and (cells.get("receipt_named") or cells.get("numbers_in_ext") or cells.get("shape_expected", 0) >= 0.3):
        return ("progresses" if cells.get("shape_expected", 0) >= 0.3 else "holds"), "receipt"   # C33 (the owner): a printed value holds; it is progress only when it speaks to the expected output
    if answers: return decide(answers), "judgment"
    return "unsettled", "sheet"
def outcome_of(kind, by, guess):
    if guess: return "guesses"
    if kind in ("hallucination", "invention") and by in ("receipt", "shape", "sources"): return "false"   # proven by the machine's print, the brain's shape or three sources, never by a model's word
    if kind in ("completes", "progresses", "supersedes", "holds") and by in ("receipt", "shape", "sources"): return "confirmed"
    return None
def tally_voice(voice, kind, by, guess, name=None, run=None):
    # C25 (the owner, 11-03 17:0x): inputs are measured; a fact proven false lowers that voice's trust, a labeled guess does not.
    # C31 (the owner, 11-03 21:3x): the topic is the project first, then the words the claim touches; the checkpoint is not a topic. One keyed row per voice, one per (voice, gate).
    _VOICES.clear()   # the voice table is read from the verdict lines of the tree (voice_table); a new verdict changes it
BANDS_DEFAULT = {"llm": [0.2, 0.8], "owner": [0.5, 0.8], "reference_alone": 0.6, "reference_agree": 1.0, "owner_and_source": 0.85, "llm_and_two_sources": 0.95, "llm_and_owner": 0.5,
                 "note": "the owner, 2026-11-03 21:5x: llm ceiling 80 floor 20, turn dependent; owner ceiling .80 floor 50, informed guesses; reference 1.00 when true between sources, 60 alone; owner and source agree strong, llm and two sources very strong, llm and human without a source 50/50; the machine print is the ground"}
def bands():
    had = cx_get("bands", "judge", 0)
    if had:
        try: return json.loads(had[3])
        except ValueError: pass
    cx_put("bands", "judge", 0, 0, clock(), json.dumps(BANDS_DEFAULT)); return dict(BANDS_DEFAULT)
def belief_of(voice, name, kind, by, sc):
    # C32: the belief of a claim from who stands behind it: the machine's print, the sources agreeing, the owner, and the voice inside its band
    B = bands(); band = "owner" if voice == "owner" else "llm"; lo, hi = B[band]
    pt = project_trust(voice, name); had = cx_get("voice", voice, 0)
    obs = pt["trust"] if pt and pt["trust"] is not None else None
    if obs is None and had:
        d = json.loads(had[3]); t = d["confirmed"] + d["false"]; obs = (d["confirmed"] / t) if t else None
    banded = min(hi, max(lo, obs if obs is not None else (lo + hi) / 2))
    owner_srcs = set(nm for (nm, b) in sources() if b == "owner")
    conf = sc.get("confirm", []) if sc else []
    ref_conf = [x for x in conf if x not in owner_srcs]; owner_conf = any(x in owner_srcs for x in conf) or band == "owner"
    if by == "receipt" and kind in ("completes", "progresses", "supersedes", "holds"): return 1.0, "the machine's print"
    own = own_design(name) and owner_conf   # C37 (the owner, 11-04): on a design of the owner, the owner's line is a reference until the design's own prints ground it
    if own: ref_conf = ref_conf + ["the designer"]
    if len(ref_conf) >= 2: return (B["reference_agree"] if band == "owner" else B["llm_and_two_sources"]), "two sources agree" + (" (the designer counted, C37)" if own else "")
    if len(ref_conf) == 1 and owner_conf and not own: return B["owner_and_source"], "the owner and a source agree"
    if len(ref_conf) == 1 and own: return max(B["reference_alone"], round(banded, 2) if band == "owner" else 0.0), "the designer on their own design: a reference alone until the design's prints ground it (C37)"
    if len(ref_conf) == 1: return B["reference_alone"], "a reference alone"
    if owner_conf and band == "llm": return B["llm_and_owner"], "llm and owner agree, no source"
    return round(banded, 2), "the voice alone, inside its band %.2f to %.2f" % (lo, hi)
def word_trust(voice, run):
    # the voice's record on the words this claim touches: confirmed and false over those gates, and the trust they give
    c = f = n = 0
    for g in set(x for x in content_gates(run) if not is_value(x)):
        hg = cx_get("vgate", voice, g)
        if hg: e = json.loads(hg[3]); c += e.get("confirmed", 0); f += e.get("false", 0); n += 1
    return {"gates": n, "confirmed": c, "false": f, "trust": round(c / (c + f), 2) if (c + f) else None}
def project_trust(voice, name):
    had = cx_get("voice", voice, 0)
    if not had: return None
    bp = (json.loads(had[3]).get("by_project") or {}).get(name)
    if not bp: return None
    t = bp["confirmed"] + bp["false"]
    return {"claims": bp["claims"], "confirmed": bp["confirmed"], "false": bp["false"], "trust": round(bp["confirmed"] / t, 2) if t else None}
def voices():
    out = []
    for vn, d in sorted(voice_table()[0].items()):
        tot = d["confirmed"] + d["false"]; out.append((vn, d, (d["confirmed"] / tot) if tot else None))
    return out
NO_PARTS = set()   # (name, n) pairs judged for the record only: no part added, no state moved (the capture against a done project's newest checkpoint)
def parts_cover(name, n):
    # C39 (the owner, 11-04 04:3x: the judge has to be able to judge more than one sentence as in this expected output situation): the expected shape covered by the standing parts together, each grounded by a receipt, the shape or the owner; a model part never closes a checkpoint
    ex = cx_get("expected", name, n)
    if not ex: return 0.0, 0, 0, 0
    Es = set(g for g in content_gates(ex[0]) if not is_value(g))
    if not Es: return 0.0, 0, 0, 0
    got, used = set(), 0
    for p in parts_of(name, n, 1000):
        if p.get("superseded_by") or p.get("rejected_by") or not p.get("run"): continue
        if p.get("by") not in ("receipt", "shape", "owner", "sources", None): continue
        hit = Es & set(content_gates(p["run"]))
        if len(hit) / len(Es) >= 0.3: got |= hit; used += 1   # C33: a part counts only when it speaks to the expected itself; chatter parts with common words never add up to a close
    return round(len(got) / len(Es), 3), len(got), len(Es), used
def close_by_parts(name, n):
    # C39: the state moves when the parts together meet the expected (0.7 of its gates), the same bar one sentence has
    if (name, n) in NO_PARTS: return ""
    cov, k, m, used = parts_cover(name, n)
    if not used: return ""
    st = cx_get("state", name, n)
    if cov >= THRESH and (not st or st[3] != "done") and RAIL: return met_waits(name, n, "its parts together, %d of %d expected gates by %d parts (C39)" % (k, m, used))
    if cov >= THRESH and (not st or st[3] != "done"):
        v_state(name, n, "done"); n2 = next_checkpoint(name)
        if n2 is not None and n2 != n:
            s2 = cx_get("state", name, n2)
            if not s2 or s2[3] != "working": v_state(name, n2, "working")
        return " | C%d done by its parts together: %d of %d expected gates covered by %d parts (C39); next C%s" % (n, k, m, used, n2)
    return " | parts together cover %.2f of the expected (%d of %d gates, %d parts)" % (cov, k, m, used)
def v_judge(name, n, run, text=None, answers_given=None, judge_name=None):
    pr = cx_get("project", name, 0); ck = cx_get("checkpoint", name, n); ex = cx_get("expected", name, n)
    if not pr or not ck: raise SystemExit("no such project/checkpoint: %s %s" % (name, n))
    if text is None:
        rows = cxq("SELECT value FROM record WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", name, run)
        if not rows: raise SystemExit("ingest run %s is not in the index" % run)
        text = line_text(run)
    t0 = time.time(); cells = sheet_cells(name, n, run, text, pr, ck, ex)
    state = {"project": name, "scope": pr[3], "checkpoint": ck[3], "expected": ex[3] if ex else "(none)", "accepted_state": accepted_state(name, n), "ingest": text}
    answers, model = {}, None
    kind, by = formula(cells, {})
    if kind == "unsettled":
        if answers_given is not None: answers, model = answers_given, judge_name
        else:
            la = learned_answers(cells); W0 = weights() or {}; lv = W0.get("v", 0)
            if W0.get("acc", 1.0) < 0.7: la = None; print("  learned v%s abstains: %.2f on leave-one-out, below 0.7 (more marks needed)" % (lv, W0.get("acc", 0)))
            if la is not None and decide(la) != "unsettled": answers, model = la, "learned v%d" % lv
            elif judge_route():
                try: got, model = judge_batch(state, [(run, text)]); answers = got.get(run, {})
                except (urllib.error.URLError, urllib.error.HTTPError, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
                    raise SystemExit("judge call failed, no verdict written: %s" % e)
            elif la is not None: answers, model = la, "learned v%d (abstained)" % lv
    if answers: kind, by = formula(cells, answers)
    judge = model if (by == "judgment" and model) else by
    if answers and by == "judgment": p = answers.get(kind, 0.0) if kind in answers else max(answers.values())
    elif by in ("shape", "receipt", "sources"): p = cells["shape_expected"] if kind in ("completes", "progresses") else 1.0
    else: p = 1.0 if kind in ("noise", "drift", "dupe") else 0.0
    body = "%s %.3f %s" % (kind, p, judge)
    vrun, at, _ = record("verdict", name, run, body)
    accepting = kind in ("completes", "progresses", "supersedes") and (name, n) not in NO_PARTS   # holds adds no part: true, not progress (C33)
    gr = dict(cells.get("ground") or {}); pg0 = cells.get("pair_ground") or {}
    if pg0.get("pairs"): gr["agree"] = len(pg0.get("agree", [])); gr["of"] = pg0.get("sources", 0)
    bl0, br0 = belief_of(iv0.get("voice", "hand") if (iv0 := (lambda rr: (json.loads(rr[0][0]) if rr and rr[0][0].startswith("{") else {}))(cxq("SELECT value FROM record WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", name, run))) else "hand", name, kind, by, cells.get("sources") or {}); gr["belief"] = bl0
    part = add_part(name, n, run, text, p, judge, gr) if accepting else ("rejected" if retire_part(name, n, run, vrun, "rejected_by") else "")
    if kind == "supersedes" and cells.get("supersedes_run") and not part.startswith("refused") and retire_part(name, n, cells["supersedes_run"], run, "superseded_by"): part += " | retired the part of run %d" % cells["supersedes_run"]
    moved = ""
    if kind == "completes" and p >= THRESH and by not in ("shape", "receipt"): moved = " | a judgment cell's completes does not move the state: the receipt, the shape or the owner's accept does"
    if kind == "completes" and p >= THRESH and by in ("shape", "receipt") and (name, n) not in NO_PARTS:
        st = cx_get("state", name, n)
        if (not st or st[3] != "done") and RAIL: moved = met_waits(name, n, "this verdict, completes %.2f by %s" % (p, by))
        elif not st or st[3] != "done":
            v_state(name, n, "done"); n2 = next_checkpoint(name)
            if n2 is not None and n2 != n:
                s2 = cx_get("state", name, n2)
                if not s2 or s2[3] != "working": v_state(name, n2, "working")
            moved = " | C%d done by this verdict; next C%s" % (n, n2)
    if not moved and accepting and part and not part.startswith("refused"): moved = close_by_parts(name, n)   # C39
    irow = cxq("SELECT value FROM record WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", name, run); iv = {}
    try: iv = json.loads(irow[0][0]) if irow else {}
    except (ValueError, TypeError): iv = {}
    cx_put("verdict", name, run, vrun, at, json.dumps({"n": n, "run": run, "kind": kind, "p": p, "judge": judge, "answers": answers, "sheet": cells, "part": part, "voice": iv.get("voice", "hand"), "guess": bool(iv.get("guess"))}))
    tally_voice(iv.get("voice", "hand"), kind, by, bool(iv.get("guess")), name, run)
    geo = cells["geometry"]
    vc = iv.get("voice", "hand"); pt = project_trust(vc, name); wt = word_trust(vc, run); bl, brule = belief_of(vc, name, kind, by, cells.get("sources") or {})
    print("  belief %.2f (%s)" % (bl, brule))
    rec = "held before" if cells.get("same_as") or cells.get("echo") else ("supersedes run %s" % cells["supersedes_run"]) if cells.get("supersedes_run") else "new to the project record"
    print("  voice: %s%s | belief row: 1 the project record: %s; 2 the words: %s on %d gates (%d confirmed, %d false); 3 the sources: %d confirm, %d disagree, agreement %d of %d | this voice on %s: %s" % (vc, " (a labeled guess)" if iv.get("guess") else "", rec, ("trust %.2f" % wt["trust"]) if wt["trust"] is not None else "no record", wt["gates"], wt["confirmed"], wt["false"], len((cells.get("sources") or {}).get("confirm", [])), len((cells.get("sources") or {}).get("disagree", [])), len((cells.get("pair_ground") or {}).get("agree", [])), (cells.get("pair_ground") or {}).get("sources", 0), name, ("trust %.2f over %d claims" % (pt["trust"], pt["claims"])) if pt and pt["trust"] is not None else "no record yet"))
    if cells.get("numbers_spec"): print("  numbers the spec holds (the repo source): %s (C47b)" % ", ".join(cells["numbers_spec"]))
    print("  ground: %s | receipts %d (%s)%s numbers in %s out %s%s" % (ground_str(cells.get("ground")), cells.get("receipt_runs", 0), ",".join(cells.get("receipt_cmds", [])) or "-", "" if not cells.get("receipt_runs") or cells.get("receipt_before_claim") else " all newer than the claim: no print at its time", ",".join(cells.get("numbers_in", [])) or "-", ",".join(cells.get("numbers_out", [])) or "-", ((" | rounded: " + ", ".join("%s for %s" % kv for kv in cells["numbers_rounded"].items())) if cells.get("numbers_rounded") else "") + ((" | newest print: " + cells["receipt_newest"]) if cells.get("receipt_newest") else "")))
    ec = cells.get("enc") or {}
    if ec.get("neurons"): print("  encoder words (C59, side by side, not deciding until the owner retires the cut): %d neurons in %d words; shared with the expected %d neurons, %d whole words (the cut shares %d words); the cut throws away %d: %s" % (ec["neurons"], ec["words"], ec.get("shared_expected", 0), ec.get("words_expected", 0), cells.get("shared_expected", 0), ec.get("cut_drops", 0), " ".join(_ENC_DROPPED.get(run, [])[:16]) or "-"))
    if cells.get("numbers_in_newer") and kind in ("hallucination", "unsettled", "drift"): print("  a print newer than this claim holds %s: a later print never switches a verdict (C33b); pipe the print first, then make the claim again (re-ingest it) and judge the new run (C33c)" % ", ".join(cells["numbers_in_newer"]))
    if cells.get("print_missing") and kind not in ("noise", "dupe", "drift") and (name, n) not in NO_PARTS:   # C35.3
        print("  no print holds %s: pipe the print this claim is about, then type the claim again (C35.3)" % ", ".join(cells["print_missing"]))
        ask_question(name, n, run, ["no print holds %s" % ", ".join(cells["print_missing"][:6])], vrun)
    if cells.get("measure_missing") and kind not in ("noise", "dupe", "drift") and (name, n) not in NO_PARTS:   # C40: a drift line asks nothing
        print("  no print to check this: it names %s, settled by %s; ask for that print (C34)" % (", ".join(w for m0 in cells["measure_missing"] for w in cells["measures"][m0]), ", ".join(cells["measure_missing"])))
        ask_question(name, n, run, ["no print of %s for a claim about %s" % (m0, ", ".join(cells["measures"][m0])) for m0 in cells["measure_missing"]], vrun)
    pg = cells.get("pair_ground") or {}
    if pg.get("pairs"): print("  pairs: %d, held by sources %s | memory %s | held by no source: %s | agreement %d of %d sources%s" % (pg["pairs"], " ".join("%s %d" % kv for kv in sorted(pg["held_by"].items(), key=lambda kv: -kv[1])[:4]) or "none", " ".join("%s %d" % kv for kv in sorted(pg["memory"].items(), key=lambda kv: -kv[1])[:3]) or "none", "; ".join(pg["none"][:6]) or "-", len(pg.get("agree", [])), pg.get("sources", 0), (" (" + ", ".join(pg["agree"][:4]) + ")") if pg.get("agree") else ""))
    cg = code_ground(name, run)
    if cg: print("  code ground (C50): " + "; ".join(cg))
    no_source = pg.get("pairs", 0) >= 3 and not pg.get("held_by") and not cells.get("numbers_in_ext")   # no source holds any pair and no print grounds a value: the run left known ground at its first pair
    unknown = (cells.get("ground", {}).get("none") or []) + ([("pair: " + x) for x in pg.get("none", [])[:6]] if no_source else [])
    no_record = False
    for tl in (cells.get("timeline") or []):   # C38: the record of the graph's own time is the ground for a claim that names a time
        print("  timeline: %s (%s) holds %d of %d words and %d of %d pairs in %d lines of %s%s (C38)" % (tl["when"], time.strftime("%m-%d", time.localtime(tl["t0"])), tl["words_held"], tl["words"], tl["pairs_held"], tl["pairs"], tl["lines"], name, (" | not held: " + ", ".join(tl["missing"])) if tl["missing"] else ""))
        if not tl["lines"]: unknown = ["no record of %s on %s (%s)" % (name, tl["when"], time.strftime("%m-%d", time.localtime(tl["t0"])))] + unknown; no_record = True
        elif tl["words"] and tl["words_held"] * 2 < tl["words"]: unknown = ["the record of %s on %s does not hold: %s" % (name, tl["when"], ", ".join(tl["missing"][:6]))] + unknown
    sc = cells.get("sources") or {}
    if sc.get("confirm") or sc.get("disagree"): print("  sources: %d confirm (%s) | %d disagree (%s)" % (len(sc.get("confirm", [])), ", ".join(sc.get("confirm", [])[:4]), len(sc.get("disagree", [])), "; ".join("%s differs by %s: %s" % (d["source"], ",".join(d["differs"]), d["line"][:70]) for d in sc.get("disagree", [])[:3])))
    if cells.get("designer") and len(sc.get("disagree", [])) >= 3 and not sc.get("confirm"):   # C37
        print("  three sources disagree with the designer on their own design: a question, not a verdict (C37)"); unknown = ["three sources disagree with the designer: " + "; ".join("%s: %s" % (d["source"], d["line"][:60]) for d in sc["disagree"][:3])] + unknown
    oc = cells.get("owner_conflict")
    if oc:
        print("  against an owner line (differs by %s): %s" % (",".join(oc["differs"]), oc["line"][:120])); unknown = ["against the owner line run %d (%s): %s" % (oc["run"], ",".join(oc["differs"]), oc["line"][:80])] + unknown
    asking = (name, n) not in NO_PARTS   # a session's narration judged for the record only asks no meaning questions
    if asking and oc and kind not in ("noise", "dupe"): ask_question(name, n, run, unknown[:8], vrun)   # a claim against the owner's words is asked about whatever its verdict here
    settled = by in ("shape", "receipt", "sources") and kind != "unsettled"   # the shape or a print already decided this claim; no meaning question
    if asking and not settled and (len(unknown) >= 2 or no_source or no_record) and kind not in ("noise", "dupe", "drift"): ask_question(name, n, run, unknown[:8], vrun)   # C38: a day with no record is asked by itself
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
        la = learned_answers(cells, W) if (W or {}).get("acc", 1.0) >= 0.7 else None
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
def parked(name, n):
    # a checkpoint whose every part left says it waits on the owner or the kernel: the rail moves past it (the owner, 11-03: keep it working)
    left = [r for r in remainders_of(name, n) if not r.get("satisfied")]
    return bool(left) and all(any(g in line_text(r["run"]) for g in GATED) for r in left)
def next_checkpoint(name):
    cps = cx_list("checkpoint", name)
    for (n, run, at, ts, text) in cps:
        st = cx_get("state", name, n)
        if st and st[3] == "working" and not parked(name, n): return n
    for (n, run, at, ts, text) in cps:
        st = cx_get("state", name, n)
        if (not st or st[3] == "open") and not parked(name, n): return n
    return None
def hydration_text(name, pr, nxt):
    lines = []
    lines.append("PROJECT %s: %s" % (name, pr[3]))
    if nxt is not None:
        ck = cx_get("checkpoint", name, nxt); ex = cx_get("expected", name, nxt)
        lines.append("DO NOW, C%d: %s" % (nxt, ck[3]))
        if ex: lines.append("EXPECTED OUTPUT: %s" % ex[3])
        mt = cx_get("met", name, nxt) if RAIL else None
        if mt:
            try: mw = json.loads(mt[3])[-1]["why"]
            except (ValueError, IndexError, KeyError): mw = "a verdict"
            lines.append("MET, NOT CLOSED: the expected was met by %s; only the cortex own check closes C%d (rail C1)%s" % (mw, nxt, "" if check_audited(name, nxt) else "; its check is not yet written and audited"))
        ps = parts_of(name, nxt)
        if ps: lines.append("ACCEPTED SO FAR (parts of C%d's state, each with its time, confidence and ground): " % nxt + " | ".join("%s [%s%s | %s]" % (line_text(p["run"])[:90], time.strftime("%m-%d %H:%M", time.localtime(p.get("ts") or 0)), (" p%.2f %s" % (p["p"], p.get("by") or "")) if p.get("p") is not None else "", ("the owner's word" if p.get("by") == "owner" or (p.get("by") is None and p.get("p") is None) else ground_str(p.get("ground")))) for p in reversed(ps)))
        rc = receipts_of(name, nxt)
        if rc:
            et = toks(ex[3]) if ex else set()
            def head(cmd): return toks(" ".join(cmd.split()[:3])) - {"cortex", "c"}   # the program and its first arguments name a print; a capture's shell line does not
            named = sorted([(cmd, d) for cmd, d in rc.items() if head(cmd) & et], key=lambda kv: -kv[1].get("ts", 0))[:6]; others = sorted([(cmd, d) for cmd, d in rc.items() if not (head(cmd) & et)], key=lambda kv: -kv[1].get("ts", 0))[:3]
            # C41 (the owner: give them enough): the prints the expected names, whole; then the newest three others, three lines each
            for cmd, d in named: lines.append("RECEIPT %s [%s]: " % (cmd[:60], time.strftime("%m-%d %H:%M", time.localtime(d.get("ts", 0)))) + " / ".join(receipt_line(l)[:120] for l in d.get("lines", [])[:8]))
            if others: lines.append("OTHER RECEIPTS (%d commands on C%d; the newest %d): " % (len(rc), nxt, len(others)) + " | ".join("%s => %s [%s]" % (cmd[:50], " / ".join(receipt_line(l)[:70] for l in d.get("lines", [])[:3]), time.strftime("%m-%d %H:%M", time.localtime(d.get("ts", 0)))) for cmd, d in others))
        ck0 = cx_get("check", name, nxt)
        if ck0:
            cl = cx_get("checklast", name, nxt); cld = json.loads(cl[3]) if cl else None
            lines.append("THE CORTEX'S OWN CHECK on C%d (the cortex runs it in the repo after your turn; it decides, your sentences do not; it uses numbers of its own, so special cases and edited tests fail it): %s | last print: %s" % (nxt, json.loads(ck0[3]).get("cmd"), (cld["last"][:300] if cld else "not run yet")))
        nd = cx_get("need", name, nxt)
        if nd:
            try: lines.append("WHAT THE LAST WORKERS SAID THIS HYDRATION LACKED (C41; the liaison or the owner adds it, a worker does not invent it): " + " | ".join(x.get("text", "")[:160] for x in json.loads(nd[3])[-4:]))
            except ValueError: pass
        left = [r for r in remainders_of(name, nxt) if not r.get("satisfied")]
        if left: lines.append("REMAINDER of C%d (parts left not satisfied): " % nxt + "; ".join("%d %s" % (r["k"], line_text(r["run"])[:100]) for r in left[:6]))
        # C41b: why the last turn did not close this checkpoint: its refusals by receipt, with the cause; feedback, never state (the owner, C40)
        ref = []
        for (rn, v) in cxq("SELECT n, value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 30", name):
            d = json.loads(v)
            if d.get("n") != nxt or d.get("kind") != "hallucination" or d.get("judge") != "receipt": continue
            sh = d.get("sheet") or {}; ref.append("run %d: %s -> the number%s %s %s in no print of this checkpoint (pipe that print first, or leave the number out)" % (rn, line_text(rn)[:70], "s" if len(sh.get("numbers_out") or []) > 1 else "", ", ".join(sh.get("numbers_out") or []), "are" if len(sh.get("numbers_out") or []) > 1 else "is"))
            if len(ref) >= 2: break
        if ref: lines.append("WHY THE LAST TURN DID NOT CLOSE C%d (refusals by the print; feedback, not state): " % nxt + " | ".join(ref))
        qs = open_questions(name, nxt, 5)
        if qs: lines.append("OPEN QUESTIONS (words of C%d's claims that no receipt, owner line or reference holds; the owner answers them, a worker never guesses them): " % nxt + "; ".join("run %d: %s" % (d["run"], ", ".join(d["words"])) for d in qs))
        lines.append("RECEIPTS RULE: before a sentence cites a print, pipe that print in: <command> | cortex receipt %s %d <command>; a sentence about a print names its command; a number said before its print is a guess; a print older than the claim is the only one that judges it." % (name, nxt))
        lines.append("END YOUR ANSWER with one line `EXPECTED: met` or `EXPECTED: not met`, then one sentence that restates the EXPECTED OUTPUT above in its own words with the values you observed after piping the print (that sentence is what the judge matches against the print; a paraphrase does not close the checkpoint), then the live output. Add `NEEDED: <what this hydration lacked>` only for something still missing now, and `FLAW: <a flaw in this checkpoint or its expected that you cannot fix or verify yourself>` if you found one; the cortex hands a flaw back to the owner.")
    else:
        lines.append("DO NOW: nothing; every checkpoint is done. Say so.")
        left = [(cn, r) for (cn, run, at, ts, ctext) in cx_list("checkpoint", name) for r in remainders_of(name, cn) if not r.get("satisfied")]
        if left: lines.append("REMAINDER (the contract's parts left not satisfied, from the brain; the owner's word makes one a checkpoint): " + "; ".join("C%d.%d %s" % (cn, r["k"], line_text(r["run"])[:100]) for (cn, r) in left[:10]))
        nw = next_work(name)
        if nw: lines.append("NEXT WORK (the first part left that names neither the kernel nor the owner): C%d.%d %s" % nw)
    if nxt is not None: lines.append("DISPUTE (C53): if a verdict called a true sentence of yours invention, hallucination or drift, add one line DISPUTE: run <run> <why> (the run numbers are in WHY THE LAST TURN DID NOT CLOSE); the sixth gives a second opinion from the guessing, the project record and the sources, and tells you the shape the brain holds so you can say it that way.")
    lines.append("LAWS: report only what you observed as live output; name the command and its output; never invent a result, a term or a file; stay inside the scope; if the expected output is not met say so and why.")
    lines.append("ALL CHECKPOINTS (state; only C%s is yours now; the done ones one line each, C41):" % (nxt if nxt is not None else "-"))
    for (n, run, at, ts, text) in cx_list("checkpoint", name):
        st = cx_get("state", name, n); s = st[3] if st else "open"
        lines.append("  C%d [%s] %s" % (n, s, text[:70] if (s == "done" and n != nxt) else (text if n == nxt else text[:160])))
    vs = [(n, jload(v)) for (n, v) in cxq("SELECT n, value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 40", name)]
    moves = [(n, d) for (n, d) in vs if d.get("kind") in ("completes", "progresses", "supersedes", "holds") and d.get("part") and not str(d.get("part")).startswith("refused")][:3]
    if moves:
        lines.append("LAST MOVES (verdicts that added state; drift, hallucination and invention never hydrate, C40):")
        for (n, d) in moves: lines.append("  C%s %s %.2f by %s: %s" % (d.get("n"), d.get("kind"), d.get("p", 0), d.get("judge"), line_text(n)[:90]))
    return "\n".join(lines) + "\n"
def hydration(name, at=None):
    pr = cx_get("project", name, 0)
    if not pr: raise SystemExit("no project " + name)
    return hydration_text(name, pr, at if at is not None else next_checkpoint(name))
def v_hydrate(name, at=None):
    h = hydration(name, at); sys.stdout.write(h); print("[%d bytes]" % len(h.encode()), file=sys.stderr)
def v_accept(name, n, run=None):
    # the owner's word: with a run, that ingest's sentence becomes a part of C n's state; without, C n is done
    if run is None and RAIL: print(met_waits(name, n, "the accept").strip(" |") or "C%d is done already" % n); return
    if run is None: v_state(name, n, "done"); return
    rows = cxq("SELECT value FROM record WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", name, run)
    if not rows: raise SystemExit("ingest run %s is not in the index" % run)
    text = line_text(run); r = add_part(name, n, run, text, None, "owner"); answer_question(name, run, "accept"); print("part %s for %s C%d from run %d: %s" % (r, name, n, run, text[:90]))
    m2 = close_by_parts(name, n)
    if m2: print(m2.strip(" |"))
def v_reject(name, n, run):
    # the owner's word, the counterpart of accept: that sentence is not a part of C n's state whatever the judge said; it stays as history and is never re-accepted
    answer_question(name, run, "reject")
    if retire_part(name, n, run, "owner", "rejected_by"): print("part of run %d rejected from %s C%d by the owner" % (run, name, n))
    else: raise SystemExit("no part of run %s in %s C%d" % (run, name, n))
    # a part this run had superseded comes back: the newer value was never true, so the older one stands again
    for (k, v) in cxq("SELECT n, value FROM record WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 200", name):
        d = json.loads(v)
        if d.get("n") == n and d.get("superseded_by") == run:
            d.pop("superseded_by"); cx_put("part", name, k, d["run"], clock(), json.dumps(d)); print("part of run %d stands again in %s C%d (it was superseded by the rejected run)" % (d["run"], name, n))
MODEL_BY_KIND = {"read": "haiku", "write": "sonnet", "design": "opus"}   # the router's model per step kind (handler C7); a judgment step goes to jev
def worker(engine, model, prompt, cwd, act):
    env = dict(os.environ); env["PATH"] = os.path.expanduser("~/.local/bin") + ":" + env.get("PATH", "")   # C44b: the worker pipes its prints with cortex receipt
    if engine == "claude":
        cmd = ["claude", "-p", "--model", model, "--output-format", "text"] + (["--dangerously-skip-permissions"] if act else [])
        t0 = time.time(); p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=3600, env=env)
        return p.stdout, p.stderr, p.returncode, time.time() - t0
    if engine == "codex":
        last = os.path.join(cwd, ".codex-last-message.txt")
        if os.path.exists(last): os.remove(last)
        cmd = ["codex", "exec", "-C", cwd, "--output-last-message", last] + (["--model", model] if model and model != "default" else []) + (["--dangerously-bypass-approvals-and-sandbox"] if act else ["-s", "read-only"]) + ["-"]
        t0 = time.time(); p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=3600, env=env)
        out = open(last).read() if os.path.exists(last) else p.stdout
        return out, p.stderr, p.returncode, time.time() - t0
    raise SystemExit("engine must be claude or codex")
def judgment_step(name, n, ck):
    # the router: a judgment step is one jev question over the project's state; no model turn. The answer is ingested and judged like any output.
    pr = cx_get("project", name, 0); ex = cx_get("expected", name, n)
    part_texts = [line_text(json.loads(v).get("run") or 0) for (v,) in cxq("SELECT value FROM record WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 200", name)]
    state = {"project": name, "scope": pr[3], "checkpoint": ck[3], "expected": ex[3] if ex else "(none)", "accepted_state": accepted_state(name, n), "accepted_parts_of_the_project": part_texts[:20], "last_verdicts": [line_text(json.loads(v).get("run") or 0)[:200] for (_, v) in cxq("SELECT n, value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 3", name)]}
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
def v_turn(name, engine="claude", model=None, act=False, at=None, cwd=None):
    nxt = at if at is not None else next_checkpoint(name)
    if nxt is None: print("nothing to do: every checkpoint of %s is done" % name); return None
    if not cx_get("checkpoint", name, nxt): raise SystemExit("no checkpoint %s %d" % (name, nxt))
    st = cx_get("state", name, nxt)
    if not st or st[3] != "working": v_state(name, nxt, "working")
    kind = cx_get("kind", name, nxt); kind = kind[3] if kind else "write"
    if model is None: model = MODEL_BY_KIND.get(kind, "sonnet") if engine == "claude" else "default"
    h = hydration(name, nxt); cwd = cwd or repo_of(name) or os.path.join(WORKDIR, name); os.makedirs(cwd, exist_ok=True)
    if kind == "judgment":
        print("turn %s C%d: a judgment step, routed to the judge (no worker)" % (name, nxt))
        out, p = judgment_step(name, nxt, cx_get("checkpoint", name, nxt)); err, rc, secs = "", 0, 0.0
        print("the judge answered: %s" % out)
        run_ = v_ingest(name, out, quiet=True)
        if p >= THRESH:
            r0 = run_[0]["run"] if run_ else 0; add_part(name, nxt, r0, out[:300], p, "judgment")
            if out.startswith("judgment by graph") and RAIL: print(met_waits(name, nxt, "the judgment by graph (%.2f)" % p).strip(" |"))
            elif out.startswith("judgment by graph"):
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
    needed = [m.group(1).strip() for m in re.finditer(r"(?mi)^\s*needed:\s*(.+?)\s*$", out)]; flaws = [m.group(1).strip() for m in re.finditer(r"(?mi)^\s*flaw:\s*(.+?)\s*$", out)]   # C41, C44: the worker's own lines
    for x in needed:
        if x.lower() not in ("none", "nothing", "-"): v_need(name, nxt, x, who="%s:%s" % (engine, model))
    disputes = [(int(m.group(1)), m.group(2).strip()) for m in re.finditer(r"(?mi)^\s*dispute:\s*(?:run\s+)?(\d+)\s*(.*)$", out)]
    for (dr, why) in disputes[:3]:   # C53: the worker asks for a second opinion; the sixth rules and the next hydration carries it
        try: ruling, shape = v_dispute(name, dr, why or "the worker holds it correct"); v_need(name, nxt, "the sixth on run %d: %s | %s" % (dr, ruling[:140], shape[:200]), who="sixth")
        except (SystemExit, Exception) as e: print("dispute on run %d failed: %s" % (dr, e))
    body = re.sub(r"(?mi)^\s*(needed|flaw|dispute):.*$", "", out)
    ing = v_ingest(name, body, quiet=True); kinds = judge_many(name, nxt, [i for i in ing if not i["same_as"]])
    print("ingested %d sentences (%d repeats), verdicts: %s" % (len(ing), sum(1 for i in ing if i["same_as"]), " ".join(kinds) or "none"))
    st_now = cx_get("state", name, nxt)
    if st_now and st_now[3] == "done": print("C%d done by its verdict; next C%s" % (nxt, next_checkpoint(name)))
    elif "completes" in kinds: print("C%d has a completes from a judgment cell, not from the shape: the state waits for the shape or the owner's accept" % nxt)
    elif kinds and all(k in ("drift", "invention", "hallucination") for k in kinds): print("C%d stays working: the output was off rail (%s); the next hydration carries these verdicts" % (nxt, ",".join(sorted(set(kinds)))))
    else: print("C%d stays working" % nxt)
    print("--- worker output (first 1200 bytes) ---"); print(out[:1200])
    return {"n": nxt, "engine": "%s:%s" % (engine, model), "secs": secs, "kinds": kinds, "out": out, "needed": needed, "flaws": [f for f in flaws if f.lower() not in ("none", "nothing", "-")], "prompt_bytes": len(h.encode())}
def repo_of(name):
    rp = cx_get("repo", name, 0)
    try: return json.loads(rp[3]).get("path") if rp else None
    except ValueError: return None
def repo_words(path, limit=40000):
    # the repo's own words: readme, docs and markdown at the root, bounded; the owner's spec in the repo is the owner's voice
    import glob
    cands, seen, out, total = [], set(), [], 0
    for pat in ("README*", "readme*", "Readme*", "*.md", "docs/*.md", "doc/*.md", "spec/*.md", "SPEC*", "*.txt"):
        cands += sorted(glob.glob(os.path.join(path, pat)))
    for f in cands:
        if f in seen or not os.path.isfile(f): continue
        seen.add(f)
        try: t = open(f, errors="replace").read()
        except OSError: continue
        t = t[: max(0, limit - total)]; total += len(t); out.append((os.path.relpath(f, path), t))
        if total >= limit: break
    return out
PLAN_PROMPT = """You are planning a build for the cortex, a persistent memory that prescribes one checkpoint at a time to a headless worker whose whole context is the hydration, and judges the worker's output against an expected output that is a live print.
PROJECT %s: %s
THE REPO'S OWN WORDS (%s):
%s
WRITE THE OUTLINE: between 3 and 9 checkpoints in build order. Each checkpoint is exactly one line:
checkpoint <n> : <what is built, one sentence> || <the live output that proves it: the command the worker runs in the repo and what it prints, with the values it must print>
Rules: an expected output is an observable print, never a test name, a summary or an intent; the first checkpoint is the smallest piece that prints; every later checkpoint uses what the earlier ones built; stay inside the repo's own words; no other text, no headings, no code.
"""
def v_plan(name, path, engine="claude", model=None, scope=None):
    # C43 (the owner, 11-04 05:0x: if i give you a repo and say ingest this into cortex, build the outlines checkpoints and expected outputs): the repo's words in, an outline out, read before any build
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path): raise SystemExit("no such folder: " + path)
    words = repo_words(path)
    if not words: raise SystemExit("the repo has no readme, docs or markdown to plan from: " + path)
    text = "\n\n".join("## %s\n%s" % (f, t) for f, t in words)
    pr = cx_get("project", name, 0)
    if not pr:
        sc = scope or re.sub(r"\s+", " ", re.sub(r"(?m)^#.*$", "", words[0][1]).strip())[:300]
        v_project(name, sc); pr = cx_get("project", name, 0)
    cx_put("repo", name, 0, 0, clock(), json.dumps({"path": path, "ts": int(time.time())}))
    src = name + "-repo"
    if not cx_get("source", src, 0): v_source(src, "owner", "the repo %s own words (readme, docs, markdown), read %s" % (path, time.strftime("%Y-%m-%d")), ["software"])
    typed_n = source_type(src, text)
    if model is None: model = MODEL_BY_KIND.get("design", "opus") if engine == "claude" else "default"
    prompt = PLAN_PROMPT % (name, pr[3], path, text[:12000])
    print("plan %s: %d files, %d repo sentences typed as the owner source %s; design worker %s %s, prompt %d bytes" % (name, len(words), typed_n, src, engine, model, len(prompt.encode())))
    out, err, rc, secs = worker(engine, model, prompt, path, False)
    if rc != 0 or not out.strip(): print("worker stderr: " + err[-600:]); raise SystemExit("the design worker failed, nothing typed")
    got = []
    for m in re.finditer(r"(?mi)^\s*checkpoint\s+(\d+)\s*:\s*(.+?)\s*\|\|\s*(.+?)\s*$", out):
        n = int(m.group(1))
        if cx_get("checkpoint", name, n): print("C%d exists already; not re-typed" % n); continue
        v_checkpoint(name, n, m.group(2), m.group(3)); got.append(n)
    print("plan %s: %d checkpoints typed open in %.0f s (%s); read them with cortex status %s before cortex build %s" % (name, len(got), secs, " ".join("C%d" % x for x in got), name, name))
    if not got: print("--- the design worker's output (first 1500 bytes) ---"); print(out[:1500])
def handback(name, n, text, res):
    # C44, C45: a flaw the worker found that the cortex cannot settle, or a checkpoint that does not move: parked on the owner, listed by cortex handbacks
    rs = remainders_of(name, n)
    v_remainder(name, n, "hand-back: %s (waits on the owner: cortex decide %s <k> accept|reject|checkpoint)" % (text[:220], name))
    rs2 = remainders_of(name, n); rrun = rs2[-1]["run"] if rs2 else 0
    hb = cx_list("handback", name); k = (max([h[0] for h in hb]) + 1) if hb else 1
    cx_put("handback", name, k, rrun, clock(), json.dumps({"n": n, "text": text[:600], "remainder_run": rrun, "remainder_k": len(rs2), "worker": (res or {}).get("engine"), "out": ((res or {}).get("out") or "")[:1500], "ts": int(time.time()), "decided": None}))
    print("hand-back %d on %s C%d: %s | the build moves on; the owner decides with cortex decide %s %d accept|reject|checkpoint" % (k, name, n, text[:120], name, k))
def v_build(name, engine="claude", model=None, box_min=30, max_turns=12, act=True):
    # C44 (the owner, 11-04 05:0x: tell cortex to build it; it prescribes the work to the headless workers, checks the outputs, prescribes the next steps; a flaw it cannot settle is handed back and the build moves on)
    t0 = time.time(); turns, k, log = {}, 0, []
    try: sys.stdout.reconfigure(line_buffering=True)   # the schedule lines reach the log as they happen (python -I ignores PYTHONUNBUFFERED)
    except (AttributeError, ValueError): pass
    cwd = repo_of(name) or os.path.join(WORKDIR, name)
    print("build %s: box %d min, at most %d turns, worker %s, cwd %s" % (name, box_min, max_turns, engine, cwd))
    while time.time() - t0 < box_min * 60 and k < max_turns:
        nxt = next_checkpoint(name)
        if nxt is None:
            alldone = all((cx_get("state", name, n0) or (0, 0, 0, "open"))[3] == "done" for (n0, r0, a0, t0_, x0) in cx_list("checkpoint", name))
            print("build %s: nothing unblocked: %s" % (name, "every checkpoint is done" if alldone else "the rest wait on the owner (cortex handbacks %s)" % name)); break
        turns[nxt] = turns.get(nxt, 0) + 1; k += 1
        before = (cx_get("state", name, nxt) or (0, 0, 0, "open"))[3]; nparts = parts_cover(name, nxt)[3]
        if RAIL and not check_audited(name, nxt):   # rail C2, C3: the check is written and audited before the worker's turn; the worker never sees it
            pr_, why_ = prove_check(name, nxt)
            if pr_ == "work wrong": v_need(name, nxt, "the check written by the exec printed on the work: %s" % why_[:260], who="cortex check")
            elif pr_ != "audited":
                if pr_ != "audit failed": handback(name, nxt, ("not yet a checkpoint, no machine print can show its expected: %s" if pr_ == "no check" else "the check could not be written and audited: %s") % why_[:300], {"engine": "claude"})
                print("schedule: C%d has no audited check (%s: %s); the build moves on" % (nxt, pr_, why_[:160]))
                if pr_ == "audit failed": break
                continue
        try: res = v_turn(name, engine, model, act, nxt, cwd=cwd)
        except SystemExit as e: res = {"n": nxt, "engine": engine, "secs": 0.0, "kinds": [], "out": "", "needed": [], "flaws": ["the worker failed: %s" % e]}
        res = res or {}
        after = (cx_get("state", name, nxt) or (0, 0, 0, "open"))[3]; moved = (after == "done") or (parts_cover(name, nxt)[3] > nparts)   # a model's part is not a move
        chk_note = ""; chk = run_check(name, nxt, cwd)   # C47: the cortex's own check, the worker never touched it
        if chk is not None:
            if chk["ok"]:
                chk_note = " check ok"
                if after != "done" and (RAIL or re.search(r"(?mi)^\s*expected:\s*met\b", res.get("out") or "")):   # 11-04 16:3x (the lesson build): the cortex own print decides (C47); check ok and the worker's met line close the checkpoint, the check's print its part
                    if close_by_check(name, nxt, chk) is not False: after = "done"; moved = True; chk_note += " (closed by the cortex own check)"
            else:
                chk_note = " check WRONG: " + chk["last"][:120]
                if after == "done": v_state(name, nxt, "working"); after = "working"; print("C%d reopened: the cortex's own check failed: %s" % (nxt, chk["last"][:200])); chk_note += " (reopened)"
                moved = False; v_need(name, nxt, "the cortex own check printed: %s" % chk["last"][:260], who="cortex check")
        line = "turn %d C%d worker %s %.0f s prompt %d bytes verdicts %s moved %s%s%s" % (k, nxt, res.get("engine", engine), res.get("secs", 0.0), res.get("prompt_bytes", 0), ",".join(res.get("kinds") or []) or "none", ("yes, %s" % after) if moved else "no", (" needed: " + " ; ".join(res["needed"])[:100]) if res.get("needed") else "", (" flaw: " + " ; ".join(res["flaws"])[:100]) if res.get("flaws") else "")
        line += chk_note; record("schedule", name, None, clean(line)); print("schedule: " + line); log.append(line)
        if res.get("flaws"): handback(name, nxt, "; ".join(res["flaws"]), res)
        elif not moved and turns[nxt] >= 2: handback(name, nxt, "no progress after %d turns" % turns[nxt], res)
    print("build %s: %d turns in %.0f s; %d hand-backs open; run cortex formula %s" % (name, k, time.time() - t0, len([1 for (hk, hr, ha, ht, hv) in cx_list("handback", name) if not json.loads(hv).get("decided")]), name))
def v_handbacks(name):
    rows = cx_list("handback", name)
    for (k, run, at, ts, v) in rows:
        d = json.loads(v); print("hand-back %d C%d [%s] %s: %s%s" % (k, d.get("n"), time.strftime("%m-%d %H:%M", time.localtime(d.get("ts", 0))), d.get("worker") or "", d.get("text", "")[:200], (" | decided: " + d["decided"]) if d.get("decided") else " | open"))
    print("%d hand-backs of %s; decide one: cortex decide %s <k> accept|reject|checkpoint [: <new checkpoint text> || <expected>]" % (len(rows), name, name))
def v_decide(name, k, how, text=None):
    # C45 (the owner: i give or you give a decision on it, cortex is updated and build moves on)
    had = cx_get("handback", name, k)
    if not had: raise SystemExit("no hand-back %d of %s" % (k, name))
    d = json.loads(had[3]); n = d["n"]
    if how not in ("accept", "reject", "checkpoint"): raise SystemExit("decide accept|reject|checkpoint")
    note = text if (how != "checkpoint" and text and " || " not in text) else None   # a note after the colon is the decision reason, not a re-typed checkpoint
    if note: text = None
    if how in ("accept", "checkpoint") and text:
        exp = None
        if " || " in text: text, exp = text.split(" || ", 1)
        run, at, _ = record("checkpoint", name, n, clean(text)); print("checkpoint %s %d re-typed run %d" % (name, n, run))
        if exp: run2, at2, _ = record("expected", name, n, clean(exp)); print("expected %s %d re-typed run %d" % (name, n, run2))
    rs = remainders_of(name, n)
    for r in rs:
        if r["run"] == d.get("remainder_run") and not r.get("satisfied"): r["satisfied"] = "decided %s by the owner or the liaison %s" % (how, time.strftime("%m-%d %H:%M")); r["satisfied_ts"] = int(time.time())
    cx_put("remainder", name, n, d.get("remainder_run") or 0, clock(), json.dumps(rs))
    d["decided"] = how; d["decided_ts"] = int(time.time()); d["note"] = note; cx_put("handback", name, k, had[0], had[1], json.dumps(d))
    st = cx_get("state", name, n)
    if not st or st[3] != "done": v_state(name, n, "working")
    print("hand-back %d of %s decided: %s; C%d unparked; cortex build %s continues" % (k, name, how, n, name))
def project_for_cwd(cwd):
    # which project a hub session's turn belongs to, by its working folder; a folder of no project is not captured
    if not cwd: return None
    if "/neuron" in cwd.lower(): return "neuron"
    if cwd.rstrip("/") == "/home/exnulla" or cwd.startswith("/home/exnulla/.claude"): return "cortex"   # the hub session's own folders (skills, memory, scratchpad) are the cortex session (11-04 18:xx: two hours of a session went uncaptured after a cd)
    return None
EXPECTED_MARK = re.compile(r"expected: ?(not )?met|^(needed|flaw):")
def candidate(name, n, text):
    # C40 (the owner, 11-04 05:0x: judging should judge context against prior state context; do not flood the cortex with drift, hallucination, invention that can later hydrate):
    # a sentence is judged only when it can be state: it carries an observation or the expected mark, or shares two words with the expected or with the accepted parts
    t = text.lower()
    if OBS.search(t) or EXPECTED_MARK.search(t): return True
    cw = content_words(t); ex = cx_get("expected", name, n)
    if ex and len(cw & content_words(ex[3])) >= 2: return True
    known = set()
    for p in parts_of(name, n, 50): known |= content_words(line_text(p["run"]))
    return len(cw & known) >= 2
def v_capture(cwd=None, name=None):
    # the hub's Stop hook pipes the tail of a transcript here: the last assistant text is ingested and, when jev has a key, judged
    # every assistant text in the tail, in order (the final message lands after the Stop hook runs, so it is caught at the next Stop; repeats tick)
    raw = sys.stdin.read(); texts_all = []; hook = {}; cmds = {}; results = []; owner_texts = []
    for line in raw.splitlines():
        try: d = json.loads(line)
        except ValueError: continue
        if d.get("type") == "hook": hook = d; continue   # C20: the hook's own line: cwd, the turn's final message (transcript_path may lag it), session, event
        c0 = d.get("message", {}).get("content")
        if isinstance(c0, list):   # C21: the machine's own prints in the session: a Bash tool_use and its tool_result
            for b in c0:
                if not isinstance(b, dict): continue
                if b.get("type") == "tool_use" and b.get("name") == "Bash": cmds[b.get("id")] = str((b.get("input") or {}).get("command", ""))
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in cmds:
                    cc = b.get("content"); txt = cc if isinstance(cc, str) else "\n".join(x.get("text", "") for x in cc if isinstance(x, dict)) if isinstance(cc, list) else ""
                    if txt.strip(): results.append((cmds[b.get("tool_use_id")], txt))
        if d.get("type") == "user" and not d.get("isSidechain"):   # C29: the owner's own words in the session are a voice the judge scores too (the owner, 11-03: i should be judged also yes)
            cu = d.get("message", {}).get("content"); tu = cu if isinstance(cu, str) else "\n".join(b.get("text", "") for b in cu if isinstance(b, dict) and b.get("type") == "text") if isinstance(cu, list) else ""
            tu = re.sub(r"(?s)<pasted_content[^>]*>.*?</pasted_content>", " ", tu); tu = re.sub(r"(?s)<system-reminder>.*?</system-reminder>|<command-[a-z-]+>.*?</command-[a-z-]+>|<local-command[^>]*>.*?</local-command[^>]*>", " ", tu)
            if tu.strip() and not tu.lstrip().startswith("<") and "This session is being continued" not in tu: owner_texts.append(tu.strip())
            continue
        if d.get("type") != "assistant": continue
        c = d.get("message", {}).get("content")
        texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"] if isinstance(c, list) else ([c] if isinstance(c, str) else [])
        t = "\n".join(x for x in texts if x and x.strip())
        if t.strip(): texts_all.append(t)
    final_msg = (hook.get("last_assistant_message") or "").strip()
    if final_msg and (not texts_all or texts_all[-1].strip() != final_msg): texts_all.append(final_msg)
    cwd = cwd or hook.get("cwd")
    VOICE[0] = "hub:" + ((hook.get("session_id") or "")[:8] or "unknown")   # C25: the voice of these sentences
    if not texts_all: print("capture: no assistant text in the tail"); return
    name = name or project_for_cwd(cwd)
    if not name: print("capture: cwd %s belongs to no cortex project; nothing ingested" % cwd); return
    nxt0 = next_checkpoint(name)
    if nxt0 is None:
        cps0 = cx_list("checkpoint", name, desc=True, limit=1); nxt0 = cps0[0][0] if cps0 else None
    nrec = 0
    if nxt0 is not None and results:
        for (cmd, txt) in results[-40:]:   # the prints of the session, forty at most (C35: twelve cut the print a later sentence cited), before its sentences
            cmdline = clean(cmd.strip().splitlines()[0] if cmd.strip() else "command")[:70]
            lines = [clean(l) for l in txt.splitlines() if clean(l)][:20]
            if not lines: continue
            for l in lines:
                body = "%s => %s" % (cmdline, l)
                try: nrec += not record("receipt", name, nxt0, body)[2].get("tick")   # the brain answers the typed line: a tick is a line it holds
                except RuntimeError: continue
        if nrec: print("receipts: %d lines typed from %d tool results for C%d" % (nrec, len(results[-40:]), nxt0))
    own = []
    if owner_texts:
        VOICE[0] = "owner"; own = v_ingest(name, "\n".join(owner_texts), quiet=True, repeat_to_kernel=False); VOICE[0] = "hub:" + ((hook.get("session_id") or "")[:8] or "unknown")
    last = "\n".join(texts_all); ing = v_ingest(name, last, quiet=True, repeat_to_kernel=False); new = [i for i in ing if not i["same_as"]] + [i for i in own if not i["same_as"]]
    print("capture %s: %d texts, %d sentences, %d new, %d repeats, %d bytes%s%s" % (name, len(texts_all), len(ing), len(new), len(ing) + len(own) - len(new), len(last.encode()), (", the turn's final message included (%d bytes)" % len(final_msg.encode())) if final_msg else "", (", the owner's voice: %d messages, %d sentences" % (len(owner_texts), len(own))) if owner_texts else ""))
    cap = {"ts": int(time.time()), "texts": len(texts_all), "sentences": len(ing), "new": len(new), "event": hook.get("hook_event_name") or "stop", "session": (hook.get("session_id") or "")[:8], "final": bool(final_msg)}
    cx_put("capture", name, 0, 0, clock(), json.dumps(cap))
    nxt = next_checkpoint(name); newest = False
    if nxt is None:
        cps = cx_list("checkpoint", name, desc=True, limit=1)
        if not cps: return
        nxt = cps[0][0]; newest = True; NO_PARTS.add((name, nxt))   # every checkpoint done: the truth matrix still runs against the newest one, for the record only: no parts, no state (C18.2)
    try:
        cands = [i for i in new if candidate(name, nxt, i["text"])]   # C40: the rest are typed for the record, never judged, never asked
        kinds = judge_many(name, nxt, cands[-20:]); print("judged %d of %d new sentences against C%d%s (C40: candidates only; %d recorded, not judged): %s" % (len(cands[-20:]), len(new), nxt, " (every checkpoint done; the newest)" if newest else "", len(new) - len(cands), " ".join(kinds)))
        cap["judged"] = len(cands[-20:]); cap["recorded"] = len(new) - len(cands); cx_put("capture", name, 0, 0, clock(), json.dumps(cap))
    except SystemExit as e: print("not judged: %s" % e)
# ---- the owner's input output formula (2026-11-02): before/after + progression = diff output + before and after states + progression
#      = expected completed output contract: satisfied parts and the remainder not satisfied. A snapshot per report; the next report diffs it. ----
def snapshot(name):
    vs = {}
    for (v,) in cxq("SELECT value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n", name):
        d = json.loads(v); vs.setdefault(d.get("n"), {}); vs[d.get("n")][d.get("kind")] = vs[d.get("n")].get(d.get("kind"), 0) + 1
    cps = {}
    for (n, run, at, ts, text) in cx_list("checkpoint", name):
        st = cx_get("state", name, n); ex = cx_get("expected", name, n)
        cps[str(n)] = {"state": st[3] if st else "open", "parts": len(parts_of(name, n, 1000)), "verdicts": vs.get(n, {})}
    ing = cxq("SELECT count(*) FROM record WHERE kind = 'ingest' AND name = ? AND n > 0", name)[0][0]
    return {"clock": clock(), "ts": int(time.time()), "checkpoints": cps, "ingests": ing, "verdicts": sum(sum(x.values()) for x in vs.values())}
def v_formula(name):
    now = snapshot(name)
    prev_rows = cxq("SELECT value FROM record WHERE kind = 'formula' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 1", name)
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
        ex = cx_get("expected", name, int(n)); ck = cx_get("checkpoint", name, int(n))
        print("  C%s done: %s | part: %s" % (n, (ex[3] if ex else "")[:100] or (ck[3] if ck else "")[:100], line_text(ps[0]["run"])[:110] if ps else "(no part recorded)"))
    rem = [n for n in cps if n not in done]
    parts_left = [(int(n), r) for n in cps for r in remainders_of(name, int(n)) if not r.get("satisfied")]
    print("CONTRACT, REMAINDER (%d checkpoints open, %d parts left not satisfied):" % (len(rem), len(parts_left)))
    for n in rem:
        c = cps[n]; miss = []
        if c["parts"] == 0: miss.append("no accepted part")
        if not c["verdicts"].get("completes"): miss.append("no completes verdict")
        cov, k, m, used = parts_cover(name, int(n))
        if used: miss.append("parts together cover %.2f of the expected (%d of %d gates, %d parts; C39)" % (cov, k, m, used))
        ex = cx_get("expected", name, int(n))
        print("  C%s [%s] expected: %s | missing: %s" % (n, c["state"], (ex[3] if ex else "")[:110] or "(none)", ", ".join(miss)))
    for (n, r) in parts_left: print("  C%d.%d left: %s" % (n, r["k"], line_text(r["run"])[:130]))
    nw = next_work(name)
    print("NEXT WORK (the first part left that names neither the kernel nor the owner): %s" % (("C%d.%d %s" % nw) if nw else "none; what is left waits on the kernel or the owner"))
    cx_put("formula", name, now["clock"], 0, now["clock"], json.dumps(now))
GATED = ("waits on the kernel", "waits on the owner")   # a remainder part that says it waits on the kernel or the owner is not the front door next work
def remainders_of(name, n):
    had = cx_get("remainder", name, n)
    return json.loads(had[3]) if had else []
def next_work(name):
    for (cn, run, at, ts, ctext) in cx_list("checkpoint", name):
        for r in remainders_of(name, cn):
            if r.get("satisfied"): continue
            t = line_text(r["run"])
            if not any(g in t for g in GATED): return cn, r["k"], t
    return None
def v_remainder(name, n=None, text=None, k=None, note=None):
    # cortex remainder <name> <n> : <part left not satisfied>   |   cortex remainder <name> <n> <k> satisfied [: by what]   |   cortex remainder <name>
    if n is None:
        tot = open_ = 0
        for (cn, run, at, ts, ctext) in cx_list("checkpoint", name):
            for r in remainders_of(name, cn):
                tot += 1; open_ += 0 if r.get("satisfied") else 1
                print("C%d.%d %s%s" % (cn, r["k"], line_text(r["run"])[:140], (" [satisfied %s: %s]" % (time.strftime("%m-%d %H:%M", time.localtime(r.get("satisfied_ts", 0))), r["satisfied"])) if r.get("satisfied") else ""))
        nw = next_work(name)
        print("%d remainder parts of %s, %d not satisfied. NEXT WORK: %s" % (tot, name, open_, ("C%d.%d %s" % nw) if nw else "none that is the front door's; the rest wait on the kernel or the owner"))
        return
    if not cx_get("checkpoint", name, n): raise SystemExit("no such checkpoint: %s %d" % (name, n))
    rs = remainders_of(name, n)
    if k is not None:
        hit = [r for r in rs if r["k"] == k]
        if not hit: raise SystemExit("no remainder part %d on %s C%d" % (k, name, n))
        hit[0]["satisfied"] = note or "yes"; hit[0]["satisfied_ts"] = int(time.time())
        cx_put("remainder", name, n, hit[0]["run"], clock(), json.dumps(rs)); print("remainder %s C%d.%d satisfied: %s" % (name, n, k, note or "yes")); return
    run = record("remainder", name, n, text)[0]
    rs.append({"k": len(rs) + 1, "run": run, "ts": int(time.time()), "satisfied": None})
    cx_put("remainder", name, n, run, clock(), json.dumps(rs)); print("remainder %s C%d.%d run %d: %s" % (name, n, len(rs), run, text[:120]))
def v_need_clear(name, n):
    had = cx_get("need", name, n)
    if had: cx_put("need", name, n, had[0], had[1], "[]")
    print("needs of %s C%d cleared (answered by the liaison)" % (name, n))
def v_need(name, n, text, who="hand"):
    # C41: what a worker said the hydration lacked; typed on the checkpoint, carried by its next hydration
    if not cx_get("checkpoint", name, n): raise SystemExit("no such checkpoint: %s %d" % (name, n))
    try: run = record("need", name, n, clean(text))[0]
    except RuntimeError as e: raise SystemExit("refused: %s" % e)
    had = cx_get("need", name, n); L = json.loads(had[3]) if had else []
    L.append({"text": clean(text)[:300], "run": run, "who": who, "ts": int(time.time())}); cx_put("need", name, n, run, clock(), json.dumps(L[-20:]))
    print("need %s C%d run %d (%s): %s" % (name, n, run, who, clean(text)[:120]))
def v_mark(name, run, kind, why=""):
    # the labeled set: the owner's (or the known-truth) word on what a judged sentence was; cortex learn trains the weights on these
    if kind not in MARKS: raise SystemExit("a mark is one of: " + " ".join(sorted(MARKS)))
    v = cx_get("verdict", name, run)
    if not v: raise SystemExit("no verdict for run %s in %s; judge it first so the mark knows its checkpoint" % (run, name))
    n = json.loads(v[3]).get("n"); cx_put("mark", name, run, run, clock(), json.dumps({"kind": kind, "n": n, "why": why, "ts": int(time.time())})); answer_question(name, run, "mark:" + kind)
    print("mark %s run %d C%s: %s" % (name, run, n, kind))
def key_project(nm):
    return 0   # the neuron keys every line at arrival (D5)
def v_learn(names=None, key_only=False):
    t0 = time.time()
    names = names or sorted(set(r[0] for r in cxq("SELECT name FROM record WHERE kind = 'project' AND name >= '' AND n = 0")))
    for nm in names: print("key %s: %d lines keyed in %.1f s" % (nm, key_project(nm), time.time() - t0))
    if key_only: return
    rows = []
    for nm in names:
        pr = cx_get("project", nm, 0)
        for (n, run, at, ts, value) in cx_list("mark", nm, limit=5000):
            d = json.loads(value); ck = cx_get("checkpoint", nm, d["n"]); ex = cx_get("expected", nm, d["n"])
            ing = cxq("SELECT value FROM record WHERE kind = 'ingest' AND name = ? AND run = ? AND n > 0", nm, run)
            if not ing or not ck or not pr: continue
            rows.append((feats(sheet_cells(nm, d["n"], run, line_text(run), pr, ck, ex)), d["kind"], nm, run))
    if len(rows) < 6: print("learn: %d marks; at least 6 are needed" % len(rows)); return
    def fit(train): return {k: train_logistic([r[0] for r in train], [1.0 if LABEL_Q.get(r[1]) == k else 0.0 for r in train]) for k in JUDGE_QUESTIONS}
    hits, wrong = 0, []
    for i in range(len(rows)):
        W = {"w": fit(rows[:i] + rows[i + 1:])}; got = decide(learned_answers_x(rows[i][0], W)); want = rows[i][1] if rows[i][1] in LABEL_Q else "unsettled"
        if got == want: hits += 1
        else: wrong.append("%s run %d: marked %s, learned %s" % (rows[i][2], rows[i][3], rows[i][1], got))
    v = (weights() or {}).get("v", 0) + 1
    rec = {"v": v, "w": fit(rows), "feats": list(FEATS), "rows": len(rows), "loo": round(hits / len(rows), 3), "ts": int(time.time())}
    rec["acc"] = round(hits / len(rows), 3) if rows else 0.0   # the leave-one-out accuracy travels with the weights; below 0.7 the judge does not use them
    cx_put("weights", "judge", 0, 0, clock(), json.dumps(rec)); cx_put("weights", "judge", v, 0, clock(), json.dumps(rec))
    print("learn: weights v%d from %d marks; leave-one-out verdict accuracy %.2f (%d of %d) in %.1f s" % (v, len(rows), hits / len(rows), hits, len(rows), time.time() - t0))
    for w in wrong: print("   missed: " + w)
def learned_answers_x(x, W): return {k: round(sigmoid(sum(a * b for a, b in zip(W["w"].get(k, []), x))), 3) for k in JUDGE_QUESTIONS}
def v_verdicts(name, n=None, limit=40):
    # the owner reads the judge here: every judged line of a project (or of checkpoint n), newest first, with the run that mark and accept and reject take
    parts = {}
    for (ts, v) in cxq("SELECT ts, value FROM record WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 500", name):
        d = json.loads(v); parts[d.get("run")] = d
    rows = cxq("SELECT n, ts, value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT ?", name, 2000 if n is not None else limit)
    shown = 0
    print("%-7s %-4s %-13s %-5s %-22s %-11s %-12s %-12s %-24s %s" % ("run", "C", "verdict", "p", "judge", "when", "part", "mark", "ground", "sentence"))
    for (run, ts, v) in rows:
        d = json.loads(v)
        if n is not None and d.get("n") != n: continue
        pt = parts.get(run); st = "-"
        if pt: st = "rejected" if pt.get("rejected_by") == "owner" else ("retired" if (pt.get("superseded_by") or pt.get("rejected_by")) else "part")
        m = cx_get("mark", name, run); mk = json.loads(m[3]).get("kind") if m else "-"
        print("%-7d C%-3s %-13s %-5.2f %-22s %-11s %-12s %-12s %-24s %s" % (run, d.get("n"), d.get("kind"), d.get("p") or 0, (d.get("judge") or "")[:22], time.strftime("%m-%d %H:%M", time.localtime(ts)), st, mk, ground_str((d.get("sheet") or {}).get("ground"))[:24] if (d.get("sheet") or {}).get("ground") else "(judged before c16)", line_text(run)[:90]))
        shown += 1
        if shown >= limit: break
    print("%d judged lines of %s%s. mark one: cortex mark %s <run> <kind> [: why]; the owner's word: cortex accept|reject %s <n> <run>" % (shown, name, (" at C%d" % n) if n is not None else "", name, name))
def v_recall(name, t0=0, t1=None, kinds=None):
    # cortex recall <project> [<kind> ...] [from <unix> to <unix>]: the project's records in time order from the tree (the owner, 11-03: a time state read ... recall print);
    # the brain's own recall is `recall : <key words>` at its prompt (the find primitive writes the key memory into the line's key cell)
    t1 = t1 or int(time.time()); keys, extra = keys_of(name); rows = []
    for (kind, n), krun in keys.items():
        if kinds and kind not in kinds: continue
        for (m, text, times) in records_of(krun):
            for t in times:
                if t0 <= t <= t1: rows.append((t, kind, n, m, text))
    rows.sort()
    for (t, kind, n, m, text) in rows: print("%s %s%s run %d: %s" % (time.strftime("%m-%d %H:%M:%S", time.localtime(t)), kind, (" %d" % n) if n is not None else "", m, text[:140]))
    print("%d records of %s between %s and %s" % (len(rows), name, time.strftime("%Y-%m-%d %H:%M", time.localtime(t0)) if t0 else "the first", time.strftime("%Y-%m-%d %H:%M", time.localtime(t1))))
def v_status(name=None):
    st = ask("stats")["main"]
    r = judge_route()
    print("brain: gates %d runs %d hops %d refused %d clock %d | judge: receipt, shape, learned v%s, then %s | tree: projects %d keys %d records %d" % ((st["gates"], st["runs"], st["hops"], st["refused"], clock(), (weights() or {}).get("v", 0), ("jev via " + jev_route()["via"]) if r == "jev" else ("claude:%s (subscription)" % JUDGE_MODEL if r == "claude" else "none")) + tree_count()))
    # C48 (the owner, 11-04: the neuron kernel is far more advanced now ... updating it into the system): which kernel answers this port,
    # told by the door verbs the cascade kernel added (moved, restep, relabel answer; the g35 kernel of 11-02 says unknown request)
    try:
        mv = ask("moved %d" % clock()); newk = "moved" in mv
    except Exception: mv = {}; newk = False
    print("kernel: port %d, %s | stats: defined %d shards %d stubs %d" % (PORT, ("the cascade kernel of hp (g37 + 11-03/11-04: the door answers moved, restep, relabel; places history, %d moved since the clock, %d passes)" % (len(mv.get("moved", [])), mv.get("passes", 0))) if newk else "the g35 kernel of 11-02 (the door does not answer moved)", st.get("defined", -1), st.get("shards", -1), st.get("stubs", -1)))
    rf = retired_functions()
    if rf: print("held by the neuron (retired from the front door on the owner word): " + ", ".join(rf))
    fr = cx_get("freeze", "handler", 0)
    if fr:
        try: now = hashlib.sha256(open(HANDLER, "rb").read()).hexdigest()
        except OSError: now = "(file missing)"
        print("freeze: brain %s file %s %s" % (fr[3][:16], now[:16], "EQUAL" if now == fr[3] else "DIFFERENT"))
    caps = []
    for (nm,) in cxq("SELECT name FROM record WHERE kind = 'capture' AND name >= '' AND n = 0"):
        c = cx_get("capture", nm, 0)
        if c:
            d = json.loads(c[3]); caps.append("%s %s (%s, %d sentences, %d new%s%s)" % (nm, time.strftime("%m-%d %H:%M", time.localtime(d.get("ts", 0))), d.get("event", "stop"), d.get("sentences", 0), d.get("new", 0), (", %d judged, %d recorded only" % (d["judged"], d.get("recorded", 0))) if "judged" in d else "", ", final message in" if d.get("final") else ""))
    print("captures: " + ("; ".join(caps) if caps else "none yet") + " | a stale time here is a failed or missing capture (C20)")
    B = bands(); print("bands: llm %.2f to %.2f, owner %.2f to %.2f, a reference alone %.2f, two sources %.2f; owner and source %.2f, llm and two sources %.2f, llm and owner %.2f (the owner, 11-03 21:5x; cx bands/judge)" % (B["llm"][0], B["llm"][1], B["owner"][0], B["owner"][1], B["reference_alone"], B["reference_agree"], B["owner_and_source"], B["llm_and_two_sources"], B["llm_and_owner"]))
    vs = voices()
    if vs: print("voices: " + "; ".join("%s claims %d, confirmed %d, false %d, guesses %d, trust %s%s" % (vn, d["claims"], d["confirmed"], d["false"], d["guesses"], ("%.2f" % t) if t is not None else "none yet", (" [" + " ".join("%s %s" % (pj, ("%.2f" % (b["confirmed"] / (b["confirmed"] + b["false"]))) if (b["confirmed"] + b["false"]) else "-") for pj, b in sorted(d.get("by_project", {}).items())) + "]") if d.get("by_project") else "") for (vn, d, t) in vs) + " | proven by receipt, shape or sources only; a labeled guess is not counted; per project in brackets, per word on the verdict line (C25, C31)")
    names = [name] if name else sorted(set(r[0] for r in cxq("SELECT name FROM record WHERE kind = 'project' AND name >= '' AND n = 0")))
    for nm in names:
        pr = cx_get("project", nm, 0)
        if not pr: print("no project", nm); continue
        print("project %s (run %d): %s" % (nm, pr[0], pr[3][:120]))
        nxt = next_checkpoint(nm)
        for (n, run, at, ts, text) in cx_list("checkpoint", nm):
            s = cx_get("state", nm, n); print("  C%d [%s]%s %s" % (n, s[3] if s else "open", " NEXT" if n == nxt else "", text[:110]))
            if name:   # jev C3: the status of one project lists each checkpoint with its expected output
                ex = cx_get("expected", nm, n)
                if ex: print("      expected: %s" % ex[3][:240])
        for (n, v) in cxq("SELECT n, value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 3", nm):
            d = jload(v)
            if d: print("  verdict run %d C%s %s %.2f (%s): %s" % (n, d.get("n"), d.get("kind"), d.get("p", 0), d.get("judge"), line_text(n)[:70]))
def v_freeze(path):
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    run, at, _ = record("freeze", "handler", 0, sha); os.chmod(path, 0o444)
    print("frozen %s sha256 %s run %d clock %d (file now read-only)" % (path, sha, run, at))

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
    bad = [f for f in files if f.lower().endswith(CODE_EXT)]
    if bad: raise SystemExit("hard block (the owner, 11-04 18:2x): code never enters the brain as words: %s; type a code base as a source db: cortex source %s reference --db --path <folder>" % (", ".join(os.path.relpath(b, root) for b in bad[:4]), name))
    # C50 (the owner, 11-04: code base docs should be able to sources with paths, so the brain can start to understand code that is being handed to it, beyond just shape):
    # a code base's docs and code typed as a reference source, every sentence keyed with the file path and the line it came from, so a claim's ground names the file
    t0 = time.time(); n_typed = dupes = noise = refused = 0; by_file = {}
    for f in files:
        rel = os.path.relpath(f, root); k_file = 0
        for (ln, para) in file_paragraphs(f):
            plines = [x.lower() for x in para.splitlines()]
            for sent in sentences(para):
                if is_noise(sent): noise += 1; continue
                k = text_key(sent)
                if cx_get("source", name, k): dupes += 1; continue
                try: r = record("source", name, None, sent)[2]
                except RuntimeError: refused += 1; continue
                head = sent.lower()[:25]; off = next((i for i, x in enumerate(plines) if head in x), 0)   # the sentence's own line inside the paragraph (a code file has few blank lines)
                run = r["run"]; cx_put("source", name, k, run, clock(), json.dumps({"path": rel, "line": ln + off})); n_typed += 1; k_file += 1
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
    root = os.path.abspath(os.path.expanduser(root))
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
    row = cxq("SELECT value FROM record WHERE kind = 'source' AND name = ? AND run = ? AND n > 0", nm, run)
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
            if source_is_db(nm):   # C54: the db row itself names the file and line
                if not cx_get("spair", nm, text_key("%s %s" % (sym_of(a), sym_of(b)))): continue
                for (sid, t, p, l) in db_lines_holding(nm, [sym_of(a), sym_of(b)], 1):
                    if p and (nm, p, l) not in seen: seen.add((nm, p, l)); out.append("%s %s:%s holds %s %s" % (nm, p, l, sym_of(a), sym_of(b)))
                if len(out) >= limit: return out
                continue
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
    qs = open_questions(name, None, 60); srcs = [nm for (nm, b) in sources()]; closed = 0
    print("questions of %s asked of the sources: %d open" % (name, len(qs)))
    for d in qs:
        words = d.get("words") or []; found, found_shown, left, ptrs = [], [], [], []
        for w in words:
            if w.startswith(("no print", "no record", "against the owner", "three sources", "the record of")): left.append(w); continue
            body = w[6:] if w.startswith("pair: ") else w
            toks = [t for t in re.findall(r"[a-z][a-z0-9_']+", body.lower()) if t not in STOP]
            gates = [gate_of_word(t) for t in toks]
            holders = []
            if w.startswith("pair: ") and len(gates) == 2 and all(gates): holders = [(nm, source_holds_pair(nm, gates[0], gates[1])) for nm in srcs]; holders = [(nm, h) for (nm, h) in holders if h]
            elif gates and all(gates): holders = [(nm, source_holds_gate(nm, gates[0])) for nm in srcs if all(source_holds_gate(nm, g) for g in gates)]
            if holders:
                where, shown = [], []
                for (nm, h) in holders[:3]:
                    if source_is_db(nm):   # C54, C51.1: the lines found, from the source db, with path and line; the record keeps the row id, the text is re-cut at read
                        for (sid, t, p, l) in db_lines_holding(nm, toks, 1): where.append("%s%s" % (nm, (" %s:%s" % (p, l)) if p else "")); shown.append("%s%s: %s" % (nm, (" %s:%s" % (p, l)) if p else "", t[:100])); ptrs.append({"w": w, "src": nm, "id": sid})
                        continue
                    first = json.loads(h[3]).get("first"); p, l = source_line_of(nm, first)
                    where.append("%s%s" % (nm, (" %s:%s" % (p, l)) if p else "")); shown.append(where[-1]); ptrs.append({"w": w, "src": nm, "run": first})
                found.append("%s held by %s" % (w, ", ".join(where))); found_shown.append("%s held by %s" % (w, ", ".join(shown)))
            elif len(toks) == 1 and not w.startswith("pair: "):
                # C51: a word no source holds is asked of the brain's own dictionaries (define : word); the definitions typed as the source defined-words populate what the brain needed to know
                defs = kernel_define(toks[0])
                if defs:
                    src = "defined-words"
                    if not cx_get("source", src, 0): v_source(src, "reference", "definitions the brain fetched from its own dictionaries (wn, gcide, wikt, moby) when a question named a word no source held (C51, 11-04)", ["meaning", "language"])
                    typed_k = 0
                    for (frm, txt) in defs:
                        for sent in sentences(txt):
                            if is_noise(sent): continue
                            k = text_key(sent)
                            if cx_get("source", src, k): continue
                            try: r = record("source", src, None, sent)[2]
                            except RuntimeError: continue
                            cx_put("source", src, k, r["run"], clock(), json.dumps({"from": frm, "word": toks[0]})); typed_k += 1
                    found.append("%s defined by %s (%d lines from %s)" % (w, src, typed_k, ",".join(sorted(set(f for f, t in defs))))); found_shown.append(found[-1]); ptrs.append({"w": w, "src": src, "word": toks[0]})
                else: left.append(w)
            else: left.append(w)
        if found and not left:
            answer_question(name, d["run"], "sources: " + "; ".join(found)[:300], ptrs); closed += 1
            try: record("answer", name, d["run"], "C%d run %d: %s" % (d.get("n", 0), d["run"], "; ".join(found)[:400]))
            except RuntimeError: pass
            print("  C%s run %d: closed by the sources: %s" % (d.get("n"), d["run"], "; ".join(found_shown)[:300]))
        else: print("  C%s run %d: %s%s" % (d.get("n"), d["run"], ("held: " + "; ".join(found_shown)[:200] + " | ") if found else "", "no source holds: " + "; ".join(left)[:240]))
    print("%d of %d questions closed by the sources; %d answered by the sources before (cortex questions %s --answered prints their lines, C51.1); the rest wait on the owner or a new source" % (closed, len(qs), len(answered_questions(name)), name))
def answered_questions(name, limit=60):
    # C51.1: the questions of a project the sources answered (closed by cortex questions --ask), newest first
    out = []
    for (run, v) in cxq("SELECT n, value FROM record WHERE kind = 'question' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 300", name):
        d = json.loads(v)
        if not str(d.get("answered") or "").startswith("sources"): continue
        d["run"] = run; out.append(d)
    return out[:limit]
def question_lines(d):
    # C51.1 (remainder of C51): the lines found for an answered question, read now: a source db row by its id (the text re-cut at read, C54), a typed source line replayed from its run,
    # the brain's own definitions (defined-words) by the word; a question closed before the pointers were kept (11-04 23:xx) is looked up again by its words
    lines = []; ptrs = list(d.get("found") or [])
    if not ptrs:
        for w in d.get("words") or []:
            body = w[6:] if w.startswith("pair: ") else w
            toks = [t for t in re.findall(r"[a-z][a-z0-9_']+", body.lower()) if t not in STOP]
            if not toks: continue
            for nm in [n for (n, b) in sources()]:
                if source_is_db(nm):
                    for (sid, t, p, l) in db_lines_holding(nm, toks, 1): ptrs.append({"w": w, "src": nm, "id": sid})
            if len(toks) == 1 and not w.startswith("pair: "): ptrs.append({"w": w, "src": "defined-words", "word": toks[0]})
    for p in ptrs:
        if p.get("id"):
            c = cx_db(); rows = list(c.execute("SELECT text, path, line FROM corpus WHERE id = ?", (p["id"],))); c.close()
            for (t, pa, l) in rows: lines.append((p["w"], p["src"], ("%s:%s" % (pa, l)) if pa else "row %d" % p["id"], t))
        elif p.get("run"):
            pa, l = source_line_of(p["src"], p["run"]); lines.append((p["w"], p["src"], ("%s:%s" % (pa, l)) if pa else "run %d" % p["run"], line_text(p["run"])))
        elif p.get("word"):
            for (run, v) in cxq("SELECT run, value FROM record WHERE kind = 'source' AND name = ? AND n > 0", p["src"]):
                try: dv = json.loads(v)
                except (ValueError, TypeError): continue
                if dv.get("word") == p["word"]: lines.append((p["w"], p["src"], "run %d from %s" % (run, dv.get("from")), line_text(run)))
    seen, out = set(), []   # a migrated source holds a line twice, as a db row and as its typed history run: print it once
    for L in lines:
        k = (L[0], (L[3] or "").strip().lower()[:120])
        if k in seen: continue
        seen.add(k); out.append(L)
    return out
def v_questions_answered(name):
    qs = answered_questions(name)
    print("questions of %s answered by the sources: %d" % (name, len(qs)))
    for d in qs:
        print("C%s run %d (%s): %s | answered %s%s" % (d.get("n"), d["run"], time.strftime("%m-%d %H:%M", time.localtime(d["ts"])), ", ".join(d.get("words") or []), time.strftime("%m-%d %H:%M", time.localtime(d.get("answered_ts") or d["ts"])), "" if d.get("found") else " (closed before the pointers were kept; looked up again by its words)"))
        L = question_lines(d)
        for (w, src, where, t) in L[:12]: print("  %s: %s %s: %s" % (w, src, where, (t or "")[:140]))
        if not L: print("  no line found now: the source that answered may be retired or its rows gone")
    print("%d answered questions of %s; the lines are re-read from the source db by row id, replayed from the run for a typed source (C51.1)" % (len(qs), name))
def kernel_define(word):
    # the brain's own dictionaries asked: define : <word>; the def rows of the run's out mailbox (run N from wn: <text>) are the definitions
    try: r = ask("type main define : %s" % word)
    except Exception: return []
    out = []
    for row in (r.get("out") or []):
        if len(row) >= 4 and row[2] == "def":
            m = re.match(r"run \d+ from (\w+): (.*)", str(row[3]), re.S)
            if m: out.append((m.group(1), m.group(2)))
    return out
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
def v_why(name, plan=False, quiet=False):
    # C49 (the owner, 11-04 15:3x: the sixth should see the trust drop the incorrect judgement and ask why did this happen, how did it happen, can it be fixed, do we have a plan,
    # then the cortex can register its own plan, ask the headless to build it): the verdicts of this project the record itself proves wrong, each with the cells that decided it
    # and the rule; --plan registers the cortex's own plan on the project cortex-self (a clone of the front door, built by the headless against the test brain on port 7010)
    faults = []
    vs = [(run, jload(v), ts) for (run, v, ts) in cxq("SELECT n, value, ts FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 400", name)]
    parts = {}
    for (k, v) in cxq("SELECT n, value FROM record WHERE kind = 'part' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 400", name):
        d = jload(v); parts.setdefault(d.get("run"), []).append(d)
    marks = {}
    for (k, v) in cxq("SELECT n, value FROM record WHERE kind = 'mark' AND name = ? AND n > 0 LIMIT 400", name): marks[k] = jload(v)
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
    if not quiet: print("why %s: %d verdicts of %d the record proves wrong%s" % (name, len(faults), len(vs), (": " + ", ".join("%s %d" % kv for kv in sorted(kinds.items(), key=lambda kv: -kv[1]))) if kinds else ""))
    for f in (faults[:30] if not quiet else []):
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
def judge_keep(test_cx):
    # the judge brain's tables (judge_*) exist only in the test kernel's cx.db; before a refresh copies the live cx.db over it, they are kept in a copy beside it
    import sqlite3
    if not os.path.exists(test_cx): return None
    c = sqlite3.connect("file:%s?mode=ro" % test_cx, uri=True); n = c.execute("SELECT count(*) FROM sqlite_master WHERE tbl_name LIKE 'judge%'").fetchone()[0]; c.close()
    if not n: return None
    keep = test_cx + ".judge-keep"; shutil.copy(test_cx, keep); return keep
def judge_restore(test_cx, keep):
    # the tables first, their rows, then the triggers (a trigger made before the rows would fire on them)
    import sqlite3
    c = sqlite3.connect(test_cx, timeout=60); c.execute("ATTACH DATABASE ? AS k", (keep,)); out = []
    objs = c.execute("SELECT type, name, sql FROM k.sqlite_master WHERE tbl_name LIKE 'judge%' AND sql IS NOT NULL").fetchall()
    for (ty, nm, sql) in [o for o in objs if o[0] == "table"]:
        c.execute("DROP TABLE IF EXISTS main.%s" % nm); c.execute(sql); c.execute("INSERT INTO main.%s SELECT * FROM k.%s" % (nm, nm))
        out.append("%s %d" % (nm, c.execute("SELECT count(*) FROM main.%s" % nm).fetchone()[0]))
    for (ty, nm, sql) in [o for o in objs if o[0] in ("index", "view")] + [o for o in objs if o[0] == "trigger"]: c.execute(sql); out.append("%s %s" % (ty, nm))
    c.commit(); c.execute("DETACH DATABASE k"); c.close()
    return "the judge brain carried over the copy (kept in %s): %s" % (os.path.basename(keep), ", ".join(out))
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
        lst = open(os.path.join(NK, "sources", "LIST")).read().split() if os.path.exists(os.path.join(NK, "sources", "LIST")) else "wn gcide mwt moby map sqldoc measured wikt cx".split()
        subprocess.Popen("cd %s && NK_MAP=%s/brain.map nohup ./nk 7010 egg-symbols.txt sources %s > %s/nk.log 2>&1 < /dev/null &" % (NK, T, " ".join(lst), T), shell=True)
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
        live_cx = os.path.join(HOME, "cortex", "nk", "sources", "cx.db")   # C54: the source db goes with the brain it answers
        test_cx = os.path.join(NK, "sources", "cx.db")
        if os.path.exists(live_cx):
            keep = judge_keep(test_cx)   # the judge brain lives only in the test kernel's source db (judge C1 to C3, rail C6): carried over the copy, never lost
            shutil.copy(live_cx, test_cx)
            if keep: print(judge_restore(test_cx, keep))
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
    track = os.path.abspath(os.path.expanduser(track))
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
def source_symbol(name):
    # the source's symbol in the brain: short (the kernel keeps a symbol short), unique by a hash tail
    slug = re.sub(r"[^a-z]+", "_", name.lower()).strip("_")   # letters only: the encoder ends a symbol at a digit
    tail = "".join(chr(97 + b % 26) for b in hashlib.sha256(name.encode()).digest()[:6])
    return "src_" + slug if (len(slug) <= 20 and re.sub(r"[^a-z0-9]+", "", name.lower()) == slug.replace("_", "")) else "src_" + slug[:14].strip("_") + "_" + tail
def source_gate(name):
    # the source's own symbol in the brain (born once), its gate kept in cx.me so a return carries it as its arrival
    sym = source_symbol(name); rows = q("SELECT gate FROM main.label WHERE symbol = ?", sym)
    if not rows:
        try: typed(sym)
        except RuntimeError: pass
        rows = q("SELECT gate FROM main.label WHERE symbol = ?", sym)
    if not rows: print("the source symbol %s has no gate; the source answers with gate 0 until it has one" % sym); return 0
    g = rows[0][0]; c = cx_db(); c.execute("INSERT OR REPLACE INTO me (source, gate) VALUES (?, ?)", (name, g)); c.commit(); c.close(); return g   # the source db's own row (its shape), written in the db
def source_is_db(nm):
    try: return bool(source_info(nm).get("db"))
    except Exception: return False
def source_holds_gate(nm, g):
    # the owner, 11-04 18:4x: all may stay until the replacement is built correct: a source grounds by its typed keys or by its db keys, both
    if source_is_db(nm):
        try: return bool(q("SELECT 1 FROM cx.words WHERE word = ? AND source = ? LIMIT 1", sym_of(g).lower(), nm))
        except RuntimeError: return False
    return True if cx_get("gate", nm, g) else None
def source_holds_pair(nm, a, b):
    if source_is_db(nm):
        try: return bool(q("SELECT 1 FROM cx.words x JOIN cx.words y ON y.id = x.id WHERE x.word = ? AND y.word = ? AND x.source = ? LIMIT 1", sym_of(a).lower(), sym_of(b).lower(), nm))
        except RuntimeError: return False
    return True if cx_get("pair", nm, pair_key(a, b)) else None
def cx_db_k(c):
    cols = [r[1] for r in c.execute("PRAGMA table_info(corpus)")]
    if "k" not in cols: c.execute("ALTER TABLE corpus ADD COLUMN k INTEGER"); c.execute("CREATE INDEX IF NOT EXISTS corpus_k ON corpus (k)"); c.commit()
def source_db_type(name, items, quiet=False, replace=False):
    # items: (sentence, path, line); the sentences into cx.db (corpus and words), the word and pair keys into the index; nothing typed into the brain
    t0 = time.time(); c = cx_db(); cx_db_k(c); cur = c.cursor(); n_typed = dupes = noise = 0; words_seen, pairs_seen = {}, {}
    for (sent, path, line) in items:
        if is_noise(sent): noise += 1; continue
        k = text_key(sent)
        if cur.execute("SELECT 1 FROM corpus WHERE k = ? AND source = ? LIMIT 1", (k, name)).fetchone(): dupes += 1; continue   # the db itself says repeat; a typed row of the same sentence stays as it is (the owner, 11-04 18:4x: all may stay until the replacement is built correct)
        cw = [w for w in re.findall(r"[a-z][a-z0-9_']+", sent.lower()) if w not in STOP]
        if not cw: noise += 1; continue
        cur.execute("INSERT INTO corpus (source, word, text, path, line, k) VALUES (?, ?, ?, ?, ?, ?)", (name, cw[0], sent, path, line, k)); sid = cur.lastrowid
        cur.executemany("INSERT INTO words (word, id, source) VALUES (?, ?, ?)", [(w, sid, name) for w in sorted(set(cw))])
        if not cx_get("source", name, k): cx_put("source", name, k, 0, clock(), json.dumps({"db": sid, "path": path, "line": line}) if path else json.dumps({"db": sid}))   # a typed row keeps its run; the db row stands beside it
        for w in set(cw): words_seen[w] = words_seen.get(w, 0) + 1
        for (a, b) in zip(cw, cw[1:]): pairs_seen["%s %s" % (a, b)] = pairs_seen.get("%s %s" % (a, b), 0) + 1
        n_typed += 1
        if n_typed % 2000 == 0:
            c.commit()
            if not quiet: print("  %d into the db, %.0f s" % (n_typed, time.time() - t0), flush=True)
    c.commit(); c.close()
    had = cx_get("source", name, 0); d = json.loads(had[3]); c2 = cx_db(); held = c2.execute("SELECT count(*) FROM corpus WHERE source = ?", (name,)).fetchone()[0]; c2.close()
    if held: d["db"] = True; d["db_lines"] = held
    else: d.pop("db", None); d.pop("db_lines", None)   # a source with nothing in the db is not a db source
    cx_put("source", name, 0, had[0], had[1], json.dumps(d)); _SRCD.pop(name, None)
    g = source_gate(name)
    if not quiet: print("source %s into cx.db: %d sentences, %d words keyed, %d pairs keyed, %d repeats, %d noise, gate %d, %.1f s; the brain run count did not grow" % (name, n_typed, len(words_seen), len(pairs_seen), dupes, noise, g, time.time() - t0))
    return n_typed
def v_source_db(name, band, text, domain, path=None, globs=None, from_brain=False, raw=None):
    if not cx_get("source", name, 0):
        if not text: raise SystemExit("register the source first: cortex source %s owner|reference --db : <what it is>" % name)
        v_source(name, band or "reference", text, domain or ["software"])
    items = []
    if from_brain:
        # the migration: a source typed as lines into the brain replayed from its runs into cx.db; the typed runs stay as history
        rows = cxq("SELECT n, run, value FROM record WHERE kind = 'source' AND name = ? AND n > 0 AND run > 0 LIMIT 400000", name)
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
    return source_db_type(name, items, replace=from_brain)
def db_rows_of(name, sids):
    if not sids: return {}
    c = cx_db(); out = {}
    for (sid, text, path, line, src) in c.execute("SELECT id, text, path, line, source FROM corpus WHERE id IN (%s)" % ",".join(str(int(s)) for s in sids)): out[sid] = (text, path, line, src)
    c.close(); return out
def v_ask_source(name, word, run=None):
    # cortex ask-source <name|all> <word or 'a b'> [--run R]: the request written into cx.inbox under run R; the returns read back as the return runs under R, each with its src row
    c = cx_db(); c.close()
    if run is None:
        run = record("ask", name, None, word)[0]
    gates = {row[1]: row[0] for row in q("SELECT source, gate FROM cx.me")}
    before = set(t["id"] for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3)
    run = NK_MEM(run)
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
# ---- C53 (the owner, 11-04 16:4x: a second police officer like the sixth to catch the things the judge misses; the llm asks for a second opinion; the sixth steps in and
#      calls the guessing, or the brain data on the topic, or the sources, or all three, to help the judge make a better ruling, or to inform the llm the data might not be
#      wrong but the way you shaped the data is: say the same thing in a more correct way). The ruling is typed on the sixth prompt, the sixth's own record. ----
def nearest_shape(name, n, run):
    # the line the brain holds nearest to the claim: the expected of C n or one of its parts, by shared content gates
    cg = set(g for g in content_gates(run) if not is_value(g)); best = (0, None, None)
    cands = []
    ex = cx_get("expected", name, n)
    if ex and ex[0]: cands.append(("the expected of C%s" % n, ex[0]))
    for p in parts_of(name, n): cands.append(("a part of C%s" % n, p["run"]))
    for (label, r0) in cands:
        og = set(g for g in content_gates(r0) if not is_value(g)); shared = len(cg & og)
        if shared > best[0]: best = (shared, label, r0)
    return best
def v_second(name, run, reason=None):
    row = cxq("SELECT value FROM record WHERE kind = 'verdict' AND name = ? AND n = ?", name, run)
    if not row: raise SystemExit("run %d has no verdict on %s" % (run, name))
    d = jload(row[0][0]); n = d.get("n"); kind, by, sh = d.get("kind"), d.get("judge"), d.get("sheet") or {}; text = line_text(run)
    print("second opinion on %s run %d (%s %.2f by %s): %s" % (name, run, kind, d.get("p") or 0, by, text[:120]))
    if reason: print("  the dispute: %s" % reason[:200])
    # read 1, the guessing brain (the owner, 11-02, neuron run 263885: "it is another neuron brain taught to be the guessing brain"; 10-23: it makes guesses of what a word
    # meaning should be, with time and state, and back-props when the sixth returns the word wrong with reasons): NOT BUILT (neuron C13 recorded the design; the kernel's
    # guesser was taken out 10-31). This read is empty until it exists; the dictionaries are sources, read 3, not the guessing (the owner, 11-04 18:xx: ask the cortex for the prose)
    none = [w for w in ((sh.get("ground") or {}).get("none") or []) if not w.startswith("pair")][:3]
    try: gb = line_text(263885)[:150]
    except Exception: gb = ""
    r1 = "not built (neuron C13 holds the design: %s); the words with no ground it would guess at: %s" % (gb or "the owner 11-02", ", ".join(none) or "none")
    print("  1 the guessing brain: " + r1)
    # read 2, the project record
    pg = pair_ground(name, run); mem = pg.get("memory") or {}; held_mem = max(mem.values()) if mem else 0; np_ = pg.get("pairs") or 0
    shared, label, r0 = nearest_shape(name, n, run); shape_line = line_text(r0)[:160] if r0 else ""
    r2 = "%d of %d pairs held by the record (%s); nearest shape %s, %d gates shared: %s" % (held_mem, np_, " ".join("%s %d" % kv for kv in sorted(mem.items(), key=lambda kv: -kv[1])[:3]) or "none", label or "none", shared, shape_line[:100])
    print("  2 the project record: " + r2)
    # read 3, the sources
    held = pg.get("held_by") or {}; top = sorted(held.items(), key=lambda kv: -kv[1])[:4]; found = []
    for nm, cnt in top:
        if source_is_db(nm):
            for (a, b) in pairs_of(run)[:16]:
                rows = db_lines_holding(nm, [sym_of(a), sym_of(b)], 1)
                if rows: found.append("%s %s:%s %s" % (nm, rows[0][2] or "-", rows[0][3] or "-", rows[0][1][:70])); break
    defs = []
    for w in none[:2]:
        d0 = kernel_define(w)
        if d0: defs.append("%s = %s: %s" % (w, d0[0][0], d0[0][1][:70]))
    r3 = "%s hold %s of %d pairs%s%s" % (", ".join("%s %d" % kv for kv in top) or "no source", "/".join(str(c) for nm, c in top) or "0", np_, ("; " + "; ".join(found)) if found else "", ("; the kernel's dictionaries: " + "; ".join(defs)) if defs else "")
    print("  3 the sources (the dbs and the kernel's dictionaries): " + r3)
    # the ruling: a machine print the judge read is not overruled; data a source or the record holds moves an off rail verdict to unsettled
    src_half = bool(top) and top[0][1] * 2 >= np_ > 0; mem_half = np_ > 0 and held_mem * 2 >= np_; moved = False
    if kind in ("invention", "hallucination", "drift") and by == "receipt" and sh.get("numbers_out"): ruling = "the judge stands: no print holds %s, and a source cannot stand in for the machine's print; pipe the print, then say it again" % ", ".join(sh["numbers_out"][:4])
    elif kind in ("invention", "hallucination", "drift") and (src_half or mem_half): ruling = "the data is held by %s: the verdict moves to unsettled by the sixth; the judge's call stays as history" % ("the sources " + ", ".join(nm for nm, c in top[:2]) if src_half else "the project record"); moved = True
    elif kind in ("invention", "hallucination", "drift"): ruling = "the judge stands: neither a source nor the record holds the data; the words with no ground: %s" % (", ".join(none) or "-")
    else: ruling = "the verdict was %s by %s; nothing to overrule, but the shape below is the one the brain holds" % (kind, by)
    shape = ("the brain holds this shape (%s): %s | your values: %s" % (label, shape_line, ", ".join(sh.get("numbers") or []) or "none")) if r0 else "no shape held yet for C%s" % n
    print("  ruling: " + ruling); print("  say it this way: " + shape)
    body = "run %d: %s | %s" % (run, ruling[:200], shape[:200])
    try: srun = ask("type sixth cortex second %s %d : %s" % (name, run, clean(body))).get("run") or 0
    except Exception: srun = 0
    cx_put("second", name, run, srun, clock(), json.dumps({"n": n, "ruling": ruling, "shape": shape, "reads": [r1[:300], r2[:300], r3[:300]], "moved": moved, "reason": (reason or "")[:300], "ts": int(time.time()), "sixth_run": srun}))
    if moved:
        v_judge(name, n, run, answers_given={"unsettled": 0.7}, judge_name="sixth")
    print("  the ruling typed on the sixth as run %d" % srun)
    return ruling, shape
def v_dispute(name, run, reason):
    record("dispute", name, run, clean(reason)[:400]); return v_second(name, run, reason)
# ---- C55 (the owner, 11-04 16:4x: why did, why does, how did, how does, when did, when is, when does, what should be done next): the question word routes to the record ----
def state_hist(name, n):
    # the state history of a checkpoint as a list (the row holds a list, or a dict with the list under hist or history); the state row itself when the history is empty
    st = cx_get("states", name, n); hist = []
    if st:
        h = jload(st[3]); hist = h if isinstance(h, list) else ((h.get("hist") or h.get("history") or []) if isinstance(h, dict) else [])
    if not hist:
        s0 = cx_get("state", name, n)
        if s0: hist = [{"state": s0[3], "run": s0[0], "at": s0[1], "ts": s0[2]}]
    return hist
def v_askq(name, qtext):
    t = qtext.lower().strip().rstrip("?"); reads = []
    m_run = re.search(r"\brun\s+(\d+)", t); m_c = re.search(r"\bc\s?(\d+)\b", t)
    if t.startswith("why"):
        if m_run:
            run = int(m_run.group(1)); row = cxq("SELECT value FROM record WHERE kind = 'verdict' AND name = ? AND n = ?", name, run)
            if not row: print("run %d has no verdict on %s" % (run, name)); return
            d = jload(row[0][0]); sh = d.get("sheet") or {}
            print("why run %d got %s by %s (C%s): numbers out %s | words out %s | no ground for %s | measure missing %s | shape of the expected %.2f | sources confirm %d disagree %d" % (run, d.get("kind"), d.get("judge"), d.get("n"), ",".join(sh.get("numbers_out") or []) or "-", ",".join((sh.get("words_out") or [])[:8]) or "-", ",".join((sh.get("ground") or {}).get("none") or []) or "-", ",".join(sh.get("measure_missing") or []) or "-", sh.get("shape_expected") or 0, len((sh.get("sources") or {}).get("confirm") or []), len((sh.get("sources") or {}).get("disagree") or [])))
            for f in v_why(name, quiet=True):
                if f["run"] == run: print("  and the record proves it wrong: %s | %s" % (f["why"], f["cells"]))
            sec = cx_get("second", name, run)
            if sec: print("  the sixth ruled: %s" % jload(sec[3]).get("ruling", "")[:200])
            reads = ["the verdict row", "cortex why", "the sixth's record"]
        elif m_c:
            n = int(m_c.group(1)); vs = [(r, jload(v)) for (r, v) in cxq("SELECT n, value FROM record WHERE kind = 'verdict' AND name = ? AND n > 0 ORDER BY n DESC LIMIT 300", name)]
            mine = [(r, d) for (r, d) in vs if d.get("n") == n][:8]
            print("why C%d stands as it does: %d verdicts; the newest: %s" % (n, len(mine), " | ".join("run %d %s by %s" % (r, d.get("kind"), d.get("judge")) for (r, d) in mine[:5])))
            for f in v_why(name, quiet=True):
                if f["n"] == n: print("  the record proves run %d wrong: %s" % (f["run"], f["why"]))
            reads = ["the verdict rows of C%d" % n, "cortex why"]
        else:
            fs = v_why(name, quiet=True); print("why, over %s: %d verdicts the record proves wrong: %s" % (name, len(fs), "; ".join("run %d %s" % (f["run"], f["why"]) for f in fs[:6]) or "none")); reads = ["cortex why"]
    elif t.startswith("how"):
        if m_c:
            n = int(m_c.group(1)); sched = [v for (k, r, a, ts, v) in cx_list("schedule", name) if (" C%d " % n) in (v or "")]
            print("how C%d moved: %d build turns%s" % (n, len(sched), (": " + " | ".join(s[:110] for s in sched[-4:])) if sched else ""))
            for p in parts_of(name, n)[:6]: print("  part by %s p%.2f: %s" % (p.get("by") or "-", p.get("p") or 0, line_text(p["run"])[:100]))
            hist = state_hist(name, n)
            if hist: print("  states: " + " -> ".join("%s %s" % (h.get("state"), time.strftime("%m-%d %H:%M", time.localtime(h.get("ts") or 0))) for h in hist[-6:]))
            reads = ["the schedule lines", "the parts of C%d" % n, "the state history"]
        elif m_run:
            run = int(m_run.group(1)); x = ask("run main %d" % run); r = x.get("run") or {}; kids = x.get("tree") or []
            print("how run %d went: arrival %s, kind %s, %s hops, ended %s, %d runs in its tree (%d returns), text: %s" % (run, r.get("arrival"), r.get("kind"), r.get("hops"), r.get("ended"), len(kids), sum(1 for k in kids if k.get("kind") == 3), (r.get("text") or "")[:100]))
            reads = ["run main %d" % run]
        else: print("how: name a checkpoint (C n) or a run (run N)")
    elif t.startswith("when"):
        if m_c:
            n = int(m_c.group(1)); hist = state_hist(name, n)
            if hist: print("when C%d: " % n + " -> ".join("%s at %s" % (h.get("state"), time.strftime("%m-%d %H:%M", time.localtime(h.get("ts") or 0))) for h in hist))
            else:
                s0 = cx_get("state", name, n); print("when C%d: %s since %s (no history yet; cortex states --backfill)" % (n, s0[3] if s0 else "open", time.strftime("%m-%d %H:%M", time.localtime(s0[2])) if s0 else "-"))
            reads = ["the state history of C%d" % n]
        else:
            words = [w for w in t.split()[1:] if w not in ("was", "is", "did", "does", "the", "state", "of", name)]
            v_at(name, words or ["today"]); reads = ["cortex at"]
    elif "next" in t:
        nw = next_work(name); print("what next on %s: " % name + ("C%d.%d %s" % nw if nw else "nothing of the front door's; the rest wait on the kernel or the owner")); reads = ["the remainder"]
    elif t.startswith("what is") or t.startswith("what does") or t.startswith("what are"):
        w = re.sub(r"^what (is|does|are)( an?| the)? ", "", t).split(" mean")[0].strip(); toks_ = [x for x in re.findall(r"[a-z][a-z0-9_']+", w) if x not in STOP]
        defs = kernel_define(toks_[0]) if toks_ else []
        print("what is %s: %s" % (w, ("; ".join("%s: %s" % (f, d0[:90]) for f, d0 in defs[:3])) if defs else "no definition in the brain's dictionaries"))
        for (nm, band) in sources():
            if source_is_db(nm):
                for (sid, txt, p, l) in db_lines_holding(nm, toks_[:2], 1): print("  %s %s:%s %s" % (nm, p or "-", l or "-", txt[:110]))
        reads = ["define", "the source dbs"]
    else: print("not routed yet: ask why did/does (run N or C n), how did (C n or run N), when did (C n) or when is (a day), what next, what is <word>")
    if reads: print("  reads: " + ", ".join(reads))
# ---- C57 / the project teach (the owner, 11-04 18:4x: all may stay until you build the replacement correct, better until neuron builds the replacement on its own without
#      any help from you; caveat you have to teach it to do this): a lesson = a brain function the front door does outside the brain; the brain's own answer is read from
#      its runs, the front door's answer taken on the same inputs, the two printed side by side; retired only on the owner's word (cortex retire) ----
def teach_inputs(name, k, kind="ingest"):
    import random
    rows = cxq("SELECT n, run, value FROM record WHERE kind = ? AND name = ? AND n > 0 AND run > 0 LIMIT 400", kind, name)
    random.shuffle(rows); out = []
    for (n, run, v) in rows:
        t = line_text(run)
        if t and len(t) > 20: out.append((run, t))
        if len(out) >= k: break
    return out
def brain_know(run):
    rows = q("SELECT value FROM main.run_sheet WHERE run = ? AND cell = 26", run)
    return rows[0][0] if rows else None
def source_gates():
    return {row[1]: row[0] for row in q("SELECT source, gate FROM cx.me")}
def brain_pairs_held(name, run):
    # the brain's own ask: every pair of the claim into cx.inbox under the claim's run; the returns laid under it, one per source row holding the pair; counted per source as pairs held
    gates = source_gates(); before = set(t["id"] for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3); held = {}
    dbs = [nm for (nm, band) in sources() if source_is_db(nm)]
    for (a, b) in set(pairs_of(run)):
        w = "%s %s" % (sym_of(a), sym_of(b))
        for nm in dbs: q("INSERT INTO cx.inbox (run, cell, about, word, source) VALUES (?, 24, 0, ?, ?)", NK_MEM(run), w, nm)   # one ask per source: the trigger answers at most 24 rows per ask, so a common pair is not starved by the first sources
        time.sleep(0.05)
        kids = [t for t in (ask("run main %d" % run).get("tree") or []) if t.get("kind") == 3 and t["id"] not in before]
        for t in kids: before.add(t["id"])
        for nm in set(gates.get(t.get("arrival")) for t in kids if gates.get(t.get("arrival"))): held[nm] = held.get(nm, 0) + 1
    return held
def v_teach(function, k=5, name="cortex"):
    rows = []; equal = 0; total = 0
    if function == "dupe":
        import random
        lines = cxq("SELECT n, run, value FROM record WHERE kind = 'line' AND name = '*' AND n > 0 AND run > 0 LIMIT 600"); random.shuffle(lines); picked = []
        for (n0, run0, v0) in lines:
            t0_ = line_text(run0)
            if t0_ and len(t0_) > 20: picked.append((run0, t0_))
            if len(picked) >= k: break
        for (run, t) in picked:   # the lesson taught 11-04 20:4x: the brain keys a repeat by the whole typed line (its prefix too), the front door by the sentence; the lesson re-types the line as the brain saw it
            full = (ask("run main %d" % run).get("run") or {}).get("text") or ("cortex ingest : %s" % t)
            try: kr = typed(full)["run"]
            except RuntimeError: continue
            rr = run_row(kr); brain = (rr[1] or 0) if rr else 0
            fd = run   # C30: the sentence's one run is the line row we picked; the brain must answer that run as same_as when the line is typed again
            total += 1; eq = brain == fd and brain > 0; equal += 1 if eq else 0
            if not eq and brain == 0: noround = locals().get("noround", 0) + 1; locals()["noround"] = noround   # the brain saw a new line: its own decode of the run does not round-trip the encoder (apostrophes, decimals); the hp builder's encoder work
            rows.append("brain same_as %d | front door first run %d | %s | %s" % (brain, fd, "equal" if eq else ("not replayable by the encoder, the brain saw a new line" if brain == 0 else "differ"), t[:70]))
    elif function == "pairs":
        dbs = [nm for (nm, band) in sources() if source_is_db(nm)]
        for (run, t) in teach_inputs(name, k):
            fd = {}
            for (a, b) in set(pairs_of(run)):
                for nm in dbs:
                    if db_lines_holding(nm, [sym_of(a), sym_of(b)], 1): fd[nm] = fd.get(nm, 0) + 1   # the front door reads the db directly; the brain asks through its inbox and lays the returns
            brain = brain_pairs_held(name, run)
            total += 1; eq = brain == fd; equal += 1 if eq else 0
            rows.append("run %d: brain %s | front door %s | %s | %s" % (run, " ".join("%s %d" % kv for kv in sorted(brain.items())) or "none", " ".join("%s %d" % kv for kv in sorted(fd.items())) or "none", "equal" if eq else "differ", t[:60]))
    elif function == "known":
        pr = cx_get("project", name, 0)
        for (run, t) in teach_inputs(name, k):
            kn = brain_know(run) or "-"
            words = [sym_of(x) for x in content_gates(run) if not is_value(x)]; srcs = [nm for (nm, band) in sources()]
            none = [sym_of(x) for x in content_gates(run) if not is_value(x) and not any(source_holds_gate(nm, x) for nm in srcs)]
            try: known_n, all_n = [int(x) for x in kn.split("/")]
            except Exception: known_n, all_n = 0, len(words)
            unknown_n = max(0, all_n - known_n); overlap = min(unknown_n, len(none))
            total += 1
            rows.append("run %d: brain know %s (unknown %d) | front door no ground %d: %s | overlap at most %d | %s" % (run, kn, unknown_n, len(none), ", ".join(none[:5]) or "-", overlap, t[:50]))
    elif function == "words":   # C59 (the owner 11-05 18:21): the line as the encoder laid it, runs inside the run, beside the front door cut
        laid = thrown = 0
        for (run, t) in teach_inputs(name, k):
            W = run_words(run); c_ = enc_cells(run, {}); lost = _ENC_DROPPED.get(run, [])
            total += 1; laid += c_["neurons"]; thrown += len(lost)
            rows.append("run %d: the encoder %d neurons in %d words | the cut keeps %d words and throws away %d neurons: %s | %s" % (run, c_["neurons"], len(W), len(content_words(t)), len(lost), " ".join(lost[:14]) or "-", t[:50]))
        rows.append("in all: the encoder laid %d neurons, the cut threw away %d" % (laid, thrown))
    else: raise SystemExit("teach dupe|pairs|known|words")
    print("teach %s on %s, %d inputs at random:" % (function, name, total))
    for r in rows: print("  " + r)
    if function == "dupe":
        nr = sum(1 for r in rows if "not replayable" in r); print("equal %d of %d, %d differ, %d not replayable by the encoder" % (equal, total, total - equal - nr, nr))
    elif function == "pairs": print("equal %d of %d" % (equal, total))
    else: print("measured %d of %d (a measure, not a replacement)" % (total, total))
    body = "lesson %s: %d inputs, %s" % (function, total, ("equal %d of %d" % (equal, total)) if function in ("dupe", "pairs") else "measured")
    try: record("lesson", "teach", None, clean(body))
    except RuntimeError: pass
    return equal, total
def v_retire(function, words):
    # the owner's word only: the front door reads the brain's answer alone for this function from now on
    cx_put("retired", "teach", text_key(function), 0, clock(), json.dumps({"function": function, "owner": words[:300], "ts": int(time.time())}))
    try: record("retire", "teach", None, clean("%s : %s" % (function, words)))
    except RuntimeError: pass
    print("retired from the front door on the owner word: %s; the brain answers it alone now" % function)
def retired_functions():
    out = []
    for (n, run, at, ts, v) in cx_list("retired", "teach"):
        try: out.append(json.loads(v).get("function"))
        except Exception: pass
    return [x for x in out if x]
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
    name = "lesson-senses"
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
            r = ask_learner("type main define : %s" % w); run = r.get("run") or 0; g = learner_gate(w); nsense = 0
            for i in range(10):   # the define run fills its sense cell from the returns; read it when it is there, up to five seconds
                cells = [c for c in (ask_learner("run main %d" % run).get("cells") or []) if c[0] == 187]; nsense = len((cells[0][2] or "").split()) if cells and cells[0][2] else 0
                if nsense: break
                time.sleep(0.5)
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
# ---- jev C2 (the owner, 11-09 01:30: cortex decides what to hydrate you with based on your ask): the hydration by the ask, bounded; the state, the source rows the ask
#      and the project's open work need (best by rarity, a few per source), the record lines that hold an ask word; never the whole record ----
ASK_GENERIC = set("build built make made get give tell show find need needs want use using used what which who how why when where one two new all any each every more most other some such own same way thing things part parts like".split())
def ask_words(text):
    return [w for w in dict.fromkeys(re.findall(r"[a-z][a-z0-9_']+", (text or "").lower())) if w not in STOP and len(w) > 1]
REFLIST = re.compile(r"\bin proc\b|\bproceedings of\b|\bet al\.?,? \(?(19|20)\d\d|\barxiv[: ]\d|\bdoi\b|\bpp\. \d|\bvol\. \d|^\s*\[\d+\]")
def hydration_ask(name, question, cap=12000, ask_cap=8, other_cap=2):
    import sqlite3, math
    pr = cx_get("project", name, 0)
    if not pr: raise SystemExit("no project " + name)
    t0 = time.time(); aw = [w for w in ask_words(question) if w not in ASK_GENERIC] or ask_words(question)
    cps = cx_list("checkpoint", name); states = {n: (cx_get("state", name, n) or (0, 0, 0, "open"))[3] for (n, run, at, ts, text) in cps}
    cw = []
    for (n, run, at, ts, text) in cps:
        if states[n] != "done": cw += ask_words(text)
    cw = [w for w in dict.fromkeys(cw) if w not in aw and w not in ASK_GENERIC]
    sw = [w for w in dict.fromkeys(ask_words(pr[3])) if w not in aw and w not in cw and w not in ASK_GENERIC]   # the scope is the owner's speech: its words steer least
    routed = [nm for (nm, b) in routed_sources(name) if source_is_db(nm)]
    nxt = next_checkpoint(name); st = ["PROJECT %s: %s" % (name, pr[3][:700])]
    for (n, run, at, ts, text) in cps:
        ex = cx_get("expected", name, n); st.append("  C%d [%s]%s %s%s" % (n, states[n], " NEXT" if n == nxt else "", text[:220], (" || expected: " + ex[3][:160]) if ex else ""))
    groups, cand, weight, total, nopath, dropped = {}, {}, {}, 1, 0, 0
    if routed:
        c = sqlite3.connect("file:%s?mode=ro" % cx_db_path(), uri=True, timeout=30); ph = ",".join("?" * len(routed))
        total = c.execute("SELECT count(*) FROM corpus WHERE source IN (%s)" % ph, routed).fetchone()[0] or 1
        for (w, base) in [(w, 1.0) for w in aw[:12]] + [(w, 0.4) for w in cw[:50]] + [(w, 0.2) for w in sw[:40]]:
            ids = [i for (i,) in c.execute("SELECT id FROM words WHERE word = ? AND source IN (%s) LIMIT 6000" % ph, [w] + routed)]
            if not ids or len(ids) > total * 0.08: continue   # a word in more than 8 of 100 rows tells nothing
            weight[w] = base * math.log(total / len(ids))
            for i in ids: cand.setdefault(i, set()).add(w)
        top = sorted(cand.items(), key=lambda kv: -sum(weight[w] for w in kv[1]))[:1500]
        got = {}
        if top:
            for (i, src, path, line, text) in c.execute("SELECT id, source, path, line, text FROM corpus WHERE id IN (%s)" % ",".join(str(int(i)) for i, _ in top)): got[i] = (src, path, line, text)
        c.close()
        scored = []
        for i, ws in top:
            if i not in got: continue
            src, path, line, text = got[i]
            if not path or line is None: nopath += 1; continue   # a row is given with its path and line, or not at all
            hasask = [w for w in ws if w in aw]
            if len(text) < 40 or REFLIST.search(text) or (len(ws) < 2) or (not hasask and len(ws) < 3): dropped += 1; continue
            nw = len([w for w in ask_words(text) if w not in ASK_GENERIC])
            scored.append((sum(weight[w] for w in ws) / math.sqrt(max(8, nw) / 8.0), bool(hasask), src, path, line, text))
        seen, per = set(), {}
        for (sc, hasask, src, path, line, text) in sorted(scored, key=lambda x: -x[0]):
            k = re.sub(r"[^a-z]+", "", text.lower())[:120]
            if k in seen: continue
            if per.get((src, hasask), 0) >= (ask_cap if hasask else other_cap): continue
            seen.add(k); per[(src, hasask)] = per.get((src, hasask), 0) + 1; groups.setdefault(src, []).append((sc, path, line, text))
    rec = []
    pwset = set(cw) | set(sw)
    if aw:
        def keep(t, w): return len((set(ask_words(t)) & pwset) - {w}) >= 2   # a record line holds an ask word and two of the project's words
        for (rn,) in cxq("SELECT run FROM record WHERE kind = 'ingest' AND name = ? AND n > 0 ORDER BY ts DESC LIMIT 120", name):
            t = line_text(rn)
            if t and set(ask_words(t)) & set(aw): rec.append("run %d (ingest): %s" % (rn, t[:240]))
        for kind in ("need", "handback"):
            for (n, run, at, ts, v) in cx_list(kind, name):
                if set(ask_words(v)) & set(aw): rec.append("%s %s C%d: %s" % (kind, name, n, re.sub(r"\s+", " ", v)[:240]))
        owners = [nm for (nm, b) in sources() if b == "owner"]
        for w in aw[:6]:
            g = gate_of(w)
            if not g: continue
            for nm in owners:
                had = cx_get("gate", nm, g)
                if not had: continue
                try: d = json.loads(had[3])
                except ValueError: continue
                for rn in sorted(set([d.get("first"), d.get("last")]) - {None}):
                    t = line_text(rn)
                    if t and keep(t, w): rec.append("run %d (owner source %s, holds %s): %s" % (rn, nm, w, t[:240]))
    rec = list(dict.fromkeys(rec)); nrows = sum(len(v) for v in groups.values())
    head = ["ASK %s: %s" % (name, question),
            "THE CORTEX READ (jev C2): ask words %s; the open checkpoints' words %s; the scope's words weigh least; %d routed source dbs (%s), %d rows, %d candidates; %d rows kept from %d sources (at most %d per source holding an ask word, %d otherwise), %d left out with no path, %d left out as reference lists, fragments or one word; %d record lines; %.1f s" % (", ".join(aw) or "-", ", ".join(w for w in cw if w in weight)[:240] or "-", len(routed), ",".join(routes().get(name) or []) or "every source", total, len(cand), nrows, len(groups), ask_cap, other_cap, nopath, dropped, len(rec), time.time() - t0),
            "STATE:"] + st
    body = "\n".join(head) + "\n"
    out_rec = ["RECORD LINES holding an ask word (the project's own lines; the owner's lines that also hold two of the project's words):"] if rec else []
    tail = "LAWS: report only what you observed as live output; never invent a result, a term, a file or a source row; a row not printed here is not in your hydration."
    room = cap - len((body + tail).encode()) - 200
    rec_room = min(2500, room // 4) if rec else 0
    for r in rec:
        if len(("\n".join(out_rec) + r).encode()) > rec_room: break
        out_rec.append("  " + r)
    room -= len("\n".join(out_rec).encode())
    # the rows grouped by source, the sources in the order of their best row; the budget is spent best row first across all sources
    order = sorted(groups, key=lambda s0: -max(x[0] for x in groups[s0])); flat = sorted([(x[0], s0, x) for s0 in groups for x in groups[s0]], key=lambda y: -y[0])
    picked, used = {}, len("SOURCE ROWS".encode()) + 80
    for (sc, s0, (sc2, path, line, text)) in flat:
        ln = "    %s:%s: %s" % (path, line, re.sub(r"\s+", " ", text)[:340])
        extra = len(ln.encode()) + 1 + (0 if s0 in picked else len(s0) + 4)
        if used + extra > room: continue
        picked.setdefault(s0, []).append(ln); used += extra
    out_rows = ["SOURCE ROWS (source, then path:line: the row; the sources in the order of their best row for the ask):"]
    for s0 in order:
        if s0 in picked: out_rows.append("  " + s0); out_rows += picked[s0]
    if len(out_rows) == 1: out_rows.append("  (none: no routed source db holds the ask's words%s)" % ("" if routed else "; the project routes to no db source: cortex route %s <domains>" % name))
    return body + "\n".join(out_rows) + "\n" + ("\n".join(out_rec) + "\n" if len(out_rec) > 1 else "") + tail + "\n"
def v_route(name=None, doms=None):
    # a project routes to the domains its claims are about (C36); the liaison sets it for a new project
    R = routes()
    if name and doms is not None:
        R[name] = doms; cx_put("routes", "judge", 0, 0, clock(), json.dumps(R)); print("route %s -> %s" % (name, ",".join(doms)))
        n = len([1 for (nm, b) in routed_sources(name) if b == "reference" and set(source_info(nm).get("domain") or []) & set(doms)])
        print("%s now counts %d reference sources" % (name, n))
    else: print("routes: " + "; ".join("%s -> %s" % (k, ",".join(v)) for k, v in R.items() if k != "note"))
# ---- jev C3: the outline built by a claude exec turn from the ask hydration alone (an empty folder, no tools granted); every row it names must be a row the hydration printed ----
ASKPLAN_PROMPT = """You write the outline of a build for the cortex, a persistent memory that prescribes one checkpoint at a time to a headless worker and closes a checkpoint only when a check the cortex runs itself prints check ok.
Your whole context is the hydration below: the project's state and the source rows the cortex chose for the ask. You have no other source: do not search, fetch or read anything else; this folder is empty.

{HYD}
WRITE THE OUTLINE of what is left to build for project {NAME}, as {LO} to {HI} checkpoints in build order, numbered from {N0}. Each checkpoint is exactly one line:
checkpoint <n> : <what is built, one sentence, ending with the source rows it rests on as (source path:line)> || <the live output that proves it: the command run and what it prints, with the values it must print>
Rules: every source row you name is one printed above, as source path:line exactly; an expected output is a print a machine check can run on random inputs, never a test name, a summary or an intent; the first checkpoint is the smallest piece that prints; every later one uses what the earlier ones built; build on what the state says exists and do not repeat a checkpoint that is there; stay inside the scope; no other text, no headings, no code.
"""
def v_plan_ask(name, question, engine="claude", model=None, lo=4, hi=9):
    pr = cx_get("project", name, 0)
    if not pr: raise SystemExit("no project " + name)
    hyd = hydration_ask(name, question)
    cps = cx_list("checkpoint", name); n0 = (max(n for (n, run, at, ts, text) in cps) + 1) if cps else 1
    if model is None: model = MODEL_BY_KIND.get("design", "opus") if engine == "claude" else "default"
    cwd = os.path.join(RAILDIR, "%s-plan-ask" % name)
    if os.path.exists(cwd): shutil.rmtree(cwd)
    os.makedirs(cwd)
    prompt = fill(ASKPLAN_PROMPT, HYD=hyd, NAME=name, N0=n0, LO=lo, HI=hi)
    print("plan %s --ask %r: the hydration %d bytes, the design worker %s %s in an empty folder, prompt %d bytes" % (name, question, len(hyd.encode()), engine, model, len(prompt.encode())))
    out, err, rc, secs = worker(engine, model, prompt, cwd, False)
    if rc != 0 or not out.strip(): print("worker stderr: " + err[-600:]); raise SystemExit("the design worker failed, nothing typed")
    printed, cur = set(), None
    for l in hyd.split("\n"):
        m0 = re.match(r"^  (\S+)$", l); m1 = re.match(r"^    (\S+?:\d+): ", l)
        if m0: cur = m0.group(1)
        elif m1 and cur: printed.add("%s %s" % (cur, m1.group(1)))
    got, refused = [], []
    for m in re.finditer(r"(?mi)^\s*checkpoint\s+(\d+)\s*:\s*(.+?)\s*\|\|\s*(.+?)\s*$", out):
        n, text, exp = int(m.group(1)), m.group(2), m.group(3)
        named = re.findall(r"([a-z0-9][a-z0-9.\-]+ [^\s():,;]+?:\d+)", text)
        bad = [x for x in named if x not in printed]
        if not named: refused.append("C%d names no source row" % n); continue
        if bad: refused.append("C%d names rows the hydration did not print: %s" % (n, ", ".join(bad[:3]))); continue
        if cx_get("checkpoint", name, n): refused.append("C%d exists already" % n); continue
        v_checkpoint(name, n, "%s (jev C3: written by %s %s from the hydration of the ask: %s)" % (text, engine, model, question), exp); got.append(n)
    record("planask", name, n0, clean("the outline of %s from the ask %s was written by %s %s in %d s from a hydration of %d bytes: %d checkpoints typed open (%s), %d refused%s" % (name, question, engine, model, secs, len(hyd.encode()), len(got), " ".join("C%d" % x for x in got), len(refused), ("; " + "; ".join(refused)[:300]) if refused else "")))
    print("plan %s --ask: %d checkpoints typed open in %.0f s (%s)%s" % (name, len(got), secs, " ".join("C%d" % x for x in got), ("; refused: " + "; ".join(refused)) if refused else ""))
    if not got: print("--- the design worker's output (first 2000 bytes) ---"); print(out[:2000])
    return got
USAGE = """cortex <verb> ...
  senses plan|lecture|problems|reteach|test|quiz [--n k]   the project lesson-senses: a lesson the brain takes the way a human is taught; the learner on CORTEX_LEARNER (7010), the key in wn.db read by the judge only
  teach dupe|pairs|known [--n k] [--project p]   C57 / teach: a lesson the brain takes: its own answer beside the front door answer on k random inputs; equal k of k
  retire <function> : <the owner words>   teach C5: the owner word; the front door reads the brain answer alone for that function
  second <project> <run>          C53: the sixth's second opinion on a verdict: the guessing, the project record, the sources; a ruling and the shape the brain holds
  dispute <project> <run> : <why>   C53: the llm disputes a verdict; the sixth rules
  ask <project> <question>        C55: why did (run N | C n), how did (C n | run N), when did (C n), when is <day>, what next, what is <word>
  source <name> reference --db [--path <folder> [--glob a,b] | --from-brain | -] : <what>   C54: a source into cx.db (the attached source db), keyed by word and pair in the index; nothing typed into the brain
  ask-source <name|all> <word or "a b"> [--run R]   C54: the request in cx.inbox, the returns laid as return runs under R with their src rows
  sources --migrate [--box min]   C54: every reference source typed as lines moved into cx.db
  lesson <project> <track folder> [--ladder 1,2,3,4,5,6 | --pick slug,slug]   C52: a public teaching track as an outline, the key held by the cortex
  why <project> [--plan]        C49: the verdicts the record proves wrong, with the cells and the rule; --plan registers the cortex own plan on cortex-self
  self start|stop|refresh       the test system: the cascade kernel on 7010 over a copy of the live brain
  source <name> reference --path <folder> [--glob a,b] : <what>   C50: a code base docs and code typed with paths
  questions <project> --ask     C51: the open questions asked of the sources
  questions <project> --answered   C51.1: the questions the sources answered, each with its lines found re-read now (source, file:line or run, the line)
  project <name> : <scope>                 the project's scope line
  checkpoint <name> <n> : <text> [|| <expected>] [--kind read|write|design|judgment]
  state <name> <n> open|working|done
  ingest <name> <text | ->                 sentences typed as cortex ingest lines (- reads stdin)
  judge <name> <n> <run>                   verdict on an ingested run against checkpoint n
  hydrate <name> [--at n]                  the next worker's whole prompt
  hydrate <name> --ask <question>          jev C2: the state, the source rows and record lines the ask and the open work need, bounded (12 kb)
  plan <name> --ask <question> [--model m]   jev C3: the design worker writes the outline from that hydration alone; a checkpoint naming a row it was not given is refused
  route [<project> <a,b>]                  the domains a project routes to (C36)
  turn <name> [--engine claude|codex] [--model m] [--act]   hydrate, one worker turn, ingest, judge, move
  plan <name> <repo path> [--engine e] [--model m] [--scope s]   C43: the repo's own words typed as an owner source; a design worker writes the outline; typed open; read it before build
  build <name> [--box min] [--turns k] [--engine e] [--model m] [--no-act]   C44: hydrate, one headless turn on the hydration alone, ingest, judge, move, again; NEEDED grows the hydration; FLAW parks and hands back
  handbacks <name>                         C45: the parked flaws with the worker's text
  decide <name> <k> accept|reject|checkpoint [: <text> || <expected>]   C45: the owner's or the liaison's decision; the checkpoint unparks; build continues
  recall <project> [<kind> ...] [from <unix> to <unix>]   the project's records in time order, read from the tree by key (the owner, 11-03: a time state read ... recall print)
  status [<name>]
  verdicts <name> [n] [--limit k]          every judged line of the project (or of checkpoint n), newest first: run, verdict, p, judge, when, part, mark, ground, sentence
  receipt <name> <n> <command ...>         the machine's own print on stdin (df -h / | cortex receipt audit 1 df -h /): the checkpoint's ground for values
  source <name> owner|reference : <text>   register a source (the owner's words, a textbook, code docs; say where from and as of); then
  source <name> -                          type the source's sentences from stdin (build time, no judge); a claim's words are then checked against it
  questions <name> [n]                     the open meaning questions: words of judged claims that no receipt, owner line or reference holds
  remainder <name> [<n> : <text>]          the contract's parts left not satisfied, typed on their checkpoint; <name> alone lists them and names the next work
  remainder <name> <n> <k> satisfied [: by what]
  freeze <path>                            sha of the handler into the brain; file read-only
  source <name> --domain a,b               the domains of a source (C36); a project routes to domains, agreement counts the routed sources
  sources                                  every source with its band, domains, lines and origin, and the routes
  author <name> <n> [--model m]            rail C2 (the owner, 11-09): a claude exec turn writes the check of C n (a library program plus variables, citations), or answers no check
  audit-check <name> <n>                   rail C3: the check run on the real work twice (fresh inputs) and on broken copies a codex exec turn made without seeing it; every copy caught or the check is refused
  prove <name> [n] [--done] [--box min]    rail C4: write and audit the check of each checkpoint (or the done ones), run it: check ok keeps or closes, check wrong reopens, no check hands back
  jev ask --state <file> --q <id>:<formula> [--q ...]   jev C4: one line <id> noul=<p> per question, in the order given; each answer's reasons kept (C8)
  jev problog --clauses <file> --query <atom>   jev C5: p=<value> by the distribution semantics, in the judge brain (the clauses the query depends on, every world's least model)
  jev mln --rules <file> --state <file> --query <atom>   jev C6: p=<value>, the C5 worlds weighted by exp(sum w_i n_i(x)), in the judge brain
  jev psl --rules <file> --state <file> --query <atom>   jev C6: truth=<value>, the free atom's y in [0,1] of the least weighted total of max(0, l_j(y)), in the judge brain
  jev opinion --rows <file>                  jev C7: <atom> b= d= u= a= p= per fused opinion (trust discounted, cumulative fusion, p = b + a u), in the judge brain; problog, mln, psl read opinion rows fused
  jev why <id> | jev retract <row id> [--undo]   jev C8: the path:line of the rows an answer depends on; a retracted row revises only the answers that listed it, asked again from the record in the judge brain
  jev verify --claim <text> --source <db|file|source name>   jev C9: <fact> label=<supported|refuted|nei> row=<path:line|none> per fact, then score=
  jev calibrate --set <file> [--bins k]      jev C10: bucket=<lo-hi> n= mean_p= freq= per bucket, then ece=  (cortex jev help: the file formats)
  jev <project ...> [--n k] [--seed s]     rail C6: our own jev (the judge brain, rows of sql on the test kernel: the seven questions from evidence, the owner bands, the truth table) beside the python judge on k random judged claims; decides nothing
  look <word> [<word>] [--source s]        rail C5: the source db rows that hold a word or a pair, with source, path and line (read only)
  check <name> <n> : <command>             C47: the cortex's own check of a checkpoint, run in the repo after every build turn; its print is a receipt the worker never touched; check ok closes, check wrong reopens
  check <name> <n>                         run the check now and type its print
  need <name> <n> : <text>                 C41: what a worker said the hydration lacked; carried by the next hydration of that checkpoint
  questions <name> --prune                 C40: retire the questions of sentences that are not candidates for state
  states --backfill [project]              C42: seed the state history from the formula snapshots and the current state
  at <name> <when> [word]                  C38: the state of the project at a time of the graph's own (last tuesday, yesterday, 11-03), and the lines that held a word, each with its verdict and part state
  ingest <name> --voice <who> <text>       the voice of a hand ingest (owner, hand, a session); the capture sets it by itself
  voices --rebuild                         recompute every voice's counts from the newest verdict of each judged run
  accept <name> <n> [run]                  the owner's word: with a run, that sentence is a part of C n's state; without, C n is done
  reject <name> <n> <run>                  the owner's word: that sentence is not a part of C n's state, whatever the judge said
  mark <name> <run> <kind> [: <why>]       the labeled set: what that judged sentence was (completes progresses regresses supersedes drift invention hallucination dupe noise unsettled)
  learn [<name> ...] [--key]               the (project, gate) key for every line, then the judge's weights from the marks (leave-one-out accuracy printed); --key keys only
  learn --pairs [--box seconds]            build time: the (source or project, word pair) key for every line (C23: a claim's pairs held by which sources; a pair held nowhere is a question)
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
    elif v == "ingest":
        if "--voice" in a: i = a.index("--voice"); VOICE[0] = a[i + 1]; a = a[:i] + a[i + 2:]
        v_ingest(a[0], sys.stdin.read() if a[1:] == ["-"] else " ".join(a[1:]))
    elif v == "judge": v_judge(a[0], int(a[1]), int(a[2]))
    elif v == "hydrate":
        if "--ask" in a:
            h = hydration_ask(a[0], " ".join(a[a.index("--ask") + 1:])); sys.stdout.write(h); print("[%d bytes]" % len(h.encode()), file=sys.stderr)
        else: v_hydrate(a[0], int(a[a.index("--at") + 1]) if "--at" in a else None)
    elif v == "route": v_route(a[0] if a else None, [x for x in a[1].split(",") if x] if len(a) > 1 else None)
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
    elif v == "author":
        r9 = v_author(a[0], int(a[1]), next((a[i + 1] for i in range(len(a) - 1) if a[i] == "--model"), None)); print(json.dumps(r9)[:1500])
    elif v == "audit-check":
        r9 = v_audit_check(a[0], int(a[1])); print(json.dumps(r9)[:1500])
    elif v == "prove":
        v_prove(a[0], int(a[1]) if len(a) > 1 and a[1].isdigit() else None, "--done" in a, int(a[a.index("--box") + 1]) if "--box" in a else None, next((a[i + 1] for i in range(len(a) - 1) if a[i] == "--model"), None))
    elif v == "jev" and a and a[0] == "ask":
        return v_jev_ask(a[1:])   # jev C4: the judge brain answers; jev.py is not imported
    elif v == "jev" and a and a[0] == "problog":
        return v_jev_problog(a[1:])   # jev C5: the judge brain answers; jev.py is not imported
    elif v == "jev" and a and a[0] == "verify":
        return v_jev_verify(a[1:])   # jev C9: the judge brain labels; jev.py is not imported
    elif v == "jev" and a and a[0] == "calibrate":
        return v_jev_calibrate(a[1:])   # jev C10: the judge brain pools and buckets; jev.py is not imported
    elif v == "jev" and a and a[0] in ("why", "retract"):
        return v_jev_reason(a[0], a[1:])   # jev C8: the judge brain answers from its record; jev.py is not imported
    elif v == "jev" and a and a[0] == "opinion":
        return v_jev_opinion(a[1:])   # jev C7: the judge brain answers; jev.py is not imported
    elif v == "jev" and a and a[0] in ("mln", "psl"):
        return v_jev_soft(a[0], a[1:])   # jev C6: the judge brain answers; jev.py is not imported
    elif v == "jev" and a and a[0] in JEV_VERBS:
        import jev as jev_c4   # jev C4 to C10: the outline verbs (the owner 11-09: stick to the outline .. proceed); jev.py beside this file
        return jev_c4.main(a, jev_door())
    elif v == "jev":
        v_jev([x for x in a if not x.startswith("--") and not (a.index(x) > 0 and a[a.index(x) - 1] in ("--n", "--seed"))] or ["cortex"], int(a[a.index("--n") + 1]) if "--n" in a else 8, int(a[a.index("--seed") + 1]) if "--seed" in a else None)
    elif v == "look":
        v_look([x for x in a if not x.startswith("--") and not (a.index(x) > 0 and a[a.index(x) - 1] == "--source")], a[a.index("--source") + 1] if "--source" in a else None)
    elif v == "check":
        s6 = " ".join(a)
        if " : " in s6: k6, t6 = split_colon(a); v_check_set(k6[0], int(k6[1]), t6)
        else: v_check_run(a[0], int(a[1]), "--close" in a)
    elif v == "need":
        if "--clear" in a: v_need_clear(a[0], int(a[1]))
        else: k4, t4 = split_colon(a); v_need(k4[0], int(k4[1]), t4)
    elif v == "mark":
        s = " ".join(a); why = ""
        if " : " in s: s, why = s.split(" : ", 1)
        k = s.split(); v_mark(k[0], int(k[1]), k[2], why)
    elif v == "learn":
        if "--pairs" in a: print("pairs: the word pairs of every line are read from the brain's own seq when the judge asks; nothing to build")
        else: v_learn([x for x in a if not x.startswith("--")] or None, key_only="--key" in a)
    elif v == "verdicts": v_verdicts(a[0], int(a[1]) if len(a) > 1 and a[1].isdigit() else None, int(a[a.index("--limit") + 1]) if "--limit" in a else 40)
    elif v == "receipt": v_receipt(a[0], int(a[1]), " ".join(a[2:]))
    elif v == "source":
        dom = None; path7 = None; globs7 = None
        if "--domain" in a: i = a.index("--domain"); dom = [x for x in a[i + 1].split(",") if x]; a = a[:i] + a[i + 2:]
        if "--path" in a: i = a.index("--path"); path7 = a[i + 1]; a = a[:i] + a[i + 2:]
        if "--glob" in a: i = a.index("--glob"); globs7 = [x for x in a[i + 1].split(",") if x]; a = a[:i] + a[i + 2:]
        if "--db" in a:
            a = [x for x in a if x != "--db"]; fb = "--from-brain" in a; a = [x for x in a if x != "--from-brain"]
            s7 = " ".join(a); t7 = None
            if " : " in s7: s7, t7 = s7.split(" : ", 1)
            k7 = s7.split(); stdin_ = len(k7) >= 2 and k7[-1] == "-"
            v_source_db(k7[0], (k7[1] if len(k7) > 1 and k7[1] in BANDS else None), t7, dom, path7, globs7, fb, (sys.stdin.read() if stdin_ else None))
        elif path7 is not None:
            s7 = " ".join(a); t7 = None
            if " : " in s7: s7, t7 = s7.split(" : ", 1)
            k7 = s7.split(); v_source_path(k7[0], k7[1] if len(k7) > 1 else "reference", path7, t7, dom, globs7)
        elif len(a) >= 2 and a[1] == "-": v_source(a[0])
        elif dom is not None and " : " not in " ".join(a): v_source(a[0], None, None, dom)
        else:
            k2, t2 = split_colon(a); v_source(k2[0], k2[1] if len(k2) > 1 else None, t2, dom)
    elif v == "lesson":
        ladder, picks = None, None
        if "--ladder" in a: i = a.index("--ladder"); ladder = [int(x) for x in a[i + 1].split(",") if x]; a = a[:i] + a[i + 2:]
        if "--pick" in a: i = a.index("--pick"); picks = [x for x in a[i + 1].split(",") if x]; a = a[:i] + a[i + 2:]
        v_lesson(a[0], a[1], ladder, picks)
    elif v == "why": v_why(a[0], "--plan" in a)
    elif v == "self": test_kernel(a[0] if a else "")
    elif v == "second": v_second(a[0], int(a[1]))
    elif v == "dispute":
        s8 = " ".join(a); t8 = s8.split(" : ", 1)[1] if " : " in s8 else "the worker holds it correct"; k8 = s8.split(" : ", 1)[0].split(); v_dispute(k8[0], int(k8[1]), t8)
    elif v == "ask": v_askq(a[0], " ".join(a[1:]))
    elif v == "senses": v_senses(a[0], int(a[a.index("--n") + 1]) if "--n" in a else 6)
    elif v == "teach": v_teach(a[0], int(a[a.index("--n") + 1]) if "--n" in a else 5, a[a.index("--project") + 1] if "--project" in a else "cortex")
    elif v == "retire":
        s9 = " ".join(a); t9 = s9.split(" : ", 1)[1] if " : " in s9 else ""; v_retire(s9.split(" : ", 1)[0].split()[0], t9)
    elif v == "sources":
        if "--migrate" in a: v_source_migrate_all(int(a[a.index("--box") + 1]) if "--box" in a else 120)
        else: v_sources()
    elif v == "ask-source": v_ask_source(a[0], " ".join(x for x in a[1:] if not x.startswith("--") and not (a.index(x) > 0 and a[a.index(x) - 1] == "--run")), int(a[a.index("--run") + 1]) if "--run" in a else None)
    elif v == "states":
        print("states: every state line of a checkpoint is a record under its key with its time; the history is read from the tree, nothing to backfill")
    elif v == "at": v_at(a[0], a[1:])
    elif v == "voices":
        if "--rebuild" in a: rebuild_voices()
        else: print("cortex voices --rebuild   recompute every voice's counts from the newest verdict of each judged run")
    elif v == "questions":
        if "--ask" in a: v_questions_ask(a[0])
        elif "--answered" in a: v_questions_answered(a[0])
        else: v_questions(a[0], int(a[1]) if len(a) > 1 and a[1].isdigit() else None, "--prune" in a)
    elif v == "remainder":
        if len(a) == 1: v_remainder(a[0])
        elif len(a) >= 4 and a[3] == "satisfied":
            s3 = " ".join(a); note = s3.split(" : ", 1)[1] if " : " in s3 else None; v_remainder(a[0], int(a[1]), None, int(a[2]), note)
        else: k3, t3 = split_colon(a); v_remainder(k3[0], int(k3[1]), t3)
    elif v == "plan":
        engine, model, scope = "claude", None, None
        if "--engine" in a: i = a.index("--engine"); engine = a[i + 1]; a = a[:i] + a[i + 2:]
        if "--model" in a: i = a.index("--model"); model = a[i + 1]; a = a[:i] + a[i + 2:]
        if "--scope" in a: i = a.index("--scope"); scope = a[i + 1]; a = a[:i] + a[i + 2:]
        if "--ask" in a: v_plan_ask(a[0], " ".join(a[a.index("--ask") + 1:]), engine, model)
        else: v_plan(a[0], a[1], engine, model, scope)
    elif v == "build":
        engine, model, box, turns = "claude", None, 30, 12
        if "--engine" in a: engine = a[a.index("--engine") + 1]
        if "--model" in a: model = a[a.index("--model") + 1]
        if "--box" in a: box = int(a[a.index("--box") + 1])
        if "--turns" in a: turns = int(a[a.index("--turns") + 1])
        v_build(a[0], engine, model, box, turns, "--no-act" not in a)
    elif v == "handbacks": v_handbacks(a[0])
    elif v == "decide":
        s5 = " ".join(a); t5 = None
        if " : " in s5: s5, t5 = s5.split(" : ", 1)
        k5 = s5.split(); v_decide(k5[0], int(k5[1]), k5[2], t5)
    elif v == "status": v_status(a[0] if a else None)
    elif v == "recall": v_recall(a[0], int(a[a.index("from") + 1]) if "from" in a else 0, int(a[a.index("to") + 1]) if "to" in a else None, [x for x in a[1:] if x not in ("from", "to") and not x.isdigit()])
    elif v == "formula": v_formula(a[0])
    elif v == "q": print(json.dumps(ask("q " + " ".join(a)))[:4000])   # a keyed read for the builder; the kernel refuses a scan
    elif v == "freeze": v_freeze(a[0] if a else HANDLER)
    else: print(USAGE); return 2
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
