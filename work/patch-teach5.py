src = open("cortex.py").read()
old = '''        for (run, t) in picked:   # the lesson taught 11-04 20:4x: a line typed before C30 carried its project in the prefix; the brain holds it as another line, the front door as the same sentence
            try: kr = typed("cortex ingest : %s" % t)["run"]
            except RuntimeError: continue
'''
new = '''        for (run, t) in picked:   # the lesson taught 11-04 20:4x: the brain keys a repeat by the whole typed line (its prefix too), the front door by the sentence; the lesson re-types the line as the brain saw it
            full = (ask("run main %d" % run).get("run") or {}).get("text") or ("cortex ingest : %s" % t)
            try: kr = typed(full)["run"]
            except RuntimeError: continue
'''
assert src.count(old) == 1; src = src.replace(old, new); open("cortex.py", "w").write(src); print("patched")
