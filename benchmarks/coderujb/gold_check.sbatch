#!/bin/bash
#SBATCH --job-name=ufm7-ujb-gold
#SBATCH --partition=gorgonas
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=/snfs2/carlosleao/ufm7/logs/ujb_gold_%j.out
# usage: sbatch coderujb/gold_check.sbatch [LIMIT]   (LIMIT runs only the first N pending items, for a smoke test)
set -uo pipefail
D=/snfs2/carlosleao/ufm7
C=/sonic_home/carlosleao/ufm7
echo "node $(hostname) start $(date -Is)"
# shellcheck source=/dev/null
source $D/d4j/activate.sh
# checkouts and builds go to node-local disk, only the results file is on NFS
WORK=/tmp/ufm7_ujb_${SLURM_JOB_ID}
mkdir -p "$WORK"
export HOME=$WORK
# the passwd home (/home/pos/carlosleao) does not exist on the gorgonas nodes, and tests such as
# Lang SystemUtilsTest::testGetUserHome assert that user.home exists
export JAVA_TOOL_OPTIONS="-Duser.home=$WORK"
trap 'rm -rf $WORK' EXIT
java -version 2>&1 | head -1
# the same script grades model answers: UJB_ITEMS=answers.jsonl UJB_OUT=grade_results.jsonl
ITEMS=$D/coderujb/${UJB_ITEMS:-items.jsonl}
OUT=$D/coderujb/${UJB_OUT:-gold_results.jsonl}
echo "cpus $(nproc), budgets test ${UJB_TEST_BUDGET:-120} suite ${UJB_SUITE_BUDGET:-180}, $ITEMS -> $OUT"
python3 -I $C/coderujb/gold_check.py "$ITEMS" "$WORK" "$OUT" 8 ${1:+"$1"}
echo "end $(date -Is)"
