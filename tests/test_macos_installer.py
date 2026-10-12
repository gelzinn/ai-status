"""Run the macOS installer on Linux with only native OS tools replaced."""

import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packages/lib/install-macos.sh"
REAL_GIT = shutil.which("git")
REAL_BASH = shutil.which("bash")


class MacOSInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="AI Status macOS é ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.installed = self.home / ".local/share/ai-status"
        self.bundle = self.installed / "AI Status.app"
        self.agent = self.home / "Library/LaunchAgents/com.gelzin.ai-status.plist"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("bash", "python3", "dirname", "cat", "mkdir", "rm", "cp", "mv", "rmdir",
                     "mktemp", "ln", "chmod", "touch", "sleep", "find", "readlink", "date", "sed"):
            executable = shutil.which(name)
            if executable:
                (self.bin / name).symlink_to(executable)
        self.env = {
            **os.environ, "HOME": str(self.home), "PATH": str(self.bin),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CEILING_DIRECTORIES": str(self.root),
            "GIT_AUTHOR_NAME": "Installer Test", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Installer Test", "GIT_COMMITTER_EMAIL": "test@example.com",
            "TEST_REAL_GIT": REAL_GIT, "TEST_ASSETS": str(self.root / "assets"),
            "TEST_LOG": str(self.root / "tools.jsonl"),
            "TEST_ACTIVE_ROOT": str(self.installed),
            "TEST_RESPONSE": json.dumps({"tag_name": "v0.10.0", "draft": False, "prerelease": False}),
        }
        self.repo = self.root / "repo"
        self.repo.mkdir()
        shutil.copytree(ROOT / "packages/lib", self.repo / "packages/lib",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "windows", "quickshell", "fonts"))
        shutil.copytree(ROOT / "packages/shared", self.repo / "packages/shared")
        self.git("init", "-b", "main")
        for version in ("0.9.0", "0.10.0", "0.11.0"):
            lib = self.repo / "packages/lib"
            if version == "0.9.0":
                (lib / "VERSION").write_text(version + "\n")
                (self.repo / "package.json").write_text(json.dumps({"name": "legacy-workspace", "private": True}))
            else:
                (lib / "VERSION").unlink(missing_ok=True)
                (self.repo / "package.json").write_text(json.dumps({"version": version}))
            (lib / "marker").write_text(version)
            self.git("add", ".")
            self.git("-c", "commit.gpgsign=false", "commit", "-m", "feat: " + version)
            if version != "0.11.0":
                self.git("tag", "v" + version)
                self.make_release(version)
        self.bootstrap = self.root / "bootstrap/install-macos.sh"
        self.bootstrap.parent.mkdir()
        shutil.copyfile(INSTALLER, self.bootstrap)
        self.write_tool("uname", "import sys; print('arm64' if '-m' in sys.argv else 'Darwin')")
        self.write_tool("sw_vers", "print('13.0')")
        self.write_tool("id", "print('501')")
        self.write_tool("defaults", "import os, sys; value=os.environ.get('TEST_PLUGIN_DIR'); print(value or ''); sys.exit(0 if value else 1)")
        self.write_tool("xcrun", "import os; print(os.path.join(os.environ['PATH'], 'swiftc'))")
        self.write_tool("swiftc", """
import json, os, pathlib, sys
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(['swiftc', *sys.argv[1:]]) + '\\n')
if os.environ.get('TEST_SWIFTC_FAIL'):
    sys.exit(1)
output = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text('#!/bin/bash\\nexit 0\\n')
output.chmod(0o755)
""")
        for name in ("launchctl", "open", "codesign", "plutil"):
            self.write_tool(name, """
import json, os, pathlib, sys
with open(os.environ['TEST_LOG'], 'a') as log:
    name = pathlib.Path(sys.argv[0]).name
    log.write(json.dumps([name, *sys.argv[1:]]) + '\\n')
    if name == 'open' or (name == 'launchctl' and 'bootstrap' in sys.argv):
        root = pathlib.Path(os.environ['TEST_ACTIVE_ROOT'])
        manifest = root / 'package.json'
        version = json.loads(manifest.read_text())['version'] if manifest.exists() else (root / 'packages/lib/VERSION').read_text().strip()
        log.write(json.dumps(['started-version', version]) + '\\n')
""")
        self.write_tool("git", """
import os, subprocess, sys
if sys.argv[1] == 'clone':
    sys.exit('Public installs must download a checked stable release')
sys.exit(subprocess.run([os.environ['TEST_REAL_GIT'], *sys.argv[1:]]).returncode)
""")
        self.write_tool("curl", """
import os, pathlib, sys
args = sys.argv[1:]
url = args[-1]
if '/releases/latest' in url:
    print(os.environ['TEST_RESPONSE'])
    sys.exit(int(os.environ.get('TEST_CURL_EXIT', '0')))
if '/releases/download/' not in url:
    sys.exit('Unexpected download URL: ' + url)
tag, name = url.split('/releases/download/')[1].split('/')
asset = pathlib.Path(os.environ['TEST_ASSETS']) / tag / name
exists = asset.is_file()
if exists:
    pathlib.Path(args[args.index('--output') + 1]).write_bytes(asset.read_bytes())
if '--write-out' in args:
    print('200' if exists else '404', end='')
sys.exit(0 if exists else 22)
""")

    def write_tool(self, name, body):
        filename = self.bin / name
        filename.write_text("#!" + sys.executable + "\n" + body + "\n")
        filename.chmod(0o755)

    def git(self, *arguments):
        return subprocess.run([REAL_GIT, "-C", str(self.repo), *arguments], env=self.env,
                              check=True, capture_output=True, text=True)

    def make_release(self, version):
        directory = self.root / "assets" / ("v" + version)
        directory.mkdir(parents=True)
        archive = directory / f"ai-status-v{version}.tar.gz"
        with tarfile.open(archive, "w:gz") as package:
            package.add(self.repo / "packages", arcname="packages")
            if (self.repo / "package.json").exists():
                package.add(self.repo / "package.json", arcname="package.json")
        (directory / "SHA256SUMS").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")

    def run_installer(self, *arguments, local=False, start=False, autostart=True):
        script = self.repo / "packages/lib/install-macos.sh" if local else self.bootstrap
        flags = ["--no-interactive", "--skip-check"]
        if not start:
            flags.append("--no-start")
        if not autostart:
            flags.append("--no-autostart")
        return subprocess.run([REAL_BASH, str(script), *flags, *arguments], cwd=self.root, env=self.env,
                              capture_output=True, text=True, timeout=30)

    def tool_calls(self, name):
        path = self.root / "tools.jsonl"
        calls = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [call for call in calls if call[0] == name]

    def assert_success(self, result, version):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.installed_version(self.installed), version)
        self.assertEqual((self.installed / "packages/lib/marker").read_text(), version)
        self.assertTrue((self.installed / "packages/shared/providers/providers.json").is_file())
        self.assertTrue((self.home / ".local/bin/ai-status").is_symlink())
        self.assertFalse((self.installed / ".git").exists())

    def installed_version(self, root):
        manifest = root / "package.json"
        return json.loads(manifest.read_text())["version"] if manifest.exists() else (root / "packages/lib/VERSION").read_text().strip()

    def rewrite_manifest(self, data):
        self.rewrite_package_file("package.json", data)

    def rewrite_package_file(self, name, data):
        directory = self.root / "assets/v0.10.0"
        archive = directory / "ai-status-v0.10.0.tar.gz"
        replacement = io.BytesIO()
        with tarfile.open(archive, "r:gz") as source, tarfile.open(fileobj=replacement, mode="w:gz") as target:
            for member in source:
                if member.name == name:
                    member.size = len(data)
                    target.addfile(member, io.BytesIO(data))
                else:
                    target.addfile(member, source.extractfile(member))
        archive.write_bytes(replacement.getvalue())
        (directory / "SHA256SUMS").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")

    def seed_existing_install(self):
        self.installed.mkdir(parents=True)
        (self.installed / "keep").write_text("existing install")

    def assert_preserved(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.installed / "keep").read_text(), "existing install")
        self.assertFalse((self.installed.parent / ".ai-status-update.lock").exists())
        self.assertFalse(list(self.installed.parent.glob(".ai-status-stage.*")))

    def test_default_installs_native_bundle_and_per_user_agent_without_launching(self):
        result = self.run_installer()
        self.assert_success(result, "0.10.0")
        info = plistlib.loads((self.bundle / "Contents/Info.plist").read_bytes())
        self.assertTrue(info["LSUIElement"])
        self.assertEqual(info["CFBundleVersion"], "0.10.0")
        self.assertEqual(info["CFBundleShortVersionString"], "0.10.0")
        self.assertTrue((self.installed / "package.json").is_file())
        self.assertFalse((self.installed / "packages/lib/VERSION").exists())
        self.assertTrue((self.bundle / "Contents/MacOS" / info["CFBundleExecutable"]).is_file())
        runtime = json.loads((self.bundle / "Contents/Resources/runtime.json").read_text())
        self.assertTrue(Path(runtime["python"]).is_absolute())
        self.assertEqual(Path(runtime["cli"]), self.installed / "packages/lib/src/bin/ai-status")
        self.assertNotIn(".ai-status-stage.", json.dumps(runtime))
        shortcut = self.home / "Applications/AI Status.app"
        self.assertTrue(shortcut.is_symlink())
        self.assertEqual(shortcut.resolve(), self.bundle.resolve())
        self.assertFalse((self.bundle / "AI Status.app").exists())
        agent = plistlib.loads(self.agent.read_bytes())
        self.assertEqual(agent["Label"], "com.gelzin.ai-status")
        self.assertTrue(agent["RunAtLoad"])
        executable = Path(agent["ProgramArguments"][0])
        self.assertTrue(executable.is_absolute())
        self.assertTrue(executable.is_file())
        self.assertEqual(len(self.tool_calls("swiftc")), 1)
        self.assertFalse(self.tool_calls("open"))
        self.assertFalse(any("bootstrap" in call for call in self.tool_calls("launchctl")))

    def test_no_autostart_does_not_create_a_login_agent(self):
        result = self.run_installer(autostart=False)
        self.assert_success(result, "0.10.0")
        self.assertFalse(self.agent.exists())
        self.assertFalse(any("bootstrap" in call for call in self.tool_calls("launchctl")))

    def test_local_checkout_keeps_branch_code_instead_of_published_main(self):
        result = self.run_installer(local=True)
        self.assert_success(result, "0.11.0")
        self.assertTrue(self.bundle.is_dir())

    def test_legacy_local_checkout_omits_its_unversioned_workspace_manifest(self):
        self.git("checkout", "v0.9.0")
        self.assert_success(self.run_installer(local=True), "0.9.0")
        self.assertFalse((self.installed / "package.json").exists())

    def test_explicit_version_and_offline_rollback_restore_exact_versions(self):
        self.assert_success(self.run_installer("--version", "v0.9.0"), "0.9.0")
        self.assert_success(self.run_installer(), "0.10.0")
        self.env["TEST_CURL_EXIT"] = "22"
        self.assert_success(self.run_installer("--rollback"), "0.9.0")
        previous = self.installed.with_name("ai-status.previous")
        self.assertEqual(self.installed_version(previous), "0.10.0")
        self.assertTrue((previous / "package.json").exists())
        self.assertFalse((self.installed / "package.json").exists())
        self.assertEqual((self.home / "Applications/AI Status.app").resolve(), self.bundle.resolve())
        self.assertFalse((self.bundle / "AI Status.app").exists())

    def test_start_loads_the_login_agent_or_opens_the_app_without_autostart(self):
        self.assert_success(self.run_installer(start=True), "0.10.0")
        bootstrap = next(call for call in self.tool_calls("launchctl") if "bootstrap" in call)
        self.assertEqual(bootstrap[1:], ["bootstrap", "gui/501", str(self.agent)])
        self.assert_success(self.run_installer(start=True, autostart=False), "0.10.0")
        self.assertFalse(self.agent.exists())
        self.assertEqual(self.tool_calls("open")[-1][1:], ["-a", str(self.home / "Applications/AI Status.app")])
        self.assertFalse((self.bundle / "AI Status.app").exists())

    def test_update_preserves_existing_display_preferences(self):
        self.assert_success(self.run_installer("--version", "0.9.0"), "0.9.0")
        filename = self.home / ".config/ai-status/selected.json"
        selected = {"provider": "codex", "idx": 1, "metric": "weekly", "icon_mode": "off",
                    "show_provider": False, "show_model": False, "show_metric": True, "show_pct": True,
                    "custom": "keep this"}
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(json.dumps(selected))
        self.assert_success(self.run_installer(), "0.10.0")
        self.assertEqual(json.loads(filename.read_text()), selected)

    def test_bad_checksum_preserves_the_existing_install(self):
        self.seed_existing_install()
        (self.root / "assets/v0.10.0/SHA256SUMS").write_text("0" * 64 + "  ai-status-v0.10.0.tar.gz\n")
        self.assert_preserved(self.run_installer())
        self.assertFalse(self.bundle.exists())

    def test_predownloaded_package_updates_from_installed_script_with_json_progress(self):
        self.assert_success(self.run_installer("--version", "0.9.0"), "0.9.0")
        self.env["TEST_CURL_EXIT"] = "22"
        assets = self.root / "assets/v0.10.0"
        arguments = [REAL_BASH, str(self.installed / "packages/lib/install-macos.sh"),
                     "--no-interactive", "--skip-check", "--no-autostart", "--json-progress",
                     "--version", "v0.10.0", "--package", str(assets / "ai-status-v0.10.0.tar.gz"),
                     "--checksums", str(assets / "SHA256SUMS")]
        result = subprocess.run(arguments, cwd=self.root, env=self.env, capture_output=True, text=True, timeout=30)
        self.assert_success(result, "0.10.0")
        events = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([event["stage"] for event in events], ["verifying", "installing", "restarting", "complete"])
        self.assertEqual(self.tool_calls("started-version")[-1], ["started-version", "0.10.0"])
        self.assertFalse(self.agent.exists())
        self.assertFalse((self.installed.parent / ".ai-status-update.lock").exists())

    def test_predownloaded_package_rechecks_checksum_and_preserves_install_on_failure(self):
        self.seed_existing_install()
        assets = self.root / "assets/v0.10.0"
        sums = assets / "SHA256SUMS"
        sums.write_text("0" * 64 + "  ai-status-v0.10.0.tar.gz\n")
        result = self.run_installer("--version", "0.10.0", "--package", str(assets / "ai-status-v0.10.0.tar.gz"),
                                    "--checksums", str(sums), "--json-progress")
        self.assert_preserved(result)
        self.assertFalse(self.tool_calls("swiftc"))
        events = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([event["stage"] for event in events], ["verifying"])

    @unittest.skipIf(sys.platform == "win32", "Requires a Unix pipe that has no reader")
    def test_native_installation_finishes_when_old_ui_closes_progress_pipe(self):
        assets = self.root / "assets/v0.10.0"
        arguments = [REAL_BASH, str(self.bootstrap), "--no-interactive", "--skip-check", "--no-autostart",
                     "--json-progress", "--version", "v0.10.0", "--package", str(assets / "ai-status-v0.10.0.tar.gz"),
                     "--checksums", str(assets / "SHA256SUMS")]
        reader, writer = os.pipe()
        os.close(reader)
        try:
            result = subprocess.run(arguments, cwd=self.root, env=self.env, stdout=writer, stderr=subprocess.PIPE,
                                    text=True, timeout=30)
        finally:
            os.close(writer)
        result.stdout = ""
        self.assert_success(result, "0.10.0")
        self.assertEqual(self.tool_calls("started-version")[-1], ["started-version", "0.10.0"])
        self.assertNotIn("BrokenPipe", result.stderr)

    def test_invalid_canonical_manifest_is_rejected_before_build_or_activation(self):
        self.seed_existing_install()
        for data in (b'{invalid json', b'{"version":"0.9.0"}', b'{"version":null}'):
            with self.subTest(data=data):
                self.rewrite_manifest(data)
                self.assert_preserved(self.run_installer())
                self.assertFalse(self.tool_calls("swiftc"))

    def test_cli_version_disagreement_is_rejected_before_build_or_activation(self):
        self.seed_existing_install()
        self.rewrite_package_file("packages/lib/src/core/__init__.py", b'__version__ = "0.9.0"\n')
        result = self.run_installer()
        self.assert_preserved(result)
        self.assertIn("CLI and release version metadata disagree", result.stderr)
        self.assertFalse(self.tool_calls("swiftc"))

    def test_failed_native_build_preserves_the_existing_install(self):
        self.seed_existing_install()
        self.env["TEST_SWIFTC_FAIL"] = "1"
        self.assert_preserved(self.run_installer())
        self.assertFalse(self.agent.exists())

    def test_failed_running_app_quit_preserves_active_version_and_does_not_start_replacement(self):
        self.assert_success(self.run_installer("--version", "0.9.0"), "0.9.0")
        executable = self.bundle / "Contents/MacOS/AIStatus"
        executable.write_text('#!/bin/bash\nif [ "$1" = --quit ]; then exit 1; fi\nexit 0\n')
        executable.chmod(0o755)
        original_agent = self.agent.read_bytes()
        original_runtime = (self.bundle / "Contents/Resources/runtime.json").read_bytes()
        result = self.run_installer(start=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.installed / "packages/lib/VERSION").read_text().strip(), "0.9.0")
        self.assertEqual((self.installed / "packages/lib/marker").read_text(), "0.9.0")
        self.assertEqual((self.home / "Applications/AI Status.app").resolve(), self.bundle.resolve())
        self.assertEqual(self.agent.read_bytes(), original_agent)
        self.assertEqual((self.bundle / "Contents/Resources/runtime.json").read_bytes(), original_runtime)
        self.assertFalse((self.installed.parent / ".ai-status-update.lock").exists())
        self.assertFalse(list(self.installed.parent.glob(".ai-status-stage.*")))
        # Recovery may reload the previous login agent after bootout; every
        # launch must still see the original library, never the replacement.
        self.assertTrue(self.tool_calls("started-version"))
        self.assertTrue(all(call == ["started-version", "0.9.0"] for call in self.tool_calls("started-version")))

    def test_failed_release_lookup_preserves_the_existing_install(self):
        self.seed_existing_install()
        self.env["TEST_CURL_EXIT"] = "22"
        self.assert_preserved(self.run_installer())

    def test_invalid_mode_fails_before_mutating_the_existing_install(self):
        self.seed_existing_install()
        self.assert_preserved(self.run_installer("--mode", "unknown"))
        self.assertFalse(self.tool_calls("swiftc"))

    def test_optional_swiftbar_modes_do_not_build_a_native_bundle(self):
        plugin_dir = self.home / "Library/Application Support/SwiftBar/Plugins"
        self.env["TEST_PLUGIN_DIR"] = str(plugin_dir)
        for mode, command in (("stream", "swiftbar-stream"), ("periodic", "swiftbar")):
            with self.subTest(mode=mode):
                self.assert_success(self.run_installer("--mode", mode), "0.10.0")
                plugins = list(plugin_dir.glob("ai-status.*.py"))
                self.assertEqual(len(plugins), 1)
                self.assertIn(command, plugins[0].read_text())
                self.assertIn("<xbar.version>v0.10.0</xbar.version>", plugins[0].read_text())
                syntax = subprocess.run([REAL_BASH, "-n", str(plugins[0])], capture_output=True, text=True)
                self.assertEqual(syntax.returncode, 0, syntax.stderr)
                # Execute the generated shell wrapper with a harmless installed
                # CLI so paths containing spaces and Unicode are really tested.
                cli = self.installed / "packages/lib/src/bin/ai-status"
                cli.write_text("import json, sys\nprint(json.dumps(sys.argv[1:]))\n")
                execution = subprocess.run([str(plugins[0])], env=self.env, capture_output=True, text=True, timeout=5)
                self.assertEqual(execution.returncode, 0, execution.stderr)
                self.assertEqual(json.loads(execution.stdout), [command])
                self.assertFalse(self.bundle.exists())
                self.assertFalse(self.agent.exists())
        self.assertFalse(self.tool_calls("swiftc"))


if __name__ == "__main__":
    unittest.main()
