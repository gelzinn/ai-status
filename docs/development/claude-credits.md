# Claude credits: source validation and scope

AI Status keeps Claude Cloud credits, Console API credits, subscription quotas,
extra-usage spend and saved quota resets separate. Dollar amounts are not counts
of resets, and a cost report is not a remaining balance.

## Cloud credits

The [Cloud promotion rules](https://support.claude.com/en/articles/17152539-cloud-sessions-bonus-credit-promotion)
describe credits for Claude Code sessions hosted by Anthropic, attached to a
Claude account. They have an expiration and are separate from ordinary plan
limits and purchased usage credits. Promotion amounts, eligibility and deadlines
can change; the collector does not hardcode them or infer eligibility from a
Pro/Max plan label.

The existing Claude OAuth usage request can contain `iguana_necktie`. No extra
request, Console login, browser-cookie discovery, claim or redemption is needed.
The parser follows the shape documented by
[CodexBar](https://github.com/steipete/CodexBar/blob/main/docs/claude.md#cloud-session-credits)
and the pinned [Pane implementation and live-shape fixture](https://github.com/ItsJazii/pane/blob/beb4bbfd4e7c776d970a56d254e8cce4d61154d9/src-tauri/src/providers/claude.rs#L992).
CodexBar also exposes its [Cloud snapshot parser](https://github.com/steipete/CodexBar/blob/main/Sources/CodexBarCore/Providers/Claude/ClaudeCloudCreditsSnapshot.swift)
and [parser fixtures](https://github.com/steipete/CodexBar/blob/main/Tests/CodexBarTests/ClaudeCloudCreditsTests.swift).
These are implementation evidence for a private usage-response field, not a
published Anthropic API contract.

| Source field | Meaning |
| --- | --- |
| `limit_dollars` | Reported Cloud allowance in USD |
| `used_dollars` | Reported Cloud usage in USD |
| `remaining_dollars` | Reported remaining Cloud balance in USD; takes precedence over a derived balance |
| `resets_at` | Expiration of this credit, not a recurring quota reset |
| `locked_reason` | Provider-reported inability to use the credit |
| `utilization` | Usage percentage; does not by itself establish a funded balance |

The dollar fields are already USD. They must not be divided by 100, added to
Codex usage credits or extra-usage spend, or used as a quota-alert window. When
the balance is omitted, it can be derived only from valid reported allowance
and usage amounts. Missing, null or malformed dollar data does not imply that
the account has a full allowance or zero balance; ordinary quota parsing stays
available.

Cloud credits are emitted through the provider's `monetary_credits` collection
with `id`, `title`, `currency`, `balance`, `limit`, `used`, `expires_at` and
`available`. Here `available` records only whether the provider locked the credit;
the presentation's `status` and current `balance` determine its displayed state.
Timestamps are normalized to UTC; the original lock reason is not persisted.
The shared presentation helper prepares an amount row for the existing
Quickshell, Waybar, Windows and macOS views. The row belongs to the same
configured account and cache as its usage response. It retains fractional dollars
and a reported zero; available, exhausted, expired and unavailable states preserve
their different meanings. Known expiry is checked against the current clock when preparing the
view, including while offline. Cached/failed observations and observations older
than ten minutes are unavailable, with their last amount and observation time
identified. A cached positive number after its expiry cannot be presented as
spendable credit.

The [automated credit tests](../../packages/lib/tests/test_cloud_credits.py)
cover the upstream response shape and synthetic edge cases. The implementation
and PR can be reviewed with that coverage; a tester with an eligible account
will perform the live check below. This live check has not yet been performed,
and the fixtures do not establish that every plan, account or authentication
source receives the block.

### Manual check for the PR tester

1. Use the PR's checkout or preview build, sign in to the intended Claude account
   through Claude Code, and enable that connection in AI Status. Follow the
   [Linux](linux.md), [Windows](windows.md) or [macOS](macos.md) development guide
   for the chosen interface. A stable-release installation does not contain an
   unmerged PR's changes.
2. In Claude's own usage view, record this account's Cloud credit balance and
   expiration. Refresh AI Status and compare **Cloud credits** on the same
   account. The value should be USD, with no 100-fold conversion or addition to
   extra usage, API credits or saved reset counts. Account labels and ordinary
   quota windows should stay correct.
3. From the PR checkout, `python3 packages/lib/src/bin/ai-status status` prints
   the normalized provider snapshot as JSON (`python` on Windows). Inspect the
   Claude entry's `monetary_credits` locally. For a bug report, share only that
   credit collection, the interface/OS and whether the refresh succeeded; remove
   unrelated provider data and account identifiers. No credential file or cookie
   is needed in the report.
4. Open the available interfaces and check the credit amount/detail row. If
   multiple Claude connections exist, select each and verify balances remain
   attached to their original account. Cloud credits should also remain
   selectable alongside the quota windows.
5. Disconnect the network after a successful refresh and refresh again. The
   last amount should be identified as an observation while the credit becomes
   **Unavailable**. Restore connectivity, allow any reported cooldown, and
   refresh to recover the current balance. Restart AI Status and confirm the
   account and cached-state behavior persists.
6. Report a missing or mismatched row with the sanitized details from step 3.
   A successful quota refresh without a valid Cloud block should omit the
   credit row. Zero balances, malformed blocks, locks and expiration crossing
   while offline are covered by fixtures; do not consume credits or change the
   machine clock merely to create those cases.

Record which account state and interface were checked. A matching live result
confirms that observed source/account combination; it does not establish access
for every Claude plan or Console organization.

## Monthly API credits: investigation result

Anthropic's [monthly API credit rules](https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-and-team-plans)
place these credits in a linked Claude Console organization. They are shared
across that organization, consumed before purchased credits, renewed with the
billing cycle and unused credits expire. The Console Billing page exposes credit
amounts and expiration dates. This is a separate wallet from Cloud session
credits and subscription extra usage.

The current `anthropic-api` collector reads
`GET https://api.anthropic.com/v1/organizations/cost_report`. The official
[Usage and Cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api)
reports historical usage and costs, with cost amounts expressed as decimal
cents. It does not document a remaining-credit balance, credit grants or their
expiration; Priority Tier costs are excluded. Subtracting reported spend from a
plan's advertised monthly grant would therefore create an unsupported balance,
especially with purchased credits, partial cycles, multiple users or delayed
reporting.

The [Admin API authentication guide](https://platform.claude.com/docs/en/manage-claude/admin-api)
confirms Admin keys in `x-api-key`, OAuth bearer tokens with `org:admin`, and
unscoped personal or service-account keys with the required permissions.
Workspace inference keys cannot read costs. The documented organization-info
endpoint (`/v1/organizations/me`) returns organization identity, not billing
balance. These permissions do not establish access to private Console billing
endpoints.

### Candidate Console source remains unconfirmed

The upstream [codexbar-ios investigation](https://github.com/hemsoft-dev/codexbar-ios/issues/34)
identifies this private candidate:

```text
GET https://platform.claude.com/api/organizations/{organization_id}/prepaid/credits
```

That issue requires validation of authentication and wallet scope; it does not
provide a verified monthly-grant schema or live eligible response. The
[Claude Spend Tracker author's guide](https://marketplace.visualstudio.com/items?itemName=MichalHradil.claude-spend-tracker)
describes Console balance collection with an explicitly supplied or captured
`sessionKey` browser cookie on `platform.claude.com`, but does not publish the
endpoint or response contract. Neither source confirms that the current Claude
Code OAuth credential or an Admin API key can read the candidate.

Do not confuse this candidate with
`https://claude.ai/api/organizations/{organization_id}/prepaid/credits`:
CodexBar documents that different domain as the subscription's purchased Usage
credits balance. A matching email alone cannot establish that both sessions
refer to the same organization or wallet.

Before implementing Console balance collection:

1. Verify a read-only balance request and authentication with an eligible
   organization's owner, admin or billing session. Record the exact domain,
   organization identity, response units and pagination, if any, using a
   redacted response. Do not publish cookies, tokens, personal information or
   purchase/claim identifiers.
2. Confirm whether the response distinguishes the monthly promotional grant
   from purchased credits, provides a remaining amount per grant, and reports
   each grant's actual expiration. Validate the grant/list endpoint separately
   if the balance response is aggregate-only.
3. Bind results to the selected Console organization. Verify explicit credential
   selection, multiple organizations, roles, expiry and 401/403 behavior without
   reading unrelated browser profiles or changing billing state.
4. If only an aggregate balance is authoritative, use **API balance** with a
   visible explanation that monthly-credit attribution and expiration are
   unavailable. Do not infer them from plan name, month boundaries or costs.
5. Verify fractional and zero amounts, missing fields, expired grants, unavailable
   responses, cache age and account isolation before enabling the UI.

Until that evidence exists, AI Status continues to show **reported API costs**;
there is no monthly-API-credit balance integration or invented placeholder
balance. No claim, purchase or redemption action belongs in the collector.
