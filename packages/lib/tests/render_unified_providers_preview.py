"""Capture production Qt provider settings with isolated example accounts."""

import argparse
import copy
import os
from pathlib import Path
import sys
from unittest.mock import patch


def render(output):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    library = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(library / "src"), str(library / "tests")]
    from PySide6.QtTest import QTest
    from core import config, paths, state, tray
    from render_bar_items_previews import DATA, ITEMS, SELECTED
    from test_tray import DesktopTests

    output.mkdir(parents=True, exist_ok=True)
    DesktopTests.setUpClass()
    case = DesktopTests()
    case.setUp()
    try:
        case.app.setStyle("Fusion")
        case.app.setFont(tray.panel_font())
        config.save_config(["codex", "claude", "copilot"])
        state.save_selected(copy.deepcopy(SELECTED))
        panel = case.dashboard
        panel.selected = state.load_selected()
        panel.data = {name: [entry for entry in copy.deepcopy(DATA) if entry["_dir"] == name]
                      for name in ("codex", "claude")}
        panel.data["copilot"] = [{"provider": "Copilot", "metrics": [{"type": "monthly", "percentage": 17}]}]
        with patch.object(config, "available_connections", return_value=["codex", "claude", "copilot", "kiro"]), \
             patch.object(tray.QSystemTrayIcon, "show"), \
             patch.object(paths, "IS_WINDOWS", True), \
             patch.object(tray, "startup_enabled", return_value=False), \
             patch.object(panel, "isActiveWindow", return_value=True), \
             patch.object(panel, "refresh") as refresh:
            panel.draw()
            panel.show()
            panel.configure()
            settings = panel.settings_view
            settings.select_section("providers")
            panel.settings_scroll.verticalScrollBar().setValue(0)
            QTest.qWait(150)
            assert settings.bar_selections == ITEMS
            assert panel.grab().save(str(output / "windows-providers.png"))

            # Move a middle selection before the first, then the last into the
            # middle, using production controls; capture all three positions.
            for name, index, direction in (("windows-reorder-middle", 1, -1),
                                           ("windows-reorder-last", 2, -1),
                                           ("windows-reorder-first", 0, 1)):
                row = settings.bar_order.item(index)
                button = next(control for control in settings.bar_order.itemWidget(row).findChildren(tray.ControlButton)
                              if control.property("orderDirection") == direction)
                QTest.mouseClick(button, tray.Qt.MouseButton.LeftButton)
                QTest.qWait(80)
                assert panel.grab().save(str(output / (name + ".png")))
            assert settings.bar_selections == [ITEMS[2], ITEMS[1], ITEMS[0]]
            assert config.enabled_order() == ["codex", "claude", "copilot"]
            assert all(not choice.checkbox.isChecked() for choice in settings.bar_items.items
                       if choice.identity[0] == "copilot")

            panel.settings_scroll.ensureWidgetVisible(settings.providers.itemWidget(settings.providers.item(1)))
            QTest.qWait(80)
            assert panel.grab().save(str(output / "windows-provider-limits.png"))
            panel.settings_scroll.verticalScrollBar().setValue(panel.settings_scroll.verticalScrollBar().maximum())
            QTest.qWait(80)
            assert panel.grab().save(str(output / "windows-provider-bottom.png"))
            settings.select_section("general")
            QTest.qWait(80)
            assert panel.grab().save(str(output / "windows-general.png"))
            refresh.assert_not_called()
            print("Saved production Qt settings previews to", output)
            panel.hide()
            panel.hide_trays()
    finally:
        case.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    render(parser.parse_args().output.resolve())
