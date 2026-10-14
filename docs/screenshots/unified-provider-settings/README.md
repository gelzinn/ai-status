# Unified provider settings previews

These captures use the production Quickshell and Qt settings views with
isolated sample accounts. They show Providers combining active connections,
per-limit bar checkboxes and a separate ordered list of displayed items.
General contains refresh and appearance controls. No real provider account is
queried, and the capture commands do not change the user's preferences.

## Quickshell

Run from the repository root with the system Qt Quick Test runner installed:

```bash
python3 packages/lib/tests/render_unified_providers_qml.py
```

The helper uses the normal 380 × 680 panel, bundled fonts and logos, the
production snapshot builder and `BarWidget`, plus the isolated daemon and
Omarchy theme fixtures used by the QML tests. Its assertions check that the
first, middle and last selected rows are visible, moves preserve complete
identities, provider order stays unchanged, and the settings draft does not
mutate the saved snapshot.

| Capture | What it shows |
| --- | --- |
| `linux-providers.png` | All three selected items and their reorder/remove controls |
| `linux-providers-reordered.png` | The last selected item moved to first with two up-arrow clicks |
| `linux-providers-bottom.png` | Lower provider cards: active Kiro with no displayed limit, and inactive Cursor |
| `linux-general.png` | Refresh and appearance without duplicate provider/bar selection controls |
| `linux-bar-before.png` / `linux-bar-after.png` | Production bar rendering of the original and reordered selections |

The bar snapshots use these identities, all at account index `0`:

| Position | Before | After |
| --- | --- | --- |
| First | `codex / weekly` | `claude / weekly` |
| Middle | `claude / rolling` | `codex / weekly` |
| Last | `claude / weekly` | `claude / rolling` |

The offscreen Omarchy fixtures demonstrate the production plugin layout;
they do not replace a smoke test in an installed Omarchy shell.

## Windows Qt panel

With the desktop PySide6 requirements installed:

```bash
python3 packages/lib/tests/render_unified_providers_preview.py \
  --output docs/screenshots/unified-provider-settings
```

`windows-providers.png` starts with the same three selections as the Linux
preview. `windows-reorder-middle.png`, `windows-reorder-last.png` and
`windows-reorder-first.png` capture moves of the middle, last and first items,
ending in `claude / weekly`, `claude / rolling`, `codex / weekly` order.
`windows-provider-limits.png` shows inline per-limit selection;
`windows-provider-bottom.png` shows active Copilot with no displayed limit and
inactive Kiro. `windows-general.png` shows refresh and appearance controls.

These captures render the production Qt panel offscreen with the Fusion style
and Windows options enabled. They validate its controls, not the native
Windows notification area. Windows controls actual tray icon positions and
visibility even though AI Status saves and processes the selected item order.

## Native macOS

The macOS captures come from CI run
[38515524626](https://github.com/gelzinn/ai-status/actions/runs/38515524626),
artifact `macos-panel-preview`, built from commit `aaf626a`. The native
production build, runtime checks and developer smoke fixtures passed on
macOS 14. The fixture version label is sample data.

`macos-providers.png` shows Claude weekly → Codex weekly → Claude rolling;
`macos-providers-reordered.png` shows Claude rolling → Claude weekly → Codex
weekly. All three rows are visible. `macos-provider-limits.png` and
`macos-providers-bottom.png` show inline provider controls further down;
`macos-providers-unavailable.png` retains unavailable/deleted selections for
review and removal. `macos-general.png` contains refresh and appearance.

To reproduce on macOS, build the separate developer smoke app with
`AI_STATUS_SMOKE` and run its executable with
`--smoke --preview-directory /tmp/ai-status-providers-preview`, following the
commands in `.github/workflows/ci.yml` under `macos-native`. CI also verifies
that production artifacts omit the developer fixtures.
