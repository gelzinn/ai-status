# Updating AI Status

**Updates use the same command as installation -- the install script handles both fresh installs and upgrades automatically.**

## Update Command

```bash
curl -fsSL https://ai-status.gelzin.com/install | bash
```

Or from a local clone:

```bash
bash packages/lib/install.sh
```

## How It Works

The script installs a **lean copy** at `~/.local/share/ai-status/` — only the
library itself (`packages/lib` plus the shared provider metadata), never the
website, `node_modules`, or build output. Each run re-extracts that copy, so the
same command covers every case:

| State | Action |
|---|---|
| First install | Extracts the lib and sets up symlinks |
| Already installed | Re-extracts the latest version (this is the update) |
| Local checkout | Extracts from your working tree, local edits included |
| Older full-repo install | Replaced with the lean copy automatically |

After updating, the script restarts Waybar automatically to apply changes.

## Checking Your Version

The current version is shown at the top of the Waybar tooltip. You can also check:

```bash
cat ~/.local/share/ai-status/packages/lib/VERSION
```
