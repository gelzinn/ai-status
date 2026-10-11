# macOS development and validation

The SwiftUI sources are in `packages/lib/macos/`. The native app consumes
the shared JSON daemon and uses the same settings validation and provider
selection commands as the other native panels.

Run `bash packages/lib/install-macos.sh` from the repository root on a Mac
to compile and launch the checkout's code, including local changes.
Verify menu bar selection, popover open/close and Escape, manual and background
refresh, settings Save/Cancel and reordering, reset-credit navigation, About,
multiple displays, and launch at sign-in. Check both light and dark
appearance, provider errors, missing credentials and cached results.

Linux checks cover the backend and installer behavior. They do not verify
AppKit/SwiftUI compilation or the on-screen macOS experience; those need a
Mac.
