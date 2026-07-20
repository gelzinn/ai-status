#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════
# AI Status — macOS installer (SwiftBar menu-bar plugin)
#
# The Linux installer wires a Waybar module; macOS has no Waybar, so this drops
# a SwiftBar plugin into your SwiftBar plugin folder. The plugin renders the
# same provider usage data (shared core in packages/lib) and, in streaming
# mode, animates the Claude spark in the menu bar while it refreshes.
#
#   curl -fsSL https://ai-status.gelzin.com/install/macos | bash
#
# Re-run to update. Requires SwiftBar (https://swiftbar.app) and python3.
# ═══════════════════════════════════════════════════════════

export TERM=xterm-256color

C_GREEN=$'\033[0;32m'
C_CYAN=$'\033[0;36m'
C_PURPLE=$'\033[0;35m'
C_YELLOW=$'\033[0;33m'
C_RED=$'\033[0;31m'
C_DIM=$'\033[2m'
C_RESET=$'\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/config.sh" ]; then
    # shellcheck source=./config.sh
    source "$SCRIPT_DIR/config.sh"
fi
: "${REPO_URL:=https://github.com/gelzinn/ai-status}"

INSTALL_DIR="$HOME/.local/share/ai-status"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/ai-status"
SWIFTBAR_BUNDLE="com.ameba.SwiftBar"

# ── flags ─────────────────────────────────────────────────
MODE="stream"          # stream (animated) | periodic (simple, re-run on interval)
SKIP_CHECK=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)         MODE="$2"; shift 2 ;;
        --skip-check)   SKIP_CHECK=true; shift ;;
        --no-interactive) shift ;;   # accepted for parity; this installer is non-interactive
        *) echo "Unknown flag: $1"; exit 1 ;;
    esac
done
case "$MODE" in stream|periodic) ;; *) echo "Invalid --mode: $MODE (stream|periodic)"; exit 1 ;; esac

echo ""
echo -e "  ${C_YELLOW}AI Status${C_RESET} ${C_DIM}— macOS installer${C_RESET}"
echo ""

# ── OS guard ──────────────────────────────────────────────
if [ "$(uname -s)" != "Darwin" ]; then
    echo -e "  ${C_RED}✖${C_RESET} This installer is for macOS."
    echo -e "  ${C_DIM}On Linux use:${C_RESET} curl -fsSL https://ai-status.gelzin.com/install | bash"
    exit 1
fi

