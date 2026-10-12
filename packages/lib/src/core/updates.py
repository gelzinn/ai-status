"""Optional updates with observable downloads and verified installation.

Reading a guide never downloads or installs anything. Windows opens a verified
installer; native macOS installs in the app; Linux/SwiftBar use a terminal.
"""

import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

from . import fetch, paths
from .provider_http import QueryError, _UsageRedirects, request_bytes

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
            title="Update on Windows", actionLabel="Update now", canUpdate=True,
            description="Downloads and opens Setup.\nYour settings are kept.",
        )
    elif method == "windows-portable":
        guide.update(title="Update a portable Windows copy",
                     description="Replace this copy with the latest ZIP.\nYour settings stay in AppData.")
    elif method == "omarchy":
        guide.update(title="Update the Omarchy plugin",
                     command="omarchy plugin update " + PLUGIN_ID + " --yes && omarchy restart shell",
                     actionLabel="Update now", canUpdate=shutil.which("omarchy") is not None,
                     description="Updates in Terminal, then restarts the shell.\nYour settings are kept.")
    elif method in ("linux-installer", "macos-installer"):
        native = method == "macos-installer" and options["mode"] == "native"
        guide.update(title="Update on macOS" if method == "macos-installer" else "Update on Linux",
                     command=_installer_command(method, options, latest),
                     actionLabel="Update now", canUpdate=True,
                     description="Installs and restarts automatically.\nYour settings are kept." if native else
                                 "Updates in Terminal.\nYour settings are kept.")
        if method == "macos-installer":
            guide["mode"] = options["mode"]
    else:
        guide.update(title="Update your installation",
                     description="Update this copy manually.\nYour settings are kept.")
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


def _event(progress, stage, message, **details):
    progress({"stage": stage, "message": message, **details})


def _download_progress(progress, message, downloaded, total=None):
    details = {"downloadedBytes": downloaded}
    if isinstance(total, int) and total > 0:
        details.update(totalBytes=total, percent=min(100, downloaded * 100 / total))
    _event(progress, "downloading", message, **details)


def _stream_process(arguments, progress, timeout, failure_message, transactional=False, include_errors=False, **options):
    """Drain JSON stdout while stderr goes to disk, with a bounded lifetime."""
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, encoding="utf-8", errors="replace", **options)
        expired = threading.Event()

        def stop():
            try:
                if transactional and options.get("start_new_session"):
                    # Stop compilers and other children too: Bash defers traps
                    # while a foreground child runs, and inherited JSON pipes
                    # otherwise keep the reader blocked after the timeout.
                    os.killpg(process.pid, signal.SIGTERM)
                elif process.poll() is None:
                    process.terminate() if transactional else process.kill()
            except ProcessLookupError:
                # The updater may have exited between the timeout and signal.
                pass

        def expire():
            expired.set()
            # Let the installer's TERM/EXIT traps restore its transaction. A
            # hard kill during activation would bypass cleanup and rollback.
            stop()

        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        timer.start()
        try:
            for line in process.stdout:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except (ValueError, TypeError):
                    raise OSError("The updater returned invalid progress. Try again or use the update guide.") from None
                if not isinstance(event, dict) or not isinstance(event.get("stage"), str):
                    raise OSError("The updater returned invalid progress. Try again or use the update guide.")
                progress(event)
            status = process.wait()
            if expired.is_set():
                raise OSError("The update timed out. Try again or use the update guide.")
            if status:
                if include_errors:
                    errors.seek(0, 2)
                    errors.seek(max(0, errors.tell() - 4096))
                    lines = errors.read().decode("utf-8", "replace").splitlines()
                    lines = ["".join(character for character in line if character.isprintable()).strip()
                             for line in lines if line.strip() and not line.startswith("Installation failed;")]
                    detail = "\n".join(lines[-3:])[-500:]
                    if detail:
                        failure_message += "\n" + detail
                raise OSError(failure_message)
        except BaseException:
            stop()
            process.wait()
            raise
        finally:
            timer.cancel()
            process.stdout.close()


