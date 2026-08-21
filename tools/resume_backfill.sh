#!/usr/bin/env bash
# Wait for the DiffusionGemma riddle runs to finish, release the machine, then
# resume the reasoning backfill.
#
# The two cannot overlap. DiffusionGemma holds 53 GB of the card and its weights
# hold 49 GB of a disk with 11 GB free, while the backfill pulls a 20 to 29 GB
# model per step. Freeing the weights is what makes room for the next pull.
#
# The backfill resumes rather than restarts: gemma4-31b keeps the 8 reasoning
# items it already completed and continues from item 9.
set -uo pipefail
cd ~/idrockbench
exec >> logs/resume_backfill.log 2>&1
echo "resume armed $(date -u +%Y-%m-%dT%H:%M:%SZ)"

while pgrep -f "idrockbench.cli run" > /dev/null; do sleep 30; done
echo "riddles finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Release the GPU and the disk.
pkill -f "uvicorn server:app" 2>/dev/null
sleep 5
rm -rf ~/dgserve/model
echo "weights removed, disk now:"
df -h / | tail -1

echo "resuming backfill $(date -u +%Y-%m-%dT%H:%M:%SZ)"
bash tools/backfill_reasoning.sh
