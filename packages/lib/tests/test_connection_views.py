"""Connection identity and amount presentation across desktop adapters."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from core import accounts, config, daemon, quickshell, render, state


class ConnectionViewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for target, value in (("core.config.CONFIG_FILE", str(root / "providers.json")),
                              ("core.state.SELECTED_FILE", str(root / "selected.json")),
                              ("core.state.CACHE_FILE", str(root / "usage.json"))):
            replacement = patch(target, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        # Keep CLI logins on this machine out of the saved-account fixtures.
        discovery = patch("core.folder_accounts.discover", return_value=[])
        discovery.start()
        self.addCleanup(discovery.stop)
        accounts.save_document({"version": 1, "accounts": [
            {"id": "personal", "provider": "openrouter", "label": "Personal"},
            {"id": "work", "provider": "openrouter", "label": "Work"},
        ]}, config.accounts_file())
        config.save_config([])
        self.data = [dict(provider="OpenRouter", _dir="openrouter", _idx=0,
                          _connection_id="account:" + name, _account_id=name, _account_label=label,
                          metrics=[dict(type="balance", name="Available balance", percentage=None,
                                        amount=amount, unit="USD", detail="Available credits")])
                     for name, label, amount in (("personal", "Personal", 8.25), ("work", "Work", 42.50))]
        self.selected = dict(provider="account:work", idx=0, metric="balance:Available balance", icon_mode="off")

    def test_snapshot_amounts_labels_loading_and_logo_use_independent_identity(self):
        result = quickshell.build_snapshot(self.data, self.selected, pending={"account:personal"},
                                          logo_paths={"openrouter": "/tmp/openrouter.png"})
        self.assertEqual([p["id"] for p in result["providers"]], ["account:personal", "account:work"])
        self.assertEqual(result["text"], "OpenRouter · Work $42.50")
        self.assertTrue(result["providers"][0]["loading"])
        self.assertFalse(result["providers"][1]["loading"])
        self.assertEqual(result["providers"][1]["logoPath"], "/tmp/openrouter.png")
        metric = result["providers"][1]["metrics"][0]
        self.assertFalse(metric["hasPercentage"])
        self.assertIsNone(metric["percentage"])
        self.assertEqual(metric["value"], "$42.50")
        json.dumps(result, allow_nan=False)

    def test_waybar_amount_has_no_fake_progress_and_account_label_is_escaped(self):
        self.data[1]["_account_label"] = "Work <admin>"
        output = render.build_final_state(self.data, self.selected)
        self.assertIn("$42.50", output["tooltip"])
        self.assertIn("Work &lt;admin&gt;", output["tooltip"])
        self.assertNotIn("0%", quickshell.plain_text(output["tooltip"]))
        self.assertNotIn("█", output["tooltip"])

    def test_settings_reorder_and_disable_accounts_preserves_credentials(self):
        choice = dict(self.selected)
        choice.pop("icon_mode")
        payload = dict(enabled=["account:work"], display=dict(show_provider=True, show_model=True,
                       show_metric=False, show_pct=True), iconMode="logo", selected=choice)
        with patch.object(state, "trigger_refresh"):
            quickshell.save_settings(payload)
        self.assertEqual(config.enabled_connection_order(), ["account:work"])
        self.assertEqual(len(config.load_accounts()), 2)
        snapshot = quickshell.build_snapshot(self.data, self.selected)
        self.assertEqual(len(snapshot["providers"]), 1)
        self.assertEqual(snapshot["settings"]["names"]["account:work"], "OpenRouter · Work")

    def test_click_selection_and_stream_groups_cannot_mix_accounts(self):
        state.save_cache(self.data)
        with patch.object(state, "trigger_refresh") as refresh:
            quickshell.select_metric(self.selected)
            refresh.assert_not_called()
        self.assertEqual(state.load_selected()["provider"], "account:work")
        groups = daemon._group_by_dir(self.data)
        self.assertEqual(set(groups), {"account:personal", "account:work"})
        self.assertEqual(groups["account:work"][0]["metrics"][0]["amount"], 42.50)

    def test_text_only_allowance_is_visible_without_percentage(self):
        entry = dict(self.data[0], metrics=[dict(type="monthly", percentage=None, value="Unlimited", detail="Included usage")])
        snapshot = quickshell.build_snapshot([entry], self.selected)
        self.assertEqual(snapshot["providers"][0]["metrics"][0]["value"], "Unlimited")
        self.assertFalse(snapshot["providers"][0]["metrics"][0]["hasPercentage"])

    def test_account_credit_ratio_survives_snapshot_selection_and_tooltip(self):
        metric = dict(type="credits", name="Account spend / total credits", percentage=25,
                      amount=25, limit=100, unit="USD", value_format="amount_ratio")
        entry = dict(self.data[1], metrics=[metric])
        choice = dict(self.selected, metric=render.metric_key(metric))
        self.assertEqual(quickshell.build_snapshot([entry], choice)["text"], "OpenRouter · Work $25.00")
        choice["show_total"] = True
        snapshot = quickshell.build_snapshot([entry], choice)
        self.assertEqual(snapshot["providers"][0]["metrics"][0]["value"], "$25.00 / $100.00")
        self.assertTrue(snapshot["providers"][0]["metrics"][0]["hasPercentage"])
        self.assertEqual(snapshot["text"], "OpenRouter · Work $25.00 / $100.00")
        tooltip = render.build_final_state([entry], choice)["tooltip"]
        self.assertIn("$25.00 / $100.00", tooltip)
        self.assertIn("█", tooltip)

    def test_invalid_credit_denominators_keep_safe_amount_fallbacks(self):
        for limit in (0, -1, None, "unavailable", float("inf"), float("nan")):
            with self.subTest(limit=limit):
                metric = dict(amount=0, limit=limit, percentage=None, unit="USD", value_format="amount_ratio")
                self.assertEqual(render.metric_value(metric), "$0.00")

    def test_compact_amount_labels_keep_units_values_and_distinct_details(self):
        metric = dict(type="balance", name="Available balance (USD)", detail="Available balance",
                      amount=75, percentage=None, unit="USD")
        snapshot = quickshell.build_snapshot([dict(self.data[0], metrics=[metric])], self.selected)
        visible = snapshot["providers"][0]["metrics"][0]
        self.assertEqual(visible["name"], "Available balance")
        self.assertEqual(visible["value"], "$75.00")
        self.assertEqual(visible["detail"], "")
        self.assertEqual(visible["key"], "balance:Available balance (USD)")
        for detail in ("Resets tomorrow", "Project A · us-central1", "Set a management key to see credits"):
            with self.subTest(detail=detail):
                self.assertEqual(render.metric_detail(dict(metric, detail=detail)), detail)

    def test_account_summary_priority_preserves_selection_and_metric_text(self):
        from test_metered_apis import load
        parsed = load("openrouter", "parse").parse(json.dumps({
            "key": {"data": {"usage_monthly": 12, "limit": 100, "limit_remaining": 88, "limit_reset": "monthly"}},
            "credits": {"data": {"total_credits": 100, "total_usage": 25}},
        }))
        entry = dict(self.data[0], metrics=parsed["metrics"])
        snapshot = quickshell.build_snapshot([entry], dict(provider="account:personal", idx=0, icon_mode="off",
                                              metric="credits:Account credit balance (USD)"))
        self.assertEqual([metric["name"] for metric in snapshot["providers"][0]["metrics"]],
                         ["Credit balance", "Key · monthly"])
        self.assertEqual(snapshot["providers"][0]["metrics"][0]["detail"], "$25.00 of $100.00 used (25%)")
        self.assertEqual(snapshot["selected"]["provider"], "account:personal")
        self.assertEqual(snapshot["selected"]["metric"], "credits:Account spend / total credits (USD)")
        choice = dict(provider="account:personal", idx=0, metric=snapshot["selected"]["metric"],
                      icon_mode="off", show_metric=True)
        self.assertIn("Credit balance $75.00", render.get_selected_metric_text([entry], choice))

    @unittest.skipIf(sys.platform == "win32", "Windows configuration uses the tray dialog")
    def test_terminal_choices_use_readable_titles_and_preserve_selection_ids(self):
        from core import tui
        metric = dict(type="credits", name="Credit balance", id="Account spend / total credits (USD)",
                      amount=75, percentage=None, unit="USD")
        with patch.object(state, "load_cache", return_value=[dict(self.data[0], metrics=[metric])]):
            options = tui.get_selectable_items()
        self.assertEqual(options[0]["metric"], "credits:Account spend / total credits (USD)")
        self.assertEqual(options[0]["label"], "OpenRouter · Personal · Credit balance")

    @unittest.skipIf(sys.platform == "win32", "Windows configuration uses the tray dialog")
    def test_terminal_choices_skip_failed_and_unusable_observations(self):
        from core import tui
        failed = dict(self.data[0], _error="Authentication failed", metrics=[
            dict(type="generic", percentage=0, detail="Authentication failed")])
        available = dict(self.data[1], metrics=self.data[1]["metrics"] + [
            dict(type="credits", name="Unavailable balance", percentage=None),
            dict(type="monthly", name="Invalid usage", percentage=float("nan"))])
        with patch.object(state, "load_cache", return_value=[failed, available]):
            options = tui.get_selectable_items()
        self.assertEqual([(item["provider"], item["metric"]) for item in options],
                         [("account:work", "balance:Available balance")])

    def test_monetary_values_keep_their_scope_and_have_no_invented_progress(self):
        values = [dict(type="balance", name=name, percentage=None, amount=amount, unit=unit)
                  for name, amount, unit in (("Balance", 20.5, "USD"), ("Granted", 2, "USD"),
                                             ("Purchased", 18.5, "USD"))]
        entry = dict(self.data[0], metrics=values)
        snapshot = quickshell.build_snapshot([entry], self.selected)
        metrics = snapshot["providers"][0]["metrics"]
        self.assertTrue(all(metric["isAmount"] and not metric["hasPercentage"] for metric in metrics))
        self.assertEqual([metric["value"] for metric in metrics], ["$20.50", "$2.00", "$18.50"])
        quota = dict(type="monthly", percentage=25, amount=5, limit=20, unit="USD")
        self.assertFalse(render.metric_is_amount(quota))
        for invalid in (None, True, "unavailable", float("inf"), float("nan")):
            self.assertFalse(render.metric_is_amount(dict(amount=invalid, percentage=None)))
        self.assertEqual(render.metric_detail(dict(values[0], detail=None)), "")
        self.assertIn("Resets in", render.metric_detail(dict(values[0], detail=None, reset_in_seconds=3600)))

    def test_shorter_amount_title_preserves_selection_identity_and_period(self):
        from core import extra_providers
        metric = extra_providers.parse("lyceum", {"available_credits": 3.5, "used_credits": 2})["metrics"][1]
        original = dict(metric)
        original.pop("title")
        original["detail"] = "Credits used (reported period)"
        self.assertEqual(render.metric_key(metric), render.metric_key(original))
        self.assertEqual(render.metric_title(metric), "Credits used")
        self.assertEqual(render.metric_detail(metric), "Reported period")
        self.assertEqual(render.metric_value(metric), "$2.00")


if __name__ == "__main__":
    unittest.main()
