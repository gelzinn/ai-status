# Windows 10 and 11

AI Status has a native desktop adapter for x64 Windows 10 (1809 or newer) and
Windows 11. It uses a notification-area icon and a dashboard instead of Waybar.
No WSL, Bash, Git, jq, curl, Python installation, or Nerd Font is required for
the packaged application.

## Install and use

Download `ai-status-<version>-windows-x64-setup.exe` from the
[GitHub release](https://github.com/gelzinn/ai-status/releases/latest) once a
release containing Windows assets has been published. Run it as your normal
user; installation does not require administrator access. Launch **AI Status**
from the Start menu. A portable ZIP is also built: extract the entire folder
and open `ai-status.exe`. Keep `ai-status-cli.exe` and `_internal` beside it.
For portable upgrades, extract into a fresh folder and replace the old app folder;
settings/cache live in your user profile.

- Click the selected provider's tray logo to toggle the usage panel. Windows may initially put it in
  the hidden-icons menu; move it beside the clock using Windows settings.
- Click a provider or a metric to select it; the arrow/bullet marks the active
  selection, matching the landing-page preview. The tray logo and short usage
  tooltip follow that selection. Up/Down cycles metrics; Escape closes the panel.
- The panel only lists providers with usable metrics. Failed/unconnected providers
  do not occupy rows. The square **⋯** menu and tray context menu contain
  **Refresh**, **Settings**, **Connection details**, update/log actions and **Exit**.
- **Settings** enables/disables providers and lets you drag to reorder them.
  Starting at sign-in is optional and disabled by default.
- **Refresh** updates immediately; background updates run every five minutes.
  A failed provider shows a diagnostic. If recent usage is cached, it is
  explicitly labeled as cached. Its reason is available on hover and in
  **Connection details**, along with authentication failures for hidden providers.
- Claude and Codex show a **Reset credits** link beneath their usage metrics.
  Open it to see that provider's reset types, quantities, local expiry dates and
  remaining time in a table. The back arrow or Escape returns to usage without
  changing your tray selection. Expired, paused or spent credits are excluded.
  If details are unavailable, the known credit count remains visible and missing
  information is labeled. Use the provider's own app to redeem a reset.
- Clicking outside the panel or closing it keeps the tray app running. Use **Exit** in its menu
  to stop it. An active query finishes before exit so child processes close.
- The tray menu opens the latest release for updates. Run the new installer
  to upgrade; the app runtime is replaced completely and configuration is
  preserved. There is no unattended executable
  replacement or remote shell execution.

The installer and app contain their own runtime. Provider applications and
authenticated sessions are separate prerequisites; their CLIs are not bundled
or installed automatically. Uninstalling removes the sign-in entry and keeps
your AI Status settings/cache. It never deletes provider credentials.

Before a release includes Windows assets, use the **Windows package** workflow's
separate **ai-status-<version>-windows-x64-setup** or
**ai-status-<version>-windows-x64-portable** artifact. GitHub wraps each artifact
in a ZIP. Extract the setup artifact and run
`ai-status-<version>-windows-x64-setup.exe` inside it; do not rename the downloaded
ZIP to `.exe`. The installer and portable payload are separate downloads.
The UI uses the app's
favicon for its executable/installer identity, bundled provider logos, and the
same Geist Mono font as the landing-page preview, all available offline.

### Windows publisher and SmartScreen

Preview packages are currently unsigned. Windows can show **Unknown publisher**
and a **Windows protected your PC** SmartScreen prompt for these downloads.
The application name, icon and version metadata identify the package, but they
do not establish a verified publisher. Authenticode signing requires a trusted
code-signing certificate or a signing service configured by the maintainer.
Even a valid signature does not guarantee that a new download already has
SmartScreen reputation. See Microsoft's
[SmartScreen guidance for developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

## Authentication and provider compatibility

| Provider | Existing authentication used by AI Status |
| --- | --- |
| Claude | `%USERPROFILE%\.claude\.credentials.json`, then OpenCode's Claude session; honors `CLAUDE_CONFIG_DIR` |
| Codex | `%USERPROFILE%\.codex\auth.json`; honors `CODEX_HOME`; requires ChatGPT OAuth |
| Copilot | OpenCode's `github-copilot` entry in `auth.json` |
| Z.AI | OpenCode's Z.AI entry in `account.json` |
| OpenCode Go | OpenCode's `opencode-go` key plus workspace/session cookie in `%USERPROFILE%\.config\opencode-bar\opencode-go.json` |
| Command Code | `%USERPROFILE%\.commandcode\auth.json` or `COMMANDCODE_API_KEY` |
| Kiro | An installed, authenticated **native** `kiro-cli` on PATH |
| Antigravity | An installed, authenticated native `agy`; automated through Windows ConPTY |

OpenCode data files are read from `%USERPROFILE%\.local\share\opencode` or
`%XDG_DATA_HOME%\opencode` when set. Its Go workspace configuration honors
`XDG_CONFIG_HOME`. Credentials are only read; AI Status does not write them,
perform provider sign-in, or copy them into its cache/log.

All eight collectors are included, but inclusion does not guarantee that an
upstream CLI or account is compatible. In particular, the current
[Kiro system requirements](https://kiro.dev/docs/getting-started/installation/)
list **Windows 11** for the native CLI. **Kiro on Windows 10 is conditional on
the installed CLI actually working** and is not claimed as verified native
support. AI Status attempts the native command and reports installation,
sign-in or incompatible-output failures; there is no WSL fallback.

[Antigravity provides a native Windows CLI](https://www.antigravity.google/docs/cli/install/).
Its collector uses Windows' built-in ConPTY API directly and still depends on the
CLI's interactive `/usage` output. No pywinpty/WinPTY runtime is shipped. CLI/API
changes can require a collector/parser update. HTTP-backed providers likewise
retain the same usage endpoints and account requirements as the Linux module.

## Data and command line

Settings are stored in `%APPDATA%\ai-status`. Usage cache, runtime coordination
files and `ai-status-error.log` live in `%LOCALAPPDATA%\ai-status\cache`.
These directories are separate from the installation so upgrades preserve them.

From the extracted/installed directory in PowerShell:

```powershell
.\ai-status-cli.exe doctor   # Version, directories, collectors, Qt/ConPTY availability
.\ai-status-cli.exe status   # One JSON snapshot: {providers: [...], errors: {...}}
.\ai-status-cli.exe refresh  # Requests an update of the running app/daemon
.\ai-status-cli.exe config   # Opens desktop settings, activates an existing instance
```

`status` is read-only with respect to provider sessions and saves usage cache.
`daemon` remains a JSON stream adapter; Linux's Waybar output/controls are
preserved. The desktop reads structured provider metrics directly rather than
trying to render Waybar's Pango markup or Linux icon fonts.

## Develop and build

Use x64 Python 3.12, Inno Setup 6, and Visual Studio Build Tools with the x64
C++ compiler and Windows SDK on a Windows build machine. Git for Windows
supplies the OpenSSL **test tool** used to generate an untrusted localhost
certificate; OpenSSL is not shipped with the app. From the repo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r packages/lib/windows/requirements.txt
python packages/lib/src/windows.py tray
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s packages/lib/tests -v
Remove-Item Env:QT_QPA_PLATFORM
.\packages\lib\windows\build.ps1
```

The build produces a small native windowed launcher and a console helper sharing
one Python/Qt runtime in `dist/ai-status`, an installer and a portable ZIP. The
launcher carries the app icon, preserves arguments/exit status, and starts the
helper without a console window. The helper runs bundled collectors in isolated
subprocesses with explicit timeouts; running `.py` files through Windows file
associations is never required. Qt/Python remain external dynamic libraries in
the folder. Dependency license texts accompany the package.

The **Windows package** workflow runs tests, builds both distributions and
smoke-tests the packaged collectors, GUI dependencies, silent install and
uninstall on a Windows runner. Release automation attaches those artifacts to
the existing versioned GitHub release. Hosted Windows runners do not replace
interactive testing on Windows 10/11: validate tray interaction, scaling,
Explorer restart, suspend/resume, upgrade and authenticated usage on both OSes
before announcing full provider compatibility.

The package ships only raster widgets and the required Windows/offscreen Qt
platform plugins. OpenGL software emulation, QML/Quick, QtNetwork/QtSvg, unused
image/TLS plugins, translations, legacy Bash collectors and bytecode caches are
excluded. Windows HTTPS uses WinHTTP and the system certificate store, including
normal certificate/hostname checks, timeouts, proxy settings and decompression.
Authentication headers are retained on same-origin redirects and removed when
the origin changes. HTTPS redirects to HTTP are rejected. Linux uses the
standard-library HTTP client as before.

Python/OpenSSL and Qt TLS libraries are omitted from the Windows bundle. The
Universal CRT comes from Windows 10/11; duplicate MSVC 14 DLLs are consolidated
to the newest backwards-compatible version. Qt remains dynamically linked and
replaceable. The installer uses solid LZMA2 with a 64 MiB dictionary; the portable
ZIP retains Deflate for Windows Explorer compatibility. Frozen Python bytecode
uses optimization level 2 and maximum zlib compression, omitting development
docstrings/assertions; runtime input validation uses explicit exceptions.

CI renders the packaged widgets/logos, runs real ConPTY input/output checks,
tests native HTTP against localhost (including invalid TLS certificates), and
verifies public HTTPS from the frozen executable. It also tests the native
launcher, silent install/upgrade/uninstall in a Unicode path (including removal
of obsolete runtime DLLs and preservation of user data), and enforces size budgets
of 54 MiB installed, 22 MiB for the portable ZIP, and 17 MiB for the installer.
The build summary lists the largest remaining runtime files.
