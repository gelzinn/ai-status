# Installing AI Status

For the native Windows 10/11 tray app and bundled installer, follow the
[Windows guide](WINDOWS.md). For the native macOS menu bar app, see
[macOS setup](MACOS.md). The Bash/Waybar instructions below are for Linux.

## One-command install (recommended for LLMs)

Copy and run this single command. It detects your active bar and configures Waybar or Omarchy Quickshell with sensible defaults (provider logo, name, model, and percentage shown):

```bash
curl -fsSL https://raw.githubusercontent.com/gelzinn/ai-status/main/packages/lib/install.sh | bash -s -- \
  --icon-mode logo \
  --show-provider true \
  --show-model true \
  --show-metric false \
  --show-pct true \
  --bar auto \
  --configure-bar true \
  --no-interactive
```

If you prefer no logo (text-only), swap `--icon-mode logo` for `--icon-mode off`. Right-click the module to change preferences later: Quickshell has a native settings page and Waybar uses the config TUI.

Use `--bar waybar` or `--bar quickshell` to select explicitly. Automatic detection prefers a running Omarchy shell, then Waybar; when neither is running it uses the only available integration, or Waybar if both are installed. The installer configures and reloads only the selected bar. Existing `--configure-waybar true|false` flags still work and select Waybar; combining them with `--bar quickshell` is an error.

On updates, existing display preferences and provider selection are preserved unless explicit flags or wizard choices replace them. `--no-interactive` without `--configure-bar true` installs but does not add/enable a bar widget.

## Omarchy Quickshell plugin

This integration targets the new Omarchy shell (Quattro), not arbitrary standalone Quickshell configurations. Start the Omarchy shell before installing.

```bash
omarchy plugin add https://github.com/gelzinn/ai-status.git --enable
```

The repository contains the plugin manifest, native QML UI, Python backend, and provider scripts. Direct plugin installation needs no previous AI Status CLI install, no Node, and no NPM. It creates a Git checkout under `~/.config/omarchy/plugins/io.github.gelzinn.ai-status/`. This includes repository source but no website dependencies or build artifacts; the shell executes the bundled Python backend.

Dependencies: Linux, the compatible Omarchy Quickshell shell and its plugin CLI, `python3`, `jq`, `curl`, and `git`. Provider-specific authentication and optional CLIs are documented in [PROVIDERS.md](PROVIDERS.md). Quickshell settings run inside the panel without a terminal. The optional CLI configuration TUI (`ai-status config`) needs an available terminal (`foot`, `alacritty`, `kitty`, `ghostty`, `wezterm`, or `xterm`). Qt renders original SVG/raster logos, so no image rasterizer is required. Logos are downloaded from the URLs in the shared provider metadata and cached under `~/.cache/ai-status/quickshell-logos/`; failed images fall back to a placeholder. Provider logos in the panel are independent of the bar's icon preference.

The widget runs inside the existing shell process, using a single Python daemon for all monitors. It shares `~/.config/ai-status/` and provider caches with Waybar. The usage panel shows only providers with valid metrics, including legitimate 0% usage and valid cached results. Providers without usable data stay available in Settings. Initial loading shows “Checking your connected providers…”; cached bars shimmer during refresh and finish independently as each provider responds. Bars use the Windows preview animation: a 1.5-second shimmer, a 1.5-second eased fill, and initial delays of 100 ms plus 150 ms per provider. The panel also shows provider logos, aligned percentages, reset details, and the installed version. Left-click opens/closes the panel. Its fixed header has **Refresh** and **Configure** icons. Right-click or **Configure** switches to the native settings page, where you choose the active provider/limit, toggle display fields and icon mode, and enable/disable or reorder providers. The back arrow sits before the Settings title. **Save** applies preferences and keeps settings open; **Cancel**, Back, or Escape discards any remaining unsaved edits and returns to usage. Saving errors stay in the form. Provider authentication remains documented in [PROVIDERS.md](PROVIDERS.md).

