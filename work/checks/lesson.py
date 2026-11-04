#!/usr/bin/env python3
# lesson.py (C52, 2026-11-04): the cortex's own check of a lesson checkpoint (the owner: checkpoints, tests, answer key held by the judge).
# The key (the tests, their shas, the exemplar) lives in ~/cortex/work/keys/<name>/<slug>, outside the repo the worker edits.
# usage: python3 lesson.py <name> <slug>          the repo's solution against the key's tests, on a scratch copy; prints check ok | check wrong
#        python3 lesson.py <name> <slug> --key    the exemplar against the key's tests (the key proven once, at lesson time)
import sys, os, json, hashlib, shutil, subprocess, tempfile, re
name, slug = sys.argv[1], sys.argv[2]; keymode = "--key" in sys.argv
HOME = os.path.expanduser("~"); W = os.path.join(HOME, "cortex", "work"); repo = os.path.join(W, name, slug); kd = os.path.join(W, "keys", name, slug)
key = json.load(open(os.path.join(kd, "key.json"))); lang = key["lang"]
def say(s): print(s); sys.exit(0)
if not keymode:
    for t, sha in key["shas"].items():
        p = os.path.join(repo, t)
        if not os.path.exists(p): say("check wrong: the tests file %s is missing from %s" % (t, repo))
        if hashlib.sha256(open(p, "rb").read()).hexdigest() != sha: say("check wrong: the tests file %s was changed (its sha differs from the key's)" % t)
    for s in key["solution"]:
        if not os.path.exists(os.path.join(repo, s)): say("check wrong: the solution file %s is missing from %s" % (s, repo))
d = tempfile.mkdtemp(prefix="lesson-check-")
try:
    for s in key["solution"]:
        srcf = os.path.join(kd, "example-" + os.path.basename(s)) if keymode else os.path.join(repo, s)
        os.makedirs(os.path.dirname(os.path.join(d, s)), exist_ok=True); shutil.copy(srcf, os.path.join(d, s))
    for t in key["tests"]: os.makedirs(os.path.dirname(os.path.join(d, t)), exist_ok=True); shutil.copy(os.path.join(kd, os.path.basename(t)), os.path.join(d, t))
    if lang == "python":
        p = subprocess.run(["python3", "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider"] + key["tests"], cwd=d, capture_output=True, text=True, timeout=120)
        out = p.stdout + p.stderr; m = re.search(r"(\d+) passed", out); f = re.search(r"(\d+) (failed|error)", out)
        if p.returncode == 0 and m and int(m.group(1)) == key["ntests"] and not f: say("check ok: %s passed of %d on the cortex own copy, the tests untouched (sha)%s" % (m.group(1), key["ntests"], " [the key]" if keymode else ""))
        tail = [l for l in out.strip().splitlines() if l.strip()]
        say("check wrong: %s" % ((tail[-1] if tail else "no output from pytest") if not (m and f) else "%s passed, %s" % (m.group(1), f.group(0)))[:220])
    elif lang == "go":
        if os.path.exists(os.path.join(kd, "go.mod")): shutil.copy(os.path.join(kd, "go.mod"), d)
        p = subprocess.run(["go", "test", "-count=1", "./..."], cwd=d, capture_output=True, text=True, timeout=300)
        out = p.stdout + p.stderr
        if p.returncode == 0 and re.search(r"(?m)^ok\b", out): say("check ok: go test prints ok on the cortex own copy, the tests untouched (sha)%s" % (" [the key]" if keymode else ""))
        tail = [l for l in out.strip().splitlines() if l.strip()]
        say("check wrong: %s" % (tail[-1] if tail else "no output from go test")[:220])
    say("check wrong: no runner for " + lang)
finally:
    shutil.rmtree(d, ignore_errors=True)
