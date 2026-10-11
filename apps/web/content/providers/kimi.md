AI Status tracks supported Kimi Code subscription quota windows using a coding-plan key or the Kimi Code CLI session. This helps you see when a coding allowance is nearing its reset. For prepaid model API funds, use the separate [Moonshot integration](/providers/moonshot); Kimi Code membership and Moonshot pay-as-you-go billing are different services.

## Requirements

- A Kimi Code account with a compatible subscription quota response.
- `KIMI_API_KEY` containing a Kimi Code key, or an existing Kimi Code CLI OAuth login.
- The correct region: `global` for the international endpoint, or the mainland default.

The variable accepted by AI Status is **`KIMI_API_KEY`**, even if another client calls its coding key something else. An account can also use `options.api_key_env` to name a credential-source variable.

## Connect your coding subscription

1. Follow the official [Kimi Code getting-started guide](https://www.kimi.com/code/docs/en/kimi-code-cli/guides/getting-started.html). Start `kimi`, enter `/login`, and choose Kimi Code OAuth for your membership account.
2. AI Status can read `access_token` from `~/.kimi-code/credentials/kimi-code.json`. Alternatively, create a coding key in the [Kimi Code Console](https://www.kimi.com/code/console) and supply it as `KIMI_API_KEY`. Kimi explains the distinction from the general platform in its [membership guide](https://www.kimi.com/en/help/kimi-code/membership-guide).
3. Set `options.region: "global"` for international accounts. A default connection can discover `~/.kimi-code/region`; explicit accounts need their own region setting. Requests use `/coding/v1/usages` on `api.kimi.ai` internationally or `api.kimi.com` otherwise.
4. Enable **Kimi** in AI Status. Linux users use Quickshell **Settings** or `ai-status config` for Waybar. Windows users open tray **Settings** and **Save**; macOS users use menu bar **Settings** and **Save**. Choose **Refresh**; Waybar also refreshes with a left-click or `ai-status refresh`.

## Personal and work connections

Save this as `kimi-work.json`:

```json
{
  "id": "kimi-work",
  "provider": "kimi",
  "label": "Work coding plan",
  "env": {
    "KIMI_API_KEY": {"from_file": "~/.config/credentials/kimi-work-code-key"}
  },
  "options": {"region": "global"}
}
```

Import with `ai-status accounts add --file kimi-work.json`. For another membership, use another ID, label, and credential reference. An OAuth connection can instead set `auth_file` to its own CLI credential file. Explicit accounts do not fall back to your default CLI login. On Windows run `.\ai-status-cli.exe` from the AI Status app folder, or use its full path, and replace file paths with Windows paths. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## What it tracks

Supported responses yield a weekly subscription percentage or a combined monthly percentage, plus a five-hour rolling window when recognized. Percentages represent usage consumed; resets come from the service. Membership level appears when reported. Window availability depends on the response shape, and the integration does not promise every quota or Extra Usage wallet shown by newer Kimi clients.

AI Status does not refresh CLI OAuth tokens. Renew them through Kimi's own login. Missing or unrecognized quota data stays unavailable, rather than showing a guessed percentage or a Moonshot balance.

## Troubleshooting

| Symptom | What to check |
|---|---|
| 401 / expired credential | Re-run `/login` in Kimi Code or replace the coding key reference. |
| Key works for model calls but quota fails | Check it is a Kimi Code key, not a Moonshot platform key. |
| 403 or wrong regional account | Match `region` to the membership and credential. |
| Unrecognized rolling window / no metrics | The service response may have changed; compare the provider's own usage display and update AI Status. |
| 429 / cached quota | Wait for the retry cooldown; Refresh cannot bypass it. |
