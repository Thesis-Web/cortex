#!/usr/bin/env python3
# nkbottom.py (2026-10-30): the env handler for the kernel, as bottom6 was for v6: types the lines of a file into the kernel over its socket,
# fills {run:k}, {gate:x} and {gate6:x} by reading the kernel back, writes the ledger. It decides nothing.
# usage: python3 nkbottom.py <port> --lines FILE [--ledger FILE] [--quiet]
import socket, json, re, sys, time
PORT = int(sys.argv[1])
def ask(req):
    s = socket.create_connection(('127.0.0.1', PORT)); s.sendall((req + '\n').encode()); buf = b''
    while True:
        d = s.recv(1 << 20)
        if not d: break
        buf += d
        if buf.endswith(b'\n'): break
    s.close(); return json.loads(buf.decode())
def q(sql): return ask('q ' + sql)['rows']
RUNS = []
def fill(line):
    def r(m):
        k = int(m.group(1)); return str(RUNS[k - 1]) if 0 < k <= len(RUNS) and RUNS[k - 1] else m.group(0)
    line = re.sub(r'\{run:(\d+)\}', r, line)
    def g(m):
        schema = 'sixth' if m.group(1) == '6' else 'main'
        rows = q(f"SELECT gate FROM {schema}.label WHERE symbol = '{m.group(2)}'")
        return str(rows[0][0]) if rows else m.group(0)
    return re.sub(r'\{gate(6?):([^}]+)\}', g, line)
def type_line(line, quiet=False):
    schema, text = ('sixth', line[3:]) if line.startswith('6> ') else ('main', line)
    r = ask(f'type {schema} {text}')
    if 'error' in r: print('refused:', r['error']); RUNS.append(None); return None
    RUNS.append(r['run'])
    if not quiet:
        print(f"  [{schema}: run {r['run']}, {r['runs']} runs, {r['hits']} hits, {r['born']} born, {r['seconds']:.2f} s]")
        for (s, run, c, v) in r['out']: print(f"  {s} run {run} · {c}: {v}")
    return r
def main():
    quiet = '--quiet' in sys.argv; lines = None; ledger = None
    if '--lines' in sys.argv: lines = [l.rstrip('\n') for l in open(sys.argv[sys.argv.index('--lines') + 1], encoding='utf-8')]
    if '--ledger' in sys.argv: ledger = open(sys.argv[sys.argv.index('--ledger') + 1], 'w', encoding='utf-8')
    k = 0
    if ledger: ledger.write("| # | prompt | line | run | runs | hits | born | refused | s | what the brain put in its out mailbox |\n|---|---|---|---|---|---|---|---|---|---|\n")
    for l in lines or []:
        if not l.strip() or l.startswith('#'):
            if ledger and l.startswith('# '): ledger.write(f"| | | *{l[2:].replace('|', '/')}* | | | | | | | |\n")
            continue
        k += 1; l = fill(l)
        print('>', l[:140] + ('…' if len(l) > 140 else ''), flush=True)
        r = type_line(l, quiet)
        if ledger:
            if r is None: ledger.write(f"| {k} | | {l[:60].replace('|', '/')} | refused | | | | | | |\n"); continue
            outs = '<br>'.join(f"{s} run {run} · {c}: {str(v)[:90].replace('|', '/')}" for (s, run, c, v) in r['out'][:8])
            ledger.write(f"| {k} | {r['schema']} | `{l[:60].replace('|', '/')}` | {r['run']} | {r['runs']} | {r['hits']} | {r['born']} | {r['refused']} | {r['seconds']:.2f} | {outs} |\n"); ledger.flush()
    if ledger: ledger.close()
    print('stats:', ask('stats'))
main()
