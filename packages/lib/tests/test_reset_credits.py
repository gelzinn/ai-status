import json
from datetime import datetime, timezone
from unittest.mock import patch

from test_portability import IsolatedState, load_provider
from core import fetch, render, reset_credits
from core.provider_http import QueryError

FUTURE = "2099-10-22T16:00:00Z"
CLAUDE_USAGE = {
    "five_hour": {"utilization": 2}, "seven_day": {"utilization": 24},
    "limits": [{"kind": "weekly_scoped", "percent": 53,
                "scope": {"model": {"display_name": "Fable"}}}],
    "cedar_ember": {"eligible": True, "grants": [
        {"id": "redemption-secret", "label": "Opus launch reset", "resets_left": 2,
         "ends_at": FUTURE, "usable_now": True, "paused": False},
        {"resets_left": 1, "usable_now": False},
        {"resets_left": 1, "usable_now": True, "paused": True},
        {"resets_left": 0, "usable_now": True},
    ]},
}
CODEX_USAGE = {"plan_type": "pro", "rate_limit": {"primary_window": {
    "used_percent": 23, "limit_window_seconds": 18000, "reset_after_seconds": 3600}},
    "rate_limit_reset_credits": {"available_count": 2}}


class ResetCreditsTests(IsolatedState):
    def codex_credentials(self):
        self.write(self.root / "codex/auth.json", {"tokens": {
            "access_token": "example", "account_id": "account"}})

    def test_claude_opts_into_grants_and_preserves_all_usage_windows(self):
        self.write(self.root / "claude/.credentials.json", {"claudeAiOauth": {
            "accessToken": "example", "subscriptionType": "pro"}})
        module = load_provider("claude")
        with patch.object(module, "request", return_value=json.dumps(CLAUDE_USAGE)) as api:
            result = load_provider("claude", "parse").parse(json.dumps(module.query()))
        self.assertIn("cedar_ember=1", api.call_args.args[0])
        self.assertTrue(api.call_args.args[1]["User-Agent"].startswith("claude-cli/"))
        self.assertEqual([metric["type"] for metric in result["metrics"]], ["rolling", "weekly", "weekly"])
        self.assertEqual(result["metrics"][2]["detail"], "Fable · no reset available")
        self.assertEqual([render.metric_key(metric) for metric in result["metrics"]],
                         ["rolling", "weekly", "weekly:Fable"])
        self.assertEqual(result["reset_credits"]["available"], 2)
        self.assertEqual(len(result["reset_credits"]["credits"]), 1)
        self.assertNotIn("redemption-secret", json.dumps(result))

    def test_claude_ineligible_or_missing_grants_leave_usage_intact(self):
        for block in (None, {}, {"eligible": False, "grants": CLAUDE_USAGE["cedar_ember"]["grants"]},
                      {"eligible": True, "grants": None}, {"eligible": True, "grants": [None, {}, "invalid"]}):
            with self.subTest(block=block):
                usage = {"five_hour": {"utilization": 21}, "cedar_ember": block}
                result = load_provider("claude", "parse").parse(json.dumps(usage))
                self.assertEqual(result["metrics"][0]["percentage"], 21)
                self.assertEqual(reset_credits.display_lines(result.get("reset_credits")), [])

    def test_codex_fetches_optional_expiry_with_the_same_account(self):
        self.codex_credentials()
        module = load_provider("codex")
        details = {"available_count": 999, "credits": [
            {"id": "redemption-secret", "status": "available", "title": "Full reset", "expires_at": FUTURE},
            {"id": "spent-secret", "status": "redeemed", "expires_at": FUTURE}]}
        with patch.object(module, "request", side_effect=[json.dumps(CODEX_USAGE), json.dumps(details)]) as api:
            raw = module.query()
        self.assertTrue(api.call_args.args[0].endswith("/rate-limit-reset-credits"))
        self.assertEqual(api.call_args_list[0].args[1], api.call_args_list[1].args[1])
        self.assertEqual(api.call_args.args[1]["ChatGPT-Account-Id"], "account")
        self.assertNotIn("secret", raw)
        result = load_provider("codex", "parse").parse(raw)
        self.assertEqual(result["metrics"][0]["percentage"], 23)
        self.assertEqual(result["reset_credits"]["available"], 2)
        self.assertEqual(len(result["reset_credits"]["credits"]), 1)
        self.assertIn("Expires", "\n".join(reset_credits.display_lines(result["reset_credits"])))

    def test_codex_detail_failure_keeps_usage_and_credit_count(self):
        self.codex_credentials()
        module = load_provider("codex")
        for optional in (QueryError("HTTP 403"), QueryError("HTTP 429"), "invalid JSON", "null", '{"credits":null}'):
            with self.subTest(optional=optional):
                with patch.object(module, "request", side_effect=[json.dumps(CODEX_USAGE), optional]):
                    result = load_provider("codex", "parse").parse(module.query())
                self.assertEqual(result["metrics"][0]["percentage"], 23)
                self.assertEqual(reset_credits.display_lines(result["reset_credits"]),
                                 ["Reset credits: 2 available", "Expiry not provided"])

    def test_codex_does_not_request_details_without_available_credits(self):
        self.codex_credentials()
        module = load_provider("codex")
        for block in (None, {}, {"available_count": 0, "credits": None}, {"available_count": -1}):
            with self.subTest(block=block):
                raw = json.dumps({"plan_type": "pro", "rate_limit_reset_credits": block})
                with patch.object(module, "request", return_value=raw) as api:
                    self.assertEqual(module.query(), raw)
                api.assert_called_once()
                self.assertEqual(reset_credits.display_lines(reset_credits.from_codex(json.loads(raw))), [])

    def test_expired_credits_disappear_and_unknown_expiry_is_explicit(self):
        now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        block = {"available": 2, "credits": [
            {"count": 1, "title": "Expired reset", "expires_at": "2026-10-09T23:59:59Z"},
            {"count": 1, "title": "Available reset", "expires_at": None}]}
        lines = reset_credits.display_lines(block, now)
        self.assertEqual(lines, ["Reset credits: 1 available", "Available reset", "Expiry not provided"])
        self.assertEqual(reset_credits.display_lines({"available": 1, "credits": block["credits"][:1]}, now), [])

    def test_metadata_survives_cache_and_is_escaped_in_waybar_loading_and_ready(self):
        result = load_provider("claude", "parse").parse(json.dumps(CLAUDE_USAGE))
        result["reset_credits"]["credits"][0]["title"] = '<b>Reset & credit</b>'
        directory = str(self.root / "providers/claude")
        fetch._save_cache(directory, result)
        self.assertEqual(fetch._load_cache(directory), result)
        self.assertFalse(fetch._is_error_result(result))
        for tooltip in (render.format_provider_block(result), render.format_loading_provider_block(result, 0)):
            self.assertIn("Reset credits: 2 available", tooltip)
            self.assertIn("&lt;b&gt;Reset &amp; credit&lt;/b&gt;", tooltip)
            self.assertNotIn("<b>Reset", tooltip)

    def test_malformed_optional_counts_cannot_create_credits(self):
        for amount in (None, True, -1, 1.5, float("nan"), "invalid"):
            with self.subTest(amount=amount):
                self.assertEqual(reset_credits.count(amount), 0)
        self.assertEqual(reset_credits.display_lines({"available": 1, "credits": [None, "invalid"]}),
                         ["Reset credits: 1 available", "Expiry not provided"])

    def test_display_details_do_not_exceed_available_count_or_include_expired_credits(self):
        now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        block = {"available": 4, "credits": [
            {"title": "Expired", "count": 1, "expires_at": "2026-10-09T16:00:00Z"},
            {"title": "Full reset", "count": 2, "expires_at": FUTURE},
            {"title": "Weekly reset", "count": 9, "expires_at": FUTURE},
            {"title": "Invalid", "count": 0}]}
        data = reset_credits.available_credits(block, now)
        self.assertEqual(data["available"], 3)
        self.assertEqual([item["title"] for item in data["credits"]], ["Full reset", "Weekly reset"])
        self.assertEqual([item["count"] for item in data["credits"]], [2, 1])
        self.assertEqual(data["undetailed"], 0)
        self.assertEqual(block["credits"][2]["count"], 9)  # Display normalization leaves cached data intact.
        data = reset_credits.available_credits({"available": 3, "credits": [
            {"title": "Full reset", "count": 1, "expires_at": FUTURE}]}, now)
        self.assertEqual(data["available"], 3)
        self.assertEqual(data["undetailed"], 2)
