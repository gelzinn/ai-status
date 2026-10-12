# Native update progress previews

The images render the production views with sample data. No provider query or
real update runs during capture. The fixture starts at v0.15.0 with v0.16.0
available; completion and already-current examples adjust the versions to match
their state.

Windows follows the download through checksum verification and automatic setup
opening. The user completes the normal setup wizard. macOS follows downloading,
verification and installation inside the app, then closes briefly and reopens.
Linux follows release checking and terminal opening; the actual download and
installation continue in that terminal. Unknown download sizes show transferred
bytes and an indeterminate bar.

## Before and after

| Platform | Previous update page | New progress and next step |
| --- | --- | --- |
| Windows | ![Previous Windows tutorial](before/windows-guide.png) | ![Windows download progress](windows-downloading.png) |
| macOS | ![Previous macOS Terminal guide](before/macos-guide.png) | ![Native macOS download progress](macos-downloading.png) |
| Linux / Omarchy | ![Previous Linux tutorial](before/linux-guide.png) | ![Linux terminal handoff](linux-terminal.png) |

The previous Windows downloading state only changed the status text:

![Previous Windows download feedback](before/windows-downloading.png)

## Windows

<details>
<summary>Show all 12 Windows states</summary>

| Stage | Production widget preview |
| --- | --- |
| Update notice | ![Windows: Update notice](windows-available.png) |
| Compact update page | ![Windows: Compact update page](windows-guide.png) |
| Check stable release | ![Windows: Check stable release](windows-checking.png) |
| Check published checksum | ![Windows: Check published checksum](windows-checksum.png) |
| Download without a supplied size | ![Windows: Download without a supplied size](windows-downloading-unknown.png) |
| Download with real byte progress | ![Windows: Download with real byte progress](windows-downloading.png) |
| Verify downloaded installer | ![Windows: Verify downloaded installer](windows-verifying.png) |
| Open setup automatically | ![Windows: Open setup automatically](windows-opening.png) |
| Setup opened; finish in wizard | ![Windows: Setup opened; finish in wizard](windows-installer.png) |
| Download failed; Retry update | ![Windows: Download failed; Retry update](windows-error.png) |
| Retry starts a new check | ![Windows: Retry starts a new check](windows-retry.png) |
| Already up to date | ![Windows: Already up to date](windows-up-to-date.png) |

</details>

The fixed footer stays visible while the page scrolls. After setup opens, **Done**
returns to usage without opening another installer. If setup is cancelled, opening
the update page again offers the update action.

## macOS

<details>
<summary>Show all 17 macOS states</summary>

| Stage | Native SwiftUI preview |
| --- | --- |
| Update notice | ![macOS: Update notice](macos-available.png) |
| Compact update page | ![macOS: Compact update page](macos-guide.png) |
| Optional Terminal command | ![macOS: Optional Terminal command](macos-manual-alternative.png) |
| Check stable release | ![macOS: Check stable release](macos-checking.png) |
| Download without a supplied size | ![macOS: Download without a supplied size](macos-downloading-unknown.png) |
| Download with real byte progress | ![macOS: Download with real byte progress](macos-downloading.png) |
| Verify downloaded package | ![macOS: Verify downloaded package](macos-verifying.png) |
| Install verified package | ![macOS: Install verified package](macos-installing.png) |
| Close briefly and reopen automatically | ![macOS: Close briefly and reopen automatically](macos-restarting.png) |
| Completion fixture with new version | ![macOS: Completion fixture with new version](macos-complete.png) |
| Already up to date | ![macOS: Already up to date](macos-up-to-date.png) |
| Runtime unavailable; retry feedback | ![macOS: Runtime unavailable; retry feedback](macos-error.png) |
| Interrupted download; retry feedback | ![macOS: Interrupted download; retry feedback](macos-download-error.png) |
| Retry starts a new check | ![macOS: Retry starts a new check](macos-retry.png) |
| Manual installation fallback | ![macOS: Manual installation fallback](macos-manual.png) |
| SwiftBar Terminal alternative | ![macOS: SwiftBar Terminal alternative](macos-terminal-guide.png) |
| SwiftBar terminal opened | ![macOS: SwiftBar terminal opened](macos-terminal-handoff.png) |

</details>

These are native macOS captures from the compiled SwiftUI app, including the
shared Settings Save spinner. The completion fixture renders the final CLI result;
during a real native update the old app closes at the restart stage, and the new
app opens on usage. SwiftBar still hands installation to Terminal and explicitly
shows **Updater opened**.

## Linux

<details>
<summary>Show all 9 Linux / Omarchy states</summary>

| Stage | Production QML preview |
| --- | --- |
| Update notice | ![Linux: Update notice](linux-available.png) |
| Compact update page | ![Linux: Compact update page](linux-guide.png) |
| Optional copyable command | ![Linux: Optional copyable command](linux-command.png) |
| Check stable release | ![Linux: Check stable release](linux-checking.png) |
| Open terminal automatically | ![Linux: Open terminal automatically](linux-opening.png) |
| Terminal opened; continue there | ![Linux: Terminal opened; continue there](linux-terminal.png) |
| Terminal unavailable; command expanded | ![Linux: Terminal unavailable; command expanded](linux-error.png) |
| Retry starts a new check | ![Linux: Retry starts a new check](linux-retry.png) |
| Already up to date | ![Linux: Already up to date](linux-up-to-date.png) |

</details>

The spinner is the same loader-circle used by Saving. The bar is indeterminate
while checking the release and opening the terminal. The footer explains where to
follow the remaining work and when the shell restarts. **Done** returns to usage.

## Capture sources and reproduction

- Windows: production Qt widgets rendered offscreen on Linux with PySide6 6.12,
  bundled fonts and artwork. Source: commit `818fab6`. Baselines render the old
  widgets and guide from `38df1df` with the same sample versions.
- Linux: production QML rendered offscreen with Qt Quick's software renderer and
  the test daemon/Omarchy theme (dark surface, blue accent, 6px corners). Source:
  commit `818fab6`; this does not capture a running Omarchy desktop.
- macOS: unmodified `update-*.png` files from the `macos-panel-preview` artifact
  for commit `818fab6` in the
  [native macOS CI run](https://github.com/gelzinn/ai-status/actions/runs/38299549938/job/114978908864).
- The Linux and macOS baselines are the existing tracked
  [Linux guide](../updates-linux-guide.png) and
  [native macOS guide](../updates-macos-guide.png), copied without alteration.

From the repository root, with the desktop test dependencies installed:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=packages/lib/src \
  python3 packages/lib/tests/render_update_previews.py --output docs/screenshots/update-progress
QT_QPA_PLATFORM=offscreen PYTHONPATH=packages/lib/src \
  python3 packages/lib/tests/render_update_previews.py --output docs/screenshots/update-progress/before --before-ref 38df1df
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python3 packages/lib/tests/render_update_progress_qml.py --output docs/screenshots/update-progress
```

On macOS, build the app as described in
[macOS development](../../development/macos.md), then run the binary with
`--smoke --preview-directory /tmp/ai-status-update-previews`. Copy its
`update-*.png` files here with the `macos-` prefix. The local CLI fixtures validate
live progress, split lines, large stdout/stderr output, final output without a
newline, error and retry; they never execute an installer.

