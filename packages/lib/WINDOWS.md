# Windows 10 and 11

AI Status has a native desktop adapter for x64 Windows 10 (1809 or newer) and
Windows 11. It uses a notification-area icon and a desktop dashboard.
No WSL, Bash, Git, jq, curl, Python installation, or Nerd Font is required for
the packaged application.

## Install and use

Download `ai-status-<version>-windows-x64-setup.exe` from the
[latest GitHub release](https://github.com/gelzinn/ai-status/releases/latest).
Run it as your normal user; installation does not require administrator access. Launch **AI Status**
from the Start menu. For a portable installation, download
`ai-status-<version>-windows-x64.zip` from the same release, extract the entire
folder and open `ai-status.exe`. Keep `ai-status-cli.exe` and `_internal` beside it.
For portable upgrades, extract into a fresh folder and replace the old app folder;
settings/cache live in your user profile.

- Click the selected provider's tray logo to toggle the usage panel. Windows may initially put it in
  the hidden-icons menu; move it beside the clock using Windows settings.
- Click a provider or a metric to select it; the arrow/bullet marks the active
  selection. The tray logo and short usage
  tooltip follow that selection. Up/Down cycles metrics; Escape closes the panel.
- The panel only lists providers with usable metrics. Failed/unconnected providers
  do not occupy rows. The header has **Refresh** and **Settings** icons. The tray
  context menu also contains **Connection details**,
  update/log actions and **Exit**. R refreshes usage and C opens settings.
- **Settings** opens inside the panel, with the back arrow before the title.
  Choose the active provider/limit, with provider logos in the selector and its
  options, set display fields and the bar icon, enable/disable
  providers, and reorder them with drag and drop, the per-row arrows, or
  Alt+Up/Down. **Save** applies changes and keeps settings open; the back arrow,
  Escape or **Cancel** returns to usage and discards any remaining unsaved edits.
  Starting at sign-in is optional and disabled by default.
- **About AI Status** in Settings shows the project logo, description, author,
  version, build commit, MIT license, quick guide and links to GitHub,
  documentation and bug reports. Back returns to your settings draft.
- **Refresh** updates immediately; background updates run every five minutes.
  Only its icon rotates while the update is running.
  A failed provider shows a diagnostic. If recent usage is cached, it is
  explicitly labeled as cached. Its reason is available on hover and in
  **Connection details**, along with authentication failures for hidden providers.
- Claude and Codex show a **Reset credits** link beneath their usage metrics.
  Open it to see that provider's reset types, quantities, local expiry dates and
  remaining time in a rounded table. The provider logo/name is a plain heading;
  the back arrow before the panel title or Escape returns to usage without
  changing your tray selection. Expired, paused or spent credits are excluded.
  If details are unavailable, the known credit count remains visible and missing
  information is labeled. **Apply** in a small third column replaces that row
  with confirmation of the account, reset type and consumption of **one reset
  credit**. Hold the confirmation button for **3 seconds** while its background
  fills. Releasing early, leaving the button or losing focus resets the progress;
  Cancel, Back or Escape dismisses confirmation without sending a reset.
  Details without a usable credit ID or verifiable account remain read-only.
  Usage and credit inventory refresh
  after the response. An uncertain result is never retried automatically;
  refresh and check the account before confirming another reset. See
  [provider eligibility](PROVIDERS.md#claude).
- **Update available** is an optional blue link with a right arrow. Open it to
  see the installed/latest versions and the new GitHub release's notes.
  The back arrow or Escape returns to usage, keeping your selection and position.
  For an installed app, **Update now** downloads the new setup
  file, verifies its published SHA-256 checksum and opens the normal setup wizard.
  The fixed actions footer shows a spinner, download percentage and transferred
  bytes, then verification and automatic setup opening. Follow setup and leave
  **Launch AI Status** selected to restart. Progress survives closing the panel
  or navigating away. Results show a notice on the left and a compact **Retry**
  or **Done** button on the right. The release notes and installation guide use
  outlined controls. A portable app links to the manual guide for replacing its
  folder. Updates never start until you choose the update action.
- Clicking outside the panel or closing it keeps the tray app running. Use **Exit** in its menu
  to stop it. An active query finishes before exit so child processes close.
- **Update AI Status** in the tray menu opens the same guide. Running the new
  installer replaces the app runtime and preserves configuration. You can keep
  using the current version and update when convenient; updates are optional.

The installer and app contain their own runtime. Provider applications and
authenticated sessions are separate prerequisites; their CLIs are not bundled
or installed automatically.

To uninstall, remove **AI Status** in Windows Settings under **Apps**, or delete
the portable application folder after exiting it. Disable **Start at sign-in**
in Settings before removing a portable installation. The installer's uninstaller
removes the sign-in entry and keeps your AI Status settings/cache. It never deletes provider credentials.

The UI uses the app's favicon for its executable/installer identity, bundled
provider logos, and the Geist Mono font, all available offline.

### Windows publisher and SmartScreen

The Windows installer and executables are currently unsigned. Windows can show
**Unknown publisher** and a **Windows protected your PC** SmartScreen prompt for these downloads.
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
| Copilot | `GITHUB_COPILOT_TOKEN`, OpenCode's `github-copilot` entry in `auth.json`, or native `gh auth token` |
| Z.AI | `ZAI_API_KEY` or OpenCode's Z.AI entry in `account.json` |
| OpenCode Go | `OPENCODE_GO_API_KEY` or OpenCode's `opencode-go.key` in `auth.json`; no workspace cookie |
| Command Code | `%USERPROFILE%\.commandcode\auth.json` or `COMMANDCODE_API_KEY` |
| Kiro | An installed, authenticated **native** `kiro-cli` on PATH |
| Antigravity | An installed, authenticated native `agy`; automated through Windows ConPTY |

OpenCode data files are read from `%USERPROFILE%\.local\share\opencode` or
`%XDG_DATA_HOME%\opencode` when set. Credentials are only read; AI Status does not write them,
perform provider sign-in, or copy them into its cache/log.

The additional opt-in providers are Anthropic API, OpenAI API, Google Cloud,
OpenRouter, DeepSeek, DeepInfra, Kimi, MiniMax, Kilo, Lyceum, Novita, Moonshot,
Grok API, SuperGrok, Grok Bot, Cursor, Nous Research, Ollama Cloud, OrcaRouter,
Alibaba Model Studio and Devin. See [Providers & Authentication](PROVIDERS.md)
for their credential variables, account permissions and options. Enable the
providers you configure in Settings. API cost and balance metrics remain amounts;
progress bars require a reported limit or an explicitly configured budget.

Cursor reads `%APPDATA%\Cursor\User\globalStorage\state.vscdb` or its
JSON session file; `CURSOR_ACCESS_TOKEN` is an explicit override. Grok Bot reads
`%APPDATA%\Grok Bot\sand-secrets.json` and the adjacent `Local State` key
using the current Windows user's DPAPI. Its Chromium `v10`/`v11` token reader
depends on the desktop app's storage format; use `GROK_BOT_ACCESS_TOKEN` if that
format is incompatible. These readers do not perform sign-in or refresh tokens.

All 29 collectors are included, but inclusion does not guarantee that an
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
depend on their providers' usage endpoints and account requirements.

## Data and command line

Settings are stored in `%APPDATA%\ai-status`. Usage cache, runtime coordination
files and `ai-status-error.log` live in `%LOCALAPPDATA%\ai-status\cache`.
These directories are separate from the installation so upgrades preserve them.

Open PowerShell in the portable folder or the installed application directory
(default: `%LOCALAPPDATA%\Programs\AI Status`):

```powershell
.\ai-status-cli.exe doctor   # Version, directories, collectors, Qt/ConPTY availability
.\ai-status-cli.exe status   # One JSON snapshot: {providers: [...], errors: {...}}
.\ai-status-cli.exe refresh  # Requests an update of the running app/daemon
.\ai-status-cli.exe config   # Opens desktop settings, activates an existing instance
```

Add any number of independent connections using the bundled CLI. For example,
point a Codex connection at that account's own OAuth file:

```powershell
.\ai-status-cli.exe accounts add codex --id work-codex --label Work --auth-file C:\Users\you\work-codex\auth.json
.\ai-status-cli.exe accounts add --file connection.json
.\ai-status-cli.exe accounts list
```

Connection definitions live in `%APPDATA%\ai-status\accounts.json`.
`auth_file` selects an existing credential file; `env` maps provider variables
to separate source environment variables, rather than storing secret values.
The app must inherit those variables when launched. Explicit connections need
their own credential source. See [the account guide](PROVIDERS.md#multiple-accounts-and-connections)
for the JSON format and provider options. HTTP 429 cooldowns persist across
refreshes and restarts; they respect `Retry-After` and retain cached metrics.

`status` is read-only with respect to provider sessions and saves usage cache.
`daemon` provides a JSON stream of usage updates. The desktop reads structured
provider metrics directly.
