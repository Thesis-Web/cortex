#!/usr/bin/env python3
# g34/door_fix.py (2026-11-01): the door's match_runs read the whole input table (no key); the kernel refuses that read, so every typed
# line since the door's restart at 11:23 failed with KeyError 'rows' before reaching the brain. The typed lines come from the kernel's
# mailbox read `newest` instead. Door only; the kernel is not touched.
import os
os.chdir(os.path.expanduser('~/nk'))
s = open('serve8.py').read()
a = '''    for schema in ('main', 'sixth'):
        rows = q(f"SELECT run FROM {schema}.input WHERE run IS NOT NULL ORDER BY id")['rows']
        typed[schema] = [(r[0], decode(schema, r[0])) for r in rows]
'''
b = '''    for schema in ('main', 'sixth'):
        # the typed lines from the kernel's mailbox read (newest first): a read of the whole input table has no key and the kernel refuses it
        n = ask('newest ' + schema + ' 5000')
        typed[schema] = [(l['run'], l['text']) for l in reversed(n.get('lines', []))]
'''
assert s.count(a) == 1, 'match_runs not as expected'
open('serve8.py', 'w').write(s.replace(a, b))
import ast; ast.parse(open('serve8.py').read())
print('door: match_runs reads newest; serve8 parses')
