#!/bin/bash
# usage: scripts/sync_cluster.sh
# Copies the code (tracked and untracked-but-not-ignored files under the pipeline dirs) to a new
# dated dir on the cluster and prints its path. Jobs are submitted against that dir, so editing
# the code here never changes a queued job. The dir is made read-only after the copy.
#
# With uncommitted changes the sha in the name does not identify the code, and a hash of
# `git diff HEAD` would miss untracked files. CODE_FILES.sha256 lists the sha256 of every copied
# file, sorted by path, and CODE_VERSION records the sha256 of that listing (files_sha256). On the
# cluster, `sha256sum -c CODE_FILES.sha256` checks the copy; the same listing over a later commit
# shows whether it holds the code that ran.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
PATHS=(src slurm configs manifests scripts pyproject.toml results/block1/dstudy.json)
SHA=$(git rev-parse --short HEAD)
DIRTY=$(git status --porcelain -- "${PATHS[@]}" | head -c1)
NAME="$(date +%Y%m%d-%H%M)-$SHA${DIRTY:+-dirty}"
DEST=/sonic_home/carlosleao/ufm9/$NAME
LIST=$(mktemp) SUMS=$(mktemp)
trap 'rm -f "$LIST" "$SUMS"' EXIT
git ls-files -co --exclude-standard -- "${PATHS[@]}" | LC_ALL=C sort > "$LIST"
tr '\n' '\0' < "$LIST" | xargs -0 shasum -a 256 > "$SUMS"
FILES_SHA=$(shasum -a 256 < "$SUMS" | cut -d' ' -f1)
ssh -o BatchMode=yes phocus4 "test ! -e $DEST && mkdir -p $DEST"
rsync -a --files-from="$LIST" ./ "phocus4:$DEST/"
rsync -a "$SUMS" "phocus4:$DEST/CODE_FILES.sha256"
{
  echo "head $(git rev-parse HEAD)"
  echo "files_sha256 $FILES_SHA"
  echo "synced $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git status --porcelain -- "${PATHS[@]}"
} | ssh -o BatchMode=yes phocus4 "cat > $DEST/CODE_VERSION && chmod -R a-w $DEST"
echo "$DEST"
echo "files_sha256 $FILES_SHA"
