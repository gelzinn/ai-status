#!/bin/bash
export VERSION
VERSION=$(cat "$(dirname "$0")/VERSION")

WORKSPACE_CONFIG="$(dirname "$0")/../../workspace.config"
if [ -f "$WORKSPACE_CONFIG" ]; then
  # Sourcing the variables safely
  set -a
  # shellcheck source=/dev/null
  source "$WORKSPACE_CONFIG"
  set +a
fi

export REPO_URL
if [ -z "$REPO_URL" ]; then
  REPO_URL=$(git -C "$(dirname "$0")" remote get-url origin 2>/dev/null \
    | sed 's/^git@github\.com:/https:\/\/github.com\//' \
    | sed 's/\.git$//')
  : "${REPO_URL:=https://github.com/gelzinn/ai-status}"
fi

export PROJECT_NAME
: "${PROJECT_NAME:="AI Status"}"
