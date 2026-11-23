#!/bin/bash
#SBATCH --job-name=ufm9-gen
#SBATCH --partition=medusas_dev,medusas_shr
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/snfs2/carlosleao/ufm9/logs/gen_%j.out
# usage: sbatch slurm/generate.sbatch CODE_DIR MODEL RUN_DIR [generate args]
#   CODE_DIR  dated copy of this repo under /sonic_home/carlosleao/ufm9
#   MODEL     short name from configs/experiment.toml
#   RUN_DIR   holds <benchmark>/requests.jsonl; replies go to <benchmark>/gen/MODEL.jsonl
# One job per model: the model loads once and both benchmarks run, each to its own file.
# Submit through slurm/submit_generate.sh. 2 h fits the smoke run; pass --time for block 1.
# With --transcription in the generate args, vLLM gets [transcription].max_model_len.
set -u
C="${1:?code dir}" MODEL="${2:?model}" R="${3:?run dir}"
shift 3
W=/snfs2/carlosleao/ufm8
# shellcheck source=/dev/null
source "$W/venv/bin/activate"
# $HOME is not writable on the GPU nodes
export HF_HOME="$W/hf" HF_HUB_OFFLINE=1 HOME="$W/home" XDG_CACHE_HOME="$W/cache"
export PYTHONPATH="$C/src" CODEIMG_CONFIG="$C/configs/experiment.toml"
CODEIMG_JOB_START=$(date +%s)
export CODEIMG_JOB_START

SECTION=experiment
for a in "$@"; do [ "$a" = --transcription ] && SECTION=transcription; done
read -r REPO LIMIT MAXLEN < <(python - "$MODEL" "$SECTION" <<'EOF'
import sys
from codeimg import config
c = config.load()
print(c["models"][sys.argv[1]]["repo"], c["experiment"]["image_limit"], c[sys.argv[2]]["max_model_len"])
EOF
)
mapfile -t VARGS < <(python - "$MODEL" <<'EOF'
import sys
from codeimg import config
# one arg per line and nothing at all for an empty list, or mapfile reads one empty argument
sys.stdout.write("".join(a + "\n" for a in config.load()["models"][sys.argv[1]]["vllm_args"]))
EOF
)
[ -n "${REPO:-}" ] || { echo "model $MODEL not in $CODEIMG_CONFIG"; exit 1; }
echo "code $C model $MODEL ($REPO) run $R max_model_len $MAXLEN vllm args ${VARGS[*]:-} generate args $*"
hostname
CODEIMG_GPU=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)
export CODEIMG_GPU
echo "$CODEIMG_GPU"

PORT=$((8000 + SLURM_JOB_ID % 1000))
VLOG=/snfs2/carlosleao/ufm9/logs/vllm_$SLURM_JOB_ID.log
vllm serve "$REPO" --port "$PORT" --max-model-len "$MAXLEN" --gpu-memory-utilization 0.92 \
  --limit-mm-per-prompt "{\"image\": $LIMIT}" ${VARGS[@]+"${VARGS[@]}"} > "$VLOG" 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null; wait $VLLM_PID 2>/dev/null' EXIT

for _ in $(seq 1 240); do
  curl -sf "http://localhost:$PORT/health" > /dev/null && break
  if ! kill -0 "$VLLM_PID" 2>/dev/null; then
    echo "vllm exited before becoming ready. Last lines of $VLOG:"; tail -30 "$VLOG"; exit 1
  fi
  sleep 5
done
curl -sf "http://localhost:$PORT/health" > /dev/null || { echo "vllm not ready after 20 min"; exit 1; }
CODEIMG_SERVER_READY=$(date +%s)
export CODEIMG_SERVER_READY

ARGS=("$@")
for b in coderujb deveval; do
  mkdir -p "$R/$b/gen"
  python -m codeimg generate --model "$MODEL" --requests "$R/$b/requests.jsonl" \
    --out "$R/$b/gen/$MODEL.jsonl" --port "$PORT" ${ARGS[@]+"${ARGS[@]}"} || exit 1
  # the seed check is one item per model, so only the first benchmark runs it
  KEEP=(); for a in ${ARGS[@]+"${ARGS[@]}"}; do [ "$a" = --seed-check ] || KEEP+=("$a"); done
  ARGS=(${KEEP[@]+"${KEEP[@]}"})
done
