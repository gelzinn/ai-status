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
and downloads its exact `vX.Y.Z` tag. Commits merged into `main` after that
release are not installed until the next release is published. Drafts and
prereleases are excluded. If resolving or downloading the release fails, the
installer stops instead of falling back to `main`.

To install a specific version, including rolling back to an earlier release:

```bash
curl -fsSL https://ai-status.gelzin.com/install | bash -s -- --version v0.9.0
```

Both `v0.9.0` and `0.9.0` are accepted. The release must contain the current
`packages/lib` and `packages/shared` layout and a matching `VERSION` file;
older releases from before the monorepo migration are not supported.
An explicit version does not require the GitHub releases API to be available.

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

After updating, the script restarts Waybar automatically to apply changes.

Release notes are available on [GitHub Releases](https://github.com/gelzinn/ai-status/releases)
and, for releases made with the new workflow, in `packages/lib/CHANGELOG.md`.

## Checking Your Version

The current version is shown at the top of the Waybar tooltip. You can also check:

```bash
cat ~/.local/share/ai-status/packages/lib/VERSION
```
