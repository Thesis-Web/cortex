src = open("cortex.py").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, ("anchor", src.count(old), old[:80]); src = src.replace(old, new)
rep('    if cwd.rstrip("/") == "/home/exnulla": return "cortex"\n',
    '    if cwd.rstrip("/") == "/home/exnulla" or cwd.startswith("/home/exnulla/.claude"): return "cortex"   # the hub session\'s own folders (skills, memory, scratchpad) are the cortex session (11-04 18:xx: two hours of a session went uncaptured after a cd)\n')
rep('''def code_share(raw):
    ls = [l for l in raw.splitlines() if l.strip()]
    if not ls: return 0.0
    return sum(1 for l in ls if is_noise(l) in ("code", "command-or-markup", "symbols")) / len(ls)
''', '''CODE_HEAD = re.compile(r"^\\s*(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|const|let|var|function|fn|pub|struct|impl|package|func|print|#include|using|namespace|async|await|yield|lambda|switch|case|break|continue|static|void|int|char|float|double|bool|self\\.|this\\.)\\b")
def is_code_line(l):
    t = l.strip()
    if not t: return False
    if is_noise(t) in ("code", "command-or-markup", "symbols"): return True
    if CODE_HEAD.match(t): return True
    return bool(re.search(r"[=(){}\\[\\];]", t)) and len(content_words(t)) <= 3
def code_share(raw):
    ls = [l for l in raw.splitlines() if l.strip()]
    if not ls: return 0.0
    return sum(1 for l in ls if is_code_line(l)) / len(ls)
''')
open("cortex.py", "w").write(src); print("patched")
