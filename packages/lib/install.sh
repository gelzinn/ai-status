#!/bin/bash
set -e

export TERM=xterm-256color

C_GREEN=$'\033[0;32m'
C_CYAN=$'\033[0;36m'
C_PURPLE=$'\033[0;35m'
C_DIM=$'\033[2m'
C_RESET=$'\033[0m'

bool_color() { [ "$1" = "true" ] && echo "$C_GREEN" || echo "$C_DIM"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/config.sh" ]; then
    # shellcheck source=./config.sh
    source "$SCRIPT_DIR/config.sh"
fi
: "${REPO_URL:=https://github.com/gelzinn/ai-status}"
INSTALL_DIR="$HOME/.local/share/ai-status"
BIN_DIR="$HOME/.local/bin"
WAYBAR_CONFIG="$HOME/.config/waybar/config.jsonc"

# When running install.sh directly from a local dev checkout (not the
# installed copy at INSTALL_DIR), prefer this checkout's own check.sh /
# install-wizard.py so local edits are actually exercised instead of
# silently falling back to whatever is already installed.
USE_LOCAL_LIB=false
if [ "$SCRIPT_DIR" != "$INSTALL_DIR/packages/lib" ] && git -C "$SCRIPT_DIR" rev-parse --git-dir > /dev/null 2>&1; then
    USE_LOCAL_LIB=true
fi

# ── defaults ──────────────────────────────────────────────
ICON_MODE="bot"
SHOW_PROVIDER="true"
SHOW_MODEL="true"
SHOW_METRIC="false"
SHOW_PCT="true"
CONFIGURE_WAYBAR=""
NON_INTERACTIVE=false
SKIP_CHECK=false

# ── parse flags ───────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --icon-mode)        ICON_MODE="$2"; shift 2 ;;
        --show-provider)    SHOW_PROVIDER="$2"; shift 2 ;;
        --show-model)       SHOW_MODEL="$2"; shift 2 ;;
        --show-metric)      SHOW_METRIC="$2"; shift 2 ;;
        --show-pct)         SHOW_PCT="$2"; shift 2 ;;
        --configure-waybar) CONFIGURE_WAYBAR="$2"; shift 2 ;;
        --no-interactive)   NON_INTERACTIVE=true; shift ;;
        --skip-check)       SKIP_CHECK=true; shift ;;
        *) echo "Unknown flag: $1"; exit 1 ;;
    esac
done

# ═══════════════════════════════════════════════════════════
# INSTALL / UPDATE
# ═══════════════════════════════════════════════════════════

# Migrate old config and cache from waybar-ai-status to ai-status
if [ -d "$HOME/.config/waybar-ai-status" ] && [ ! -d "$HOME/.config/ai-status" ]; then
    mv "$HOME/.config/waybar-ai-status" "$HOME/.config/ai-status"
fi
if [ -d "$HOME/.local/share/omarchy-ai-status" ] && [ ! -d "$INSTALL_DIR" ]; then
    echo -e "  ${C_DIM}> migrating old installation directory...${C_RESET}"
    mv "$HOME/.local/share/omarchy-ai-status" "$INSTALL_DIR"
fi

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "  ${C_DIM}> updating...${C_RESET}"
    git -C "$INSTALL_DIR" pull --ff-only 2>&1 | while IFS= read -r line; do echo -e "  ${C_DIM}${line}${C_RESET}"; done
    [ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
elif [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR" "$INSTALL_DIR"
elif [ "$SCRIPT_DIR" = "$INSTALL_DIR" ]; then
    :
elif git -C "$SCRIPT_DIR" rev-parse --git-dir > /dev/null 2>&1; then
    REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
    cp -r "$REPO_ROOT" "$INSTALL_DIR"
else
    echo -e "  ${C_DIM}> installing...${C_RESET}"
    git clone "$REPO_URL" "$INSTALL_DIR" 2>&1 | while IFS= read -r line; do echo -e "  ${C_DIM}${line}${C_RESET}"; done
    [ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
fi

# Check requirements
CHECK_SCRIPT="$INSTALL_DIR/packages/lib/check.sh"
[ "$USE_LOCAL_LIB" = true ] && CHECK_SCRIPT="$SCRIPT_DIR/check.sh"
if [ "$SKIP_CHECK" = false ]; then
    bash "$CHECK_SCRIPT"
fi

# ═══════════════════════════════════════════════════════════
# CONFIGURATION WIZARD
# ═══════════════════════════════════════════════════════════

if [ "$NON_INTERACTIVE" = false ]; then
    if [ ! -t 0 ]; then
        echo -e "  ${C_DIM}non-interactive mode — using defaults${C_RESET}"
        CONFIGURE_WAYBAR="false"
    elif [ -n "$CONFIGURE_WAYBAR" ]; then
        echo -e "  ${C_DIM}flags detected — skipping interactive setup${C_RESET}"
    else
        WIZARD_SCRIPT="$INSTALL_DIR/packages/lib/install-wizard.py"
        [ "$USE_LOCAL_LIB" = true ] && WIZARD_SCRIPT="$SCRIPT_DIR/install-wizard.py"
        [ ! -f "$WIZARD_SCRIPT" ] && WIZARD_SCRIPT="$SCRIPT_DIR/install-wizard.py"
        WIZARD_OUT="/tmp/ai-status-wizard.json"
        python3 "$WIZARD_SCRIPT" "$WIZARD_OUT"
        eval "$(python3 -c "
import json
with open('$WIZARD_OUT') as f:
    d = json.load(f)
for k, v in d.items():
    print(f'{k}={v}')
")"
    fi
fi

# ── validate ───────────────────────────────────────────────
case "$ICON_MODE" in bot|logo|off) ;; *) echo "Invalid --icon-mode: $ICON_MODE"; exit 1 ;; esac
for f in SHOW_PROVIDER SHOW_MODEL SHOW_METRIC SHOW_PCT; do
    val="${!f}"
    case "$val" in true|false) ;; *) echo "Invalid --$f: $val"; exit 1 ;; esac
