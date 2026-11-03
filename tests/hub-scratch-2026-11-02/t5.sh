#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
echo "=== C5's contract again: probe C4, a worker turn whose verdict moves a state"
echo "--- next before: $(cortex hydrate probe 2>/dev/null | sed -n 2,2p | cut -c1-100)"
time cortex turn probe --at 4 --engine claude --model haiku --act 2>&1 | grep -v "^  judgment cells" | cut -c1-260
echo "--- next after:  $(cortex hydrate probe 2>/dev/null | sed -n 2,2p | cut -c1-100)"
echo; echo "=== C7's contract again: probe C2, a judgment step with no worker process, the project's parts in the judge's state"
echo "--- worker processes before: $(pgrep -c -f 'claude -p --model .* --dangerously|codex exec')"
time cortex turn probe --at 2 2>&1 | grep -v "^  judgment cells" | cut -c1-260
echo "--- worker processes after: $(pgrep -c -f 'claude -p --model .* --dangerously|codex exec')"
echo; echo "=== probe status"; cortex status probe | grep "C[0-9]"
