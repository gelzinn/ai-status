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

- Click the tray icon to open the dashboard. Windows may initially put it in
  the hidden-icons menu; move it beside the clock using Windows settings.
- Use the dropdown to choose the provider and metric shown in the tooltip.
- **Settings** enables/disables providers and lets you drag to reorder them.
  Starting at sign-in is optional and disabled by default.
- **Refresh** updates immediately; background updates run every five minutes.
  A failed provider shows a diagnostic. If recent usage is cached, it is
  explicitly labeled as cached and includes the reason it could not refresh.
- Closing the dashboard keeps the tray app running. Use **Exit** in its menu
  to stop it. An active query finishes before exit so child processes close.
- The tray menu opens the latest release for updates. Run the new installer
  to upgrade; configuration is preserved. There is no unattended executable
  replacement or remote shell execution.

The installer and app contain their own runtime. Provider applications and
authenticated sessions are separate prerequisites; their CLIs are not bundled
or installed automatically. Uninstalling removes the sign-in entry and keeps
your AI Status settings/cache. It never deletes provider credentials.

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
Its collector still depends on the CLI's interactive `/usage` output. CLI/API
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

Use x64 Python 3.12 and Inno Setup 6 on a Windows build machine. From the repo:

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

The build produces a windowed app plus a console helper in `dist/ai-status`,
an installer and a portable ZIP. The helper runs bundled collectors in isolated
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
