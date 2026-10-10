# Providers & Authentication Guide

For Windows credential locations and native CLI compatibility, see the
[Windows guide](WINDOWS.md#authentication-and-provider-compatibility).

**AI Status never ships or hardcodes API keys.** Every provider script reads credentials from your existing local authentication files -- OpenCode tokens, Copilot OAuth sessions, `.codex/auth.json`, and similar. Below is how each provider authenticates.

## Provider Overview

| Provider | Tracks | Auth Source | Key File |
|---|---|---|---|
| Antigravity | Weekly + 5-hour limits per model (Gemini, Claude/GPT) | agy CLI session | agy login state (handled by Antigravity CLI) |
| Claude | Session (5h) + weekly, including per-model weekly limits | Claude Code OAuth (fallback: OpenCode) | `~/.claude/.credentials.json`, `~/.local/share/opencode/auth.json` |
| Codex | 5-hour + weekly (a single monthly window on free plans) | Codex auth token | `~/.codex/auth.json` |
| Copilot | Chat + completions usage | OpenCode Copilot OAuth | `~/.local/share/opencode/auth.json` |
| Kiro | Usage percentage + reset timer | Native CLI session | `kiro-cli` login state |
| OpenCode | Rolling, weekly, monthly usage | OpenCode auth | `~/.local/share/opencode/auth.json` |
| Z.AI | Rolling, weekly, monthly usage | OpenCode account key | `~/.local/share/opencode/account.json` |
| Command Code | Monthly usage | Native CLI API key | `~/.commandcode/auth.json` or `COMMANDCODE_API_KEY` |

## Per-Provider Details

### Antigravity (Gemini + Claude/GPT)

Antigravity provides usage data for both Gemini models and Claude/GPT models through its `agy` CLI. The [query.py](src/providers/antigravity/query.py) uses a Unix PTY or Windows ConPTY to interact with the CLI, send `/usage`, and capture the quota output.

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
| **Endpoint** | `https://api.anthropic.com/api/oauth/usage?cedar_ember=1` |
| **Metrics** | Session (5-hour rolling) and weekly usage with reset timers, including per-model weekly limits; shows the subscription plan (Pro/Max/Team) when available |

Eligible Claude accounts also show **Reset credits** in the Quickshell panel and Waybar tooltip: available campaign resets, their labels, and expiration dates. Only unspent grants marked usable and not paused by the API are counted. The opt-in inventory requires a recognized Claude CLI user agent; the query uses published version `2.1.281`. If the service changes that requirement or reports no eligible grants, the credit section is hidden while usage remains available.

### Codex

Uses the Codex access token and account ID from `~/.codex/auth.json` to call OpenAI's usage API.

| Detail | |
|---|---|
| **Auth** | `~/.codex/auth.json` with valid `access_token` and `account_id` |
| **Endpoint** | `https://chatgpt.com/backend-api/wham/usage` |
| **Metrics** | Plan type; a 5-hour and a weekly usage window on paid plans (a single monthly window on free), each with a reset timer |

Codex also shows banked **Reset credits** when the usage response reports an available count. Only then does the query make an optional GET to `https://chatgpt.com/backend-api/wham/rate-limit-reset-credits` for titles and expirations. If that request fails, usage and the original count remain visible with **Expiration not reported**. Redeemed credits are excluded from the detail list. Counts come from the usage response, even if the detail endpoint reports a different count.

These sections display the provider's inventory for manual resets, separately from automatic usage-window reset timers. AI Status only reads it; redemption remains in the provider's own client. Redemption IDs are excluded from parsed snapshots and caches. Known past deadlines are labeled **Expired** rather than showing a negative countdown; cached provider data retains its existing cached marker.

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

If a provider shows **"API unreachable"**, **0%**, or nothing at all:

1. **Check the auth file.** Confirm the key file from the table above exists and holds a valid, non-expired token. The most common cause is an expired login — re-authenticate with that provider's own CLI or app.
2. **Run the query by hand.** Each provider has a `query.sh` you can run directly to see the raw API response:
   ```bash
   bash ~/.local/share/ai-status/packages/lib/src/providers/<name>/query.sh
   ```
3. **Read the daemon log.** Errors are written to `/tmp/ai-status-error.log`.
4. **Refresh without restarting.** After fixing credentials, left-click the module (or run `ai-status refresh`) — no need to restart Waybar.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development details.