done
[ -z "$CONFIGURE_WAYBAR" ] && CONFIGURE_WAYBAR="false"

echo ""
echo -e "  ${C_PURPLE}icon${C_RESET}          ${C_DIM}>${C_RESET} ${C_CYAN}$ICON_MODE${C_RESET}"
echo -e "  ${C_PURPLE}show provider${C_RESET} ${C_DIM}>${C_RESET} $(bool_color "$SHOW_PROVIDER")$SHOW_PROVIDER${C_RESET}"
echo -e "  ${C_PURPLE}show model${C_RESET}    ${C_DIM}>${C_RESET} $(bool_color "$SHOW_MODEL")$SHOW_MODEL${C_RESET}"
echo -e "  ${C_PURPLE}show metric${C_RESET}   ${C_DIM}>${C_RESET} $(bool_color "$SHOW_METRIC")$SHOW_METRIC${C_RESET}"
echo -e "  ${C_PURPLE}show %${C_RESET}        ${C_DIM}>${C_RESET} $(bool_color "$SHOW_PCT")$SHOW_PCT${C_RESET}"
echo -e "  ${C_PURPLE}waybar config${C_RESET} ${C_DIM}>${C_RESET} $(bool_color "$CONFIGURE_WAYBAR")$CONFIGURE_WAYBAR${C_RESET}"
echo ""

# ═══════════════════════════════════════════════════════════
# SYMLINK
# ═══════════════════════════════════════════════════════════

mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/packages/lib/src/bin/ai-status" "$BIN_DIR/ai-status"
ln -sf "$BIN_DIR/ai-status" "$BIN_DIR/waybar-ai-status"

# ═══════════════════════════════════════════════════════════
# SAVE PREFERENCES
# ═══════════════════════════════════════════════════════════

CONFIG_DIR="$HOME/.config/ai-status"
mkdir -p "$CONFIG_DIR"

python3 -c "
import json, os

path = os.path.expanduser('$CONFIG_DIR/selected.json')
icon = '$ICON_MODE'
sp = '$SHOW_PROVIDER'.lower() == 'true'
sm = '$SHOW_MODEL'.lower() == 'true'
smt = '$SHOW_METRIC'.lower() == 'true'
pct = '$SHOW_PCT'.lower() == 'true'

existing = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            existing = json.load(f)
    except: pass

existing['icon_mode'] = icon
existing['show_provider'] = sp
existing['show_model'] = sm
existing['show_metric'] = smt
existing['show_pct'] = pct

if 'provider' not in existing:
    existing['provider'] = 'claude'
if 'idx' not in existing:
    existing['idx'] = 0
if 'metric' not in existing:
    existing['metric'] = 'rolling'

with open(path, 'w') as f:
    json.dump(existing, f, indent=2)
print(f'  \033[2msaved display preferences to {path}\033[0m')
"

# ═══════════════════════════════════════════════════════════
# WAYBAR CONFIGURATION
# ═══════════════════════════════════════════════════════════

if [ "$CONFIGURE_WAYBAR" = true ] && command -v waybar &>/dev/null; then
    echo ""
    echo -e "  ${C_PURPLE}${C_DIM}waybar modules${C_RESET}"

    WAYBAR_DIR="$(dirname "$WAYBAR_CONFIG")"
    mkdir -p "$WAYBAR_DIR"

    WANTS_LOGO=false
    [ "$ICON_MODE" = "logo" ] && WANTS_LOGO=true

    python3 - "$WAYBAR_CONFIG" "$WANTS_LOGO" <<'PYEOF'
