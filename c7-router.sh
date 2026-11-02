#!/bin/bash
# c7-router.sh (2026-11-02): a codex turn on the probe (fenced live output kept as sentences), then a judgment step routed to jev and stopped
# at the key boundary with no model process started; then the progress ingested and the repo committed.
export PATH=$HOME/.local/bin:$PATH
echo "=== codex turn on probe C1"; cortex turn probe --engine codex --act 2>&1 | grep -v "^  jev not asked"
echo; echo "=== probe 1 accepted (my word on a probe, not the owner's), probe 2 is a judgment step"
cortex accept probe 1
cortex checkpoint probe 2 --kind judgment : "the probe's kernel release was reported as live output" "||" "jev answers that the statement holds"
echo "--- processes before"; pgrep -c -f "claude -p|codex exec" ; echo "--- turn"; cortex turn probe; echo "rc=$?"; echo "--- processes after"; pgrep -c -f "claude -p|codex exec"
echo; echo "=== progress ingested"
cortex ingest cortex "c5 mechanics passed live: the worker's prompt was the hydration (638 bytes), haiku ran uname -r in 5.9 s, its output was ingested and judged; the state did not move because jev has no key. c6 passed: the neuron project is registered with four checkpoints and its hydration is 1394 bytes. c9 passed: from the hub, ssh hp2 cortex hydrate cortex prints the hydration and no cortex file is on the hub. c7 is coded: a judgment step goes to jev and a model is chosen by step kind; it runs only once the key is in place."
echo; echo "=== commit"; cd ~/cortex; printf 'brain/\nwork/\nnk/sources/\nnk/sources-slice/\nnk/nk\nnk/hello\nnk/out/\n' > .gitignore; git add -A >/dev/null 2>&1; git -c user.name=cortex -c user.email=cortex@hp2 commit -qm "cortex 2026-11-02: nk kernel copy, front door, handler, education and checkpoint scripts" && git log --oneline -1 && git count-objects -vH | grep size-pack
