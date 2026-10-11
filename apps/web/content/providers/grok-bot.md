AI Status reads Grok Bot's weekly included usage for the signed-in desktop account. It shows how much of that allowance has been consumed and when the service says it resets. This connection monitors the account's allowance; it does not list Bots, inspect their conversations, or measure each task's cost.

## Requirements

- An eligible Grok Bot account and the official desktop app signed in.
- A compatible local encrypted session, or `GROK_BOT_ACCESS_TOKEN` holding an authorized access token.
- AI Status running as the OS user who owns the credential store.

Eligibility and account linking are described in [Grok Bot getting started](https://docs.x.ai/grok-bot/get-started). Product availability and local credential-reader compatibility are separate: a working desktop app does not guarantee every storage format can be read by AI Status.

## Connect the desktop session

1. Download the official Grok Bot desktop app from the links in [Get started](https://docs.x.ai/grok-bot/get-started) or [Grok Bot](https://x.ai/bot). Sign in to the account whose included allowance you want to monitor.
2. AI Status checks `GROK_BOT_ACCESS_TOKEN` first. Otherwise it reads `Grok Bot/sand-secrets.json` in the platform's application configuration directory: `~/.config` on Linux, `~/Library/Application Support` on macOS, or `%APPDATA%` on Windows. Linux respects `XDG_CONFIG_HOME`.
3. Local discovery uses the active account entry and the app's encrypted token format. macOS requires access to the existing Grok Bot Safe Storage Keychain item; Linux can use the user's secret service; Windows uses the app's local encryption metadata. If storage is incompatible, use an explicit authorized token source or `auth_file` referencing a compatible store. `options.access_token_env` can name a token variable.
4. Enable **Grok Bot** in AI Status. On Linux use Quickshell **Settings** or `ai-status config` for Waybar. On Windows open tray **Settings** and **Save**; on macOS open menu bar **Settings** and **Save**. Choose **Refresh**. Waybar also refreshes by left-clicking the module or running `ai-status refresh`.

## Separate account connections

Use references to independently authorized session variables:

```bash
ai-status accounts add grok-bot --id bot-personal --label Personal --env GROK_BOT_ACCESS_TOKEN=BOT_PERSONAL_ACCESS_TOKEN
ai-status accounts add grok-bot --id bot-work --label Work --env GROK_BOT_ACCESS_TOKEN=BOT_WORK_ACCESS_TOKEN
```

The right-hand values are source variable names, never literal tokens. For desktop startup, a JSON connection definition can map `GROK_BOT_ACCESS_TOKEN` with `from_file` to a private token file. Alternatively, use `--auth-file` for a compatible native store; encrypted files can depend on the owning OS account and its key store. Explicit connections do not borrow another active login. On Windows run `.\ai-status-cli.exe` from the app folder or by full path. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## What it tracks

Weekly included usage is a percentage **used**, with the next reset when reported. A plan label appears when available. If the response explicitly reports no included allowance, AI Status displays **No included allowance** without a guessed percentage.

The integration does not expose an on-demand balance, per-Bot usage, or all SuperGrok product usage. Use [SuperGrok](/providers/supergrok) for its supported subscription billing metrics. AI Status reads the session but does not refresh tokens or perform provider sign-in. The desktop authentication and usage endpoint can change independently of AI Status.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Cannot read encrypted session | Run as the same OS user, unlock the key store, and check desktop storage compatibility. |
| No token for a named connection | Provide its own `auth_file` or explicit access-token reference. |
| 401 or 403 | Sign in again and confirm the account's Grok Bot entitlement. |
| Wrong allowance or account | Local discovery follows the desktop app's active account; check the connection source. |
| No included allowance | Verify plan eligibility in the provider; this is an explicit service response. |
| 429 / cached usage | Wait for the retry cooldown; Refresh cannot bypass it. |