def _download_windows(url, destination, progress):
    # Use Windows' built-in TLS and certificate store without bundling OpenSSL.
    # Streaming the response keeps large installers off the collector's 8 MiB cap.
    executable = shutil.which("powershell.exe")
    if not executable:
        raise OSError("Windows PowerShell is unavailable. Download the installer from the release page.")

    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    script = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$response = $null; $inputStream = $null; $outputStream = $null
function Write-DownloadProgress {
    $event = @{stage='downloading'; message='Downloading the Windows installer…'; downloadedBytes=$downloaded}
    if ($total -gt 0) { $event.totalBytes=$total; $event.percent=[Math]::Min(100, $downloaded * 100.0 / $total) }
    [Console]::Out.WriteLine(($event | ConvertTo-Json -Compress))
    [Console]::Out.Flush()
}
try {
    $request = [Net.HttpWebRequest]::Create(URL)
    $request.UserAgent = 'ai-status'
    $request.Timeout = 120000; $request.ReadWriteTimeout = 120000
    $request.MaximumAutomaticRedirections = 6
    $response = $request.GetResponse()
    if ($response.ResponseUri.Scheme -ne 'https') { throw 'Insecure redirect' }
    $total = $response.ContentLength; $downloaded = [long]0
    $inputStream = $response.GetResponseStream()
    $outputStream = [IO.File]::Open(DESTINATION, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    $buffer = New-Object byte[] 65536
    $clock = [Diagnostics.Stopwatch]::StartNew(); $last = 0
    Write-DownloadProgress
    while (($count = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        $outputStream.Write($buffer, 0, $count); $downloaded += $count
        if ($clock.ElapsedMilliseconds - $last -ge 100) { Write-DownloadProgress; $last = $clock.ElapsedMilliseconds }
    }
    if ($downloaded -eq 0 -or ($total -gt 0 -and $downloaded -ne $total)) { throw 'Incomplete download' }
    Write-DownloadProgress
} catch {
    [Console]::Error.WriteLine('Installer download failed.')
    exit 1
} finally {
    if ($outputStream) { $outputStream.Dispose() }
    if ($inputStream) { $inputStream.Dispose() }
    if ($response) { $response.Dispose() }
}
""".replace("URL", quote(url)).replace("DESTINATION", quote(destination))
    _stream_process([executable, "-NoProfile", "-NonInteractive", "-Command", script], progress, 180,
                    "Installer download failed. Check your connection or use the release page.",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not destination.is_file() or not destination.stat().st_size:
        raise OSError("Installer download failed. Check your connection or use the release page.")


def _download_macos(url, destination, progress):
    request = urllib.request.Request(url, headers={"User-Agent": "ai-status"})
    try:
        with urllib.request.build_opener(_UsageRedirects()).open(request, timeout=120) as response, destination.open("xb") as output:
            length = response.headers.get("Content-Length")
            total = int(length) if length and length.isdigit() and int(length) > 0 else None
            downloaded = 0
            message = "Downloading the macOS update…"
            _download_progress(progress, message, downloaded, total)
            last = time.monotonic()
            while block := response.read(65536):
                output.write(block)
                downloaded += len(block)
                if time.monotonic() - last >= 0.1:
                    _download_progress(progress, message, downloaded, total)
                    last = time.monotonic()
            if not downloaded or (total is not None and downloaded != total):
                raise OSError("Incomplete download")
            _download_progress(progress, message, downloaded, total)
    except (urllib.error.URLError, OSError, QueryError):
        raise OSError("Update download failed. Check your connection and try again.") from None


def _release_checksum(base, filename, progress):
    _event(progress, "checking", "Checking the release checksum…")
    try:
        checksums = request_bytes(base + "SHA256SUMS", timeout=15).decode("utf-8")
    except (QueryError, UnicodeError, OSError):
        raise OSError("Could not download the release checksum. Try again or use the release page.") from None
    matching = [line.split() for line in checksums.splitlines()
                if len(line.split()) == 2 and line.split()[1].lstrip("*") == filename]
    if len(matching) != 1 or not re.fullmatch(r"[a-fA-F0-9]{64}", matching[0][0]):
        raise ValueError("This release has no valid update checksum. Use the release page or try again later.")
    return matching[0][0].lower(), checksums


def _verify_download(filename, expected):
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError("The update checksum did not match. Nothing was installed; try again.")


def _windows_update(latest, progress):
    filename = "ai-status-" + latest + "-windows-x64-setup.exe"
    base = REPOSITORY + "/releases/download/v" + latest + "/"
    expected, _ = _release_checksum(base, filename, progress)
    # A unique directory avoids concurrent writers and reusing an unverified file.
    cache = paths.CACHE_DIR / "updates"
    cache.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="v" + latest + "-", dir=cache))
    installer = directory / filename
    try:
        _event(progress, "downloading", "Downloading the Windows installer…", downloadedBytes=0)
        _download_windows(base + filename, installer, progress)
        _event(progress, "verifying", "Verifying the installer…")
        _verify_download(installer, expected)
        _event(progress, "opening", "Opening setup automatically…")
        subprocess.Popen([str(installer)], close_fds=True)
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    # Setup needs the file while running, so leave the verified cache in place.
    return "Setup is open. Finish installation and leave Launch AI Status selected to reopen the app."


def _macos_update(latest, options, progress):
    if sys.platform == "darwin":
        # launchd kills the old app's remaining process-group members when its
        # job stops. Move this updater and its children into our own group first.
        os.setpgrp()
    filename = "ai-status-v" + latest + ".tar.gz"
    base = REPOSITORY + "/releases/download/v" + latest + "/"
    expected, checksums = _release_checksum(base, filename, progress)
    with tempfile.TemporaryDirectory(prefix="ai-status-update-") as temporary:
        directory = Path(temporary)
        archive = directory / filename
        sums = directory / "SHA256SUMS"
        sums.write_text(checksums, encoding="utf-8")
        _download_macos(base + filename, archive, progress)
        _event(progress, "verifying", "Verifying the macOS update…")
        _verify_download(archive, expected)
        arguments = ["/bin/bash", str(paths.LIB_DIR / "install-macos.sh"), "--no-interactive",
                     "--mode", options["mode"], "--version", "v" + latest, "--package", str(archive),
                     "--checksums", str(sums), "--json-progress"]
        if not (Path.home() / "Library/LaunchAgents/com.gelzin.ai-status.plist").is_file():
            arguments.append("--no-autostart")
        _event(progress, "installing", "Installing the verified update. Your settings are kept…")
        _stream_process(arguments, progress, 900,
                        "The update could not be installed. Your previous version and settings were preserved; try again or use the update guide.",
                        transactional=True, include_errors=True, start_new_session=True)
    return "AI Status was updated and reopened. Your settings were kept."


def run_update(progress=None):
    """Start an optional updater only after an explicit UI/CLI user action.

    The callback receives dict events with stage/message and optional byte counts.
    Downloads without a known size omit totalBytes/percent for indeterminate UI.
    """
    progress = progress or (lambda event: None)
    guide = update_guide()
    if not guide["canUpdate"]:
        raise ValueError("This installation uses a manual update. Follow the update guide or release page.")
    _event(progress, "checking", "Checking the latest stable release…")
    latest = fetch.check_for_updates()
    if fetch.stable_version(latest) is None:
        raise OSError("Could not check the latest stable release. Check your connection and try again.")
    if not fetch.newer_version(latest, fetch.get_version_info()["current"]):
        return "AI Status is already up to date."
    if guide["method"] == "windows-installer":
        return _windows_update(latest, progress)
    method, options = _installation()
    if method == "macos-installer" and options["mode"] == "native":
        return _macos_update(latest, options, progress)
    # Resolve the guide again after the version check to pin the command to the
    # actual validated release; do not execute a caller-provided command.
    guide = update_guide()
    _event(progress, "opening", "Opening the updater in a terminal…")
    _terminal(guide["command"])
    next_step = ("Omarchy restarts the shell when the update succeeds." if guide["method"] == "omarchy" else
                 "Your menu bar refreshes after installation." if guide["method"] == "macos-installer" else
                 "Your desktop bar reloads after installation.")
    return "The updater is open in a terminal. Follow its progress there. " + next_step
