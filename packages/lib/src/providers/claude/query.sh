#!/bin/bash
# Reads the Claude OAuth token from Claude Code's credential store first,
# then falls back to OpenCode's auth store for users without Claude Code.
CLAUDE_CODE_CREDS="$HOME/.claude/.credentials.json"
OPENCODE_AUTH="$HOME/.local/share/opencode/auth.json"

TOKEN=""
PLAN=""

if [[ -f "$CLAUDE_CODE_CREDS" ]]; then
  TOKEN=$(jq -r '.claudeAiOauth.accessToken // empty' "$CLAUDE_CODE_CREDS" 2>/dev/null)
  EXPIRES_AT=$(jq -r '.claudeAiOauth.expiresAt // 0' "$CLAUDE_CODE_CREDS" 2>/dev/null)
  NOW_MS=$(($(date +%s) * 1000))
  if [[ -n "$TOKEN" && "$EXPIRES_AT" =~ ^[0-9]+$ && "$EXPIRES_AT" -gt 0 && "$EXPIRES_AT" -le "$NOW_MS" ]]; then
    TOKEN=""
  fi
  if [[ -n "$TOKEN" ]]; then
    PLAN=$(jq -r '.claudeAiOauth.subscriptionType // empty' "$CLAUDE_CODE_CREDS" 2>/dev/null)
  fi
fi

if [[ -z "$TOKEN" ]]; then
  TOKEN=$(jq -r '.anthropic.access // .claude.access // empty' "$OPENCODE_AUTH" 2>/dev/null)
fi

if [[ -z "$TOKEN" ]]; then
  echo "NO_TOKEN"
  exit 0
fi

RESPONSE=$(curl -s --max-time 15 "https://api.anthropic.com/api/oauth/usage" \
  -H "Authorization: Bearer $TOKEN" \
  -H "anthropic-beta: oauth-2025-04-20" 2>/dev/null)

if [[ -z "$RESPONSE" ]]; then
  echo "OFFLINE"
  exit 0
fi

jq -cn --arg plan "$PLAN" --argjson usage "$RESPONSE" '{plan: $plan, usage: $usage}' 2>/dev/null || echo "OFFLINE"
