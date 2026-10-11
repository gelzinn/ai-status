AI Status reads your Claude Console organization's reported API costs for the current UTC month. It keeps workspace spend visible while you work. Claude Pro, Max, and Team subscription quotas use the separate [Claude integration](/providers/claude).

## Requirements

- An organization in [Claude Console](https://platform.claude.com/) with an authorized Admin API credential.
- `ANTHROPIC_ADMIN_KEY` for a Console Admin key, or an unscoped personal/service account key with admin access. Alternatively, `ANTHROPIC_ADMIN_TOKEN` for OAuth with `org:admin` scope.
- AI Status on Linux, Windows, or macOS.

Workspace inference keys cannot read costs. See Anthropic's [Admin API credential guide](https://platform.claude.com/docs/en/manage-claude/admin-api).

## Set up cost monitoring

1. Select your organization in Claude Console. An organization admin can create an Admin API key in Console settings; follow [Create an Admin API key](https://platform.claude.com/docs/en/manage-claude/admin-api). Ordinary inference keys and Enterprise Analytics keys are different credentials.
2. Provide the credential under `ANTHROPIC_ADMIN_KEY`, or reference a private file as below. For OAuth, supply `ANTHROPIC_ADMIN_TOKEN`; OAuth takes precedence when both exist. AI Status does not refresh OAuth sessions.
3. Choose scope. Without `workspace_id`, the collector sums the organization. Setting `workspace_id` groups the report by workspace and filters it locally after reading every page. Optional `monthly_budget` and `budget_currency` add a monitoring budget.
4. Enable **Anthropic API** in Settings. On Linux, use Quickshell **Settings** or `ai-status config` for Waybar. On Windows, open tray **Settings** and **Save**; on macOS use menu bar **Settings** and **Save**. Choose **Refresh**. Waybar also refreshes with a left-click or `ai-status refresh`.

## Separate workspaces or organizations

Save `anthropic-work.json`, replacing the workspace ID and file path with your references:

```json
{
  "id": "anthropic-work",
  "provider": "anthropic-api",
  "label": "Work workspace",
  "env": {
    "ANTHROPIC_ADMIN_KEY": {"from_file": "~/.config/credentials/anthropic-work-admin"}
  },
  "options": {
    "workspace_id": "your-workspace-id",
    "monthly_budget": 150,
    "budget_currency": "USD"
  }
}
```

Import with `ai-status accounts add --file anthropic-work.json`. Windows uses `.\ai-status-cli.exe` and a Windows file path. Add another ID and credential source for another organization. File references work for desktop launches without shell environment variables. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On Windows, run `.\ai-status-cli.exe` from the AI Status application folder or use its full path; it may not be on your terminal PATH.

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## What the numbers mean

AI Status sums daily costs from month start to the request time, converting decimal cents into currency units. Currencies stay separate. A bar appears only with a positive configured budget; it does not impose a spending limit. The countdown marks the next UTC month.

The [Usage and Cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api) covers Console costs and excludes Priority Tier charges. Bedrock, Vertex AI, Enterprise Analytics, and subscription invoices need their own reporting. An empty valid report means no reported costs, not an available balance.

## Troubleshooting

| Symptom | What to check |
|---|---|
| 401 or 403 / cost access denied | Use an admin-compatible credential for this organization; workspace inference keys cannot read costs. |
| OAuth stopped working | Renew the authorized session in its owning tool and update the token source. |
| Unexpected workspace total | Check `workspace_id`; omitting it includes the organization. |
| Cost differs from an invoice | Compare the UTC period and billing products covered by the official report. |
| 429 or cached values | Wait for the retry cooldown; Refresh and restarts do not bypass it. |
