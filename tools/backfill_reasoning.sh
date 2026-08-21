#!/usr/bin/env bash
# Backfill the reasoning_uz cell for the six models that lack a usable one.
#
# Four never ran the track. Two ran it under the old configuration and scored 7
# and 4 items out of 100, below the publish floor, so their per-item files are
# deleted before the run: resume retries only `error` rows, and a truncated row
# counts as done, so leaving them in place would skip exactly the items that
# need redoing.
#
# This runs on the A100 rather than spark-3, even though spark holds every model
# already. Measured, spark manages about 4.5 reasoning items an hour against
# roughly ten times that here, so handing spark even one model would make the
# whole batch finish later than running all six on one faster machine.
#
# Each model is pulled, run, then removed: the six together are ~130 GB against
# 78 GB free, so only one is ever resident.
#
# The run ids match the existing run directories deliberately. With those files
# present, resume skips the completed dtm and translation items and evaluates
# only the missing track, which is what turns six partial rows into six
# complete ones instead of six orphan runs.
set -uo pipefail
cd ~/idrockbench
export PYTHONPATH=src
export OLLAMA_HOST=127.0.0.1:11500
OLLAMA=~/.local/bin/ollama

run_one() {
  local cfg="$1" tag="$2" runid="$3"
  echo
  echo "════════ $cfg ($tag) ════════"
  date -u +"  started %Y-%m-%dT%H:%M:%SZ"
  if ! $OLLAMA pull "$tag" >/dev/null 2>&1; then
    echo "  x pull failed: $tag"
    return 1
  fi
  ./.venv/bin/python -m idrockbench.cli run --model "$cfg" --suite core --run-id "$runid" \
    || echo "  x $cfg did not complete"
  $OLLAMA rm "$tag" >/dev/null 2>&1 && echo "  removed $tag"
  df -h / | tail -1
}

# Smallest first, so a failure surfaces early and cheaply.
run_one gemma4-26b               "gemma4:26b"                 "gemma-4-26b-20260819T145922Z"
run_one qwen38-27b               "qwen3.8:latest"             "qwen38-27b"
run_one gemma4-31b               "gemma4:31b"                 "gemma4-31b"
run_one qwen35-35b               "qwen3.5:35b"                "qwen35-35b"
run_one nemotron35-lightning-30b "nemotron-3.5-lightning:30b" "nemotron35-lightning-30b"
run_one qwen35-27b               "qwen3.5:27b"                "qwen3.5-27b-20260819T161458Z"

echo
date -u +"backfill complete %Y-%m-%dT%H:%M:%SZ"
