# Installing AI Status

## ⚠️ Upgrading from v0.4.x (omarchy-ai-status)?
The project has been renamed to **AI Status**. When you run the install script below, your existing configurations will be migrated automatically. However, **you must update your Waybar config** to use the new `ai-status` command instead of `waybar-ai-status`.

## Quick Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gelzinn/ai-status/main/packages/lib/install.sh)
```

## From a Local Clone

```bash
git clone https://github.com/gelzinn/ai-status.git
cd ai-status
./packages/lib/install.sh
```

## What the Install Script Does

| Step | Action |
|---|---|
| 1 | Clones (or pulls) the repository to `~/.local/share/ai-status/` |
| 2 | Checks system dependencies (Linux, Waybar, python3, jq, curl, git) |
| 3 | Creates a symlink at `~/.local/bin/ai-status` |
| 4 | Restarts Waybar to load the new module |

## After Installing

Add the module to your Waybar config:

```jsonc
"custom/ai-status": {
    "format": "{}",
    "return-type": "json",
    "exec": "~/.local/bin/ai-status daemon",
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
    "tooltip": true
}
```

| Action | Behavior |
|---|---|
| Left-click | Refresh data immediately |
| Right-click | Open provider configuration TUI |
| Scroll up/down | Switch between providers in the status text |
| Middle-click | Cycle metric type (rolling → weekly → monthly) |

The status text shows the usage percentage of the selected provider. Hover to see all providers in the tooltip (the active one is marked with →).

## Updating

Run the same command again -- it detects the existing installation and pulls the latest changes, then restarts Waybar.
