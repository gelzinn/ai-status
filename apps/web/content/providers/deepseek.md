DeepSeek exposes the prepaid funds available for API calls. AI Status reads that account balance and its granted/purchased credit breakdown, so you can see whether a top-up is needed before starting more API work.

## Requirements

A DeepSeek API platform account and a valid API key; network access to `api.deepseek.com`. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Sign in to the [DeepSeek API platform](https://platform.deepseek.com/) and create or copy an API key from API Keys. Use the account whose prepaid funds you want to monitor.

## Step 2 — Configure the connection

Provide `DEEPSEEK_API_KEY` to AI Status, or map it to an account-specific environment variable as shown below. The collector does not read a DeepSeek chat browser session.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add deepseek --id deepseek-personal --label Personal --env DEEPSEEK_API_KEY=DEEPSEEK_PERSONAL_CREDENTIAL
ai-status accounts add deepseek --id deepseek-work --label Work --env DEEPSEEK_API_KEY=DEEPSEEK_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "deepseek-work",
  "provider": "deepseek",
  "label": "Work",
  "env": {
    "DEEPSEEK_API_KEY": {
      "from_file": "/path/to/private-credentials/deepseek-work-key"
    }
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **DeepSeek** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

The [balance API](https://api-docs.deepseek.com/api/get-user-balance/) returns **Available balance**, plus **Granted credits** and **Purchased credits** when present. These are remaining monetary amounts, not cumulative spending. Granted credits are the unexpired grants reported by DeepSeek. Currency entries remain separate; USD and CNY are never added together.

## Limits and troubleshooting

This integration has no token counts, model-level cost history, monthly spend, or rolling subscription window. A balance does not acquire a percentage or reset timer. Separate keys can still report the same account funds; creating another key does not create another wallet.

| Symptom | What to check |
|---|---|
| Missing credential | Check that DEEPSEEK_API_KEY or its referenced source is available to the running app. |
| Rejected key | Create a replacement in the API platform and update that connection’s source. |
| Unexpected currency or funds | Compare with the balance page for the account owning this key, including grants and top-ups. |
| Balance unavailable | Check the platform account and API availability; unavailable data is not a zero balance. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
