AI Status reads SuperGrok subscription usage through an authenticated Grok Build session. It shows included credit consumption, the current usage period, and product breakdowns when returned. A reported prepaid API balance appears as a separate amount; it does not define your subscription quota.

## Requirements

- A Grok account whose authenticated billing response exposes subscription usage.
- A compatible Grok Build login stored locally, or its session credential supplied as `SUPERGROK_ACCESS_TOKEN`.
- AI Status on Linux, Windows, or macOS.

The SuperGrok connection follows your consumer account's subscription scope. To monitor a team's API prepaid credits with a management credential, use [Grok API](/providers/grok). A normal inference key is not the subscription-session credential described here.

## Connect your Grok account

1. Install the official Grok Build client using its [project documentation](https://github.com/xai-org/grok-build). Follow the [authentication guide](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/02-authentication.md) and run `grok login` to complete browser sign-in. Device authentication is also documented for environments without a local browser.
2. AI Status reads compatible saved credential entries from `~/.grok/auth.json`. `GROK_HOME` changes that default directory. A named account can instead provide `auth_file` pointing at its authorized Grok Build file.
3. For an explicit session, supply `SUPERGROK_ACCESS_TOKEN` or set `options.api_key_env` to a variable holding that session credential. The collector sends it to Grok Build's billing endpoint with its client authentication header. AI Status does not start a browser flow or refresh that session.
4. Enable **SuperGrok** in Settings. On Linux use Quickshell **Settings** or `ai-status config` for Waybar. On Windows open tray **Settings** and **Save**; on macOS open menu bar **Settings** and **Save**. Choose **Refresh**. Waybar also refreshes with a left-click; CLI users run `ai-status refresh`.

## Monitor separate subscriptions

Point each connection at an independently authorized credential file:

```bash
ai-status accounts add supergrok --id supergrok-personal --label Personal --auth-file /path/to/personal-grok/auth.json
ai-status accounts add supergrok --id supergrok-work --label Work --auth-file /path/to/work-grok/auth.json
```

Use different IDs and files for different accounts. Explicit connections do not fall back to the default Grok login. You can also map `SUPERGROK_ACCESS_TOKEN` from an account-specific environment variable or private file in a JSON connection definition. On Windows run `.\ai-status-cli.exe` from the app folder or by full path, with Windows paths. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## Read subscription usage

Current responses can supply a weekly or monthly included-usage percentage, with reset time and per-product percentages. Older compatible responses can supply included-credit amounts and a monthly limit. AI Status uses whichever supported representation the billing service returns and displays the subscription label when present.

The [Grok subscription FAQ](https://docs.x.ai/grok/faq) describes the provider's shared usage pool and its own Settings → Usage display. Do not add product percentages to the overall pool or treat a reset as an invoice prediction. Different plans and billing-response versions can expose different metrics. AI Status does not retrieve a full message history or estimate compute consumption locally.

## Troubleshooting

| Symptom | What to check |
|---|---|
| 401 / expired session | Run `grok login` again in the owning Grok Build configuration. |
| 403 / no subscription data | Confirm this account has access to the billing response and the intended subscription. |
| Plan missing or wrong account | Match the local login to the account used to purchase the subscription. |
| API key works but quota fails | Use the compatible subscription login, not a model-call key. |
| Product rows missing | Only product percentages returned by billing are shown. |
| 429 / cached usage | Wait for the retry cooldown; repeated Refresh does not bypass it. |
