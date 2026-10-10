"""Connection identity and amount presentation across desktop adapters."""
import json
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
