#!/bin/bash
# Run on the login node: downloads one model, then queues its check job with any extra vllm args.
# Usage: bash queue_one.sh <hf-model-id> [extra vllm serve args]
set -u
MODEL="${1:?usage: bash queue_one.sh <hf-model-id> [extra vllm args]}"
W=/snfs2/carlosleao/ufm8
CODE=/sonic_home/carlosleao/ufm8
# shellcheck disable=SC1091
source "$W/venv/bin/activate"
export HF_HOME="$W/hf"

cd "$CODE" || exit 1
echo "$(date '+%F %T') downloading $MODEL"
if python -c "
import sys
from huggingface_hub import snapshot_download
snapshot_download(sys.argv[1], allow_patterns=['*.json', '*.jinja', '*.safetensors', '*.txt', '*.model', '*.tiktoken'])
" "$MODEL"; then
  sbatch run_checks.sbatch "$@"
else
  echo "download failed for $MODEL, not queued"
fi