Click a provider heading or usage metric to select it immediately. Scroll the bar to switch between providers with valid data; middle-click switches metrics. Escape on the usage page closes the panel; `r` refreshes, `c` opens settings, and Up/Down scroll. In settings, Tab focuses the form controls; Space or Enter activates the focused control. Preferences are saved only when you press **Save**.

Both settings selectors open floating lists without expanding the form. Provider names match the landing page, and their logos appear in the active limit and its options and beside every provider checkbox. Both selectors use the same right-aligned chevron. The header divider reaches the panel borders, and only the Refresh icon rotates during updates.

The bar has no hover tutorial. Open **About AI Status** in Settings for the project logo, description, author, version, commit, MIT license, quick guide and links to GitHub, documentation and bug reports. Back returns to your settings draft. Reset details also use the header's back arrow; their provider logo/name is a plain heading above a rounded table.

The header uses monochrome Lucide vector icons for refresh, configuration, and back, matching the landing page's icon family and following the shell's foreground color. Claude and Codex show **Reset credits: N available** when usable manual resets exist. Clicking it opens the same details layout as Windows: provider/back navigation, explanation, and a table with reset type, credit count, local expiry date, remaining time, and UTC offset. Expired credits are removed, details are bounded by the authoritative count, and missing expiry details are indicated explicitly. Back or Escape restores the usage page, scroll position, and focused button without changing the bar selection. The same inventory appears in the Waybar tooltip; see [PROVIDERS.md](PROVIDERS.md) for endpoint behavior.

```bash
# Place the widget (defaults to right on first enable):
omarchy bar move io.github.gelzinn.ai-status --section right

# Update only this plugin:
omarchy plugin update io.github.gelzinn.ai-status

# Disable or remove the plugin without deleting shared credentials/preferences:
omarchy plugin disable io.github.gelzinn.ai-status
omarchy plugin remove io.github.gelzinn.ai-status
```

The AI Status installer offers this same integration with `--bar quickshell --configure-bar true`. It keeps the existing lean CLI installation and uses Omarchy's Git-managed add/update commands for the plugin, preserving its placement. If a plugin folder is not Git-managed, it reports the conflict and leaves that folder untouched. A local development install clones the checkout's committed HEAD; uncommitted QML edits must be tested in a user-owned plugin copy instead.

The script downloads the latest published stable release, even when `main`
has newer commits. Add `--version v0.9.0` to select a specific compatible
release. Packages are verified with SHA-256 and validated before activation;
updates preserve existing preferences unless you pass flags to change them.
See [Updating AI Status](UPDATES.md) for details and rollback.

## Interactive install

Prefer to choose each option manually? Run the wizard:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gelzinn/ai-status/main/packages/lib/install.sh)
```

Arrow keys toggle Yes/No, Enter confirms. When both integrations are available and no explicit bar flag was passed, the wizard first offers Quickshell or Waybar. It then asks:

1. Show provider logo as an image?
2. Show provider name? (e.g. "Claude")
3. Show model/plan name? (e.g. "(Pro)")
4. Show metric type? (e.g. "Rolling Usage")
5. Show percentage? (e.g. "4%")
6. Add/enable the widget in the selected bar automatically?

## macOS menu bar app

```bash
curl -fsSL https://ai-status.gelzin.com/install/macos | bash
```

The default native mode builds a SwiftUI/AppKit menu bar app with the shared Python backend. It follows the same Usage, Settings, reset-credit and About page layout as Windows and Omarchy Quickshell. Click the menu bar item to open the panel, then choose a provider or limit. Refresh and Settings stay in the header.

Requires macOS 13+, Python 3.10+ and Xcode Command Line Tools (`xcode-select --install`). SwiftBar is optional. The installer uses the latest stable release with checksum verification; running it from a checkout installs that checkout's code. Re-run to update while preserving your preferences. A user LaunchAgent starts the native app at sign-in.

For the SwiftBar dropdown integration, pass `--mode stream` (animated) or `--mode periodic`. Those modes also require [SwiftBar](https://swiftbar.app).

See [MACOS.md](MACOS.md) for requirements, branch testing, menu actions and validation on a Mac.

## Manual Waybar config

If you skipped automatic Waybar setup, add these blocks to `~/.config/waybar/config.jsonc`:

```jsonc
"custom/ai-status": {
    "exec": "~/.local/bin/ai-status daemon",
    "restart-interval": 1,
    "return-type": "json",
    "format": "{}",
    "tooltip": true,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric"
}
```

To also show the provider logo (with the same tooltip on hover), add this image module.

> The one-command install with `--icon-mode logo` sets all of this up for you. The manual steps below are only needed if you skipped automatic Waybar setup.

```jsonc
"image#ai-status": {
    "exec": "~/.local/bin/ai-status logo",
    "size": 14,
    "interval": 3,
    "signal": 11,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
    "tooltip": true
}
```

Notes for the logo module:

- `ai-status logo` prints the logo PNG path on line 1 and the tooltip on line 2, so hovering the logo shows the same breakdown (loading animation included) as the text module.
- `"interval"` is required for the image to render; `"signal": 11` refreshes it instantly on provider/data changes.
- Rendering the logo needs an SVG rasterizer (`imagemagick` or `librsvg`); logos are rasterised to opaque RGB PNGs. Without a rasterizer the logo is simply skipped.

Include both in your layout section, with `image#ai-status` before `custom/ai-status`:

