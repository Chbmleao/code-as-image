#!/bin/bash
#SBATCH --job-name=ufm9-dev-grade
#SBATCH --partition=gorgonas
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --dependency=singleton
#SBATCH --output=/snfs2/carlosleao/ufm9/logs/dev_grade_%j.out
# usage: sbatch slurm/grade_deveval.sbatch CODE_DIR ANSWERS_JSONL OUT_JSONL
# Grades in the work tree the ufm7 gold check used, so each repo's .eggs are already fetched.
# That tree is shared, so --dependency=singleton keeps a second grading job from splicing into it
# at the same time (keep the job name).
set -uo pipefail
C="${1:?code dir}" ANS="${2:?answers.jsonl}" OUT="${3:?output jsonl}"
W=/snfs2/carlosleao/ufm7/deveval
RUN=$W/work
echo "node $(hostname) start $(date -Is) code $C"
export PATH=$W/venv/bin:$PATH HOME=$RUN XDG_CACHE_HOME=$RUN/.cache PYTHONDONTWRITEBYTECODE=1
python --version
python -I "$C/slurm/launch.py" codeimg.grade.deveval "$ANS" "$W/src/Source_Code" \
  "$RUN/Source_Code" "$OUT" 14
rc=$?
echo "end $(date -Is) exit $rc"
exit $rc
