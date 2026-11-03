#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
echo "=== the graph's definition words: does uname's definition name the kernel? (keyed reads)"
cortex q "SELECT l.symbol FROM main.defwords d JOIN main.label l ON l.gate = d.word WHERE d.gate = (SELECT gate FROM main.label WHERE symbol = 'uname') LIMIT 40" | cut -c1-400
echo; echo "=== probe C4: the earlier sentence judged again under the fixed formula (a completes verdict moves the state by itself)"
cortex judge probe 4 264705 | cut -c1-300
echo; echo "=== C5's contract on a fresh line: probe C5, a worker turn whose verdict moves the state inside the turn"
cortex checkpoint probe 5 --kind read : "report how long this machine has been up as printed by the command uptime -p" "||" "the command uptime -p was run and its one printed line is quoted" | tail -1
echo "--- next before: $(cortex hydrate probe --at 5 2>/dev/null | sed -n 2,2p | cut -c1-90)"
time cortex turn probe --at 5 --engine claude --model haiku --act 2>&1 | grep -v "^  judgment cells" | cut -c1-280
echo "--- next after:  $(cortex hydrate probe 2>/dev/null | sed -n 2,2p | cut -c1-90)"
echo; echo "=== C7's contract: probe C2, the judgment step, graph over the parts' words and definitions first, then a direct holds question"
echo "--- worker processes before: $(pgrep -c -f 'claude -p --model .* --dangerously|codex exec')"
time cortex turn probe --at 2 2>&1 | cut -c1-280
echo "--- worker processes after: $(pgrep -c -f 'claude -p --model .* --dangerously|codex exec')"
echo; cortex status probe | grep "C[0-9] \["
