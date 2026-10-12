"""Exercise the real installer against local tagged repos, without network or Waybar."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "packages/lib/install.sh"
REAL_GIT = shutil.which("git")
REAL_BASH = shutil.which("bash")
REAL_PYTHON = sys.executable
ROOT = INSTALLER.parents[2]
spec = importlib.util.spec_from_file_location("build_release", ROOT / ".github/scripts/build_release.py")
release_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_builder)


class StableInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-status-installer-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.installed = self.home / ".local/share/ai-status"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # A restricted PATH prevents the tests from finding/restarting a real
        # Waybar, while still exercising real tags, archives and file operations.
        for name in ("bash", "python3", "dirname", "cat", "mkdir", "rm", "cp", "mv", "rmdir", "mktemp", "ln"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": str(self.bin),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Installer Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Installer Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "TEST_REAL_GIT": REAL_GIT,
            "TEST_REPO": str(self.root / "repo"),
            "TEST_CURL_LOG": str(self.root / "curl.log"),
            "TEST_ASSETS": str(self.root / "assets"),
            "TEST_RESPONSE": json.dumps({"tag_name": "v0.10.0", "draft": False, "prerelease": False}),
        }
        self.repo = Path(self.env["TEST_REPO"])
        self.repo.mkdir()
        self.git("init", "-b", "main")
        lib = self.repo / "packages/lib"
        shutil.copytree(ROOT / "packages/lib", lib, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "packages/shared", self.repo / "packages/shared")
        (self.repo / "apps/web").mkdir(parents=True)
        (lib / "check.sh").write_text("#!/bin/bash\nexit 0\n")
        shutil.copyfile(INSTALLER, lib / "install.sh")
        (self.repo / "packages/shared/provider.txt").write_text("metadata\n")
        (self.repo / "apps/web/unreleased.txt").write_text("website\n")
        for version in ("0.9.0", "0.10.0", "0.11.0"):
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
                if version == "0.9.0":
                    self.make_legacy_release(version)
                else:
                    release_builder.build(self.repo, self.root / "assets" / ("v" + version), version)
        self.git("tag", "v9.9.9")  # Deliberately disagrees with canonical metadata.
        self.bootstrap = self.root / "bootstrap/install.sh"
        self.bootstrap.parent.mkdir()
        shutil.copyfile(INSTALLER, self.bootstrap)
        self.write_tool("curl", """
import os, pathlib, subprocess, sys
args = sys.argv[1:]
url = args[-1]
with open(os.environ['TEST_CURL_LOG'], 'a') as log:
    log.write(url + '\\n')
if '/releases/latest' in url:
    print(os.environ['TEST_RESPONSE'])
    sys.exit(int(os.environ.get('TEST_CURL_EXIT', '0')))
output = pathlib.Path(args[args.index('--output') + 1])
if '/releases/download/' in url:
    tag, name = url.split('/releases/download/')[1].split('/')
    asset = pathlib.Path(os.environ['TEST_ASSETS']) / tag / name
    exists = asset.is_file() and not os.environ.get('TEST_LEGACY')
    if exists:
        output.write_bytes(asset.read_bytes())
    if '--write-out' in args:
        print('200' if exists else '404', end='')
    sys.exit(0 if exists else 22)
if 'codeload.github.com' in url:
    tag = url.rsplit('/', 1)[1]
    result = subprocess.run([os.environ['TEST_REAL_GIT'], '-C', os.environ['TEST_REPO'],
                             'archive', '--format=tar.gz', '--prefix=source/', tag], capture_output=True)
    output.write_bytes(result.stdout)
    sys.exit(result.returncode)
sys.exit('Unexpected download URL: ' + url)
""")
        self.write_tool("git", """
import os, shutil, subprocess, sys
args = sys.argv[1:]
if args[0] == 'clone':
    sys.exit('Public installs must download release packages, not clone git')
