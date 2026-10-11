"""Codex usage credits remain distinct from plan quotas and banked resets."""
import copy
import json
import os
from unittest.mock import patch

from test_portability import IsolatedState, load_provider
from core import config, fetch, quickshell, render, state, swiftbar
from core.provider_http import QueryError


# CreditStatusDetails in openai/codex defines credits.balance as an optional
# string, with independent has_credits and unlimited flags.
USAGE = {
    "plan_type": "pro",
    "rate_limit": {
        "primary_window": {"used_percent": 20, "limit_window_seconds": 18000,
                           "reset_after_seconds": 3600},
        "secondary_window": {"used_percent": 99, "limit_window_seconds": 604800,
                             "reset_after_seconds": 604800},
    },
    "credits": {"has_credits": True, "unlimited": False, "balance": "62500.00"},
    "rate_limit_reset_credits": {"available_count": 3},
}
KEY = "credits:Usage credits (credits)"


class CodexUsageCreditsTests(IsolatedState):
    def setUp(self):
        super().setUp()
        self.parser = load_provider("codex", "parse")
        config.save_config(["codex"])

    def parse(self, credits):
        usage = copy.deepcopy(USAGE)
        usage["credits"] = credits
        return self.parser.parse(json.dumps(usage))

    def entry(self, result=None):
        return dict(result or self.parser.parse(json.dumps(USAGE)), _dir="codex", _idx=0)

    def test_promotional_balance_does_not_replace_quotas_or_reset_inventory(self):
        result = self.parser.parse(json.dumps(USAGE))
        self.assertEqual([metric["type"] for metric in result["metrics"]], ["rolling", "weekly", "credits"])
        self.assertEqual([metric["percentage"] for metric in result["metrics"]], [20, 99, None])
        self.assertEqual(result["metrics"][2]["amount"], 62500)
        self.assertEqual(result["metrics"][2]["unit"], "credits")
        self.assertNotIn("limit", result["metrics"][2])
        self.assertIsNone(result["metrics"][2]["reset_in_seconds"])
        self.assertEqual(result["reset_credits"], {"available": 3, "credits": []})
        self.assertEqual(render.metric_key(result["metrics"][2]), KEY)

    def test_fractional_large_zero_and_signed_balances_use_the_reported_amount(self):
        for balance in ("62500.25", "125000.75", 80000, "0", 0, "-0.25"):
            with self.subTest(balance=balance):
                result = self.parse({"has_credits": False, "unlimited": False, "balance": balance})
                metric = result["metrics"][2]
                self.assertEqual(metric["amount"], float(balance))
                self.assertIsNone(metric["percentage"])
                self.assertEqual(render.metric_key(metric), KEY)

    def test_unlimited_wins_over_an_incidental_balance(self):
        result = self.parse({"has_credits": True, "unlimited": True, "balance": "0"})
        metric = result["metrics"][2]
        self.assertEqual(render.metric_value(metric), "Unlimited")
        self.assertNotIn("amount", metric)
        self.assertIsNone(metric["percentage"])
        self.assertEqual(render.metric_key(metric), KEY)

    def test_available_credits_without_a_valid_balance_do_not_become_zero(self):
        for balance in (None, True, False, "", "NaN", "Infinity", "-Infinity", "1e999", [], {}, "unreported"):
            with self.subTest(balance=balance):
                result = self.parse({"has_credits": True, "balance": balance})
                metric = result["metrics"][2]
                self.assertEqual(render.metric_value(metric), "Available")
                self.assertEqual(render.metric_detail(metric), "Balance not reported")
                self.assertNotIn("amount", metric)

    def test_missing_or_malformed_credit_blocks_leave_quota_windows_intact(self):
        for credits in (None, [], "62500", 62500, True, {}, {"has_credits": False},
                        {"has_credits": "true", "unlimited": "true"},
                        {"balance": True}, {"balance": "NaN"}):
            with self.subTest(credits=credits):
                result = self.parse(credits)
                self.assertEqual([m["percentage"] for m in result["metrics"]], [20, 99])
                self.assertEqual(result["reset_credits"]["available"], 3)
        usage = copy.deepcopy(USAGE)
        del usage["credits"]
        self.assertEqual(len(self.parser.parse(json.dumps(usage))["metrics"]), 2)

    def test_balance_only_response_is_still_a_usable_selectable_provider(self):
        result = self.parser.parse(json.dumps({"plan_type": "pro", "credits": USAGE["credits"]}))
        entry = self.entry(result)
        self.assertFalse(fetch._is_error_result(entry))
        self.assertEqual(len(quickshell.usable_metrics(entry)), 1)
        snapshot = quickshell.build_snapshot([entry])
        self.assertEqual(snapshot["selected"]["metric"], KEY)
        self.assertEqual(snapshot["providers"][0]["metrics"][0]["value"], "62,500.00 credits")

    def test_non_object_and_invalid_json_do_not_crash_the_parser(self):
        for raw in ("null", "[]", '"62500"', "true", "invalid JSON", None):
            with self.subTest(raw=raw):
                self.assertEqual(self.parser.parse(raw), {"provider": "Codex", "metrics": []})

    def test_cache_and_quickshell_keep_balance_and_resets_independent(self):
        entry = self.entry()
        fetch._save_cache("codex", entry)
        cached = fetch._load_cache("codex")
        self.assertEqual(cached, entry)
        state.save_cache([cached])
        quickshell.select_metric({"provider": "codex", "idx": 0, "metric": KEY})
        selected = state.load_selected()
        snapshot = quickshell.build_snapshot([cached], selected)
        provider = snapshot["providers"][0]
        balance = next(m for m in provider["metrics"] if m["key"] == KEY)
        self.assertEqual(balance["name"], "Usage credits")
        self.assertEqual(balance["value"], "62,500.00 credits")
        self.assertFalse(balance["hasPercentage"])
        self.assertTrue(balance["isAmount"])
        self.assertEqual(provider["resetCredits"]["available"], 3)
        self.assertIn("62,500.00 credits", snapshot["text"])
        self.assertEqual(selected["metric"], KEY)

    def test_waybar_and_swiftbar_display_balance_without_a_fake_percentage(self):
        entry = self.entry()
        selected = {"provider": "codex", "idx": 0, "metric": KEY, "icon_mode": "off"}
        for tooltip in (render.format_provider_block(entry), render.format_loading_provider_block(entry, 0)):
            self.assertIn("Usage credits", tooltip)
            self.assertIn("62,500.00 credits", tooltip)
            self.assertIn("Reset credits: 3 available", tooltip)
            balance_section = tooltip.split("Usage credits:", 1)[1].split("Reset credits:", 1)[0]
            self.assertNotIn("█", balance_section)
            self.assertNotIn("%", quickshell.plain_text(balance_section))
        ready = render.build_final_state([entry], selected=selected)
        self.assertIn("62,500.00 credits", ready["text"])
        loading = render.build_loading_state([entry], 0, selected=selected)
        self.assertIn("62,500.00 credits", loading["tooltip"])
        self.assertIn(render.SPINNERS[0], loading["text"])
        menu = swiftbar.render_menu([entry], selected)
        self.assertIn("Usage credits:  62,500.00 credits", menu)
        self.assertIn("Reset credits: 3 available", menu)
        self.assertIn("62,500.00 credits", menu.splitlines()[0])

    def test_collector_preserves_balance_when_reset_details_are_unavailable(self):
        query = load_provider("codex")
        for details in (QueryError("HTTP 403"), "invalid JSON", '{"credits": []}'):
            with self.subTest(details=details), \
                    patch.dict(os.environ, {"CODEX_ACCESS_TOKEN": "fixture-token", "CODEX_ACCOUNT_ID": "fixture-account"}, clear=True), \
                    patch.object(query, "request", side_effect=[json.dumps(USAGE), details]) as request:
                result = self.parser.parse(query.query())
            self.assertEqual(result["metrics"][2]["amount"], 62500)
            self.assertEqual(result["reset_credits"]["available"], 3)
            self.assertEqual(request.call_args_list[0].args[1], request.call_args_list[1].args[1])

    def test_balance_needs_no_additional_request_when_there_are_no_resets(self):
        query = load_provider("codex")
        usage = dict(USAGE, rate_limit_reset_credits={"available_count": 0})
        with patch.dict(os.environ, {"CODEX_ACCESS_TOKEN": "fixture-token"}, clear=True), \
                patch.object(query, "request", return_value=json.dumps(usage)) as request:
            result = self.parser.parse(query.query())
        request.assert_called_once()
        self.assertEqual(result["metrics"][2]["amount"], 62500)
        self.assertEqual(result["reset_credits"]["available"], 0)
