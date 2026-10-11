# README interface previews

The desktop panel PNGs render the production AI Status interfaces
with sample Codex and Claude usage and the fixture's 0.10.0 version label.
Those renders contain no account credentials or live usage data. The Waybar
capture is retained from the original README.

- `windows-usage.png` and `windows-settings.png` use the native Qt widget adapter
  under an offscreen renderer, with the Windows settings option enabled.
- `omarchy-usage.png`, `omarchy-settings.png` and `reset-credits.png` use the
  production QML pages with the existing test daemon and dark Omarchy theme
  fixtures from `packages/lib/tests/qml/`. The panel items are captured with Qt
  Quick's OpenGL renderer in a transparent window, preserving transparency
  outside their rounded corners.
- `macos-usage.png` uses the production SwiftUI/AppKit view rendered by the
  native smoke test on `macos-14`, with the same sample usage and reset credits.
  The PNG is unchanged from the `macos-panel-preview` artifact in the
  [successful native CI run](https://github.com/gelzinn/ai-status/actions/runs/38153142733/job/114510559665)
  for commit `38b129698917394fef0a99bc917abc64bab2133d`.

All three interfaces read the same bundled `assets/panel-icons.json` geometry for
refresh, settings and navigation arrows. Header controls have transparent idle
backgrounds and show a fill only on hover. A focus outline appears when
navigating with Tab; mouse clicks and programmatic focus do not add a border.

`waybar-tooltip.png` is the unchanged public screenshot previously hosted at
`https://github.com/user-attachments/assets/dcba0b97-d462-452e-b1b6-000cc445b803`.

The README labels the rendered desktop panels as sample-data views. The Omarchy theme and platform
window behavior on a running desktop can differ from the fixtures.

Provider logos, app artwork and fonts come from the bundled assets. See
[artwork and licenses](../../packages/lib/assets/README.md).
