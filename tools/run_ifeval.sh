#!/usr/bin/env bash
# Evaluate verifiable instruction following across a list of models.
#
#     bash tools/run_ifeval.sh qwen36-27b gemma4-31b ...
#
# The most expensive track in the suite. Constraints ask for real writing, up to
# 1200 words on a single item, so generations run about 144 seconds each against
# under a second for a direct-answer DTM item. Budget roughly 80 minutes per
# model and split the list across machines rather than running all of them in
# one place.
#
# Two things must be true for the number to mean anything, both checked before
# this script was written:
#
#   max_tokens 4096. The longest length constraint asks for 1200 words, roughly
#   3000 tokens of Uzbek. At the previous 2048 a model would be cut off before it
#   could satisfy the instruction, and a budget limit would be scored as an
#   instruction-following failure. Probed: 4096 left every response finishing
#   naturally, the longest using 1628 tokens.
#
#   lingua installed. Without the detector the 31 language:response_language
#   constraints are excluded, and constraint_coverage silently drops on that
#   machine only, making the score unreproducible anywhere else.
#
# Read constraint_coverage beside the score. Roughly a quarter of constraints
# still lack Uzbek arguments and are excluded rather than guessed at.
set -uo pipefail
cd ~/idrockbench
export PYTHONPATH=src
PY=./.venv/bin/python

[ $# -gt 0 ] || { echo "usage: run_ifeval.sh <model-config>..."; exit 1; }

$PY -c "import lingua" 2>/dev/null || {
  echo "x lingua-language-detector missing, coverage would be understated"
  exit 1
}

echo "ifeval_uz over $# model(s)"
for m in "$@"; do
  echo
  echo "════════ $m ════════"
  date -u +"  started %Y-%m-%dT%H:%M:%SZ"
  $PY -m idrockbench.cli run --model "$m" --tasks ifeval_uz --run-id "ife-$m" \
    || echo "  x $m did not complete"
done

echo
date -u +"ifeval sweep complete %Y-%m-%dT%H:%M:%SZ"
