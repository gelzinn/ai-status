AI Status reads the signed-in Cursor user's usage summary, showing included model pools and on-demand spend for the billing cycle. If you already use Cursor IDE, its local session is usually the easiest credential source. This integration reads your dashboard session; it does not use a Cursor cloud-agent API key.

## Requirements

- Cursor IDE or a compatible Cursor CLI browser login under your OS user account.
- Alternatively, a valid session access token supplied as `CURSOR_ACCESS_TOKEN`.
- AI Status on Linux, Windows, or macOS with access to the local credential store.

`CURSOR_API_KEY` is a credential supported by Cursor's own tools, but AI Status's usage-summary collector expects a session token. See Cursor's [CLI authentication guide](https://cursor.com/docs/cli/reference/authentication) for the provider's login methods.

## Connect the signed-in account

1. Install and sign in to [Cursor](https://cursor.com/downloads), or use the browser login from the [Cursor CLI](https://cursor.com/docs/cli/overview). Current CLI documentation uses `agent login`; older installations call it `cursor-agent login`.
2. AI Status first checks `CURSOR_ACCESS_TOKEN`, then reads Cursor IDE's `User/globalStorage/state.vscdb`. The base directory is `~/.config/Cursor` on Linux (respecting `XDG_CONFIG_HOME`), `%APPDATA%/Cursor` on Windows, or `~/Library/Application Support/Cursor` on macOS.
3. If needed, the default connection checks a compatible CLI `auth.json`: Linux `~/.config/cursor/auth.json`, Windows `%APPDATA%/Cursor/auth.json`, or macOS `~/.cursor/auth.json`. macOS also supports the existing Cursor access-token Keychain entry. A custom `auth_file` can point to a compatible database or JSON containing `accessToken`.
4. Enable **Cursor** in AI Status. Linux users use Quickshell **Settings** or `ai-status config` for Waybar. On Windows open tray **Settings** and **Save**; on macOS open menu bar **Settings** and **Save**. Choose **Refresh**; Waybar also refreshes with a left-click or `ai-status refresh`.

## Track separate sessions

For independently authorized sessions, reference existing credential files:

```bash
ai-status accounts add cursor --id cursor-personal --label Personal --auth-file /path/to/personal-cursor/auth.json
ai-status accounts add cursor --id cursor-work --label Work --auth-file /path/to/work-cursor/auth.json
```

Each JSON file must contain that account's `accessToken`; filenames are not token values. Alternatively, map `CURSOR_ACCESS_TOKEN` from an account-specific variable, or use `options.access_token_env`. Explicit connections do not fall back to another IDE login. On Windows run `.\ai-status-cli.exe` from the app folder or by full path, with Windows credential paths. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## What it tracks

Included usage appears as **Cursor Models** and **Other Models** percentages consumed. On-demand spend uses currency amounts returned for the billing cycle, with a percentage only when a positive applicable cap exists. Some plans report unlimited included usage, which is displayed as **Unlimited** without a percentage. Billing-cycle end supplies the reset countdown; membership type appears when returned.

AI Status does not reconstruct token usage or sum both model pools into a new allowance. The dashboard endpoint and local storage can change with Cursor releases. AI Status reads credentials and does not renew sessions.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Cursor token invalid | Sign in again; an API key is not the JWT session token expected here. |
| 401 or 403 | Re-authenticate the account in Cursor and confirm dashboard access. |
| CLI works, no usage token found | New CLI storage may differ; use the IDE session or an explicit compatible credential source. |
| Wrong user displayed | Check `auth_file` and explicit token mappings; default discovery follows the active local login. |
| Unlimited / no bar | This reflects the provider response; no finite cap is being invented. |
| 429 / cached usage | Wait for the retry cooldown. |