result = subprocess.run([os.environ['TEST_REAL_GIT'], *args])
sys.exit(result.returncode)
""")

    def write_tool(self, name, body):
        path = self.bin / name
        if path.is_symlink():
            path.unlink()
        path.write_text("#!" + REAL_PYTHON + "\n" + body)
        path.chmod(0o755)

    def git(self, *args):
        return subprocess.run([REAL_GIT, "-C", str(self.repo), *args],
                              env=self.env, check=True, capture_output=True, text=True)

    def run_installer(self, *args, local=False, pipe_cwd=None, checks=False, display_flags=True):
        script = self.repo / "packages/lib/install.sh" if local else self.bootstrap
        invocation = [REAL_BASH, str(script)] if pipe_cwd is None else [REAL_BASH, "-s", "--"]
        return subprocess.run(
            [*invocation, "--no-interactive", *([] if checks else ["--skip-check"]),
             "--configure-waybar", "false", *(["--icon-mode", "off"] if display_flags else []), *args],
            cwd=pipe_cwd or self.root, env=self.env, capture_output=True, text=True,
            input=INSTALLER.read_text() if pipe_cwd else None, timeout=30,
        )

    def assert_installed(self, version):
        self.assertEqual(self.installed_version(self.installed), version)
        self.assertEqual((self.installed / "packages/lib/marker").read_text(), version)
        self.assertTrue((self.installed / "packages/shared/provider.txt").exists())
        self.assertFalse((self.installed / "apps").exists())
        self.assertFalse((self.installed / ".git").exists())
        self.assertTrue((self.home / ".local/bin/ai-status").is_symlink())

    def installed_version(self, root):
        manifest = root / "package.json"
        return json.loads(manifest.read_text())["version"] if manifest.exists() else (root / "packages/lib/VERSION").read_text().strip()

    def make_legacy_release(self, version):
        directory = self.root / "assets" / ("v" + version)
        directory.mkdir(parents=True)
        archive = directory / f"ai-status-v{version}.tar.gz"
        with tarfile.open(archive, "w:gz") as package:
            package.add(self.repo / "packages", arcname="packages")
        (directory / "SHA256SUMS").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")

    def seed_existing_install(self):
        self.installed.mkdir(parents=True)
        (self.installed / "keep").write_text("existing install")

    def assert_failed_preserving_install(self, *args):
        result = self.run_installer(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.installed / "keep").read_text(), "existing install")
        self.assertFalse((self.installed.parent / ".ai-status-update.lock").exists())
        self.assertFalse(list(self.installed.parent.glob(".ai-status-stage.*")))

    def test_latest_uses_published_tag_instead_of_main(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.10.0")
        self.assertEqual((self.root / "curl.log").read_text().splitlines()[0],
                         "https://api.github.com/repos/gelzinn/ai-status/releases/latest")

    def test_canonical_manifest_is_staged_and_version_file_is_optional(self):
        self.rewrite_package(lambda member: member.name != "packages/lib/VERSION")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.10.0")
        self.assertEqual(json.loads((self.installed / "package.json").read_text())["version"], "0.10.0")
        self.assertFalse((self.installed / "packages/lib/VERSION").exists())

    def test_invalid_canonical_manifest_does_not_fall_back_to_legacy_version(self):
        self.seed_existing_install()
        directory = self.root / "assets/v0.10.0"
        archive = directory / "ai-status-v0.10.0.tar.gz"
        replacement = io.BytesIO()
        with tarfile.open(archive, "r:gz") as source, tarfile.open(fileobj=replacement, mode="w:gz") as target:
            for member in source:
                if member.name == "package.json":
                    data = b'{"version":"invalid"}'
                    member.size = len(data)
                    target.addfile(member, io.BytesIO(data))
                else:
                    target.addfile(member, source.extractfile(member))
        archive.write_bytes(replacement.getvalue())
        (directory / "SHA256SUMS").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
        self.assert_failed_preserving_install()

    def test_upgrade_and_rollback_use_exact_versions(self):
        for args, version in ((["--version", "0.9.0"], "0.9.0"),
                              ([], "0.10.0"), (["--version", "v0.9.0"], "0.9.0")):
            result = self.run_installer(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assert_installed(version)

    def test_explicit_version_does_not_need_release_api(self):
        self.env["TEST_CURL_EXIT"] = "22"
        result = self.run_installer("--version", "v0.9.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.9.0")
        self.assertNotIn('/releases/latest', (self.root / "curl.log").read_text())

    def test_failed_api_even_with_valid_json_preserves_install(self):
        self.seed_existing_install()
        self.env["TEST_CURL_EXIT"] = "22"
        self.assert_failed_preserving_install()

    def test_invalid_release_responses_preserve_install(self):
        self.seed_existing_install()
        for response in ("not JSON", "{}", '{"tag_name": "main"}',
                         '{"tag_name": "v0.10.0-beta.1"}',
                         '{"tag_name": "v0.10.0", "draft": true}',
                         '{"tag_name": "v0.10.0", "prerelease": true}'):
            with self.subTest(response=response):
                self.env["TEST_RESPONSE"] = response
                self.assert_failed_preserving_install()

    def test_missing_tag_preserves_install(self):
        self.seed_existing_install()
        self.assert_failed_preserving_install("--version", "v0.99.0")

    def test_version_mismatch_preserves_install(self):
        self.seed_existing_install()
        self.assert_failed_preserving_install("--version", "v9.9.9")

    def test_incomplete_release_preserves_install(self):
        self.seed_existing_install()
        self.rewrite_package(lambda member: not member.name.startswith("packages/shared/"))
        self.assert_failed_preserving_install()

    def rewrite_package(self, include=lambda member: True):
        directory = self.root / "assets/v0.10.0"
        archive = directory / "ai-status-v0.10.0.tar.gz"
        replacement = io.BytesIO()
        with tarfile.open(archive, "r:gz") as source, tarfile.open(fileobj=replacement, mode="w:gz") as target:
            for member in source:
                if include(member):
                    target.addfile(member, source.extractfile(member))
        archive.write_bytes(replacement.getvalue())
        (directory / "SHA256SUMS").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")

    def test_package_install_does_not_require_git(self):
        (self.bin / "git").unlink()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.10.0")

    def test_legacy_release_uses_a_tag_archive_without_git(self):
        self.env["TEST_LEGACY"] = "1"
        (self.bin / "git").unlink()
        result = self.run_installer("--version", "v0.9.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.9.0")
        self.assertFalse((self.installed / "package.json").exists())

    def test_legacy_local_checkout_omits_its_unversioned_workspace_manifest(self):
        self.git("checkout", "v0.9.0")
        result = self.run_installer(local=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.9.0")
        self.assertFalse((self.installed / "package.json").exists())

    def test_bad_checksum_preserves_install(self):
        self.seed_existing_install()
        (self.root / "assets/v0.10.0/SHA256SUMS").write_text("0" * 64 + "  ai-status-v0.10.0.tar.gz\n")
        self.assert_failed_preserving_install()

    def test_updates_preserve_preferences_and_explicit_flags_override_them(self):
        result = self.run_installer("--version", "v0.9.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path = self.home / ".config/ai-status/selected.json"
        saved = {"icon_mode": "logo", "show_provider": False, "show_model": False,
                 "show_metric": True, "show_pct": False, "provider": "codex", "idx": 3,
                 "metric": "weekly", "custom": "keep this"}
        path.write_text(json.dumps(saved))
        result = self.run_installer(display_flags=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(path.read_text()), saved)
        result = self.run_installer()  # Explicit flags take precedence.
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(path.read_text()), {**saved, "icon_mode": "off"})

    def test_offline_rollback_restores_previous_version(self):
        for args in (("--version", "v0.9.0"), (), ("--rollback",)):
            result = self.run_installer(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.9.0")
        previous = self.home / ".local/share/ai-status.previous"
        self.assertEqual(self.installed_version(previous), "0.10.0")
        self.assertTrue((previous / "package.json").exists())
        self.assertFalse((self.installed / "package.json").exists())

    def test_internal_setup_without_git_preserves_settings(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.bin / "git").unlink()
        prefs = self.home / ".config/ai-status/selected.json"
        before = prefs.read_bytes()
        result = subprocess.run([REAL_BASH, str(self.installed / "packages/lib/install.sh"), "--no-interactive", "--skip-check"],
                                env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(prefs.read_bytes()), json.loads(before))
        self.assert_installed("0.10.0")

    def test_existing_lock_prevents_concurrent_update(self):
        self.seed_existing_install()
        lock = self.installed.parent / ".ai-status-update.lock"
        lock.mkdir()
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Another installation is running", result.stderr)
        self.assertTrue(lock.exists())
        self.assertEqual((self.installed / "keep").read_text(), "existing install")

    def test_failed_activation_restores_previous_install(self):
        self.seed_existing_install()
        self.env["TEST_REAL_MV"] = shutil.which("mv")
        self.write_tool("mv", """
