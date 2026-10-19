Codex authenticates through the **Codex CLI**: once you're signed in, it writes an access token and account ID to `~/.codex/auth.json`, and AI Status uses those to call OpenAI's usage API. No manual token copying — just log in to the CLI.

## Requirements

- The **Codex CLI** signed in
- `python3` and `curl` (already required by AI Status)

## Step 1 — Sign in to the Codex CLI

Install and log in to the Codex CLI. After signing in, it stores your credentials at:

```
~/.codex/auth.json
```

AI Status reads `tokens.access_token` and `tokens.account_id` from that file — that's all it needs.

## Step 2 — Enable it in AI Status

Right-click the AI Status module to open the config TUI, make sure **Codex** is enabled, then left-click to refresh. Codex's usage windows show up in the tooltip within a few seconds.

## What it tracks

On paid plans, a **5-hour** and a **weekly** usage window; on the free plan, a single **monthly** window. Each comes with a reset timer, plus your plan type.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Shows nothing | `~/.codex/auth.json` is missing or empty — sign in to the Codex CLI again. |
| Blank after a while | The stored token was rotated; re-run the CLI login to refresh `auth.json`. |
| Wrong plan/windows | Confirm you're logged into the account whose usage you want to track. |

Run the provider's fetch script by hand to see the raw response:

```bash
bash ~/.local/share/ai-status/packages/lib/src/providers/codex/query.sh
```

## Multiple accounts

Extra Codex logins show up on their own. AI Status looks for config folders you run Codex with through `CODEX_HOME` — `~/.codex-<name>` and `~/.config/seats/codex/<name>` (where [seats](https://github.com/gelzinn/seats) keeps them; `$SEATS_HOME` moves it) — and adds one connection per signed-in account, labeled with its email. Renaming or moving a folder keeps the same connection, and `~/.codex` stays the regular Codex entry.

For a login kept anywhere else, set `auth_file` to that account's Codex `auth.json`, use `CODEX_HOME`, or map `CODEX_ACCESS_TOKEN` and, when needed, `CODEX_ACCOUNT_ID` to separate environment variables. This collector requires ChatGPT OAuth; OpenAI API keys belong to the OpenAI API provider. There is no application-imposed account limit. See the [authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).