```jsonc
"modules-right": [
    "image#ai-status",
    "custom/ai-status",
    "network",
    "clock",
    "tray"
]
```

Then enable logo mode: right-click the module, open the config TUI, set **Provider Icon** to **Provider Logo**.

## Reverting

When you let the installer configure Waybar automatically, it backs up your existing config to `~/.config/waybar/config.jsonc.ai-status.bak` **before** touching anything. If something looks off, restore it with:

```bash
ai-status revert
```

This copies the backup back (saving the current one as `.pre-revert` first) and reloads Waybar. If you added the modules by hand, there's no backup — just remove them yourself.

## Usage

| Action | Behavior |
|---|---|
| Left-click | Refresh in Waybar; open/close the details panel in Quickshell |
| Right-click | Native settings page in Quickshell; provider configuration TUI in Waybar |
| Scroll up/down | Switch between providers |
| Middle-click | Cycle through the provider's limits (rolling → weekly → monthly, and per-model ones like Claude's Fable weekly) |

The config TUI lets you enable/disable providers, reorder with Shift+J/K, toggle display settings, and switch icon modes (bot, logo, off).

## Command line

Run `ai-status --help` to see the commands and `ai-status help COMMAND` for
details. Help accepts nested commands, such as `ai-status help accounts add`;
`ai-status accounts add --help` works too. `ai-status --version` prints the
installed version. On Linux, running `ai-status` without arguments shows help
and exits successfully. On Windows and macOS, it opens the native app.

The examples below use `ai-status`. If `~/.local/bin` is not on your Linux or
macOS `PATH`, use `~/.local/bin/ai-status`. In the Windows installation or
portable folder, use `.\ai-status-cli.exe` from PowerShell.

| Task | Command |
| --- | --- |
| Find installed provider IDs and their enabled state | `ai-status providers` |
| Collect usage for enabled connections | `ai-status status` |
| Check the version, paths and installed collectors | `ai-status doctor` |
| Change providers, ordering and display preferences | `ai-status config` |
| Request a refresh of the running app or daemon | `ai-status refresh` |

`status` prints JSON with `providers` and `errors` and updates the usage cache.
`doctor` also prints JSON; it checks the installation without collecting
provider usage. `providers` lists default connections without verifying their
credentials; use `providers --json` for scripts. For example, save a snapshot
with `ai-status status > usage.json`.

### Default sessions and additional accounts

Default connections read credentials saved by the provider's own app or CLI.
For example, your normal Codex login supplies the default Codex connection.
Sign in through that tool and enable the provider with `ai-status config`;
`accounts add` is for additional profiles or explicit credential sources.

`ai-status accounts` is the same as `ai-status accounts list`: it lists saved
additional connections, separately from default sessions. An empty account
list does not mean your provider CLI is signed out. Use `status` to check usage
and provider errors.

