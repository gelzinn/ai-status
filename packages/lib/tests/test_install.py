"""Exercise real installer files with isolated homes and fake desktop commands."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1]
PLUGIN_ID = "io.github.gelzinn.ai-status"


@unittest.skipIf(sys.platform == "win32", "Requires Linux shell integration")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ai-status-test-' ")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.bin = self.home / "fake-bin"
        self.bin.mkdir()
        self.log = self.home / "commands"
        self.env = dict(os.environ, HOME=str(self.home), PATH=f"{self.bin}:{os.environ['PATH']}", AI_STATUS_TEST_LOG=str(self.log), AI_STATUS_TEST_HOME=str(self.home), AI_STATUS_TEST_SHELL="0", AI_STATUS_TEST_WAYBAR="0")
        self.stub("omarchy-shell", 'echo "shell $*" >> "$AI_STATUS_TEST_LOG"\nexit "$AI_STATUS_TEST_SHELL"')
        self.stub("qs", "exit 0")
        self.stub("waybar", 'echo "waybar $*" >> "$AI_STATUS_TEST_LOG"')
        self.stub("pkill", 'echo "pkill $*" >> "$AI_STATUS_TEST_LOG"')
        self.stub("pgrep", 'if [ "$2" = waybar ]; then exit "$AI_STATUS_TEST_WAYBAR"; fi\nexit 1')
        self.stub("omarchy", '''echo "omarchy $*" >> "$AI_STATUS_TEST_LOG"
case "$2" in
  add) mkdir -p "$AI_STATUS_TEST_HOME/.config/omarchy/plugins/io.github.gelzinn.ai-status/.git" ;;
esac
exit "${AI_STATUS_TEST_PLUGIN_FAILURE:-0}"''')
        self.waybar_config = self.home / ".config/waybar/config.jsonc"
        self.waybar_config.parent.mkdir(parents=True)
        self.original_waybar = '{"modules-right": ["clock"], "clock": {"format": "https://example.com"}}\n'
        self.waybar_config.write_text(self.original_waybar)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body + "\n")
        path.chmod(0o755)

    def install(self, *flags, success=True):
        result = subprocess.run(["bash", str(LIB / "install.sh"), "--no-interactive", "--skip-check", *flags], env=self.env, capture_output=True, text=True, timeout=20)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def commands(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_quickshell_leaves_waybar_intact_and_uses_native_install(self):
        self.install("--bar", "quickshell", "--configure-bar", "true")
        self.assertEqual(self.waybar_config.read_text(), self.original_waybar)
        self.assertFalse(Path(str(self.waybar_config) + ".ai-status.bak").exists())
        self.assertIn("omarchy plugin add", self.commands())
        self.assertIn(f"omarchy plugin enable {PLUGIN_ID}", self.commands())
        self.assertNotIn("pkill", self.commands())
        self.assertNotIn("waybar ", self.commands())
        self.assertTrue((self.home / ".local/bin/ai-status").is_symlink())

    def test_repeated_quickshell_install_updates_only_ai_status_and_keeps_preferences(self):
        self.install("--bar", "quickshell", "--configure-bar", "true", "--show-pct", "false", "--icon-mode", "off")
        self.log.write_text("")
        self.install("--bar", "quickshell", "--configure-bar", "true")
        self.assertIn(f"omarchy plugin update {PLUGIN_ID} --yes", self.commands())
        self.assertNotIn("plugin add", self.commands())
        prefs = json.loads((self.home / ".config/ai-status/selected.json").read_text())
        self.assertFalse(prefs["show_pct"])
        self.assertEqual(prefs["icon_mode"], "off")

    def test_legacy_flag_selects_waybar_and_preserves_omarchy_configuration(self):
        shell_config = self.home / ".config/omarchy/shell.json"
        shell_config.parent.mkdir(parents=True)
        shell_config.write_text('{"version": 1, "bar": {"layout": {"right": [{"id": "omarchy.clock"}]}}}')
        original_shell = shell_config.read_text()
        self.install("--configure-waybar", "true")
        configured = json.loads(self.waybar_config.read_text())
        self.assertIn("custom/ai-status", configured["modules-right"])
        self.assertEqual(configured["clock"]["format"], "https://example.com")
        self.assertEqual(Path(str(self.waybar_config) + ".ai-status.bak").read_text(), self.original_waybar)
        self.assertEqual(shell_config.read_text(), original_shell)
        self.assertNotIn("omarchy plugin", self.commands())

    def test_auto_prefers_active_omarchy_shell(self):
        self.install("--configure-bar", "true")
        self.assertIn("omarchy plugin add", self.commands())
        self.assertEqual(self.waybar_config.read_text(), self.original_waybar)

    def test_auto_uses_active_waybar_when_shell_is_offline(self):
        self.env["AI_STATUS_TEST_SHELL"] = "1"
        self.install("--configure-bar", "true")
        self.assertIn("custom/ai-status", json.loads(self.waybar_config.read_text()))
        self.assertNotIn("omarchy plugin", self.commands())

    def test_manual_plugin_install_does_not_enable(self):
        self.install("--bar", "quickshell", "--configure-bar", "false")
        self.assertIn("omarchy plugin add", self.commands())
        self.assertNotIn("plugin enable", self.commands())

    def test_conflicting_or_invalid_flags_do_not_install(self):
        for flags in (("--bar", "quickshell", "--configure-waybar", "true"), ("--bar", "unknown"), ("--configure-bar", "invalid"), ("--show-pct", "invalid"), ("--bar",)):
            self.install(*flags, success=False)
            self.assertFalse((self.home / ".local/share/ai-status").exists())
            self.assertEqual(self.waybar_config.read_text(), self.original_waybar)

    def test_existing_unmanaged_plugin_is_not_overwritten(self):
        plugin = self.home / f".config/omarchy/plugins/{PLUGIN_ID}"
        plugin.mkdir(parents=True)
        marker = plugin / "local.qml"
        marker.write_text("custom")
        self.install("--bar", "quickshell", "--configure-bar", "true", success=False)
        self.assertEqual(marker.read_text(), "custom")
        self.assertNotIn("plugin add", self.commands())

    def test_plugin_failure_does_not_report_success_or_change_waybar(self):
        self.env["AI_STATUS_TEST_PLUGIN_FAILURE"] = "1"
        result = self.install("--bar", "quickshell", "--configure-bar", "true", success=False)
        self.assertNotIn("done", result.stdout)
        self.assertEqual(self.waybar_config.read_text(), self.original_waybar)

    def test_quickshell_requirements_do_not_require_waybar(self):
        (self.bin / "waybar").unlink()
        result = subprocess.run(["bash", str(LIB / "check.sh"), "quickshell"], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("SVG rasterizer", result.stdout)


if __name__ == "__main__":
    unittest.main()
