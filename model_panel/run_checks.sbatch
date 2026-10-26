#!/bin/bash
#SBATCH --job-name=ufm8-checks
#SBATCH --partition=medusas_dev,medusas_shr
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/sonic_home/carlosleao/ufm8/logs/checks_%j.out
# Usage: sbatch run_checks.sbatch <hf-model-id> [extra vllm serve args]
# Runs the image token check, then the text-only baseline, against one vLLM server.
set -u
MODEL="${1:?usage: sbatch run_checks.sbatch <hf-model-id> [extra vllm args]}"
shift
W=/snfs2/carlosleao/ufm8
CODE=/sonic_home/carlosleao/ufm8
PY=/opt/python/3-12-1/bin/python3

# The venv was built on the login node; it only runs here if the same interpreter path exists.
if [ ! -x "$PY" ]; then
  echo "missing $PY on $(hostname). /opt/python has:"; ls /opt/python; exit 1
fi
# shellcheck disable=SC1091
source "$W/venv/bin/activate"
export HF_HOME="$W/hf" HF_HUB_OFFLINE=1
# $HOME on the GPU nodes is /home/pos/..., which is not writable there, and vLLM, inductor and
# triton all write caches under it.
export HOME="$W/home" XDG_CACHE_HOME="$W/cache"
mkdir -p "$HOME" "$XDG_CACHE_HOME"

echo "$MODEL $*"
hostname
nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv

# Two jobs can land on the same node, so the port is derived from the job id.
PORT=$((8000 + SLURM_JOB_ID % 1000))
VLOG="$CODE/logs/vllm_$SLURM_JOB_ID.log"
vllm serve "$MODEL" --port "$PORT" --max-model-len 16384 --gpu-memory-utilization 0.92 \
  --limit-mm-per-prompt '{"image": 4}' "$@" > "$VLOG" 2>&1 &
VLLM_PID=$!

for _ in $(seq 1 240); do
  curl -sf "http://localhost:$PORT/health" > /dev/null && break
  if ! kill -0 "$VLLM_PID" 2>/dev/null; then
    echo "vllm exited before becoming ready. Last lines of $VLOG:"; tail -30 "$VLOG"; exit 1
  fi
  sleep 5
done

python "$CODE/token_check.py" "$MODEL" "$PORT" | tee -a "$CODE/token_check.jsonl"
python "$CODE/text_baseline.py" "$MODEL" "$PORT"

kill "$VLLM_PID"
wait "$VLLM_PID" 2>/dev/null
