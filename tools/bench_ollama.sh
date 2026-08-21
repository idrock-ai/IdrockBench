#!/usr/bin/env bash
# A private Ollama for benchmarking, reading whichever model store already
# holds the weights.
#
# Why not use the machine's own daemon: on spark-3 it runs as user `ollama` and
# serves with `-np 1`, so a harness asking for concurrent requests gets them one
# at a time. That is invisible on tracks that return a single letter and ruinous
# on instruction following, where each generation takes over two minutes. At an
# effective concurrency of one, 535 IFEval items is fifteen hours per model.
#
# Port 11502 on both machines, deliberately, so one base_url in a model config
# is correct wherever the model runs.
#
#     bash tools/bench_ollama.sh /usr/share/ollama/.ollama/models
set -uo pipefail

STORE="${1:?usage: bench_ollama.sh <ollama models dir>}"
[ -d "$STORE" ] || { echo "no such model store: $STORE"; exit 1; }

export OLLAMA_MODELS="$STORE"
export OLLAMA_HOST=127.0.0.1:11502
export OLLAMA_NUM_PARALLEL=8
export OLLAMA_CONTEXT_LENGTH=16384
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=15m

exec ollama serve
