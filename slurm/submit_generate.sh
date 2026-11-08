#!/bin/bash
# usage: slurm/submit_generate.sh CODE_DIR RUN_DIR [generate args]
#   RUN_DIR  /snfs2/carlosleao/ufm9/<smoke|block1>, holding <benchmark>/requests.jsonl
# One job per model; each writes only its own <benchmark>/gen/<model>.jsonl, so no two jobs write
# the same file. SBATCH_TIME overrides the 2 h limit. Prints the sbatch lines and asks first.
set -eu
C="${1:?code dir}" R="${2:?run dir}"
shift 2
for b in coderujb deveval; do
  [ -f "$R/$b/requests.jsonl" ] || { echo "missing $R/$b/requests.jsonl"; exit 1; }
done
# the login node's python3 may predate tomllib, so the table names are read with sed
MODELS=$(sed -n 's/^\[models\.\(.*\)\]$/\1/p' "$C/configs/experiment.toml")
CMDS=()
for m in $MODELS; do
  CMDS+=("sbatch --job-name=ufm9-gen-$m ${SBATCH_TIME:+--time=$SBATCH_TIME} $C/slurm/generate.sbatch $C $m $R $*")
done
printf '%s\n' "${CMDS[@]}"
read -r -p "submit these ${#CMDS[@]} jobs? [y/N] " ok
[ "$ok" = y ] || exit 0
mkdir -p /snfs2/carlosleao/ufm9/logs
for c in "${CMDS[@]}"; do $c; done
