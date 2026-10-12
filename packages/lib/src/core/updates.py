"""Optional update guides and explicit, user-initiated updater handoffs.

Reading a guide never downloads or installs anything. Windows opens a verified
installer; Unix desktops open a terminal so installation remains visible.
"""

import hashlib
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from . import fetch, paths
from .provider_http import QueryError, request_bytes

REPOSITORY = "https://github.com/gelzinn/ai-status"
GUIDE_URL = REPOSITORY + "/blob/main/packages/lib/UPDATES.md"
PLUGIN_ID = "io.github.gelzinn.ai-status"
TERMINALS = ("foot", "alacritty", "kitty", "ghostty", "wezterm", "xterm", "gnome-terminal", "konsole")


def _within(directory, root):
    try:
        directory.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _macos_mode(installation):
    if (installation / "AI Status.app/Contents/MacOS/AIStatus").is_file():
        return "native"
    plugins = Path.home() / "Library/Application Support/SwiftBar/Plugins"
    try:
        settings = plistlib.loads((Path.home() / "Library/Preferences/com.ameba.SwiftBar.plist").read_bytes())
        custom = settings.get("PluginDirectory") if isinstance(settings, dict) else None
        if isinstance(custom, str) and custom:
            plugins = Path(custom).expanduser()
    except (OSError, ValueError, plistlib.InvalidFileException):
        pass
    for mode, filename in (("stream", "ai-status.5s.py"), ("periodic", "ai-status.30s.py")):
        if (plugins / filename).is_file():
            return mode
    return ""


def _installation():
    """Identify supported installs; never overwrite a checkout or portable app."""
    if paths.IS_WINDOWS:
        if not getattr(sys, "frozen", False):
            return "source", {}
        directory = Path(sys.executable).resolve().parent
        return ("windows-installer" if (directory / "unins000.exe").is_file() else "windows-portable"), {}
    installation = Path.home() / ".local/share/ai-status"
    plugin = Path.home() / ".config/omarchy/plugins" / PLUGIN_ID
    if sys.platform.startswith("linux") and _within(paths.LIB_DIR, plugin):
        return "omarchy", {}
    if _within(paths.LIB_DIR, installation):
        if sys.platform == "darwin":
            mode = _macos_mode(installation)
            return ("macos-installer" if mode else "manual"), {"mode": mode}
        if sys.platform.startswith("linux"):
            return "linux-installer", {"bar": "quickshell" if plugin.is_dir() else "waybar"}
    return "source", {}


def _installer_command(method, options, latest):
    flags = ["--no-interactive"]
    if fetch.stable_version(latest) is not None:
        flags += ["--version", "v" + latest.removeprefix("v")]
    if method == "macos-installer":
        endpoint = "install/macos"
        flags += ["--mode", options["mode"]]
        if options["mode"] == "native" and not (Path.home() / "Library/LaunchAgents/com.gelzin.ai-status.plist").is_file():
            flags.append("--no-autostart")
    else:
        endpoint = "install"
        flags += ["--bar", options.get("bar", "waybar")]
    # pipefail stops a failed bootstrap download from appearing successful.
    return "set -o pipefail; curl -fsSL https://ai-status.gelzin.com/" + endpoint + " | bash -s -- " + shlex.join(flags)


def update_guide():
    """Return plain presentation data with a guide matching this installation."""
    method, options = _installation()
    latest = fetch.get_version_info()["latest"]
    release_url = (REPOSITORY + "/releases/tag/v" + latest.removeprefix("v")
                   if fetch.stable_version(latest) is not None else REPOSITORY + "/releases/latest")
    guide = {
        "method": method, "title": "Update AI Status",
        "description": "Updates are optional. Your provider settings and credentials are kept.",
        "steps": [], "command": "", "actionLabel": "Open update guide",
        "canUpdate": False, "releaseUrl": release_url, "guideUrl": GUIDE_URL,
    }
    if method == "windows-installer":
        guide.update(
            title="Update on Windows", actionLabel="Download and open installer", canUpdate=True,
            description="Download the latest stable installer, verify its SHA-256 checksum, and open setup. Your settings are kept.",
            steps=["Open the installer with the button below; downloading may take a moment.",
                   "Follow setup using your existing installation folder. If asked, allow setup to close AI Status.",
                   "Leave Launch AI Status selected at the end to restart with the new version."],
        )
    elif method == "windows-portable":
        guide.update(title="Update a portable Windows copy", steps=[
            "Download the Windows portable ZIP from the release page.",
            "Quit AI Status, extract the new version to a new folder, then launch ai-status.exe.",
            "Your settings stay in AppData. Keep the old folder until the new version works.",
        ])
    elif method == "omarchy":
        guide.update(title="Update the Omarchy plugin",
                     command="omarchy plugin update " + PLUGIN_ID + " --yes && omarchy restart shell",
                     actionLabel="Update in terminal", canUpdate=shutil.which("omarchy") is not None,
                     steps=["Open the updater in a terminal using the button below.",
                            "After the plugin update succeeds, Omarchy restarts the shell to load the new UI."])
    elif method in ("linux-installer", "macos-installer"):
        guide.update(title="Update on macOS" if method == "macos-installer" else "Update on Linux",
                     command=_installer_command(method, options, latest), actionLabel="Update in terminal", canUpdate=True,
                     steps=["Open the updater in a terminal using the button below, or run the command shown.",
                            "The installer verifies the stable release and preserves your current setup.",
                            "AI Status restarts after installation." if method == "macos-installer" else "The installer reloads your desktop bar after installation."])
    else:
        guide.update(title="Update your installation", steps=[
            "This copy is outside a supported installer location. Use the update guide for your installation method.",
            "For a source checkout, pull the desired release and rerun the installer for your platform.",
            "A checkout or custom installation is never replaced automatically.",
        ])
    return guide


