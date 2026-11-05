src = open("cortex.py").read(); block = open("work/teach-block.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('USAGE = """cortex <verb> ...\n', block + 'USAGE = """cortex <verb> ...\n  teach dupe|pairs|known [--n k] [--project p]   C57 / teach: a lesson the brain takes: its own answer beside the front door answer on k random inputs; equal k of k\n  retire <function> : <the owner words>   teach C5: the owner word; the front door reads the brain answer alone for that function\n')
rep('    elif v == "sources":\n        if "--migrate" in a:', '''    elif v == "teach": v_teach(a[0], int(a[a.index("--n") + 1]) if "--n" in a else 5, a[a.index("--project") + 1] if "--project" in a else "cortex")
    elif v == "retire":
        s9 = " ".join(a); t9 = s9.split(" : ", 1)[1] if " : " in s9 else ""; v_retire(s9.split(" : ", 1)[0].split()[0], t9)
    elif v == "sources":
        if "--migrate" in a:''')
rep('    fr = cx_get("freeze", "handler", 0)\n', '    rf = retired_functions()\n    if rf: print("held by the neuron (retired from the front door on the owner word): " + ", ".join(rf))\n    fr = cx_get("freeze", "handler", 0)\n')
open("cortex.py", "w").write(src); print("applied")
