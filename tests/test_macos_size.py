"""Check macOS size reporting and its enforceable production limits."""

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packages/lib/macos/size_report.py"
SPEC = importlib.util.spec_from_file_location("macos_size_report", SCRIPT)
SIZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SIZE)


class MacOSSizeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.installed = self.root / "installed"
        self.bundle = self.installed / "AI Status.app"
        self.executable = self.bundle / "Contents/MacOS/AIStatus"
        self.executable.parent.mkdir(parents=True)
        self.executable.write_bytes(b"prod")
        self.baseline = self.root / "baseline"
        self.baseline.write_bytes(b"baseline")
        (self.installed / "runtime.py").write_bytes(b"py")

    def test_measures_each_scope_without_following_symlinks(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "large").write_bytes(b"x" * 100)
        (self.installed / "external-directory").symlink_to(outside, target_is_directory=True)
        (self.installed / "external-file").symlink_to(outside / "large")
        (self.installed / "broken").symlink_to(outside / "missing")
        (self.installed / "app-alias").symlink_to(self.bundle, target_is_directory=True)
        sizes, files = SIZE.measurements(self.executable, self.bundle, self.installed, self.baseline)
        self.assertEqual(sizes, {"executable": 4, "bundle": 4, "installed": 6, "baseline": 8})
        self.assertEqual(files, [(Path("AI Status.app/Contents/MacOS/AIStatus"), 4),
                                 (Path("runtime.py"), 2)])

    def test_invalid_input_cannot_produce_a_successful_report(self):
        self.baseline.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "nonempty regular file"):
            SIZE.measurements(self.executable, self.bundle, self.installed, self.baseline)
        alias = self.root / "installed-alias"
        alias.symlink_to(self.installed, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "directory, not a symlink"):
            SIZE.tree_files(alias)
        with self.assertRaises(ValueError):
            SIZE.measurements(self.executable, self.bundle, self.root / "unrelated", self.baseline)
        with self.assertRaises(FileNotFoundError):
            SIZE.regular_file_size(self.root / "missing")

    def test_budget_boundary_and_excess(self):
        budgets = {"executable": 4, "bundle": 4, "installed": 6}
        self.assertEqual(SIZE.exceeded_budgets(dict(budgets), budgets), [])
        self.assertEqual(SIZE.exceeded_budgets({**budgets, "installed": 7}, budgets), ["installed"])

    def test_cli_preserves_report_and_summary_when_budget_fails(self):
        report = self.root / "report.txt"
        summary = self.root / "summary.md"
        summary.write_text("Earlier step\n", encoding="utf-8")
        result = subprocess.run([
            sys.executable, str(SCRIPT), "--executable", str(self.executable),
            "--bundle", str(self.bundle), "--installed", str(self.installed),
            "--baseline-executable", str(self.baseline), "--report", str(report),
            "--summary", str(summary), "--compiler", "Swift test\nTarget: test",
            "--max-executable-mib", str(3 / SIZE.MIB),
        ], capture_output=True, text=True, env={**os.environ, "GITHUB_STEP_SUMMARY": ""})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("size budget exceeded: executable", result.stderr)
        self.assertEqual(report.read_text(encoding="utf-8"), result.stdout)
        self.assertEqual(summary.read_text(encoding="utf-8"), "Earlier step\n" + result.stdout)
        self.assertIn("Production reduction: 4 bytes", result.stdout)
        self.assertIn("50.0%", result.stdout)
        self.assertIn("| FAIL |", result.stdout)

    def test_invalid_numeric_budget_is_rejected(self):
        for value in ("nan", "inf", "-1", "0"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                SIZE.mib_budget(value)


if __name__ == "__main__":
    unittest.main()
