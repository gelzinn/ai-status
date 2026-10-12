import copy
import json
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from test_portability import IsolatedState, load_provider
from core import fetch, notifications, state, usage_credits


NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
# Upstream attributed live shape, not an independent eligible-account capture:
# https://github.com/ItsJazii/pane/blob/beb4bbfd4e7c776d970a56d254e8cce4d61154d9/
# src-tauri/src/providers/claude.rs#L1049
UPSTREAM_CLOUD = {
    "utilization": 0.0, "resets_at": "2026-11-05T07:59:00+00:00",
    "limit_dollars": 100, "used_dollars": 0.0, "remaining_dollars": 100.0,
    "locked_reason": None,
}


def entry(block=None, **metadata):
    cloud = usage_credits.from_claude({"iguana_necktie": UPSTREAM_CLOUD if block is None else block})
    return {"provider": "Claude", "metrics": [], "_observed_at": NOW.timestamp(),
            "monetary_credits": [cloud] if cloud else [], **metadata}


class CloudCreditParsingTests(unittest.TestCase):
    def test_upstream_shape_has_dollars_and_absolute_expiration(self):
        row = entry()["monetary_credits"][0]
        self.assertEqual(row, {"id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
                               "balance": 100.0, "limit": 100.0, "used": 0.0,
                               "expires_at": "2026-11-05T07:59:00Z", "available": True})
        self.assertEqual(usage_credits.presentation(entry(), NOW)[0]["status"], "available")

    def test_remaining_dollars_win_and_used_dollars_are_fallback(self):
        reported = entry({"limit_dollars": 100, "used_dollars": 10, "remaining_dollars": 75.125})
        derived = entry({"limit_dollars": 100, "used_dollars": 24.875})
        self.assertEqual(reported["monetary_credits"][0]["balance"], derived["monetary_credits"][0]["balance"])
        self.assertEqual(reported["monetary_credits"][0]["balance"], 75.125)
        self.assertEqual(reported["monetary_credits"][0]["used"], 10)
        self.assertEqual(derived["monetary_credits"][0]["used"], 24.875)
        exact = entry({"limit_dollars": 0.3, "used_dollars": 0.1})["monetary_credits"][0]
        self.assertEqual(exact["balance"], 0.2)
        self.assertEqual(exact["used"], 0.1)

    def test_plan_names_do_not_gate_cloud_credits_or_change_quotas(self):
        usage = {"five_hour": {"utilization": 12}, "seven_day": {"utilization": 34},
                 "iguana_necktie": UPSTREAM_CLOUD,
                 "cedar_ember": {"eligible": True, "grants": [{"resets_left": 2, "usable_now": True}]}}
        parser = load_provider("claude", "parse").parse
        for plan in ("", "pro", "max", "team", "enterprise", "unknown-plan"):
            with self.subTest(plan=plan):
                parsed = parser(json.dumps({"plan": plan, "usage": usage}))
                self.assertEqual([metric["percentage"] for metric in parsed["metrics"]], [12, 34])
                self.assertEqual(parsed["monetary_credits"][0]["balance"], 100)
                self.assertEqual(parsed["reset_credits"]["available"], 2)
                self.assertEqual(usage_credits.metrics(parsed, NOW)[0]["unit"], "USD")

    def test_missing_null_and_malformed_blocks_preserve_normal_quota(self):
        blocks = [None, {}, [], 42, {"limit_dollars": None, "remaining_dollars": None},
                  {"limit_dollars": 0, "remaining_dollars": 0},
                  {"limit_dollars": 100, "utilization": 25}]
        for field in ("limit_dollars", "used_dollars", "remaining_dollars"):
            for value in (True, False, "25", [], {}, float("nan"), float("inf"), -1, 101 if field != "limit_dollars" else -100, 10 ** 400):
                blocks.append({"limit_dollars": 100, "used_dollars": 25, "remaining_dollars": 75, field: value})
        blocks.extend({"limit_dollars": 100, "remaining_dollars": 75, "resets_at": value}
                      for value in ("not-a-date", "2026-11-05", "2026-11-05T07:59:00", 1793865540, True))
        blocks.extend({"limit_dollars": 100, "remaining_dollars": 75, "locked_reason": value}
                      for value in (False, 42, [], {}))
        parser = load_provider("claude", "parse").parse
        for block in blocks:
            with self.subTest(block=block):
                result = parser(json.dumps({"five_hour": {"utilization": 12}, "iguana_necktie": block}))
                self.assertNotIn("monetary_credits", result)
                self.assertEqual(result["metrics"][0]["percentage"], 12)

    def test_locked_reason_is_not_exposed_or_persisted(self):
        result = entry({"limit_dollars": 100, "remaining_dollars": 75, "locked_reason": "internal-provider-reason"})
        row = usage_credits.presentation(result, NOW)[0]
        self.assertEqual(row["status"], "unavailable")
        self.assertIsNone(row["balance"])
        self.assertEqual(row["observed_balance"], 75)
        self.assertIn("Last observed $75.00", row["detail"])
        self.assertNotIn("internal-provider-reason", json.dumps(result) + json.dumps(row))
        self.assertTrue(usage_credits.has_credit_data(result))
        empty = entry({"limit_dollars": 100, "remaining_dollars": 75, "locked_reason": "  "})
        self.assertEqual(usage_credits.presentation(empty, NOW)[0]["status"], "available")

    def test_zero_balance_is_exhausted_and_unknown_expiry_is_explicit(self):
        zero = entry({"limit_dollars": 100, "remaining_dollars": 0})
        row = usage_credits.presentation(zero, NOW)[0]
        self.assertEqual((row["status"], row["balance"], row["value"]), ("exhausted", 0, "$0.00"))
        self.assertIn("Exhausted", row["detail"])
        self.assertIn("Expiration not reported", row["detail"])
        self.assertTrue(usage_credits.has_credit_data(zero))

    def test_expiry_uses_utc_instead_of_reset_metadata(self):
        source = entry({"limit_dollars": 250, "remaining_dollars": 150.50,
                        "resets_at": "2026-11-05T02:59:00-05:00"})
        metric = usage_credits.metrics(source, NOW)[0]
        self.assertEqual(metric["amount"], 150.50)
        self.assertIn("Expires 2026-11-05T07:59:00Z", metric["detail"])
        self.assertIsNone(metric["percentage"])
        self.assertNotIn("reset_at", metric)
        self.assertNotIn("reset_in_seconds", metric)
        self.assertEqual(usage_credits.display_lines(source, NOW)[0], "Cloud credits: $150.50")


