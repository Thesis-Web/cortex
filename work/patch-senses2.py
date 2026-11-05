src = open("cortex.py").read()
old = '''            r = ask_learner("type main define : %s" % w); run = r.get("run") or 0; g = learner_gate(w)
            cells = [c for c in (ask_learner("run main %d" % run).get("cells") or []) if c[0] == 187]; nsense = len((cells[0][2] or "").split()) if cells and cells[0][2] else 0
'''
new = '''            r = ask_learner("type main define : %s" % w); run = r.get("run") or 0; g = learner_gate(w); nsense = 0
            for i in range(10):   # the define run fills its sense cell from the returns; read it when it is there, up to five seconds
                cells = [c for c in (ask_learner("run main %d" % run).get("cells") or []) if c[0] == 187]; nsense = len((cells[0][2] or "").split()) if cells and cells[0][2] else 0
                if nsense: break
                time.sleep(0.5)
'''
assert src.count(old) == 1; src = src.replace(old, new); open("cortex.py", "w").write(src); print("patched")
