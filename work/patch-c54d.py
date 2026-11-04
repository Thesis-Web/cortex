src = open("cortex.py").read()
old = '''        for f in ("brain.map.main.db", "brain.map.sixth.db", "brain.map.xyz"):
            if os.path.exists(os.path.join(B, f)): shutil.copy(os.path.join(B, f), os.path.join(T, f))
'''
new = '''        for f in ("brain.map.main.db", "brain.map.sixth.db", "brain.map.xyz"):
            if os.path.exists(os.path.join(B, f)): shutil.copy(os.path.join(B, f), os.path.join(T, f))
        live_cx = os.path.join(HOME, "cortex", "nk", "sources", "cx.db")   # C54: the source db goes with the brain it answers
        if os.path.exists(live_cx): shutil.copy(live_cx, os.path.join(NK, "sources", "cx.db"))
'''
assert src.count(old) == 1; src = src.replace(old, new); open("cortex.py", "w").write(src); print("patched")
