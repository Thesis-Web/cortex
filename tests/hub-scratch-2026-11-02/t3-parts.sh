#!/bin/bash
# t3-parts.sh (2026-11-02): completing previous state: the live output that satisfied each done checkpoint, recorded in the brain as its part.
export PATH=$HOME/.local/bin:$PATH
part(){ R=$(cortex ingest "$1" "$3" | sed -n 's/^ingest run \([0-9]*\).*/\1/p' | head -1); [ -n "$R" ] && cortex accept "$1" "$2" "$R" | cut -c1-120 || echo "C$2: nothing new to accept"; }
part cortex 0 "c0 satisfied: 86 symbols laid in each brain; a typed line returned run 1 and the clock advanced to 3."
part cortex 1 "c1 satisfied: define : cortex asked wn gcide moby and wikt in 62 ms; the second ask recalled in 9 ms with no source asked."
part cortex 2 "c2 satisfied: an ingest returned run 105995 at clock 106033; the same sentence again returned the first run with again 2 and nothing typed."
part cortex 3 "c3 satisfied: the hydration of 2083 bytes listed c0 to c9 with states read from the index."
part cortex 4 "c4 satisfied: the on-scope ingest and the recipe got different verdict lines; a bogus key gave http 401 and no verdict."
part cortex 6 "c6 satisfied: cortex hydrate neuron printed the neuron rail of 1394 bytes from the brain."
part cortex 9 "c9 satisfied: from the hub, ssh hp2 cortex hydrate cortex printed the hydration; no cortex file on the hub."
part cortex 10 "c10 satisfied: nine worker lines checked in 38 ms, four kept, four noise by reason, one restated dropped against its first run."
part cortex 11 "c11 satisfied: the recipe was drift by sheet in 23 ms from the deterministic cells; the on-scope sentence stayed unsettled with empty judgment cells."
part cortex 12 "c12 satisfied: a part was added by the owner's word, ticked to 2 on repeat, and shown in the hydration at c10."
part cortex 13 "c13 satisfied: seven owner lines on the guessing brain were ingested into the neuron project."
part probe 1 "probe c1 satisfied: haiku ran uname -r and printed 6.12.74+deb13+1-amd64."
part probe 3 "probe c3 satisfied: codex ran hostname and printed jameshp2."
echo; echo "=== the diff cell: a sentence that only restates c11's accepted state, and one with new words"
R=$(cortex ingest cortex "the recipe was drift by sheet from the deterministic cells and the on-scope sentence stayed unsettled." | sed -n 's/^ingest run \([0-9]*\).*/\1/p' | head -1); [ -n "$R" ] && cortex judge cortex 11 $R | cut -c1-250
R=$(cortex ingest cortex "the sheet now carries a diff cell that counts the new words against the accepted state." | sed -n 's/^ingest run \([0-9]*\).*/\1/p' | head -1); [ -n "$R" ] && cortex judge cortex 11 $R | cut -c1-250
echo; echo "=== the formula again: after"; cortex formula cortex | cut -c1-200; echo; cortex formula probe | cut -c1-200
cd ~/cortex && git add -A >/dev/null 2>&1; git -c user.name=cortex -c user.email=cortex@hp2 commit -qm "cortex 2026-11-02: the input output formula (cortex formula), the diff cell, satisfying parts for every done checkpoint, capture of every assistant text" && git log --oneline -1
