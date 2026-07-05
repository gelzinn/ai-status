#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$SCRIPT_DIR/config.sh" ]; then
    source "$SCRIPT_DIR/config.sh"
fi

INSTALL_DIR="$HOME/.local/share/ai-status"
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
ln -sf "$INSTALL_DIR/src/bin/ai-status" "$BIN_DIR/ai-status"

OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
    SWIFTBAR_DIRS="${HOME}/.swiftbar/plugins ${HOME}/Library/Application Support/SwiftBar/Plugins"
    for d in $SWIFTBAR_DIRS; do
        if [ -d "$d" ]; then
            mkdir -p "$d"
            wrapper="$d/ai-status.5m.sh"
            echo '#!/bin/bash' > "$wrapper"
            echo "exec $BIN_DIR/ai-status swiftbar" >> "$wrapper"
            chmod +x "$wrapper"
            echo "SwiftBar plugin created at: $wrapper"
            break
        fi
    done
fi

# Restart Waybar (Linux only)
if [ "$OS" = "Linux" ] && command -v waybar &>/dev/null; then
    echo "Restarting Waybar..."
    pkill waybar 2>/dev/null || true
    sleep 0.5
    nohup waybar >/dev/null 2>&1 &
    disown
fi

echo "Done!"
