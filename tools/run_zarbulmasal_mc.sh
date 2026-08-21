#!/usr/bin/env bash
# Evaluate the multiple-choice zarbulmasal track across every benchmarked model.
#
# This is the recognition half of the riddle pair. The free-text task asks the
# model to name the answer; this one gives it four options. Running both over the
# same 331 items is the point: a model that picks `olma` from a list but cannot
# produce it from the clues has memorised nothing useful, and only the gap
# between the two scores shows that.
#
# Chance here is 25%, against 0% for free text, so the two numbers are not
# comparable to each other directly - only the gap is meaningful.
#
# Largest models first, so the headline numbers arrive early rather than after
# ten hours of small ones.
set -uo pipefail
cd ~/idrockbench
export PYTHONPATH=src
PY=./.venv/bin/python

MODELS=(
  qwen36-27b qwen35-35b gemma4-31b qwen38-27b qwen35-27b gemma4-26b
  nemotron35-lightning-30b gemma4-12b qwen35-9b gemma4-e4b qwen35-4b
  gemma4-e2b qwen35-2b qwen35-0.8b
)

echo "zarbulmasal_mc over ${#MODELS[@]} models"
for m in "${MODELS[@]}"; do
  echo
  echo "════════ $m ════════"
  date -u +"  started %Y-%m-%dT%H:%M:%SZ"
  # Run id is separate from the core-suite run so a riddle score can never be
  # mistaken for part of a published composite.
  $PY -m idrockbench.cli run --model "$m" --tasks zarbulmasal_mc \
      --run-id "zarb-mc-$m" \
    || echo "  x $m did not complete"
done

echo
date -u +"zarbulmasal_mc sweep complete %Y-%m-%dT%H:%M:%SZ"
