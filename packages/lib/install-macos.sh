#!/bin/bash
set -eo pipefail

# AI Status: native macOS menu bar app, with optional SwiftBar compatibility.
# Public installs use a checksummed stable package; checkout installs use local
# sources. Build and validate everything before replacing the active version.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_IS_FILE=false
case "$0" in */install-macos.sh|install-macos.sh) SCRIPT_IS_FILE=true ;; esac
if [ "$SCRIPT_IS_FILE" = true ] && [ -f "$SCRIPT_DIR/config.sh" ]; then
    # shellcheck source=./config.sh
    # Version validation uses the staged tree, including legacy workspace layouts.
    source "$SCRIPT_DIR/config.sh" --repository-only
fi
: "${REPO_URL:=https://github.com/gelzinn/ai-status}"
INSTALL_DIR="$HOME/.local/share/ai-status"
PREVIOUS_DIR="$INSTALL_DIR.previous"
BIN_DIR="$HOME/.local/bin"
APP_LINK="$HOME/Applications/AI Status.app"
AGENT_FILE="$HOME/Library/LaunchAgents/com.gelzin.ai-status.plist"
MODE=native
NO_START=false
AUTOSTART=true
SKIP_CHECK=false
ROLLBACK=false
RELEASE_TAG=""

while [ $# -gt 0 ]; do
    case "$1" in
        --mode|--version) [ $# -ge 2 ] && [ -n "$2" ] || { echo "Missing value for $1" >&2; exit 1; } ;;
    esac
    case "$1" in
        --mode) MODE="$2"; shift 2 ;;
        --version) RELEASE_TAG="v${2#v}"; shift 2 ;;
        --rollback) ROLLBACK=true; shift ;;
        --no-start) NO_START=true; shift ;;
        --no-autostart) AUTOSTART=false; shift ;;
        --skip-check) SKIP_CHECK=true; shift ;;
        --no-interactive) shift ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
