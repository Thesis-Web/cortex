src = open("cortex.py").read(); block = open("work/senses-block.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('USAGE = """cortex <verb> ...\n', block + 'USAGE = """cortex <verb> ...\n  senses plan|lecture|problems|reteach|test|quiz [--n k]   the project lesson-senses: a lesson the brain takes the way a human is taught; the learner on CORTEX_LEARNER (7010), the key in wn.db read by the judge only\n')
rep('    elif v == "teach": v_teach(', '    elif v == "senses": v_senses(a[0], int(a[a.index("--n") + 1]) if "--n" in a else 6)\n    elif v == "teach": v_teach(')
open("cortex.py", "w").write(src); print("applied")
