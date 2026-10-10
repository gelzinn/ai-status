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
  # Release packages are not git checkouts, and git is optional for users.
  # A checkout without an origin must also keep working under set -e.
  if command -v git >/dev/null 2>&1 && CONFIG_REPO_URL=$(git -C "$(dirname "$0")" remote get-url origin 2>/dev/null); then
    REPO_URL="${CONFIG_REPO_URL/#git@github.com:/https:\/\/github.com/}"
    REPO_URL="${REPO_URL%.git}"
  fi
  : "${REPO_URL:=https://github.com/gelzinn/ai-status}"
fi

export PROJECT_NAME
: "${PROJECT_NAME:="AI Status"}"
