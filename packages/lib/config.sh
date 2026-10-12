#!/bin/bash
export VERSION
CONFIG_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "${1:-}" != --repository-only ]; then
    VERSION=$(python3 - "$CONFIG_LIB_DIR/src" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from core import __version__
print(__version__)
PY
) || { return 1 2>/dev/null || exit 1; }
fi

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
