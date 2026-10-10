"""Exercise the real installer against local tagged repos, without network or Waybar."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "packages/lib/install.sh"
REAL_GIT = shutil.which("git")
REAL_BASH = shutil.which("bash")


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
        # Waybar, while still exercising real git clones and file operations.
        for name in ("bash", "python3", "dirname", "cat", "mkdir", "rm", "cp", "mktemp", "ln"):
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
            "TEST_RESPONSE": json.dumps({"tag_name": "v0.10.0", "draft": False, "prerelease": False}),
        }
        self.repo = Path(self.env["TEST_REPO"])
        self.repo.mkdir()
        self.git("init", "-b", "main")
        lib = self.repo / "packages/lib"
        (lib / "src/bin").mkdir(parents=True)
        (self.repo / "packages/shared").mkdir(parents=True)
        (self.repo / "apps/web").mkdir(parents=True)
        (lib / "check.sh").write_text("#!/bin/bash\nexit 0\n")
        shutil.copyfile(INSTALLER, lib / "install.sh")
        (lib / "src/bin/ai-status").write_text("#!/bin/bash\nexit 0\n")
        (self.repo / "packages/shared/provider.txt").write_text("metadata\n")
        (self.repo / "apps/web/unreleased.txt").write_text("website\n")
        for version in ("0.9.0", "0.10.0", "0.11.0"):
            (lib / "VERSION").write_text(version + "\n")
            (lib / "marker").write_text(version)
            self.git("add", ".")
            self.git("-c", "commit.gpgsign=false", "commit", "-m", "feat: " + version)
            if version != "0.11.0":
                self.git("tag", "v" + version)
        self.git("tag", "v9.9.9")  # Deliberately disagrees with VERSION.
        self.bootstrap = self.root / "bootstrap/install.sh"
        self.bootstrap.parent.mkdir()
        shutil.copyfile(INSTALLER, self.bootstrap)
        self.write_tool("curl", """
import os, sys
with open(os.environ['TEST_CURL_LOG'], 'a') as log:
    log.write(sys.argv[-1] + '\\n')
print(os.environ['TEST_RESPONSE'])
sys.exit(int(os.environ.get('TEST_CURL_EXIT', '0')))
""")
        self.write_tool("git", """
import os, shutil, subprocess, sys
args = sys.argv[1:]
if args[0] == 'clone':
    assert '--branch' in args, 'Installer attempted an unpinned clone'
    args[-2] = os.environ['TEST_REPO']
result = subprocess.run([os.environ['TEST_REAL_GIT'], *args])
if args[0] == 'clone' and result.returncode == 0 and os.environ.get('TEST_MISSING_SHARED'):
    shutil.rmtree(os.path.join(args[-1], 'packages/shared'))
sys.exit(result.returncode)
""")

    def write_tool(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env python3\n" + body)
        path.chmod(0o755)

    def git(self, *args):
        return subprocess.run([REAL_GIT, "-C", str(self.repo), *args],
                              env=self.env, check=True, capture_output=True, text=True)

    def run_installer(self, *args, local=False, pipe_cwd=None):
        script = self.repo / "packages/lib/install.sh" if local else self.bootstrap
        invocation = [REAL_BASH, str(script)] if pipe_cwd is None else [REAL_BASH, "-s", "--"]
        return subprocess.run(
            [*invocation, "--no-interactive", "--skip-check",
             "--configure-waybar", "false", "--icon-mode", "off", *args],
            cwd=pipe_cwd or self.root, env=self.env, capture_output=True, text=True,
            input=INSTALLER.read_text() if pipe_cwd else None, timeout=30,
        )

    def assert_installed(self, version):
        self.assertEqual((self.installed / "packages/lib/VERSION").read_text().strip(), version)
        self.assertEqual((self.installed / "packages/lib/marker").read_text(), version)
        self.assertTrue((self.installed / "packages/shared/provider.txt").exists())
        self.assertFalse((self.installed / "apps").exists())
        self.assertFalse((self.installed / ".git").exists())
        self.assertTrue((self.home / ".local/bin/ai-status").is_symlink())

    def seed_existing_install(self):
        self.installed.mkdir(parents=True)
        (self.installed / "keep").write_text("existing install")

    def assert_failed_preserving_install(self, *args):
        result = self.run_installer(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.installed / "keep").read_text(), "existing install")

    def test_latest_uses_published_tag_instead_of_main(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_installed("0.10.0")
        self.assertEqual((self.root / "curl.log").read_text().strip(),
                         "https://api.github.com/repos/gelzinn/ai-status/releases/latest")

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
        self.assertFalse((self.root / "curl.log").exists())

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
        self.env["TEST_MISSING_SHARED"] = "1"
        self.assert_failed_preserving_install()

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
