src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
# the hard block: code never enters the brain as words (typed lines); fenced code dropped from typed prose; a retired source grounds nothing
rep('def source_type(name, raw):\n    t0 = time.time(); n_typed = dupes = noise = refused = 0\n',
    '''CODE_EXT = (".py", ".c", ".h", ".ts", ".tsx", ".js", ".rs", ".go", ".sql", ".sh", ".java", ".cpp", ".cc", ".rb", ".php", ".cs", ".swift", ".kt", ".lua", ".pl")
def code_share(raw):
    ls = [l for l in raw.splitlines() if l.strip()]
    if not ls: return 0.0
    return sum(1 for l in ls if is_noise(l) in ("code", "command-or-markup", "symbols")) / len(ls)
def hard_block_code(raw, where):
    # the owner, 11-04 18:2x: a hard block for the hub builder and the neuron builder: code written into the neuron as words is never ingested; code lives outside the brain as a source db
    if code_share(raw) >= 0.3: raise SystemExit("hard block (the owner, 11-04 18:2x): code never enters the brain as words (%s: %.0f%% code lines); type it as a source db: cortex source <name> reference --db ..." % (where, code_share(raw) * 100))
def source_type(name, raw):
    raw = re.sub(r"```.*?```", " ", raw, flags=re.S)   # the owner, 11-04: fenced code never enters the brain as words
    hard_block_code(raw, "the text of source " + name)
    t0 = time.time(); n_typed = dupes = noise = refused = 0
''')
rep('''def source_type_paths(name, root, files, limit_per_file=400):
''', '''def source_type_paths(name, root, files, limit_per_file=400):
    bad = [f for f in files if f.lower().endswith(CODE_EXT)]
    if bad: raise SystemExit("hard block (the owner, 11-04 18:2x): code never enters the brain as words: %s; type a code base as a source db: cortex source %s reference --db --path <folder>" % (", ".join(os.path.relpath(b, root) for b in bad[:4]), name))
''')
rep('''def sources():
    if not _SRC:
        for (nm, v) in q("SELECT name, value FROM main.cx WHERE kind = 'source' AND n = 0 AND name >= ''"):
            try: _SRC.append((nm, json.loads(v).get("band", "reference")))
            except ValueError: pass
''', '''def sources():
    if not _SRC:
        for (nm, v) in q("SELECT name, value FROM main.cx WHERE kind = 'source' AND n = 0 AND name >= ''"):
            try:
                d = json.loads(v)
                if d.get("retired"): continue   # the owner, 11-04 18:2x: a source typed in breach of the code block grounds nothing; its runs stay as history
                _SRC.append((nm, d.get("band", "reference")))
            except ValueError: pass
''')
open("cortex.py", "w").write(src); print("patched")
