#!/bin/bash
set -eo pipefail

export TERM=xterm-256color

C_GREEN=$'\033[0;32m'
C_CYAN=$'\033[0;36m'
C_PURPLE=$'\033[0;35m'
C_DIM=$'\033[2m'
C_RESET=$'\033[0m'

bool_color() { [ "$1" = "true" ] && echo "$C_GREEN" || echo "$C_DIM"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# With curl | bash, $0 is bash and SCRIPT_DIR is the caller's working
# directory. Only a directly invoked install.sh may use checkout metadata.
SCRIPT_IS_FILE=false
case "$0" in */install.sh|install.sh) SCRIPT_IS_FILE=true ;; esac
if [ "$SCRIPT_IS_FILE" = true ] && [ -f "$SCRIPT_DIR/config.sh" ]; then
    # shellcheck source=./config.sh
    # Version validation uses the staged tree, including legacy workspace layouts.
    source "$SCRIPT_DIR/config.sh" --repository-only
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
if [ "$SCRIPT_IS_FILE" = true ] && [ "$SCRIPT_DIR" != "$INSTALL_DIR/packages/lib" ] && git -C "$SCRIPT_DIR" rev-parse --git-dir > /dev/null 2>&1; then
    USE_LOCAL_LIB=true
fi

# ── defaults ──────────────────────────────────────────────
ICON_MODE="bot"
SHOW_PROVIDER="true"
SHOW_MODEL="true"
SHOW_METRIC="false"
SHOW_PCT="true"
PREFS_FILE="$HOME/.config/ai-status/selected.json"
[ -f "$PREFS_FILE" ] || PREFS_FILE="$HOME/.config/waybar-ai-status/selected.json"
if [ -f "$PREFS_FILE" ]; then
    # Load only known display settings. Provider selection and other settings
    # remain in selected.json; explicit command-line flags below take precedence.
    SAVED_PREFS="$(python3 - "$PREFS_FILE" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
if not isinstance(data, dict):
    sys.exit("Display preferences must be a JSON object; refusing to reset them")
mode = data.get("icon_mode", "bot" if data.get("show_icon", True) else "off")
if mode in ("bot", "logo", "off"):
    print("ICON_MODE=" + mode)
for key in ("show_provider", "show_model", "show_metric", "show_pct"):
    if isinstance(data.get(key), bool):
        print(key.upper() + "=" + str(data[key]).lower())
PY
)"
    while IFS='=' read -r key value; do
        [ -z "$key" ] || printf -v "$key" '%s' "$value"
    done <<< "$SAVED_PREFS"
fi
CONFIGURE_WAYBAR=""
CONFIGURE_BAR=""
BAR="auto"
BAR_EXPLICIT=false
NON_INTERACTIVE=false
SKIP_CHECK=false
RELEASE_TAG=""
ROLLBACK=false

# ── parse flags ───────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --icon-mode|--show-provider|--show-model|--show-metric|--show-pct|--configure-waybar|--configure-bar|--bar)
            [ $# -ge 2 ] || { echo "Missing value for $1" >&2; exit 1; } ;;
    esac
    case "$1" in
        --icon-mode)        ICON_MODE="$2"; shift 2 ;;
        --show-provider)    SHOW_PROVIDER="$2"; shift 2 ;;
        --show-model)       SHOW_MODEL="$2"; shift 2 ;;
        --show-metric)      SHOW_METRIC="$2"; shift 2 ;;
        --show-pct)         SHOW_PCT="$2"; shift 2 ;;
        --configure-waybar) CONFIGURE_WAYBAR="$2"; shift 2 ;;
        --configure-bar)    CONFIGURE_BAR="$2"; shift 2 ;;
        --bar)              BAR="$2"; [ "$BAR" = auto ] || BAR_EXPLICIT=true; shift 2 ;;
        --no-interactive)   NON_INTERACTIVE=true; shift ;;
        --skip-check)       SKIP_CHECK=true; shift ;;
        --version)          [ $# -ge 2 ] && [ -n "$2" ] || { echo "Missing value for --version" >&2; exit 1; }
                           RELEASE_TAG="$2"; shift 2 ;;
        --rollback)         ROLLBACK=true; shift ;;
        *) echo "Unknown flag: $1"; exit 1 ;;
    esac
done

