# AI Status for macOS

AI Status runs as a native SwiftUI/AppKit menu bar app. Its usage, Settings,
reset-credit and About pages follow the same structure as the Windows tray
app and Omarchy Quickshell plugin, using the shared provider backend.

## Requirements

- macOS 13 or newer.
- Python 3.10 or newer, available as `python3` when you install.
- Xcode Command Line Tools, including `swiftc`.
- Provider apps or CLIs with authenticated sessions. See
  [PROVIDERS.md](PROVIDERS.md) for each provider's credential sources.

Install the Command Line Tools with `xcode-select --install`. If your existing
`python3` is too old, install a supported Python release before running the
installer. Homebrew users can run `brew install python`; use a Python
installation with working CA certificates for provider HTTPS requests.
The native app uses the Python interpreter discovered during
installation, so it does not depend on the menu bar process's limited `PATH`.
SwiftBar is required only for the optional SwiftBar modes.

## Install or update

```bash
curl -fsSL https://ai-status.gelzin.com/install/macos | bash
```

The default `--mode native` installs the shared core, builds the native `.app`
locally, links `~/.local/bin/ai-status`, and starts the menu bar app. The remote
installer uses the latest stable release with checksum verification. Re-run
the command to update; your provider selection and display preferences are
preserved. A user LaunchAgent starts the app when you sign in.

The bundle lives at `~/.local/share/ai-status/AI Status.app`, with a shortcut at
`~/Applications/AI Status.app`. Launch it from Applications or run
`~/.local/bin/ai-status macos`. The login agent is
`~/Library/LaunchAgents/com.gelzin.ai-status.plist`.

| Installer option | Behavior |
| --- | --- |
| `--mode native` | Build the native app; the default integration |
| `--mode stream` / `--mode periodic` | Install the optional SwiftBar plugin |
| `--version vX.Y.Z` | Install a specific published stable release |
| `--rollback` | Restore the previous local installation |
| `--no-start` | Install files without launching or loading the login agent |
| `--no-autostart` | Disable launch at sign-in |
| `--skip-check` | Skip the macOS version preflight; Python and build tools remain required |
| `--no-interactive` | Accepted for scripted installs; installation is non-interactive |

Before this macOS port has been released, install it from its branch checkout:

```bash
git clone --depth 1 --branch feat/macos-swiftbar \
  https://github.com/gelzinn/ai-status /tmp/ai-status-macos
bash /tmp/ai-status-macos/packages/lib/install-macos.sh
```

For an existing checkout, run `bash packages/lib/install-macos.sh` from the
repository root. This installs the checkout's code, including local changes,
instead of downloading a stable release.

## Usage panel

Click the menu bar item to open or close the panel. The header contains
**Refresh** and **Settings** controls. Provider cards show their logos,
account or plan names, usage bars, percentages and reset countdowns. Click
a provider heading or a limit to choose what appears in the menu bar.

Usage refreshes every five minutes. Loading feedback appears during a
refresh, and usable cached data stays visible if a provider request fails.
Providers without usable metrics remain available in Settings.

When Claude or Codex reports available manual resets, **Reset credits: N
available** opens a separate details page. It shows the credit type, count,
expiry, remaining time and time zone when available. Redeem credits through
the provider's own app; AI Status displays the inventory. Back returns to
the usage panel without changing the selected limit.

## Settings and About

Settings includes the selected provider and limit, menu bar display fields,
icon mode, and a list of providers to enable, disable or reorder. **Save**
applies changes and keeps Settings open. Back or **Cancel** returns to usage
and discards unsaved edits.

**About AI Status** shows the installed version, project details, license,
usage guide and links. Its back control returns to Settings. Authentication
continues to use your provider's own apps and CLIs; Settings does not perform
provider sign-in.

The native app shares preferences and cache with the other integrations
in `~/.config/ai-status/selected.json` and `~/.cache/ai-status.json`.
`~/.local/bin/ai-status config` opens its native Settings page.

Claude authentication also supports the local `Claude Code-credentials`
Keychain entry. `CLAUDE_CONFIG_DIR` scopes credential lookup for a separate
Claude profile. Credential lookup is read-only; the app does not change
provider credentials.

## Optional SwiftBar integration

Keep using [SwiftBar](https://swiftbar.app) with either compatibility mode:

```bash
# Streamable plugin with loading animation:
curl -fsSL https://ai-status.gelzin.com/install/macos | bash -s -- --mode stream

# Periodic plugin without streaming animation:
curl -fsSL https://ai-status.gelzin.com/install/macos | bash -s -- --mode periodic
```

Install SwiftBar separately (`brew install --cask swiftbar`, or download it
from its website). The installer reads its configured plugin directory and
falls back to `~/Library/Application Support/SwiftBar/Plugins`.

The menu bar shows your selected usage. Its dropdown includes provider logos,
progress bars, reset timers and the active limit marker. Click a provider or
limit to select it. **Refresh**, **Settings** and **About AI Status** appear
as menu actions. SwiftBar Settings opens the shared terminal configuration
interface; the full native pages are available in `--mode native`.

## Development and validation

The SwiftUI sources are in `packages/lib/macos/`. The native app consumes
the shared JSON daemon and uses the same settings validation and provider
selection commands as the other native panels.

Run the installer from a checkout on a Mac to compile and launch it. Verify
menu bar selection, popover open/close and Escape, manual and background
refresh, settings Save/Cancel and reordering, reset-credit navigation, About,
multiple displays, and launch at sign-in. Check both light and dark
appearance, provider errors, missing credentials and cached results.

Linux checks cover the backend and installer behavior. They do not verify
AppKit/SwiftUI compilation or the on-screen macOS experience; those need a
Mac.
