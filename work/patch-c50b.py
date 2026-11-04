src = open("cortex.py").read()
old = """        for (ln, para) in file_paragraphs(f):
            for sent in sentences(para):
                if is_noise(sent): noise += 1; continue
                k = text_key(sent)
                if cx_get("source", name, k): dupes += 1; continue
                try: r = typed("cortex source %s : %s" % (name, sent))
                except RuntimeError: refused += 1; continue
                run = r["run"]; cx_put("source", name, k, run, clock(), json.dumps({"path": rel, "line": ln})); key_gates(name, run); key_pairs(name, run); n_typed += 1; k_file += 1
"""
new = """        for (ln, para) in file_paragraphs(f):
            plines = [x.lower() for x in para.splitlines()]
            for sent in sentences(para):
                if is_noise(sent): noise += 1; continue
                k = text_key(sent)
                if cx_get("source", name, k): dupes += 1; continue
                try: r = typed("cortex source %s : %s" % (name, sent))
                except RuntimeError: refused += 1; continue
                head = sent.lower()[:25]; off = next((i for i, x in enumerate(plines) if head in x), 0)   # the sentence's own line inside the paragraph (a code file has few blank lines)
                run = r["run"]; cx_put("source", name, k, run, clock(), json.dumps({"path": rel, "line": ln + off})); key_gates(name, run); key_pairs(name, run); n_typed += 1; k_file += 1
"""
assert src.count(old) == 1; src = src.replace(old, new); open("cortex.py", "w").write(src); print("patched")
