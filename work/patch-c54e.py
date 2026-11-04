src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('''    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return "src_" + slug if len(slug) <= 20 else "src_" + slug[:14].strip("_") + "_" + hashlib.sha256(name.encode()).hexdigest()[:6]
''', '''    slug = re.sub(r"[^a-z]+", "_", name.lower()).strip("_")   # letters only: the encoder ends a symbol at a digit
    tail = "".join(chr(97 + b % 26) for b in hashlib.sha256(name.encode()).digest()[:6])
    return "src_" + slug if (len(slug) <= 20 and re.sub(r"[^a-z0-9]+", "", name.lower()) == slug.replace("_", "")) else "src_" + slug[:14].strip("_") + "_" + tail
''')
rep('''    if not rows: raise SystemExit("the source symbol %s has no gate" % sym)
    g = rows[0][0]; q("INSERT OR REPLACE INTO cx.me (source, gate) VALUES (?, ?)", name, g); return g
''', '''    if not rows: print("the source symbol %s has no gate; the source answers with gate 0 until it has one" % sym); return 0
    g = rows[0][0]; q("INSERT OR REPLACE INTO cx.me (source, gate) VALUES (?, ?)", name, g); return g
''')
open("cortex.py", "w").write(src); print("patched")
