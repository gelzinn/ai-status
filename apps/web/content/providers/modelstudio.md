AI Status reads Alibaba Cloud Model Studio Token Plan rolling and weekly usage through a Bailian CLI console session. It keeps the plan's consumption and reset times visible alongside other coding subscriptions. The credential required for this usage query is a console access token, even if you use a separate Token Plan key for model calls.

## Requirements

- An Alibaba Cloud account with a compatible Model Studio Token Plan.
- The official Bailian CLI (`bl`) signed in using **console login**.
- Alternatively, `MODELSTUDIO_ACCESS_TOKEN` containing an authorized console access token.

A standard `DASHSCOPE_API_KEY` or Token Plan inference key alone is not read by this collector. Alibaba explains the differences in [Installation and authentication](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/cli/installation).

## Connect console usage

1. Install the official Bailian CLI using the provider's [installation guide](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/cli/installation). It includes Linux, macOS, and Windows instructions.
2. Run `bl auth login --console` and complete the browser authorization for the intended Alibaba Cloud account. `bl auth status --output json` checks the login with masked credential details. Logging in only with an API key enables model calls but does not provide the same console capabilities.
3. AI Status reads `access_token` or `accessToken` from `~/.bailian/config.json`. An account can set `auth_file` to its own compatible config file, or use `MODELSTUDIO_ACCESS_TOKEN` / `options.access_token_env`.
4. Verify `region` and `site`. They default to the file's `console_region` and `console_site`, then `cn-beijing` and `domestic`. International accounts need `site: "international"`; Singapore uses `region: "ap-southeast-1"`. These options determine the console gateway used for the query.
5. Enable **Alibaba Model Studio** in AI Status. On Linux use Quickshell **Settings** or `ai-status config` for Waybar. On Windows open tray **Settings** and **Save**; on macOS open menu bar **Settings** and **Save**. Choose **Refresh**, or left-click the Waybar module.

## Separate console accounts

Save this as `modelstudio-work.json`:

```json
{
  "id": "modelstudio-work",
  "provider": "modelstudio",
  "label": "Work Token Plan",
  "auth_file": "/path/to/work-bailian/config.json",
  "options": {
    "site": "international",
    "region": "ap-southeast-1"
  }
}
```

Import with `ai-status accounts add --file modelstudio-work.json`. Use another ID and authorized config file for another account. Explicit connections do not borrow the default console session. On Windows run `.\ai-status-cli.exe` from the AI Status app folder or by full path, and substitute a Windows credential path. For desktop startup, files avoid dependence on terminal-only exports. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## What it tracks

The usage response's five-hour and one-week ratios become percentages used, with countdowns derived from the reported reset timestamps. Only present windows appear. They are Token Plan allowances, not Alibaba Cloud's entire billing balance or the spend of every workspace.

AI Status does not collect pay-as-you-go costs, manage plan seats, or refresh the console token. Region/site mismatches and console-session expiry can prevent usage even when your model-call key still works. Console gateway formats may change independently of the inference API.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Session expired / request unsuccessful | Run `bl auth login --console` again for the intended account. |
| Model calls work, usage fails | An inference key alone does not authorize this console query. |
| 401 or 403 | Check console authorization and account access to Token Plan usage. |
| Wrong gateway or no quota | Match `site` and `region` to the signed-in console account. |
| Missing five-hour or weekly row | Only compatible fields returned by the service are shown. |
| 429 / cached result | Wait for the connection's retry cooldown before refreshing. |
