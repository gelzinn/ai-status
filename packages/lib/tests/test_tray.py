import sys
import time
from pathlib import Path
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
        self.dashboard.animation.stop()
        self.addCleanup(self.dashboard.tray.hide)
        self.addCleanup(self.dashboard.deleteLater)

    def test_incremental_dashboard_selection_and_cache_warning(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "_dir": "codex", "_idx": 0,
            "_cached": True, "_error": "Session expired", "metrics": [
                {"type": "rolling", "percentage": 120}, {"type": "weekly", "percentage": 10},
            ]}])
        self.assertEqual(len(self.dashboard.metric_values), 2)
        self.dashboard.metric_buttons[1].click()
        self.assertEqual(state.load_selected()["metric"], "weekly")
        self.assertIn("10%", self.dashboard.tray.toolTip())
        self.assertIn("cached", self.dashboard.tray.toolTip())
        labels = [item.text() for item in self.dashboard.scroll.widget().findChildren(QLabel)]
        self.assertTrue(any("Cached data" in text for text in labels))

    def test_failed_provider_is_hidden_from_usage_panel(self):
        self.dashboard.on_error("copilot", "<b>Sign in</b>")
        labels = self.dashboard.scroll.widget().findChildren(QLabel)
        self.assertFalse(any("Sign in" in label.text() or "copilot" in label.text().lower() for label in labels))
        self.assertEqual(self.dashboard.errors["copilot"], "<b>Sign in</b>")
        self.assertFalse(self.dashboard.metric_values)

    def test_no_providers_does_not_show_old_cache(self):
        config.save_config([])
        self.dashboard.draw()
        self.assertEqual(len(self.dashboard.metric_values), 0)
        self.assertIn("No usage", self.dashboard.tray.toolTip())

    def test_compact_panel_has_square_actions_and_project_identity(self):
        self.assertEqual(self.dashboard.menu_button.width(), self.dashboard.menu_button.height())
        self.assertFalse(self.dashboard.windowIcon().isNull())
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)",
            "metrics": [{"type": "weekly", "percentage": 23}]}])
        self.assertLess(self.dashboard.height(), 300)
        self.assertTrue(self.dashboard.windowFlags() & tray.Qt.WindowType.FramelessWindowHint)
        labels = [label.text() for label in self.dashboard.scroll.widget().findChildren(QLabel)]
        self.assertIn("[", labels)
        self.assertIn("]", labels)
        self.assertIn("•", labels)
        self.assertIn("→", labels)

    def test_all_bundled_provider_logos_have_visible_pixels(self):
        for name in config.available_providers():
            self.assertTrue(tray.icon_has_pixels(tray.provider_icon(name)), name)

    def test_provider_settings_save_disabled_providers(self):
        settings = tray.ProviderSettings(self.dashboard)
        self.addCleanup(settings.deleteLater)
        for i in range(settings.providers.count()):
            settings.providers.item(i).setCheckState(tray.Qt.CheckState.Unchecked)
        with patch.object(paths, "IS_WINDOWS", False):
            settings.save()
        self.assertEqual(config.enabled_order(), [])

    def test_settings_display_names_preserve_ids_and_reordering(self):
        config.save_config(["zai", "commandcode", "claude"])
        settings = tray.ProviderSettings(self.dashboard)
        self.addCleanup(settings.deleteLater)
        self.assertEqual([settings.providers.item(i).text() for i in range(3)],
                         ["Z.AI", "Command Code", "Claude"])
        item = settings.providers.takeItem(2)
        settings.providers.insertItem(0, item)
        with patch.object(paths, "IS_WINDOWS", False):
            settings.save()
        self.assertEqual(config.enabled_order(), ["claude", "zai", "commandcode"])

    def test_clicking_provider_and_cycling_metrics_updates_tray_logo(self):
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "_idx": 0,
            "metrics": [{"type": "weekly", "percentage": 23}]}])
        self.dashboard.on_result("copilot", [{"provider": "Copilot", "_idx": 0,
            "metrics": [{"type": "monthly", "percentage": 7}]}])
        codex_icon = self.dashboard.tray.icon().pixmap(32, 32).toImage()
        self.dashboard.provider_buttons[("copilot", 0)].click()
        self.assertEqual(self.dashboard.tray.toolTip(), "Copilot 7%")
        self.assertNotEqual(codex_icon, self.dashboard.tray.icon().pixmap(32, 32).toImage())
        self.dashboard.cycle_metric(1)
        self.assertEqual(self.dashboard.tray.toolTip(), "Codex (Pro) 23%")
        self.assertEqual(state.load_selected()["provider"], "codex")

    def test_failed_selected_provider_falls_back_to_available_data(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "metrics": [{"type": "rolling", "percentage": 20}]}])
        self.dashboard.on_result("copilot", [{"provider": "Copilot", "metrics": [{"type": "monthly", "percentage": 7}]}])
        self.dashboard.on_error("codex", "Session expired")
        self.dashboard.on_result("codex", None)
        self.assertEqual(self.dashboard.selected["provider"], "copilot")
        self.assertEqual(len(self.dashboard.metric_values), 1)
        self.assertEqual(self.dashboard.tray.toolTip(), "Copilot 7%")

    def test_activation_file_opens_existing_app_without_qt_network(self):
        paths.atomic_json(paths.RUNTIME_DIR / "desktop-request.json", {"action": "config", "id": "new"})
        with patch.object(self.dashboard, "configure") as configure:
            self.dashboard.poll_state()
            self.dashboard.poll_state()
        configure.assert_called_once()

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
        self.assertFalse(Path(state.LOCK_FILE).exists())
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
        from core import console, windows_console
        process = MagicMock()
        process.read.side_effect = ["Welcome to the Antigravity CLI\n>",
            "GEMINI MODELS\nWeekly Limit\n[=====]\n80%\nQuota available\n"]
        with patch.object(windows_console.PtyProcess, "spawn", return_value=process), patch.object(console, "cli_path", return_value="agy.exe"), patch.object(console.time, "monotonic", side_effect=[0, 1, 2, 3, 4]):
            raw = console.query_antigravity()
        self.assertIn("Weekly Limit", raw)
        process.write.assert_called_once_with("/usage\r")
        process.close.assert_called_once_with(force=True)

    def test_timeout_cleans_up_native_console(self):
        from core import console, windows_console
        from core.provider_http import QueryError
        process = MagicMock()
        with patch.object(windows_console.PtyProcess, "spawn", return_value=process), patch.object(console, "cli_path", return_value="agy.exe"), patch.object(console.time, "monotonic", side_effect=[0, 16]):
            with self.assertRaises(QueryError):
                console.query_antigravity()
        process.close.assert_called_once_with(force=True)