class CloudCreditFreshnessTests(unittest.TestCase):
    def test_offline_expiration_is_recomputed_without_mutating_cached_balance(self):
        source = entry({"limit_dollars": 100, "remaining_dollars": 75,
                        "resets_at": "2026-10-12T12:02:00Z"})
        original = copy.deepcopy(source)
        self.assertEqual(usage_credits.metrics(source, NOW)[0]["amount"], 75)
        deadline = NOW + timedelta(minutes=2)
        row = usage_credits.presentation(source, deadline)[0]
        self.assertEqual(row["status"], "expired")
        self.assertIsNone(row["balance"])
        self.assertEqual(usage_credits.metrics(source, deadline)[0]["value"], "Expired")
        self.assertIn("Last observed $75.00", row["detail"])
        self.assertEqual(source, original)
        source["_cached"] = True
        self.assertEqual(usage_credits.presentation(source, deadline)[0]["status"], "expired")

    def test_failed_refresh_marks_recent_balance_unavailable(self):
        for metadata in ({"_cached": True}, {"_error": "offline"}, {"error": "failed"}):
            with self.subTest(metadata=metadata):
                row = usage_credits.presentation(entry(**metadata), NOW)[0]
                self.assertEqual(row["status"], "unavailable")
                self.assertTrue(row["stale"])
                self.assertIsNone(row["balance"])
                self.assertIn("Last observed $100.00", row["detail"])
                self.assertIn("Observed 2026-10-12T12:00:00Z", row["detail"])
                self.assertIn("Refresh unavailable", row["detail"])

    def test_observation_age_and_future_or_invalid_timestamps_are_unavailable(self):
        self.assertEqual(usage_credits.presentation(entry(), NOW + timedelta(seconds=600))[0]["status"], "available")
        self.assertEqual(usage_credits.presentation(entry(), NOW + timedelta(seconds=601))[0]["status"], "unavailable")
        for observed in (True, None, "unknown", float("nan"), float("inf"), -1, 10 ** 400, NOW.timestamp() + 6):
            with self.subTest(observed=observed):
                row = usage_credits.presentation(entry(_observed_at=observed), NOW)[0]
                self.assertEqual(row["status"], "unavailable")
                self.assertIsNone(row["balance"])

    def test_cached_balance_without_observation_time_is_unavailable(self):
        source = entry(_cached=True)
        del source["_observed_at"]
        row = usage_credits.presentation(source, NOW)[0]
        self.assertEqual(row["status"], "unavailable")
        self.assertIn("Observation time unavailable", row["detail"])

    def test_missing_observation_time_cannot_claim_available_balance(self):
        source = entry()
        del source["_observed_at"]
        row = usage_credits.presentation(source, NOW)[0]
        self.assertEqual(row["status"], "unavailable")
        self.assertIsNone(row["balance"])
        self.assertIn("Observation time unavailable", row["detail"])
        self.assertTrue(usage_credits.has_credit_data(source))
        source["monetary_credits"][0]["expires_at"] = "2026-10-11T12:00:00Z"
        self.assertEqual(usage_credits.presentation(source, NOW)[0]["status"], "expired")

    def test_damaged_cached_rows_cannot_create_balance_or_crash_other_rows(self):
        valid = entry()["monetary_credits"][0]
        for invalid in (None, [], {}, {**valid, "balance": -1}, {**valid, "currency": "credits"},
                        {**valid, "available": "yes"}, {**valid, "limit": 0},
                        {**valid, "used": 101}, {**valid, "expires_at": "invalid"}):
            with self.subTest(invalid=invalid):
                self.assertFalse(usage_credits.has_credit_data({"monetary_credits": [invalid]}))
                source = entry()
                source["monetary_credits"].insert(0, invalid)
                self.assertEqual(len(usage_credits.presentation(source, NOW)), 1)
        duplicate = entry()
        duplicate["monetary_credits"] *= 2
        self.assertEqual(len(usage_credits.metrics(duplicate, NOW)), 1)

    def test_currency_row_never_drives_quota_notifications(self):
        metric = usage_credits.metrics(entry({"limit_dollars": 100, "remaining_dollars": 0}), NOW)[0]
        self.assertIsNone(notifications._quota(metric))


