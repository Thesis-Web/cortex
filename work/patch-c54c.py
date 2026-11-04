src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('def source_symbol(name): return "src_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")\n',
    'def source_symbol(name):\n    # the source\'s symbol in the brain: short (the kernel keeps a symbol short), unique by a hash tail\n    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")\n    return "src_" + slug if len(slug) <= 20 else "src_" + slug[:14].strip("_") + "_" + hashlib.sha256(name.encode()).hexdigest()[:6]\n')
rep('def source_db_type(name, items, quiet=False):\n', 'def source_db_type(name, items, quiet=False, replace=False):\n')
rep('        k = text_key(sent)\n        if cx_get("source", name, k): dupes += 1; continue\n        cw = [w for w in re.findall(r"[a-z][a-z0-9_\']+", sent.lower()) if w not in STOP]\n',
    '        k = text_key(sent); had = cx_get("source", name, k)\n        if had and (not replace or \'"db"\' in (had[3] or "")): dupes += 1; continue   # a typed row is replaced by the migration; a db row is a repeat\n        cw = [w for w in re.findall(r"[a-z][a-z0-9_\']+", sent.lower()) if w not in STOP]\n')
rep('    return source_db_type(name, items)\n', '    return source_db_type(name, items, replace=from_brain)\n')
open("cortex.py", "w").write(src); print("patched")
