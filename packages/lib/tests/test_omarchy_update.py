"""Exercise the Omarchy recovery helper with real Git and isolated installs."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

LIB = Path(__file__).resolve().parents[1]
PLUGIN_ID = "io.github.gelzinn.ai-status"
GIT = shutil.which("git")


@unittest.skipIf(sys.platform == "win32", "Requires Linux shell integration")
@unittest.skipUnless(GIT and shutil.which("bash"), "Requires Git and Bash")
class OmarchyUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status-omarchy-' ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.source = self.root / "source"
        self.source.mkdir()
        self.plugin = self.home / ".config/omarchy/plugins" / PLUGIN_ID
        self.backups = self.plugin.parent / ".ai-status-backups"
        self.log = self.root / "commands"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CACHE_HOME=str(self.home / "cache"),
                        XDG_STATE_HOME=str(self.home / "state"),
                        PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_COUNT="0",
                        AI_STATUS_TEST_LOG=str(self.log), AI_STATUS_TEST_REAL_GIT=GIT)
        for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
                    "EMAIL", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            self.env.pop(key, None)
        self.git(self.source, "init", "-b", "main")
        self.manifest = {"schemaVersion": 1, "id": PLUGIN_ID, "version": "0.1.0"}
        (self.source / "manifest.json").write_text(json.dumps(self.manifest))
        (self.source / ".gitignore").write_text(".env\n")
        self.commit_source("first")
        self.plugin.parent.mkdir(parents=True)
        self.git(self.root, "clone", str(self.source), str(self.plugin))
        self.previous_head = self.git(self.plugin, "rev-parse", "HEAD").stdout.strip()
        self.preferences = self.home / ".config/ai-status/selected.json"
        self.preferences.parent.mkdir(parents=True)
        self.preferences.write_text('{"usage_display":"remaining","show_model":false}')
        self.bar = self.home / ".config/omarchy/shell.json"
        self.bar.write_text(json.dumps({"bar": {"layout": {"left": [{"id": PLUGIN_ID, "settings": {"custom": True}}]}}}))
        self.saved_preferences = self.preferences.read_bytes()
        self.saved_bar = self.bar.read_bytes()
        self.other = self.plugin.parent / "other.plugin/manifest.json"
        self.other.parent.mkdir()
        self.other.write_text('{"id":"other.plugin"}')
        self.saved_other = self.other.read_bytes()
        self.tool("git", '''import os, subprocess, sys
if os.environ.get('AI_STATUS_TEST_CLONE_FAILURE') and 'clone' in sys.argv[1:]:
    print('Fixture clone failed', file=sys.stderr)
    sys.exit(7)
if os.environ.get('AI_STATUS_TEST_ORIGIN_FAILURE') and sys.argv[3:5] == ['remote', 'set-url']:
    sys.exit(8)
sys.exit(subprocess.call([os.environ['AI_STATUS_TEST_REAL_GIT'], *sys.argv[1:]]))
''')
        # Mirrors Omarchy's fetch/ff-only update and validated add without
        # requiring a desktop or modifying any shell preferences.
        self.tool("omarchy", '''import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['AI_STATUS_TEST_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
plugin = Path.home() / '.config/omarchy/plugins/io.github.gelzinn.ai-status'
def git(*arguments, capture=False):
    return subprocess.run(['git', '-C', str(plugin), *arguments], capture_output=capture, text=True)
if args[:2] == ['plugin', 'update']:
    if os.environ.get('AI_STATUS_TEST_FETCH_FAILURE'):
        print('omarchy-plugin-update: fetch failed', file=sys.stderr)
        sys.exit(7)
    result = git('fetch', '--quiet', 'origin', 'HEAD', capture=True)
    if result.returncode:
        print('omarchy-plugin-update: fetch failed', file=sys.stderr)
        sys.exit(1)
    result = git('merge', '--ff-only', 'FETCH_HEAD', capture=True)
    if result.returncode:
        print("omarchy-plugin-update: cannot fast-forward 'io.github.gelzinn.ai-status'; you have local changes in " + str(plugin), file=sys.stderr)
        sys.exit(1)
elif args[:2] == ['plugin', 'add']:
    if os.environ.get('AI_STATUS_TEST_WAIT_ON_ADD'):
        import time
        (Path.home() / 'updater-ready').touch()
        time.sleep(30)
    if os.environ.get('AI_STATUS_TEST_VALIDATION_FAILURE'):
        print('omarchy-plugin-add: refusing to add: validation failed', file=sys.stderr)
        sys.exit(6)
    if plugin.exists():
        sys.exit('Existing plugin would be overwritten')
    result = subprocess.run(['git', 'clone', '--', args[2], str(plugin)])
    if result.returncode:
        sys.exit(result.returncode)
    if os.environ.get('AI_STATUS_TEST_RESCAN_FAILURE'):
        sys.exit(9)
elif args == ['restart', 'shell']:
    sys.exit(int(os.environ.get('AI_STATUS_TEST_RESTART_FAILURE', '0')))
else:
    sys.exit('Unexpected Omarchy command: ' + repr(args))
''')
        self.tool("omarchy-shell", "import sys\n")

    def tool(self, name, script):
        executable = self.bin / name
        executable.write_text("#!/usr/bin/env python3\n" + script)
        executable.chmod(0o755)

    def git(self, directory, *arguments):
        return subprocess.run([GIT, "-C", str(directory), *arguments], env=self.env,
                              capture_output=True, text=True, check=True, timeout=15)

    def commit_source(self, text):
        (self.source / "Panel.qml").write_text(text)
        self.git(self.source, "add", ".")
        self.git(self.source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
                 "-c", "commit.gpgsign=false", "commit", "-m", text)

    def update(self, piped=False):
        command = ["bash"] if piped else ["bash", str(LIB / "update-omarchy.sh")]
        return subprocess.run(command, input=(LIB / "update-omarchy.sh").read_text() if piped else None, env=self.env,
                              capture_output=True, text=True, timeout=20)

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def assert_settings_preserved(self):
        self.assertEqual(self.preferences.read_bytes(), self.saved_preferences)
        self.assertEqual(self.bar.read_bytes(), self.saved_bar)
        self.assertEqual(self.other.read_bytes(), self.saved_other)

    def only_backup(self):
        copies = list(self.backups.glob("*/plugin"))
        self.assertEqual(len(copies), 1)
        return copies[0]

    def test_clean_fast_forward_keeps_native_update_and_needs_no_backup_or_git_identity(self):
        self.commit_source("second")
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.plugin / "Panel.qml").read_text(), "second")
        self.assertEqual(self.commands(), [["plugin", "update", PLUGIN_ID, "--yes"], ["restart", "shell"]])
        self.assertFalse(self.backups.exists())
        self.assert_settings_preserved()

    def test_untouched_install_recovers_from_rewritten_upstream_and_updates_again(self):
        self.assertEqual(self.git(self.plugin, "status", "--porcelain").stdout, "")
        self.git(self.source, "checkout", "--orphan", "replacement")
        self.git(self.source, "branch", "-D", "main")
        self.git(self.source, "branch", "-m", "main")
        self.commit_source("rewritten upstream")
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.plugin / "Panel.qml").read_text(), "rewritten upstream")
        backup = self.only_backup()
        self.assertEqual(self.git(backup, "rev-parse", "HEAD").stdout.strip(), self.previous_head)
        self.assertEqual(self.git(backup, "status", "--porcelain").stdout, "")
        self.assertEqual(self.git(self.plugin, "remote", "get-url", "origin").stdout.strip(), str(self.source))
        self.assertEqual(self.commands()[-1], ["restart", "shell"])
        self.assert_settings_preserved()
        self.commit_source("third")
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.plugin / "Panel.qml").read_text(), "third")
        self.assertEqual(self.only_backup(), backup)

    def test_recovery_keeps_tracked_staged_untracked_and_ignored_files_in_backup(self):
        self.commit_source("second")
        (self.plugin / "Panel.qml").write_text("local staged")
        self.git(self.plugin, "add", "Panel.qml")
        (self.plugin / "Panel.qml").write_text("local unstaged")
        (self.plugin / "notes.txt").write_text("local notes")
        (self.plugin / ".env").write_text("private fixture")
        previous_status = self.git(self.plugin, "status", "--porcelain").stdout
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backup = self.only_backup()
        self.assertEqual(self.git(backup, "status", "--porcelain").stdout, previous_status)
        self.assertEqual((backup / "Panel.qml").read_text(), "local unstaged")
        self.assertEqual(self.git(backup, "show", ":Panel.qml").stdout, "local staged")
        self.assertEqual((backup / "notes.txt").read_text(), "local notes")
        self.assertEqual((backup / ".env").read_text(), "private fixture")
        self.assertEqual(self.git(self.plugin, "status", "--porcelain").stdout, "")
        self.assertNotIn("private fixture", result.stdout + result.stderr)
        self.assertEqual(backup.parent.stat().st_mode & 0o777, 0o700)
        self.assert_settings_preserved()

    def test_piped_recovery_supports_older_installs_without_the_helper(self):
        self.commit_source("second")
        (self.plugin / "Panel.qml").write_text("local")
        self.assertFalse((self.plugin / "packages/lib/update-omarchy.sh").exists())
        result = self.update(piped=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.plugin / "Panel.qml").read_text(), "second")
        self.assertEqual((self.only_backup() / "Panel.qml").read_text(), "local")
        self.assertEqual(self.commands()[-1], ["restart", "shell"])
        self.assert_settings_preserved()

    def test_interrupted_reinstallation_restores_the_previous_plugin(self):
        self.commit_source("second")
        (self.plugin / "Panel.qml").write_text("local")
        self.env["AI_STATUS_TEST_WAIT_ON_ADD"] = "1"
        process = subprocess.Popen(["bash", str(LIB / "update-omarchy.sh")], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            deadline = time.monotonic() + 5
            while not (self.home / "updater-ready").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.home / "updater-ready").exists())
            os.killpg(process.pid, signal.SIGTERM)
            output, errors = process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("Previous AI Status plugin restored", errors, output + errors)
            self.assertEqual((self.plugin / "Panel.qml").read_text(), "local")
            self.assertNotIn(["restart", "shell"], self.commands())
            self.assert_settings_preserved()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()

    def test_preparation_failure_keeps_original_checkout_in_place(self):
        self.commit_source("second")
        (self.plugin / "Panel.qml").write_text("local")
        self.env["AI_STATUS_TEST_CLONE_FAILURE"] = "1"
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.plugin / "Panel.qml").read_text(), "local")
        self.assertFalse(self.backups.exists())
        self.assertEqual(len(self.commands()), 1)
        self.assert_settings_preserved()

    def test_failed_add_validation_rescan_and_origin_repair_restore_original_checkout(self):
        self.commit_source("second")
        (self.plugin / "Panel.qml").write_text("local")
        original_status = self.git(self.plugin, "status", "--porcelain").stdout
        for failure, expected in (("VALIDATION", 6), ("RESCAN", 9), ("ORIGIN", 1)):
            with self.subTest(failure=failure):
                self.env["AI_STATUS_TEST_" + failure + "_FAILURE"] = "1"
                result = self.update()
                del self.env["AI_STATUS_TEST_" + failure + "_FAILURE"]
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertIn("Previous AI Status plugin restored", result.stderr)
                self.assertEqual((self.plugin / "Panel.qml").read_text(), "local")
                self.assertEqual(self.git(self.plugin, "status", "--porcelain").stdout, original_status)
                self.assertNotIn(["restart", "shell"], self.commands())
                self.assert_settings_preserved()

    def test_wrong_plugin_id_aborts_before_moving_original(self):
        (self.source / "manifest.json").write_text(json.dumps({**self.manifest, "id": "other.plugin"}))
        self.commit_source("second")
        (self.plugin / "Panel.qml").write_text("local")
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not identify the AI Status plugin", result.stderr)
        self.assertEqual((self.plugin / "Panel.qml").read_text(), "local")
        self.assertFalse(self.backups.exists())
        self.assertEqual(len(self.commands()), 1)
        self.assert_settings_preserved()

    def test_fetch_failure_does_not_reinstall_or_restart(self):
        self.env["AI_STATUS_TEST_FETCH_FAILURE"] = "1"
        result = self.update()
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(self.commands()), 1)
        self.assertFalse(self.backups.exists())
        self.assertEqual(self.git(self.plugin, "rev-parse", "HEAD").stdout.strip(), self.previous_head)
        self.assert_settings_preserved()

    def test_concurrent_update_and_unmanaged_folder_are_left_untouched(self):
        lock = self.home / "cache/ai-status/omarchy-plugin-update.lock"
        lock.mkdir(parents=True)
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Another AI Status plugin update", result.stderr)
        self.assertEqual(self.commands(), [])
        lock.rmdir()
        (self.plugin / ".git").rename(self.root / "original-git")
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a managed Git checkout", result.stderr)
        self.assertEqual(self.commands(), [])
        self.assert_settings_preserved()
