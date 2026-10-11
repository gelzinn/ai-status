Moonshot tracks prepaid API-platform funds for Kimi model calls. AI Status shows the available, cash, and voucher balances for the selected API region. Kimi coding subscription quotas use the separate Kimi integration.

## Requirements

A Moonshot/Kimi API-platform key and the region that issued it; access to `api.moonshot.ai` or `api.moonshot.cn`. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Sign in to the [international API platform](https://platform.moonshot.ai/) or [China API platform](https://platform.moonshot.cn/), open the developer console, and create an API key. These official platform addresses may redirect to Kimi-branded pages.

## Step 2 — Configure the connection

Supply `MOONSHOT_API_KEY`. The default collector uses `api.moonshot.ai` and labels amounts USD. For the China endpoint, add `"region": "cn"` to the account’s `options`; it uses `api.moonshot.cn` and CNY. Keep the key and endpoint region together.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add moonshot --id moonshot-personal --label Personal --env MOONSHOT_API_KEY=MOONSHOT_PERSONAL_CREDENTIAL
ai-status accounts add moonshot --id moonshot-work --label Work --env MOONSHOT_API_KEY=MOONSHOT_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "moonshot-work",
  "provider": "moonshot",
  "label": "Work",
  "env": {
    "MOONSHOT_API_KEY": {
      "from_file": "/path/to/private-credentials/moonshot-work-key"
    }
  },
  "options": {
    "region": "cn"
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **Moonshot** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

**Available balance**, **Cash balance**, and **Voucher balance** come from `/v1/users/me/balance`. They describe the platform’s remaining funds by category; they are not three independent amounts to add together. The collector requires the service’s success status before displaying the values, so a rejected regional request cannot silently become a zero balance.

## Limits and troubleshooting

This integration does not read a Kimi CLI login or show coding-plan weekly/session limits. It also does not collect model-level costs, token usage, or monthly spending. Monetary balances have no usage percentage or reset countdown. International and China balances are separate account contexts and currencies, so configure individual connections when monitoring both.

| Symptom | What to check |
|---|---|
| Balance request rejected | Check that the key was issued by the platform matching the configured region. |
| CNY account displayed as USD | Use region: cn for the China connection and verify its key. |
| Kimi coding quota missing | Enable the separate Kimi provider with coding subscription credentials. |
| Wrong account balance | Check the saved key reference rather than relying on the browser’s current login. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
