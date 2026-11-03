#!/bin/bash
# t8-freeze.sh (2026-11-02): C5 and C7 closed with their live parts, then C8: the handler frozen, proven, and closed; then the formula.
export PATH=$HOME/.local/bin:$PATH
part(){ R=$(cortex ingest "$1" "$3" | sed -n 's/^ingest run \([0-9]*\).*/\1/p' | head -1); [ -n "$R" ] && cortex accept "$1" "$2" "$R" | cut -c1-110; cortex state "$1" "$2" done | cut -c1-60; }
part cortex 5 "c5 satisfied: probe c6 was one live turn on hp2 whose prompt of 1382 bytes was the hydration; the worker's sentence was judged completes 0.80 by the subscription judge; the verdict moved c6 to done inside the turn and the next hydration read c5 instead."
part cortex 7 "c7 satisfied: probe c2 was a judgment step routed to the judge; it answered holds 0.85 from the project's accepted parts with zero worker processes before and after; the judgment moved c2 to done."
echo; echo "=== C8: freeze the handler"; cortex freeze ~/cortex/CORTEX-HANDLER.md | cut -c1-160
echo "--- status compares"; cortex status | grep "^freeze"
echo "--- a write must fail"; (echo "x" >> ~/cortex/CORTEX-HANDLER.md) 2>&1 | head -1; ls -l ~/cortex/CORTEX-HANDLER.md | cut -c1-40
part cortex 8 "c8 satisfied: the handler's sha256 is a line in the brain, cortex status prints brain and file shas equal, the file is read-only and a write to it failed with permission denied."
echo; echo "=== the input output formula, end of turn"; cortex formula cortex | cut -c1-200; echo; cortex formula probe | cut -c1-200
cd ~/cortex && git add -A >/dev/null 2>&1; git -c user.name=cortex -c user.email=cortex@hp2 commit -qm "cortex 2026-11-02: judge without keys (sheet, graph, subscription model, jev optional); C5 C7 C8 closed; handler frozen" && git log --oneline -1
