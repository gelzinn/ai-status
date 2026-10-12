# Settings subnavigation previews

These screenshots render the production Settings panels with simulated Codex
and Claude usage, four enabled providers and the product version from the root
manifest. They contain no live account data or credentials.

Each interface has four sections: General, Appearance, Alerts and Providers.
The section buttons, panel header and Save/Cancel actions remain visible while
the section content scrolls.

- `quickshell-*.png` uses Qt Quick Test's offscreen software renderer and the
  unchanged dark shell fixtures in `packages/lib/tests/qml/`. The fixtures use a
  monospace font and square corners. A running Omarchy desktop supplies its own
  theme, font and window behavior. The Providers capture uses twelve sample
  connections, including the four enabled ones.
- `windows-*.png` uses the production Qt widget adapter with its Windows startup
  option enabled, an offscreen renderer on Linux and the Fusion widget style.
  Configuration and cache files are isolated by the desktop test fixture. This
  is a rendered preview of the Windows interface, rather than a native Windows
  desktop capture.

The macOS native smoke test also captures `settings-general.png`,
`settings-appearance.png`, `settings-alerts.png` and `settings-providers.png`.
The `macos-native` job in `.github/workflows/ci.yml` runs that capture on
`macos-14` and uploads it in the `macos-panel-preview` artifact. The Linux
renderers used here do not validate the native macOS layout.

To regenerate the Quickshell previews with Qt 6 Quick Test installed:

```sh
python3 packages/lib/tests/render_settings_previews.py --platform quickshell
```

Set `QMLTESTRUNNER` when the executable is outside the standard Qt 6 location.
The renderer inherits Qt library, plugin and import paths from the environment.
To regenerate the Windows adapter previews, install
`packages/lib/windows/requirements.txt` in the Python environment and run:

```sh
python packages/lib/tests/render_settings_previews.py --platform windows
```

Both commands default to this directory; `--output` chooses another destination.
Provider logos come from the bundled assets. See the
[artwork and licenses](../../../packages/lib/assets/README.md).
