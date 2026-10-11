AI Status reads MiniMax Token Plan quota windows with your subscription key. It shows consumed rolling and weekly allowances per model returned by the service, with reset countdowns. This connection does not calculate a pay-as-you-go wallet balance or token costs from generated messages.

## Requirements

- A MiniMax subscription whose `/v1/token_plan/remains` response exposes compatible quota fields.
- The **Token Plan Subscription Key** supplied as `MINIMAX_API_KEY`.
- The appropriate international or mainland account region.

MiniMax distinguishes subscription quota from prepaid credits in its [Token Plan documentation](https://platform.minimax.io/docs/guides/pricing-token-plan). A general pay-as-you-go API key is not interchangeable with the subscription key for this integration.

## Set up your subscription key

1. Sign in to [MiniMax Platform](https://platform.minimax.io/) and open your subscription management page. Use the subscription's **Get API Key** or Subscription Key control. The [subscription landing page](https://platform.minimax.io/subscribe/token-plan) may direct you to MiniMax's current plan offering; check your existing plan in the console rather than relying on an old price or plan name.
2. Save the subscription key privately and supply it to AI Status as `MINIMAX_API_KEY`. Named accounts can map it from an account-specific environment variable or credential file. `options.api_key_env` can also name the source variable.
3. For mainland credentials, set `options.region: "cn"`. The collector uses `api.minimaxi.com` for that region and `api.minimax.io` otherwise. AI Status does not switch regions automatically based on the key.
4. Enable **MiniMax** in Settings. Linux users use Quickshell **Settings** or `ai-status config` for Waybar. Windows users open tray **Settings** and **Save**; macOS users open menu bar **Settings** and **Save**. Choose **Refresh**, or left-click the Waybar module. CLI refresh is `ai-status refresh`.

## Keep two subscriptions separate

Save this as `minimax-work.json`:

```json
{
  "id": "minimax-work",
  "provider": "minimax",
  "label": "Work Token Plan",
  "env": {
    "MINIMAX_API_KEY": {"from_file": "~/.config/credentials/minimax-work-subscription"}
  },
  "options": {"region": "cn"}
}
```

Run `ai-status accounts add --file minimax-work.json`. A personal subscription should have another ID and credential source. On Windows run `.\ai-status-cli.exe` from the AI Status application folder or use its full path; replace the example filename with a Windows path. File references also support desktop launches without shell exports. See the [multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## Understand the quota display

MiniMax returns remaining percentages. AI Status converts these to percentages **used**, so a higher bar means less allowance remains. Rolling and weekly rows retain their model names. The service's millisecond timestamps supply the reset countdowns; the rolling interval can be classified as a longer daily window when its reported duration exceeds five hours.

Only fields actually returned are shown. The integration does not infer a monthly token count, aggregate overlapping model pools, or turn prepaid credits into a subscription percentage. A new plan or changed response without the supported rolling/weekly fields may be unavailable even when model calls still work.

## Troubleshooting

| Symptom | What to check |
|---|---|
| MiniMax rejected the request | Confirm the Subscription Key and region; MiniMax can return a business error inside an HTTP-success response. |
| 401 or 403 | Replace a revoked/invalid key and verify account eligibility. |
| Works internationally, fails with mainland key | Set `region: "cn"`; credential regions are separate. |
| No model quota rows | Check subscription status and whether its response uses supported quota fields. |
| Reset differs from the calendar month | These are service-defined rolling/weekly windows, not invoice periods. |
| 429 / cached data | Wait for the retry cooldown before refreshing. |
