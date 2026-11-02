#!/usr/bin/env python3
# build_sources.py (2026-10-29): lays three full source brains in the shape make_sources.py laid the slice (me, corpus, inbox,
# outbox, the work and carry triggers), from the full dictionaries downloaded this morning:
#   wn    WordNet 3.1 (wordnetcode.princeton.edu/wn3.1.dict.tar.gz): one line per synset, the gloss with its lemmas in [syn: {..}]
#         as dict.org prints it; a row for every single-word lemma of the synset, lowercased.
#   gcide GCIDE 0.54 (ftp.gnu.org/gnu/gcide): one line per <def>, tags stripped; a row for each <ent> of the entry, lowercased.
#         Quotations (<q>), etymologies (<ety>) and pronunciations are left out: the owner's 10-22 measurement found they inflate
#         the counts, and they are not the description of the action. That choice is mine.
#   moby  Moby Thesaurus (gutenberg.org/ebooks/3202, mthesaur.txt): one line "like X" per synonym of a root, as the slice shaped
#         the thesaurus lines and as define's relationship rule reads them.
# usage: python3 -I build_sources.py <dl dir> <out dir> wn gcide moby   (name the sources to lay)
import os, re, sys, html, sqlite3, time
DL, OUT = sys.argv[1], sys.argv[2]
GATES = {'wn': 7, 'gcide': 8, 'moby': 11}
SHAPE = """
CREATE TABLE me (gate INTEGER NOT NULL);
INSERT INTO me VALUES ({gate});
CREATE TABLE corpus (id INTEGER PRIMARY KEY, word TEXT NOT NULL, hw TEXT, text TEXT NOT NULL);
CREATE TABLE inbox (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, about INTEGER, word TEXT);
CREATE TABLE outbox (id INTEGER PRIMARY KEY, run INTEGER, cell INTEGER, about INTEGER, text TEXT);
CREATE TRIGGER work AFTER INSERT ON inbox BEGIN
  INSERT INTO outbox (run, cell, about, text) SELECT NEW.run, NEW.cell, NEW.about, text FROM corpus WHERE word = NEW.word ORDER BY id;
  DELETE FROM inbox WHERE id = NEW.id;
END;
CREATE TRIGGER carry AFTER INSERT ON outbox BEGIN
  SELECT mother('INSERT INTO main.secondary (run, cell, gate, about, text) VALUES (' || NEW.run || ', ' || NEW.cell || ', ' || (SELECT gate FROM me) || ', ' || NEW.about || ', ' || quote(NEW.text) || ')');
  DELETE FROM outbox WHERE id = NEW.id;
END;"""

def lay(name, rows):
    p = os.path.join(OUT, name + '.db')
    if os.path.exists(p): os.remove(p)
    db = sqlite3.connect(p)
    db.executescript(SHAPE.format(gate=GATES[name]))
    db.executemany("INSERT INTO corpus (word, hw, text) VALUES (?, ?, ?)", rows)
    db.execute("CREATE INDEX corpus_word ON corpus (word)")
    db.commit()
    n, w = db.execute("SELECT count(*), count(DISTINCT word) FROM corpus").fetchone()
    db.close()
    print(f"{name}: {n} lines, {w} words, {os.path.getsize(p) // 1024} KB")

def wordnet():
    rows = []
    for pos in ('noun', 'verb', 'adj', 'adv'):
        with open(os.path.join(DL, 'wn', 'dict', 'data.' + pos), encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.startswith('  '): continue
                left, _, gloss = line.partition(' | ')
                t = left.split()
                n = int(t[3], 16)
                lemmas = [re.sub(r'\(.*?\)$', '', t[4 + 2 * i]) for i in range(n)]
                text = gloss.strip() + ' [syn: {' + '}, {'.join(l.replace('_', ' ') for l in lemmas) + '}]'
                for l in lemmas:
                    if '_' in l: continue
                    rows.append((l.lower(), l, text))
    lay('wn', rows)

ENT = {'ae': 'æ', 'AE': 'Æ', 'oe': 'œ', 'OE': 'Œ', 'ldquo': '"', 'rdquo': '"', 'lsquo': "'", 'rsquo': "'", 'br': ' ', 'sect': '§', 'pound': '£', 'deg': '°', 'prime': "'", 'frac12': '1/2', 'frac14': '1/4', 'frac34': '3/4', 'hellip': '...', 'mdash': ' - ', 'ndash': '-', 'root': ''}
def clean(s):
    s = re.sub(r'<([A-Za-z0-9?]+)/', lambda m: ENT.get(m.group(1), '' if m.group(1) in ('root',) else _mark(m.group(1))), s)   # GCIDE's self-closing marks: <ae/ <amac/ <br/ <ldquo/
    s = re.sub(r'</?[A-Za-z][A-Za-z0-9]*(\s[^<>]*)?>', ' ', s)     # ordinary tags
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s
def _mark(name):
    # accented letters are written <amac/ (a macron), <ecr/ (e breve), <oomac/ ...: keep the base letter
    m = re.match(r'^([a-zA-Z])(mac|cr|sl|um|breve|dot|cir|til|acute|grave|ring|ced)$', name)
    if m: return m.group(1)
    m = re.match(r'^(oo|ae|oe)(mac|cr)$', name)
    if m: return m.group(1)
    return ''

def gcide():
    # an entry is its <ent> headwords (one or several, then <hw>); an entry with no <ent> is its <hw>; a <def> belongs to the entry it is
    # under. GCIDE's prefix lists (Un-, Re-, ...) name a thousand <ent>s under one entry: there only the first (the prefix) takes the defs.
    rows = []; tag = re.compile(r'<ent>(.*?)</ent>|<def>(.*?)</def>|<hw>(.*?)</hw>', re.S)
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        with open(os.path.join(DL, 'gcide', 'gcide-0.54', 'CIDE.' + letter), encoding='latin-1') as f: s = f.read()
        ents, had_hw = [], False
        for m in tag.finditer(s):
            if m.group(3) is not None:
                if had_hw: ents = [clean(m.group(3))]     # a second <hw> with no <ent> between: an entry of its own (the "See abased." lines)
                had_hw = True; continue
            if m.group(1) is not None:
                e = clean(m.group(1))
                if had_hw: ents, had_hw = [e], False
                else: ents.append(e)
            else:
                d = clean(m.group(2))
                if not d: continue
                for e in (ents if len(ents) <= 8 else ents[:1]):
                    if e: rows.append((e.lower(), e, d))
    lay('gcide', rows)

def moby():
    rows = []
    with open(os.path.join(DL, 'moby', 'mthesaur.txt'), encoding='latin-1') as f:
        for line in f:
            parts = line.rstrip('\r\n').split(',')
            root = parts[0].strip()
            for syn in parts[1:]:
                syn = syn.strip()
                if syn: rows.append((root, root, 'like ' + syn))
    lay('moby', rows)

if 'wn' in sys.argv[3:]: t = time.time(); wordnet(); print(f'  {time.time() - t:.1f} s')
if 'gcide' in sys.argv[3:]: t = time.time(); gcide(); print(f'  {time.time() - t:.1f} s')
if 'moby' in sys.argv[3:]: t = time.time(); moby(); print(f'  {time.time() - t:.1f} s')
