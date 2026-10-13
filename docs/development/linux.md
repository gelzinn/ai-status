# Linux development

A local development install clones the checkout's committed HEAD; uncommitted QML edits must be tested in a user-owned plugin copy instead.

## Development validation

```bash
python3 -m unittest discover -s packages/lib/tests -v
python3 packages/lib/tests/run_qml_tests.py
omarchy plugin validate ~/.config/omarchy/plugins/io.github.gelzinn.ai-status
qmllint -I "$OMARCHY_PATH/shell" \
  ~/.config/omarchy/plugins/io.github.gelzinn.ai-status/packages/lib/quickshell/*.qml
omarchy-shell shell summon io.github.gelzinn.ai-status '{}'
omarchy-shell shell hide io.github.gelzinn.ai-status
```

Validate a clean checkout/plugin folder: the Omarchy validator rejects symlinks, including those in local `node_modules`. On an Omarchy desktop, check click, Escape, repeat open/close, scroll, middle-click, configuration, themes, horizontal/vertical bars, and multiple monitors. Confirm one Python daemon across monitors and that disabling/removing the plugin stops it. Check hot reload, shell restart, backend restart, provider errors, and missing logos. Test Waybar separately with its existing modules and `ai-status revert`.

After copying QML changes into the installed plugin, run `omarchy restart shell`
before validating the updated panel: hot reload can retain older components.
Check the selected account and limit label, grouped provider list, scrolling,
Tab/Shift+Tab, Enter/Space, and Escape/Back across pages. Confirm that saved
preferences and bar placement are preserved.

Check one and several selected bar items, including two limits from one account,
two accounts for one provider, and monetary values. Verify checkbox keyboard
navigation, Save/Cancel, legacy single-item preferences, and rejection of an
empty selection. Click/scroll/middle-click must change the first item while
keeping the others without duplicates. Temporarily unavailable selections
must remain saved and return when usable data does. Check per-item loading
and used/remaining values in both Quickshell and Waybar, individual Quickshell
logos, and Waybar's single image following the first available selected item.
Ensure several labels fit or clip predictably on horizontal and vertical bars.
