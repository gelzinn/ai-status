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

The public installer resolves the latest **published stable GitHub Release**
and downloads its versioned package. Commits merged into `main` after that
release are not installed until the next release is published. Drafts and
prereleases are excluded. If resolving or downloading the release fails, the
installer stops instead of falling back to `main`.

New releases include a package containing only the library and shared
provider metadata, plus a SHA-256 checksum verified by the installer. Older
releases without a package use an archive of the exact tag. Downloading either
format does not require git; older versions can still list it in their own
dependency checks.

To install a specific version, including rolling back to an earlier release:

```bash
curl -fsSL https://ai-status.gelzin.com/install | bash -s -- --version v0.9.0
```

Both `v0.9.0` and `0.9.0` are accepted. The release must contain the current
`packages/lib` and `packages/shared` layout and a matching `VERSION` file;
older releases from before the monorepo migration are not supported.
An explicit version does not require the GitHub releases API to be available.

After a successful update, the previous installation is kept at
`~/.local/share/ai-status.previous`. To restore it without downloading anything:

```bash
bash ~/.local/share/ai-status/packages/lib/install.sh --rollback
```

`--rollback` uses the previous local copy and cannot be combined with
`--version`. It preserves your current preferences. You can also choose a
published older release with `--version` as shown above.

Running from a local checkout installs that checkout's working tree for
development, including unreleased changes. `--version` is only supported by
the remote installer. To update an installed copy, use the public command
above; running its internal `install.sh` directly only repeats setup.

## How It Works

The script installs a **lean copy** at `~/.local/share/ai-status/` — only the
library itself (`packages/lib` plus the shared provider metadata), never the
website, `node_modules`, or build output. Each run re-extracts that copy, so the
same command covers every case:

| State | Action |
|---|---|
| First install | Extracts the lib and sets up symlinks |
| Already installed | Re-extracts the latest published stable release |
| Local checkout | Extracts from your working tree, local edits included |
| Older full-repo install | Replaced with the lean copy automatically |

After updating, the script reloads only the selected bar. Waybar receives its existing reload signal; Quickshell uses Omarchy's plugin add/update mechanism and hot reload. Use `--bar waybar` or `--bar quickshell` to choose explicitly. Existing display preferences are preserved unless changed in the wizard or by flags.

For a plugin installed directly through Omarchy, update only AI Status with:

```bash
omarchy plugin update io.github.gelzinn.ai-status
```

Omarchy keeps the plugin's bar placement and refuses updates it cannot fast-forward. Shared preferences and provider credentials remain outside the plugin checkout.
Downloads, checksums, Python validation, CLI import, and dependency checks
run in a staging directory before replacing the active installation. If
activation or setup fails, the installer restores the previous files,
preferences, command symlinks, and Waybar configuration. Concurrent installer
runs are blocked by a lock.

Updates preserve your provider selection, metric, and display preferences
and skip the first-install wizard. Explicit display flags override the saved
values. Waybar modules are only reconfigured during an update if you pass
`--configure-waybar true`.


Release notes are available on [GitHub Releases](https://github.com/gelzinn/ai-status/releases)
and, for releases made with the new workflow, in `packages/lib/CHANGELOG.md`.

## Checking Your Version

The current version appears at the top of the Waybar tooltip or Quickshell details panel. For the CLI installation, you can also check:

```bash
ai-status --version
```

For older versions without that flag, read
`~/.local/share/ai-status/packages/lib/VERSION`.
