#!/bin/bash
# c7b-codex.sh (2026-11-02): a codex turn on a read step of the probe, with codex's real flags.
export PATH=$HOME/.local/bin:$PATH
cortex checkpoint probe 3 --kind read : "report the hostname of this machine as printed by the command hostname" "||" "the command hostname was run and its one printed line is quoted"
echo "=== codex turn on probe C3"; cortex turn probe --at 3 --engine codex --act 2>&1 | grep -v "^  jev not asked"
