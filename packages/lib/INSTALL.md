# Installing AI Status

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

The widget runs inside the existing shell process, using a single Python daemon for all monitors. It shares `~/.config/ai-status/` and provider caches with Waybar. The panel shows loading and error states, cached results, provider logos, percentages beside progress bars, reset details, and the installed version. Left-click opens/closes the panel. Its fixed header has **Refresh** and **Configure** icons. Right-click or **Configure** switches to the native settings page, where you choose the active provider/limit, toggle display fields and icon mode, and enable/disable or reorder providers. **Save** applies preferences; **Cancel**, Back, or Escape discards the draft and returns to usage. Saving errors stay in the form. Provider authentication remains documented in [PROVIDERS.md](PROVIDERS.md).

Scroll the bar to switch providers; middle-click switches metrics. Escape on the usage page closes the panel; `r` refreshes, `c` opens settings, and Up/Down scroll. In settings, Tab focuses the form controls; Space or Enter activates the focused control. Preferences are saved only when you press **Save**.

The header uses monochrome Lucide vector icons for refresh, configuration, and back, matching the landing page's icon family and following the shell's foreground color. Claude and Codex show a separate **Reset credits** section when the provider reports available manual resets, including labels and expiration details. The same inventory appears in the Waybar tooltip; see [PROVIDERS.md](PROVIDERS.md) for endpoint behavior.

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

## CLI flags reference

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

## Daemon interfaces

`ai-status daemon` (or `--format waybar`) keeps the existing newline-delimited `{text, tooltip}` JSON/Pango contract. `ai-status daemon --format quickshell` emits snapshots with `schemaVersion: 1`, `text`, `version`, `selected`, `iconMode`, `logoPath`, `loading`, and `providers`. Providers contain stable `id`/`idx`, `name`, `loading`, `cached`, `error`, and `metrics`; metrics contain `key`, `type`, `name`, `percentage`, `resetInSeconds`, and plain-text `detail`. Loading snapshots arrive as each provider finishes; animation is handled by the UI rather than encoded as Pango.

`ai-status scroll-up --frontend quickshell` and `scroll-down --frontend quickshell` change the shared selection without writing Waybar's logo or sending it refresh signals. Existing commands default to Waybar behavior. `ai-status revert` continues to restore only the Waybar backup.

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
