#!/bin/bash
#SBATCH --job-name=ufm7-dev-grade
#SBATCH --partition=gorgonas
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=/snfs2/carlosleao/ufm7/logs/dev_grade_%j.out
# usage: sbatch deveval/grade.sbatch   (after make_answers has written $D/answers.jsonl)
# smoke test on the gold bodies: DEV_ANS=answers_gold.jsonl DEV_OUT=grade_gold.jsonl sbatch ...
# Grades in the work tree the gold check used, so each repo's .eggs are already fetched.
set -uo pipefail
W=/snfs2/carlosleao/ufm7/deveval
D=/snfs2/carlosleao/ufm7/deveval_calib
C=/sonic_home/carlosleao/ufm7
RUN=$W/work
echo "node $(hostname) start $(date -Is)"
export PATH=$W/venv/bin:$PATH HOME=$RUN XDG_CACHE_HOME=$RUN/.cache PYTHONDONTWRITEBYTECODE=1
python -I $C/deveval/grade_answers.py $D/${DEV_ANS:-answers.jsonl} $W/src/Source_Code \
  $RUN/Source_Code $D/${DEV_OUT:-grade_results.jsonl} 14
echo "end $(date -Is)"
