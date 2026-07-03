# Updating Omarchy AI Status

**Updates use the same command as installation -- the install script handles both fresh installs and upgrades automatically.**

## Update Command

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/gelzinn/omarchy-ai-status/main/install.sh)
```

Or from a local clone:

```bash
./install.sh
```

## How It Works

The script maintains a clone at `~/.local/share/omarchy-ai-status/`. On each run it detects whether:

| State | Action |
|---|---|
| First install | Clones the repository and sets up symlinks |
| Already installed | Pulls latest changes via `git pull` |
| Stale directory | Removes and reclones |
| Local clone | Copies files directly |

After updating, the script restarts Waybar automatically to apply changes.

## Checking Your Version

The current version is shown at the top of the Waybar tooltip. You can also check:

```bash
cat ~/.local/share/omarchy-ai-status/VERSION
```
