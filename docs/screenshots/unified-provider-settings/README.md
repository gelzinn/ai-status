# Unified provider settings previews

These captures use the production settings views with isolated sample
accounts. Providers has one compact row per connection: Active, provider name,
Show in bar and up/down controls. A provider can be active without being
displayed. One order drives both Usage and bar selections. Clicking the name
opens a temporary limits menu; there is no second persistent list. General
contains refresh and appearance. Capture commands do not query real provider
accounts or change the user's preferences.

## Quickshell

Run from the repository root with the system Qt Quick Test runner installed:

```bash
python3 packages/lib/tests/render_unified_providers_qml.py
```

The helper uses a fixed 380 × 680 panel viewport, bundled fonts and logos, the
production snapshot builder and `BarWidget`, plus the isolated daemon and
Omarchy theme fixtures used by the QML tests. Its nine connection rows include
an additional account, an active provider with no bar items and inactive
providers. Assertions check that first, middle and last provider rows are
visible, moving a provider moves its selected limits together while retaining
their identities/order, and the draft does not mutate the saved snapshot.

| Capture | What it shows |
| --- | --- |
| `linux-providers.png` | One compact provider list, including active-hidden Kiro and inactive Cursor |
| `linux-providers-reordered.png` | Claude moved before Codex with one provider up-arrow click |
| `linux-provider-limits.png` | Temporary Claude limits menu showing selected and unselected metrics |
| `linux-general.png` | Refresh and appearance without duplicate provider/bar selection controls |
| `linux-bar-before.png` / `linux-bar-after.png` | Production bar rendering of the original and reordered selections |

The bar snapshots use these identities, all at account index `0`:

| Position | Before | After |
| --- | --- | --- |
| First | `codex / weekly` | `claude / rolling` |
| Middle | `claude / rolling` | `claude / weekly` |
| Last | `claude / weekly` | `codex / weekly` |

The offscreen Omarchy fixtures demonstrate the production plugin layout;
they do not replace a smoke test in an installed Omarchy shell.

## Windows Qt panel

With the desktop PySide6 requirements installed:

```bash
python3 packages/lib/tests/render_unified_providers_preview.py \
  --output docs/screenshots/unified-provider-settings
```

`windows-providers.png` shows the compact provider rows, including displayed,
active-hidden and inactive providers. The selected providers start as Codex,
Claude, Copilot; `windows-providers-middle.png` moves Copilot to the middle,
and `windows-providers-reordered.png` moves it to first. Their selected limits
move together in the shared Usage/bar order.
`windows-provider-limits.png` shows the temporary per-limit menu;
`windows-general.png` shows refresh and appearance controls.

These captures render the production Qt panel offscreen with the Fusion style
and Windows options enabled. They validate its controls, not the native
Windows notification area. Windows controls actual tray icon positions and
visibility even though AI Status saves and processes the selected item order.
