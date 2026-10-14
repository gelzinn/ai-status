"""Capture the production Qt usage page with one or several configured bar items.

These previews render the Windows Qt adapter through Qt's offscreen backend;
they do not include native Windows desktop chrome or contact any providers.
"""

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
    from core import config, state, tray
    from render_bar_items_previews import DATA, SELECTED
    from test_tray import DesktopTests

    output.mkdir(parents=True, exist_ok=True)
    DesktopTests.setUpClass()
    case = DesktopTests()
    case.setUp()
    try:
        case.app.setStyle("Fusion")
        case.app.setFont(tray.panel_font())
        config.save_config(["codex", "claude", "copilot"])
        panel = case.dashboard
        panel.data = {name: [entry for entry in copy.deepcopy(DATA) if entry["_dir"] == name]
                      for name in ("codex", "claude")}
        panel.data["codex"][0]["reset_credits"] = {"available": 3}
        panel.data["claude"][0]["metrics"] = panel.data["claude"][0]["metrics"][:2]
        panel.data["copilot"] = [{"provider": "Copilot", "metrics": [
            {"type": "monthly", "percentage": 17, "reset_in_seconds": 1209600}]}]
        pins = [{"provider": "codex", "idx": 0, "metric": "weekly"},
                {"provider": "claude", "idx": 0, "metric": "rolling"},
                {"provider": "copilot", "idx": 0, "metric": "monthly"}]
        with patch.object(tray.QSystemTrayIcon, "show"), \
             patch.object(panel, "isActiveWindow", return_value=True), \
             patch.object(panel, "refresh") as refresh, \
             patch.object(tray.fetch, "get_version_info", return_value={"has_update": False}):
            for multiple, name in ((False, "single"), (True, "multiple")):
                selected = copy.deepcopy(SELECTED)
                state.set_selected_items(selected, pins if multiple else pins[:1])
                state.save_selected(selected)
                panel.selected = state.load_selected()
                panel.draw()
                panel.show()
                QTest.mouseMove(panel, tray.QPoint(1, 1))
                QTest.qWait(2100)
                row = panel.metric_buttons[0]
                assert row.property("interactive") is not multiple
                assert panel.bar_items_link.isHidden() is not multiple
                normal = panel.grab()
                assert normal.save(str(output / f"windows-{name}.png"))
                QTest.mouseMove(row, row.rect().center())
                QTest.qWait(100)
                hovered = panel.grab()
                assert hovered.save(str(output / f"windows-{name}-hover.png"))
                assert (normal.toImage() == hovered.toImage()) is multiple
                if multiple:
                    before = state.load_selected()
                    row.click()
                    panel.provider_buttons[("claude", 0)].click()
                    panel.cycle_metric(1)
                    assert state.load_selected() == before
            refresh.assert_not_called()
            panel.hide()
            panel.hide_trays()
            print("Saved production Qt usage selection previews to", output)
    finally:
        case.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    render(parser.parse_args().output.resolve())
