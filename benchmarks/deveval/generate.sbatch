#!/bin/bash
#SBATCH --job-name=ufm7-dev-gen
#SBATCH --partition=medusas_dev,medusas_shr
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/snfs2/carlosleao/ufm7/logs/dev_gen_%j.out
# usage: sbatch deveval/generate.sbatch <hf-model-id> [extra vllm serve args]
# Same server setup as coderujb/generate.sbatch; only the prompts and output dir differ.
set -u
MODEL="${1:?usage: sbatch deveval/generate.sbatch <hf-model-id> [extra vllm args]}"
shift
W=/snfs2/carlosleao/ufm8
C=/sonic_home/carlosleao/ufm7
D=/snfs2/carlosleao/ufm7/deveval_calib
# shellcheck source=/dev/null
source "$W/venv/bin/activate"
export HF_HOME="$W/hf" HF_HUB_OFFLINE=1
export HOME="$W/home" XDG_CACHE_HOME="$W/cache"
mkdir -p "$HOME" "$XDG_CACHE_HOME" "$D/gen"

echo "$MODEL $*"
hostname
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv

PORT=$((8000 + SLURM_JOB_ID % 1000))
VLOG=/snfs2/carlosleao/ufm7/logs/dev_vllm_$SLURM_JOB_ID.log
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

python "$C/shared/generate.py" "$MODEL" "$PORT" "$D/calib_prompts.jsonl" "$D/gen"

kill "$VLLM_PID"
wait "$VLLM_PID" 2>/dev/null
