Claude is the easiest provider to set up: if you already use **Claude Code**, AI Status reads its OAuth token straight from the credential store it writes — nothing extra to configure. It calls Anthropic's usage endpoint and shows your session and weekly limits.

> No Claude Code? AI Status falls back to an OpenCode session authenticated with Claude (see the OpenCode auth below). Either one works.

## Requirements

- **Claude Code** signed in, **or** OpenCode authenticated with Anthropic
- `curl` and `jq` (already required by AI Status)

## Step 1 — Sign in to Claude Code

Install [Claude Code](https://docs.claude.com/en/docs/claude-code) and log in. Once you're signed in, it stores an OAuth token at:

```
~/.claude/.credentials.json
```

That's the only thing AI Status needs — it reads `claudeAiOauth.accessToken` from that file (and your plan from `subscriptionType`).

## Alternative — via OpenCode

If you don't use Claude Code, authenticate Anthropic through OpenCode instead:

```bash
opencode auth login
```

Pick **Anthropic / Claude** and complete the sign-in. AI Status will read the token from `~/.local/share/opencode/auth.json` as a fallback.

## Step 2 — Enable it in AI Status

Right-click the AI Status module to open the config TUI, make sure **Claude** is enabled, then left-click to refresh.

## What it tracks

Your session (5-hour rolling) and weekly usage, **including per-model weekly limits** (e.g. Fable's own weekly window), each with a reset timer. Your plan (Pro / Max / Team) is shown when available.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Shows nothing / `NO_TOKEN` | Neither source has a token — sign in to Claude Code, or run `opencode auth login` and pick Anthropic. |
| Was working, now blank | The token expired. AI Status ignores expired tokens automatically; just re-open Claude Code (or re-run the OpenCode login) to refresh it. |
| `OFFLINE` in the tooltip | Couldn't reach `api.anthropic.com` — check your connection.

Run the provider's fetch script by hand to see the raw response:

```bash
bash ~/.local/share/ai-status/packages/lib/src/providers/claude/query.sh
```

## Multiple accounts

Set `auth_file` to that account's Claude Code `.credentials.json`, use `CLAUDE_CONFIG_DIR`, or map `CLAUDE_ACCESS_TOKEN` to its own environment variable. Explicit accounts do not fall back to another OpenCode session. There is no application-imposed account limit. See the [authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).