import os, sys
args = sys.argv[1:]
if any('.ai-status-stage.' in arg for arg in args):
    sys.exit(1)
os.execv(os.environ['TEST_REAL_MV'], [os.environ['TEST_REAL_MV'], *args])
""")
        self.assert_failed_preserving_install()

    def test_failed_setup_restores_library_preferences_and_symlinks(self):
        result = self.run_installer("--version", "v0.9.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path = self.home / ".config/ai-status/selected.json"
        before = path.read_bytes()
        alias = self.home / ".local/bin/waybar-ai-status"
        alias.unlink()
        alias.symlink_to("custom-command")
        self.env["TEST_REAL_PYTHON"] = REAL_PYTHON
        self.write_tool("python3", """
import os, subprocess, sys
args = sys.argv[1:]
if len(args) > 1 and args[1].endswith('/selected.json'):
    result = subprocess.run([os.environ['TEST_REAL_PYTHON'], *args], input=sys.stdin.read(), text=True)
    sys.exit(1)
os.execv(os.environ['TEST_REAL_PYTHON'], [os.environ['TEST_REAL_PYTHON'], *args])
""")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.9.0")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(os.readlink(alias), "custom-command")

    def test_failed_waybar_setup_restores_config_and_its_original_backup(self):
        result = self.run_installer("--version", "v0.9.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        prefs = self.home / ".config/ai-status/selected.json"
        original_prefs = prefs.read_bytes()
        config = self.home / ".config/waybar/config.jsonc"
        config.parent.mkdir(parents=True)
        config.write_text('{"modules-right": ["clock"]}\n')
        backup = config.with_name(config.name + ".ai-status.bak")
        backup.write_text("an earlier backup\n")
        original_config, original_backup = config.read_bytes(), backup.read_bytes()
        self.write_tool("waybar", "")
        self.env["TEST_REAL_PYTHON"] = REAL_PYTHON
        self.write_tool("python3", """