case "$BAR" in auto|waybar|quickshell) ;; *) echo "Invalid --bar: $BAR" >&2; exit 1 ;; esac
if [ -n "$CONFIGURE_WAYBAR" ]; then
    [ "$BAR" != quickshell ] || { echo "--configure-waybar cannot be used with --bar quickshell" >&2; exit 1; }
    [ -z "$CONFIGURE_BAR" ] || [ "$CONFIGURE_BAR" = "$CONFIGURE_WAYBAR" ] || { echo "Conflicting configuration flags" >&2; exit 1; }
    BAR="waybar"
    BAR_EXPLICIT=true
    CONFIGURE_BAR="$CONFIGURE_WAYBAR"
fi
validate_options() {
    case "$ICON_MODE" in bot|logo|off) ;; *) echo "Invalid --icon-mode: $ICON_MODE" >&2; exit 1 ;; esac
    local option value
    for option in SHOW_PROVIDER SHOW_MODEL SHOW_METRIC SHOW_PCT CONFIGURE_BAR; do
        value="${!option}"
        case "$value" in true|false) ;; "") [ "$option" = CONFIGURE_BAR ] || exit 1 ;; *) echo "Invalid $option: $value" >&2; exit 1 ;; esac
    done
}
validate_options

quickshell_available() {
    command -v omarchy >/dev/null 2>&1 && command -v omarchy-shell >/dev/null 2>&1 &&
        { command -v qs >/dev/null 2>&1 || command -v quickshell >/dev/null 2>&1; }
}
if [ "$BAR" = auto ]; then
    if quickshell_available && OMARCHY_SHELL_IPC_TIMEOUT=2 omarchy-shell shell ping >/dev/null 2>&1; then
        BAR="quickshell"
    elif pgrep -x waybar >/dev/null 2>&1 || command -v waybar >/dev/null 2>&1; then
        BAR="waybar"
    elif quickshell_available; then
        BAR="quickshell"
    else
        # Preserve headless/manual Waybar setup; dependency validation below
        # reports a missing bar unless the caller explicitly skips it.
        BAR="waybar"
    fi
fi

