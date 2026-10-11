"""Update detection, platform preservation and verified installer handoffs."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import cli, fetch, paths, updates


class VersionDetectionTests(unittest.TestCase):
    def test_update_requires_a_newer_stable_semver(self):
        for latest, current, expected in (
            ("0.12.1", "0.11.0", True), ("0.10.0", "0.9.9", True),
            ("0.12.1", "0.12.1", False), ("0.11.0", "0.12.1", False),
            ("1.0.0", "0.99.99", True), ("main", "0.12.1", False),
            ("0.13.0-beta.1", "0.12.1", False), (None, "0.12.1", False),
            ("0.13.0", "invalid", False), ("00.13.0", "0.12.1", False),
        ):
            with self.subTest(latest=latest, current=current):
                with patch.object(fetch, "_latest_version", latest), patch.object(fetch, "__version__", current):
                    self.assertEqual(fetch.get_version_info()["has_update"], expected)

    def test_releases_api_drafts_prereleases_and_malformed_tags_are_excluded(self):
        releases = [{"tag_name": "v0.13.0", "draft": True}, {"tag_name": "v0.13.0", "prerelease": True},
                    {"tag_name": "v0.13.0-beta.1"}, {"tag_name": "main"}, {"tag_name": 123}, []]
        for release in releases:
            with self.subTest(release=release), patch.object(fetch, "request", return_value=json.dumps(release)), \
                    patch.object(fetch, "_latest_version", None):
                self.assertIsNone(fetch.check_for_updates())
                self.assertFalse(fetch.get_version_info()["has_update"])
        with patch.object(fetch, "request", return_value=json.dumps({"tag_name": "v0.13.0"})), \
                patch.object(fetch, "_latest_version", None):
            self.assertEqual(fetch.check_for_updates(), "0.13.0")


class UpdateGuideTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ai-status-updates-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        for item in (
            patch.object(Path, "home", return_value=self.home),
            patch.object(paths, "IS_WINDOWS", False),
            patch.object(paths, "CACHE_DIR", self.home / "cache"),
            patch.object(fetch, "_latest_version", "0.13.0"),
        ):
            item.start()
            self.addCleanup(item.stop)

    def managed_lib(self):
        lib = self.home / ".local/share/ai-status/packages/lib"
        lib.mkdir(parents=True)
        return lib

    def test_native_macos_uses_real_route_preserves_mode_and_disabled_autostart(self):
        lib = self.managed_lib()
        app = self.home / ".local/share/ai-status/AI Status.app/Contents/MacOS/AIStatus"
        app.parent.mkdir(parents=True)
        app.touch()
        app_link = self.home / "Applications/AI Status.app"
        app_link.parent.mkdir()
        app_link.symlink_to(app.parents[2])
        with patch.object(paths, "LIB_DIR", lib), patch.object(sys, "platform", "darwin"):
            guide = updates.update_guide()
        self.assertEqual(guide["method"], "macos-installer")
        self.assertTrue(guide["canUpdate"])
        self.assertIn("https://ai-status.gelzin.com/install/macos", guide["command"])
        self.assertIn("--mode native", guide["command"])
        self.assertIn("--version v0.13.0", guide["command"])
        self.assertIn("--no-autostart", guide["command"])
        agent = self.home / "Library/LaunchAgents/com.gelzin.ai-status.plist"
        agent.parent.mkdir(parents=True)
        agent.touch()
        with patch.object(paths, "LIB_DIR", lib), patch.object(sys, "platform", "darwin"):
            self.assertNotIn("--no-autostart", updates.update_guide()["command"])

    def test_swiftbar_custom_plugin_folder_preserves_existing_stream_mode(self):
        lib = self.managed_lib()
        plugins = self.home / "my swiftbar plugins"
        plugins.mkdir()
        (plugins / "ai-status.5s.py").touch()
        preference = self.home / "Library/Preferences/com.ameba.SwiftBar.plist"
        preference.parent.mkdir(parents=True)
        preference.write_bytes(plistlib.dumps({"PluginDirectory": str(plugins)}))
        with patch.object(paths, "LIB_DIR", lib), patch.object(sys, "platform", "darwin"):
            guide = updates.update_guide()
        self.assertTrue(guide["canUpdate"])
        self.assertIn("--mode stream", guide["command"])

    def test_omarchy_install_uses_plugin_manager_and_general_install_preserves_bar(self):
        plugin = self.home / ".config/omarchy/plugins" / updates.PLUGIN_ID
        plugin_lib = plugin / "packages/lib"
        plugin_lib.mkdir(parents=True)
        with patch.object(paths, "LIB_DIR", plugin_lib), patch.object(sys, "platform", "linux"), \
                patch.object(updates.shutil, "which", return_value="/usr/bin/omarchy"):
            guide = updates.update_guide()
        self.assertEqual(guide["method"], "omarchy")
        self.assertEqual(guide["command"], "omarchy plugin update " + updates.PLUGIN_ID + " --yes")
        lib = self.managed_lib()
        with patch.object(paths, "LIB_DIR", lib), patch.object(sys, "platform", "linux"):
            self.assertIn("--bar quickshell", updates.update_guide()["command"])

    def test_source_and_portable_guides_never_replace_them_automatically(self):
        with patch.object(paths, "LIB_DIR", self.home / "checkout/packages/lib"), \
                patch.object(sys, "platform", "linux"), patch.object(fetch, "request") as network, \
                patch.object(updates.subprocess, "Popen") as launch:
            guide = updates.update_guide()
        self.assertFalse(guide["canUpdate"])
        network.assert_not_called()
        launch.assert_not_called()
        self.assertFalse((self.home / "cache").exists())
        with patch.object(paths, "IS_WINDOWS", True), patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", str(self.home / "portable/ai-status-cli.exe")):
            guide = updates.update_guide()
        self.assertEqual(guide["method"], "windows-portable")
        self.assertFalse(guide["canUpdate"])
        self.assertIn("AppData", " ".join(guide["steps"]))

    def test_frozen_windows_with_uninstaller_can_open_installer(self):
        directory = self.home / "installed"
        directory.mkdir()
        (directory / "unins000.exe").touch()
        with patch.object(paths, "IS_WINDOWS", True), patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", str(directory / "ai-status-cli.exe")):
            guide = updates.update_guide()
        self.assertEqual(guide["method"], "windows-installer")
        self.assertTrue(guide["canUpdate"])


class UpdateActionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ai-status-update-action-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for item in (
            patch.object(paths, "CACHE_DIR", self.root / "cache"),
            patch.object(fetch, "__version__", "0.12.1"),
            patch.object(fetch, "_latest_version", "0.13.0"),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_update_does_not_downgrade_or_install_after_failed_check(self):
        for latest in ("0.12.1", "0.11.0", None):
            with self.subTest(latest=latest), patch.object(updates, "_installation", return_value=("windows-installer", {})), \
                    patch.object(fetch, "check_for_updates", return_value=latest), \
                    patch.object(updates, "_windows_update") as install:
                if latest is None:
                    with self.assertRaisesRegex(OSError, "Could not check"):
                        updates.run_update()
                else:
                    self.assertIn("already up to date", updates.run_update())
                install.assert_not_called()

    def test_checksum_mismatch_and_missing_checksum_never_launch_installer(self):
        filename = "ai-status-0.13.0-windows-x64-setup.exe"
        for checksum in (("0" * 64 + "  " + filename + "\n").encode(), b"no matching checksum"):
            def download(url, destination):
                destination.write_bytes(b"installer-bytes")
            with self.subTest(checksum=checksum), patch.object(updates, "request_bytes", return_value=checksum), \
                    patch.object(updates, "_download_windows", side_effect=download), \
                    patch.object(updates.subprocess, "Popen") as launch:
                with self.assertRaises(ValueError):
                    updates._windows_update("0.13.0", lambda message: None)
                launch.assert_not_called()
            self.assertFalse(list((self.root / "cache").rglob("*.exe")))

    def test_verified_installer_is_opened_only_after_exact_release_checksum(self):
        payload = b"verified-installer-bytes"
        filename = "ai-status-0.13.0-windows-x64-setup.exe"
        checksum = (hashlib.sha256(payload).hexdigest() + "  " + filename + "\n").encode()
        def download(url, destination):
            self.assertEqual(url, updates.REPOSITORY + "/releases/download/v0.13.0/" + filename)
            destination.write_bytes(payload)
        messages = []
        with patch.object(updates, "request_bytes", return_value=checksum), \
                patch.object(updates, "_download_windows", side_effect=download), \
                patch.object(updates.subprocess, "Popen") as launch:
            result = updates._windows_update("0.13.0", messages.append)
        self.assertIn("installer is open", result)
        self.assertNotIn("successfully installed", result)
        installer = Path(launch.call_args.args[0][0])
        self.assertEqual(installer.read_bytes(), payload)
        self.assertIn("Verifying the installer…", messages)

    def test_macos_terminal_reports_failed_handoff_and_does_not_claim_success(self):
        with patch.object(sys, "platform", "darwin"), \
                patch.object(updates.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(OSError, "Could not open Terminal"):
                updates._terminal("echo updater")

    def test_cli_reports_handoff_and_actionable_failure_with_nonzero_exit(self):
        for result, error, expected in (("The updater is open in a terminal.", None, 0),
                                        (None, OSError("Checksum download failed."), 1)):
            output, errors = io.StringIO(), io.StringIO()
            with self.subTest(expected=expected), patch.object(updates, "run_update", return_value=result, side_effect=error), \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                status = cli.main(["update"])
            self.assertEqual(status, expected)
            self.assertEqual(output.getvalue().strip(), result or "")
            self.assertEqual(errors.getvalue().strip(), str(error) if error else "")


if __name__ == "__main__":
    unittest.main()
