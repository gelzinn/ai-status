# Linux development

A local development install clones the checkout's committed HEAD; uncommitted QML edits must be tested in a user-owned plugin copy instead.

## Development validation

```bash
python3 -m unittest discover -s packages/lib/tests -v
omarchy plugin validate ~/.config/omarchy/plugins/io.github.gelzinn.ai-status
qmllint -I "$OMARCHY_PATH/shell" \
  ~/.config/omarchy/plugins/io.github.gelzinn.ai-status/packages/lib/quickshell/*.qml
omarchy-shell shell summon io.github.gelzinn.ai-status '{}'
omarchy-shell shell hide io.github.gelzinn.ai-status
```

Validate a clean checkout/plugin folder: the Omarchy validator rejects symlinks, including those in local `node_modules`. On an Omarchy desktop, check click, Escape, repeat open/close, scroll, middle-click, configuration, themes, horizontal/vertical bars, and multiple monitors. Confirm one Python daemon across monitors and that disabling/removing the plugin stops it. Check hot reload, shell restart, backend restart, provider errors, and missing logos. Test Waybar separately with its existing modules and `ai-status revert`.
