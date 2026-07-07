#!/bin/bash
AUTH_FILE="$HOME/.codex/auth.json"
if [[ ! -f "$AUTH_FILE" ]]; then
  exit 0
fi

ACCESS=$(python3 -c "import json; print(json.load(open('$AUTH_FILE'))['tokens']['access_token'])" 2>/dev/null)
ACCOUNT_ID=$(python3 -c "import json; print(json.load(open('$AUTH_FILE'))['tokens']['account_id'])" 2>/dev/null)

if [[ -z "$ACCESS" ]]; then
  exit 0
fi

curl -s --max-time 10 \
  -H "Authorization: Bearer $ACCESS" \
  -H "ChatGPT-Account-Id: $ACCOUNT_ID" \
  "https://chatgpt.com/backend-api/wham/usage" 2>/dev/null || true