@unittest.skipUnless(sys.platform == "win32", "Requires the real Windows ConPTY APIs")
class NativeConsoleTests(IsolatedState):
    def collect(self, proc, marker):
        result = ""
        deadline = time.monotonic() + 8
        while marker not in result and time.monotonic() < deadline:
            try:
                result += proc.read(timeout=0.2)
            except TimeoutError:
                continue
            except EOFError:
                break
        self.assertIn(marker, result)
        return result

    def test_real_console_unicode_input_output_and_cleanup(self):
        from core.windows_console import PtyProcess
        proc = PtyProcess.spawn([sys.executable, "-u", "-c",
            "print('READY', flush=True); text=input(); print('READ:'+text, flush=True)"])
        try:
            self.collect(proc, "READY")
            proc.write("é café\r")
            self.collect(proc, "READ:é café")
        finally:
            proc.close(force=True)
        self.assertFalse(proc.reader.is_alive())
        self.assertFalse(proc.isalive())
        proc.close(force=True)

    def test_cmd_launcher_with_unicode_and_spaces(self):
        from core.windows_console import PtyProcess
        script = self.root / "provider helper.cmd"
        script.write_text("@echo off\r\necho ai-status-wrapper-ok\r\n", encoding="utf-8")
        proc = PtyProcess.spawn([str(script)])
        try:
            self.collect(proc, "ai-status-wrapper-ok")
        finally:
            proc.close(force=True)
        self.assertFalse(proc.reader.is_alive())

    def test_failed_spawn_closes_console_and_reader(self):
        from core.windows_console import PtyProcess
        before = {thread.ident for thread in __import__("threading").enumerate()}
        with self.assertRaises(OSError):
            PtyProcess.spawn([str(self.root / "missing.exe")])
        self.assertEqual({thread.ident for thread in __import__("threading").enumerate()}, before)


if __name__ == "__main__":
    unittest.main()
