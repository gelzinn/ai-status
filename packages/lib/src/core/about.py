"""Project identity shared by the desktop panels."""
from functools import lru_cache
import subprocess
import sys

from . import __version__, paths

GITHUB = "https://github.com/gelzinn/ai-status"


@lru_cache(maxsize=1)
def project_info():
    commit_file = paths.LIB_DIR / "BUILD_COMMIT"
    try:
        commit = commit_file.read_text().strip()
    except OSError:
        commit = ""
    if not commit and not getattr(sys, "frozen", False):
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=paths.LIB_DIR.parents[1],
                stderr=subprocess.DEVNULL, text=True, timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if paths.IS_WINDOWS else 0,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return {
        "name": "AI Status", "version": __version__, "commit": commit[:8] or "Unavailable",
        "description": "Monitor AI provider usage limits from your desktop.",
        "author": "gelzin.com", "license": "MIT",
        "github": GITHUB, "documentation": GITHUB + "#readme",
        "issues": GITHUB + "/issues/new", "licenseUrl": GITHUB + "/blob/main/LICENSE",
    }
