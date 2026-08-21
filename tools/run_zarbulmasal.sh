#!/usr/bin/env bash
# Evaluate the free-text zarbulmasal track across every benchmarked model.
#
# The recall half of the riddle pair, and the one that matters. The model is
# given the riddle and must NAME the answer; there are no options to choose
# from, so chance is 0% rather than 25%.
#
# Run this against run_zarbulmasal_mc.sh over the same 331 items. The gap
# between the two is the finding: probed on 20 items, Qwen3.6 27B scored 75.5%
# picking the answer from four options and 20.0% producing it from the clues.
# A model that recognises `olma` in a list but cannot recall it has memorised
# nothing useful, and only running both formats shows that.
#
# Scoring was validated before this sweep: extraction parsed 20 of 20 with no
# truncations, and every wrong answer was a genuinely different word rather than
# a correct answer the matcher failed to accept. In a free-text task the
# dangerous error is the false negative, because it depresses every model at
# once and looks like difficulty rather than a broken scorer.
set -uo pipefail
cd ~/idrockbench
export PYTHONPATH=src
PY=./.venv/bin/python

MODELS=(
  qwen36-27b qwen35-35b gemma4-31b qwen38-27b qwen35-27b gemma4-26b
  nemotron35-lightning-30b gemma4-12b qwen35-9b gemma4-e4b qwen35-4b
  gemma4-e2b qwen35-2b qwen35-0.8b
)

echo "zarbulmasal (free text) over ${#MODELS[@]} models"
for m in "${MODELS[@]}"; do
  echo
  echo "════════ $m ════════"
  date -u +"  started %Y-%m-%dT%H:%M:%SZ"
  $PY -m idrockbench.cli run --model "$m" --tasks zarbulmasal \
      --run-id "zarb-$m" \
    || echo "  x $m did not complete"
done

echo
date -u +"zarbulmasal sweep complete %Y-%m-%dT%H:%M:%SZ"
