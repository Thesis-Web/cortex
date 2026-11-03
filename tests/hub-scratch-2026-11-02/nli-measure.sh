#!/bin/bash
# nli-measure.sh (2026-11-02): can hp2 run a small NLI cross-encoder as a local jev-like judge, and how fast? A measurement in its own venv;
# nothing of the brain touched. Time box: the script stops itself after 15 minutes.
set -u
cd ~/cortex; T0=$(date +%s)
echo "start $(date +%T)"
python3 -m venv ~/cortex/judge-venv 2>&1 | tail -1 || { echo "venv failed"; exit 1; }
V=~/cortex/judge-venv/bin
timeout 600 $V/pip install -q --index-url https://download.pytorch.org/whl/cpu torch 2>&1 | tail -2; echo "torch installed $(($(date +%s) - T0))s"
timeout 300 $V/pip install -q transformers sentencepiece 2>&1 | tail -2; echo "transformers installed $(($(date +%s) - T0))s"
timeout 400 $V/python - <<'PY'
import time, torch
torch.set_num_threads(2)
from transformers import AutoTokenizer, AutoModelForSequenceClassification
name = "cross-encoder/nli-MiniLM2-L6-H768"
t0 = time.time(); tok = AutoTokenizer.from_pretrained(name); model = AutoModelForSequenceClassification.from_pretrained(name).eval(); print("model loaded in %.1fs; labels %s" % (time.time() - t0, model.config.id2label))
state = ("project cortex. checkpoint: report the linux kernel release of this machine as printed by the command uname -r. "
         "expected: the command uname -r was run and its one printed line is quoted. accepted state: nothing accepted yet. "
         "ingest: i ran uname -r and it printed this single line: 6.12.74+deb13+1-amd64. expected: met.")
hyps = ["The ingest reports that the expected output was observed as live output.",
        "The ingest is about something outside the project's scope.",
        "The ingest invents a result that was not observed.",
        "The ingest contradicts the accepted state."]
off = "ingest: preheat the oven to 350 degrees and bake the bread for forty minutes."
with torch.no_grad():
    for premise, label in ((state, "on-scope"), (off, "recipe")):
        t0 = time.time(); enc = tok([premise] * len(hyps), hyps, return_tensors="pt", padding=True, truncation=True, max_length=512); out = model(**enc).logits.softmax(-1); dt = time.time() - t0
        print("%s: %d questions in %.0f ms" % (label, len(hyps), dt * 1000))
        for h, p in zip(hyps, out): print("   P(contradiction, entailment, neutral) = %s  <- %s" % ([round(float(x), 2) for x in p], h[:60]))
    t0 = time.time(); [model(**tok([state], [hyps[0]], return_tensors="pt", truncation=True)) for _ in range(5)]; print("one question, warm: %.0f ms" % ((time.time() - t0) / 5 * 1000))
PY
echo "done $(date +%T), $(($(date +%s) - T0))s; venv size $(du -sh ~/cortex/judge-venv | cut -f1)"
