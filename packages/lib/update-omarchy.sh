#!/bin/bash
# Shared by the installer and the plugin's explicit Update action.

ai_status_update_omarchy_plugin() (
    set -uo pipefail
    umask 077
    export GIT_TERMINAL_PROMPT=0
    export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -oBatchMode=yes}"
    local plugin_id="io.github.gelzinn.ai-status"
    local plugin_dir="$HOME/.config/omarchy/plugins/$plugin_id"
    local lock="${XDG_CACHE_HOME:-$HOME/.cache}/ai-status/omarchy-plugin-update.lock"
    local work="" backup="" origin status installed=false

    if [ ! -d "$plugin_dir/.git" ] || [ -L "$plugin_dir" ]; then
        echo "AI Status plugin is not a managed Git checkout: $plugin_dir" >&2
        exit 1
    fi
    mkdir -p -- "${lock%/*}" || exit 1
    if ! mkdir -- "$lock" 2>/dev/null; then
        echo "Another AI Status plugin update is running (lock: $lock)." >&2
        exit 1
    fi
    cleanup_omarchy_update() {
        local result=$?
        trap - EXIT
        if [ -n "$backup" ] && [ -d "$backup/plugin" ] && [ "$installed" = false ]; then
            if [ -e "$plugin_dir" ] || [ -L "$plugin_dir" ]; then
                mv -- "$plugin_dir" "$backup/failed-plugin" || {
                    echo "Previous plugin remains at $backup/plugin; could not move the failed installation." >&2
                    result=1
                }
            fi
            if [ ! -e "$plugin_dir" ] && [ ! -L "$plugin_dir" ]; then
                if mv -- "$backup/plugin" "$plugin_dir"; then
                    echo "Previous AI Status plugin restored." >&2
                    if command -v omarchy-shell >/dev/null 2>&1; then
                        omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
                    fi
                else
                    echo "Could not restore the plugin; its complete backup remains at $backup/plugin." >&2
                    result=1
                fi
            fi
        fi
        [ -z "$work" ] || rm -rf -- "$work"
        rmdir -- "$lock" || result=1
        exit "$result"
    }
    trap cleanup_omarchy_update EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    work="$(mktemp -d "${plugin_dir%/*}/.ai-status-update.XXXXXX")" || exit 1

    if omarchy plugin update "$plugin_id" --yes > "$work/update.log" 2>&1; then
        cat "$work/update.log"
        exit 0
    else
        status=$?
        cat "$work/update.log" >&2
    fi
    # Omarchy suppresses Git's merge error and uses this message for every
    # failed fast-forward, including divergent history in an untouched clone.
    case "$(cat "$work/update.log")" in
        *"omarchy-plugin-update: cannot fast-forward '$plugin_id';"*) ;;
        *) exit "$status" ;;
    esac
    origin="$(git -C "$plugin_dir" remote get-url origin)" || exit 1
    case "$origin" in
        ""|-*) echo "The plugin has no usable origin repository." >&2; exit 1 ;;
        /*|*:*) ;;
        *) origin="$(cd "$plugin_dir" && realpath -m -- "$origin")" || exit 1 ;;
    esac
    echo "Preparing a fresh AI Status plugin checkout…"
    # Prepare the replacement before moving the installed copy. Its original
    # files and Git history never need a reset, clean, stash or local commit.
    git clone --no-hardlinks -- "$origin" "$work/source" || exit 1
    python3 - "$work/source/manifest.json" "$plugin_id" <<'PY' || exit 1
import json, sys
from pathlib import Path
try:
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, ValueError):
    sys.exit("Update source has no usable plugin manifest; installed files were kept.")
if not isinstance(manifest, dict) or manifest.get("id") != sys.argv[2]:
    sys.exit("Update source does not identify the AI Status plugin; installed files were kept.")
PY
    # Hidden siblings are excluded by Omarchy's catalog/update scans and stay
    # on the same filesystem, so moving/restoring the checkout is atomic.
    local backup_root="${plugin_dir%/*}/.ai-status-backups"
    mkdir -p -- "$backup_root" || exit 1
    backup="$(mktemp -d "$backup_root/$plugin_id.XXXXXX")" || exit 1
    echo "Preserving the installed plugin at $backup/plugin"
    mv -- "$plugin_dir" "$backup/plugin" || exit 1
    # Add validates the clean checkout and rescans it. We do not remove or
    # disable the plugin: its id, bar placement and settings remain in shell.json.
    omarchy plugin add "$work/source" --yes || exit $?
    [ -d "$plugin_dir/.git" ] || { echo "Omarchy did not install the expected plugin." >&2; exit 1; }
    git -C "$plugin_dir" remote set-url origin "$origin" || exit 1
    installed=true
    echo "AI Status plugin recovered. Previous files and Git history: $backup/plugin"
)

if [ -z "${BASH_SOURCE[0]:-}" ] || [ "${BASH_SOURCE[0]}" = "$0" ]; then
    ai_status_update_omarchy_plugin && omarchy restart shell
fi
