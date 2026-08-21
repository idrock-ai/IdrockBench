#!/usr/bin/env bash
# Sync the harness to a remote GPU host and make sure it can run there.
#
#     bash tools/deploy_remote.sh newuu_3@spark-3.idrock.uz
#
# `runs/` and `.venv/` are never deleted on the remote: results are the point of
# the exercise, and rebuilding the environment on every sync wastes minutes.
set -euo pipefail
HOST="${1:?usage: deploy_remote.sh user@host [remote_dir]}"
DIR="${2:-idrockbench}"

# Everything the remote OWNS. --delete would otherwise remove these on every
# sync: it has already cost a rebuilt virtualenv and a live run's log file.
# Anything generated on the remote belongs in this list.
REMOTE_OWNED=(
  '.venv'        # environment, expensive to rebuild
  'runs'         # results — the entire point of the exercise
  'logs'         # a running batch writes here
  'probe.json'   # tools/probe_models.py output
)

EXCLUDES=()
for path in "${REMOTE_OWNED[@]}" .git site/dist node_modules __pycache__ \
            .pytest_cache .ruff_cache docs/paper; do
  EXCLUDES+=(--exclude "$path")
done

rsync -az --delete "${EXCLUDES[@]}" ./ "$HOST:~/$DIR/"

ssh "$HOST" "
  set -e
  cd ~/$DIR
  # A half-deleted venv leaves the directory but no interpreter, so test
  # for the binary rather than the directory.
  [ -x .venv/bin/python ] || { rm -rf .venv; python3 -m venv .venv; }
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q pyyaml sacrebleu requests
  ./.venv/bin/python -c 'import yaml, sacrebleu, requests' && echo 'environment ok'
  PYTHONPATH=src ./.venv/bin/python -m idrockbench.cli validate 2>&1 | grep -E '^(✓|✗)'
"
echo
echo "Deployed to $HOST:~/$DIR"
