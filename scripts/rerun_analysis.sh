#!/bin/bash
# usage: scripts/rerun_analysis.sh [--no-r] [--reliability]
#   --no-r         skip the two analysis/glmm_main.R fits (the reports then read the committed
#                  glmm.json and glmm_contrast_cov.csv)
#   --reliability  also refit analysis/reliability.R (83 min on an M4 laptop)
#   R_ENV          the conda env with analysis/environment.yml (default codeimg-glmm)
#
# Rebuilds results/analysis/, results/claude/ (findings, gaps, ranks, figures), results/reliability/
# (report), results/block1/dstudy.*, results/audit/summary.md and the last-block report from the
# committed answer tables.
# The steps that read the model replies run only where those exist: scratch/contamination/
# (scripts/contamination_inputs.py) for the contamination flags and the Claude gaps, and the
# Claude run directory (CLAUDE_RUN, default ~/UFMG/ufm9-claude/full) for replies.json.
set -euo pipefail
cd "$(dirname "$0")/.."

with_r=1
with_rel=0
for a in "$@"; do
  case "$a" in
    --no-r) with_r=0 ;;
    --reliability) with_rel=1 ;;
    *) echo "unknown option $a" >&2; exit 2 ;;
  esac
done
CLAUDE_RUN="${CLAUDE_RUN:-$HOME/UFMG/ufm9-claude/full}"
R_ENV="${R_ENV:-codeimg-glmm}"
an() { uv run python scripts/analysis.py "$@"; }
# glmm_main.R and reliability.R ask for single-threaded BLAS, so a rerun writes the same numbers
rs() { OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 mamba run -n "$R_ENV" Rscript "$@"; }

t() { local s=$SECONDS; echo "== $*"; "$@"; echo "   $((SECONDS - s)) s"; }
skip() { echo "== skipped: $1"; }

# the run counts per model come from dstudy.json, which the analysis steps read
t uv run python scripts/dstudy.py
t an gaps
t an prep --scratch scratch/analysis
if [ $with_r = 1 ]; then t rs analysis/glmm_main.R --in scratch/analysis --out results/analysis
else skip "glmm_main.R, 5 models (--no-r)"; fi
if [ -d scratch/contamination ]; then t an contamination --answers scratch/contamination
else skip "contamination, 5 models (no scratch/contamination)"; fi
t an report

t an prep --models all --scratch scratch/analysis_all
if [ $with_r = 1 ]; then
  t rs analysis/glmm_main.R --in scratch/analysis_all --out results/claude/analysis
else skip "glmm_main.R, 7 models (--no-r)"; fi
if [ -d scratch/contamination ]; then
  t an gaps --models claude --answers scratch/contamination
  t an contamination --models all --answers scratch/contamination
else skip "Claude gaps and contamination (no scratch/contamination)"; fi
if [ -d "$CLAUDE_RUN" ]; then t an replies --run-dir "$CLAUDE_RUN"
else skip "replies.json (no $CLAUDE_RUN)"; fi
t an ranks
t an report --models all

t uv run python scripts/reliability.py prep
if [ $with_rel = 1 ]; then t rs analysis/reliability.R --workers 6
else skip "reliability.R (no --reliability)"; fi
t uv run python scripts/reliability.py report

t uv run python scripts/audit_sample.py summary
t uv run python scripts/last_block.py report
