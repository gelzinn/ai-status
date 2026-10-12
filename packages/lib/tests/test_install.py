"""Exercise real installer files with isolated homes and fake desktop commands."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
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
        self.install("--bar", "quickshell", "--configure-bar", "true", "--show-pct", "false", "--icon-mode", "off",
                     "--usage-display", "remaining")
        self.log.write_text("")
        self.install("--bar", "quickshell", "--configure-bar", "true")
        self.assertIn(f"omarchy plugin update {PLUGIN_ID} --yes", self.commands())
        self.assertNotIn("plugin add", self.commands())
        prefs = json.loads((self.home / ".config/ai-status/selected.json").read_text())
        self.assertFalse(prefs["show_pct"])
        self.assertEqual(prefs["icon_mode"], "off")
        self.assertEqual(prefs["usage_display"], "remaining")

    def test_usage_display_defaults_to_used_and_explicit_flag_overrides_saved_mode(self):
        self.install("--bar", "waybar", "--configure-bar", "false")
        path = self.home / ".config/ai-status/selected.json"
        self.assertEqual(json.loads(path.read_text())["usage_display"], "used")
        prefs = {**json.loads(path.read_text()), "provider": "codex", "metric": "weekly", "custom": "keep"}
        path.write_text(json.dumps(prefs))
        self.install("--bar", "waybar", "--configure-bar", "false", "--usage-display", "remaining")
        self.assertEqual(json.loads(path.read_text()), {**prefs, "usage_display": "remaining"})
        self.install("--bar", "waybar", "--configure-bar", "false", "--usage-display", "used")
        self.assertEqual(json.loads(path.read_text()), {**prefs, "usage_display": "used"})

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
        for flags in (("--bar", "quickshell", "--configure-waybar", "true"), ("--bar", "unknown"),
                      ("--configure-bar", "invalid"), ("--show-pct", "invalid"), ("--bar",),
                      ("--usage-display", "invalid"), ("--usage-display",), ("--usage-display", "")):
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


@unittest.skipIf(sys.platform == "win32", "The installer wizard requires a controlling terminal")
class InstallerWizardTests(unittest.TestCase):
    def wizard(self, keys, default="used"):
        import fcntl
        import pty
        import select
        import termios

        temporary = tempfile.TemporaryDirectory(prefix="ai-status-wizard-")
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "preferences.json"
        master, slave = pty.openpty()

        def attach_terminal():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

        process = subprocess.Popen([sys.executable, str(LIB / "install-wizard.py"), str(output), "waybar", "true", default],
                                   stdin=slave, stdout=slave, stderr=slave, preexec_fn=attach_terminal)
        os.close(slave)
        transcript = b""
        sent = False
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master], [], [], 0.1)
                if readable:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    transcript += chunk
                    if not sent and b"Show the provider logo" in transcript:
                        os.write(master, keys)
                        sent = True
                if process.poll() is not None:
                    break
            process.wait(timeout=1)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        return process.returncode, transcript.decode(), json.loads(output.read_text()) if output.exists() else None

    def test_wizard_offers_used_and_remaining_and_accepts_arrow_selection(self):
        code, transcript, result = self.wizard(b"\r" * 5 + b"\x1b[C\r\r")
        self.assertEqual(code, 0, transcript)
        self.assertIn("Show quota as", transcript)
        self.assertIn("Used", transcript)
        self.assertIn("Remaining", transcript)
        self.assertEqual(result["USAGE_DISPLAY"], "remaining")

    def test_wizard_used_default_and_remaining_preference(self):
        for mode in ("used", "remaining"):
            with self.subTest(mode=mode):
                code, transcript, result = self.wizard(b"\r" * 7, default=mode)
                self.assertEqual(code, 0, transcript)
                self.assertEqual(result["USAGE_DISPLAY"], mode)

    def test_cancel_during_usage_display_does_not_publish_preferences(self):
        code, transcript, result = self.wizard(b"\r" * 5 + b"\x1b[C\x03")
        self.assertEqual(code, 1, transcript)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
