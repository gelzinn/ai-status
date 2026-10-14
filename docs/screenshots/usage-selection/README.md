# Usage selection previews

These Linux captures render the production Quickshell panel with the bundled
Geist Mono font, provider logos and isolated sample usage. The shared Python
snapshot builder supplies the data; a recording model replaces backend actions.
No provider requests, credentials or installed preferences are used.

Generate them from the repository root:

```bash
python3 packages/lib/tests/render_usage_selection_previews.py \
  --output docs/screenshots/usage-selection
```

The helper requires Qt Quick Test (`qmltestrunner`, or `QMLTESTRUNNER` pointing to
it). The default software renderer supports headless capture. For OpenGL with an
available X display, pass `--qml-renderer opengl`.

| Capture | Configured bar items |
|---|---|
| `linux-single-item.png` | Codex weekly; usage clicks remain available |
| `linux-multiple-items.png` | Codex weekly, Claude rolling and Claude weekly |
| `linux-same-provider-items.png` | Claude rolling and Claude weekly |
| `linux-unavailable-item.png` | Codex weekly plus a temporarily unavailable Claude limit; only one item is currently visible in the bar |

Each multiple-item case verifies that ordinary usage rows have static text
accessibility roles, skip the tab order, and do not record a selection on mouse
or keyboard activation. The helper also checks that saved pins remain unchanged,
reset and cloud credit details still open, and the compact hint opens Providers
settings. It verifies that the hint and final credit row fit inside the viewport.

## Qt usage page

The `windows-*.png` captures render the production Windows Qt adapter on Linux
using Qt's offscreen backend, Fusion style, bundled font and provider artwork.
They show the application's controls and are not screenshots of a native
Windows desktop. The data and preferences are isolated fixtures; no providers
are contacted.

With the dependencies from `packages/lib/windows/requirements.txt` installed,
generate them from the repository root:

```bash
QT_QPA_PLATFORM=offscreen python3 packages/lib/tests/render_usage_selection_preview.py \
  --output docs/screenshots/usage-selection
```

| Capture | Interaction |
|---|---|
| `windows-single.png` | One configured bar item; provider and usage rows switch the selection |
| `windows-single-hover.png` | The same page with the pointer over the first usage row; its hover background is visible |
| `windows-multiple.png` | Codex weekly, Claude rolling and Copilot monthly; ordinary usage rows are read-only, and the hint opens Providers settings |
| `windows-multiple-hover.png` | The same pointer position as the single-item hover capture; no hover background appears |

The helper checks that single-item hover changes the image, while multiple-item
hover remains byte-identical to the resting capture. It also verifies that
clicking usage rows or provider headers and cycling metrics preserve all saved
bar items. Reset credit details remain available through their own action.
