AI Status reads supported Devin CLI daily and weekly allowances, plus an overage balance when the service supplies one. It helps monitor the coding account used by your local CLI. It does not query Devin Cloud session history, organization ACU analytics, or cloud API billing.

## Requirements

- The official Devin CLI with a compatible authorized session.
- A `credentials.toml` containing the top-level `windsurf_api_key` field read by this integration, or that compatible credential supplied as `DEVIN_API_KEY`.
- AI Status on Linux, Windows, or macOS.

The environment variable's name does not make every Devin API key compatible. AI Status uses the CLI seat-status service, not the public cloud API. Enterprise authentication and billing can have different scopes; see [Devin CLI authentication](https://docs.devin.ai/cli/enterprise/devin-auth).

## Connect the CLI account

1. Install Devin CLI using the official [quickstart](https://docs.devin.ai/cli). Native Windows installation is available alongside Linux and macOS instructions.
2. Start `devin` and sign in with the account you want to monitor. The interactive `/login` command is documented in [Essential commands](https://docs.devin.ai/cli/essential-commands); `devin auth login` is documented for enterprise authentication. Complete your provider's supported login flow rather than creating an unrelated cloud API key.
3. AI Status looks for `devin/credentials.toml` under `XDG_DATA_HOME` on Linux/macOS, defaulting to `~/.local/share/devin/credentials.toml`. Windows uses `%APPDATA%/devin/credentials.toml`. It reads only the top-level `windsurf_api_key` field. A custom `auth_file` can point to another compatible CLI credential file. Explicit overrides use `DEVIN_API_KEY` or `options.api_key_env`.
4. Enable **Devin** in Settings. Linux users use Quickshell **Settings** or `ai-status config` for Waybar. On Windows open tray **Settings** and **Save**; on macOS open menu bar **Settings** and **Save**. Choose **Refresh**. Waybar also refreshes with a left-click or `ai-status refresh`.

## Keep CLI accounts independent

Reference existing, separately authorized credential files:

```bash
ai-status accounts add devin --id devin-personal --label Personal --auth-file /path/to/personal-devin/credentials.toml
ai-status accounts add devin --id devin-work --label Work --auth-file /path/to/work-devin/credentials.toml
```

Alternatively, map `DEVIN_API_KEY` from an account-specific environment variable or private credential file using a JSON connection definition. Explicit accounts need their own source and do not borrow the default CLI session. On Windows run `.\ai-status-cli.exe` from the AI Status application folder or by full path, and use Windows paths. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## What the metrics mean

The service reports daily and weekly percentages remaining. AI Status converts them to percentages **used**, preserving each window's reset timestamp. The optional overage balance is converted from vendor-reported USD micros to dollars and appears as an amount, without an invented spending limit.

These allowances are not an ACU total or a dollar estimate of every Devin task. AI Status cannot assume your organization is entitled to the legacy seat-status response just because the CLI can authenticate. Missing quota fields, incompatible credentials, or changed response formats remain unavailable. Authentication stays with the official CLI; the monitor does not perform login or token renewal.

## Troubleshooting

| Symptom | What to check |
|---|---|
| No compatible credential found | Verify the configured file exists and has top-level `windsurf_api_key`; other CLI auth formats may not be supported. |
| 401 or 403 from seat-status service | Re-authenticate and check credential compatibility and CLI entitlement. |
| Cloud API key works, monitor fails | The monitor expects a compatible CLI seat credential, not a general cloud API key. |
| Daily/weekly rows absent | The account may not expose those plan-status fields; consult its own usage display. |
| Overage differs from enterprise analytics | The displayed balance is the vendor's seat-status USD amount, not organization ACUs. |
| 429 / cached quota | Wait for the retry cooldown before refreshing. |