import os, subprocess, sys
args = sys.argv[1:]
if len(args) > 1 and args[1].endswith('/waybar/config.jsonc'):
    subprocess.run([os.environ['TEST_REAL_PYTHON'], *args], input=sys.stdin.read(), text=True, check=True)
    sys.exit(1)
os.execv(os.environ['TEST_REAL_PYTHON'], [os.environ['TEST_REAL_PYTHON'], *args])
""")
        result = self.run_installer("--configure-waybar", "true")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.9.0")
        self.assertEqual(config.read_bytes(), original_config)
        self.assertEqual(backup.read_bytes(), original_backup)
        self.assertEqual(prefs.read_bytes(), original_prefs)

    def test_failed_update_restores_legacy_paths(self):
        old_install = self.home / ".local/share/omarchy-ai-status"
        old_install.mkdir(parents=True)
        (old_install / "keep").write_text("existing install")
        old_config = self.home / ".config/waybar-ai-status"
        old_config.mkdir(parents=True)
        prefs = old_config / "selected.json"
        prefs.write_text('{"icon_mode":"logo","provider":"codex"}')
        original = prefs.read_bytes()
        self.env["TEST_CURL_EXIT"] = "22"
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((old_install / "keep").read_text(), "existing install")
        self.assertEqual(prefs.read_bytes(), original)
        self.assertFalse(self.installed.exists())
        self.assertFalse((self.home / ".config/ai-status").exists())

    def test_failed_requirements_do_not_replace_install(self):
        self.seed_existing_install()
        self.env["TEST_LEGACY"] = "1"
        (self.repo / "packages/lib/check.sh").write_text("#!/bin/bash\nexit 1\n")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-m", "fix: fail requirements")
        self.git("tag", "v0.11.0")
        result = self.run_installer("--version", "v0.11.0", checks=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.installed / "keep").read_text(), "existing install")

    def test_invalid_version_arguments_preserve_install(self):
        self.seed_existing_install()
        for args in (("--version",), ("--version", ""), ("--version", "main"),
                     ("--version", "v0.10.0-beta.1")):
            with self.subTest(args=args):
                self.assert_failed_preserving_install(*args)

    def test_local_checkout_still_installs_unreleased_working_tree(self):
        result = self.run_installer(local=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.11.0")
        self.assertFalse((self.root / "curl.log").exists())

    def test_piped_installer_inside_checkout_still_uses_stable_release(self):
        for directory in (self.repo, self.repo / "packages/lib"):
            with self.subTest(directory=directory):
                result = self.run_installer(pipe_cwd=directory)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_installed("0.10.0")

    def test_piped_installer_inside_installed_copy_performs_update(self):
        result = self.run_installer("--version", "v0.9.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.run_installer(pipe_cwd=self.installed / "packages/lib")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.10.0")


if __name__ == "__main__":
    unittest.main()
