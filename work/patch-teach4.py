src = open("cortex.py").read()
old = '''            held = cx_get("line", "*", text_key(t)); fd = held[0] if held else 0   # C30: the sentence's one run, whichever project typed it first
'''
new = '''            fd = run   # C30: the sentence's one run is the line row we picked; the brain must answer that run as same_as when the sentence is typed again
'''
assert src.count(old) == 1; src = src.replace(old, new); open("cortex.py", "w").write(src); print("patched")
