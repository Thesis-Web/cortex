#!/bin/bash
# t4-judge.sh (2026-11-02): the judge without keys, live: graph cells, the subscription model for the unsettled, a worker turn whose verdict
# moves a state (cortex C5's contract), a judgment step answered with no worker (C7's contract).
export PATH=$HOME/.local/bin:$PATH
echo "=== C7's and probe C2's expected lines re-worded: the judge, not jev by name"
cortex checkpoint cortex 7 : "the router: a step marked judgment goes to the judge (the graph over the state, then the subscription model, jev only if a key exists), never to a worker; model by step kind" "||" "a turn's receipt shows a judgment step answered by the judge with no worker process started" | tail -1
cortex checkpoint probe 2 --kind judgment : "the probe's kernel release was reported as live output" "||" "the judge answers that the statement holds" | tail -1
echo; echo "=== the judge on the two C11 sentences (graph first; the subscription model for what is unsettled)"
cortex judge cortex 11 264178 | cut -c1-300
time cortex judge cortex 11 264188 | cut -c1-300
echo; echo "=== C5's contract: a worker turn whose verdict moves a state"
cortex checkpoint probe 4 --kind read : "report the number of cpu cores of this machine as printed by the command nproc" "||" "the command nproc was run and its one printed line is quoted" | tail -1
echo "--- hydration before"; cortex hydrate probe --at 4 2>/dev/null | sed -n 2,2p | cut -c1-120
time cortex turn probe --at 4 --engine claude --model haiku --act 2>&1 | grep -v "^  judgment cells" | cut -c1-300
echo "--- hydration after (what is next now)"; cortex hydrate probe 2>/dev/null | sed -n 2,2p | cut -c1-120
echo; echo "=== C7's contract: a judgment step with no worker process"
echo "--- worker processes before: $(pgrep -c -f 'claude -p --model .* --output-format text --dangerously|codex exec')"
time cortex turn probe --at 2 2>&1 | grep -v "^  judgment cells" | cut -c1-300
echo "--- worker processes after: $(pgrep -c -f 'claude -p --model .* --output-format text --dangerously|codex exec')"
