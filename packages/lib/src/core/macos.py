"""Native macOS app integration using the shared desktop snapshot contract.

AppKit/SwiftUI own presentation. The collector remains standard-library Python;
bundled provider artwork avoids network requests or SVG rasterizers at startup.
"""
from pathlib import Path
import os
import subprocess
import sys

from . import paths


class LogoCache:
    def get(self, provider):
        if provider not in {p.name for p in paths.PROVIDERS_DIR.iterdir() if p.is_dir()}:
            return ""
        logo = paths.LIB_DIR / "assets" / "providers" / f"{provider}.png"
        return str(logo) if logo.is_file() else ""


def configure_environment():
    """Make native CLI installs visible when the app starts from Finder/login."""
    existing = os.environ.get("PATH", "").split(os.pathsep)
    defaults = [str(Path.home() / ".local/bin"), str(Path.home() / ".npm-global/bin"),
                "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys(p for p in existing + defaults if p))


def launch(configure=False):
    if sys.platform != "darwin":
        raise SystemExit("The native menu bar app requires macOS.")
    application = Path.home() / "Applications" / "AI Status.app"
    executable = application / "Contents" / "MacOS" / "AIStatus"
    if not executable.is_file():
        raise SystemExit("Install the native app: bash packages/lib/install-macos.sh")
    # A second app invocation forwards to the first instance and exits. This
    # also lets `config` open Settings when the app is already running.
    subprocess.Popen([str(executable), *(["--settings"] if configure else [])],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
