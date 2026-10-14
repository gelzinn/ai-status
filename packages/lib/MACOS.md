# AI Status for macOS

AI Status runs as a native SwiftUI/AppKit menu bar app, with usage, Settings,
reset-credit and About pages powered by its provider backend.

## Requirements

- macOS 13 or newer.
- Python 3.10 or newer, available as `python3` when you install.
- Xcode Command Line Tools, including `swiftc`.
- Provider apps or CLIs with authenticated sessions, or explicitly configured
  API credential sources. See
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

When a newer version is available, **Update available: vX.Y.Z →** opens a
compact update page with the new GitHub release's notes. **Update now** downloads and installs
for a supported native installation. The fixed footer shows a spinner, download
percentage and transferred bytes, followed by verification, installation and
automatic restart. AI Status closes briefly and reopens with your settings kept.
**Update manually…** reveals the copyable Terminal command and installation
guide. Back or **Esc** returns to usage; returning to Updates keeps the running
progress. Results show a notice on the left and a compact **Retry** or **Done**
button on the right. Release notes, manual update and guide controls have matching
borders and padding. Updating is optional.

You can also run `~/.local/bin/ai-status update` to start the updater. SwiftBar
updates continue in Terminal. Development
checkouts and unrecognized installations show manual instructions instead of
replacing the checkout.

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

## Usage panel

Click the menu bar item to open or close the panel. The header contains
**Refresh** and **Settings** controls. Connection cards show their provider
logos and account or plan names, with usage bars and reset countdowns for
quotas, and reported costs or balances for API services. Click a connection
heading or a metric to replace one menu bar selection, keeping additional
selected items in provider order. Balances have
no invented percentage; a cost percentage requires a reported limit or a
configured monitoring budget.

Usage refreshes at the saved interval, defaulting to five minutes. Loading
feedback appears during a refresh, and usable cached data stays visible if a
provider request fails.
Providers without usable metrics remain available in Settings.

When Claude or Codex reports available manual resets, **Reset credits: N
available** opens a separate details page. It shows the credit type, count,
expiry, remaining time and time zone when available. **Apply** in the small
third column replaces that row with confirmation of the account, reset type
and consumption of **one reset credit**. Hold the confirmation button for
**3 seconds** while its background fills. Releasing early, leaving the button
or losing focus resets the progress; Cancel, Back or Escape dismisses
confirmation without sending a reset.
Details without a usable credit ID or verifiable account remain read-only.
Usage and credit inventory refresh after the response. An uncertain result is
never retried automatically; refresh and check the account before confirming
another reset. Back returns to the usage panel without changing the selected
limit. See [provider eligibility](PROVIDERS.md#claude).

## Settings and About

**Providers** has one compact row per connection with **Active**, its name,
**Show in bar** and up/down controls. Active controls usage collection even
when Show in bar is off. Open the row's small menu to choose the account/limit
items without a second persistent list. Move a provider row to change the
same order in Usage and the menu bar. Selected limits within that provider
keep their relative order, including saved limits that are temporarily
unavailable. Each selected item shows its own usage label. Disabling a
connection removes its bar items; at least one active connection and one bar
item are required to save.

**General** includes menu bar display fields, icon mode and the **Automatic
refresh** slider. Choose 5–60 minutes in steps of 5; the default is 5. Alerts
remains separate.
Dragging changes the draft only. Saving the interval updates the daemon's
schedule without restarting or forcing an extra collection. SwiftBar also
follows the saved interval. Provider cooldowns and request timeouts are
preserved. **Save** applies changes and keeps Settings open. Back or **Cancel**
returns to usage and discards unsaved edits.

**About AI Status** shows the installed version, project details, license,
usage guide and links. Its back control returns to Settings. Authentication
continues to use your provider's own apps and CLIs; Settings does not perform
provider sign-in.

Manage additional accounts with `~/.local/bin/ai-status accounts`. Saved
connections have independent labels and credential sources. For launches from
Finder or at sign-in, file-based credential references avoid depending on shell-only
environment variables. See [multiple accounts and connections](PROVIDERS.md#multiple-accounts-and-connections)
for commands and credential-source examples.

The native app stores preferences in `~/.config/ai-status/selected.json`
and cached usage in `~/.cache/ai-status.json`.
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

The menu bar shows all selected usage labels together. In logo mode, SwiftBar
shows one provider image for the first available selected item. Its dropdown
includes provider logos, progress bars, reset timers and markers for every
selected limit. Click a provider or limit to change the first item while
retaining the additional selections. **Refresh**, **Settings** and **About AI
Status** appear as menu actions. SwiftBar Settings opens the shared terminal
configuration interface, where you can select one or more items; the full
native pages and per-item menu bar logos are available in `--mode native`.
