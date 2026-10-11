Kilo’s coding account has a credit balance used by its services. AI Status reads that balance for your personal account or an explicitly selected organization, giving you a quick view of the credits available for Kilo work.

## Requirements

A Kilo account and its Kilo API key; for organization tracking, the organization ID and account access to it. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Follow [Kilo’s authentication guide](https://kilo.ai/docs/getting-started/setup-authentication): sign in at [app.kilo.ai](https://app.kilo.ai/), open Your Profile in your personal account, and copy the API key near the bottom.

## Step 2 — Configure the connection

Provide `KILO_API_KEY`. To track an organization, add `"organization_id": "YOUR_KILO_ORGANIZATION_ID"` to the connection’s `options`, replacing the label with the real ID. AI Status sends this as the organization context header.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add kilo --id kilo-personal --label Personal --env KILO_API_KEY=KILO_PERSONAL_CREDENTIAL
ai-status accounts add kilo --id kilo-work --label Work --env KILO_API_KEY=KILO_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "kilo-work",
  "provider": "kilo",
  "label": "Work",
  "env": {
    "KILO_API_KEY": {
      "from_file": "/path/to/private-credentials/kilo-work-key"
    }
  },
  "options": {
    "organization_id": "YOUR_KILO_ORGANIZATION_ID"
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **Kilo** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

**Available credit balance** is the USD amount reported by `/api/profile/balance`. The optional organization context changes which balance is requested; without it the request uses the personal account context. It is an account credit snapshot, with no invented maximum or percentage.

## Limits and troubleshooting

This guide covers Kilo coding account credits. Signing in to the editor does not automatically configure the collector’s key. It does not collect task counts, model usage, a Kilo Pass allowance window, or credits held by a separately configured external service. Kilo’s [gateway authentication documentation](https://kilo.ai/docs/gateway/authentication) explains organization context and BYOK billing; those external charges are not a Kilo credit balance.

| Symptom | What to check |
|---|---|
| No Kilo data | Configure KILO_API_KEY explicitly; extension login alone is insufficient here. |
| Personal balance shown for work | Check organization_id in the work connection’s options. |
| Organization request rejected | Confirm the key’s account can access that organization and the ID is correct. |
| Coding activity does not reduce credits | Check how that task was billed in Kilo; the collector only reports the Kilo wallet. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
