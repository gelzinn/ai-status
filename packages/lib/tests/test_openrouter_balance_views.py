"""Account credits collected with an inference key reach the desktop views."""
import copy
import json
import os
import unittest
from unittest.mock import patch

from test_portability import IsolatedState, load_provider
from core import accounts, config, fetch, macos, paths, quickshell, render, state, swiftbar
from core.provider_http import QueryError

try:
    from PySide6.QtWidgets import QApplication
    from core import tray
    HAS_QT = True
except ImportError:
    HAS_QT = False


ACCOUNT_KEY = "credits:Account spend / total credits (USD)"
MONTHLY_KEY = "monthly:Month spend (this key) (USD)"
KEY_USAGE = {"data": {"usage_monthly": 2.24, "limit": None, "is_management_key": False}}
CREDITS = {"data": {"total_credits": 100.50, "total_usage": 25.25}}


def collect(credits=CREDITS):
    query = load_provider("openrouter")

    def response(url, headers):
        if url.endswith("/key"):
            return copy.deepcopy(KEY_USAGE)
        if url.endswith("/credits"):
            if isinstance(credits, Exception):
                raise credits
            return copy.deepcopy(credits)
        raise AssertionError(f"Unexpected OpenRouter endpoint: {url}")

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fixture-inference-key"}, clear=True), \
            patch.object(query, "json_request", side_effect=response) as request:
        result = load_provider("openrouter", "parse").parse(json.dumps(query.query()))
    return dict(result, _dir="openrouter", _idx=0), request.call_args_list


