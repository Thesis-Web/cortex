#!/bin/bash
# c5-turn.sh (2026-11-02): C3/C4 closed, the repeat tick shown, then one live blink turn on a probe project (claude haiku, acting on hp2).
export PATH=$HOME/.local/bin:$PATH
echo "=== repeat tick (the sentence is now under its hash key)"; cortex ingest cortex "The cortex holds the state of a project in the brain."
cortex state cortex 3 done; cortex state cortex 4 done; cortex state cortex 5 working
cortex ingest cortex "c4 passed in its geometry form: two verdict lines typed, the on-scope ingest at 0.61 radians and the recipe at 0.90 radians from the scope; a bogus key gave http 401 and no verdict. the jev truth table waits for the owner's key."
echo; echo "=== probe project"
cortex project probe : "a probe project on hp2 to prove the blink loop: one worker turn whose whole context is the hydration."
cortex checkpoint probe 1 : "report the linux kernel release of this machine as printed by the command uname -r" "||" "the command uname -r was run and its one printed line is quoted"
echo; echo "=== the hydration the worker will get"; H=$(cortex hydrate probe 2>/dev/null); printf '%s' "$H" | wc -c
echo; echo "=== turn"; time cortex turn probe --engine claude --model haiku --act
echo; echo "=== status probe"; cortex status probe
