# macOS development and validation

The SwiftUI sources are in `packages/lib/macos/`. The native app consumes
the shared JSON daemon and uses the same settings validation and provider
selection commands as the other native panels.

Run `bash packages/lib/install-macos.sh` from the repository root on a Mac
to compile and launch the checkout's code, including local changes.
Verify menu bar selection, popover open/close and Escape, manual and background
refresh, settings Save/Cancel and reordering, reset-credit and update navigation, About,
multiple displays, and launch at sign-in. Check both light and dark
appearance, provider errors, missing credentials and cached results.

Select one and several menu bar items, including two limits from one account
and two accounts for one provider. Check individual logos, loading and
used/remaining values, Save/Cancel, empty-selection validation and migration
from existing single-item preferences. Clicking a usage metric must replace
the first item while retaining the rest without duplicates. Temporarily
unavailable items must remain saved and reappear when data returns. Check the
combined menu bar width and popover position on a crowded bar and multiple
displays.

Production builds use `-Osize`, whole-module optimization, linker dead stripping
and symbol stripping before ad-hoc signing. They omit the developer fixture code.
The installed app's `--smoke` validates bundled fonts/icons and constructs the
native panel without provider requests or desktop notifications;
`--check-runtime` checks its Python/backend configuration.

For full smoke validation and screenshots, compile with `-D AI_STATUS_SMOKE`.
After installing the checkout, run this on a Mac to build a separate temporary
app with the same production optimization settings:

```sh
AI_STATUS_SMOKE_DIR="$(mktemp -d)"
AI_STATUS_SMOKE_APP="$AI_STATUS_SMOKE_DIR/AI Status.app"
cp -R "$HOME/.local/share/ai-status/AI Status.app" "$AI_STATUS_SMOKE_APP"
swiftc -Osize -whole-module-optimization -Xlinker -dead_strip -D AI_STATUS_SMOKE \
  -parse-as-library -target "$(uname -m)-apple-macosx13.0" \
  -framework Cocoa -framework SwiftUI -framework UserNotifications \
  packages/lib/macos/AIStatus.swift -o "$AI_STATUS_SMOKE_APP/Contents/MacOS/AIStatus"
strip -u -r "$AI_STATUS_SMOKE_APP/Contents/MacOS/AIStatus"
codesign --force --sign - "$AI_STATUS_SMOKE_APP"
codesign --verify --strict "$AI_STATUS_SMOKE_APP"
"$AI_STATUS_SMOKE_APP/Contents/MacOS/AIStatus" \
  --smoke --preview-directory "$AI_STATUS_SMOKE_DIR/previews"
```

The developer app's `--smoke --preview-directory` command renders
the update notice, compact update page, downloads with known and unknown sizes,
verification, installation, automatic restart, completion, retry feedback and
manual fallback alongside the other native pages. The local fixture validates
live `update --json-progress` output before process exit, split JSON writes,
unterminated final lines, large stdout/stderr output, navigation during a download,
failure and retry. It never runs an installer or accesses the network.

On a supported installed build, **Update now** downloads and installs inside
the app. The actions footer uses the same spinner as Settings Save, shows real
download percentage and transferred bytes when the server supplies a size, and
keeps an indeterminate bar for other stages. The page explains that AI Status
restarts automatically and keeps settings. Terminal commands are available
under **Update manually…**. Verify that closing and reopening the panel or
returning to usage preserves the running update, and that retry works after a
network failure. The updater runs independently of short settings commands and
survives the old app quitting so the installer can activate and reopen the new
version.

Quota notifications use `UserNotifications` under the AI Status app identity.
The app requests permission on its first enabled snapshot; `--smoke` never
requests permission or sends desktop alerts. The smoke fixture validates quota
preferences, threshold input, per-account/window overrides, silence controls,
and the notification selection payload. On a Mac, verify permission allowed
and denied, a threshold crossing and quota recovery, clicking a banner to open
the corresponding account and window, and restarting between submission and
acknowledgment. Check that disabling alerts, quiet hours and silence discard
pending alerts, and that reconnecting after five minutes never shows an old
quota observation. The Python outbox lives in
`~/.config/ai-status/native-alerts.json`; notification settings and suppression
history use separate files in the same directory.

Linux checks cover the backend and installer behavior. They do not verify
AppKit/SwiftUI compilation or the on-screen macOS experience; those need a
Mac.

The macOS CI job verifies the signed production build and measures it before
backend tests or preview generation. `packages/lib/macos/size_report.py` reports
the executable, `.app` bundle, and current installed payload separately; the
bundle and executable are included in the installed total. Initial limits are
2 MiB, 3 MiB and 5 MiB respectively. CI compares the production executable
with the same source/compiler built using the previous `-O` settings and
embedded developer fixtures, signed without stripping. This comparison isolates
the build changes; it does not reproduce an older release's source or measure a
compressed download. The report includes architecture, Swift compiler version
and the largest installed files in the job summary and `macos-size-report`
artifact. The fixture app is a separate copy and never affects these totals.

The initial arm64 measurement with Apple Swift 5.10 was 0.83 MiB for the
executable, 1.23 MiB for the bundle and 2.53 MiB for the installed payload.
The comparison executable was 2.30 MiB, a 63.8% executable reduction.
Compiler versions and architectures can change these figures.

Measurements sum regular-file logical bytes without following symlinks. They
exclude system frameworks, the external Python runtime, user settings and
retained rollback sources. File allocation and Finder's size presentation can
differ. Native installs discard other platforms' UI/test files and build caches;
the Lucide license remains with the icons. After a successful update, rollback
retains the previous sources and assets and recompiles the previous app when
requested, avoiding a second installed executable. A failed installation keeps
the active app intact.
