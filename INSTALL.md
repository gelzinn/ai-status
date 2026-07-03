# Installing Omarchy AI Status

## Quick Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gelzinn/omarchy-ai-status/main/install.sh)
```

## From a Local Clone

```bash
git clone https://github.com/gelzinn/omarchy-ai-status.git
cd omarchy-ai-status
./install.sh
```

## What the Install Script Does

| Step | Action |
|---|---|
| 1 | Clones (or pulls) the repository to `~/.local/share/omarchy-ai-status/` |
| 2 | Checks system dependencies (Linux, Waybar, python3, jq, curl, git) |
| 3 | Creates a symlink at `~/.local/bin/waybar-ai-status` |
| 4 | Restarts Waybar to load the new module |

## After Installing

Add the module to your Waybar config:

```jsonc
"custom/ai-status": {
    "format": "{}",
    "return-type": "json",
    "exec": "~/.local/bin/waybar-ai-status daemon",
    "on-click": "~/.local/bin/waybar-ai-status refresh",
    "on-click-right": "~/.local/bin/waybar-ai-status config",
    "tooltip": true
}
```

Left-click refreshes data immediately. Right-click opens the provider configuration TUI.

## Updating

Run the same command again -- it detects the existing installation and pulls the latest changes, then restarts Waybar.
