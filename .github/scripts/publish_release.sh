#!/bin/bash
set -euo pipefail

# Release Please creates a draft first. This also resumes an existing draft
# after a failed upload, even when Release Please has no new outputs on retry.
VERSION=$(cat packages/lib/VERSION)
TAG="v$VERSION"
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT
gh release view "$TAG" --repo "$GITHUB_REPOSITORY" --json isDraft,isPrerelease,tagName > "$WORK_DIR/release.json"
if [ "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["isDraft"] and not d["isPrerelease"])' "$WORK_DIR/release.json")" != True ]; then
    echo "$TAG is already published; nothing to upload."
    exit 0
fi

git fetch origin "refs/tags/$TAG:refs/tags/$TAG"
mkdir "$WORK_DIR/source"
git archive "$TAG" packages/lib packages/shared | tar -x -C "$WORK_DIR/source"
python3 .github/scripts/build_release.py --source "$WORK_DIR/source" --output "$WORK_DIR/assets" --version "$VERSION"
gh release upload "$TAG" "$WORK_DIR/assets/ai-status-$TAG.tar.gz" "$WORK_DIR/assets/SHA256SUMS" \
    --repo "$GITHUB_REPOSITORY" --clobber

# Test the actual uploaded bytes before making them visible through latest.
mkdir "$WORK_DIR/downloaded"
gh release download "$TAG" --repo "$GITHUB_REPOSITORY" --pattern "ai-status-$TAG.tar.gz" --pattern SHA256SUMS \
    --dir "$WORK_DIR/downloaded"
(cd "$WORK_DIR/downloaded" && sha256sum --check SHA256SUMS)
gh release edit "$TAG" --repo "$GITHUB_REPOSITORY" --draft=false --latest
