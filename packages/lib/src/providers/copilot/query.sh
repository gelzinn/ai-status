#!/bin/bash
set -e
AUTH_FILE="$HOME/.local/share/opencode/auth.json"
TOKEN=$(jq -r '."github-copilot".access // empty' "$AUTH_FILE" 2>/dev/null)
if [[ -z "$TOKEN" ]]; then
  echo '{}'
  exit 0
fi
curl -s "https://api.github.com/copilot_internal/user" \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/json" \
  -H "Editor-Version: vscode/1.96.2" 2>/dev/null || echo '{}'
