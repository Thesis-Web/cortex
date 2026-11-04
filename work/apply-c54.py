src = open("cortex.py").read(); block = open("work/c54-block.py").read()
def rep(old, new, count=1):
    global src
    assert src.count(old) == count, ("anchor", src.count(old), old[:90]); src = src.replace(old, new)
rep('USAGE = """cortex <verb> ...\n', block + 'USAGE = """cortex <verb> ...\n  source <name> reference --db [--path <folder> [--glob a,b] | --from-brain | -] : <what>   C54: a source into cx.db (the attached source db), keyed by word and pair in the index; nothing typed into the brain\n  ask-source <name|all> <word or "a b"> [--run R]   C54: the request in cx.inbox, the returns laid as return runs under R with their src rows\n  sources --migrate [--box min]   C54: every reference source typed as lines moved into cx.db\n')
# the ground reads a db source by its word keys
rep('            if band in BANDS and cx_get("gate", src, w): g[band] += 1; held = True; g.setdefault("by_source", {}); g["by_source"][src] = g["by_source"].get(src, 0) + 1\n',
    '            if band in BANDS and source_holds_gate(src, w): g[band] += 1; held = True; g.setdefault("by_source", {}); g["by_source"][src] = g["by_source"].get(src, 0) + 1   # C54: a db source by its word key\n')
rep('        who = [nm for nm in srcn if cx_get("pair", nm, k)]\n', '        who = [nm for nm in srcn if source_holds_pair(nm, a, b)]   # C54: a db source by its pair key\n')
# code ground for db sources
rep('''    out, seen = [], set()
    pathed = [nm for (nm, band) in sources() if source_info(nm).get("path")]
    if not pathed: return out
    for (a, b) in pairs_of(run):
        k = pair_key(a, b)
        for nm in pathed:
            had = cx_get("pair", nm, k)
            if not had: continue
            first = json.loads(had[3]).get("first"); p, l = source_line_of(nm, first)
            if p and (nm, p, l) not in seen: seen.add((nm, p, l)); out.append("%s %s:%s holds %s %s" % (nm, p, l, sym_of(a), sym_of(b)))
            if len(out) >= limit: return out
    return out
''', '''    out, seen = [], set()
    pathed = [nm for (nm, band) in sources() if source_info(nm).get("path")]
    if not pathed: return out
    for (a, b) in pairs_of(run):
        k = pair_key(a, b)
        for nm in pathed:
            if source_is_db(nm):   # C54: the db row itself names the file and line
                if not cx_get("spair", nm, text_key("%s %s" % (sym_of(a), sym_of(b)))): continue
                for (sid, t, p, l) in db_lines_holding(nm, [sym_of(a), sym_of(b)], 1):
                    if p and (nm, p, l) not in seen: seen.add((nm, p, l)); out.append("%s %s:%s holds %s %s" % (nm, p, l, sym_of(a), sym_of(b)))
                if len(out) >= limit: return out
                continue
            had = cx_get("pair", nm, k)
            if not had: continue
            first = json.loads(had[3]).get("first"); p, l = source_line_of(nm, first)
            if p and (nm, p, l) not in seen: seen.add((nm, p, l)); out.append("%s %s:%s holds %s %s" % (nm, p, l, sym_of(a), sym_of(b)))
            if len(out) >= limit: return out
    return out
''')
# questions --ask: db sources hold words and pairs; the lines found printed (C51.1)
rep('''            if w.startswith("pair: ") and len(gates) == 2 and all(gates): holders = [(nm, cx_get("pair", nm, pair_key(gates[0], gates[1]))) for nm in srcs]; holders = [(nm, h) for (nm, h) in holders if h]
            elif gates and all(gates): holders = [(nm, cx_get("gate", nm, gates[0])) for nm in srcs if all(cx_get("gate", nm, g) for g in gates)]
            if holders:
                where = []
                for (nm, h) in holders[:3]:
                    first = json.loads(h[3]).get("first"); p, l = source_line_of(nm, first)
                    where.append("%s%s" % (nm, (" %s:%s" % (p, l)) if p else ""))
                found.append("%s held by %s" % (w, ", ".join(where)))
''', '''            if w.startswith("pair: ") and len(gates) == 2 and all(gates): holders = [(nm, source_holds_pair(nm, gates[0], gates[1])) for nm in srcs]; holders = [(nm, h) for (nm, h) in holders if h]
            elif gates and all(gates): holders = [(nm, source_holds_gate(nm, gates[0])) for nm in srcs if all(source_holds_gate(nm, g) for g in gates)]
            if holders:
                where = []
                for (nm, h) in holders[:3]:
                    if source_is_db(nm):   # C54, C51.1: the lines found, from the source db, with path and line
                        for (sid, t, p, l) in db_lines_holding(nm, toks, 1): where.append("%s%s: %s" % (nm, (" %s:%s" % (p, l)) if p else "", t[:100]))
                        continue
                    first = json.loads(h[3]).get("first"); p, l = source_line_of(nm, first)
                    where.append("%s%s" % (nm, (" %s:%s" % (p, l)) if p else ""))
                found.append("%s held by %s" % (w, ", ".join(where)))
''')
# sources list shows db sources
rep('''        print("%-44s %-9s %-26s %7d  %s%s" % (nm, b, ",".join(d.get("domain") or []) or "-", cnt, (d.get("text") or "")[:100], (" | path " + d["path"]) if d.get("path") else ""))\n''',
    '''        print("%-44s %-9s %-26s %7d  %s%s%s" % (nm, b, ",".join(d.get("domain") or []) or "-", cnt, (d.get("text") or "")[:100], (" | path " + d["path"]) if d.get("path") else "", (" | db %d lines" % d.get("db_lines", 0)) if d.get("db") else ""))\n''')
