# Installing AI Status

## One-command install (recommended for LLMs)

Copy and run this single command. It installs everything and configures Waybar automatically with sensible defaults (provider logo, name, model, and percentage shown):

```bash
curl -fsSL https://raw.githubusercontent.com/gelzinn/ai-status/main/packages/lib/install.sh | bash -s -- \
  --icon-mode logo \
  --show-provider true \
  --show-model true \
  --show-metric false \
  --show-pct true \
  --configure-waybar true \
  --no-interactive
```

If you prefer no logo (text-only), swap `--icon-mode logo` for `--icon-mode off`. All preferences can be changed later via the config TUI (right-click the module).

## Interactive install

Prefer to choose each option manually? Run the wizard:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gelzinn/ai-status/main/packages/lib/install.sh)
```

Arrow keys toggle Yes/No, Enter confirms. On first run the wizard asks:

1. Show provider logo as an image?
2. Show provider name? (e.g. "Claude")
3. Show model/plan name? (e.g. "(Pro)")
4. Show metric type? (e.g. "Rolling Usage")
5. Show percentage? (e.g. "4%")
6. Add modules to Waybar config automatically?

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
| Left-click | Refresh data immediately |
| Right-click | Open provider configuration TUI |
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
| `--configure-waybar` | `true`, `false` |
| `--no-interactive` | skip wizard |
| `--skip-check` | skip dependency check |