class OpenRouterBalanceViewsTests(IsolatedState):
    def setUp(self):
        super().setUp()
        config.save_config(["openrouter"])
        for replacement in (
            patch.object(fetch, "get_version_info", return_value={"current": "0.15.0", "latest": "0.15.0", "has_update": False}),
            patch.object(macos.LogoCache, "get", return_value=""),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_inference_key_shows_account_bar_and_separate_key_spend(self):
        entry, requests = collect()
        self.assertEqual([call.args[0] for call in requests], [
            "https://openrouter.ai/api/v1/key", "https://openrouter.ai/api/v1/credits"])
        self.assertTrue(all(call.args[1]["Authorization"] == "Bearer fixture-inference-key" for call in requests))
        selected = dict(provider="openrouter", idx=0, metric=ACCOUNT_KEY, icon_mode="off")
        snapshot = quickshell.build_snapshot([entry], selected)
        account, monthly = snapshot["providers"][0]["metrics"]
        self.assertEqual(account["key"], ACCOUNT_KEY)
        self.assertTrue(account["hasPercentage"])
        self.assertFalse(account["isAmount"])
        self.assertAlmostEqual(account["percentage"], 25.25 / 100.50 * 100, places=2)
        self.assertEqual(account["value"], "$25.25 / $100.50")
        self.assertEqual(account["detail"], "Available balance: $75.25")
        self.assertEqual(monthly["key"], MONTHLY_KEY)
        self.assertEqual(monthly["value"], "$2.24")
        self.assertFalse(monthly["hasPercentage"])
        self.assertEqual(snapshot["selected"]["metric"], ACCOUNT_KEY)
        self.assertIn("$25.25 / $100.50", snapshot["text"])
        json.dumps(snapshot, allow_nan=False)
        for output in (render.build_final_state([entry], selected)["tooltip"],
                       swiftbar.render_menu([entry], selected)):
            with self.subTest(output=output[:30]):
                self.assertIn("$25.25 / $100.50", output)
                self.assertIn("$75.25", output)
                self.assertIn("$2.24", output)
                self.assertIn("█", output)

    def test_remaining_preference_keeps_account_identity_and_monthly_spend(self):
        entry, _ = collect()
        original = copy.deepcopy(entry)
        selected = dict(provider="openrouter", idx=0, metric=ACCOUNT_KEY, icon_mode="off", usage_display="remaining")
        snapshot = quickshell.build_snapshot([entry], selected)
        account, monthly = snapshot["providers"][0]["metrics"]
        self.assertEqual(account["key"], ACCOUNT_KEY)
        self.assertAlmostEqual(account["percentage"], 75.25 / 100.50 * 100, places=2)
        self.assertEqual(account["value"], "$75.25 / $100.50")
        self.assertEqual(monthly["value"], "$2.24")
        self.assertFalse(monthly["hasPercentage"])
        self.assertIn("$75.25 / $100.50", render.build_final_state([entry], selected)["text"])
        self.assertIn("$75.25 / $100.50", swiftbar.render_menu([entry], selected).splitlines()[0])
        self.assertEqual(entry, original)

    def test_denied_credit_lookup_keeps_valid_key_usage_without_a_balance_bar(self):
        for status in (401, 403):
            with self.subTest(status=status):
                entry, _ = collect(QueryError(f"HTTP {status}", status=status))
                snapshot = quickshell.build_snapshot([entry], dict(provider="openrouter", idx=0, metric=ACCOUNT_KEY))
                metrics = snapshot["providers"][0]["metrics"]
                self.assertEqual(len(metrics), 1)
                self.assertEqual(metrics[0]["key"], MONTHLY_KEY)
                self.assertEqual(metrics[0]["value"], "$2.24")
                self.assertFalse(metrics[0]["hasPercentage"])
                self.assertEqual(snapshot["selected"]["metric"], MONTHLY_KEY)
                self.assertNotIn("$0.00", snapshot["text"])

    def test_credit_selection_remains_bound_to_the_selected_account(self):
        accounts.save_document({"version": 1, "accounts": [
            {"id": "personal", "provider": "openrouter", "label": "Personal"},
            {"id": "work", "provider": "openrouter", "label": "Work"},
        ]}, config.accounts_file())
        config.save_config([])
        personal, _ = collect()
        work, _ = collect({"data": {"total_credits": 50, "total_usage": 40}})
        data = [dict(entry, _connection_id="account:" + account, _account_label=label)
                for entry, account, label in ((personal, "personal", "Personal"), (work, "work", "Work"))]
        state.save_cache(data)
        selected = dict(provider="account:work", idx=0, metric=ACCOUNT_KEY)
        quickshell.select_metric(selected)
        snapshot = quickshell.build_snapshot(data, dict(state.load_selected(), icon_mode="off"))
        self.assertEqual(snapshot["selected"]["provider"], "account:work")
        self.assertEqual(snapshot["selected"]["metric"], ACCOUNT_KEY)
        self.assertEqual(snapshot["text"], "OpenRouter · Work $40.00 / $50.00")
        self.assertEqual([provider["metrics"][0]["detail"] for provider in snapshot["providers"]],
                         ["Available balance: $75.25", "Available balance: $10.00"])


@unittest.skipUnless(HAS_QT, "Install windows/requirements.txt to test the desktop adapter")
class OpenRouterDesktopBalanceTests(IsolatedState):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        replacement = patch.object(paths, "CONFIG_DIR", self.root / "config")
        replacement.start()
        self.addCleanup(replacement.stop)
        config.save_config(["openrouter"])
        with patch.object(tray.QTimer, "singleShot"), patch.object(tray.QSystemTrayIcon, "show"):
            self.dashboard = tray.Dashboard(self.app)
        for timer in (self.dashboard.poll, self.dashboard.auto_refresh, self.dashboard.animation):
            timer.stop()
        self.addCleanup(self.dashboard.tray.hide)
        self.addCleanup(self.dashboard.deleteLater)

    def test_collected_account_credits_render_as_a_selectable_progress_bar(self):
        entry, _ = collect()
        self.dashboard.on_result("openrouter", [entry])
        self.dashboard.show()
        self.app.processEvents()
        account, monthly = self.dashboard.metric_buttons
        self.assertEqual(account.value[2], ACCOUNT_KEY)
        self.assertEqual(account.percentage.text(), "$25.25 / $100.50")
        self.assertEqual(account.description.text(), "Available balance: $75.25")
        self.assertFalse(account.bar_container.isHidden())
        self.assertFalse(account.is_amount)
        self.assertTrue(monthly.bar_container.isHidden())
        account.click()
        self.assertEqual(state.load_selected()["metric"], ACCOUNT_KEY)
        self.assertIn("$25.25 / $100.50", self.dashboard.tray.toolTip())
        monthly.click()
        self.assertEqual(state.load_selected()["metric"], MONTHLY_KEY)
        self.assertIn("$2.24", self.dashboard.tray.toolTip())

    def test_empty_wallet_keeps_zero_balance_visible_without_invented_progress(self):
        entry, _ = collect({"data": {"total_credits": 0, "total_usage": 0}})
        self.dashboard.on_result("openrouter", [entry])
        self.dashboard.show()
        self.app.processEvents()
        balances = [row for row in self.dashboard.metric_buttons if row.value[2].startswith("credits:")]
        self.assertTrue(balances)
        self.assertTrue(all(row.bar_container.isHidden() for row in balances))
        self.assertTrue(all(row.percentage.text() == "$0.00" for row in balances))
        balance = next(row for row in balances if row.value[2] == "credits:Account credit balance (USD)")
        balance.click()
        self.assertEqual(state.load_selected()["metric"], balance.value[2])
        self.assertIn("$0.00", self.dashboard.tray.toolTip())


if __name__ == "__main__":
    unittest.main()
