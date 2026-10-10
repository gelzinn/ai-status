"""Test release-note validation and draft publication without writing to GitHub."""

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


ROOT = Path(__file__).resolve().parents[1]


def script_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ".github/scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metadata = script_module("check_pr")
builder = script_module("build_release")


class PullRequestNotesTests(unittest.TestCase):
    def pr(self, title="feat(install): make updates recoverable", note="feat(install): restore your version if an update fails"):
        return {"title": title, "body": f"## User-facing changes\n\nBEGIN_COMMIT_OVERRIDE\n{note}\nEND_COMMIT_OVERRIDE\n"}

    def test_concrete_entries_and_breaking_changes_pass(self):
        metadata.validate(self.pr(note="feat(install): restore your version if an update fails\n\nfix(settings): preserve display preferences"))
        metadata.validate(self.pr("feat!: change the config format", "feat!: change the config format\n\nBREAKING CHANGE: migrate the config first"))

    def test_invalid_title_or_missing_notes_fail(self):
        for pr in ({"title": "improve stuff"}, {"title": "fix(install): preserve downloads", "body": "## Description\nImproved downloads."}):
            with self.subTest(pr=pr), self.assertRaises(ValueError):
                metadata.validate(pr)

    def test_placeholder_mismatched_type_or_duplicate_notes_fail(self):
        examples = [self.pr(note="feat(scope): replace with a concrete change"), self.pr(note="fix: preserve settings")]
        duplicate = self.pr()
        duplicate["body"] += "\nBEGIN_COMMIT_OVERRIDE\nfeat: another entry\nEND_COMMIT_OVERRIDE\n"
        examples.append(duplicate)
        for pr in examples:
            with self.subTest(pr=pr), self.assertRaises(ValueError):
                metadata.validate(pr)

    def test_breaking_title_needs_breaking_notes(self):
        with self.assertRaises(ValueError):
            metadata.validate(self.pr("feat!: change config", "feat: change config"))

    def test_maintenance_and_generated_release_prs_need_no_entry(self):
        metadata.validate({"title": "docs: explain installation", "body": "## User-facing changes\nNone.\n"})
        metadata.validate({"title": "chore(main): release 0.10.0", "body": ":robot: I have created a release..."})
        commented = "<!-- BEGIN_COMMIT_OVERRIDE\nfeat: replace this\nEND_COMMIT_OVERRIDE -->"
        metadata.validate({"title": "ci: add checks", "body": commented})


class DraftPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-status-release-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "HOME": str(self.root / "home"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Release Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Release Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GITHUB_REPOSITORY": "gelzinn/ai-status",
            "TEST_REAL_GIT": shutil.which("git"),
            "TEST_REPO": str(self.repo),
            "TEST_SERVER": str(self.root / "server"),
            "TEST_STATE": str(self.root / "release.json"),
            "TEST_LOG": str(self.root / "calls.jsonl"),
        }
        shutil.copytree(ROOT / "packages/lib", self.repo / "packages/lib", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "packages/shared", self.repo / "packages/shared")
        shutil.copytree(ROOT / ".github/scripts", self.repo / ".github/scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.version = (self.repo / "packages/lib/VERSION").read_text().strip()
        self.tag = "v" + self.version
        self.asset = "ai-status-" + self.tag + ".tar.gz"
        self.git("init", "-b", "main")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-m", "chore: release")
        self.git("tag", self.tag)
        # Untagged changes must not be packaged, even on a publication retry.
        (self.repo / "packages/lib/unreleased.py").write_text("invalid python ???\n")
        Path(self.env["TEST_STATE"]).write_text(json.dumps({"isDraft": True, "isPrerelease": False, "tagName": self.tag}))
        self.tool("git", """
import os, sys
args = sys.argv[1:]
if args[0] == 'fetch':
    sys.exit(0)
os.execv(os.environ['TEST_REAL_GIT'], [os.environ['TEST_REAL_GIT'], '-C', os.environ['TEST_REPO'], *args])
""")
        self.tool("gh", """
import json, os, pathlib, shutil, sys
args = sys.argv[1:]
with open(os.environ['TEST_LOG'], 'a') as out:
    out.write(json.dumps(args) + '\\n')
state = pathlib.Path(os.environ['TEST_STATE'])
server = pathlib.Path(os.environ['TEST_SERVER'])
action = args[1]
if action == 'view':
    print(state.read_text())
elif action == 'upload':
    server.mkdir(exist_ok=True)
    for name in args[3:5]:
        source = pathlib.Path(name)
        shutil.copyfile(source, server / source.name)
        if os.environ.get('TEST_FAIL_UPLOAD'):
            sys.exit(1)
elif action == 'download':
    target = pathlib.Path(args[args.index('--dir') + 1])
    for index, argument in enumerate(args):
        if argument == '--pattern':
            name = args[index + 1]
            shutil.copyfile(server / name, target / name)
            if name.endswith('.tar.gz') and os.environ.get('TEST_CORRUPT_DOWNLOAD'):
                with (target / name).open('ab') as out:
                    out.write(b'corrupt')
elif action == 'edit':
    assert '--draft=false' in args and '--latest' in args
    data = json.loads(state.read_text())
    data['isDraft'] = False
    state.write_text(json.dumps(data))
else:
    sys.exit('Unexpected gh command')
""")

    def tool(self, name, body):
        script = self.bin / name
        script.write_text("#!" + sys.executable + "\n" + body)
        script.chmod(0o755)

    def git(self, *args):
        return subprocess.run([self.env["TEST_REAL_GIT"], "-C", str(self.repo), *args], env=self.env,
                              check=True, capture_output=True)

    def publish(self):
        return subprocess.run(["bash", ".github/scripts/publish_release.sh"], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, timeout=30)

    def state(self):
        return json.loads(Path(self.env["TEST_STATE"]).read_text())

    def actions(self):
        return [json.loads(line)[1] for line in Path(self.env["TEST_LOG"]).read_text().splitlines()]

    def test_exact_tag_is_published_only_after_uploaded_bytes_are_verified(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.actions(), ["view", "upload", "download", "edit"])
        self.assertFalse(self.state()["isDraft"])
        with tarfile.open(Path(self.env["TEST_SERVER"]) / self.asset) as archive:
            self.assertNotIn("packages/lib/unreleased.py", archive.getnames())

    def test_partial_upload_can_be_retried_without_publishing_early(self):
        self.env["TEST_FAIL_UPLOAD"] = "1"
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.state()["isDraft"])
        self.assertNotIn("edit", self.actions())
        del self.env["TEST_FAIL_UPLOAD"]
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.state()["isDraft"])

    def test_corrupt_uploaded_bytes_keep_release_as_a_draft(self):
        self.env["TEST_CORRUPT_DOWNLOAD"] = "1"
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.state()["isDraft"])
        self.assertNotIn("edit", self.actions())

    def test_published_release_is_left_untouched_on_rerun(self):
        state = self.state()
        state["isDraft"] = False
        Path(self.env["TEST_STATE"]).write_text(json.dumps(state))
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.actions(), ["view"])
        self.assertFalse(Path(self.env["TEST_SERVER"]).exists())

    def test_package_is_deterministic_lean_and_has_a_matching_checksum(self):
        source = self.root / "export"
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(self.git("archive", self.tag).stdout)) as archive:
            archive.extractall(source, filter="data")
        (source / "packages/lib/__pycache__").mkdir()
        (source / "packages/lib/__pycache__/ignored.pyc").write_bytes(b"cache")
        (source / "apps/web").mkdir(parents=True)
        (source / "apps/web/unreleased.txt").write_text("web only")
        first = builder.build(source, self.root / "first", self.version)
        second = builder.build(source, self.root / "second", self.version)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with tarfile.open(first) as archive:
            names = archive.getnames()
        self.assertTrue(all(name.startswith(("packages/lib/", "packages/shared/")) for name in names))
        self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))
        self.assertEqual((first.parent / "SHA256SUMS").read_text(), hashlib.sha256(first.read_bytes()).hexdigest() + "  " + first.name + "\n")
        with self.assertRaises(ValueError):
            builder.build(source, self.root / "wrong", "99.99.99")


if __name__ == "__main__":
    unittest.main()
