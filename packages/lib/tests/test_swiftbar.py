"""SwiftBar compatibility preserves native model rules and safe menu syntax."""

from pathlib import Path
import base64
import os
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import accounts, cli, config, macos, state, swiftbar


class SwiftBarCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        configuration = patch.object(config, "CONFIG_FILE", str(Path(temporary.name) / "providers.json"))
        configuration.start()
        self.addCleanup(configuration.stop)
        enabled = patch.object(config, "enabled_order", return_value=["codex", "claude"])
        enabled.start()
        self.addCleanup(enabled.stop)
        # Keep Claude logins on this machine out of the saved-account fixtures.
        discovery = patch("core.claude_accounts.discover", return_value=[])
        discovery.start()
        self.addCleanup(discovery.stop)
        self.selected = {"provider": "claude", "idx": 0, "metric": "rolling", "icon_mode": "off"}
        self.data = [
            {"_dir": "claude", "_idx": 0, "provider": "Claude", "metrics": [
                {"type": "rolling", "percentage": 25, "reset_in_seconds": 3600}]},
            {"_dir": "codex", "_idx": 1, "provider": "Codex", "_cached": True,
             "_error": "<span>Temporarily unavailable</span>", "metrics": [
                 {"type": "weekly", "percentage": 40, "detail": "<b>Weekly</b> resets tomorrow"}]},
        ]

    def account_data(self):
        accounts.save_document({"version": 1, "accounts": [
            {"id": "personal", "provider": "openrouter", "label": "Personal"},
            {"id": "work", "provider": "openrouter", "label": "Work"},
        ], "order": ["account:work", "account:personal"]}, config.accounts_file())
        return [dict(provider="OpenRouter", _dir="openrouter", _idx=0,
                     _connection_id="account:" + name, _account_id=name, _account_label=label,
                     metrics=[dict(type="balance", name="Available balance", percentage=None,
                                   amount=amount, unit="USD")])
                for name, label, amount in (("personal", "Personal", 8.25), ("work", "Work", 42.5))]

    def test_accounts_use_independent_selection_and_amounts_without_fake_progress(self):
        data = self.account_data()
        selected = dict(provider="account:work", idx=0, metric="balance:Available balance", icon_mode="off")
        with patch.object(config, "enabled_order", return_value=[]):
            menu = swiftbar.render_menu(data, selected)
        self.assertEqual(menu.splitlines()[0], "OpenRouter · Work $42.50")
        self.assertLess(menu.index("→ OpenRouter · Work"), menu.index("OpenRouter · Personal"))
        self.assertIn("Available balance:  $42.50", menu)
        self.assertIn("Available balance:  $8.25", menu)
        self.assertNotIn("░", menu)
        self.assertNotIn("%", menu)
        actions = [dict(part.split("=", 1) for part in shlex.split(line.rsplit(" | ", 1)[1]))
                   for line in menu.splitlines() if 'param2="swiftbar-select"' in line]
        self.assertEqual({action["param3"] for action in actions}, {"account:work", "account:personal"})
        self.assertTrue(any(action.get("checked") == "true" and action["param3"] == "account:work" for action in actions))

    def test_account_logos_and_refresh_pending_use_provider_and_connection_ids(self):
        data = self.account_data()
        selected = dict(provider="account:work", idx=0, metric="balance:Available balance", icon_mode="logo")
        logo = macos.LogoCache().get("openrouter")
        with patch.object(config, "enabled_order", return_value=[]), \
                patch.object(macos.LogoCache, "get", return_value=logo) as get:
            snapshot = swiftbar._snapshot(data, selected, spinner="⠋")
            menu = swiftbar.render_menu(data, selected, spinner="⠋")
        self.assertEqual({call.args[0] for call in get.call_args_list}, {"openrouter"})
        self.assertTrue(all(provider["loading"] for provider in snapshot["providers"]))
        self.assertEqual(snapshot["logoPath"], logo)
        self.assertIn("⠋", menu.splitlines()[0])
        encoded = menu.splitlines()[0].split("image=", 1)[1]
        self.assertEqual(base64.b64decode(encoded), Path(logo).read_bytes())

    def test_amount_ratio_retains_real_progress_and_shared_display_value(self):
        data = self.account_data()
        metric = dict(type="credits", name="Account spend / total credits", percentage=25,
                      amount=25, limit=100, unit="USD", value_format="amount_ratio")
        data[1]["metrics"] = [metric]
        selected = dict(provider="account:work", idx=0, metric="credits:Account spend / total credits", icon_mode="off")
        with patch.object(config, "enabled_order", return_value=[]):
            menu = swiftbar.render_menu(data, selected)
        self.assertIn("$25.00 / $100.00", menu)
        self.assertIn("████░░░░░░░░░░░░", menu)
        self.assertNotIn("25%", menu)

    def test_text_only_allowance_is_selectable_without_percentage(self):
        data = self.account_data()
        data[1]["metrics"] = [dict(type="monthly", percentage=None, value="Unlimited", detail="Included usage")]
        selected = dict(provider="account:work", idx=0, metric="monthly", icon_mode="off")
        with patch.object(config, "enabled_order", return_value=[]):
            menu = swiftbar.render_menu(data, selected)
        self.assertIn("Monthly Usage:  Unlimited", menu)
        self.assertIn("Included usage", menu)
        self.assertNotIn("░", menu)
        self.assertNotIn("%", menu)

    def test_account_changes_invalidate_the_stream_without_changing_provider_config(self):
        self.account_data()
        before = cli._swiftbar_sig()
        path = config.accounts_file()
        stat = os.stat(path)
        os.utime(path, (stat.st_atime, stat.st_mtime + 2))
        self.assertNotEqual(cli._swiftbar_sig(), before)

    def test_cycle_legacy_account_selection_uses_new_summary_priority(self):
        data = self.account_data()
        data[1]["metrics"] = [
            dict(type="monthly", name="Key usage", percentage=10, display_order=10),
            dict(type="credits", name="Account credits", amount=25, percentage=None, unit="USD", display_order=-10),
        ]
        selected = dict(provider="account:work", idx=0, metric="credits:Old credit label")
        with patch.object(state, "load_cache", return_value=data), \
                patch.object(state, "load_selected", return_value=selected), patch.object(state, "save_selected") as save:
            cli.cycle_metric("swiftbar")
        self.assertEqual(save.call_args.args[0]["metric"], "credits:Account credits")

    def test_menu_follows_enabled_order_and_excludes_disabled_cache(self):
        data = self.data + [{"_dir": "zai", "_idx": 0, "provider": "Disabled ZAI",
                             "metrics": [{"type": "rolling", "percentage": 90}]}]
        menu = swiftbar.render_menu(data, self.selected)
        dropdown = menu.split("\n---\n", 1)[1]
        self.assertLess(dropdown.index("Codex"), dropdown.index("Claude"))
        self.assertNotIn("Disabled ZAI", menu)
        self.assertIn("checked=true", menu)

    def test_failed_and_invalid_usage_do_not_show_fake_zero_or_crash(self):
        failed = {"_dir": "claude", "_idx": 0, "provider": "Failed Claude", "metrics": [
            {"type": "generic", "percentage": 0, "detail": "Authentication failed"}]}
        nonfinite = {"_dir": "claude", "_idx": 2, "provider": "Invalid Claude", "metrics": [
            {"type": "rolling", "percentage": float("nan")},
            {"type": "weekly", "percentage": float("inf")},
            {"type": "monthly", "percentage": "invalid"}]}
        menu = swiftbar.render_menu([failed, nonfinite, self.data[1]], self.selected)
        self.assertIn("Codex 40%", menu.splitlines()[0])
        self.assertNotIn("Failed Claude", menu)
        self.assertNotIn("Invalid Claude", menu)
        self.assertNotIn("nan%", menu)
        self.assertNotIn("Authentication failed", menu)

    def test_menu_strips_markup_and_cannot_create_lines_from_provider_text(self):
        data = [dict(self.data[0], provider="Claude\nInjected | bash=/tmp/unwanted",
                     metrics=[{"type": "rolling", "percentage": 25,
                               "detail": "<b>Resets tomorrow</b>\nInjected | bash=/tmp/unwanted"}]), self.data[1]]
        menu = swiftbar.render_menu(data, self.selected)
        self.assertNotIn("<span", menu)
        self.assertNotIn("<b>", menu)
        self.assertNotIn("\nInjected", menu)
        self.assertNotIn(" | bash=/tmp/unwanted", menu)
        self.assertIn("Temporarily unavailable", menu)
        self.assertIn("Resets tomorrow", menu)

    def test_all_command_paths_and_metric_keys_survive_spaces_and_quotes(self):
        executable = '/tmp/AI Status é/bin/ai-status'
        detail = 'Fable "preview" · resets tomorrow'
        data = [dict(self.data[0], metrics=[{"type": "weekly", "percentage": 25, "detail": detail}])]
        selected = dict(self.selected, metric='weekly:Fable "preview"')
        with patch.object(swiftbar, "binary_path", return_value=executable):
            menu = swiftbar.render_menu(data, selected)
        actions = []
        for line in menu.splitlines():
            if "bash=" in line and " | " in line:
                parameters = dict(part.split("=", 1) for part in shlex.split(line.rsplit(" | ", 1)[1]))
                actions.append(parameters)
                self.assertEqual(parameters["bash"], sys.executable)
                self.assertEqual(parameters["param1"], executable)
        self.assertTrue(actions)
        metric = next(action for action in actions if "param5" in action)
        self.assertEqual(metric["param5"], 'weekly:Fable "preview"')

    def test_reset_credit_details_are_available_without_redemption_actions(self):
        data = [dict(self.data[0], reset_credits={"available": 2, "credits": [
            {"title": "Promo reset", "count": 1, "expires_at": "2100-01-01T00:00:00Z",
             "id": "redemption-secret"}]})]
        menu = swiftbar.render_menu(data, self.selected)
        self.assertIn("Reset credits", menu)
        self.assertIn("Promo reset", menu)
        self.assertNotIn("redemption-secret", menu)
        self.assertNotIn("param1=redeem", menu)


if __name__ == "__main__":
    unittest.main()
