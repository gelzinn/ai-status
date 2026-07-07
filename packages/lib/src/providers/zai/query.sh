#!/bin/bash
set -e

AUTH_FILE="$HOME/.local/share/opencode/account.json"
API_KEY=""

if [[ -f "$AUTH_FILE" ]]; then
    API_KEY=$(jq -r '.accounts[] | select(.serviceID == "zai-coding-plan" or .serviceID == "zai") | .credential.key' "$AUTH_FILE" 2>/dev/null | head -n 1)
fi

if [[ -z "$API_KEY" ]]; then
    echo '{"success": false}'
    exit 0
fi

curl -s "https://api.z.ai/api/monitor/usage/quota/limit" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Accept: application/json" 2>/dev/null || echo '{"success": false}'
