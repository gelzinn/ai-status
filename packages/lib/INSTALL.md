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

To also show the provider logo, add this image module.

> The one-command install with `--icon-mode logo` sets all of this up for you (absolute path, signal, size, and logo mode). The manual steps below are only needed if you skipped automatic Waybar setup.

```jsonc
"image#ai-status": {
    "path": "/home/YOUR_USERNAME/.cache/ai-status/logos/current.png",
    "size": 14,
    "signal": 11,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
    "tooltip": false
}
```

Notes for the logo module:

- **Use an absolute `path`** — Waybar does not expand `~` in `path`, so replace `YOUR_USERNAME` with your user. (The `on-*` handlers run through a shell, so `~` is fine there.)
- ai-status keeps `current.png` in sync with the selected provider and reloads it live via `"signal": 11`. Do **not** use `"exec"` here — Waybar's image `exec` mode blanks the whole bar on some builds.
- Rendering the logo needs an SVG rasterizer (`imagemagick` or `librsvg`); without it the logo is simply skipped.

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

## Usage

| Action | Behavior |
|---|---|
| Left-click | Refresh data immediately |
| Right-click | Open provider configuration TUI |
| Scroll up/down | Switch between providers |
| Middle-click | Cycle metric type (rolling → weekly → monthly) |

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
