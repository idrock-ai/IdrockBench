#!/usr/bin/env bash
# Evaluate a list of models, smallest first, and rebuild the leaderboard.
#
#     bash tools/run_batch.sh a100     qwen35-0.8b qwen35-2b ...
#     bash tools/run_batch.sh spark-3  gemma4-26b  qwen35-27b ...
#
# Each model resumes if interrupted, so re-running the script retries only what
# failed. A model that cannot answer under the suite's protocol is skipped with
# a recorded reason rather than silently scoring zero.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:src"
PY="./.venv/bin/python"; [ -x "$PY" ] || PY="python3"

# Which suite to evaluate. Defaults to the published one; override to run a
# cheaper subset over many models:
#     SUITE=knowledge bash tools/run_batch.sh spark-3 gemma4-31b qwen35-35b
SUITE="${SUITE:-core}"

LABEL="${1:?usage: run_batch.sh <label> <model-config>...}"; shift
MODELS=("$@")
[ ${#MODELS[@]} -gt 0 ] || { echo "no models given"; exit 1; }

echo "batch '$LABEL' — ${#MODELS[@]} models, suite '$SUITE', smallest first"
printf '  %s\n' "${MODELS[@]}"
echo

for m in "${MODELS[@]}"; do
  echo
  echo "════════ $m ════════"
  date -u +'  started %Y-%m-%dT%H:%M:%SZ'
  # Stable run id per model, so re-invoking the batch RESUMES rather than
  # starting a fresh run: completed items are skipped and only failures retried.
  # Without this, any interruption — a daemon restart, a config fix — costs the
  # whole model. Use `--no-resume` on the CLI for a deliberate clean re-measure.
  if ! $PY -m idrockbench.cli run --model "$m" --suite "$SUITE" --run-id "$m"; then
    echo "  ✗ $m did not complete — re-run this script to retry just this model"
  fi
done

echo
echo "════════ rebuilding leaderboard ════════"
$PY -m idrockbench.cli report --suite core
echo "BATCH_DONE $LABEL"
