#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/config.sh" ]; then
    # shellcheck source=./config.sh
    source "$SCRIPT_DIR/config.sh"
fi
: "${REPO_URL:=https://github.com/gelzinn/ai-status}"
INSTALL_DIR="$HOME/.local/share/ai-status"
BIN_DIR="$HOME/.local/bin"

# Migrate old config and cache from waybar-ai-status to ai-status
if [ -d "$HOME/.config/waybar-ai-status" ] && [ ! -d "$HOME/.config/ai-status" ]; then
    mv "$HOME/.config/waybar-ai-status" "$HOME/.config/ai-status"
fi
if [ -d "$HOME/.local/share/omarchy-ai-status" ] && [ ! -d "$INSTALL_DIR" ]; then
    echo "Migrating old installation directory..."
    mv "$HOME/.local/share/omarchy-ai-status" "$INSTALL_DIR"
fi

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating AI Status..."
    git -C "$INSTALL_DIR" pull --ff-only
elif [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR" "$INSTALL_DIR"
elif [ "$SCRIPT_DIR" = "$INSTALL_DIR" ]; then
    # Already at install dir, nothing to copy
    :
elif git -C "$SCRIPT_DIR" rev-parse --git-dir > /dev/null 2>&1; then
    # Running from a local clone — copy directly
    REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
    cp -r "$REPO_ROOT" "$INSTALL_DIR"
else
    echo "Installing AI Status..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Check requirements
bash "$INSTALL_DIR/packages/lib/check.sh"

# Create executable symlink
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/packages/lib/src/bin/ai-status" "$BIN_DIR/ai-status"
# Legacy symlink so users' waybar config doesn't break instantly
ln -sf "$BIN_DIR/ai-status" "$BIN_DIR/waybar-ai-status"

# Restart Waybar to pick up the new module
if command -v waybar &>/dev/null; then
    echo "Restarting Waybar..."
    pkill -SIGUSR2 waybar 2>/dev/null || true
    # If the user relies on restarting via nohup, we can also try that if pkill fails
    if ! pgrep -x waybar > /dev/null; then
        nohup waybar >/dev/null 2>&1 &
        disown
    fi
fi

echo "Done!"