import json, sys, os, re

DIM = "\033[2m"
RESET = "\033[0m"

def status(msg):
    print(f"  {DIM}{msg}{RESET}")

config_path = sys.argv[1]
wants_logo = sys.argv[2] == "true"
changed = False

config = {}
if os.path.exists(config_path):
    with open(config_path) as f:
        raw = f.read()
    cleaned = re.sub(r'//.*', '', raw)
    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
    try:
        config = json.loads(cleaned)
    except:
        status("warning: could not parse waybar config (will not modify)")
        sys.exit(0)

custom_module = {
    "exec": "~/.local/bin/ai-status daemon",
    "restart-interval": 1,
    "return-type": "json",
    "format": "{}",
    "tooltip": True,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
}

# NOTE: the image module reads a static `path` (not `exec`): waybar's image
# `exec` mode leaves the whole bar blank on some builds. ai-status keeps
# `current.png` in sync with the selected provider and reloads it via `signal`.
logo_module = {
    "path": os.path.expanduser("~/.cache/ai-status/logos/current.png"),
    "size": 14,
    "signal": 11,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
    "tooltip": False,
}

CUSTOM_KEY = "custom/ai-status"
LOGO_KEY = "image#ai-status"

if CUSTOM_KEY not in config:
    config[CUSTOM_KEY] = custom_module
    changed = True
    status(f"added '{CUSTOM_KEY}' module")

if wants_logo:
    if LOGO_KEY not in config:
        config[LOGO_KEY] = logo_module
        changed = True
        status(f"added '{LOGO_KEY}' module")
else:
    config.pop(LOGO_KEY, None)

MODULES_KEYS = [k for k in config if k.endswith("-right") or k == "modules-right"]
if not MODULES_KEYS:
    MODULES_KEYS = [k for k in config if k.endswith("-left") or k.endswith("-center") or k.startswith("modules-")]

def ensure_in_layout(section, module_key, after_key=None):
    global changed
    if module_key in section:
        return
    insert_at = len(section)
    for keyword in ("network", "clock", "tray", "battery", "pulseaudio"):
        for i, m in enumerate(section):
            if keyword in str(m):
                insert_at = i
                break
        if insert_at < len(section):
            break
    if after_key and after_key in section:
        after_idx = section.index(after_key)
        if insert_at <= after_idx:
            insert_at = after_idx + 1
    section.insert(insert_at, module_key)
    changed = True

if not MODULES_KEYS:
    layout = []
    if wants_logo:
        layout.append(LOGO_KEY)
    layout.append(CUSTOM_KEY)
    config["modules-right"] = layout
    changed = True
    status("created 'modules-right' section")
else:
    for mk in MODULES_KEYS:
        layout = config[mk]
        if not isinstance(layout, list):
            continue
        if wants_logo:
            if LOGO_KEY not in layout:
                ensure_in_layout(layout, LOGO_KEY)
                status(f"added '{LOGO_KEY}' to '{mk}'")
            if CUSTOM_KEY not in layout:
                ensure_in_layout(layout, CUSTOM_KEY, after_key=LOGO_KEY)
                status(f"added '{CUSTOM_KEY}' to '{mk}'")
        else:
            if LOGO_KEY in layout:
                layout.remove(LOGO_KEY)
                changed = True
            if CUSTOM_KEY not in layout:
                ensure_in_layout(layout, CUSTOM_KEY)
                status(f"added '{CUSTOM_KEY}' to '{mk}'")

if changed:
    backup = config_path + ".ai-status.bak"
    if os.path.exists(config_path) and not os.path.exists(backup):
        import shutil
        shutil.copy2(config_path, backup)
        status(f"backup saved at {backup}")

    pretty = json.dumps(config, indent=2, ensure_ascii=False)
    pretty = pretty.replace("True", "true").replace("False", "false")
    with open(config_path, 'w') as f:
        f.write(pretty + "\n")
    status(f"waybar config updated: {config_path}")
else:
    status("waybar config already up to date")
PYEOF

    # Seed current.png so the logo renders on the very first launch (the daemon
    # also refreshes it on startup, but this avoids an initial empty image).
    if [ "$WANTS_LOGO" = true ]; then
        "$BIN_DIR/ai-status" logo >/dev/null 2>&1 || true
    fi
fi

# ═══════════════════════════════════════════════════════════

if command -v waybar &>/dev/null; then
    echo ""
    echo -e "  ${C_DIM}> restarting waybar...${C_RESET}"
    pkill -SIGUSR2 waybar 2>/dev/null || true
    if ! pgrep -x waybar > /dev/null; then
        nohup waybar >/dev/null 2>&1 &
        disown
    fi
fi

echo ""
echo -e "  ${C_GREEN}done${C_RESET}"
