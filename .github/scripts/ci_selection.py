"""Select checks from the complete PR or push diff, without external dependencies."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


JOBS = (
    "lint", "python-syntax", "python-tests", "installer", "macos-installer",
    "macos-native", "release-package", "release-tests", "release-config",
    "qml-syntax", "web-build", "windows-package",
)
ALL = frozenset(JOBS)
PYTHON = {"python-syntax", "python-tests", "release-package"}
RUNTIME = PYTHON | {"installer", "macos-installer", "macos-native", "windows-package"}
ASSETS = {"python-tests", "qml-syntax", "macos-native", "windows-package", "release-package"}
LINUX_INSTALLER = {"lint", "python-tests", "installer", "release-package"}
MACOS_INSTALLER = {"lint", "macos-installer", "macos-native", "release-package", "web-build"}

# These Markdown files and installers are read/served by the website.
WEB_INPUTS = {
    "packages/lib/LINUX.md", "packages/lib/MACOS.md", "packages/lib/WINDOWS.md",
    "packages/lib/LLMS.md", "packages/lib/install.sh", "packages/lib/install-macos.sh",
}
EXACT = {
    ".github/workflows/ci.yml": ALL,
    ".github/scripts/ci_selection.py": ALL,
    ".github/workflows/windows.yml": {"windows-package"},
    ".github/workflows/release.yml": {"release-tests", "release-config"},
    ".github/scripts/build_release.py": {"python-syntax", "installer", "release-tests", "release-package"},
    ".github/scripts/publish_release.sh": {"lint", "release-tests"},
    ".github/scripts/release_please.cjs": {"release-config"},
    ".github/scripts/check_pr.py": {"python-syntax", "release-tests"},
    ".github/PULL_REQUEST_TEMPLATE.md": {"release-tests"},
    "tests/test_ci_selection.py": set(),  # Always tested by pr-metadata.
    "tests/test_installer.py": {"installer"},
    "tests/test_macos_installer.py": {"macos-installer"},
    "tests/test_release_flow.py": {"release-tests"},
    "tests/test_release_config.cjs": {"release-config"},
    "tests/test_changelog.mjs": {"web-build"},
    "package.json": RUNTIME | {"release-config", "web-build"},
    "package-lock.json": {"web-build"},
    "npm-shrinkwrap.json": {"web-build"},
    "pnpm-lock.yaml": {"web-build"},
    "yarn.lock": {"web-build"},
    "bun.lock": {"web-build"},
    "bun.lockb": {"web-build"},
    "release-please-config.json": {"release-config"},
    ".release-please-manifest.json": {"release-config"},
    "manifest.json": {"python-tests", "installer", "release-config", "release-package"},
    "workspace.config": LINUX_INSTALLER,
    "packages/lib/install.sh": LINUX_INSTALLER | {"web-build"},
    "packages/lib/config.sh": LINUX_INSTALLER,
    "packages/lib/check.sh": LINUX_INSTALLER,
    "packages/lib/install-wizard.py": PYTHON | {"installer"},
    "packages/lib/install-macos.sh": MACOS_INSTALLER,
    "packages/lib/windows/requirements.txt": {"python-tests", "windows-package", "release-package"},
    "packages/lib/windows/THIRD_PARTY.md": {"windows-package", "release-package"},
    "packages/shared/providers/providers.json": (RUNTIME - {"python-syntax"}) | {"web-build"},
    "packages/lib/quickshell/LUCIDE-LICENSE": {"windows-package", "release-package"},
    "packages/lib/assets/fonts/OFL.txt": {"windows-package", "release-package"},
    "LICENSE": {"windows-package"},
}


def jobs_for_path(filename):
    """Keep platform-specific inputs separate; unknown code gets every check."""
    if filename in EXACT:
        return EXACT[filename]
    if filename in WEB_INPUTS or filename.startswith("apps/web/"):
        return {"web-build"}
    if filename.endswith(".md") or filename.startswith(("docs/", ".github/ISSUE_TEMPLATE/")):
        return set()
    if filename in {".gitignore", ".github/CODEOWNERS", ".github/FUNDING.yml"}:
        return set()
    if filename.startswith("packages/lib/src/core/"):
        name = Path(filename).name
        if name.startswith(("macos", "swiftbar")):
            return PYTHON | {"macos-native"}
        if name == "tray.py" or name.startswith("windows_"):
            return PYTHON | {"windows-package"}
        # quickshell.py and render.py also supply Windows/macOS desktop data.
        return RUNTIME
    if filename == "packages/lib/src/windows.py":
        return PYTHON | {"windows-package"}
    if filename.startswith("packages/lib/src/providers/") and filename.endswith(".sh"):
        # Windows packages exclude the legacy shell collectors.
        return LINUX_INSTALLER | {"macos-installer", "macos-native"}
    if filename.startswith(("packages/lib/src/", "packages/lib/providers/")):
        return RUNTIME
    if filename.startswith("packages/lib/windows/"):
        return {"windows-package", "release-package"}
    if filename.startswith("packages/lib/macos/"):
        return {"macos-native", "macos-installer", "release-package"}
    if filename.startswith("packages/lib/quickshell/"):
        return {"qml-syntax", "release-package"}
    if filename.startswith("packages/lib/assets/"):
        return ASSETS
    if filename.startswith("packages/shared/"):
        # Native clients read providers.json, not the TypeScript/npm wrapper.
        return {"web-build"}
    if filename.startswith("packages/lib/tests/"):
        name = Path(filename).name
        if "/qml/" in filename or name == "run_qml_tests.py":
            return {"qml-syntax"}
        if name.startswith(("test_macos", "test_swiftbar")):
            return {"python-tests", "macos-native"}
        if name.startswith(("test_tray", "test_windows")) or name == "packaged_smoke.py":
            return {"python-tests", "windows-package"}
        if name == "test_install.py":
            return {"python-tests", "installer"}
        return {"python-tests", "windows-package"}
    return ALL


def changed_files(event_name, event, directory=None):
    """Use three-dot PR diffs and the full before/after range for pushes.

    Returning None means the diff is unavailable, so callers run all checks.
    --no-renames includes both paths when files move between platform trees.
    """
    if event_name == "pull_request":
        pr = event.get("pull_request", {})
        before = pr.get("base", {}).get("sha")
        after = pr.get("head", {}).get("sha")
        separator = "..."
    elif event_name == "push":
        before, after = event.get("before"), event.get("after")
        separator = ".."
    else:
        return None  # Explicit manual runs validate everything.
    if not all(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha)
               and sha != "0" * 40 for sha in (before, after)):
        return None
    try:
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", f"{before}{separator}{after}"],
            cwd=directory, check=True, capture_output=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return [os.fsdecode(name) for name in result.stdout.split(b"\0") if name]


def select_jobs(files):
    if files is None:
        return ALL
    return set().union(*(jobs_for_path(filename) for filename in files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", type=Path)
    args = parser.parse_args()
    files = changed_files(os.environ.get("GITHUB_EVENT_NAME"), json.loads(args.event.read_text()))
    selected = select_jobs(files)
    if files is None:
        print("Manual run or unavailable diff: running every check.")
    else:
        print(f"Changed files: {len(files)}")
    print("Selected checks: " + (", ".join(job for job in JOBS if job in selected) or "metadata only"))
    outputs = "".join(f"{job}={'true' if job in selected else 'false'}\n" for job in JOBS)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(outputs)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## Affected checks\n\n| Check | Decision |\n| --- | --- |\n")
            for job in JOBS:
                summary.write(f"| {job} | {'Run' if job in selected else 'Skip'} |\n")


if __name__ == "__main__":
    main()
