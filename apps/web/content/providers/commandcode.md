Command Code authenticates through its **CLI**: after `cmd login`, it writes an API key to `~/.commandcode/auth.json`, and AI Status uses that key to call Command Code's usage API. No manual token copying — just log in once (or drop in an API key).

## Requirements

- The **Command Code CLI** signed in, or a Command Code **API key**
- `python3` (already required by AI Status)

## Step 1 — Authenticate Command Code

Install the CLI and log in:

```bash
npm i -g command-code
cmd login
```

The browser flow finishes by writing your key to:

```
~/.commandcode/auth.json
```

AI Status reads the `apiKey` field from that file — that's all it needs.

> Prefer not to install the CLI? Create a key in the dashboard under **API Keys**, then either export `COMMANDCODE_API_KEY=<your-key>` or write it yourself:
>
> ```bash
> mkdir -p ~/.commandcode
> printf '{"apiKey":"%s"}\n' "$COMMANDCODE_API_KEY" > ~/.commandcode/auth.json
> ```

## Step 2 — Enable it in AI Status

Right-click the AI Status module to open the config TUI, make sure **Command Code** is enabled, then left-click to refresh. Your monthly usage shows up in the tooltip within a few seconds.

## What it tracks

Your **monthly spend** for the current billing period, shown as a percentage of your budget (spend ÷ (spend + remaining credits)) with a reset timer for when the period rolls over. The tooltip also shows the dollar figures, e.g. `$6.99 of $10 used`.

Behind the scenes it calls the same public endpoints the CLI's own usage view uses, on `api.commandcode.ai`: `whoami` → `billing/subscriptions` → `billing/credits` → `usage/summary`. It works for both personal and organization accounts.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Shows nothing | `~/.commandcode/auth.json` is missing or has no `apiKey` — run `cmd login`, or set `COMMANDCODE_API_KEY`. |
| Blank after a while | The stored key was revoked or rotated — run `cmd login` again, or create a fresh API key. |
| Confirm the key exists | `python3 -c "import json,os;print(bool(json.load(open(os.path.expanduser('~/.commandcode/auth.json'))).get('apiKey')))"` |

Run the provider's fetch script by hand to see the raw response:

```bash
~/.local/share/ai-status/packages/lib/src/providers/commandcode/query.py
```
