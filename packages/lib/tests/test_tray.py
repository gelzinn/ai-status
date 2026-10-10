import sys
import types
import time
import unittest
from unittest.mock import MagicMock, patch

from test_portability import IsolatedState
from core import config, paths, state

try:
    from PySide6.QtWidgets import QApplication, QLabel
    from core import tray
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "Install windows/requirements.txt to test the desktop adapter")
class DesktopTests(IsolatedState):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        config.save_config(["codex", "copilot"])
        with patch.object(tray.QTimer, "singleShot"), patch.object(tray.QSystemTrayIcon, "show"):
            self.dashboard = tray.Dashboard(self.app)
        self.dashboard.poll.stop()
        self.dashboard.auto_refresh.stop()
        self.addCleanup(self.dashboard.tray.hide)
        self.addCleanup(self.dashboard.deleteLater)

    def test_incremental_dashboard_selection_and_cache_warning(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "_dir": "codex", "_idx": 0,
            "_cached": True, "_error": "Session expired", "metrics": [
                {"type": "rolling", "percentage": 120}, {"type": "weekly", "percentage": 10},
            ]}])
        self.assertEqual(self.dashboard.active.count(), 2)
        self.dashboard.active.setCurrentIndex(1)
        self.assertEqual(state.load_selected()["metric"], "weekly")
        self.assertIn("10%", self.dashboard.tray.toolTip())
        labels = [item.text() for item in self.dashboard.scroll.widget().findChildren(QLabel)]
        self.assertTrue(any("Cached data" in text for text in labels))

    def test_failed_provider_is_visible_and_plain_text(self):
        self.dashboard.on_error("copilot", "<b>Sign in</b>")
        labels = self.dashboard.scroll.widget().findChildren(QLabel)
        label = next(item for item in labels if "Sign in" in item.text())
        self.assertEqual(label.textFormat(), tray.Qt.TextFormat.PlainText)

    def test_no_providers_does_not_show_old_cache(self):
        config.save_config([])
        self.dashboard.draw()
        self.assertEqual(self.dashboard.active.count(), 0)
        self.assertIn("No usage", self.dashboard.tray.toolTip())

    def test_provider_settings_save_disabled_providers(self):
        settings = tray.ProviderSettings(self.dashboard)
        self.addCleanup(settings.deleteLater)
        for i in range(settings.providers.count()):
            settings.providers.item(i).setCheckState(tray.Qt.CheckState.Unchecked)
        with patch.object(paths, "IS_WINDOWS", False):
            settings.save()
        self.assertEqual(config.enabled_order(), [])

    def test_overlapping_refresh_is_queued(self):
        self.dashboard.busy = True
        with patch.object(state, "acquire_lock") as lock:
            self.dashboard.refresh()
        self.assertTrue(self.dashboard.queued)
        lock.assert_not_called()

    def test_refresh_worker_delivers_results_and_releases_lock(self):
        from core import fetch
        def collect(on_result=None, on_error=None):
            data = [{"provider": "Codex", "_dir": "codex", "_idx": 0,
                     "metrics": [{"type": "rolling", "percentage": 42}]}]
            on_result("codex", data)
            return data
        with patch.object(fetch, "fetch_all_data", side_effect=collect), patch.object(fetch, "check_for_updates"):
            self.dashboard.refresh()
            deadline = time.monotonic() + 5
            while self.dashboard.busy and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
        self.assertFalse(self.dashboard.busy)
        self.assertFalse(paths.Path(state.LOCK_FILE).exists())
        self.assertIn("42%", self.dashboard.tray.toolTip())
        self.assertEqual(state.load_selected()["provider"], "codex")

    def test_exit_waits_for_worker(self):
        app = MagicMock()
        self.dashboard.app = app
        self.dashboard.busy = True
        self.dashboard.request_exit()
        app.quit.assert_not_called()
        self.dashboard.worker = MagicMock()
        self.dashboard.on_finished([])
        app.quit.assert_called_once()

    def test_windows_startup_quotes_packaged_executable(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = 1
        registry.REG_SZ = 1
        with patch.dict(sys.modules, {"winreg": registry}), patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(self.root / "ai-status-cli.exe")):
            tray.set_startup(True)
        command = registry.SetValueEx.call_args.args[-1]
        self.assertTrue(command.startswith('"'))
        self.assertIn("ai-status.exe", command)
        self.assertTrue(command.endswith(" tray"))


class ConPTYTests(unittest.TestCase):
    def test_windows_console_reads_usage_and_closes_process(self):
        from core import console
        process = MagicMock()
        process.read.side_effect = ["Welcome to the Antigravity CLI\n>",
            "GEMINI MODELS\nWeekly Limit\n[=====]\n80%\nQuota available\n"]
        winpty = types.SimpleNamespace(Backend=types.SimpleNamespace(ConPTY=1), PtyProcess=MagicMock())
        winpty.PtyProcess.spawn.return_value = process
        with patch.dict(sys.modules, {"winpty": winpty}), patch.object(console, "cli_path", return_value="agy.exe"), patch.object(console.select, "select", return_value=([1], [], [])), patch.object(console.time, "monotonic", side_effect=[0, 1, 2, 3, 4]):
            raw = console.query_antigravity()
        self.assertIn("Weekly Limit", raw)
        process.write.assert_called_once_with("/usage\r")
        process.close.assert_called_once_with(force=True)

    def test_timeout_cleans_up_native_console(self):
        from core import console
        from core.provider_http import QueryError
        process = MagicMock()
        winpty = types.SimpleNamespace(Backend=types.SimpleNamespace(ConPTY=1), PtyProcess=MagicMock())
        winpty.PtyProcess.spawn.return_value = process
        with patch.dict(sys.modules, {"winpty": winpty}), patch.object(console, "cli_path", return_value="agy.exe"), patch.object(console.time, "monotonic", side_effect=[0, 16]):
            with self.assertRaises(QueryError):
                console.query_antigravity()
        process.close.assert_called_once_with(force=True)


if __name__ == "__main__":
    unittest.main()
