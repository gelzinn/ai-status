"""Update detection, platform preservation and verified installer handoffs."""

import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import threading
import time
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
        self.assertEqual(guide["command"], "omarchy plugin update " + updates.PLUGIN_ID + " --yes && omarchy restart shell")
        lib = self.managed_lib()
        with patch.object(paths, "LIB_DIR", lib), patch.object(sys, "platform", "linux"):
            self.assertIn("--bar quickshell", updates.update_guide()["command"])

    @unittest.skipIf(sys.platform == "win32", "Requires Unix shell integration")
    @unittest.skipUnless(shutil.which("bash"), "Requires Bash to exercise the Omarchy update command")
    def test_omarchy_update_restarts_shell_only_after_success_and_propagates_failures(self):
        binary = self.home / "bin"
        binary.mkdir()
        log = self.home / "omarchy-commands"
        executable = binary / "omarchy"
        executable.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$AI_STATUS_TEST_LOG"\n'
                              'if [ "$1" = plugin ]; then exit "$AI_STATUS_TEST_UPDATE_EXIT"; fi\n'
                              'exit "$AI_STATUS_TEST_RESTART_EXIT"\n')
        executable.chmod(0o755)
        with patch.object(updates, "_installation", return_value=("omarchy", {})):
            guide = updates.update_guide()
        for update_status, restart_status, expected in ((0, 0, 0), (7, 0, 7), (0, 9, 9)):
            with self.subTest(update=update_status, restart=restart_status):
                log.write_text("")
                env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                           AI_STATUS_TEST_LOG=str(log), AI_STATUS_TEST_UPDATE_EXIT=str(update_status),
                           AI_STATUS_TEST_RESTART_EXIT=str(restart_status))
                result = subprocess.run(["bash", "-c", guide["command"]], env=env, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, expected)
                expected_commands = ["plugin update " + updates.PLUGIN_ID + " --yes"]
                if update_status == 0:
                    expected_commands.append("restart shell")
                self.assertEqual(log.read_text().splitlines(), expected_commands)

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
        self.assertIn("AppData", guide["description"])

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
            def download(url, destination, progress):
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
        def download(url, destination, progress):
            self.assertEqual(url, updates.REPOSITORY + "/releases/download/v0.13.0/" + filename)
            destination.write_bytes(payload)
        messages = []
        with patch.object(updates, "request_bytes", return_value=checksum), \
                patch.object(updates, "_download_windows", side_effect=download), \
                patch.object(updates.subprocess, "Popen") as launch:
            result = updates._windows_update("0.13.0", messages.append)
        self.assertIn("Setup is open", result)
        self.assertNotIn("successfully installed", result)
        installer = Path(launch.call_args.args[0][0])
        self.assertEqual(installer.read_bytes(), payload)
        self.assertIn({"stage": "verifying", "message": "Verifying the installer…"}, messages)
        self.assertEqual(messages[-1]["stage"], "opening")

    def test_failed_installer_launch_removes_verified_download(self):
        payload = b"installer"
        filename = "ai-status-0.13.0-windows-x64-setup.exe"
        checksum = (hashlib.sha256(payload).hexdigest() + "  " + filename).encode()
        with patch.object(updates, "request_bytes", return_value=checksum), \
                patch.object(updates, "_download_windows", side_effect=lambda url, path, progress: path.write_bytes(payload)), \
                patch.object(updates.subprocess, "Popen", side_effect=OSError("Cannot open setup")):
            with self.assertRaisesRegex(OSError, "Cannot open setup"):
                updates._windows_update("0.13.0", lambda event: None)
        self.assertFalse(list((self.root / "cache").rglob("*.exe")))

    def test_windows_stream_download_uses_system_tls_and_real_byte_events(self):
        destination = self.root / "installer.exe"
        events = []

        def stream(arguments, progress, timeout, failure, **options):
            script = arguments[-1]
            self.assertIn("HttpWebRequest", script)
            self.assertIn("GetResponseStream", script)
            self.assertIn("ContentLength", script)
            self.assertNotIn("Invoke-WebRequest", script)
            self.assertIn("-NonInteractive", arguments)
            progress({"stage": "downloading", "message": "Downloading", "downloadedBytes": 4,
                      "totalBytes": 8, "percent": 50.0})
            destination.write_bytes(b"12345678")

        with patch.object(updates.shutil, "which", return_value="powershell.exe"), \
                patch.object(updates, "_stream_process", side_effect=stream):
            updates._download_windows("https://example.com/installer.exe", destination, events.append)
        self.assertEqual(events[0]["downloadedBytes"], 4)
        self.assertEqual(events[0]["percent"], 50)

    def test_mac_download_streams_bytes_with_known_or_unknown_size(self):
        class Response(io.BytesIO):
            def __init__(self, payload, length):
                super().__init__(payload)
                self.headers = {"Content-Length": length} if length is not None else {}

        payload = b"x" * 150000
        for length in (str(len(payload)), None, "-1", "invalid"):
            events = []
            destination = self.root / ("package-" + str(length))
            with self.subTest(length=length), patch.object(updates.urllib.request, "build_opener") as opener:
                opener.return_value.open.return_value = Response(payload, length)
                updates._download_macos("https://example.com/package", destination, events.append)
            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(events[0]["downloadedBytes"], 0)
            self.assertEqual(events[-1]["downloadedBytes"], len(payload))
            if length == str(len(payload)):
                self.assertEqual(events[-1]["totalBytes"], len(payload))
                self.assertEqual(events[-1]["percent"], 100)
            else:
                self.assertNotIn("totalBytes", events[-1])
                self.assertNotIn("percent", events[-1])

    def test_mac_incomplete_download_fails_without_installation(self):
        response = io.BytesIO(b"partial")
        response.headers = {"Content-Length": "50"}
        with patch.object(updates.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(OSError, "Update download failed"):
                updates._download_macos("https://example.com/package", self.root / "partial", lambda event: None)

    def test_mac_verified_package_uses_transactional_installer_and_preserves_autostart(self):
        payload = b"release archive"
        filename = "ai-status-v0.13.0.tar.gz"
        checksum = (hashlib.sha256(payload).hexdigest() + "  " + filename).encode()
        invocations = []

        def install(arguments, progress, timeout, failure, **options):
            archive = Path(arguments[arguments.index("--package") + 1])
            self.assertEqual(archive.read_bytes(), payload)
            self.assertTrue(Path(arguments[arguments.index("--checksums") + 1]).is_file())
            self.assertIn("--json-progress", arguments)
            self.assertTrue(options["transactional"])
            invocations.append(arguments)
            progress({"stage": "restarting", "message": "Reopening automatically"})

        events = []
        with patch.object(Path, "home", return_value=self.root), \
                patch.object(sys, "platform", "darwin"), patch.object(updates.os, "setpgrp") as detach, \
                patch.object(updates, "request_bytes", return_value=checksum), \
                patch.object(updates, "_download_macos", side_effect=lambda url, path, progress: path.write_bytes(payload)), \
                patch.object(updates, "_stream_process", side_effect=install):
            result = updates._macos_update("0.13.0", {"mode": "native"}, events.append)
        self.assertIn("updated and reopened", result)
        detach.assert_called_once_with()
        self.assertIn("--no-autostart", invocations[0])
        self.assertEqual(events[-1]["stage"], "restarting")
        self.assertFalse(Path(invocations[0][invocations[0].index("--package") + 1]).exists())

    def test_native_mac_updates_in_app_while_swiftbar_keeps_terminal(self):
        for mode in ("native", "stream", "periodic"):
            with self.subTest(mode=mode), \
                    patch.object(updates, "_installation", return_value=("macos-installer", {"mode": mode})), \
                    patch.object(fetch, "check_for_updates", return_value="0.13.0"), \
                    patch.object(updates, "_macos_update", return_value="Updated and reopened") as native, \
                    patch.object(updates, "_terminal") as terminal:
                updates.run_update()
                self.assertEqual(native.call_count, 1 if mode == "native" else 0)
                self.assertEqual(terminal.call_count, 0 if mode == "native" else 1)

    @unittest.skipIf(sys.platform == "win32", "Requires Unix process groups")
    def test_native_mac_updater_survives_old_app_process_group_termination(self):
        ready, finished = self.root / "ready", self.root / "finished"
        source = str(Path(__file__).resolve().parents[1] / "src")
        child_script = """
import hashlib, os, sys, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from core import updates
ready, finished = map(Path, sys.argv[2:])
def install(arguments, progress, *args, **kwargs):
    ready.write_text(str(os.getpgrp()))
    time.sleep(0.3)
    finished.write_text('updated and reopened')
payload = b'package'
checksum = (hashlib.sha256(payload).hexdigest() + '  ai-status-v0.13.0.tar.gz').encode()
with patch.object(sys, 'platform', 'darwin'), patch.object(updates, 'request_bytes', return_value=checksum), \\
     patch.object(updates, '_download_macos', side_effect=lambda url, path, progress: path.write_bytes(payload)), \\
     patch.object(updates, '_stream_process', side_effect=install):
    updates._macos_update('0.13.0', {'mode':'native'}, lambda event: None)
"""
        supervisor = """
import os, signal, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', sys.argv[1], *sys.argv[2:]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ready = Path(sys.argv[3])
deadline = time.monotonic() + 5
while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
    time.sleep(0.01)
if not ready.exists():
    child.kill()
    raise SystemExit('Updater did not get ready')
if int(ready.read_text()) == os.getpgrp():
    child.kill()
    raise SystemExit('Updater still belongs to the app process group')
os.killpg(os.getpgrp(), signal.SIGTERM)
"""
        result = subprocess.run([sys.executable, "-c", supervisor, child_script, source, str(ready), str(finished)],
                                start_new_session=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, -signal.SIGTERM, result.stderr.decode())
        deadline = time.monotonic() + 5
        while not finished.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(finished.read_text(), "updated and reopened")

    def test_mac_bad_checksum_never_runs_installer_and_removes_download(self):
        checksum = ("0" * 64 + "  ai-status-v0.13.0.tar.gz").encode()
        downloads = []

        def download(url, path, progress):
            downloads.append(path)
            path.write_bytes(b"bad archive")

        with patch.object(updates, "request_bytes", return_value=checksum), \
                patch.object(updates, "_download_macos", side_effect=download), \
                patch.object(updates, "_stream_process") as install:
            with self.assertRaisesRegex(ValueError, "checksum did not match"):
                updates._macos_update("0.13.0", {"mode": "native"}, lambda event: None)
        install.assert_not_called()
        self.assertFalse(downloads[0].exists())

    def test_stream_process_drains_stderr_and_reports_nonzero_exit(self):
        script = "import json,sys; sys.stderr.write('x'*200000); print(json.dumps({'stage':'downloading','downloadedBytes':4}),flush=True)"
        events = []
        updates._stream_process([sys.executable, "-c", script], events.append, 5, "Failed")
        self.assertEqual(events[0]["downloadedBytes"], 4)
        with self.assertRaisesRegex(OSError, "Failed"):
            updates._stream_process([sys.executable, "-c", "import sys; sys.exit(7)"], events.append, 5, "Failed")
        with self.assertRaisesRegex(OSError, "Install Xcode Command Line Tools"):
            updates._stream_process([sys.executable, "-c", "import sys; print('Install Xcode Command Line Tools',file=sys.stderr); sys.exit(1)"],
                                    events.append, 5, "Failed", include_errors=True)

    def test_stream_process_times_out_instead_of_stalling(self):
        with self.assertRaisesRegex(OSError, "timed out"):
            updates._stream_process([sys.executable, "-c", "import time; time.sleep(10)"], lambda event: None, 0.1, "Failed")

    @unittest.skipIf(sys.platform == "win32", "Requires Unix process groups")
    @unittest.skipUnless(shutil.which("bash"), "Requires Bash transaction traps")
    def test_transactional_timeout_stops_child_and_runs_rollback_within_bound(self):
        marker = self.root / "rollback-finished"
        script = "trap 'printf rolled-back > \"$1\"; exit 143' TERM\nsleep 10\n"
        started = time.monotonic()
        with self.assertRaisesRegex(OSError, "timed out"):
            updates._stream_process([shutil.which("bash"), "-c", script, "test-installer", str(marker)],
                                    lambda event: None, 0.2, "Failed", transactional=True, start_new_session=True)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(marker.read_text(), "rolled-back")

    def test_terminal_handoff_next_step_matches_the_installation_method(self):
        for method, options, expected in (("omarchy", {}, "Omarchy restarts the shell"),
                                           ("linux-installer", {"bar": "waybar"}, "desktop bar reloads"),
                                           ("macos-installer", {"mode": "stream"}, "menu bar refreshes")):
            with self.subTest(method=method), patch.object(updates, "_installation", return_value=(method, options)), \
                    patch.object(updates.shutil, "which", return_value="/usr/bin/omarchy"), \
                    patch.object(fetch, "check_for_updates", return_value="0.13.0"), \
                    patch.object(updates, "_terminal"):
                self.assertIn(expected, updates.run_update())

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

    def test_cli_json_progress_streams_events_and_complete_or_error(self):
        def run(progress):
            progress({"stage": "downloading", "message": "Downloading…", "downloadedBytes": 25,
                      "totalBytes": 100, "percent": 25})
            return "Setup is open."

        output = io.StringIO()
        with patch.object(updates, "run_update", side_effect=run), contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(["update", "--json-progress"]), 0)
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([event["stage"] for event in events], ["downloading", "complete"])
        self.assertEqual(events[0]["percent"], 25)
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(updates, "run_update", side_effect=OSError("Download failed")), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(cli.main(["update", "--json-progress"]), 1)
        self.assertEqual(json.loads(output.getvalue()), {"stage": "error", "message": "Download failed"})
        self.assertEqual(errors.getvalue(), "")

    @unittest.skipIf(sys.platform == "win32", "Requires a Unix pipe that has no reader")
    def test_cli_json_update_survives_ui_stdout_pipe_closing_on_restart(self):
        marker = self.root / "update-finished"
        script = """
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from core import cli, updates
def run(progress):
    progress({'stage': 'restarting', 'message': 'Reopening automatically'})
    Path(sys.argv[2]).write_text('activated and reopened')
    return 'AI Status was updated and reopened.'
with patch.object(updates, 'run_update', side_effect=run):
    raise SystemExit(cli.main(['update', '--json-progress']))
"""
        reader, writer = os.pipe()
        os.close(reader)
        try:
            result = subprocess.run([sys.executable, "-c", script, str(Path(__file__).resolve().parents[1] / "src"), str(marker)],
                                    stdout=writer, stderr=subprocess.PIPE, timeout=10)
        finally:
            os.close(writer)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(marker.read_text(), "activated and reopened")
        self.assertEqual(result.stderr, b"")


