#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/config.sh" ]; then
    # shellcheck source=./config.sh
    source "$SCRIPT_DIR/config.sh"
fi
: "${REPO_URL:=https://github.com/gelzinn/omarchy-ai-status}"
INSTALL_DIR="$HOME/.local/share/omarchy-ai-status"
BIN_DIR="$HOME/.local/bin"

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating Omarchy AI Status..."
    git -C "$INSTALL_DIR" pull --ff-only
elif [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR" "$INSTALL_DIR"
elif [ "$SCRIPT_DIR" = "$INSTALL_DIR" ]; then
    # Already at install dir, nothing to copy
    :
elif git -C "$SCRIPT_DIR" rev-parse --git-dir > /dev/null 2>&1; then
    # Running from a local clone — copy directly
    cp -r "$SCRIPT_DIR" "$INSTALL_DIR"
else
    echo "Installing Omarchy AI Status..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Check requirements
bash "$INSTALL_DIR/check.sh"

# Create executable symlink
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/src/bin/waybar-ai-status" "$BIN_DIR/waybar-ai-status"

# Restart Waybar to pick up the new module
if command -v waybar &>/dev/null; then
    echo "Restarting Waybar..."
    pkill waybar 2>/dev/null || true
    sleep 0.5
    nohup waybar >/dev/null 2>&1 &
    disown
fi

echo "Done!"
