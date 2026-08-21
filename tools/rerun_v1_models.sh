#!/usr/bin/env bash
# Re-evaluate the ten models from the v1 leaderboard on the v2 harness.
#
# Run this on the machine that hosts Ollama, or point OLLAMA_BASE_URL at it:
#
#     export OLLAMA_BASE_URL=http://gpu-host:11434/v1
#     bash tools/rerun_v1_models.sh
#
# Each model resumes if interrupted, so re-running the script is safe and cheap.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:src"

# deepseek-r1-32b is deliberately last: it is a reasoning distill that cannot
# answer directly and needs ~2 minutes per item on this hardware, against under
# a second for the others. Running it first would hold up the whole board.
MODELS=(
  gemma4-26b
  gemma4-e4b
  alloma-8b
  llama31-70b
  llama31-8b
  qwen35-35b
  qwen35-9b
)

# Excluded, with reasons recorded in their configs and docs/methodology.md:
#   deepseek-r1-32b  no answer under the direct-answer protocol at any budget
#   gpt-oss-20b      same
#   mistral-small32-24b  not pulled on spark-3 (`ollama pull mistral-small3.2:24b`)
#
# The first two are not "failures" — they are reasoning models that need the
# chain-of-thought protocol. Run them with a task config that sets
# `answer_only: false`, and report them in their own column.
for m in "${MODELS[@]}"; do
  echo
  echo "──────── $m ────────"
  # --suite core is the publishable set. Add --suite all to include the two
  # tracks that are not publication-ready (mmlu_pro_uz, ifeval_uz).
  python3 -m idrockbench.cli run --model "$m" --suite core || {
    echo "  $m failed — continuing; re-run the script to retry just this model"
  }
done

echo
echo "Rebuilding the leaderboard from runs/"
python3 -m idrockbench.cli report --suite core
