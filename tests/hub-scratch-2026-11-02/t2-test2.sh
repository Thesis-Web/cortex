#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
echo "=== C10 again: the path line and an in-batch repeat"
cortex ingest cortex - <<'TXT'
/home/james/cortex/nk/nk 7007 egg-symbols.txt sources wn gcide
cat ~/cortex/brain/nk.log educate.log
The deterministic cells settle noise, dupe, restated and drift; the judgment cells settle the rest.
The deterministic cells settle noise, dupe, restated and drift; the judgment cells settle the rest.
TXT
echo; echo "=== C11: the worker's own mark as a cell (probe run 261937)"; cortex judge probe 3 261937
echo; echo "=== states and the progress note"
cortex state cortex 10 done; cortex state cortex 11 done; cortex state cortex 12 done
cortex ingest cortex "c10 c11 c12 passed live on 2026-11-02: a nine line worker output was checked line by line in 38 ms, four noise lines dropped by reason, one restated line dropped against its first run, four sentences kept; the sheet judge settled the recipe as drift from its deterministic cells alone in 23 ms and left the on-scope sentence unsettled with empty judgment cells; a part was added to c10 by the owner's word, ticked on repeat, and shown in the hydration."
cd ~/cortex && git add -A >/dev/null 2>&1; git -c user.name=cortex -c user.email=cortex@hp2 commit -qm "cortex 2026-11-02: the ingest filter (C10), the judge as a run data sheet (C11), part-wise state (C12), the guessing brain's design recorded (C13)" && git log --oneline -1
echo "=== status cortex"; cortex status cortex | grep -E "^brain|C1[0-3]"