# verbs
rep('''        if path7 is not None:
            s7 = " ".join(a); t7 = None
            if " : " in s7: s7, t7 = s7.split(" : ", 1)
            k7 = s7.split(); v_source_path(k7[0], k7[1] if len(k7) > 1 else "reference", path7, t7, dom, globs7)
''', '''        if "--db" in a:
            a = [x for x in a if x != "--db"]; fb = "--from-brain" in a; a = [x for x in a if x != "--from-brain"]
            s7 = " ".join(a); t7 = None
            if " : " in s7: s7, t7 = s7.split(" : ", 1)
            k7 = s7.split(); stdin_ = len(k7) >= 2 and k7[-1] == "-"
            v_source_db(k7[0], (k7[1] if len(k7) > 1 and k7[1] in BANDS else None), t7, dom, path7, globs7, fb, (sys.stdin.read() if stdin_ else None))
        elif path7 is not None:
            s7 = " ".join(a); t7 = None
            if " : " in s7: s7, t7 = s7.split(" : ", 1)
            k7 = s7.split(); v_source_path(k7[0], k7[1] if len(k7) > 1 else "reference", path7, t7, dom, globs7)
''')
rep('''    elif v == "sources": v_sources()\n''', '''    elif v == "sources":
        if "--migrate" in a: v_source_migrate_all(int(a[a.index("--box") + 1]) if "--box" in a else 120)
        else: v_sources()
    elif v == "ask-source": v_ask_source(a[0], " ".join(x for x in a[1:] if not x.startswith("--") and not (a.index(x) > 0 and a[a.index(x) - 1] == "--run")), int(a[a.index("--run") + 1]) if "--run" in a else None)
''')
# the test kernel reads its source list from LIST
rep('''        subprocess.Popen("cd %s && NK_MAP=%s/brain.map nohup ./nk 7010 egg-symbols.txt sources wn gcide mwt moby map sqldoc measured guess wikt > %s/nk.log 2>&1 < /dev/null &" % (NK, T, T), shell=True)\n''',
    '''        lst = open(os.path.join(NK, "sources", "LIST")).read().split() if os.path.exists(os.path.join(NK, "sources", "LIST")) else "wn gcide mwt moby map sqldoc measured wikt cx".split()
        subprocess.Popen("cd %s && NK_MAP=%s/brain.map nohup ./nk 7010 egg-symbols.txt sources %s > %s/nk.log 2>&1 < /dev/null &" % (NK, T, " ".join(lst), T), shell=True)\n''')
open("cortex.py", "w").write(src); print("applied")
