# Providers & Authentication Guide

**AI Status never ships or hardcodes API keys.** Every provider script reads credentials from your existing local authentication files -- OpenCode tokens, Copilot OAuth sessions, `.codex/auth.json`, and similar. Below is how each provider authenticates.

## Provider Overview

| Provider | Auth Source | Key File |
|---|---|---|
| Antigravity | agy CLI session | agy login state (handled by Antigravity CLI) |
| Claude | Claude Code OAuth (fallback: OpenCode) | `~/.claude/.credentials.json`, `~/.local/share/opencode/auth.json` |
| Codex | Codex auth token | `~/.codex/auth.json` |
| Copilot | GitHub Copilot OAuth | `~/.config/github-copilot/host.json` |
| Kiro | Session cookie | Browser/extension session export |
| OpenCode | OpenCode auth | `~/.local/share/opencode/auth.json` |
| Z.AI | Bearer token | `~/.config/z.ai/` config files |

## Per-Provider Details

### Antigravity (Gemini + Claude/GPT)

Antigravity provides usage data for both Gemini models and Claude/GPT models through its `agy` CLI. The [query.sh](src/providers/antigravity/query.sh) uses a Python PTY to interact with the CLI, send `/usage`, and capture the quota output.

| Detail | |
|---|---|
| **Auth** | Must be logged into the `agy` CLI (`agy` launches a browser-based login on first run) |
| **Metrics** | Weekly limit and five-hour rolling limit for each model group |
| **Note** | Gemini data may not include reset timers for all periods -- this is a limitation of the API |

### Claude

Reads the Claude Code OAuth credential store to query Anthropic's usage endpoint, falling back to the OpenCode auth store when Claude Code is not installed or its token has expired.

| Detail | |
|---|---|
| **Auth** | Claude Code login (`~/.claude/.credentials.json`), or OpenCode authenticated with Claude as fallback |
| **Endpoint** | `https://api.anthropic.com/api/oauth/usage` |
| **Metrics** | Session (5-hour rolling) and weekly usage with reset timers, including per-model weekly limits; shows the subscription plan (Pro/Max/Team) when available |

### Codex

Uses the Codex access token and account ID from `~/.codex/auth.json` to call OpenAI's usage API.

| Detail | |
|---|---|
| **Auth** | `~/.codex/auth.json` with valid `access_token` and `account_id` |
| **Endpoint** | `https://chatgpt.com/backend-api/wham/usage` |
| **Metrics** | Plan type, usage percentage, and reset timer |

### Copilot

Authenticates via GitHub Copilot's OAuth token stored by the Copilot CLI.

| Detail | |
|---|---|
| **Auth** | Copilot must be signed in via `github-copilot-cli` |
| **Metrics** | Chat and completions usage with remaining counts |

### Kiro

Scrapes usage data from Kiro's web API using session cookies.

| Detail | |
|---|---|
| **Auth** | Valid session cookie exported from browser or extension |
| **Metrics** | Usage percentage and reset timer |

### OpenCode (Go)

Queries the [opencode.ai](https://opencode.ai) Go dashboard for usage statistics.

| Detail | |
|---|---|
| **Auth** | API key from `~/.local/share/opencode/auth.json` + workspace config (see below) |
| **Metrics** | Rolling, weekly, and monthly usage percentages with reset timers |

#### Setup

The provider needs a config file at `~/.config/opencode-bar/opencode-go.json` with two values from your browser:

1. **`workspaceId`** — Log in at [opencode.ai](https://opencode.ai), go to your workspace. The URL will be `https://opencode.ai/workspace/<workspaceId>/go`. Copy the ID.

2. **`authCookie`** — On the same page, open DevTools (F12) → Network tab → click any request to `opencode.ai` → in Request Headers, copy the full `Cookie` header value.

Then create the file:

```bash
mkdir -p ~/.config/opencode-bar
cat > ~/.config/opencode-bar/opencode-go.json <<'EOF'
{
  "workspaceId": "<workspaceId>",
  "authCookie": "<authCookie>"
}
EOF
chmod 600 ~/.config/opencode-bar/opencode-go.json
```

### Z.AI

Reads a bearer token from Z.AI's local configuration to query its API.

| Detail | |
|---|---|
| **Auth** | Bearer token from `~/.config/z.ai/` |
| **Metrics** | Rolling, weekly, and monthly usage with reset timers |

## Provider Architecture

Each provider lives in `src/providers/<name>/` with two files:

| File | Purpose |
|---|---|
| `query.sh` | Fetches raw data -- makes API calls, runs CLI commands, or scrapes output |
| `parse.py` | Parses the raw output into a standardized JSON structure via a `parse(raw_output)` function |

To add a new provider, create a new directory under `src/providers/` with these two files and register it via `ai-status config`.

## Troubleshooting

If a provider shows "API unreachable" or 0%:

1. Check that the relevant auth file exists and contains valid tokens
2. Run the provider's `query.sh` directly to see raw API output
3. Verify the `parse.py` can handle the raw output format

See [CONTRIBUTING.md](CONTRIBUTING.md) for development details.
