import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))
from core import quickshell, render, reset_credits


def parser(name):
    spec = importlib.util.spec_from_file_location(name + "_parse", SOURCE / "providers" / name / "parse.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse


CLAUDE = {
    "five_hour": {"utilization": 4, "resets_at": "2099-10-22T13:00:00Z"},
    "cedar_ember": {"eligible": True, "grants": [
        {"id": "do-not-publish", "label": "Launch reset", "resets_left": 1,
         "ends_at": "2099-10-22T13:00:00Z", "usable_now": True, "paused": False},
        {"label": "Spent", "resets_left": 0, "usable_now": True},
        {"label": "Paused", "resets_left": 2, "usable_now": True, "paused": True},
        {"label": "Not yet usable", "resets_left": 1, "usable_now": False},
    ]},
}
CODEX = {
    "plan_type": "plus",
    "rate_limit": {"primary_window": {"used_percent": 3, "reset_after_seconds": 3600, "limit_window_seconds": 18000}},
    "rate_limit_reset_credits": {"available_count": 2},
}
DETAILS = {"available_count": 99, "credits": [
    {"id": "do-not-publish", "status": "available", "title": "Full reset", "expires_at": "2099-07-17T00:00:00Z"},
    {"id": "spent-id", "status": "redeemed", "title": "Spent", "expires_at": "2099-07-01T00:00:00Z"},
]}


class ResetCreditsTests(unittest.TestCase):
    def test_claude_counts_only_redeemable_grants_and_discards_handles(self):
        result = parser("claude")(json.dumps({"plan": "max", "usage": CLAUDE}))
        self.assertEqual(result["metrics"][0]["percentage"], 4)
        self.assertEqual(result["reset_credits"]["available"], 1)
        self.assertEqual(result["reset_credits"]["credits"][0]["title"], "Launch reset")
        self.assertNotIn("do-not-publish", json.dumps(result))
        self.assertNotIn("Spent", json.dumps(result["reset_credits"]))

    def test_claude_optional_ineligible_or_invalid_blocks_leave_usage_intact(self):
        for block in (None, {}, {"eligible": False, "grants": CLAUDE["cedar_ember"]["grants"]}, "invalid"):
            result = parser("claude")(json.dumps(dict(CLAUDE, cedar_ember=block)))
            self.assertEqual(result["metrics"][0]["percentage"], 4)
            self.assertFalse(reset_credits.presentation(result.get("reset_credits")))

    def test_claude_grant_counts_use_shared_normalization(self):
        usage = {"cedar_ember": {"eligible": True, "grants": [
            {"resets_left": 2, "usable_now": True},
            {"resets_left": 3, "usable_now": True},
            {"resets_left": True, "usable_now": True},
            {"resets_left": "9", "usable_now": True},
            None,
        ]}}
        self.assertEqual(reset_credits.from_claude(usage)["available"], 14)

    def test_codex_count_survives_without_expiry_details(self):
        result = parser("codex")(json.dumps(CODEX))
        self.assertEqual(result["reset_credits"], {"available": 2, "credits": []})
        presentation = reset_credits.presentation(result["reset_credits"])
        self.assertEqual(presentation["summary"], "2 resets available")
        self.assertEqual(presentation["details"], ["Expiration not reported"])

    def test_codex_filters_redeemed_credits_without_changing_usage_count(self):
        usage = dict(CODEX, rate_limit_reset_credits=dict(CODEX["rate_limit_reset_credits"], credits=DETAILS["credits"]))
        result = parser("codex")(json.dumps(usage))
        self.assertEqual(result["reset_credits"]["available"], 2)
        self.assertEqual(len(result["reset_credits"]["credits"]), 1)
        self.assertNotIn("do-not-publish", json.dumps(result))
        self.assertNotIn("Spent", json.dumps(result["reset_credits"]))

    def test_missing_zero_or_malformed_inventories_do_not_show_an_offer(self):
        for block in (None, {}, {"available_count": 0}, {"available_count": -1}, {"available_count": True}):
            inventory = reset_credits.from_codex({"rate_limit_reset_credits": block})
            self.assertIsNone(reset_credits.presentation(inventory))

    def test_expiry_and_missing_dates_are_explicit_without_negative_countdowns(self):
        now = datetime(2099, 7, 16, 12, tzinfo=timezone.utc)
        inventory = reset_credits.from_codex({"rate_limit_reset_credits": {"available_count": 3, "credits": [
            {"status": "available", "expires_at": "2099-07-17T00:00:00Z"},
            {"status": "available", "expires_at": "2099-07-01T00:00:00Z"},
            {"status": "available", "expires_at": "invalid"},
        ]}})
        lines = reset_credits.presentation(inventory, now)["details"]
        self.assertIn("12h 0m left", lines[0])
        self.assertNotIn("Expired", "\n".join(lines))
        self.assertNotIn("in -", lines[1])
        self.assertIn("Expiration not reported", lines[1])

    def test_shared_renderers_show_reset_credits_without_adding_usage_metrics(self):
        data = parser("claude")(json.dumps(CLAUDE))
        data.update(_dir="claude", _idx=0, _cached=True)
        selected = {"provider": "claude", "idx": 0, "metric": "rolling", "icon_mode": "off"}
        with patch("core.config.enabled_order", return_value=["claude"]):
            snapshot = quickshell.build_snapshot([data], selected)
        provider = snapshot["providers"][0]
        self.assertEqual(len(provider["metrics"]), 1)
        self.assertEqual(provider["resetCredits"]["available"], 1)
        self.assertTrue(provider["cached"])
        self.assertIn("Launch reset", provider["resetCredits"]["details"][0])
        for output in (render.build_final_state([data], selected), render.build_loading_state([data], 0, selected)):
            self.assertEqual(set(output), {"text", "tooltip"})
            self.assertIn("Reset credits", output["tooltip"])
            self.assertIn("Reset credits: 1 available", output["tooltip"])

    def test_provider_labels_are_plain_text_in_qml_and_escaped_for_pango(self):
        data = parser("codex")(json.dumps(CODEX))
        data.update(_dir="codex", _idx=0)
        data["reset_credits"]["credits"] = [{"title": '<b>Max & Plus</b>', "count": 1, "expires_at": None}]
        with patch("core.config.enabled_order", return_value=["codex"]):
            snapshot = quickshell.build_snapshot([data])
        self.assertIn('<b>Max & Plus</b>', snapshot["providers"][0]["resetCredits"]["details"][0])
        tooltip = render.build_final_state([data])["tooltip"]
        self.assertIn("&lt;b&gt;Max &amp; Plus&lt;/b&gt;", tooltip)


@unittest.skipIf(sys.platform == "win32", "Requires Linux shell integration")
class ResetQueryTests(unittest.TestCase):
    def run_query(self, name, usage, details=None, fail_details=False):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            auth = home / (".claude/.credentials.json" if name == "claude" else ".codex/auth.json")
            auth.parent.mkdir()
            auth.write_text(json.dumps({
                "claudeAiOauth": {"accessToken": "fixture-token", "expiresAt": 4102444800000, "subscriptionType": "max"},
                "tokens": {"access_token": "fixture-token", "account_id": "fixture-account"},
            }))
            binary = home / "bin"
            binary.mkdir()
            curl = binary / "curl"
            curl.write_text('''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['MOCK_CURL_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
if any('rate-limit-reset-credits' in arg for arg in args):
    if os.environ['MOCK_FAIL_DETAILS'] == '1': sys.exit(22)
    print(os.environ['MOCK_DETAILS'])
else:
    print(os.environ['MOCK_USAGE'])
''')
            curl.chmod(0o755)
            log = home / "requests"
            env = dict(os.environ, HOME=str(home), PATH=str(binary) + os.pathsep + os.environ["PATH"],
                       MOCK_CURL_LOG=str(log), MOCK_FAIL_DETAILS="1" if fail_details else "0",
                       MOCK_USAGE=json.dumps(usage), MOCK_DETAILS=json.dumps(details))
            result = subprocess.run(["bash", str(SOURCE / "providers" / name / "query.sh")], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            return parser(name)(result.stdout.strip()), [json.loads(line) for line in log.read_text().splitlines()]

    def test_claude_requests_reset_inventory_using_the_accepted_client_surface(self):
        result, requests = self.run_query("claude", CLAUDE)
        self.assertEqual(result["reset_credits"]["available"], 1)
        self.assertIn("https://api.anthropic.com/api/oauth/usage?cedar_ember=1", requests[0])
        self.assertIn("User-Agent: claude-cli/2.1.281 (external, cli)", requests[0])

    def test_codex_details_enrich_count_from_usage_and_never_redeem(self):
        result, requests = self.run_query("codex", CODEX, DETAILS)
        self.assertEqual(result["reset_credits"]["available"], 2)
        self.assertEqual(len(result["reset_credits"]["credits"]), 1)
        self.assertEqual(len(requests), 2)
        self.assertIn("https://chatgpt.com/backend-api/wham/rate-limit-reset-credits", requests[1])
        self.assertNotIn("POST", json.dumps(requests))
        self.assertNotIn("consume", json.dumps(requests))

    def test_codex_details_failure_does_not_lose_usage_or_count(self):
        result, requests = self.run_query("codex", CODEX, fail_details=True)
        self.assertEqual(result["metrics"][0]["percentage"], 3)
        self.assertEqual(result["reset_credits"], {"available": 2, "credits": []})
        self.assertEqual(len(requests), 2)

    def test_codex_no_available_credits_does_not_make_an_extra_request(self):
        for block in (None, {"available_count": 0}):
            result, requests = self.run_query("codex", dict(CODEX, rate_limit_reset_credits=block))
            self.assertEqual(result["metrics"][0]["percentage"], 3)
            self.assertEqual(len(requests), 1)


if __name__ == "__main__":
    unittest.main()
