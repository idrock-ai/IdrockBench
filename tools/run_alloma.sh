#!/usr/bin/env bash
# The published suite for the three alloma-Instruct models, on the DGX Spark.
#
# Smallest first, so a mistake surfaces on the 1B rather than after the 8B has
# spent hours. Each model resumes if interrupted: re-running retries only what
# failed.
#
# Traffic goes through tools/alloma_proxy.py on 11503, NOT straight to Ollama.
# The alloma tokenizer has no Uzbek apostrophe -- it carries the literal string
# APST fused into Uzbek wordpieces -- and the model card asks callers to
# substitute on the way in and reverse it on the way out. Measured on a 30-item
# smoke: 14 of 30 responses came back containing APST without the proxy, 0 of 30
# with it. The proxy must be up before this runs, and the check below is the
# gate rather than a comment saying so.
set -uo pipefail
cd ~/idrockbench
export PYTHONPATH=src
PY=./.venv/bin/python

curl -s -m 5 http://127.0.0.1:11503/api/tags > /dev/null 2>&1 || {
  echo "x apostrophe proxy is not up on 11503 — refusing to run"
  echo "  start it: ./.venv/bin/python tools/alloma_proxy.py --port 11503"
  exit 1
}

for m in alloma-1b alloma-3b alloma-8b; do
  echo
  echo "════════ $m ════════"
  date -u +"  started %Y-%m-%dT%H:%M:%SZ"
  $PY -m idrockbench.cli run --model "$m" --suite core --run-id "$m" \
    || echo "  x $m core suite did not complete"

  # Published but not composited, so it runs under its own id like the other
  # models. --suite takes precedence over --tasks, so these cannot be combined.
  $PY -m idrockbench.cli run --model "$m" --tasks zarbulmasal_mc \
      --run-id "zarb-mc-$m" || echo "  x $m zarbulmasal_mc did not complete"
done

echo
date -u +"alloma sweep complete %Y-%m-%dT%H:%M:%SZ"
