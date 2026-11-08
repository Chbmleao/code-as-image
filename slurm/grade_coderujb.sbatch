#!/bin/bash
#SBATCH --job-name=ufm9-ujb-grade
#SBATCH --partition=gorgonas
#SBATCH --cpus-per-task=32
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=/snfs2/carlosleao/ufm9/logs/ujb_grade_%j.out
# usage: sbatch slurm/grade_coderujb.sbatch CODE_DIR ANSWERS_JSONL OUT_JSONL
# Defects4J setup as in benchmarks/coderujb/gold_check.sbatch.
set -uo pipefail
C="${1:?code dir}" ANS="${2:?answers.jsonl}" OUT="${3:?output jsonl}"
D=/snfs2/carlosleao/ufm7
echo "node $(hostname) start $(date -Is) code $C"
# shellcheck source=/dev/null
source $D/d4j/activate.sh
# checkouts and builds go to node-local disk, only the results file is on NFS
WORK=/tmp/ufm9_ujb_${SLURM_JOB_ID}
mkdir -p "$WORK"
export HOME=$WORK
# the passwd home does not exist on the gorgonas nodes, and tests such as
# Lang SystemUtilsTest::testGetUserHome assert that user.home exists
export JAVA_TOOL_OPTIONS="-Duser.home=$WORK"
trap 'rm -rf $WORK' EXIT
# the budgets the calibration grading ran with (ufm7 logs); the script defaults of 120 and 180 s
# time out on Closure, whose compile alone takes minutes, and would count gold solutions as failures
export UJB_TEST_BUDGET=${UJB_TEST_BUDGET:-600} UJB_SUITE_BUDGET=${UJB_SUITE_BUDGET:-1200}
java -version 2>&1 | head -1
python3 --version
echo "cpus $(nproc), budgets test $UJB_TEST_BUDGET suite $UJB_SUITE_BUDGET"
python3 -I "$C/slurm/launch.py" codeimg.grade.coderujb "$ANS" "$WORK" "$OUT" 8
echo "end $(date -Is)"