```bash
# Reference an existing credential file for a separate Codex profile:
ai-status accounts add codex --id work-codex --label Work \
  --auth-file /path/to/work-codex/auth.json

# Read OPENROUTER_WORK_KEY from the environment at query time:
ai-status accounts add openrouter --id work-router --label "Work API" \
  --env OPENROUTER_API_KEY=OPENROUTER_WORK_KEY

ai-status accounts list
ai-status accounts list --json
ai-status accounts edit work-router --disabled
ai-status accounts remove work-router
```

Replace the auth-file path with the existing profile's credential file.
`--id` identifies the account for later edits or removal; `--label` is the name
shown in the panel. `--env TARGET=SOURCE_ENV` names the provider's expected
variable and the source variable to read; it saves the reference, not the key
value. Make that source variable available to the running app or daemon.
For launches outside your shell, use credential-file references as described
in the [account guide](PROVIDERS.md#multiple-accounts-and-connections).
Removing a connection keeps its provider credential files.

## Installer flags reference

These flags belong to `install.sh`. The installer's `--version vX.Y.Z` selects
a release; the CLI's `ai-status --version` prints the installed version.

| Flag | Values |
|---|---|
| `--icon-mode` | `logo`, `off`, `bot` |
| `--show-provider` | `true`, `false` |
| `--show-model` | `true`, `false` |
| `--show-metric` | `true`, `false` |
| `--show-pct` | `true`, `false` |
| `--bar` | `auto` (default), `waybar`, `quickshell` |
| `--configure-bar` | `true`, `false` |
| `--configure-waybar` | `true`, `false`; legacy flag selecting Waybar |
| `--no-interactive` | skip wizard |
| `--skip-check` | skip dependency check |
| `--version` | install a published `vX.Y.Z` version with the remote installer |
| `--rollback` | restore the previous local installation, without a download |

## Daemon interfaces

`ai-status daemon` (or `--format waybar`) keeps the existing newline-delimited `{text, tooltip}` JSON/Pango contract. `ai-status daemon --format quickshell` emits snapshots with `schemaVersion: 1`, `text`, `version`, `selected`, `iconMode`, `logoPath`, `loading`, and `providers`. Providers contain stable `id`/`idx`, `name`, `loading`, `cached`, `error`, and `metrics`; metrics contain `key`, `type`, `name`, `percentage`, `resetInSeconds`, and plain-text `detail`. Loading snapshots arrive as each provider finishes; animation is handled by the UI rather than encoded as Pango. Providers without valid metrics are omitted; `settings` still contains all configurable providers. `resetCredits` contains live counts and structured display rows for the separate details page.

`ai-status scroll-up --frontend quickshell` and `scroll-down --frontend quickshell` change the shared selection without writing Waybar's logo or sending it refresh signals. `ai-status select-metric --frontend quickshell --selection-json '{"provider":"codex","idx":0,"metric":"weekly"}'` selects an available metric without fetching again. Existing commands default to Waybar behavior. `ai-status revert` continues to restore only the Waybar backup.

## Development validation

```bash
python3 -m unittest discover -s packages/lib/tests -v
omarchy plugin validate ~/.config/omarchy/plugins/io.github.gelzinn.ai-status
qmllint -I "$OMARCHY_PATH/shell" \
  ~/.config/omarchy/plugins/io.github.gelzinn.ai-status/packages/lib/quickshell/*.qml
omarchy-shell shell summon io.github.gelzinn.ai-status '{}'
omarchy-shell shell hide io.github.gelzinn.ai-status
```

Validate a clean checkout/plugin folder: the Omarchy validator rejects symlinks, including those in local `node_modules`. On an Omarchy desktop, check click, Escape, repeat open/close, scroll, middle-click, configuration, themes, horizontal/vertical bars, and multiple monitors. Confirm one Python daemon across monitors and that disabling/removing the plugin stops it. Check hot reload, shell restart, backend restart, provider errors, and missing logos. Test Waybar separately with its existing modules and `ai-status revert`.
