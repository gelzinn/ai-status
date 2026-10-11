Ollama Cloud provides hosted model usage and account credits. AI Status reads the cloud account’s allowance or usage windows and purchased-credit balance. Running a local Ollama model does not create cloud billing usage.

## Requirements

An Ollama Cloud account and an API key from ollama.com; network access to the hosted service. No local Ollama server is required for this collector. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Sign in and create a key in [Ollama API key settings](https://ollama.com/settings/keys). The official [cloud guide](https://docs.ollama.com/cloud) describes key-based access and links to your account usage.

## Step 2 — Configure the connection

Provide `OLLAMA_API_KEY`, or reference a separate cloud key for each account. This collector calls `https://ollama.com/api/balance`; it does not read the local server at port 11434 or reuse the CLI’s signed-in session automatically.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add ollama --id ollama-personal --label Personal --env OLLAMA_API_KEY=OLLAMA_PERSONAL_CREDENTIAL
ai-status accounts add ollama --id ollama-work --label Work --env OLLAMA_API_KEY=OLLAMA_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "ollama-work",
  "provider": "ollama",
  "label": "Work",
  "env": {
    "OLLAMA_API_KEY": {
      "from_file": "/path/to/private-credentials/ollama-work-key"
    }
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **Ollama Cloud** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

Depending on the returned account format, AI Status shows **Monthly included credits remaining** and **Monthly included credits used**, or **Session**, **Weekly**, and **Monthly quota** when returned. Monthly quota from `limits.monthly` is distinct from monthly included credits. Monthly used credits are calculated from the reported allowance minus remaining balance, with a percentage against that allowance. Quota windows display used percentage, converting reported remaining percentages when necessary. Reset countdowns appear when supplied. **Purchased credits remaining** is separate when returned.

## Limits and troubleshooting

These metrics apply to cloud usage. There are no local token counts, GPU statistics, downloaded-model usage estimates, or per-model cost totals. Purchased credits are monetary amounts rather than quota percentages. The account response determines available windows. [Ollama authentication](https://docs.ollama.com/api/authentication) explains the difference between local and hosted access.

| Symptom | What to check |
|---|---|
| Local Ollama works, provider is blank | Configure an ollama.com cloud API key; local inference has no cloud allowance to query. |
| Signed in but missing key | CLI login is not automatically discovered by this collector; provide OLLAMA_API_KEY. |
| Monthly credits instead of weekly bars | The account returned the monthly-credit format; displayed metrics follow it. |
| Purchased balance absent | The service may omit purchased credits; absence is not assumed to mean zero. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
