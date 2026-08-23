#!/usr/bin/env bash
# Instruction following for DiffusionGemma, the one cell missing from the table.
#
# Its weights are deleted after each use because they are 49 GB on a disk that
# sits near full, so this re-fetches them, starts the shim server, runs the
# track, and clears up again. The environment and server.py are kept between
# runs: those took the debugging, the weights are a fifteen minute download.
#
# The server refuses to start if its first generation decodes empty, which is
# the failure that would otherwise score this model zero on every item and look
# like incapacity rather than a wrapper bug.
set -uo pipefail
cd ~/idrockbench
export PYTHONPATH=src

echo "fetching weights $(date -u +%Y-%m-%dT%H:%M:%SZ)"
export HF_HOME=~/dgserve/hf
~/dgserve/.venv/bin/hf download google/diffusiongemma-26B-A4B-it \
  --local-dir ~/dgserve/model > /dev/null 2>&1 || { echo "x download failed"; exit 1; }
du -sh ~/dgserve/model
df -h / | tail -1

echo "starting server $(date -u +%Y-%m-%dT%H:%M:%SZ)"
( cd ~/dgserve && setsid nohup ./.venv/bin/python -m uvicorn server:app \
    --host 127.0.0.1 --port 8077 > ~/dgserve/srv.log 2>&1 < /dev/null & )

for _ in $(seq 1 60); do
  curl -s -m 3 http://127.0.0.1:8077/v1/models > /dev/null 2>&1 && break
  grep -aqE "Traceback|refusing to serve" ~/dgserve/srv.log 2>/dev/null && {
    echo "x server failed to start"; tail -5 ~/dgserve/srv.log; exit 1; }
  sleep 10
done
grep -a "self-test" ~/dgserve/srv.log | tail -1

echo "running ifeval $(date -u +%Y-%m-%dT%H:%M:%SZ)"
./.venv/bin/python -m idrockbench.cli run --model diffusiongemma-26b \
  --tasks ifeval_uz --run-id ife-diffusiongemma-26b \
  || echo "x run did not complete"

pkill -f "uvicorn server:app" 2>/dev/null
sleep 5
rm -rf ~/dgserve/model
echo "cleaned up, disk now:"
df -h / | tail -1
date -u +"done %Y-%m-%dT%H:%M:%SZ"
