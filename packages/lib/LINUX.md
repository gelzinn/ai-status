# Installing AI Status on Linux

These instructions cover Waybar and the Omarchy Quattro Quickshell widget.

## Requirements and desktop integration

Use a Linux Wayland desktop with **Waybar**, or the **Omarchy Quattro
Quickshell shell** with its plugin CLI. The Quickshell integration is an Omarchy
plugin; arbitrary standalone Quickshell configurations are outside its scope.

The Linux installer and backend require Bash, `python3`, `jq`, and `curl`.
Omarchy plugin installation also needs `git`. For Waybar provider logos,
install an optional SVG rasterizer (`imagemagick` or `librsvg`); text continues
to work without one. Omarchy renders logos directly with Qt. The Waybar
configuration TUI needs an available terminal; Omarchy provides native settings
inside the widget. See [Providers and authentication](PROVIDERS.md) for your
provider's existing session or API credentials.

The [Linux web guide](https://ai-status.gelzin.com/linux) and
[Linux LLM guide](https://ai-status.gelzin.com/linux/llms.txt) both use this
document.

## One-command install (recommended for LLMs)

Copy and run this single command. It detects your active bar and configures Waybar or Omarchy Quickshell with sensible defaults (provider logo, name, model, and percentage shown):

```bash
curl -fsSL https://ai-status.gelzin.com/install | bash -s -- \
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

Add `--usage-display remaining` to show the quota you have left. The default
is `used`; updates preserve your choice unless you pass this flag explicitly.

Use `--bar waybar` or `--bar quickshell` to select explicitly. Automatic detection prefers a running Omarchy shell, then Waybar; when neither is running it uses the only available integration, or Waybar if both are installed. The installer configures and reloads only the selected bar. Existing `--configure-waybar true|false` flags still work and select Waybar; combining them with `--bar quickshell` is an error.

On updates, existing display preferences and provider selection are preserved unless explicit flags or wizard choices replace them. `--no-interactive` without `--configure-bar true` installs but does not add/enable a bar widget.

## Omarchy Quickshell plugin

This integration targets the Omarchy Quattro Quickshell shell. Start the Omarchy shell before installing.

```bash
omarchy plugin add https://github.com/gelzinn/ai-status.git --enable
```

The repository contains the plugin manifest, native QML UI, Python backend, and provider scripts. Direct plugin installation needs no previous AI Status CLI install, no Node, and no NPM. Omarchy manages the installed plugin under `~/.config/omarchy/plugins/io.github.gelzinn.ai-status/`; the shell executes the bundled Python backend.

Dependencies: Linux, the compatible Omarchy Quickshell shell and its plugin CLI, `python3`, `jq`, `curl`, and `git`. Provider-specific authentication and optional CLIs are documented in [PROVIDERS.md](PROVIDERS.md). Quickshell settings run inside the panel without a terminal. The optional CLI configuration TUI (`ai-status config`) needs an available terminal (`foot`, `alacritty`, `kitty`, `ghostty`, `wezterm`, or `xterm`). Qt renders original SVG/raster logos, so no image rasterizer is required. Logos are downloaded from the URLs in the shared provider metadata and cached under `~/.cache/ai-status/quickshell-logos/`; failed images fall back to a placeholder. Provider logos in the panel are independent of the bar's icon preference.

The widget runs inside the existing shell process, using a single Python daemon for all monitors. It shares `~/.config/ai-status/` and provider caches with Waybar. The usage panel shows only providers with valid metrics, including legitimate 0% usage and valid cached results. Providers without usable data stay available in Settings. Initial loading shows “Checking your connected providers…”; cached bars shimmer during refresh and finish independently as each provider responds. Bars use a 1.5-second shimmer, a 1.5-second eased fill, and initial delays of 100 ms plus 150 ms per provider. The panel also shows provider logos, aligned percentages, reset details, and the installed version. Left-click opens/closes the panel. Its fixed header has **Refresh** and **Configure** icons. Right-click or **Configure** switches to the native settings page, where account/limit checkboxes select one or more items for the bar, with no fixed item count and at least one required. You can also toggle display fields and icon mode, and enable/disable or reorder providers. The back arrow sits before the Settings title. **Save** applies preferences and keeps settings open; **Cancel**, Back, or Escape discards any remaining unsaved edits and returns to usage. Saving errors stay in the form. Provider authentication remains documented in [PROVIDERS.md](PROVIDERS.md).

Each selected item has its own usage label in Quickshell and Waybar. In logo mode, Quickshell shows a logo beside each item; Waybar shows one provider image for the first available selected item beside the combined text labels. Existing single-item preferences remain selected after updating. With one bar item configured, click a provider heading or usage metric to switch the selection, scroll the bar to select another provider with valid data, or middle-click to change its metric. With several configured items, usage headings and ordinary metrics are read-only, and bar scrolling and middle-click do not change the selection. The panel shows **Bar items: Settings → Providers**; change the items there, or use the configuration TUI in Waybar. Saved items that are temporarily unavailable still count, so a refresh cannot unlock switching unexpectedly. Credit and reset details remain interactive. Escape on the usage page closes the panel; `r` refreshes, `c` opens settings, and Up/Down scroll. In settings, Tab focuses the form controls; Space or Enter activates the focused control. Preferences are saved only when you press **Save**.

**Providers** uses one compact row per connection with **Active**, the provider name, **Show in bar** and up/down controls. Active connections collect usage even when Show in bar is off. Click the provider name to choose account/limit items in a small menu without adding a second persistent list. Move the provider row to change its order in both Usage and the bar; selected limits within that provider retain their relative order. Saved limits that are temporarily unavailable remain selectable. Disabling a connection removes its bar items; at least one active connection and one bar item are required to save. These changes remain a draft until **Save**.

**General** contains appearance controls and the **Automatic refresh** slider, which chooses 5–60 minutes in steps of 5, defaulting to 5. Dragging changes the draft; **Save** updates the schedule without restarting the daemon, and **Cancel** discards it. Changing only the interval does not force an extra collection. Alerts remains a separate section. Waybar also follows the saved interval through the shared daemon. Manual refresh, request timeouts and provider cooldowns retain their existing protections.

The usage-display and icon selectors open floating lists without expanding the form and use the same right-aligned chevron. Provider logos appear beside account/limit items and provider checkboxes. The header divider reaches the panel borders, and only the Refresh icon rotates during updates.

The bar has no hover tutorial. Open **About AI Status** in Settings for the project logo, description, author, version, commit, MIT license, quick guide and links to GitHub, documentation and bug reports. Back returns to your settings draft. Reset details also use the header's back arrow; their provider logo/name is a plain heading above a rounded table.

The header uses monochrome Lucide vector icons for refresh, configuration, and back, following the shell's foreground color. Claude and Codex show **Reset credits: N available** when usable manual resets exist. Clicking it opens a details page with provider/back navigation, explanation, and a table with reset type, credit count, local expiry date, remaining time, and UTC offset. Expired credits are removed, details are bounded by the authoritative count, and missing expiry details are indicated explicitly. Back or Escape restores the usage page, scroll position, and focused button without changing the bar selection. The same inventory appears in the Waybar tooltip; see [PROVIDERS.md](PROVIDERS.md) for endpoint behavior.

In Quickshell, **Apply** in the narrow action column replaces that row with confirmation of the account, reset type and consumption of **one reset credit**. Hold the confirmation button for **3 seconds** while its background fills. Releasing early or leaving the button resets the progress; Cancel, Back or Escape dismisses confirmation without sending a reset. Details without a usable credit ID or verifiable account remain read-only, as does the Waybar tooltip. Usage and credit inventory refresh after the response. An uncertain result is never retried automatically; refresh and check the account before confirming another reset. See [provider eligibility](PROVIDERS.md#claude).

When a newer stable release is available, the blue **Update available** link opens a compact update page with installed and available versions and the new GitHub release's notes. **Update now** starts the Omarchy updater or Linux installer in a terminal. The fixed actions footer shows the same spinner as Saving and an indeterminate bar while checking the release and opening the terminal, then **Updater opened**. Download and installation continue in Terminal; Omarchy restarts the shell after a successful update. **Update manually…** reveals a copyable alternative and expands automatically on failure. Release notes, manual update and guide controls use matching borders. Results show the notice on the left and a compact **Retry** or **Done** button on the right. **Done**, Back or Escape returns to usage and restores focus. Opening the page does not start an update. Updates remain optional; see [updates and rollback](UPDATES.md).

```bash
# Place the widget (defaults to right on first enable):
omarchy bar move io.github.gelzinn.ai-status --section right

# Update this plugin, then restart the shell after success:
bash ~/.config/omarchy/plugins/io.github.gelzinn.ai-status/packages/lib/update-omarchy.sh

# Disable or remove the plugin without deleting shared credentials/preferences:
omarchy plugin disable io.github.gelzinn.ai-status
omarchy plugin remove io.github.gelzinn.ai-status
```

The update helper recovers blocked fast-forward installs through Omarchy's
plugin manager and restarts the shell only after success. It preserves the
previous checkout under the hidden `.ai-status-backups` directory beside the
installed plugin, keeping provider preferences, credentials and bar placement.
For an older installation without the helper, see the
[one-time recovery command](UPDATES.md#how-it-works).

The AI Status installer offers this same integration with `--bar quickshell --configure-bar true`. It keeps the existing lean CLI installation and uses Omarchy's Git-managed add/update commands for the plugin, preserving its placement. If a plugin folder is not Git-managed, it reports the conflict and leaves that folder untouched.

The script downloads the latest published stable release, even when `main`
has newer commits. Add `--version v0.9.0` to select a specific compatible
release. Packages are verified with SHA-256 and validated before activation;
updates preserve existing preferences unless you pass flags to change them.
See [Updating AI Status](UPDATES.md) for details and rollback.

## Interactive install

Prefer to choose each option manually? Run the wizard:

```bash
bash <(curl -fsSL https://ai-status.gelzin.com/install)
```

Arrow keys change the selected answer; Enter confirms. When both integrations are available and no explicit bar flag was passed, the wizard first offers Quickshell or Waybar. It then asks:

1. Show provider logo as an image?
2. Show provider name? (e.g. "Claude")
3. Show model/plan name? (e.g. "(Pro)")
4. Show metric type? (e.g. "Rolling Usage")
5. Show percentage? (e.g. "4%")
6. Show quota as **Used** or **Remaining**?
7. Add/enable the widget in the selected bar automatically?

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

- `ai-status logo` prints the first available selected item's provider logo PNG path on line 1 and the tooltip on line 2, so hovering the logo shows the same breakdown (loading animation included) as the text module. The image module shows one logo; all selected usage labels remain in the text module.
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
| Scroll up/down | With one bar item configured, switch between providers |
| Middle-click | With one bar item configured, cycle through the provider's limits (rolling → weekly → monthly, and per-model ones like Claude's Fable weekly) |

The config TUI lets you enable/disable providers, reorder with Shift+J/K, select one or more account/limit items for the bar, toggle display settings, switch icon modes (bot, logo, off), and choose **Usage display: Used / Remaining**. Use Space or the left/right arrows to change the display choice, Enter to save, or Escape to cancel.

## Command line

Run `ai-status --help` to see the commands and `ai-status help COMMAND` for
details. Help accepts nested commands, such as `ai-status help accounts add`;
`ai-status accounts add --help` works too. `ai-status --version` prints the
installed version. Running `ai-status` without arguments shows help and exits
successfully.

The examples below use `ai-status`. If `~/.local/bin` is not on your `PATH`,
use `~/.local/bin/ai-status`.

| Task | Command |
| --- | --- |
| Find installed provider IDs and their enabled state | `ai-status providers` |
| Collect usage for enabled connections | `ai-status status` |
| Check the version, paths and installed collectors | `ai-status doctor` |
| Change providers, ordering and display preferences | `ai-status config` |
| Show quota remaining without opening Settings | `ai-status config --usage-display remaining` |
| Show quota used (default) | `ai-status config --usage-display used` |
| Request a refresh of the running app or daemon | `ai-status refresh` |

`status` prints JSON with `providers` and `errors` and updates the usage cache.
`doctor` also prints JSON; it checks the installation without collecting
provider usage. `providers` lists default connections without verifying their
credentials; use `providers --json` for scripts. For example, save a snapshot
with `ai-status status > usage.json`.

The usage display preference changes quota percentages, progress bars, and
amounts with a known limit across the bar and usage panel. **Remaining** shows
`100% - used`, and `$25 / $100` used becomes `$75 / $100` remaining. Raw `status`
JSON, uncapped spend, available balances, and reset credits retain their original
meaning. The CLI option redraws cached usage without fetching
providers again.

### Default sessions and additional accounts

Default connections read credentials saved by the provider's own app or CLI.
For example, your normal Codex login supplies the default Codex connection.
Sign in through that tool and enable the provider with `ai-status config`;
`accounts add` is for additional profiles or explicit credential sources.

`ai-status accounts` is the same as `ai-status accounts list`: it shows default
connections with usable data in the panel's shared cache alongside all saved
additional accounts. Listing reads local data without network requests,
provider login checks or Keychain access. A default connection can still
appear when collection is disabled if its usable cached data remains.
An empty list does not mean your provider CLI is signed out; it may not have
been collected yet.

Rows show the source (`default` or `saved`), collection state (`enabled` or
`disabled`) and recorded usage status:

| Usage status | Meaning |
| --- | --- |
| `available` | Usable usage data is recorded |
| `cached` | Usable data is marked as cached or the snapshot is older than the saved refresh interval |
| `unavailable` | A result exists without usable metrics |
| `not_checked` | No result is recorded for the saved connection |

The table identifies defaults as `default:codex`, for example, and saved
accounts by the ID you chose, such as `work-codex`. Configure defaults with
`ai-status config`; `accounts edit` and `accounts remove` operate on saved IDs.

Use `accounts --refresh` to query enabled connections and update the cache
before listing. Use `accounts --saved` for only saved accounts; these filters
are also accepted after `accounts list`. `--saved` and `--refresh` cannot be
combined. Neither a cached result nor the enabled state confirms a current
provider login.

`accounts --json` returns the combined array with `connection_id`, `source`
and `usage_status` on each record. Default records use the provider ID in `id`;
saved records retain their configured ID and account metadata. For scripts
using the previous saved-account schema, use `accounts --saved --json`.

```bash
# Reference an existing credential file for a separate Codex profile:
ai-status accounts add codex --id work-codex --label Work \
  --auth-file /path/to/work-codex/auth.json

# Read OPENROUTER_WORK_KEY from the environment at query time:
ai-status accounts add openrouter --id work-router --label "Work API" \
  --env OPENROUTER_API_KEY=OPENROUTER_WORK_KEY

ai-status accounts list
ai-status accounts list --json
ai-status accounts list --refresh
ai-status accounts list --saved --json
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
| `--usage-display` | `used` (default), `remaining` |
| `--bar` | `auto` (default), `waybar`, `quickshell` |
| `--configure-bar` | `true`, `false` |
| `--configure-waybar` | `true`, `false`; legacy flag selecting Waybar |
| `--no-interactive` | skip wizard |
| `--skip-check` | skip dependency check |
| `--version` | install a published `vX.Y.Z` version with the remote installer |
| `--rollback` | restore the previous local installation, without a download |

## Daemon interfaces

`ai-status daemon` (or `--format waybar`) keeps the existing newline-delimited `{text, tooltip}` JSON/Pango contract; `text` contains the selected usage labels together. `ai-status daemon --format quickshell` emits snapshots with `schemaVersion: 1`, `text`, `version`, `selected`, `barItems`, `iconMode`, `logoPath`, `loading`, and `providers`. `barItems` contains the ordered visible selections, each with `provider`, `idx`, `metric`, `text`, `logoPath`, and `loading`. The legacy `selected` and `logoPath` fields describe the first visible item. `settings.items` retains the ordered saved selections. Temporarily unavailable selections remain saved and reappear when usable data returns. Providers contain stable `id`/`idx`, `name`, `loading`, `cached`, `error`, and `metrics`; metrics contain `key`, `type`, `name`, `percentage`, `resetInSeconds`, and plain-text `detail`. Loading snapshots arrive as each provider finishes; animation is handled by the UI rather than encoded as Pango. Providers without valid metrics are omitted; `settings` still contains all configurable providers. `resetCredits` contains live counts and structured display rows for the separate details page. Eligible rows include opaque `actionId` handles; fresh actionable providers also include `resetAction.fingerprint` to bind confirmation to that account observation.

`ai-status scroll-up --frontend quickshell` and `scroll-down --frontend quickshell` change the shared selection without writing Waybar's logo or sending it refresh signals. `ai-status select-metric --frontend quickshell --selection-json '{"provider":"codex","idx":0,"metric":"weekly"}'` selects an available metric without fetching again. Selection commands leave preferences unchanged when more than one bar item is configured, including temporarily unavailable items; use Settings or the configuration TUI to edit that list. Existing commands default to Waybar behavior. `ai-status revert` continues to restore only the Waybar backup.
