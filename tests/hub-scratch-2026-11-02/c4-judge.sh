#!/bin/bash
# c4-judge.sh (2026-11-02): C2's repeat tick and C4's judge, live, through the front door only.
export PATH=$HOME/.local/bin:$PATH
echo "=== C2 repeat"; cortex ingest cortex "The cortex holds the state of a project in the brain."
echo "=== off-scope ingest"; R=$(cortex ingest cortex "Preheat the oven to 350 degrees and bake the bread for forty minutes." | sed -n 's/^ingest run \([0-9]*\).*/\1/p' | head -1); echo "off-scope run $R"
echo "=== judge on-scope (run 105995), no key"; cortex judge cortex 3 105995; echo "rc=$?"
echo "=== judge off-scope (run $R), no key"; cortex judge cortex 3 $R; echo "rc=$?"
echo "=== judge with a bogus key: must be an error, not a verdict"; mkdir -p ~/.config/cortex; printf 'bogus-key-for-the-negative-test' > ~/.config/cortex/typesafe.key; chmod 600 ~/.config/cortex/typesafe.key
cortex judge cortex 3 105995; echo "rc=$?"; rm -f ~/.config/cortex/typesafe.key
echo "=== verdict lines in the brain (keyed by run)"; cortex q "SELECT kind, name, n, run, substr(value,1,160) FROM main.cx WHERE kind = 'verdict' AND name = 'cortex' AND n > 0 ORDER BY n DESC LIMIT 3"
echo "=== status"; cortex status cortex | head -5