@unittest.skipUnless(sys.platform == "win32", "Native PowerShell streaming needs Windows")
class NativeWindowsDownloadTests(unittest.TestCase):
    def test_native_powershell_tls_streaming_and_failure_paths(self):
        self.assertTrue(shutil.which("powershell.exe"), "Windows PowerShell is required for installer downloads")
        openssl = shutil.which("openssl")
        if not openssl:
            candidate = Path("C:/Program Files/Git/usr/bin/openssl.exe")
            openssl = str(candidate) if candidate.is_file() else None
        self.assertTrue(openssl, "OpenSSL build tool is required for the temporary TLS fixture")
        payload = b"installer-fixture" * 16384

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/failure":
                    self.send_response(503)
                    self.end_headers()
                    return
                self.send_response(200)
                if self.path != "/unknown":
                    self.send_header("Content-Length", str(len(payload) + (1 if self.path == "/partial" else 0)))
                self.end_headers()
                try:
                    for offset in range(0, len(payload), 32768):
                        self.wfile.write(payload[offset:offset + 32768])
                        self.wfile.flush()
                        time.sleep(0.05)
                except (ConnectionResetError, BrokenPipeError):
                    pass

            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory(prefix="ai-status-windows-download-") as temporary:
            folder = Path(temporary)
            key, certificate = folder / "key.pem", folder / "cert.pem"
            subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                            "-subj", "/CN=localhost", "-keyout", str(key), "-out", str(certificate)],
                           capture_output=True, check=True, timeout=15)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certificate, key)
            fingerprint = hashlib.sha1(ssl.PEM_cert_to_DER_cert(certificate.read_text())).hexdigest().upper()
            # Trust only this ephemeral certificate in this test's subprocess.
            # A compiled callback avoids PowerShell's missing-runspace error on
            # the .NET TLS worker thread. Production certificate checks remain on.
            callback = """
using System.Net;
public class UpdateTestTls {
    public static void Install() {
        ServicePointManager.ServerCertificateValidationCallback =
            (sender, certificate, chain, errors) => certificate != null &&
                certificate.GetCertHashString() == "FINGERPRINT";
    }
}
""".replace("FINGERPRINT", fingerprint)
            prefix = "$ErrorActionPreference='Stop'; Add-Type -TypeDefinition '" + callback + "'; [UpdateTestTls]::Install();\n"
            stream = updates._stream_process

            def trust_fixture(arguments, progress, timeout, failure, **options):
                arguments = [*arguments[:-1], prefix + arguments[-1]]
                stream(arguments, progress, 20, failure, include_errors=True, **options)

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"https://127.0.0.1:{server.server_port}"
            try:
                # The production path rejects the untrusted fixture certificate.
                with self.assertRaisesRegex(OSError, "Installer download failed"):
                    updates._download_windows(url + "/known", folder / "untrusted.exe", lambda event: None)
                self.assertFalse((folder / "untrusted.exe").exists())
                with patch.object(updates, "_stream_process", side_effect=trust_fixture):
                    for route in ("known", "unknown"):
                        with self.subTest(route=route):
                            events = []
                            destination = folder / (route + ".exe")
                            updates._download_windows(url + "/" + route, destination, events.append)
                            self.assertEqual(destination.read_bytes(), payload)
                            self.assertEqual(events[0]["downloadedBytes"], 0)
                            self.assertEqual(events[-1]["downloadedBytes"], len(payload))
                            self.assertGreater(len(events), 2, "Expected progress while the response was still streaming")
                            self.assertTrue(all(event["stage"] == "downloading" for event in events))
                            if route == "known":
                                self.assertEqual(events[-1]["totalBytes"], len(payload))
                                self.assertEqual(events[-1]["percent"], 100)
                            else:
                                self.assertTrue(all("totalBytes" not in event and "percent" not in event for event in events))
                    for route in ("partial", "failure"):
                        with self.subTest(route=route), self.assertRaisesRegex(OSError, "Installer download failed"):
                            updates._download_windows(url + "/" + route, folder / (route + ".exe"), lambda event: None)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
