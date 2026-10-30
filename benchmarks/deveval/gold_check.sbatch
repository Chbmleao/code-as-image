#!/bin/bash
#SBATCH --job-name=ufm7-gold
#SBATCH --partition=gorgonas
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=/snfs2/carlosleao/ufm7/logs/gold_%j.out
# Code lives in /sonic_home/carlosleao/ufm7, everything generated goes under /snfs2/carlosleao/ufm7.
set -uo pipefail
D=/snfs2/carlosleao/ufm7
W=$D/deveval
C=/sonic_home/carlosleao/ufm7
echo "node $(hostname) start $(date -Is)"
curl -s -m 10 -o /dev/null -w "pypi reachable: %{http_code}\n" https://pypi.org/simple/ || echo "pypi unreachable"
# private copy so the pristine tree in $W/src stays untouched by test side effects; kept between
# resubmissions (the copy takes about 13 min) along with the .eggs each repo fetches
RUN=$W/work
[ -d $RUN/Source_Code ] || { mkdir -p $RUN && cp -a $W/src/Source_Code $RUN/; }
echo "work tree ready in $RUN $(date -Is)"
export PATH=$W/venv/bin:$PATH HOME=$RUN XDG_CACHE_HOME=$RUN/.cache PYTHONDONTWRITEBYTECODE=1
python -I $C/deveval/gold_check.py $W/data.jsonl $RUN/Source_Code $W/gold_results.jsonl 14
echo "end $(date -Is)"
