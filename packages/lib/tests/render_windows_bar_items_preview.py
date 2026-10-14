"""Render Windows Settings and an honest Qt preview of selected tray icons.

The Settings image uses the production widget. The tray image is a code-native
preview of the production QSystemTrayIcon artwork and tooltip text, rendered
offscreen without claiming to capture a Windows desktop.
"""

import argparse
import copy
import os
from pathlib import Path
import sys
from unittest.mock import patch


LIB = Path(__file__).resolve().parents[1]
PROJECT = LIB.parents[1]


def render(output):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(LIB / "src"))
    sys.path.insert(0, str(LIB / "tests"))
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
    from core import config, paths, state, tray
    from render_bar_items_previews import DATA, ITEMS, SELECTED
    from test_tray import DesktopTests

    class NotificationArea(QWidget):
        """A Windows-style strip; every application icon comes from the adapter."""

        def __init__(self, icons):
            super().__init__()
            self.icons = icons
            self.setFixedWidth(330)
            self.setFixedHeight(54)

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#454545"), 1))
            painter.setBrush(QColor("#252525"))
            painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 7, 7)
            painter.setPen(QPen(QColor("#eeeeee"), 1.4))
            painter.drawPolyline(QPolygonF([QPointF(20, 29), QPointF(25, 24), QPointF(30, 29)]))
            for index, icon in enumerate(self.icons):
                icon.icon().paint(painter, 52 + index * 42, 15, 24, 24)
            painter.setPen(QColor("#eeeeee"))
            font = tray.panel_font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(QRectF(self.width() - 126, 7, 106, 19), Qt.AlignmentFlag.AlignRight, "15:00")
            painter.drawText(QRectF(self.width() - 126, 28, 106, 19), Qt.AlignmentFlag.AlignRight, "10/13/2026")

    def tooltip_card(icon):
        card = QFrame()
        card.setStyleSheet("QFrame { background: #171717; border: 1px solid #464646; border-radius: 5px; }")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(icon.icon().pixmap(20, 20))
        logo.setStyleSheet("border: 0; background: transparent;")
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        text = QLabel(icon.toolTip())
        text.setTextFormat(Qt.TextFormat.PlainText)
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setStyleSheet("color: #eeeeee; border: 0; background: transparent;")
        layout.addWidget(text)
        return card

    DesktopTests.setUpClass()
    case = DesktopTests()
    case.setUp()
    try:
        case.app.setStyle("Fusion")
        case.app.setFont(tray.panel_font())
        config.save_config(["codex", "claude"])
        state.save_selected(copy.deepcopy(SELECTED))
        panel = case.dashboard
        panel.selected = state.load_selected()
        panel.data = {name: [entry for entry in copy.deepcopy(DATA) if entry["_dir"] == name]
                      for name in ("codex", "claude")}
        with patch.object(tray.QSystemTrayIcon, "show"), \
             patch.object(paths, "IS_WINDOWS", True), \
             patch.object(tray, "startup_enabled", return_value=False), \
             patch.object(panel, "isActiveWindow", return_value=True), \
             patch.object(panel, "refresh") as refresh:
            panel.draw()
            icons = [panel.tray] + [panel.metric_trays[tuple(item[key] for key in ("provider", "idx", "metric"))]
                                   for item in ITEMS[1:]]
            assert len(icons) == 3
            assert all(tray.icon_has_pixels(icon.icon()) for icon in icons)
            assert all(value in icon.toolTip() for value, icon in zip(("27%", "45%", "62%"), icons))
            panel.show()
            panel.configure()
            panel.settings_view.select_section("providers")
            panel.settings_scroll.verticalScrollBar().setValue(0)
            QTest.qWait(150)
            assert panel.settings_view.bar_selections == ITEMS
            assert panel.grab().save(str(output / "windows-settings.png"))

            preview = QWidget()
            preview.setWindowTitle("Windows tray · Qt-rendered preview")
            preview.setFont(tray.panel_font())
            preview.setStyleSheet("background: #111111;")
            layout = QVBoxLayout(preview)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(12)
            heading = QLabel("Windows tray · Qt-rendered preview")
            heading.setStyleSheet("color: #eeeeee; font-size: 14px; font-weight: 500;")
            layout.addWidget(heading)
            layout.addWidget(NotificationArea(icons), alignment=Qt.AlignmentFlag.AlignRight)
            caption = QLabel("Tooltip samples for the three selected icons")
            caption.setStyleSheet("color: #aaaaaa; font-size: 11px;")
            layout.addWidget(caption)
            cards = QHBoxLayout()
            cards.setSpacing(10)
            for icon in icons:
                cards.addWidget(tooltip_card(icon), 1)
            layout.addLayout(cards)
            preview.resize(640, 236)
            preview.show()
            QTest.qWait(100)
            assert preview.grab().save(str(output / "windows-tray.png"))
            print("Tray tooltips:")
            for icon in icons:
                print(icon.toolTip())
            print("Saved Windows production Settings and Qt-rendered tray preview to", output)
            refresh.assert_not_called()
            preview.close()
            panel.hide()
            panel.hide_trays()
    finally:
        case.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/screenshots/multiple-bar-items")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    render(output)


if __name__ == "__main__":
    main()
