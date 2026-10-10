# Contributing to AI Status

**Bug reports, feature requests, and pull requests are welcome.**

This project targets Linux, Waybar, and the Omarchy Quickshell shell. The shared Python backend lives in `packages/lib/src/core/`, providers in `packages/lib/src/providers/`, and the native Omarchy plugin in `packages/lib/quickshell/`.

## Adding a New Provider

Each provider needs two files in `src/providers/<name>/`:

| File | Purpose |
|---|---|
| `query.sh` | Fetches raw data via API call, CLI invocation, or terminal interaction |
| `parse.py` | Exports `parse(raw_output)` returning a standardized JSON structure |

Walk through `src/providers/claude/` as a reference implementation.

Steps:

1. Fork the repository on GitHub
2. Create `src/providers/<name>/query.sh` with your data-fetching logic
3. Create `src/providers/<name>/parse.py` with a `parse(raw_output)` function
4. Register the provider via `ai-status config` (it appears automatically)
5. Open a pull request

## Adding Support for Other Platforms

Waybar formatting lives in `packages/lib/src/core/render.py` using Pango markup. The Quickshell adapter emits structured snapshots from `packages/lib/src/core/quickshell.py`; QML owns its presentation. Keep new frontends separate so existing Waybar output remains compatible. To support another status bar or OS:

1. Fork the repository on GitHub
2. Add an output adapter for your target and reuse the existing queries and state
3. Update `install.sh` and `check.sh` for the new environment
4. Open a pull request

## Making Changes

| Step | Action |
|---|---|
| 1 | Fork and clone the repository |
| 2 | Make your changes -- keep the provider architecture consistent |
| 3 | Run `./install.sh` to test locally |
| 4 | Verify the daemon runs: `ai-status daemon` |
| 5 | Open a pull request describing what you changed and why |

Run `python3 -m unittest discover -s packages/lib/tests -v` for adapter and isolated installer tests. For native plugin validation and desktop acceptance checks, see [INSTALL.md](packages/lib/INSTALL.md#development-validation).

Run `python3 packages/lib/tests/run_qml_tests.py` for native settings and usage page tests. These use the production QML pages with a fake daemon and theme, via Qt Quick Test's offscreen renderer. Install `qt6-declarative-dev-tools`, `qml6-module-qtquick`, `qml6-module-qtquick-window`, `qml6-module-qtquick-shapes`, `qml6-module-qtqml-workerscript`, `qml6-module-qttest`, and `qt6-qpa-plugins`. They do not replace an Omarchy desktop smoke test.
