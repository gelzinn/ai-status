"""SwiftBar compatibility preserves native model rules and safe menu syntax."""

from pathlib import Path
import shlex
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import config, swiftbar


class SwiftBarCompatibilityTests(unittest.TestCase):
    def setUp(self):
        enabled = patch.object(config, "enabled_order", return_value=["codex", "claude"])
        enabled.start()
        self.addCleanup(enabled.stop)
        self.selected = {"provider": "claude", "idx": 0, "metric": "rolling", "icon_mode": "off"}
        self.data = [
            {"_dir": "claude", "_idx": 0, "provider": "Claude", "metrics": [
                {"type": "rolling", "percentage": 25, "reset_in_seconds": 3600}]},
            {"_dir": "codex", "_idx": 1, "provider": "Codex", "_cached": True,
             "_error": "<span>Temporarily unavailable</span>", "metrics": [
                 {"type": "weekly", "percentage": 40, "detail": "<b>Weekly</b> resets tomorrow"}]},
        ]

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