# ── requirements ──────────────────────────────────────────
if [ "$SKIP_CHECK" = false ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo -e "  ${C_RED}✖${C_RESET} python3 not found (required)."
        echo -e "  ${C_DIM}Install the Xcode Command Line Tools:${C_RESET} xcode-select --install"
        exit 1
    fi
    echo -e "  ${C_GREEN}✔${C_RESET} python3"
fi

# ═══════════════════════════════════════════════════════════
# INSTALL / UPDATE (extract only packages/lib + packages/shared)
# ═══════════════════════════════════════════════════════════

USE_LOCAL_LIB=false
if [ "$SCRIPT_DIR" != "$INSTALL_DIR/packages/lib" ] && git -C "$SCRIPT_DIR" rev-parse --git-dir > /dev/null 2>&1; then
    USE_LOCAL_LIB=true
fi

RUNNING_FROM_INSTALL=false
case "$SCRIPT_DIR/" in "$INSTALL_DIR"/*) RUNNING_FROM_INSTALL=true ;; esac

lean_extract() {
    local src="$1"
    [ -d "$src/packages/lib" ] || { echo -e "  ${C_DIM}error: packages/lib not found in $src${C_RESET}" >&2; exit 1; }
    [ -n "$INSTALL_DIR" ] || { echo -e "  ${C_DIM}error: INSTALL_DIR is empty, refusing to remove${C_RESET}" >&2; exit 1; }
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/packages"
    cp -R "$src/packages/lib" "$INSTALL_DIR/packages/lib"
    cp -R "$src/packages/shared" "$INSTALL_DIR/packages/shared"
}

mkdir -p "$(dirname "$INSTALL_DIR")"

if [ "$RUNNING_FROM_INSTALL" = true ]; then
    echo -e "  ${C_DIM}> running from the installed copy — nothing to extract${C_RESET}"
elif [ "$USE_LOCAL_LIB" = true ]; then
    echo -e "  ${C_DIM}> installing from local checkout...${C_RESET}"
    REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
    lean_extract "$REPO_ROOT"
else
    echo -e "  ${C_DIM}> installing...${C_RESET}"
    command -v git >/dev/null 2>&1 || { echo -e "  ${C_RED}✖${C_RESET} git not found (required to install)."; exit 1; }
    TMP_CLONE="$(mktemp -d)"
    trap 'rm -rf "$TMP_CLONE"' EXIT
    git clone --depth 1 "$REPO_URL" "$TMP_CLONE/repo" 2>&1 | while IFS= read -r line; do echo -e "  ${C_DIM}${line}${C_RESET}"; done
    [ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
    lean_extract "$TMP_CLONE/repo"
    rm -rf "$TMP_CLONE"
    trap - EXIT
fi

# ═══════════════════════════════════════════════════════════
# SYMLINK
# ═══════════════════════════════════════════════════════════

mkdir -p "$BIN_DIR"
if [ "$RUNNING_FROM_INSTALL" = false ]; then
    ln -sf "$INSTALL_DIR/packages/lib/src/bin/ai-status" "$BIN_DIR/ai-status"
fi
chmod +x "$INSTALL_DIR/packages/lib/src/bin/ai-status" 2>/dev/null || true
echo -e "  ${C_GREEN}✔${C_RESET} ${C_DIM}binary linked at${C_RESET} $BIN_DIR/ai-status"

# ═══════════════════════════════════════════════════════════
# DISPLAY PREFERENCES (seed defaults, never clobber existing)
# ═══════════════════════════════════════════════════════════

mkdir -p "$CONFIG_DIR"
python3 - "$CONFIG_DIR/selected.json" <<'PYEOF'
import json, os, sys

path = sys.argv[1]
existing = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            existing = json.load(f)
    except Exception:
        existing = {}

existing.setdefault("provider", "claude")
existing.setdefault("idx", 0)
existing.setdefault("metric", "rolling")
existing.setdefault("show_provider", True)
existing.setdefault("show_model", True)
existing.setdefault("show_metric", False)
existing.setdefault("show_pct", True)

with open(path, "w") as f:
    json.dump(existing, f, indent=2)
print(f"  \033[2msaved display preferences to {path}\033[0m")
PYEOF

# ═══════════════════════════════════════════════════════════
# SWIFTBAR PLUGIN
# ═══════════════════════════════════════════════════════════

echo ""
echo -e "  ${C_PURPLE}${C_DIM}swiftbar plugin${C_RESET}"

SWIFTBAR_INSTALLED=false
if [ -d "/Applications/SwiftBar.app" ] || \
   [ -d "$HOME/Applications/SwiftBar.app" ] || \
   defaults read "$SWIFTBAR_BUNDLE" PluginDirectory >/dev/null 2>&1; then
    SWIFTBAR_INSTALLED=true
fi

# Resolve the SwiftBar plugin folder from its preference; fall back to the
# conventional Application Support path and register it so SwiftBar picks it up.
PLUGIN_DIR="$(defaults read "$SWIFTBAR_BUNDLE" PluginDirectory 2>/dev/null || true)"
if [ -z "$PLUGIN_DIR" ]; then
    PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"
    mkdir -p "$PLUGIN_DIR"
    # Point SwiftBar at this folder (harmless if SwiftBar isn't installed yet).
    defaults write "$SWIFTBAR_BUNDLE" PluginDirectory "$PLUGIN_DIR" >/dev/null 2>&1 || true
    echo -e "  ${C_DIM}using default plugin folder: $PLUGIN_DIR${C_RESET}"
else
    mkdir -p "$PLUGIN_DIR"
    echo -e "  ${C_DIM}using SwiftBar plugin folder: $PLUGIN_DIR${C_RESET}"
fi

# One ai-status plugin only — clear any previous variant before writing.
rm -f "$PLUGIN_DIR"/ai-status.*.py 2>/dev/null || true

if [ "$MODE" = "stream" ]; then
    PLUGIN_FILE="$PLUGIN_DIR/ai-status.5s.py"
    SUBCOMMAND="swiftbar-stream"
    TYPE_META="$(cat <<'EOF'
# <swiftbar.type>streamable</swiftbar.type>
# <swiftbar.useTrailingStreamSeparator>true</swiftbar.useTrailingStreamSeparator>
EOF
)"
else
    PLUGIN_FILE="$PLUGIN_DIR/ai-status.30s.py"
    SUBCOMMAND="swiftbar"
    TYPE_META=""
fi

cat > "$PLUGIN_FILE" <<PLUGIN
#!/usr/bin/env python3
# <xbar.title>AI Status</xbar.title>
# <xbar.version>v${VERSION:-0.0.0}</xbar.version>
# <xbar.author>gelzin</xbar.author>
# <xbar.author.github>gelzinn</xbar.author.github>
# <xbar.desc>Monitor AI provider usage limits (Claude, Codex, Copilot, and more) in your menu bar.</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>
# <xbar.abouturl>https://github.com/gelzinn/ai-status</xbar.abouturl>
${TYPE_META}
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
"""SwiftBar plugin shim — generated by install-macos.sh.

Hands off to the installed ai-status binary, which renders the SwiftBar menu
from the shared provider core. Edit nothing here; re-run the installer to
switch between 'stream' (animated) and 'periodic' modes.
"""
import os
import sys

_bin = os.path.expanduser("~/.local/bin/ai-status")
if not os.path.exists(_bin):
    print("AI Status")
    print("---")
    print("ai-status not found — reinstall | color=#ff3b30")
    print("curl -fsSL https://ai-status.gelzin.com/install/macos | bash | "
          "bash=/bin/bash param1=-lc param2=\"curl -fsSL https://ai-status.gelzin.com/install/macos | bash\" terminal=true")
    sys.exit(0)

os.execv(_bin, [_bin, "${SUBCOMMAND}"])
PLUGIN

chmod +x "$PLUGIN_FILE"
echo -e "  ${C_GREEN}✔${C_RESET} ${C_DIM}wrote${C_RESET} $PLUGIN_FILE ${C_DIM}(${MODE} mode)${C_RESET}"

# Seed the cache so the menu shows data on first paint (best-effort, ~seconds).
echo -e "  ${C_DIM}> fetching initial provider usage...${C_RESET}"
"$BIN_DIR/ai-status" swiftbar-refresh >/dev/null 2>&1 || true

# ═══════════════════════════════════════════════════════════
# ACTIVATE
# ═══════════════════════════════════════════════════════════

echo ""
if [ "$SWIFTBAR_INSTALLED" = true ]; then
    # Nudge SwiftBar to pick up the new/updated plugin.
    open -g "swiftbar://refreshallplugins" >/dev/null 2>&1 || true
    if ! pgrep -x SwiftBar >/dev/null 2>&1; then
        open -a SwiftBar >/dev/null 2>&1 || true
    fi
    echo -e "  ${C_GREEN}done${C_RESET} ${C_DIM}— look for the AI Status item in your menu bar.${C_RESET}"
    echo -e "  ${C_DIM}If it isn't there, open SwiftBar and confirm its plugin folder is:${C_RESET}"
    echo -e "  ${C_CYAN}$PLUGIN_DIR${C_RESET}"
else
    echo -e "  ${C_YELLOW}!${C_RESET} SwiftBar doesn't appear to be installed."
    echo -e "  ${C_DIM}Install it, then re-run this command:${C_RESET}"
    echo -e "  ${C_CYAN}brew install --cask swiftbar${C_RESET}   ${C_DIM}(or download from https://swiftbar.app)${C_RESET}"
    echo -e "  ${C_DIM}On first launch, point SwiftBar's plugin folder at:${C_RESET}"
    echo -e "  ${C_CYAN}$PLUGIN_DIR${C_RESET}"
fi
echo ""
