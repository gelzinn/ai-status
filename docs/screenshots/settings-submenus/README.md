# Settings subnavigation previews

These screenshots render the production Settings panels with simulated Codex
and Claude usage, four enabled providers and the product version from the root
manifest. They contain no live account data or credentials.

Each interface has four sections: General, Appearance, Alerts and Providers.
The tabs form one horizontal strip with widths determined by their labels.
The strip scrolls horizontally when the tabs exceed the available width and
reveals the selected tab. It remains above the scrolling section content;
the panel header and Save/Cancel actions stay visible as well. The scrolling
viewports reach the panel edges and separators, with padding inside their content.

- `quickshell-*.png` uses Qt Quick Test's offscreen software renderer and the
  unchanged dark shell fixtures in `packages/lib/tests/qml/`. The fixtures use a
  monospace font and square corners. A running Omarchy desktop supplies its own
  theme, font and window behavior. The Providers capture uses sixteen sample
  connections, including the four enabled ones, and shows the tab strip scrolled
  right to reveal the selected Providers tab. `quickshell-providers-bottom.png`
  shows the bottom of the same provider list, including the padding before the
  footer separator and the content clipping at the top of the viewport.
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