class CloudCreditCollectorTests(IsolatedState):
    def test_cloud_credits_reuse_existing_authenticated_usage_request(self):
        self.write(self.root / "claude/.credentials.json", {"claudeAiOauth": {
            "accessToken": "example", "subscriptionType": "pro"}})
        query = load_provider("claude")
        raw = {"five_hour": {"utilization": 12}, "iguana_necktie": UPSTREAM_CLOUD}
        with patch.object(query, "request", return_value=json.dumps(raw)) as request:
            parsed = load_provider("claude", "parse").parse(json.dumps(query.query()))
        request.assert_called_once()
        self.assertEqual(request.call_args.args[0], query.USAGE_URL)
        self.assertEqual(parsed["monetary_credits"][0]["balance"], 100)

    def test_credit_only_success_gets_observation_and_survives_failed_refresh(self):
        self.write(self.root / "claude/.credentials.json", {"claudeAiOauth": {"accessToken": "example"}})
        directory = str(Path(__file__).resolve().parents[1] / "src/providers/claude")
        response = subprocess.CompletedProcess([], 0, json.dumps({"iguana_necktie": UPSTREAM_CLOUD}), "")
        with patch.object(fetch.time, "time", return_value=NOW.timestamp()), \
                patch.object(fetch.subprocess, "run", return_value=response), \
                patch.object(fetch, "_pace_service"):
            success = fetch.run_provider(directory)
        self.assertEqual(success["metrics"], [])
        self.assertEqual(success["_observed_at"], NOW.timestamp())
        self.assertFalse(fetch._is_error_result(success))
        with patch.object(fetch.time, "time", return_value=NOW.timestamp() + 61), \
                patch.object(fetch.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 40)), \
                patch.object(fetch, "_pace_service"):
            cached = fetch.run_provider(directory)
        self.assertTrue(cached["_cached"])
        self.assertEqual(cached["_observed_at"], NOW.timestamp())
        self.assertEqual(usage_credits.presentation(cached, NOW + timedelta(seconds=61))[0]["status"], "unavailable")

    def test_provider_and_shared_cache_preserve_expiration_and_account_isolation(self):
        directory = str(self.root / "providers/claude")
        personal = {"provider": "claude", "connection_id": "account:personal"}
        work = {"provider": "claude", "connection_id": "account:work"}
        result = entry()
        with patch.object(fetch.time, "time", return_value=NOW.timestamp()):
            fetch._save_cache(directory, result, personal, "personal-fingerprint")
            self.assertEqual(fetch._load_cache(directory, personal, "personal-fingerprint"), result)
            self.assertIsNone(fetch._load_cache(directory, work, "personal-fingerprint"))
            self.assertIsNone(fetch._load_cache(directory, personal, "other-fingerprint"))
        state.save_cache([{**result, "_connection_id": "account:personal"},
                          {**entry({"limit_dollars": 250, "remaining_dollars": 150}), "_connection_id": "account:work"}])
        restored = state.load_cache()
        self.assertEqual([usage_credits.presentation(item, NOW)[0]["balance"] for item in restored], [100, 150])
        self.assertEqual(restored[0]["monetary_credits"][0]["expires_at"], "2026-11-05T07:59:00Z")


if __name__ == "__main__":
    unittest.main()
