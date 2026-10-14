"""Capture production Qt compact provider rows and their transient limits menu."""

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
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtTest import QTest
    from core import accounts, config, paths, state, tray
    from render_bar_items_previews import DATA, ITEMS, SELECTED
    from test_tray import DesktopTests

    output.mkdir(parents=True, exist_ok=True)
    DesktopTests.setUpClass()
    case = DesktopTests()
    case.setUp()
    try:
        case.app.setStyle("Fusion")
        case.app.setFont(tray.panel_font())
        config.save_config(["codex", "claude", "copilot", "kiro"])
        accounts.save_document({"version": 1, "accounts": [
            {"id": "claude-work", "provider": "claude", "label": "Work account"}
        ]}, config.accounts_file())
        items = [*copy.deepcopy(ITEMS), {"provider": "copilot", "idx": 0, "metric": "monthly"}]
        selected = copy.deepcopy(SELECTED)
        state.set_selected_items(selected, items)
        state.save_selected(selected)
        panel = case.dashboard
        panel.selected = state.load_selected()
        panel.data = {name: [entry for entry in copy.deepcopy(DATA) if entry["_dir"] == name]
                      for name in ("codex", "claude")}
        panel.data["copilot"] = [{"provider": "Copilot", "metrics": [{"type": "monthly", "percentage": 17}]}]
        with patch.object(config, "available_connections", return_value=["codex", "claude", "copilot", "kiro", "account:claude-work", "opencode"]), \
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
            QTest.qWait(150)
            assert settings.bar_selections == items
            assert settings.providers.count() == 6
            assert not hasattr(settings, "bar_order")
            assert not settings.provider_bar_checks["kiro"].isChecked()
            assert "kiro" in settings.enabled_draft
            assert panel.grab().save(str(output / "windows-providers.png"))

            copilot = settings.providers.item(2)
            for position in range(2):
                button = next(control for control in settings.providers.itemWidget(copilot).findChildren(tray.ControlButton)
                              if control.property("orderDirection") == -1)
                QTest.mouseClick(button, tray.Qt.MouseButton.LeftButton)
                QTest.qWait(50)
                if position == 0:
                    assert panel.grab().save(str(output / "windows-providers-middle.png"))
            assert settings.bar_selections == [items[-1], *items[:-1]]
            assert panel.grab().save(str(output / "windows-providers-reordered.png"))
            assert config.enabled_order() == ["codex", "claude", "copilot", "kiro"]

            trigger = settings.findChild(tray.QPushButton, "provider-limits-claude")
            menu = trigger.menu()
            menu.popup(trigger.mapToGlobal(tray.QPoint(0, trigger.height())))
            QTest.qWait(80)
            # Both images come from live production widgets. Preserve the actual
            # popup position while allowing it to extend beyond the panel.
            offset = menu.mapToGlobal(tray.QPoint()) - panel.mapToGlobal(tray.QPoint())
            image = QImage(max(panel.width(), offset.x() + menu.width()),
                           max(panel.height(), offset.y() + menu.height()), QImage.Format.Format_ARGB32)
            image.fill(QColor("#0c0c0c"))
            painter = QPainter(image)
            painter.drawPixmap(0, 0, panel.grab())
            painter.drawPixmap(offset, menu.grab())
            painter.end()
            assert image.save(str(output / "windows-provider-limits.png"))
            menu.hide()
            settings.select_section("general")
            QTest.qWait(80)
            assert panel.grab().save(str(output / "windows-general.png"))
            refresh.assert_not_called()
            print("Saved compact production Qt settings previews to", output)
            panel.hide()
            panel.hide_trays()
    finally:
        case.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    render(parser.parse_args().output.resolve())
