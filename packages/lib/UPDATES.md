# Updating AI Status

Updates are optional. The **Update available** link opens an in-app guide for
your installation. Opening the guide does not download or install anything.
The page includes release notes and a short explanation of the next step.
Windows and the native macOS app show a spinner and progress bar in the fixed
actions footer. Downloads show the percentage and transferred bytes when the
server supplies a size; other stages use an indeterminate bar.

You can also start that action explicitly from the command line:

```bash
ai-status update
```

| Installation | Update action |
|---|---|
| Windows installer | Downloads the stable installer, verifies its SHA-256 checksum, then opens setup |
| Windows portable ZIP | Opens instructions for downloading and replacing the portable copy |
| Omarchy plugin | Opens a terminal with `omarchy plugin update io.github.gelzinn.ai-status --yes && omarchy restart shell` |
| Linux public installer | Opens a terminal with the public installer, preserving the desktop bar |
| macOS native public installer | Downloads and verifies the stable package inside the app, installs it, then reopens AI Status automatically |
| macOS SwiftBar installer | Opens Terminal with the public installer, preserving stream or periodic mode |
| Checkout or custom location | Shows manual instructions; does not replace the checkout |

Windows reports when setup opens; finish the installation in that window.
Linux and SwiftBar report when the terminal opens; follow the download and
installation there. The native macOS app follows the update through installation
and briefly closes to reopen the new version. Errors offer a retry in the app,
or appear on stderr with a nonzero CLI exit status. If no supported Linux terminal
is available, expand **Terminal command** and run it in your own terminal.

Only newer stable versions trigger the notice. Drafts, prereleases, and older
version numbers are excluded. There are no forced updates or support-expiration
notices.

The desktop checks for a new release whenever it refreshes usage: automatically
every five minutes and on manual refresh. The release query runs alongside the
provider queries, so usage results can appear while GitHub is still responding.
If GitHub is unavailable, usage still refreshes and the last known update notice
is preserved. Checking for a release does not install it.

## Windows

For an installed copy, **Download and open installer** downloads the exact
stable release installer and its `SHA256SUMS` file from GitHub. The installer
is opened only after its checksum matches. It remains a normal setup wizard;
the app does not silently replace itself.

The footer shows checking, download, verification and automatic setup opening.
The progress remains available when you close the panel or navigate back to usage.
Once setup opens, the footer explains how to finish and reopen AI Status; this
handoff does not claim that installation has finished.

Keep your existing installation folder. If setup asks to close AI Status,
allow it to do so, and leave **Launch AI Status** selected at the end to start
the updated app. You can cancel setup before installation. A verified
installer is retained in the AI Status cache while setup uses it.

For a portable copy, download the Windows portable ZIP from
[GitHub Releases](https://github.com/gelzinn/ai-status/releases/latest), quit
AI Status, and extract the new version to a new folder. Launch `ai-status.exe`
from that folder. Keep the old folder until you have checked the new version.
Both formats retain settings and provider configuration in AppData outside the
application folder.

## macOS

The public installer handles fresh installs and upgrades:

```bash
curl -fsSL https://ai-status.gelzin.com/install/macos | bash
```

For a supported native installation, **Update now** downloads the versioned
package and checks its SHA-256 checksum inside the app. The footer follows
checking, downloading, verification, installation and automatic restart. You can
navigate away and return without losing progress. **Update manually…** reveals
the copyable Terminal command when needed.

The action preserves native, SwiftBar stream or SwiftBar periodic mode; SwiftBar
continues to use Terminal. Native updates keep login startup disabled when there
is no existing AI Status LaunchAgent. The installer stages and validates the
release before stopping the old app, then restarts AI Status. The independent
updater continues through activation even after the old app closes. Failed
installation restores the previous version and keeps settings.
See [macOS installation](MACOS.md) for prerequisites and explicit mode flags.

## Linux update command

The public installer handles fresh installs and upgrades:

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

New releases include a package containing the library, shared provider
metadata, and root `package.json`, plus a SHA-256 checksum verified by the installer. Older
releases without a package use an archive of the exact tag. Downloading either
format does not require git; older versions can still list it in their own
dependency checks.

To install a specific version, including rolling back to an earlier release:

```bash
curl -fsSL https://ai-status.gelzin.com/install | bash -s -- --version v0.9.0
```

Both `v0.9.0` and `0.9.0` are accepted. The release must contain the current
`packages/lib` and `packages/shared` layout and version metadata matching the tag;
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
library itself (`packages/lib`, the shared provider metadata, and root `package.json`), never the
website, `node_modules`, or build output. Each run re-extracts that copy, so the
same command covers every case:

| State | Action |
|---|---|
| First install | Extracts the lib and sets up symlinks |
| Already installed | Re-extracts the latest published stable release |
| Local checkout | Extracts from your working tree, local edits included |
| Older full-repo install | Replaced with the lean copy automatically |

After updating, the script reloads only the selected bar. Waybar receives its existing reload signal; Quickshell updates the existing plugin, then runs `omarchy restart shell` to load the updated QML components. First-time Quickshell installation uses Omarchy's plugin add/enable mechanism. Use `--bar waybar` or `--bar quickshell` to choose explicitly. Existing display preferences are preserved unless changed in the wizard or by flags.

For a plugin installed directly through Omarchy, update only AI Status with:

```bash
omarchy plugin update io.github.gelzinn.ai-status && omarchy restart shell
```

The shell restarts only after the plugin update succeeds, so the panel loads
the updated QML components. Reopen the panel after the restart.

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


Release notes are available on the [web changelog](https://ai-status.gelzin.com/changelog)
and [GitHub Releases](https://github.com/gelzinn/ai-status/releases).

## Checking Your Version

The root `package.json` is the version source for the CLI, desktop apps,
installers, and releases. Desktop installations read it with Python; Node.js
is not required. Published archives also contain a generated
`packages/lib/VERSION` for older installers that copy only the library and
shared files. New installations prefer `package.json` and use the legacy
file only when that manifest is absent. Invalid manifest metadata stops an
installation before activation. Older releases and offline rollbacks remain
supported with their original `VERSION` file.

The current version appears at the top of the Waybar tooltip or Quickshell details panel. For the CLI installation, you can also check:

```bash
ai-status --version
```

For older versions without that flag, read
`~/.local/share/ai-status/packages/lib/VERSION`.
