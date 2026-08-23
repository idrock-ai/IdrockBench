#!/usr/bin/env bash
# Instruction following for the seven large models, on the A100.
#
# They live on spark-3, but spark's Ollama serves with a single slot and Ollama
# refuses parallel requests for the qwen35 architecture regardless, so the 27B
# to 35B models run strictly serially there: about fifteen hours each. Measured
# on this machine the same track runs at 540 to 680 items an hour, so pulling
# each model here and deleting it again is roughly a day for all seven instead
# of a week.
#
# One model resident at a time: the seven together are about 130 GB against 78
# GB free. A pull that fails leaves the previous model deleted and the next one
# absent, so each step checks before it runs.
#
# Smallest first. This track has already turned up a wrong token budget, a
# missing language detector and a single-slot daemon, and a failure is cheaper
# to find on a 17 GB model than on a 35 GB one.
set -uo pipefail
cd ~/idrockbench
export PYTHONPATH=src
export OLLAMA_HOST=127.0.0.1:11502
OLLAMA=~/.local/bin/ollama
PY=./.venv/bin/python

$PY -c "import lingua" 2>/dev/null || {
  echo "x lingua-language-detector missing, constraint coverage would be understated"
  exit 1
}

run_one() {
  local cfg="$1" tag="$2"
  echo
  echo "════════ $cfg ($tag) ════════"
  date -u +"  started %Y-%m-%dT%H:%M:%SZ"
  df -h / | tail -1

  if ! $OLLAMA pull "$tag" >/dev/null 2>&1; then
    echo "  x pull failed: $tag"
    return 1
  fi
  $PY -m idrockbench.cli run --model "$cfg" --tasks ifeval_uz --run-id "ife-$cfg" \
    || echo "  x $cfg did not complete"
  $OLLAMA rm "$tag" >/dev/null 2>&1 && echo "  removed $tag"
}

run_one gemma4-26b               "gemma4:26b"
run_one qwen36-27b               "qwen3.6:27b"
run_one qwen38-27b               "qwen3.8:latest"
run_one qwen35-27b               "qwen3.5:27b"
run_one nemotron35-lightning-30b "nemotron-3.5-lightning:30b"
run_one gemma4-31b               "gemma4:31b"
run_one qwen35-35b               "qwen3.5:35b"

echo
date -u +"ifeval large sweep complete %Y-%m-%dT%H:%M:%SZ"
