"""Regressions for platform isolation and GitHub's PR/push diff semantics."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/ci_selection.py"
spec = importlib.util.spec_from_file_location("ci_selection", SCRIPT)
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


class AffectedChecksTests(unittest.TestCase):
    def selected(self, *files):
        return selection.select_jobs(files)

    def test_readme_and_contributor_docs_need_no_builds(self):
        self.assertEqual(self.selected("README.md", "CONTRIBUTING.md", "docs/development/windows.md",
                                       "docs/screenshots/windows-usage.png", "packages/lib/assets/README.md"), set())

    def test_web_code_and_content_only_build_the_website(self):
        for filename in ("apps/web/src/app/page.tsx", "apps/web/content/providers/codex.md",
                         "apps/web/package.json", "packages/shared/providers/providers.ts",
                         "packages/shared/package.json", "package-lock.json"):
            with self.subTest(filename=filename):
                self.assertEqual(self.selected(filename), {"web-build"})

    def test_guides_read_by_the_website_still_build_it(self):
        for filename in ("LINUX.md", "WINDOWS.md", "MACOS.md", "LLMS.md"):
            with self.subTest(filename=filename):
                self.assertEqual(self.selected("packages/lib/" + filename), {"web-build"})

    def test_windows_changes_do_not_build_macos_linux_or_web(self):
        for filename in ("packages/lib/windows/build.ps1", "packages/lib/windows/ai-status.spec",
                         "packages/lib/src/windows.py", "packages/lib/src/core/tray.py",
                         "packages/lib/src/core/windows_http.py", "packages/lib/windows/requirements.txt"):
            with self.subTest(filename=filename):
                jobs = self.selected(filename)
                self.assertIn("windows-package", jobs)
                self.assertTrue(jobs.isdisjoint({"macos-native", "macos-installer", "installer", "qml-syntax", "web-build"}))

    def test_macos_changes_do_not_build_windows_linux_or_web(self):
        for filename in ("packages/lib/macos/AIStatus.swift", "packages/lib/macos/Info.plist",
                         "packages/lib/src/core/macos.py", "packages/lib/src/core/macos_credentials.py",
                         "packages/lib/src/core/swiftbar.py", "packages/lib/src/core/swiftbar_frames.py"):
            with self.subTest(filename=filename):
                jobs = self.selected(filename)
                self.assertIn("macos-native", jobs)
                self.assertTrue(jobs.isdisjoint({"windows-package", "installer", "qml-syntax", "web-build"}))

    def test_qml_changes_only_validate_qml_and_the_library_archive(self):
        self.assertEqual(self.selected("packages/lib/quickshell/Panel.qml", "packages/lib/quickshell/StableList.js"),
                         {"qml-syntax", "release-package"})
        self.assertEqual(self.selected("packages/lib/tests/qml/tst_Pages.qml"), {"qml-syntax"})

    def test_linux_installer_is_also_a_web_input(self):
        jobs = self.selected("packages/lib/install.sh")
        self.assertTrue({"lint", "installer", "web-build"}.issubset(jobs))
        self.assertTrue(jobs.isdisjoint({"windows-package", "macos-native", "macos-installer", "qml-syntax"}))
        self.assertEqual(self.selected("packages/lib/update-omarchy.sh"),
                         {"lint", "python-tests", "installer", "release-package"})
        self.assertEqual(self.selected("packages/lib/tests/test_omarchy_update.py"),
                         {"python-tests", "installer"})

    def test_macos_installer_does_not_run_the_linux_installer_or_windows_build(self):
        jobs = self.selected("packages/lib/install-macos.sh")
        self.assertTrue({"lint", "macos-installer", "macos-native", "web-build"}.issubset(jobs))
        self.assertTrue(jobs.isdisjoint({"installer", "windows-package", "qml-syntax"}))

    def test_shared_backend_runs_checks_for_every_runtime(self):
        for filename in ("packages/lib/src/core/config.py", "packages/lib/src/core/quickshell.py",
                         "packages/lib/src/core/render.py", "packages/lib/src/providers/codex/query.py"):
            with self.subTest(filename=filename):
                jobs = self.selected(filename)
                self.assertTrue({"python-syntax", "python-tests", "windows-package", "macos-native",
                                 "installer", "macos-installer", "release-package"}.issubset(jobs))
                self.assertNotIn("web-build", jobs)

    def test_provider_registry_affects_the_website_and_all_runtimes(self):
        jobs = self.selected("packages/shared/providers/providers.json")
        self.assertTrue({"web-build", "python-tests", "windows-package", "macos-native", "installer"}.issubset(jobs))

    def test_assets_used_by_native_panels_validate_all_consumers(self):
        jobs = self.selected("packages/lib/assets/app.png", "packages/lib/assets/panel-icons.json")
        self.assertTrue({"windows-package", "macos-native", "qml-syntax"}.issubset(jobs))
        self.assertNotIn("web-build", jobs)

    def test_packaged_licenses_are_not_treated_as_plain_documentation(self):
        for filename in ("LICENSE", "packages/lib/windows/THIRD_PARTY.md",
                         "packages/lib/assets/fonts/OFL.txt", "packages/lib/quickshell/LUCIDE-LICENSE"):
            with self.subTest(filename=filename):
                self.assertIn("windows-package", self.selected(filename))

    def test_release_and_plugin_metadata_have_distinct_consumers(self):
        self.assertTrue({"windows-package", "macos-native", "installer", "web-build", "release-config"}
                        .issubset(self.selected("package.json")))
        self.assertTrue(self.selected("manifest.json").isdisjoint({"windows-package", "macos-native", "web-build"}))
        self.assertEqual(self.selected("release-please-config.json"), {"release-config"})

    def test_release_scripts_do_not_trigger_native_builds(self):
        self.assertEqual(self.selected(".github/scripts/publish_release.sh"), {"lint", "release-tests"})
        self.assertEqual(self.selected(".github/scripts/release_please.cjs"), {"release-config"})

    def test_platform_test_changes_do_not_build_other_platforms(self):
        self.assertEqual(self.selected("tests/test_installer.py"), {"installer"})
        self.assertEqual(self.selected("tests/test_macos_installer.py"), {"macos-installer"})
        self.assertEqual(self.selected("tests/test_macos_size.py"), {"macos-installer", "macos-native"})
        self.assertEqual(self.selected("packages/lib/tests/test_macos.py"), {"python-tests", "macos-native"})
        self.assertEqual(self.selected("packages/lib/tests/test_tray.py"), {"python-tests", "windows-package"})

    def test_workflow_changes_validate_the_affected_workflow(self):
        self.assertEqual(self.selected(".github/workflows/ci.yml"), selection.ALL)
        self.assertEqual(self.selected(".github/scripts/ci_selection.py"), selection.ALL)
        self.assertEqual(self.selected(".github/workflows/windows.yml"), {"windows-package"})
        self.assertEqual(self.selected("tests/test_ci_selection.py"), set())

    def test_unknown_code_and_unavailable_diffs_run_every_check(self):
        self.assertEqual(self.selected("new-platform/build.py"), selection.ALL)
        self.assertEqual(selection.select_jobs(None), selection.ALL)

    def test_mixed_changes_combine_the_affected_checks(self):
        self.assertEqual(self.selected("README.md", "apps/web/src/app/page.tsx", "packages/lib/quickshell/Panel.qml"),
                         {"web-build", "qml-syntax", "release-package"})


class GitDiffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-status-ci-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "CI test")
        self.git("config", "user.email", "ci@example.invalid")
        self.write("README.md", "initial\n")
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def write(self, filename, text="test\n"):
        path = self.root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "test change")
        return self.git("rev-parse", "HEAD")

    def pr_event(self, base, head):
        return {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}

    def test_pr_diff_excludes_changes_only_on_the_base_branch(self):
        self.git("checkout", "-qb", "feature")
        self.write("apps/web/src/app/page.tsx")
        head = self.commit()
        self.git("checkout", "-q", "main")
        self.write("packages/lib/windows/build.ps1")
        base = self.commit()
        files = selection.changed_files("pull_request", self.pr_event(base, head), self.root)
        self.assertEqual(files, ["apps/web/src/app/page.tsx"])
        self.assertEqual(selection.select_jobs(files), {"web-build"})

    def test_push_diff_includes_all_commits_in_the_push(self):
        self.write("packages/lib/windows/build.ps1")
        self.commit()
        self.write("README.md", "updated docs\n")
        head = self.commit()
        files = selection.changed_files("push", {"before": self.base, "after": head}, self.root)
        self.assertIn("packages/lib/windows/build.ps1", files)
        self.assertIn("windows-package", selection.select_jobs(files))

    def test_deleted_files_and_both_sides_of_renames_are_checked(self):
        self.write("packages/lib/windows/launcher.py")
        base = self.commit()
        self.git("mv", "packages/lib/windows/launcher.py", "README-new.md")
        head = self.commit()
        files = selection.changed_files("pull_request", self.pr_event(base, head), self.root)
        self.assertIn("packages/lib/windows/launcher.py", files)
        self.assertIn("README-new.md", files)
        self.assertIn("windows-package", selection.select_jobs(files))

    def test_large_diffs_are_not_limited_to_the_first_300_files(self):
        for index in range(305):
            self.write(f"docs/{index:03}.md")
        self.write("packages/lib/windows/build.ps1")
        head = self.commit()
        files = selection.changed_files("pull_request", self.pr_event(self.base, head), self.root)
        self.assertEqual(len(files), 306)
        self.assertIn("windows-package", selection.select_jobs(files))

    def test_paths_with_newlines_are_not_split_into_multiple_changes(self):
        filename = "docs/a\npackages/lib/windows/build.ps1.md"
        self.write(filename)
        head = self.commit()
        files = selection.changed_files("push", {"before": self.base, "after": head}, self.root)
        self.assertEqual(files, [filename])
        self.assertEqual(selection.select_jobs(files), set())

    def test_missing_history_invalid_refs_and_initial_push_run_everything(self):
        for before in ("f" * 40, "0" * 40, "--output=/tmp/invalid", None):
            with self.subTest(before=before):
                files = selection.changed_files("push", {"before": before, "after": self.base}, self.root)
                self.assertIsNone(files)
                self.assertEqual(selection.select_jobs(files), selection.ALL)

    def test_manual_runs_validate_everything(self):
        self.assertIsNone(selection.changed_files("workflow_dispatch", {}, self.root))

    def test_script_writes_explicit_boolean_outputs_and_a_summary(self):
        self.write("README.md", "updated docs\n")
        head = self.commit()
        event = self.root / "event.json"
        event.write_text(json.dumps(self.pr_event(self.base, head)))
        output, summary = self.root / "outputs", self.root / "summary"
        subprocess.run([sys.executable, str(SCRIPT), str(event)], cwd=self.root, check=True, capture_output=True,
                       env={**os.environ, "GITHUB_EVENT_NAME": "pull_request", "GITHUB_OUTPUT": str(output),
                            "GITHUB_STEP_SUMMARY": str(summary)})
        values = dict(line.split("=") for line in output.read_text().splitlines())
        self.assertEqual(set(values), set(selection.JOBS))
        self.assertEqual(set(values.values()), {"false"})
        self.assertIn("| windows-package | Skip |", summary.read_text())


if __name__ == "__main__":
    unittest.main()
