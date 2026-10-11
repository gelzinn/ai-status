AI Status shows reported OpenAI API costs for the current UTC month, with project filtering and an optional monitoring budget. This is an organization billing connection. For ChatGPT plan and Codex usage windows, use the separate [Codex integration](/providers/codex).

## Requirements

- An OpenAI API organization with an organization Admin API key that can read costs.
- `OPENAI_ADMIN_KEY` available to AI Status, directly or through a credential reference.
- Optionally, organization and project IDs to identify your billing scope.

A regular `OPENAI_API_KEY`, project inference key, or Codex OAuth login cannot authenticate this collector. See OpenAI's [Administration overview](https://developers.openai.com/api/reference/administration/overview).

## Set up organization costs

1. Sign in to [OpenAI Platform](https://platform.openai.com/) and select the organization to monitor.
2. Open [organization Admin keys](https://platform.openai.com/settings/organization/admin-keys) and create an Admin key using an authorized organization account. Provide it as `OPENAI_ADMIN_KEY`.
3. Set `organization_id` for an explicit organization header; `OPENAI_ORG_ID` is the fallback. Use `project_ids` for a list, or `project_id` for one project. Without a project filter, the request covers organization costs. Use `api_key_ids` to filter specific keys, as documented by the [Costs API](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs).
4. Enable **OpenAI API** in Settings. Linux users use Quickshell **Settings** or `ai-status config` for Waybar. Windows users open tray **Settings** and **Save**; macOS users open menu bar **Settings** and **Save**. Choose **Refresh**, or run `ai-status refresh` (`.\ai-status-cli.exe refresh` on Windows).

## Monitor separate projects or organizations

Save this as `openai-work.json`:

```json
{
  "id": "openai-work",
  "provider": "openai-api",
  "label": "Work API projects",
  "env": {
    "OPENAI_ADMIN_KEY": {"from_file": "~/.config/credentials/openai-work-admin"}
  },
  "options": {
    "organization_id": "your-organization-id",
    "project_ids": ["your-project-id"],
    "monthly_budget": 200,
    "budget_currency": "USD"
  }
}
```

Run `ai-status accounts add --file openai-work.json`. On Windows substitute `.\ai-status-cli.exe` and a Windows path. Create another definition with a different ID, label, and credential source for another organization. Connections filtered to separate projects can share an authorized organization credential. Credentials are resolved in memory; saved definitions contain references. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On Windows, run `.\ai-status-cli.exe` from the AI Status application folder or use its full path; it may not be on your terminal PATH.

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## What it tracks

The collector reads every page of `/v1/organization/costs` and sums daily buckets from the first day of the current UTC month. Currencies remain separate. The countdown ends at the next UTC month, not your ChatGPT subscription renewal.

Costs appear as amounts. A positive `monthly_budget` creates a percentage only for `budget_currency` (USD by default). This is a local preference, not a provider-enforced cap. AI Status does not infer prepaid balance, token limits, request capacity, or per-model usage from costs. Incomplete pagination or malformed amounts remain unavailable rather than producing a misleading total.

## Troubleshooting

| Symptom | What to check |
|---|---|
| 401 or 403 / cost access denied | Confirm `OPENAI_ADMIN_KEY` is an organization Admin key with cost-reading access. |
| Wrong organization's amount | Check the credential's organization, `organization_id`, and `OPENAI_ORG_ID`. |
| Project amount missing | Verify project IDs and period; a valid empty report is zero reported spend. |
| No progress bar | Add a positive budget in the metric's currency. |
| 429 or cached result | Let the retry cooldown finish; repeated Refresh clicks cannot bypass it. |
