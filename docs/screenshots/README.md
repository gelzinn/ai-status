# README interface previews

The desktop panel PNGs render the production AI Status UI at version 0.10.0
with sample Codex and Claude usage. Those renders contain no account credentials
or live usage data. The Waybar capture is retained from the original README.

- `windows-usage.png` and `windows-settings.png` use the native Qt widget adapter
  under an offscreen renderer, with the Windows settings option enabled.
- `omarchy-usage.png`, `omarchy-settings.png` and `reset-credits.png` use the
  production QML pages with the existing test daemon and dark Omarchy theme
  fixtures from `packages/lib/tests/qml/`.

`waybar-tooltip.png` is the unchanged public screenshot previously hosted at
`https://github.com/user-attachments/assets/dcba0b97-d462-452e-b1b6-000cc445b803`.

The README labels the rendered desktop panels as sample-data views. The Omarchy theme and platform
window behavior on a running desktop can differ from the fixtures.

Provider logos, app artwork and fonts come from the bundled assets. See
[artwork and licenses](../../packages/lib/assets/README.md).