def _terminal(command):
    # Keep output visible, including failures, after the installer has finished.
    visible = command + "; ai_status_update_result=$?; printf '\\nUpdater exited with status %s. Press Enter to close.\\n' \"$ai_status_update_result\"; read -r ai_status_update_close; exit \"$ai_status_update_result\""
    if sys.platform == "darwin":
        shell = "bash -lc " + shlex.quote(visible)
        quoted = '"' + shell.replace("\\", "\\\\").replace('"', '\\"') + '"'
        script = "tell application \"Terminal\"\nactivate\ndo script " + quoted + "\nend tell"
        try:
            result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, timeout=15)
        except subprocess.TimeoutExpired:
            raise OSError("Terminal did not respond. Run the update command shown in the guide.") from None
        if result.returncode:
            raise OSError("Could not open Terminal. Run the update command shown in the guide.")
        return
    for name in TERMINALS:
        executable = shutil.which(name)
        if not executable:
            continue
        if name == "gnome-terminal":
            arguments = [executable, "--", "bash", "-lc", visible]
        elif name == "wezterm":
            arguments = [executable, "start", "--", "bash", "-lc", visible]
        else:
            arguments = [executable, "-e", "bash", "-lc", visible]
        subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return
    raise OSError("No supported terminal found. Run the update command shown in the guide in your terminal.")


def _download_windows(url, destination):
    # The bundled WinHTTP collector limits responses to 8 MiB. PowerShell's
    # built-in HTTPS download streams the larger installer directly to disk.
    executable = shutil.which("powershell.exe")
    if not executable:
        raise OSError("Windows PowerShell is unavailable. Download the installer from the release page.")
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"
    script = ("[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
              "Invoke-WebRequest -UseBasicParsing -Uri " + quote(url) + " -OutFile " + quote(destination)
              + " -TimeoutSec 120 -ErrorAction Stop")
    try:
        result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-Command", script],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise OSError("Installer download timed out. Try again or use the release page.") from None
    if result.returncode or not destination.is_file() or not destination.stat().st_size:
        raise OSError("Installer download failed. Check your connection or use the release page.")


def _windows_update(latest, progress):
    filename = "ai-status-" + latest + "-windows-x64-setup.exe"
    base = REPOSITORY + "/releases/download/v" + latest + "/"
    progress("Downloading the release checksum…")
    try:
        checksums = request_bytes(base + "SHA256SUMS", timeout=15).decode("utf-8")
    except (QueryError, UnicodeError, OSError):
        raise OSError("Could not download the release checksum. Try again or use the release page.") from None
    matching = [line.split() for line in checksums.splitlines()
                if len(line.split()) == 2 and line.split()[1].lstrip("*") == filename]
    if len(matching) != 1 or not re.fullmatch(r"[a-fA-F0-9]{64}", matching[0][0]):
        raise ValueError("This release has no valid installer checksum. Use the release page or try again later.")
    # A unique directory avoids concurrent writers and reusing an unverified file.
    cache = paths.CACHE_DIR / "updates"
    cache.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="v" + latest + "-", dir=cache))
    installer = directory / filename
    try:
        progress("Downloading the Windows installer…")
        _download_windows(base + filename, installer)
        progress("Verifying the installer…")
        digest = hashlib.sha256()
        with installer.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest().lower() != matching[0][0].lower():
            raise ValueError("The installer checksum did not match. Nothing was installed; try again.")
        progress("Opening the verified installer…")
        subprocess.Popen([str(installer)], close_fds=True)
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    # Setup needs the file while running, so leave the verified cache in place.
    return "The verified installer is open. Follow setup to update, then leave Launch AI Status selected to restart."


def run_update(progress=None):
    """Start an optional updater only after an explicit UI/CLI user action."""
    progress = progress or (lambda message: None)
    guide = update_guide()
    if not guide["canUpdate"]:
        raise ValueError("This installation uses a manual update. Follow the update guide or release page.")
    progress("Checking the latest stable release…")
    latest = fetch.check_for_updates()
    if fetch.stable_version(latest) is None:
        raise OSError("Could not check the latest stable release. Check your connection and try again.")
    if not fetch.newer_version(latest, fetch.get_version_info()["current"]):
        return "AI Status is already up to date."
    if guide["method"] == "windows-installer":
        return _windows_update(latest, progress)
    # Resolve the guide again after the version check to pin the command to the
    # actual validated release; do not execute a caller-provided command.
    guide = update_guide()
    progress("Opening the updater in a terminal…")
    _terminal(guide["command"])
    return ("The updater is open in Terminal. Follow its progress there; AI Status restarts after installation."
            if guide["method"] == "macos-installer" else "The updater is open in a terminal. Follow its progress there.")
