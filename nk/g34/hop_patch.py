#!/usr/bin/env python3
# g34/hop_patch.py (2026-11-01). The owner: "the function of the hop is one dna shard, it basically = spacebar in a sentence, you do not have to
# log every different hop as a dna shard ... the trigger to go the hop meaning points to the same shard of dna for all points"; "it's just a
# substitution shard... one shard that accepts the before and remainder as two variables ... you will hit the hop node but it's just a moment in
# time for the trigger to happen to get to the next table"; "it does require or can require back population of existing dna shard triggers".
# The kernel: a landing with no function row of its own hits the one hop shard (the space neuron's row); no row is laid for a pass. A binding
# line that names a row by its full key lays it then. `hop`: the back population, every pass-only row folded into the hop shard, receipts and
# memory rows re-pointed. The bundle sends the definition words of the newest lines' points; the page shows a definition's words once the
# point is present. Runs on hp in ~/nk. Every anchor must match exactly once.
import os, re
os.chdir(os.path.expanduser('~/nk'))
def patch(path, pairs):
    s = open(path).read()
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:90], s.count(a))
        s = s.replace(a, b)
    open(path, 'w').write(s); print('patched', path, len(pairs))

# ---- nk.c
patch('nk.c', [
('Shard *shard_find(Brain *b, int gate, int before, int trigger){',
 'static i64 SHROWS[2];   /* the DNA rows each brain holds (the id counter b->shards never comes down) */\n'
 'i64 nk_shard_rows(Brain *b){ return SHROWS[b->is_main]; }\n'
 'void nk_count_rows(Brain *b){ i64 n = 0; for(int g = 1; g <= b->label.n; g++){ Neuron *x = neuron_of(b, g); if(x) n += x->nsh; } SHROWS[b->is_main] = n; }\n'
 'Shard *shard_find(Brain *b, int gate, int before, int trigger){'),
('  Shard *s = &n->sh[n->nsh++]; s->id = ++b->shards; s->before = before; s->trigger = trigger; s->call = 0; s->spawn = 0; s->times = times; s->changed_at = b->clock;',
 '  Shard *s = &n->sh[n->nsh++]; s->id = ++b->shards; s->before = before; s->trigger = trigger; s->call = 0; s->spawn = 0; s->times = times; s->changed_at = b->clock; SHROWS[b->is_main]++;'),
('Shard *shard_by_id(Brain *b, int gate, i64 id){ Neuron *n = neuron_of(b, gate); if(!n) return 0; i64 i = hmap_get(&b->shid, gate, id); return i ? &n->sh[i - 1] : 0; }',
 '/* the hop: one shard for every point. The owner (2026-11-01): "the function of the hop is one dna shard, it basically = spacebar in a sentence ...\n'
 '   the trigger to go the hop meaning points to the same shard of dna for all points"; "a substitution shard ... that accepts the before and remainder\n'
 '   as two variables". It is the space neuron\'s row (before and trigger both none: the variables come from the run itself). */\n'
 'static i64 HOPID[2];\n'
 'Shard *hop_shard(Brain *b){ Neuron *n = neuron_of(b, SPACE); if(!n) return 0; if(!n->born) n->born = 1; Shard *s = shard_find(b, SPACE, 0, 0); if(!s) s = shard_lay(b, SPACE, 0, 0, 0); HOPID[b->is_main] = s->id; return s; }\n'
 'i64 hop_id(Brain *b){ if(!HOPID[b->is_main]) hop_shard(b); return HOPID[b->is_main]; }\n'
 'Shard *shard_by_id(Brain *b, int gate, i64 id){ Neuron *n = neuron_of(b, gate); if(!n) return 0; i64 i = hmap_get(&b->shid, gate, id); if(i) return &n->sh[i - 1]; if(id == hop_id(b)) return hop_shard(b); return 0; }'),
('  Shard *s = shard_find(b, gate, kb, kx);\n  if(!s) s = shard_lay(b, gate, kb, kx, 0);\n  s->times++;',
 '  Shard *s = shard_find(b, gate, kb, kx);\n  if(!s) s = hop_shard(b);   /* no function row of its own for this before and next: the hop, one shard for every point; nothing is laid for a pass */\n  s->times++;'),
])
# ---- nk.h
patch('nk.h', [
('Shard *shard_by_id(Brain *b, int gate, i64 id);',
 'Shard *shard_by_id(Brain *b, int gate, i64 id);\nShard *hop_shard(Brain *b); i64 hop_id(Brain *b); i64 nk_shard_rows(Brain *b); void nk_count_rows(Brain *b);'),
])
# ---- nkvt.c
patch('nkvt.c', [
('    if(c->idx == 1){ if(c->started) return 0; c->started = 1; Neuron *n = neuron_of(c->b, (int)c->e); if(!n || !n->born) return 0; i64 ix = hmap_get(&n->h, c->k1, c->k2); if(!ix) return 0; c->i = ix - 1; return 1; }',
 '    if(c->idx == 1){ if(c->started) return 0; c->started = 1; Neuron *n = neuron_of(c->b, (int)c->e); if(!n || !n->born) return 0; i64 ix = hmap_get(&n->h, c->k1, c->k2); if(!ix){ shard_lay(c->b, (int)c->e, (int)c->k1, (int)c->k2, 0); ix = n->nsh; } c->i = ix - 1; return 1; }   /* a row named by its full key (a binding line) exists from then on: the hop lays none for a pass */'),
('static void shards_col(Cur *c, sqlite3_context *x, int col){ R(x, c->b->shards); }',
 'static void shards_col(Cur *c, sqlite3_context *x, int col){ R(x, nk_shard_rows(c->b)); }   /* the rows held, not the id counter */'),
])
# ---- nkio.c
DOHOP = r'''/* ---- the hop laid as one shard: the back population. The owner (2026-11-01): "you do not have to log every different hop as a dna shard ...
   it means the trigger to go the hop meaning points to the same shard of dna for all points"; "it does require or can require back population of
   existing dna shard triggers". Every row that only recorded a pass (no call, no spawn) folds into the hop shard: its times go there, the row goes,
   and every receipt, memory row and firing that named it now names the hop shard. Kept: a row with a call or a spawn, the egg's row 0 of the
   core, the ok neuron's rows (its marks), the hop shard itself. A pass over the brain, once. ---- */
static void do_hop(Brain *b, SB *o){
  double t0 = now_s(); int ok = label_gate(b, "ok"); Shard *hop = hop_shard(b); i64 hid = hop->id;
  i64 rows0 = 0, kept = 0, folded = 0, moved = 0, rcs = 0, mems = 0, evs = 0;
  free(b->shid.e); b->shid.e = 0; hmap_init(&b->shid, 1 << 16);
  for(int g = 1; g <= b->label.n; g++){ Neuron *n = neuron_of(b, g); if(!n || !n->nsh) continue; rows0 += n->nsh;
    int k = 0;
    for(int j = 0; j < n->nsh; j++){ Shard *s = &n->sh[j];
      int keep = s->call || s->spawn || g == ok || s->id == hid || (s->before == 0 && s->trigger == 0 && g <= 90);
      if(keep){ if(k != j) n->sh[k] = *s; k++; } else { moved += s->times; folded++; } }
    n->nsh = k;
    free(n->h.e); n->h.e = 0; n->h.n = 0; n->h.cap = 0;
    if(k){ hmap_init(&n->h, k * 2 < 8 ? 8 : k * 2); for(int j = 0; j < k; j++){ hmap_put(&n->h, n->sh[j].before, n->sh[j].trigger, j + 1); hmap_put(&b->shid, g, n->sh[j].id, j + 1); } }
    if(k == 0){ free(n->sh); n->sh = 0; n->csh = 0; }
    else if(n->csh > k * 2 + 8){ Shard *ns = malloc(sizeof(Shard) * (k + 2)); memcpy(ns, n->sh, sizeof(Shard) * k); free(n->sh); n->sh = ns; n->csh = k + 2; }
    kept += k; }
  hop->times += moved;
  for(i64 i = 1; i <= b->nruns; i++){ Run *r = &b->runs[i];
    if(r->rcs) for(int j = 0; j < r->nrc; j++){ Rc *c = &r->rcs[j]; if(c->shard == hid) continue; if(!hmap_get(&b->shid, c->gate, c->shard)){ c->shard = hid; rcs++; } }
    if(r->has_mem && r->mem_shard && r->mem_shard != hid && !hmap_get(&b->shid, r->mem_gate, r->mem_shard)){ r->mem_shard = hid; mems++; }
    if(r->ev) for(int j = 0; j < r->nev; j++){ Ev *e = &r->ev[j]; if(e->shard != hid && !hmap_get(&b->shid, e->gate, e->shard)){ e->shard = hid; evs++; } } }
  nk_count_rows(b);
  sb_fmt(o, "{\"brain\":\"%s\",\"rows_before\":%lld,\"rows_kept\":%lld,\"rows_folded\":%lld,\"times_moved\":%lld,\"hop_shard\":%lld,\"hop_times\":%lld,\"receipts_repointed\":%lld,\"memory_rows_repointed\":%lld,\"firings_repointed\":%lld,\"seconds\":%.1f}",
    b->name, (long long)rows0, (long long)kept, (long long)folded, (long long)moved, (long long)hid, (long long)hop->times, (long long)rcs, (long long)mems, (long long)evs, now_s() - t0);
}
'''
DEFW = r'''  /* the definition words of the newest lines' points: each point's node rows, their returns read back through the encoder (the page's
     definition lines, "a symbol to the words of the lines its sources returned") */
  sb_str(o, "],\"defw\":["); first = 1; { HMap dw; hmap_init(&dw, 1 << 16); int lines = 0;
    for(int i = 0; i < nr && lines < 400; i++){ Run *r = run_of(b, runs[i]); if(!r || r->kind != 0) continue; lines++; const char *w = cell_get(b, runs[i], WHAT); if(!w) continue; int g = atoi(w); Neuron *n = (g > 0 && g <= b->label.n) ? neuron_of(b, g) : 0; if(!n || !n->nnode) continue;
      for(int j = 0; j < n->nnode && j < 300; j++){ i64 rr = n->node[j].run; int ns; const int *sq = nk_seq(b, rr, &ns);
        for(int k = 0; sq && k < ns; k++){ int x = sq[k]; if(x <= 0 || x > b->label.n || x == g) continue; unsigned char c0 = (unsigned char)b->label.sym[x][0]; if(!((c0 >= 'A' && c0 <= 'Z') || (c0 >= 'a' && c0 <= 'z'))) continue; if(hmap_get(&dw, g, x)) continue; hmap_put(&dw, g, x, rr); inc[x] = 1; if(!first) sb_str(o, ","); first = 0; sb_fmt(o, "[%d,%d,%lld]", g, x, (long long)rr); } } }
    free(dw.e); }
'''
patch('nkio.c', [
('\\"shards\\":%lld,\\"hop_us\\":%.3f,', '\\"shards\\":%lld,\\"shard_rows\\":%lld,\\"hop_us\\":%.3f,'),
('(long long)b->refused_n, (long long)b->shards, hop_us,', '(long long)b->refused_n, (long long)b->shards, (long long)nk_shard_rows(b), hop_us,'),
('b->label.n, b->label.n, (long long)b->shards, (long long)b->nruns', 'b->label.n, b->label.n, (long long)nk_shard_rows(b), (long long)b->nruns'),
("/* ---- the whole-brain page's bundle:", DOHOP + "/* ---- the whole-brain page's bundle:"),
('  if(strcmp(req, "repair") == 0){ do_repair(&MAINB, o); return; }',
 '  if(strcmp(req, "repair") == 0){ do_repair(&MAINB, o); return; }\n  if(strcmp(req, "hop") == 0){ sb_str(o, "["); do_hop(&MAINB, o); sb_str(o, ","); do_hop(&SIXTHB, o); sb_str(o, "]"); return; }'),
('  nk_map_ready();\n', '  nk_count_rows(&MAINB); nk_count_rows(&SIXTHB);\n  nk_map_ready();\n'),
('  sb_str(o, "],\\"memrows\\":["); first = 1;', DEFW + '  sb_str(o, "],\\"memrows\\":["); first = 1;'),
])
# ---- the door
patch('serve8.py', [
("    if s.startswith('SELECT r.about, s.gate, min(r.id)'): return {'cols': [], 'rows': [[a[1], a[1], a[2]] for a in d['answ']]}",
 "    if s.startswith('SELECT r.about, s.gate, min(r.id)'): return {'cols': [], 'rows': d.get('defw', [])}   # a point to the words of its definition"),
("BUNDLE['d'] = ask('bundle 400')", "BUNDLE['d'] = ask('bundle ' + os.environ.get('NK_BUNDLE_K', '2000'))"),
])
# ---- the page: a word of a point's definition is present once the point is; the look is unchanged
patch('NEURON-POINT-OF-CONNECTION-nk-2026-10-30.html', [
('  function present(g, tk) { return g <= CORE || (FIRSTG[g] !== undefined && FIRSTG[g] <= tk); }',
 '  function present(g, tk) { return g <= CORE || (FIRSTG[g] !== undefined && FIRSTG[g] <= tk) || (DEFSEEN[g] !== undefined && DEFSEEN[g] <= tk); }'),
('DEFW = {}, ANSW = [],', 'DEFW = {}, DEFSEEN = {}, ANSW = [],'),
('    HOPCOUNT = {}; R[8].forEach(function (r) { HOPCOUNT[r[0]] = r[1]; });',
 '    HOPCOUNT = {}; R[8].forEach(function (r) { HOPCOUNT[r[0]] = r[1]; });\n'
 '    DEFSEEN = {}; Object.keys(DEFW).forEach(function (g) { var f = FIRSTG[g]; if (f === undefined) return; DEFW[g].forEach(function (x) { if (DEFSEEN[x[0]] === undefined || DEFSEEN[x[0]] > f) DEFSEEN[x[0]] = f; }); });   // a word of a point\'s definition is present from the hit that reached the point (the kernel pulls returns to the sheet; they are not walked)'),
("    Object.keys(DEFW).forEach(function (g) { DEFW[g].forEach(function (x) { if (atRun(x[1])) add(g, x[0], 'definition', .6); }); });",
 "    Object.keys(DEFW).forEach(function (g) { if (!present(+g, tk)) return; DEFW[g].forEach(function (x) { add(g, x[0], 'definition', .6); }); });"),
("    ANSW.forEach(function (p) { if (atRun(p[2])) add(p[0], p[1], 'answered', 1); });",
 "    ANSW.forEach(function (p) { if (present(p[1], tk)) add(p[0], p[1], 'answered', 1); });"),
])
import ast; ast.parse(open('serve8.py').read()); print('serve8 parses')
