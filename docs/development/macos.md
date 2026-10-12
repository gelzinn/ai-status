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

The app's `--smoke --preview-directory /tmp/ai-status-previews` command renders
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
