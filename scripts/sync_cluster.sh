#!/bin/bash
# usage: scripts/sync_cluster.sh
# Copies the code (tracked and untracked-but-not-ignored files under the pipeline dirs) to a new
# dated dir on the cluster and prints its path. Jobs are submitted against that dir, so editing
# the code here never changes a queued job. The dir is made read-only after the copy.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
SHA=$(git rev-parse --short HEAD)
DIRTY=$(git status --porcelain -- src slurm configs manifests scripts pyproject.toml | head -c1)
NAME="$(date +%Y%m%d-%H%M)-$SHA${DIRTY:+-dirty}"
DEST=/sonic_home/carlosleao/ufm9/$NAME
LIST=$(mktemp)
trap 'rm -f "$LIST"' EXIT
git ls-files -co --exclude-standard -- src slurm configs manifests scripts pyproject.toml > "$LIST"
ssh -o BatchMode=yes phocus4 "test ! -e $DEST && mkdir -p $DEST"
rsync -a --files-from="$LIST" ./ "phocus4:$DEST/"
{
  echo "head $(git rev-parse HEAD)"
  echo "synced $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git status --porcelain -- src slurm configs manifests scripts pyproject.toml
} | ssh -o BatchMode=yes phocus4 "cat > $DEST/CODE_VERSION && chmod -R a-w $DEST"
echo "$DEST"
