from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core import about, paths


class ProjectInfoTests(unittest.TestCase):
    def setUp(self):
        about.project_info.cache_clear()
        self.addCleanup(about.project_info.cache_clear)

    def test_packaged_commit_is_available_without_git(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "BUILD_COMMIT").write_text("0123456789abcdef\n")
            with patch.object(paths, "LIB_DIR", Path(directory)), patch.object(about.sys, "frozen", True, create=True), patch.object(subprocess, "check_output") as git:
                info = about.project_info()
        self.assertEqual(info["commit"], "01234567")
        self.assertEqual(info["license"], "MIT")
        self.assertEqual(info["github"], about.GITHUB)
        git.assert_not_called()

    def test_source_commit_and_missing_git_fallback(self):
        with patch.object(subprocess, "check_output", return_value="abcdef0123456789\n"):
            self.assertEqual(about.project_info()["commit"], "abcdef01")
        about.project_info.cache_clear()
        with patch.object(subprocess, "check_output", side_effect=FileNotFoundError):
            self.assertEqual(about.project_info()["commit"], "Unavailable")
