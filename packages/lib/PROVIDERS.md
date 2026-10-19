# Providers & Authentication Guide

For Windows credential locations and native CLI compatibility, see the
[Windows guide](WINDOWS.md#authentication-and-provider-compatibility).

**AI Status never ships or hardcodes API keys.** Collectors read existing local authentication files or explicitly configured credential sources. External CLI credentials are read only; refresh expired sessions in the client that owns them. New providers require explicit enabling.

## Provider Overview

| Provider ID | Provider | Usage | Authentication |
| --- | --- | --- | --- |
| `claude` | Claude | Session (5h) and weekly usage, per-model limits and reported Cloud credit balance | Claude Code OAuth (OpenCode fallback) |
| `codex` | Codex | 5-hour and weekly limits (a single monthly window on free plans), usage-credit balance and banked resets | ~/.codex/auth.json |
| `opencode` | OpenCode | Rolling, weekly, and monthly usage | OPENCODE_GO_API_KEY or OpenCode auth |
| `antigravity` | Antigravity | Weekly and 5-hour limits per model (Gemini and Claude/GPT) | agy CLI session |
| `copilot` | Copilot | Chat and completions usage | GITHUB_COPILOT_TOKEN, gh auth token, or OpenCode |
| `zai` | Z.AI | Rolling, weekly, and monthly usage | ZAI_API_KEY or OpenCode |
| `kiro` | Kiro | Usage percentage and reset timer | kiro-cli session |
| `commandcode` | Command Code | 5-hour and weekly spend limits; monthly spend and available credits | ~/.commandcode/auth.json (cmd login) |
| `anthropic-api` | Anthropic API | Monthly organization API spend | ANTHROPIC_ADMIN_KEY (organization Admin key) |
| `openai-api` | OpenAI API | Monthly organization API spend | OPENAI_ADMIN_KEY (organization Admin key) |
| `google-cloud` | Google Cloud | Project quotas; optional billing-export monthly cost | gcloud or GOOGLE_CLOUD_ACCESS_TOKEN; project_id option |
| `openrouter` | OpenRouter | Key usage and limits; account spend / total credits and remaining balance | OPENROUTER_API_KEY; optional OPENROUTER_MANAGEMENT_KEY |
| `deepseek` | DeepSeek | Available prepaid balance | DEEPSEEK_API_KEY |
| `deepinfra` | DeepInfra | Prepaid balance and current-month spend | DEEPINFRA_API_KEY |
| `kimi` | Kimi | Coding subscription quota and rolling limits | KIMI_API_KEY or Kimi CLI login |
| `minimax` | MiniMax | Token Plan quota windows | MINIMAX_API_KEY (Token Plan key) |
| `kilo` | Kilo | Personal or organization credit balance | KILO_API_KEY; optional organization_id |
| `lyceum` | Lyceum | Available USD balance and reported spend | LYCEUM_API_KEY |
| `novita` | Novita | Available prepaid balance | NOVITA_API_KEY |
| `moonshot` | Moonshot | Available USD or CNY balance | MOONSHOT_API_KEY; region option |
| `grok` | Grok API (xAI) | Team prepaid balance | XAI_MANAGEMENT_KEY; team_id for organization-scoped keys |
| `supergrok` | SuperGrok | Subscription credits and product usage | Grok Build login or SUPERGROK_ACCESS_TOKEN |
| `grok-bot` | Grok Bot | Weekly included usage | Grok Bot desktop login or GROK_BOT_ACCESS_TOKEN |
| `cursor` | Cursor | Included usage pools and on-demand spend | Cursor IDE/agent login or CURSOR_ACCESS_TOKEN |
| `nous` | Nous Research | Subscription and top-up credits | NOUS_ACCESS_TOKEN or existing OAuth credentials |
| `ollama` | Ollama Cloud | Cloud session/weekly or monthly quota | OLLAMA_API_KEY (cloud key) |
| `orcarouter` | OrcaRouter | Credit limit, spend and remaining balance | ORCAROUTER_API_KEY |
| `modelstudio` | Alibaba Model Studio | Token Plan rolling and weekly quota | bl auth login --console |
| `devin` | Devin | Daily and weekly CLI quota; optional overage balance | Official Devin CLI credentials |

## Per-Provider Details

### Antigravity (Gemini + Claude/GPT)

Antigravity provides usage data for both Gemini models and Claude/GPT models through its `agy` CLI. The [query.py](src/providers/antigravity/query.py) uses a Unix PTY or Windows ConPTY to interact with the CLI, send `/usage`, and capture the quota output.

| Detail | |
|---|---|
| **Auth** | Must be logged into the `agy` CLI (`agy` launches a browser-based login on first run) |
| **Metrics** | Weekly limit and five-hour rolling limit for each model group |
| **Note** | Gemini data may not include reset timers for all periods -- this is a limitation of the API |

### Claude

Reads the Claude Code OAuth credential store to query Anthropic's usage endpoint, falling back to the OpenCode auth store when Claude Code is not installed or its token has expired.

| Detail | |
|---|---|
| **Auth** | Claude Code login (`~/.claude/.credentials.json`), or OpenCode authenticated with Claude as fallback. Other signed-in config folders become their own connections automatically (see [Multiple accounts](#multiple-accounts-and-connections)) |
| **Endpoint** | `https://api.anthropic.com/api/oauth/usage?cedar_ember=1` |
| **Metrics** | Session (5-hour rolling) and weekly usage with reset timers, including per-model weekly limits; reported Cloud credit balance and expiration; shows the subscription plan (Pro/Max/Team) when available |

**Cloud credits** shows the remaining USD amount and expiration reported in the
same usage response's `iguana_necktie` block. The dollar fields are already USD,
including fractional amounts and a zero balance. The source determines
availability; AI Status does not assume a grant from the plan name. Missing or
malformed credit data leaves ordinary quota windows available. Cloud credits use
the existing amount row, scoped to each configured account. Click the row in
Quickshell, Windows or native macOS to open a detail page with local expiration,
time remaining and timezone; Waybar and SwiftBar retain tooltip/menu details.
Exhausted, expired and unavailable states are distinct;
known expiration is checked while displaying cached data, including offline.
These monetary credits are separate from subscription **Extra usage**, Console
API credits and saved **Reset credits**. `resets_at` in the Cloud block means
expiration, not the next quota reset. See the
[source validation and API-credit investigation](../../docs/development/claude-credits.md)
for upstream evidence and the [manual PR check](../../docs/development/claude-credits.md#manual-check-for-the-pr-tester).
Automated fixtures cover the response contract; an eligible-account tester will
confirm the live balance and expiration through the PR.

Eligible Claude accounts also show **Reset credits** in the desktop panels and Waybar tooltip: available campaign resets, their labels, and expiration dates. Only unspent grants marked usable and not paused by the API are counted. The opt-in inventory requires a recognized Claude CLI user agent; the query uses published version `2.1.281`. If the service changes that requirement or reports no eligible grants, the credit section is hidden while usage remains available.

Only the service's `next_grant_id` can be applied. AI Status verifies the OAuth profile's organization, current grant eligibility and any cooldown before sending the confirmed reset to `/api/organizations/{organization.uuid}/reset_rate_limits`.

### Codex

Uses the Codex access token and account ID from `~/.codex/auth.json` to call OpenAI's usage API.

| Detail | |
|---|---|
| **Auth** | `~/.codex/auth.json` with valid `access_token` and `account_id`. Other signed-in config folders become their own connections automatically (see [Multiple accounts](#multiple-accounts-and-connections)) |
| **Endpoint** | `https://chatgpt.com/backend-api/wham/usage` |
| **Metrics** | Plan type; a 5-hour and a weekly usage window on paid plans (a single monthly window on free), each with a reset timer; usage-credit balance; available banked resets |

**Usage credits** shows the balance reported in the usage API's `credits` block,
including promotional or purchased credits included in that balance. It is shown
in credits, separately from percentage-based plan limits and **Reset credits**,
which restore rate-limit windows. A zero or negative balance is preserved;
unlimited accounts show **Unlimited**. If the API reports available credits but
omits the amount, the panel shows **Available** with **Balance not reported**.
No balance, grant expiration, or dollar conversion is inferred from reset grants.

Codex also shows banked **Reset credits** when the usage response reports an available count. Only then does the query make an optional GET to `https://chatgpt.com/backend-api/wham/rate-limit-reset-credits` for titles and expirations. If that request fails, usage and the original count remain visible with **Expiration not reported**. Redeemed credits are excluded from the detail list. Counts come from the usage response, even if the detail endpoint reports a different count.

Applying requires a ChatGPT `account_id` and the selected credit's ID. AI Status rechecks that credit is available for Codex rate limits before sending one confirmed request to `/backend-api/wham/rate-limit-reset-credits/consume`.

**Apply** is available in a narrow third column in the Quickshell, Windows and macOS reset tables for eligible credits from fresh account data. It replaces the selected row with confirmation of the account, reset type and consumption of **one reset credit**. Hold the confirmation button for **3 continuous seconds**; its background fills as you hold. Releasing early, leaving the button, losing focus or changing account details resets the progress without sending a reset. Cancel, Back or Escape dismisses the confirmation. Details without a usable credit ID or verifiable account remain read-only, as does the Waybar tooltip. Raw redemption IDs are excluded from parsed snapshots and caches; rows use opaque handles instead. Expired credits are excluded, and cached provider data remains labeled.

After a reset response, AI Status refreshes the account's usage and credit inventory. A request with an uncertain result is never retried automatically. Refresh and check the account before confirming another reset; the same confirmed observation cannot be submitted twice, including from another panel or after restarting the app.

### Copilot

Uses GITHUB_COPILOT_TOKEN, the token returned by the authenticated GitHub CLI (`gh auth token`), or an existing OpenCode Copilot session.

| Detail | |
|---|---|
| **Auth** | `gh auth login`, `GITHUB_COPILOT_TOKEN`, or OpenCode Copilot login |
| **Metrics** | Chat and completions usage with remaining counts |

### Kiro

Reads usage through the authenticated native Kiro CLI; explicit connections can query GetUsageLimits using their own session.

| Detail | |
|---|---|
| **Auth** | Native `kiro-cli` login, or a per-account token/authentication file |
| **Metrics** | Usage percentage and reset timer |

### OpenCode (Go)

Queries the read-only `https://opencode.ai/zen/go/v1/usage` endpoint directly. The parser retains compatibility with cached legacy dashboard responses.

| Detail | |
|---|---|
| **Auth** | `OPENCODE_GO_API_KEY` or key from `~/.local/share/opencode/auth.json`; no workspace cookie required |
| **Metrics** | Rolling, weekly, and monthly usage percentages with reset timers |

#### Setup

Connect OpenCode Go in OpenCode, or provide `OPENCODE_GO_API_KEY` to the AI Status process. The old `opencode-go.json` workspace cookie is no longer used or required.

### Z.AI

Reads a bearer token from Z.AI's local configuration to query its API.

| Detail | |
|---|---|
| **Auth** | Bearer token from `~/.config/z.ai/` |
| **Metrics** | Rolling, weekly, and monthly usage with reset timers |

## Provider Architecture

Each provider lives in `src/providers/<name>/` with two files:

| File | Purpose |
|---|---|
| `query.sh` | Fetches raw data -- makes API calls, runs CLI commands, or scrapes output |
| `parse.py` | Parses the raw output into a standardized JSON structure via a `parse(raw_output)` function |

To add a new provider, create a new directory under `src/providers/` with these two files and register it via `ai-status config`.

## Troubleshooting

If a provider shows **"API unreachable"**, **0%**, or nothing at all:

1. **Check the auth file.** Confirm the key file from the table above exists and holds a valid, non-expired token. The most common cause is an expired login — re-authenticate with that provider's own CLI or app.
2. **Run the query by hand.** Each provider has a `query.sh` you can run directly to see the raw API response:
   ```bash
   bash ~/.local/share/ai-status/packages/lib/src/providers/<name>/query.sh
   ```
3. **Read the daemon log.** Errors are written to `/tmp/ai-status-error.log`.
4. **Refresh without restarting.** After fixing credentials, left-click the module (or run `ai-status refresh`) — no need to restart Waybar.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development details.

## Multiple accounts and connections

There is no configured account-count limit. Each connection has a stable ID and label, its own credential references and provider options.

Claude Code, Codex and Command Code accounts don't need to be added. Every signed-in config folder of those CLIs shows up as a `discovered` connection, besides the one each CLI reads by default:

| Provider | Folders | Label |
|---|---|---|
| Claude | `~/.claude-<name>`, `~/.config/seats/claude/<name>`; `~/.claude` when `CLAUDE_CONFIG_DIR` points elsewhere | Account email |
| Codex | `~/.codex-<name>`, `~/.config/seats/codex/<name>`; `~/.codex` when `CODEX_HOME` points elsewhere | Account email |
| Command Code | `~/.commandcode-<name>`, `~/.config/seats/commandcode/<name>` | Folder name |

`~/.config/seats` is where [seats](https://github.com/gelzinn/seats) keeps one folder per account (`$SEATS_HOME` when set); seats itself is not needed. A connection's ID comes from the account, so renaming the folder keeps it. A saved account pointing at the same credential file takes its place; turning a discovered one off in Settings saves it as a disabled account.

Accounts work independently of the default provider session; adding an OpenRouter account does not require enabling the default OpenRouter entry. Every desktop can select, enable, disable and reorder saved connections. The CLI manages their credential sources:

```bash
ai-status accounts add openrouter --id personal --label Personal --env OPENROUTER_API_KEY=OPENROUTER_PERSONAL_KEY
ai-status accounts add openrouter --id work --label Work --env OPENROUTER_API_KEY=OPENROUTER_WORK_KEY
ai-status accounts list
ai-status accounts edit work --disabled
ai-status accounts remove work
```

Provide the source variables to the actual AI Status process (a shell export affects processes launched from that shell). For desktop launches, a credential file reference avoids depending on inherited environment variables. Add an account with `ai-status accounts add --file connection.json`, or use `--file -` to read JSON from stdin:

```json
{
  "id": "openai-work",
  "provider": "openai-api",
  "label": "Work organization",
  "env": {
    "OPENAI_ADMIN_KEY": {"from_file": "~/.config/my-credentials/openai-admin-key"}
  },
  "options": {
    "organization_id": "org_example",
    "project_ids": ["proj_example"],
    "monthly_budget": 100,
    "budget_currency": "USD"
  }
}
```

For CLI sessions, point to an existing account-specific credential file:

```bash
ai-status accounts add codex --id work-codex --label Work --auth-file /path/to/work-codex/auth.json
ai-status accounts add claude --id personal-claude --label Personal --auth-file /path/to/personal-claude/.credentials.json
```

Connections are stored in `~/.config/ai-status/accounts.json` on Linux and `%APPDATA%\ai-status\accounts.json` on Windows. Unix configuration files are written with mode `0600`. Environment references and filenames are saved; secret values are resolved in memory. `accounts list --json` omits option values. Existing `providers.json` and `selected.json` preferences remain supported. Removing a connection retains its external credential files.

Caches are private to the user and bound to both connection identity and credential/context fingerprints. Changing an account's key, auth file or project cannot reuse another account's cached usage. Explicit connections require their own credential source and never silently fall back to the default login. Expired OAuth sessions must be refreshed in their owning CLI.

## API spend, balance and quota

Spend, available credit and subscription quota are separate metrics. A balance has no invented percentage. An amount only gains a percentage if the API reports its applicable limit or you set a positive `monthly_budget`; a configured budget is a local monitoring preference, not a provider-enforced limit. Multiple currencies remain separate.

- **OpenAI API:** `OPENAI_ADMIN_KEY`, optionally `organization_id`/`OPENAI_ORG_ID`, `project_ids`, `monthly_budget`, `budget_currency`. Queries the paginated [organization costs API](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs) for the current UTC month; a project inference key or Codex OAuth login cannot query it.
- **Anthropic API:** `ANTHROPIC_ADMIN_KEY` for a Console Admin key or an unscoped personal/service account key with admin access; alternatively `ANTHROPIC_ADMIN_TOKEN` for `org:admin` OAuth. Workspace inference keys cannot read costs. Optional `workspace_id` scopes the paginated report, `monthly_budget`/`budget_currency` supplies a monitoring budget. [Cost report](https://platform.claude.com/docs/en/api/http/beta/organization/cost_report/retrieve) amounts are decimal cents and are converted to currency units. This collector reports costs only: it does not expose a Console API balance, attribute monthly promotional grants or report their expiry. A configured budget minus spend is not a remaining credit balance. Claude subscriptions, Cloud credits, Bedrock and Vertex invoices are separate. See the [monthly API-credit investigation](../../docs/development/claude-credits.md#monthly-api-credits-investigation-result).
- **OpenRouter:** `OPENROUTER_API_KEY` reads key usage and also attempts the [account credits API](https://openrouter.ai/docs/api/api-reference/credits/get-remaining-credits) with that same credential. **Credit balance** shows the remaining account balance in the top bar and panel. For example, $36.10 spent from $40.00 total credits leaves **$3.90** as the main value; the consumption bar and `$36.10 of $40.00 used (90%)` detail retain the spending context. Switching usage display to remaining changes the progress bar while keeping the actual balance as the main value. Monthly key spend and key caps remain separate from account totals; they are never subtracted from account credits to invent a balance. No additional credential is required by AI Status to try this lookup, and the legacy `include_credits` option does not gate it.

  OpenRouter's documented permissions still require a management key for this endpoint. If the same-key lookup returns 401/403, valid key usage stays visible with **Account balance unavailable for this key**. An already configured `OPENROUTER_MANAGEMENT_KEY` remains an optional override; a management key alone reads credits directly. Failures of an explicit management credential, rate limits and network errors follow the existing cache and cooldown handling.

  Each account can reuse its own API key through the existing credential-source options:

  ```bash
  ai-status accounts add openrouter --id personal-credits --label Personal --env OPENROUTER_API_KEY=OPENROUTER_PERSONAL_KEY
  ai-status accounts add openrouter --id work-credits --label Work --env OPENROUTER_API_KEY=OPENROUTER_WORK_KEY
  ```
- **Google Cloud:** `GOOGLE_CLOUD_ACCESS_TOKEN`, or `gcloud auth print-access-token` with optional `gcloud_account`. Set `project_id` (or `GOOGLE_CLOUD_PROJECT`). Cloud Monitoring quota series require Monitoring read permissions. `service` and `quota_metric` filter series; allocation usage is paired with the matching limit, and rate-window quotas only use compatible labels/windows.

Google Cloud billing is optional: set `billing_table` to an existing `project.dataset.table` [Cloud Billing export](https://cloud.google.com/billing/docs/how-to/export-data-bigquery). AI Status queries net current-month cost, including credits, scoped to `project_id`. `billing_project_id` controls the BigQuery job project, `billing_location` its location, `service_id` narrows services, and `billing_all_projects: true` explicitly broadens the spend scope. BigQuery read/query IAM permissions are required. Queries can incur BigQuery charges; `maximum_bytes_billed` defaults to 1 GB and query caching is enabled. Export delays apply, and missing quota/billing data stays unavailable rather than becoming a zero balance.

For prepaid providers, the table above lists the key environment variable. Additional options: `region: "cn"` for MiniMax/Moonshot, `region: "global"` for Kimi's international endpoint; `organization_id` for Kilo teams; `team_id` for organization-scoped xAI management keys; `region` and `site` for Model Studio. Native login providers accept `auth_file`, while `CURSOR_ACCESS_TOKEN`, `SUPERGROK_ACCESS_TOKEN`, `GROK_BOT_ACCESS_TOKEN`, `NOUS_ACCESS_TOKEN` and `DEVIN_API_KEY` provide explicit overrides. For Nous, set `NOUS_ACCESS_TOKEN` or explicitly configure an `auth_file` containing `access_token` (at the top level or under `nous`) from a separately authorized OAuth session; AI Status does not start a Nous device-login flow. Grok Bot's Linux/macOS credential stores and Windows credential overrides are supported; native session compatibility varies with the desktop app's storage format.

## Request limits and cached data

Automatic refresh defaults to five minutes. Settings → General offers a slider from 5 to 60 minutes in steps of 5; values outside that range or step are rejected by the backend, and malformed saved preferences fall back to 5 minutes. Saving only the interval adjusts the schedule without forcing a request. The next ordinary collection waits for the saved interval after the previous collection finishes; a reported exhausted-window reset can still schedule an earlier recovery check. Fresh successful results are reused for at least 60 seconds, including manual refresh. Collection uses at most eight workers, serializes calls to the same upstream service and spaces connection starts by at least one second, so adding accounts does not create an unbounded request burst. HTTP 429 starts a persistent cooldown for that connection and credential context: `Retry-After` is respected, with a five-minute fallback when the header is absent. Manual refresh, interval changes and application restarts do not bypass the cooldown. Request timeouts remain bounded independently of the refresh interval. The last valid snapshot stays visible with a cache/error indicator; when no cache exists, the connection reports its wait time.

This reduces request pressure but cannot guarantee that an upstream API never rate-limits the application. Provider policies, other tools using the same key, and undocumented endpoint changes still apply. Authenticated live checks require your own accounts; mocked contract tests do not establish entitlement or live availability.

Default Antigravity CLI sessions can have an OS-keyring identity that cannot be verified from credential files. These sessions query fresh usage and do not reuse cached snapshots from a previous login. An explicit token or account authentication file enables identity-bound caching.
