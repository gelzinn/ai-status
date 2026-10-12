"""Version metadata works in checkouts, lean installs and frozen desktop builds."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


LIB = Path(__file__).resolve().parents[1]


class ProductVersionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="AI Status version é ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.lib = self.root / "packages/lib"
        self.core = self.lib / "src/core"
        self.core.mkdir(parents=True)
        for name in ("__init__.py", "paths.py"):
            shutil.copyfile(LIB / "src/core" / name, self.core / name)
        shutil.copyfile(LIB / "config.sh", self.lib / "config.sh")

    def run_core(self, *, frozen=None, extra=""):
        setup = ""
        if frozen is not None:
            setup = f"sys.frozen = True; sys._MEIPASS = {str(frozen)!r}; "
        return subprocess.run([sys.executable, "-c",
            "import sys,json; sys.path.insert(0, sys.argv[1]); " + setup +
            "import core; from core import paths; " + extra +
            "print(json.dumps({'version':core.__version__, 'root':str(paths.PROJECT_ROOT), 'lib':str(paths.LIB_DIR)}))",
            str(self.lib / "src")], env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, timeout=10)

    def test_source_manifest_is_authoritative_over_legacy_and_nested_manifests(self):
        (self.root / "package.json").write_text(json.dumps({"version": "1.2.3"}))
        (self.lib / "VERSION").write_text("9.9.9\n")
        (self.lib / "package.json").write_text(json.dumps({"version": "8.8.8"}))
        result = self.run_core()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"version": "1.2.3", "root": str(self.root.resolve()), "lib": str(self.lib.resolve())})

    def test_legacy_only_installation_keeps_its_original_version(self):
        (self.lib / "VERSION").write_text("0.9.0\n")
        result = self.run_core()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["version"], "0.9.0")

    def test_present_invalid_manifest_never_falls_back_to_a_valid_legacy_file(self):
        (self.lib / "VERSION").write_text("0.9.0\n")
        for data in ("{invalid", "null", "[]", "{}", '{"version":null}', '{"version":1}',
                     '{"version":"1.2"}', '{"version":"01.2.3"}', '{"version":"v1.2.3"}',
                     '{"version":"1.2.3-beta.1"}', '{"version":" 1.2.3 "}'):
            with self.subTest(data=data):
                (self.root / "package.json").write_text(data)
                result = self.run_core()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_missing_metadata_keeps_help_import_compatible_but_strict_reads_fail(self):
        result = self.run_core()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["version"], "0.0.0")
        strict = self.run_core(extra="core.read_version(required=True); ")
        self.assertNotEqual(strict.returncode, 0)
        self.assertIn("VERSION", strict.stderr)

    def test_frozen_windows_reads_manifest_at_meipass_root(self):
        frozen = self.root / "_internal"
        (frozen / "lib").mkdir(parents=True)
        (self.root / "package.json").write_text('{"version":"9.9.9"}')
        (frozen / "package.json").write_text('{"version":"1.2.4"}')
        (frozen / "lib/VERSION").write_text("8.8.8")
        result = self.run_core(frozen=frozen)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"version": "1.2.4", "root": str(frozen), "lib": str(frozen / "lib")})

    def test_frozen_legacy_fallback_and_invalid_manifest_use_the_same_rules(self):
        frozen = self.root / "_internal"
        (frozen / "lib").mkdir(parents=True)
        (frozen / "lib/VERSION").write_text("0.8.0")
        legacy = self.run_core(frozen=frozen)
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertEqual(json.loads(legacy.stdout)["version"], "0.8.0")
        (frozen / "package.json").write_text('{"version":"invalid"}')
        self.assertNotEqual(self.run_core(frozen=frozen).returncode, 0)

    @unittest.skipIf(sys.platform == "win32", "Shell configuration is used only by Unix installers")
    def test_shell_config_uses_validated_manifest_without_node(self):
        (self.root / "package.json").write_text('{"version":"1.2.5"}')
        (self.lib / "VERSION").write_text("0.9.0")
        command = ["bash", "-c", 'source "$1" && printf "%s" "$VERSION"', "bash", str(self.lib / "config.sh")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "1.2.5")
        (self.root / "package.json").write_text('{"version":"invalid"}')
        invalid = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(invalid.stdout, "")


if __name__ == "__main__":
    unittest.main()
