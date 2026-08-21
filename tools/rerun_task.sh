#!/usr/bin/env bash
# Re-run one task for models whose run predates a task-config change.
#
#     bash tools/rerun_task.sh reasoning_uz gemma4-26b qwen35-27b
#
# Deletes only that task's per-item file and re-runs into the SAME run id, so
# resume keeps every other task's results untouched. This is why per-item
# records are kept: a protocol correction costs one task, not a whole run.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:src"
PY="./.venv/bin/python"; [ -x "$PY" ] || PY="python3"

TASK="${1:?usage: rerun_task.sh <task> <model-config>...}"; shift
[ $# -gt 0 ] || { echo "no models given"; exit 1; }

for m in "$@"; do
  # Batches use the model config name as the run id (tools/run_batch.sh);
  # fall back to the newest timestamped directory for older runs.
  run="runs/$m"
  [ -d "$run" ] || run=$(ls -dt runs/*"$m"* 2>/dev/null | head -1)
  if [ -z "$run" ] || [ ! -d "$run" ]; then echo "  ✗ $m: no run directory"; continue; fi

  echo
  echo "════════ $m — re-running $TASK in $(basename "$run") ════════"
  rm -f "$run/$TASK.jsonl"
  $PY -m idrockbench.cli run --model "$m" --tasks "$TASK" --run-id "$(basename "$run")" \
    || echo "  ✗ $m failed"
done

echo
$PY -m idrockbench.cli report --suite core
