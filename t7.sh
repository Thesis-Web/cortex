#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
echo "=== the filter joins an output block onto its sentence (dry: sentences of a worker-shaped text)"
python3 -I -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('cx', '/home/james/cortex/cortex.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for x in m.sentences('C6: \`whoami\` printed this single line:\n\n\`\`\`\njames\n\`\`\`\n\nEXPECTED: met\nLive output: \`james\`\n'): print('  -', x)
"
echo; echo "=== C5's contract on a fresh line: probe C6, a worker turn whose verdict moves the state inside the turn"
cortex checkpoint probe 6 --kind read : "report the name of the current user as printed by the command whoami" "||" "the command whoami was run and its one printed line is quoted" | tail -1
echo "--- next before: $(cortex hydrate probe --at 6 2>/dev/null | sed -n 2,2p | cut -c1-90)"
time cortex turn probe --at 6 --engine claude --model haiku --act 2>&1 | grep -v "^  judgment cells" | cut -c1-280
echo "--- next after:  $(cortex hydrate probe 2>/dev/null | sed -n 2,2p | cut -c1-90)"
echo; cortex status probe | grep "C[0-9] \["
