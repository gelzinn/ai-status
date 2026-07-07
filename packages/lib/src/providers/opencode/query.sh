#!/bin/bash
set -e

AUTH_FILE="$HOME/.local/share/opencode/auth.json"
CONFIG_FILE="$HOME/.config/opencode-bar/opencode-go.json"
API_KEY=""

if [[ -f "$AUTH_FILE" ]]; then
    API_KEY=$(jq -r '.["opencode-go"].key // empty' "$AUTH_FILE" 2>/dev/null | head -n 1)
fi

if [[ -z "$API_KEY" ]]; then
    exit 0
fi

WORKSPACE_ID=""
AUTH_COOKIE=""

if [[ -f "$CONFIG_FILE" ]]; then
    WORKSPACE_ID=$(jq -r '.workspaceId // empty' "$CONFIG_FILE" 2>/dev/null)
    AUTH_COOKIE=$(jq -r '.authCookie // empty' "$CONFIG_FILE" 2>/dev/null)
fi

if [[ -z "$WORKSPACE_ID" || -z "$AUTH_COOKIE" ]]; then
    exit 0
fi

STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $API_KEY" https://opencode.ai/zen/go/v1/models || true)

if [ "$STATUS_CODE" -ne 200 ]; then
    exit 0
fi

DASHBOARD_URL="https://opencode.ai/workspace/$WORKSPACE_ID/go"
COOKIE_HEADER="$AUTH_COOKIE"

curl -s -L "$DASHBOARD_URL" \
    -H "Accept: text/html,application/xhtml+xml" \
    -H "Cookie: $COOKIE_HEADER" \
    -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" 2>/dev/null || true
