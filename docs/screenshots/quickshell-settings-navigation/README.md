# Quickshell settings and navigation previews

These PNGs render the production QML components with the test daemon, an
offscreen Qt Quick renderer, and the dark shell fixtures from
`packages/lib/tests/qml/`. They contain simulated usage and account labels.
The displayed version is 0.12.1; the fixture uses `Style.cornerRadius: 0`.
On a running Omarchy desktop, the shell supplies the corner radius and font.

- `01-selected.png`: compact selected account and limit, with six enabled
  connections across Codex, Claude, Cursor, Kiro, and OpenRouter.
- `02-providers-accounts.png`: grouped limits, including Personal and Work
  Claude accounts.
- `03-cursor.png`: concise Cursor quota and spend labels.
- `04-more-providers.png`: the remaining groups after scrolling the menu.
- `05-links.png`: About links with the shared shell corner radius.
- `02-tab-reveals-command-code.png`: Tab brings a previously clipped provider
  control fully into view while the header and footer stay fixed.
- `resets-available.png`: four sample reset credits, with the aligned header
  icons and the current availability footer and timezone presentation.

Provider logos and app artwork come from the bundled assets. See the
[artwork and licenses](../../../packages/lib/assets/README.md).
