#!/bin/bash
# t2-test.sh (2026-11-02): C10 the filter, C11 the sheet judge, C12 part-wise state, live through the front door.
export PATH=$HOME/.local/bin:$PATH
echo "=== C10: a messy worker output, ingested as a whole and checked line by line"
cortex ingest cortex - <<'TXT'
The filter drops command lines and keeps the sentences that pertain to the state.
$ uname -r
6.12.74+deb13+1-amd64
/home/james/cortex/nk/nk 7007 egg-symbols.txt sources wn gcide
{"cols": ["gate"], "rows": [[445]]}
jq -r '.transcript_path' | { read -r f; tail -c 400000 "$f"; }
Sentences that pertain to the state are kept by the filter, and command lines are dropped.
The filter drops command lines and keeps the sentences that pertain to the state.
The judge is a run data sheet whose deterministic cells fill first.
TXT
echo; echo "=== C11: the sheet judge on the kept sentence, on the recipe (run 261415), and on a probe line with the worker's own mark (run 261937)"
R=$(cortex q "SELECT run FROM main.cx WHERE kind = 'restate' AND name = 'cortex' AND n > 0 ORDER BY ts DESC LIMIT 1" | python3 -c "import sys, json; print(json.load(sys.stdin)['rows'][0][0])")
echo "kept sentence run $R"; cortex judge cortex 10 $R
cortex judge cortex 10 261415
cortex judge cortex 10 261937
echo; echo "=== C12: the owner's word adds a part; a repeat ticks; the hydration at C10 shows it"
cortex accept cortex 10 $R; cortex accept cortex 10 $R
cortex hydrate cortex --at 10 2>/dev/null | sed -n 2,4p
