# Settings subnavigation previews

These screenshots render the production Settings panels with simulated Codex
and Claude usage, four enabled providers and the product version from the root
manifest. They contain no live account data or credentials.
There are 21 PNGs: ten Quickshell captures and eleven Windows adapter captures.
Each interface has six sections in this order: General, Appearance, Alerts,
Providers, Guide and About. Guide presents controls and keyboard bindings in a
table; About contains project details and links to Guide, Report a bug,
Documentation and GitHub.
The tabs form one horizontal strip with widths determined by their labels.
The strip scrolls horizontally when the tabs exceed the available width and
reveals the selected tab. It remains above the scrolling section content;
the panel header and Save/Cancel actions stay visible as well. The scrolling
viewports reach the panel edges and separators, with padding inside their content.
Tab faces use the opaque popup palette so scrolling text cannot show through
their labels; only the content receives the alpha fade.
The preview fixtures use 12 px above and between tabs, 4 px between section
titles and descriptions, and 16 px between groups of controls.
Each section has a capture at the top. Sections with vertical overflow also have
`*-bottom.png` captures at the end of their scroll range. The helper detects
overflow before capturing a bottom view, removes obsolete bottom captures and
restores the top before changing tabs.
Alerts has an additional expanded `*-alerts-advanced.png` capture and its scroll
views. When the top and bottom views leave a gap beneath the fixed tabs, the
helper adds a `*-middle.png` capture so the full content remains reviewable.
Advanced, Providers and Guide have bottom views in both renderers. Guide also
has a middle view on Windows. General, Appearance, collapsed Alerts and About
fit without vertical scrolling in these fixtures.

- `quickshell-*.png` uses Qt Quick Test with Mesa/OpenGL on a temporary Xvfb
  display, including the production alpha fade beneath the fixed tabs, and the
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
  desktop capture. Checkboxes and selectors share the idle outline color,
  navigation links place their arrows at the right, and the General startup
  option uses a switch beside its label.

The macOS native smoke test also captures `settings-general.png`,
`settings-appearance.png`, `settings-alerts.png`, `settings-providers.png`,
`settings-guide.png`, `settings-about.png` and `settings-alerts-advanced.png`.
The `macos-native` job in `.github/workflows/ci.yml` runs that capture on
`macos-14` and uploads it in the `macos-panel-preview` artifact. The Linux
renderers used here do not validate the native macOS layout.

To regenerate the Quickshell previews with Qt 6 Quick Test, Mesa and Xvfb:

```sh
xvfb-run -a python3 packages/lib/tests/render_settings_previews.py --platform quickshell --qml-renderer opengl
```

Set `QMLTESTRUNNER` when the executable is outside the standard Qt 6 location.
The renderer inherits Qt library, plugin and import paths from the environment.
The default `--qml-renderer software` also renders the pages without an X display;
the software fallback clips scrolling content without the OpenGL alpha fade.
To regenerate the Windows adapter previews, install
`packages/lib/windows/requirements.txt` in the Python environment and run:

```sh
python packages/lib/tests/render_settings_previews.py --platform windows
```

Both commands default to this directory; `--output` chooses another destination.
Provider logos come from the bundled assets. See the
[artwork and licenses](../../../packages/lib/assets/README.md).