[ "$ROLLBACK" = false ] || [ -z "$RELEASE_TAG" ] || { echo "Use either --rollback or --version" >&2; exit 1; }
# Only stable version tags may be requested. Never treat a branch (main) as
# an installable release; local checkouts remain available for development.
if [ -n "$RELEASE_TAG" ]; then
    RELEASE_TAG="v${RELEASE_TAG#v}"
    [[ "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid --version: expected a stable version like v0.9.0" >&2; exit 1; }
    [ "$USE_LOCAL_LIB" = false ] || { echo "--version requires the remote installer, not a local checkout" >&2; exit 1; }
fi

# ═══════════════════════════════════════════════════════════
# INSTALL / UPDATE
# ═══════════════════════════════════════════════════════════

# Stage on the same filesystem so activation uses renames, never a partial copy.
mkdir -p "$(dirname "$INSTALL_DIR")"
PREVIOUS_DIR="$INSTALL_DIR.previous"
LOCK_DIR="$(dirname "$INSTALL_DIR")/.ai-status-update.lock"
mkdir "$LOCK_DIR" 2>/dev/null || { echo "Another installation is running (lock: $LOCK_DIR)" >&2; exit 1; }
WORK_DIR=""
STAGE_DIR=""
OLD_INSTALL_MOVED=false
NEW_INSTALL_ACTIVE=false
MIGRATED_LEGACY_CONFIG=false
MIGRATED_LEGACY_INSTALL=false
SNAPSHOT_PATHS=()

cleanup() {
    local status=$? index target
    trap - EXIT
    set +e
    if [ "$status" -ne 0 ] && [ "$OLD_INSTALL_MOVED" = true ]; then
        [ "$NEW_INSTALL_ACTIVE" = false ] || rm -rf -- "$INSTALL_DIR"
        mv -- "$PREVIOUS_DIR" "$INSTALL_DIR" || echo "Could not restore $PREVIOUS_DIR; it remains available for recovery" >&2
    elif [ "$status" -ne 0 ] && [ "$NEW_INSTALL_ACTIVE" = true ]; then
        rm -rf -- "$INSTALL_DIR"
    fi
    if [ "$status" -ne 0 ]; then
        for index in "${!SNAPSHOT_PATHS[@]}"; do
            target="${SNAPSHOT_PATHS[$index]}"
            rm -f -- "$target"
            [ ! -e "$WORK_DIR/backups/$index" ] && [ ! -L "$WORK_DIR/backups/$index" ] ||
                cp -a -- "$WORK_DIR/backups/$index" "$target"
        done
        if [ "$MIGRATED_LEGACY_CONFIG" = true ]; then
            mv -- "$HOME/.config/ai-status" "$HOME/.config/waybar-ai-status"
        fi
        if [ "$MIGRATED_LEGACY_INSTALL" = true ]; then
            mv -- "$INSTALL_DIR" "$HOME/.local/share/omarchy-ai-status"
        fi
        echo "Installation failed; the previous version and settings were preserved." >&2
    fi
    [ -z "$STAGE_DIR" ] || rm -rf -- "$STAGE_DIR"
    [ -z "$WORK_DIR" ] || rm -rf -- "$WORK_DIR"
    rmdir "$LOCK_DIR"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
WORK_DIR="$(mktemp -d)"
STAGE_DIR="$(mktemp -d "$(dirname "$INSTALL_DIR")/.ai-status-stage.XXXXXX")"

# Keep legacy path migrations inside the lock and failure recovery as well.
if [ -d "$HOME/.config/waybar-ai-status" ] && [ ! -d "$HOME/.config/ai-status" ]; then
    mv "$HOME/.config/waybar-ai-status" "$HOME/.config/ai-status"
    MIGRATED_LEGACY_CONFIG=true
fi
if [ -d "$HOME/.local/share/omarchy-ai-status" ] && [ ! -d "$INSTALL_DIR" ]; then
    echo -e "  ${C_DIM}> migrating old installation directory...${C_RESET}"
    mv "$HOME/.local/share/omarchy-ai-status" "$INSTALL_DIR"
    MIGRATED_LEGACY_INSTALL=true
fi

copy_library() {
    [ -d "$1/packages/lib" ] && [ -d "$1/packages/shared" ] || { echo "Source is missing the library or shared files" >&2; exit 1; }
    mkdir -p "$STAGE_DIR/packages"
    cp -a -- "$1/packages/lib" "$STAGE_DIR/packages/lib"
    cp -a -- "$1/packages/shared" "$STAGE_DIR/packages/shared"
    if [ -e "$1/package.json" ] || [ -L "$1/package.json" ]; then
        cp -- "$1/package.json" "$STAGE_DIR/package.json"
    fi
}

RUNNING_FROM_INSTALL=false
if [ "$SCRIPT_IS_FILE" = true ]; then
    case "$SCRIPT_DIR/" in "$INSTALL_DIR"/*) RUNNING_FROM_INSTALL=true ;; esac
fi

if [ "$ROLLBACK" = true ]; then
    [ -d "$PREVIOUS_DIR/packages/lib" ] || { echo "No previous installation is available for --rollback" >&2; exit 1; }
    copy_library "$PREVIOUS_DIR"
elif [ "$RUNNING_FROM_INSTALL" = true ]; then
    [ -z "$RELEASE_TAG" ] || { echo "Use the public installer to install a specific version" >&2; exit 1; }
    copy_library "$INSTALL_DIR"
elif [ "$USE_LOCAL_LIB" = true ]; then
    REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
    copy_library "$REPO_ROOT"
else
    REPO_SLUG="${REPO_URL#https://github.com/}"
    REPO_SLUG="${REPO_SLUG%/}"
    REPO_SLUG="${REPO_SLUG%.git}"
    [[ "$REPO_URL" == https://github.com/* && "$REPO_SLUG" =~ ^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$ ]] || { echo "Expected a GitHub repository URL" >&2; exit 1; }
    if [ -z "$RELEASE_TAG" ]; then
        RELEASE_TAG="$(curl --fail --silent --show-error --location --max-time 15 \
            -H 'Accept: application/vnd.github+json' \
            "https://api.github.com/repos/$REPO_SLUG/releases/latest" | python3 -c '
import json, re, sys
release = json.load(sys.stdin)
tag = release.get("tag_name", "")
if release.get("draft") or release.get("prerelease") or not isinstance(tag, str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
    sys.exit("No valid stable release found")
print(tag)
')"
    fi
    echo -e "  ${C_DIM}> downloading $RELEASE_TAG...${C_RESET}"
    ASSET="ai-status-$RELEASE_TAG.tar.gz"
    ARCHIVE="$WORK_DIR/release.tar.gz"
    SOURCE_ARCHIVE=false
    if HTTP_CODE="$(curl --fail --silent --show-error --location --retry 2 --max-time 120 \
        --output "$ARCHIVE" --write-out '%{http_code}' \
        "https://github.com/$REPO_SLUG/releases/download/$RELEASE_TAG/$ASSET")"; then
        curl --fail --silent --show-error --location --retry 2 --max-time 30 \
            --output "$WORK_DIR/SHA256SUMS" "https://github.com/$REPO_SLUG/releases/download/$RELEASE_TAG/SHA256SUMS"
        python3 - "$ARCHIVE" "$WORK_DIR/SHA256SUMS" "$ASSET" <<'PY'
import hashlib, re, sys
from pathlib import Path
archive, sums, name = sys.argv[1:]
entries = [line.split() for line in Path(sums).read_text().splitlines()]
expected = [parts[0] for parts in entries if len(parts) == 2 and parts[1].lstrip("*") == name]
if len(expected) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", expected[0]):
    sys.exit("Missing or invalid package checksum")
if hashlib.sha256(Path(archive).read_bytes()).hexdigest() != expected[0].lower():
    sys.exit("Package checksum does not match")
PY
    elif [ "$HTTP_CODE" = 404 ]; then
        # Pre-package releases still install from the exact tag, without git.
        SOURCE_ARCHIVE=true
        curl --fail --silent --show-error --location --retry 2 --max-time 120 \
            --output "$ARCHIVE" "https://codeload.github.com/$REPO_SLUG/tar.gz/refs/tags/$RELEASE_TAG"
    else
        echo "Could not download $RELEASE_TAG" >&2
        exit 1
    fi
    python3 - "$ARCHIVE" "$STAGE_DIR" "$SOURCE_ARCHIVE" <<'PY'
from pathlib import Path, PurePosixPath
import shutil, sys, tarfile
archive, destination, source_archive = sys.argv[1:]
root = Path(destination)
with tarfile.open(archive, "r:gz") as tar:
    for member in tar:
        parts = PurePosixPath(member.name).parts
        if member.name.startswith("/") or ".." in parts:
            sys.exit("Unsafe path in release archive")
        if source_archive == "true":
            parts = parts[1:]
        if parts != ("package.json",) and (len(parts) < 2 or parts[0] != "packages" or parts[1] not in ("lib", "shared")):
            continue
        target = root.joinpath(*parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as data, target.open("wb") as out:
                shutil.copyfileobj(data, out)
            target.chmod(member.mode & 0o777)
        else:
            sys.exit("Unexpected link or special file in release archive")
PY
fi

# All validation and requirement checks happen before the active files change.
python3 - "$STAGE_DIR" "${RELEASE_TAG#v}" <<'PY'
from pathlib import Path
import json, re, sys
sys.dont_write_bytecode = True
root = Path(sys.argv[1])
lib = root / "packages/lib"
for required in (lib / "src/bin/ai-status", lib / "check.sh", root / "packages/shared/providers/providers.json"):
    if not required.is_file():
        sys.exit(f"Release is missing {required.relative_to(root)}")
manifest = root / "package.json"
if manifest.exists():
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "version" not in data and (lib / "VERSION").is_file():
        # Pre-migration package.json describes npm workspaces, not product versions.
        manifest.unlink()
        version = (lib / "VERSION").read_text(encoding="utf-8").strip()
    else:
        version = data.get("version") if isinstance(data, dict) else None
else:
    version = (lib / "VERSION").read_text(encoding="utf-8").strip()
if not isinstance(version, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
    sys.exit("Release metadata has an invalid stable version")
if sys.argv[2] and version != sys.argv[2]:
    sys.exit("Release tag and version metadata disagree")
json.load(open(root / "packages/shared/providers/providers.json", encoding="utf-8"))
for script in lib.rglob("*.py"):
    compile(script.read_bytes(), str(script), "exec")
sys.path.insert(0, str(lib / "src"))
import core.cli
import core
if core.__version__ != version:
    sys.exit("CLI and release version metadata disagree")
PY
if [ "$SKIP_CHECK" = false ]; then
    bash "$STAGE_DIR/packages/lib/check.sh" "$BAR"
fi

# Updates keep existing display preferences and do not rerun the setup wizard.
if [ -d "$INSTALL_DIR" ]; then
    NON_INTERACTIVE=true
    [ -n "$CONFIGURE_BAR" ] || CONFIGURE_BAR=false
fi

mkdir "$WORK_DIR/backups"
for target in "$HOME/.config/ai-status/selected.json" "$WAYBAR_CONFIG" "$WAYBAR_CONFIG.ai-status.bak" \
    "$BIN_DIR/ai-status" "$BIN_DIR/waybar-ai-status"; do
    index="${#SNAPSHOT_PATHS[@]}"
    if [ -e "$target" ] || [ -L "$target" ]; then
        cp -a -- "$target" "$WORK_DIR/backups/$index"
    fi
    SNAPSHOT_PATHS+=("$target")
done

# Avoid removing the shell's working directory when the public command is run
# inside the installed copy. The source has already been copied to staging.
cd "$WORK_DIR"
if [ -e "$INSTALL_DIR" ]; then
    rm -rf -- "$PREVIOUS_DIR"
    mv -- "$INSTALL_DIR" "$PREVIOUS_DIR"
    OLD_INSTALL_MOVED=true
fi
mv -- "$STAGE_DIR" "$INSTALL_DIR"
NEW_INSTALL_ACTIVE=true
STAGE_DIR=""

# ═══════════════════════════════════════════════════════════
# CONFIGURATION WIZARD
# ═══════════════════════════════════════════════════════════

if [ "$NON_INTERACTIVE" = false ]; then
    if [ -n "$CONFIGURE_BAR" ]; then
        echo -e "  ${C_DIM}flags detected — skipping interactive setup${C_RESET}"
    elif { true >/dev/tty; } 2>/dev/null; then
        # A terminal is attached — run the wizard reading from /dev/tty. This
        # works even when stdin is a pipe (the common `curl ... | bash`), which
        # the old `[ -t 0 ]` check skipped, leaving waybar unconfigured.
        WIZARD_SCRIPT="$INSTALL_DIR/packages/lib/install-wizard.py"
        [ "$USE_LOCAL_LIB" = true ] && WIZARD_SCRIPT="$SCRIPT_DIR/install-wizard.py"
        [ ! -f "$WIZARD_SCRIPT" ] && WIZARD_SCRIPT="$SCRIPT_DIR/install-wizard.py"
        WIZARD_OUT="$WORK_DIR/wizard.json"
        # If the user cancels the wizard (Ctrl-C -> exit 1), don't let `set -e`
        # abort mid-install and leave a half-state — finish with defaults.
        if python3 "$WIZARD_SCRIPT" "$WIZARD_OUT" "$BAR" "$BAR_EXPLICIT"; then
            eval "$(python3 - "$WIZARD_OUT" <<'PY'
import json, shlex, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
for key in ('BAR', 'ICON_MODE', 'SHOW_PROVIDER', 'SHOW_MODEL', 'SHOW_METRIC', 'SHOW_PCT', 'CONFIGURE_BAR'):
    if key in data:
        print(f'{key}={shlex.quote(str(data[key]))}')
PY
)"
        else
            echo -e "  ${C_DIM}setup cancelled — installing with defaults (run 'ai-status config' to change)${C_RESET}"
        fi
        rm -f "$WIZARD_OUT"
    else
        # Truly no terminal (cron/CI/headless) — configure with defaults instead
        # of leaving a half-install where waybar never gets the module.
        echo -e "  ${C_DIM}no terminal — configuring with defaults${C_RESET}"
        CONFIGURE_BAR="true"
    fi
fi

# ── validate ───────────────────────────────────────────────
validate_options
[ -z "$CONFIGURE_BAR" ] && CONFIGURE_BAR="false"
CHECK_SCRIPT="$INSTALL_DIR/packages/lib/check.sh"
[ "$USE_LOCAL_LIB" = true ] && CHECK_SCRIPT="$SCRIPT_DIR/check.sh"
if [ "$SKIP_CHECK" = false ]; then
    bash "$CHECK_SCRIPT" "$BAR"
fi
if [ "$BAR" = quickshell ]; then
    if ! OMARCHY_SHELL_IPC_TIMEOUT=2 omarchy-shell shell ping >/dev/null 2>&1; then
        echo "Start the Omarchy shell, then re-run the installer to install the plugin." >&2
        exit 1
    fi
    PLUGIN_ID="io.github.gelzinn.ai-status"
    PLUGIN_DIR="$HOME/.config/omarchy/plugins/$PLUGIN_ID"
    if [ -e "$PLUGIN_DIR" ] && [ ! -d "$PLUGIN_DIR/.git" ]; then
        echo "Existing plugin is not managed by Git: $PLUGIN_DIR. Leaving it untouched." >&2
        exit 1
    fi
fi

echo ""
echo -e "  ${C_PURPLE}icon${C_RESET}          ${C_DIM}>${C_RESET} ${C_CYAN}$ICON_MODE${C_RESET}"
echo -e "  ${C_PURPLE}show provider${C_RESET} ${C_DIM}>${C_RESET} $(bool_color "$SHOW_PROVIDER")$SHOW_PROVIDER${C_RESET}"
echo -e "  ${C_PURPLE}show model${C_RESET}    ${C_DIM}>${C_RESET} $(bool_color "$SHOW_MODEL")$SHOW_MODEL${C_RESET}"
echo -e "  ${C_PURPLE}show metric${C_RESET}   ${C_DIM}>${C_RESET} $(bool_color "$SHOW_METRIC")$SHOW_METRIC${C_RESET}"
echo -e "  ${C_PURPLE}show %${C_RESET}        ${C_DIM}>${C_RESET} $(bool_color "$SHOW_PCT")$SHOW_PCT${C_RESET}"
echo -e "  ${C_PURPLE}bar${C_RESET}           ${C_DIM}>${C_RESET} ${C_CYAN}$BAR${C_RESET}"
echo -e "  ${C_PURPLE}bar config${C_RESET}    ${C_DIM}>${C_RESET} $(bool_color "$CONFIGURE_BAR")$CONFIGURE_BAR${C_RESET}"
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

python3 - "$CONFIG_DIR/selected.json" "$ICON_MODE" "$SHOW_PROVIDER" "$SHOW_MODEL" "$SHOW_METRIC" "$SHOW_PCT" <<'PY'
import json, os, sys, tempfile
path, icon, sp, sm, smt, pct = sys.argv[1:]
existing = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as source:
        existing = json.load(source)
    if not isinstance(existing, dict):
        sys.exit("Display preferences must be a JSON object")
existing.update(icon_mode=icon, show_provider=sp == "true", show_model=sm == "true",
                show_metric=smt == "true", show_pct=pct == "true")
existing.setdefault("provider", "claude")
existing.setdefault("idx", 0)
existing.setdefault("metric", "rolling")
with tempfile.NamedTemporaryFile("w", dir=os.path.dirname(path), delete=False, encoding="utf-8") as out:
    temporary = out.name
    json.dump(existing, out, indent=2)
    out.write("\n")
try:
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
print(f"  \033[2msaved display preferences to {path}\033[0m")
PY

# ═══════════════════════════════════════════════════════════
# WAYBAR CONFIGURATION
# ═══════════════════════════════════════════════════════════

if [ "$BAR" = waybar ] && [ "$CONFIGURE_BAR" = true ] && command -v waybar &>/dev/null; then
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

def _strip_comments(text):
    # Remove // and /* */ comments, but never touch characters inside strings
    # (a naive regex would eat the // in "https://..." and break the config).
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_str = False
            i += 1; continue
        if c == '"':
            in_str = True; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2; continue
        out.append(c); i += 1
    return "".join(out)


def _strip_trailing_commas(text):
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_str = False
            i += 1; continue
        if c == '"':
            in_str = True; out.append(c); i += 1; continue
        if c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1; continue
        out.append(c); i += 1
    return "".join(out)


config = {}
if os.path.exists(config_path):
    with open(config_path) as f:
        raw = f.read()
    try:
        config = json.loads(_strip_trailing_commas(_strip_comments(raw)))
    except Exception:
        status("warning: could not parse waybar config (leaving it untouched)")
        sys.exit(0)
    if not isinstance(config, dict):
        status("waybar config is a list (multi-bar setup) — add the modules manually")
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

# The image module runs `ai-status logo`, which prints the PNG path on line 1
# and the tooltip on line 2 — so hovering the logo shows the same breakdown as
# the text module. `signal` reloads it when the provider/data changes.
logo_module = {
    "exec": "~/.local/bin/ai-status logo",
    "size": 14,
    "interval": 3,
    "signal": 11,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
    "tooltip": True,
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

MODULES_KEYS = [k for k in config if k == "modules-right" or k.endswith("-right")]
if not MODULES_KEYS:
    # No right section — fall back to a SINGLE section so the module isn't added
    # to several layouts at once (which would show it more than once).
    for cand in ("modules-center", "modules-left"):
        if isinstance(config.get(cand), list):
            MODULES_KEYS = [cand]
            break
    else:
        MODULES_KEYS = [k for k in config if k.startswith("modules-") and isinstance(config.get(k), list)][:1]

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

    # json.dumps already emits lowercase true/false; write atomically via a temp
    # file + rename so a failure mid-write can never truncate the real config.
    pretty = json.dumps(config, indent=2, ensure_ascii=False)
    tmp = config_path + ".tmp"
    with open(tmp, "w") as f:
        f.write(pretty + "\n")
    os.replace(tmp, config_path)
    status(f"waybar config updated: {config_path}")
else:
    status("waybar config already up to date")
PYEOF

    # Seed current.png so the logo renders on the very first launch (the daemon
    # also refreshes it on startup, but this avoids an initial empty image).
    if [ "$WANTS_LOGO" = true ]; then
        "$BIN_DIR/ai-status" logo >/dev/null 2>&1 || true
    fi

    echo ""
    echo -e "  ${C_DIM}Your original Waybar config was backed up. If anything looks off,${C_RESET}"
    echo -e "  ${C_DIM}run${C_RESET} ${C_CYAN}ai-status revert${C_RESET} ${C_DIM}to restore it.${C_RESET}"
elif [ "$BAR" = waybar ] && command -v waybar &>/dev/null; then
    # Manual mode — the user chose to add the modules themselves. Print the
    # blocks to copy (same as the docs / landing page). Nothing is touched, so
    # there's no backup to worry about.
    echo ""
    echo -e "  ${C_PURPLE}${C_DIM}manual waybar setup${C_RESET}"
    echo -e "  ${C_DIM}Add this to ${WAYBAR_CONFIG} and put \"custom/ai-status\"${C_RESET}"
    echo -e "  ${C_DIM}(and \"image#ai-status\") in your \"modules-right\":${C_RESET}"
    echo ""
    cat <<'MANUAL'
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
MANUAL
    if [ "$ICON_MODE" = "logo" ]; then
        echo ""
        echo -e "  ${C_DIM}For the provider logo (with tooltip on hover):${C_RESET}"
        cat <<'MANUAL'
  "image#ai-status": {
    "exec": "~/.local/bin/ai-status logo",
    "size": 14,
    "interval": 3,
    "signal": 11,
    "on-click": "~/.local/bin/ai-status refresh",
    "on-click-right": "~/.local/bin/ai-status config",
    "on-scroll-up": "~/.local/bin/ai-status scroll-up",
    "on-scroll-down": "~/.local/bin/ai-status scroll-down",
    "on-click-middle": "~/.local/bin/ai-status cycle-metric",
    "tooltip": true
  }
MANUAL
    fi
    echo ""
    echo -e "  ${C_DIM}Full guide: ${REPO_URL}/blob/main/packages/lib/LINUX.md${C_RESET}"
fi

# ═══════════════════════════════════════════════════════════

if [ "$BAR" = quickshell ]; then
    if [ -d "$PLUGIN_DIR/.git" ]; then
        omarchy plugin update "$PLUGIN_ID" --yes
    else
        # Local development installs the checkout being tested, rather than main.
        PLUGIN_SOURCE="$REPO_URL"
        [ "$USE_LOCAL_LIB" = true ] && PLUGIN_SOURCE="$REPO_ROOT"
        omarchy plugin add "$PLUGIN_SOURCE" --yes
    fi
    if [ "$CONFIGURE_BAR" = true ]; then
        # Empty placement preserves an existing position; first enable uses right.
        omarchy plugin enable "$PLUGIN_ID"
    else
        echo "Enable when ready: omarchy plugin enable $PLUGIN_ID"
    fi
elif command -v waybar &>/dev/null; then
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