done
case "$MODE" in native|stream|periodic) ;; *) echo "Invalid --mode: $MODE (native|stream|periodic)" >&2; exit 1 ;; esac
if [ -n "$RELEASE_TAG" ]; then
    [[ "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid --version: expected a stable tag" >&2; exit 1; }
fi
[ "$ROLLBACK" = false ] || [ -z "$RELEASE_TAG" ] || { echo "Use either --rollback or --version" >&2; exit 1; }
[ "$(uname -s)" = Darwin ] || { echo "This installer requires macOS. On Linux use /install." >&2; exit 1; }
command -v python3 >/dev/null || { echo "Python 3.10+ is required. Install it with: brew install python" >&2; exit 1; }
PYTHON="$(python3 -c 'import sys; print(sys.executable)')"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ is required"'
if [ "$MODE" = native ]; then
    command -v swiftc >/dev/null || { echo "Install Xcode Command Line Tools: xcode-select --install" >&2; exit 1; }
    if [ "$SKIP_CHECK" = false ]; then
        MAC_VERSION="$(sw_vers -productVersion)"
        [ "${MAC_VERSION%%.*}" -ge 13 ] || { echo "Native AI Status requires macOS 13+. Use --mode stream on older Macs." >&2; exit 1; }
    fi
fi

USE_LOCAL_LIB=false
RUNNING_FROM_INSTALL=false
if [ "$SCRIPT_IS_FILE" = true ]; then
    case "$SCRIPT_DIR/" in "$INSTALL_DIR"/*) RUNNING_FROM_INSTALL=true ;; esac
    if [ "$RUNNING_FROM_INSTALL" = false ] && git -C "$SCRIPT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
        USE_LOCAL_LIB=true
    fi
fi
[ "$USE_LOCAL_LIB" = false ] || [ -z "$RELEASE_TAG" ] || { echo "--version requires the public installer, not a checkout" >&2; exit 1; }

mkdir -p "$(dirname "$INSTALL_DIR")"
LOCK_DIR="$(dirname "$INSTALL_DIR")/.ai-status-update.lock"
mkdir "$LOCK_DIR" 2>/dev/null || { echo "Another installation is running: $LOCK_DIR" >&2; exit 1; }
WORK_DIR=""
STAGE_DIR=""
OLD_INSTALL_MOVED=false
NEW_INSTALL_ACTIVE=false
OLD_APP_STOPPED=false
OLD_AGENT_STOPPED=false
SNAPSHOT_PATHS=()
cleanup() {
    local status=$? index target
    trap - EXIT
    set +e
    if [ "$status" -ne 0 ]; then
        [ "$NEW_INSTALL_ACTIVE" = false ] || rm -rf -- "$INSTALL_DIR"
        [ "$OLD_INSTALL_MOVED" = false ] || mv -- "$PREVIOUS_DIR" "$INSTALL_DIR"
        for index in "${!SNAPSHOT_PATHS[@]}"; do
            target="${SNAPSHOT_PATHS[$index]}"
            rm -f -- "$target"
            [ ! -e "$WORK_DIR/backups/$index" ] && [ ! -L "$WORK_DIR/backups/$index" ] || cp -a -- "$WORK_DIR/backups/$index" "$target"
        done
        if [ "$NO_START" = false ] && [ "$OLD_APP_STOPPED" = true ]; then
            if [ "$OLD_AGENT_STOPPED" = true ] && [ -f "$AGENT_FILE" ]; then
                launchctl bootstrap "gui/$(id -u)" "$AGENT_FILE" >/dev/null 2>&1 || open -a "$APP_LINK" >/dev/null 2>&1
            else
                open -a "$APP_LINK" >/dev/null 2>&1
            fi
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
copy_library() {
    [ -d "$1/packages/lib" ] && [ -d "$1/packages/shared" ] || { echo "Source is missing library/shared files" >&2; exit 1; }
    mkdir -p "$STAGE_DIR/packages"
    cp -a -- "$1/packages/lib" "$STAGE_DIR/packages/lib"
    cp -a -- "$1/packages/shared" "$STAGE_DIR/packages/shared"
    if [ -e "$1/package.json" ] || [ -L "$1/package.json" ]; then
        cp -- "$1/package.json" "$STAGE_DIR/package.json"
    fi
}

if [ "$ROLLBACK" = true ]; then
    [ -d "$PREVIOUS_DIR/packages/lib" ] || { echo "No previous installation is available" >&2; exit 1; }
    copy_library "$PREVIOUS_DIR"
elif [ "$RUNNING_FROM_INSTALL" = true ]; then
    [ -z "$RELEASE_TAG" ] || { echo "Use the public installer to install a specific version" >&2; exit 1; }
    copy_library "$INSTALL_DIR"
elif [ "$USE_LOCAL_LIB" = true ]; then
    copy_library "$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
    git -C "$SCRIPT_DIR" rev-parse HEAD > "$STAGE_DIR/packages/lib/BUILD_COMMIT"
else
    REPO_SLUG="${REPO_URL#https://github.com/}"
    REPO_SLUG="${REPO_SLUG%/}"
    REPO_SLUG="${REPO_SLUG%.git}"
    [[ "$REPO_URL" == https://github.com/* && "$REPO_SLUG" =~ ^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$ ]] || { echo "Expected a GitHub repository URL" >&2; exit 1; }
    command -v curl >/dev/null || { echo "curl is required to download a release" >&2; exit 1; }
    if [ -z "$RELEASE_TAG" ]; then
        RELEASE_TAG="$(curl --fail --silent --show-error --location --max-time 15 \
            -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$REPO_SLUG/releases/latest" | "$PYTHON" -c '
import json, re, sys
release = json.load(sys.stdin)
tag = release.get("tag_name", "")
if release.get("draft") or release.get("prerelease") or not isinstance(tag, str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
    sys.exit("No valid stable release found")
print(tag)
')"
    fi
    ASSET="ai-status-$RELEASE_TAG.tar.gz"
    ARCHIVE="$WORK_DIR/release.tar.gz"
    echo "Downloading $RELEASE_TAG…"
    curl --fail --silent --show-error --location --retry 2 --max-time 120 \
        --output "$ARCHIVE" "https://github.com/$REPO_SLUG/releases/download/$RELEASE_TAG/$ASSET"
    curl --fail --silent --show-error --location --retry 2 --max-time 30 \
        --output "$WORK_DIR/SHA256SUMS" "https://github.com/$REPO_SLUG/releases/download/$RELEASE_TAG/SHA256SUMS"
    "$PYTHON" - "$ARCHIVE" "$WORK_DIR/SHA256SUMS" "$ASSET" "$STAGE_DIR" <<'PY'
import hashlib, re, shutil, sys, tarfile
from pathlib import Path, PurePosixPath
archive, sums, name, destination = sys.argv[1:]
entries = [line.split() for line in Path(sums).read_text().splitlines()]
expected = [parts[0] for parts in entries if len(parts) == 2 and parts[1].lstrip("*") == name]
if len(expected) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", expected[0]):
    sys.exit("Missing or invalid package checksum")
if hashlib.sha256(Path(archive).read_bytes()).hexdigest() != expected[0].lower():
    sys.exit("Package checksum does not match")
root = Path(destination)
with tarfile.open(archive, "r:gz") as tar:
    for member in tar:
        parts = PurePosixPath(member.name).parts
        if member.name.startswith("/") or ".." in parts:
            sys.exit("Unsafe path in release archive")
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

# Validate imported CLI and all sources without querying a provider or touching
# credentials. Old releases without macOS sources fail before activation.
INSTALL_VERSION="$("$PYTHON" - "$STAGE_DIR" "${RELEASE_TAG#v}" "$MODE" <<'PY'
import json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
root = Path(sys.argv[1])
lib = root / "packages/lib"
required = [lib / "src/bin/ai-status", root / "packages/shared/providers/providers.json"]
if sys.argv[3] == "native":
    required += [lib / "macos/AIStatus.swift", lib / "macos/Info.plist", lib / "src/core/macos.py", lib / "assets/app.png"]
else:
    required += [lib / "src/core/swiftbar.py"]
for path in required:
    if not path.is_file():
        sys.exit(f"This release is missing {path.relative_to(root)}; choose a release with macOS support.")
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
json.loads((root / "packages/shared/providers/providers.json").read_text())
for script in lib.rglob("*.py"):
    compile(script.read_bytes(), str(script), "exec")
sys.path.insert(0, str(lib / "src"))
import core.cli
import core
if core.__version__ != version:
    sys.exit("CLI and release version metadata disagree")
print(version)
PY
)"

APP="$STAGE_DIR/AI Status.app"
PLUGIN_DIR=""
PLUGIN_FILE=""
if [ "$MODE" = native ]; then
    echo "Building the native macOS menu bar app…"
    mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
    cp "$STAGE_DIR/packages/lib/macos/Info.plist" "$APP/Contents/Info.plist"
    cp -R "$STAGE_DIR/packages/lib/assets" "$APP/Contents/Resources/assets"
    "$PYTHON" - "$APP/Contents" "$PYTHON" "$INSTALL_DIR/packages/lib/src/bin/ai-status" "$INSTALL_VERSION" <<'PY'
import json, plistlib, sys
from pathlib import Path
contents = Path(sys.argv[1])
(contents / "Resources/runtime.json").write_text(json.dumps({"python": sys.argv[2], "cli": sys.argv[3]}))
plist = contents / "Info.plist"
info = plistlib.loads(plist.read_bytes())
info["CFBundleShortVersionString"] = info["CFBundleVersion"] = sys.argv[4]
plist.write_bytes(plistlib.dumps(info))
PY
    ARCH="$(uname -m)"
    swiftc -O -parse-as-library -target "$ARCH-apple-macosx13.0" \
        -framework Cocoa -framework SwiftUI "$STAGE_DIR/packages/lib/macos/AIStatus.swift" \
        -o "$APP/Contents/MacOS/AIStatus"
    # Local builds use an ad-hoc signature; a notarized distribution is separate.
    if command -v codesign >/dev/null; then codesign --force --sign - "$APP"; fi
    "$APP/Contents/MacOS/AIStatus" --smoke
else
    PLUGIN_DIR="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)"
    [ -n "$PLUGIN_DIR" ] || PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"
    if [ "$MODE" = stream ]; then PLUGIN_FILE="$PLUGIN_DIR/ai-status.5s.py"; else PLUGIN_FILE="$PLUGIN_DIR/ai-status.30s.py"; fi
    "$PYTHON" - "$WORK_DIR/plugin.py" "$PYTHON" "$INSTALL_DIR/packages/lib/src/bin/ai-status" "$MODE" "$INSTALL_VERSION" <<'PY'
import shlex, sys
from pathlib import Path
path, python, cli, mode, version = sys.argv[1:]
command = "swiftbar-stream" if mode == "stream" else "swiftbar"
metadata = ""
if mode == "stream":
    metadata = "# <swiftbar.type>streamable</swiftbar.type>\n# <swiftbar.useTrailingStreamSeparator>true</swiftbar.useTrailingStreamSeparator>\n"
Path(path).write_text(f'''#!/bin/bash
# <xbar.title>AI Status</xbar.title>
# <xbar.version>v{version}</xbar.version>
# <xbar.author>gelzin</xbar.author>
# <xbar.desc>AI provider usage limits, using the shared AI Status core.</xbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
{metadata}exec {shlex.quote(python)} {shlex.quote(cli)} {shlex.quote(command)}
''')
PY
    bash -n "$WORK_DIR/plugin.py"
fi

# Snapshot the small external integration files before activation. Existing
# preferences are never rewritten, including on first native install.
if [ "$MODE" = native ]; then
    PLUGIN_DIR="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)"
    [ -n "$PLUGIN_DIR" ] || PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"
fi
mkdir -p "$WORK_DIR/backups" "$BIN_DIR" "$HOME/Applications" "$HOME/Library/LaunchAgents"
for target in "$BIN_DIR/ai-status" "$APP_LINK" "$AGENT_FILE"; do
    [ ! -d "$target" ] || [ -L "$target" ] || { echo "Refusing to replace existing directory: $target" >&2; exit 1; }
    index="${#SNAPSHOT_PATHS[@]}"
    SNAPSHOT_PATHS+=("$target")
    [ ! -e "$target" ] && [ ! -L "$target" ] || cp -a -- "$target" "$WORK_DIR/backups/$index"
done
if [ -n "$PLUGIN_DIR" ]; then
    if [ "$MODE" != native ]; then mkdir -p "$PLUGIN_DIR"; fi
    for target in "$PLUGIN_DIR/ai-status.5s.py" "$PLUGIN_DIR/ai-status.30s.py"; do
        index="${#SNAPSHOT_PATHS[@]}"
        SNAPSHOT_PATHS+=("$target")
        [ ! -e "$target" ] || cp -a -- "$target" "$WORK_DIR/backups/$index"
    done
fi

if [ "$NO_START" = false ]; then
    if launchctl bootout "gui/$(id -u)/com.gelzin.ai-status" >/dev/null 2>&1; then OLD_AGENT_STOPPED=true; fi
    if [ -x "$INSTALL_DIR/AI Status.app/Contents/MacOS/AIStatus" ]; then
        OLD_APP_STOPPED=true
        "$INSTALL_DIR/AI Status.app/Contents/MacOS/AIStatus" --quit
    fi
fi
if [ -d "$INSTALL_DIR" ]; then
    rm -rf -- "$PREVIOUS_DIR"
    mv -- "$INSTALL_DIR" "$PREVIOUS_DIR"
    OLD_INSTALL_MOVED=true
fi
mv -- "$STAGE_DIR" "$INSTALL_DIR"
STAGE_DIR=""
NEW_INSTALL_ACTIVE=true
chmod +x "$INSTALL_DIR/packages/lib/src/bin/ai-status"
ln -sf "$INSTALL_DIR/packages/lib/src/bin/ai-status" "$BIN_DIR/ai-status"

if [ "$MODE" = native ]; then
    ln -sfn "$INSTALL_DIR/AI Status.app" "$APP_LINK"
    if [ "$AUTOSTART" = true ]; then
        "$PYTHON" - "$AGENT_FILE" "$INSTALL_DIR/AI Status.app/Contents/MacOS/AIStatus" "$HOME" <<'PY'
import os, plistlib, sys
from pathlib import Path
path, executable, home = sys.argv[1:]
# No shell interpolation. LaunchAgent/GUI processes have a minimal PATH.
environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
for key in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_DATA_HOME"):
    if os.environ.get(key):
        environment[key] = os.environ[key]
Path(path).write_bytes(plistlib.dumps({"Label": "com.gelzin.ai-status",
    "ProgramArguments": [executable], "RunAtLoad": True,
    "WorkingDirectory": home, "EnvironmentVariables": environment,
    "LimitLoadToSessionType": "Aqua"}))
PY
    else
        rm -f "$AGENT_FILE"
    fi
    if [ "$NO_START" = false ]; then
        if [ "$AUTOSTART" = true ]; then
            launchctl bootstrap "gui/$(id -u)" "$AGENT_FILE" || open -a "$APP_LINK"
        else
            open -a "$APP_LINK"
        fi
    fi
    # Remove only the two plugin names generated by previous installers.
    rm -f "$PLUGIN_DIR/ai-status.5s.py" "$PLUGIN_DIR/ai-status.30s.py"
    echo "Installed $APP_LINK. Click AI Status in the menu bar; Settings configures providers and display."
else
    rm -f "$APP_LINK" "$AGENT_FILE"
    rm -f "$PLUGIN_DIR/ai-status.5s.py" "$PLUGIN_DIR/ai-status.30s.py"
    cp "$WORK_DIR/plugin.py" "$PLUGIN_FILE"
    chmod +x "$PLUGIN_FILE"
    defaults write com.ameba.SwiftBar PluginDirectory "$PLUGIN_DIR"
    if [ "$NO_START" = false ]; then
        open -a SwiftBar >/dev/null 2>&1 || true
        open -g 'swiftbar://refreshallplugins' >/dev/null 2>&1 || true
    fi
    echo "Installed SwiftBar plugin: $PLUGIN_FILE ($MODE). Install SwiftBar with: brew install --cask swiftbar"
fi
echo "Re-run to update. Use --rollback to restore the previous library version."
