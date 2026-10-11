"""Desktop adapter. The Waybar daemon and CLI do not import Qt."""
import logging
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from PySide6.QtCore import QEasingCurve, QEvent, QModelIndex, QObject, QPoint, QPointF, QRectF, QLockFile, QThread, QTimer, Qt, QUrl, Signal, QSize, QVariantAnimation
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMenu,
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem, QStackedWidget, QStyledItemDelegate, QStyle,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import __version__, about, config, fetch, paths, render, reset_credits, state, updates

RELEASE_URL = "https://github.com/gelzinn/ai-status/releases/latest"
ASSETS = paths.LIB_DIR / "assets"
_font_family = None
PROVIDERS = paths.read_json(ASSETS / "providers.json") or paths.read_json(
    paths.LIB_DIR.parent / "shared/providers/providers.json")


def provider_name(key):
    info = config.connection_info(key) or {"provider": key, "label": key}
    name = PROVIDERS.get(info["provider"], {}).get("name", key)
    return name + (" · " + info["label"] if key.startswith("account:") else "")

# Colors, spacing and typography match the landing page's WaybarReplica.
PANEL_STYLE = """
QWidget { color: #888888; background: transparent; font-family: "Geist Mono"; font-size: 13px; }
QDialog { background: #111111; }
QWidget#panel { background: #111111; border: 1px solid #262626; border-radius: 12px; }
QWidget#header { border-bottom: 1px solid #202020; }
QLabel { background: transparent; border: none; }
QLabel#brand { color: #eeeeee; font-weight: 500; }
QAbstractButton { border: none; background: transparent; text-align: left; }
QAbstractButton:hover, QAbstractButton:focus { background: #1c1c1c; border-radius: 8px; }
QAbstractButton#updateLink:hover, QAbstractButton#updateLink:focus { background: #15283d; border-radius: 8px; }
QWidget#creditTable { border: 1px solid #262626; border-radius: 8px; }
QWidget#creditTableHeader {
    background: rgba(255, 255, 255, 10);
    border-top-left-radius: 7px; border-top-right-radius: 7px;
}
QWidget#creditRow { border-top: 1px solid #262626; }
QWidget#creditTableFooter {
    background: rgba(255, 255, 255, 10); border-top: 1px solid #262626;
    border-bottom-left-radius: 7px; border-bottom-right-radius: 7px;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 6px 0; }
QScrollBar::handle:vertical { background: #303030; border-radius: 2px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QPushButton { padding: 6px 8px; }
QAbstractButton#control, QAbstractButton#control:hover, QAbstractButton#control:focus {
    padding: 0; border: none; background: transparent; border-radius: 6px;
}
QMenu { background: #111111; border: 1px solid #262626; border-radius: 10px; padding: 6px; }
QMenu::item { color: #888888; padding: 8px 12px; margin: 1px 0; border-radius: 6px; }
QMenu::item:selected { background: #1c1c1c; color: #eeeeee; }
QMenu::item:disabled { color: #555555; background: transparent; }
QMenu::separator { height: 1px; background: #262626; margin: 6px; }
"""


def panel_font():
    global _font_family
    if _font_family is None:
        _font_family = "Consolas"
        for filename in ("GeistMono-Regular.ttf", "GeistMono-Medium.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(ASSETS / "fonts" / filename))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _font_family = families[0]
    font = QFont(_font_family)
    font.setPixelSize(13)
    return font


@lru_cache(maxsize=16)
def asset_icon(filename):
    """Bundled raster artwork works offline and does not require QtSvg plugins."""
    return QIcon(str(ASSETS / filename))


def provider_icon(name):
    name = (config.connection_info(name) or {}).get("provider", name)
    filename = f"providers/{name}.png"
    if (ASSETS / filename).is_file():
        return asset_icon(filename)
    return status_icon()


def icon_has_pixels(icon):
    image = icon.pixmap(32, 32).toImage()
    return not image.isNull() and any(image.pixelColor(x, y).alpha() for y in range(image.height()) for x in range(image.width()))


def startup_enabled():
    if not paths.IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            return bool(winreg.QueryValueEx(key, "AI Status")[0])
    except OSError:
        return False


def set_startup(enabled):
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        if enabled:
            if getattr(sys, "frozen", False):
                args = [str(Path(sys.executable).with_name("ai-status.exe")), "tray"]
            else:
                args = [sys.executable, str(paths.LIB_DIR / "src/windows.py"), "tray"]
            winreg.SetValueEx(key, "AI Status", 0, winreg.REG_SZ, subprocess.list2cmdline(args))
        else:
            try:
                winreg.DeleteValue(key, "AI Status")
            except FileNotFoundError:
                pass


def status_icon():
    return asset_icon("app.png")


class UsageButton(QAbstractButton):
    """A focusable, clickable provider/metric row, without native button chrome."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        # Let Qt draw the stylesheet background while child labels draw content.
        from PySide6.QtWidgets import QStyle, QStyleOption, QStylePainter
        option = QStyleOption()
        option.initFrom(self)
        painter = QStylePainter(self)
        painter.drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option)

    def sizeHint(self):
        return self.layout().sizeHint() if self.layout() else QSize(32, 32)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)


class UsageBar(QWidget):
    """Stable raster bar with the preview's shimmer and staggered fill animation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(15)
        self.active = False
        self.loading = False
        self.target = 0.0
        self.displayed = 0.0
        self.opacity = 1.0
        self.mounted = False
        self.delay = 100
        self.phase = 0.0
        self.fill = QVariantAnimation(self)
        self.fill.setDuration(1500)
        easing = QEasingCurve(QEasingCurve.Type.BezierSpline)
        easing.addCubicBezierSegment(QPointF(0.16, 1), QPointF(0.3, 1), QPointF(1, 1))
        self.fill.setEasingCurve(easing)
        self.fill.setStartValue(0.0)
        self.fill.setEndValue(1.0)
        self.fill.valueChanged.connect(self.advance_fill)
        self.start_delay = QTimer(self)
        self.start_delay.setSingleShot(True)
        self.start_delay.timeout.connect(self.start_fill)
        self.shimmer = QVariantAnimation(self)
        self.shimmer.setDuration(1500)
        self.shimmer.setLoopCount(-1)
        self.shimmer.setStartValue(0.0)
        self.shimmer.setEndValue(1.0)
        self.shimmer.valueChanged.connect(self.advance_shimmer)

    def sizeHint(self):
        return QSize(200, 15)

    def minimumSizeHint(self):
        return QSize(48, 15)

    def set_usage(self, percentage, active, loading, group_index=0):
        target = max(0.0, min(100.0, float(percentage)))
        changed = target != self.target or loading != self.loading
        was_loading = self.loading
        self.active = active
        self.target = target
        self.loading = loading
        self.delay = 100 + group_index * 150
        if loading:
            self.start_delay.stop()
            self.fill.stop()
            self.opacity = 0.0
            if not was_loading and self.isVisible():
                self.shimmer.start()
        else:
            self.shimmer.stop()
            if self.isVisible() and (changed or not self.mounted):
                self.schedule_fill()
        self.update()

    def schedule_fill(self):
        if self.mounted:
            self.start_fill()
        elif not self.start_delay.isActive():
            self.start_delay.start(self.delay)

    def start_fill(self):
        if self.loading or not self.isVisible():
            return
        self.fill.stop()
        self.fill_from = self.displayed
        self.opacity_from = self.opacity
        self.mounted = True
        self.fill.start()

    def advance_fill(self, progress):
        self.displayed = self.fill_from + (self.target - self.fill_from) * progress
        self.opacity = self.opacity_from + (1.0 - self.opacity_from) * progress
        self.update()

    def advance_shimmer(self, phase):
        self.phase = phase
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self.loading:
            self.shimmer.start()
        elif not self.mounted or self.displayed != self.target:
            self.schedule_fill()

    def hideEvent(self, event):
        self.start_delay.stop()
        self.fill.stop()
        self.shimmer.stop()
        if self.mounted:
            self.displayed = self.target
            self.opacity = 1.0
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QColor("#222222"))
        painter.setBrush(QColor("#1b1b1b" if self.loading else "#141414"))
        painter.drawRoundedRect(frame, 1, 1)
        inner = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(inner, 1, 1)
        painter.setClipPath(clip)
        if self.loading:
            offset = (2 * self.phase - 1) * inner.width()
            gradient = QLinearGradient(inner.left() + offset, 0, inner.right() + offset, 0)
            gradient.setColorAt(0, QColor(255, 255, 255, 0))
            gradient.setColorAt(0.5, QColor(255, 255, 255, 38))
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            painter.fillRect(inner, gradient)
        else:
            color = QColor("#eeeeee" if self.active else "#555555")
            color.setAlphaF(self.opacity)
            inner.setWidth(inner.width() * self.displayed / 100)
            painter.fillRect(inner, color)


def plain_label(text, color=None):
    label = QLabel(str(text))
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    if color:
        label.setStyleSheet(f"color: {color};")
    return label


class ArrowIcon(QWidget):
    """A centered arrow drawn without a font glyph or an extra SVG dependency."""
    def __init__(self, back=False, color="#aaaaaa"):
        super().__init__()
        self.back = back
        self.color = color
        size = panel_icons()["size"]
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        draw_control_icon(painter, QRectF(self.rect()), "arrow-left" if self.back else "arrow-right", self.color)


class ResetCreditsView(QWidget):
    """Provider-specific reset information inside the existing usage panel."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(18)
        self.heading = QWidget()
        row = QHBoxLayout(self.heading)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.logo = plain_label("")
        self.logo.setFixedSize(16, 16)
        row.addWidget(self.logo)
        self.provider_label = plain_label("", "#eeeeee")
        row.addWidget(self.provider_label, 1)
        layout.addWidget(self.heading)
        self.cached_label = plain_label("Cached data", "#666666")
        layout.addWidget(self.cached_label)
        intro = QVBoxLayout()
        intro.setSpacing(8)
        title = plain_label("Usage limit resets", "#eeeeee")
        title.setStyleSheet(title.styleSheet() + "font-weight: 500;")
        intro.addWidget(title)
        self.explanation = plain_label("")
        self.explanation.setWordWrap(True)
        intro.addWidget(self.explanation)
        layout.addLayout(intro)
        self.table = QWidget()
        self.table.setObjectName("creditTable")
        table_layout = QVBoxLayout(self.table)
        table_layout.setContentsMargins(1, 1, 1, 1)
        table_layout.setSpacing(0)
        header = QWidget()
        header.setObjectName("creditTableHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 8)
        header_layout.setSpacing(12)
        for text in ("Reset type", "Expires"):
            label = self.secondary_label(text)
            header_layout.addWidget(label, 1)
        table_layout.addWidget(header)
        self.rows_widget = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        table_layout.addWidget(self.rows_widget)
        self.total_footer = QWidget()
        self.total_footer.setObjectName("creditTableFooter")
        footer_layout = QHBoxLayout(self.total_footer)
        footer_layout.setContentsMargins(12, 12, 12, 12)
        footer_layout.setSpacing(12)
        self.available_label = plain_label("Available resets", "#888888")
        self.available_label.setWordWrap(True)
        footer_layout.addWidget(self.available_label, 1)
        self.available = plain_label("", "#eeeeee")
        self.available.setStyleSheet(self.available.styleSheet() + "font-weight: 500;")
        self.available.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer_layout.addWidget(self.available)
        table_layout.addWidget(self.total_footer)
        layout.addWidget(self.table)
        self.timezone_note = self.secondary_label("")
        self.timezone_note.setWordWrap(True)
        layout.addWidget(self.timezone_note)
        self.empty = plain_label("No reset credits available.")
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        self.notice = self.secondary_label("")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        layout.addStretch()
        self.rows = []
        self.signature = None

    @staticmethod
    def secondary_label(text):
        label = plain_label(text)
        label.setStyleSheet("color: #777777; font-size: 11px;")
        return label

    def update_provider(self, name, entry, label):
        self.provider_label.setText(label)
        self.logo.setPixmap(provider_icon(name).pixmap(16, 16))
        self.heading.setAccessibleName(label)
        self.explanation.setText(
            "Restore your 5-hour or weekly limit,\nor both, depending on the reset type."
            if name == "codex" else
            "Restore eligible usage limits.\nCredits expire on the dates below.")
        self.cached_label.setVisible(bool(entry.get("_cached")))
        self.cached_label.setToolTip(entry.get("_error", "Unable to refresh"))
        data = reset_credits.available_credits(entry.get("reset_credits"))
        self.available.setText(str(data["available"]))
        self.table.setVisible(bool(data["available"]))
        timezone_note = reset_credits.local_timezone_summary(
            item["expires_at"] for item in data["credits"] if item["expires_at"])
        self.timezone_note.setText(timezone_note)
        self.timezone_note.setVisible(bool(data["available"] and timezone_note))
        self.empty.setVisible(not data["available"])
        self.notice.setText("Some reset details haven't been provided yet." if data["undetailed"] else "")
        self.notice.setVisible(bool(data["undetailed"]))
        credits = data["credits"] + ([{"title": "Reset credit", "count": data["undetailed"], "expires_at": None}]
                                     if data["undetailed"] else [])
        signature = tuple((item["title"], item["count"], item["expires_at"]) for item in credits)
        if signature != self.signature:
            self.signature = signature
            while self.rows_layout.count():
                previous = self.rows_layout.takeAt(0).widget()
                previous.hide()
                previous.deleteLater()
            self.rows = []
            for item in credits:
                row = QWidget()
                row.setObjectName("creditRow")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(12, 12, 12, 12)
                row_layout.setSpacing(12)
                cells = []
                for _ in range(2):
                    cell = QVBoxLayout()
                    cell.setSpacing(5)
                    primary = plain_label("", "#dddddd")
                    primary.setWordWrap(True)
                    secondary = self.secondary_label("")
                    secondary.setWordWrap(True)
                    cell.addWidget(primary)
                    cell.addWidget(secondary)
                    cell.addStretch()
                    row_layout.addLayout(cell, 1)
                    cells.extend((primary, secondary))
                title, amount, expiry, remaining = cells
                title.setText(item["title"])
                amount.setText(f"{item['count']} {'credit' if item['count'] == 1 else 'credits'}")
                self.rows.append((expiry, remaining))
                self.rows_layout.addWidget(row)
        for item, (expiry, remaining) in zip(credits, self.rows):
            date = item["expires_at"]
            if date:
                stamp, duration = reset_credits.format_expiry(date)
                expiry.setText(stamp)
                remaining.setText(duration)
            else:
                expiry.setText("Not provided")
                remaining.setText("")
        self.rows_layout.activate()
        self.table.layout().activate()
        self.layout().invalidate()
        self.layout().activate()


class ProviderDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # The selected row provides the neutral focus indicator; avoid the
        # platform's blue rectangle drawn separately around the text.
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint(self, painter, option, index):
        label_option = type(option)(option)
        label_option.rect.adjust(0, 0, -60, 0)
        super().paint(painter, label_option, index)
        for offset, icon, enabled in ((56, "arrow-up", index.row() > 0),
                                      (28, "arrow-down", index.row() < index.model().rowCount() - 1)):
            rect = QRectF(option.rect.right() - offset, option.rect.top(), 28, option.rect.height())
            draw_control_icon(painter, rect, icon, "#aaaaaa" if enabled else "#444444")

    def editorEvent(self, event, model, option, index):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            if event.button() == Qt.MouseButton.LeftButton and event.position().x() >= option.rect.right() - 56:
                if event.type() == QEvent.Type.MouseButtonRelease:
                    direction = -1 if event.position().x() < option.rect.right() - 28 else 1
                    self.parent().move_provider(index.row(), direction)
                return True
        return super().editorEvent(event, model, option, index)


class ProviderList(QListWidget):
    """Native internal drag/drop and per-row arrows share the same draft order."""
    def __init__(self):
        super().__init__()
        self.setItemDelegate(ProviderDelegate(self))
        self.setIconSize(QSize(16, 16))
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAccessibleName("Providers; drag to reorder or use Alt+Up and Alt+Down")

    def move_provider(self, row, direction):
        other = row + direction
        if row < 0 or other < 0 or other >= self.count():
            return
        item = self.item(row)
        self.model().moveRow(QModelIndex(), row, QModelIndex(), other + (1 if direction > 0 else 0))
        self.setCurrentItem(item)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.AltModifier and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.move_provider(self.currentRow(), -1 if event.key() == Qt.Key.Key_Up else 1)
            event.accept()
        else:
            super().keyPressEvent(event)


@lru_cache(maxsize=1)
def panel_icons():
    """Geometry shared by the Quickshell, Windows and macOS panels."""
    return paths.read_json(ASSETS / "panel-icons.json")


@lru_cache(maxsize=16)
def control_icon_path(name):
    """Render bundled Lucide paths without requiring QtSvg plugins."""
    path = QPainterPath()
    for command, *points in panel_icons()["paths"][name]:
        if command == "M":
            path.moveTo(*points)
        elif command == "L":
            path.lineTo(*points)
        elif command == "C":
            path.cubicTo(*points)
        elif command == "Z":
            path.closeSubpath()
    return path


def draw_control_icon(painter, rect, name, color="#aaaaaa"):
    """Monochrome Lucide vectors; see quickshell/LUCIDE-LICENSE."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    icons = panel_icons()
    size = icons["size"]
    painter.translate(rect.center().x() - size / 2, rect.center().y() - size / 2)
    painter.scale(size / icons["viewBox"], size / icons["viewBox"])
    pen = QPen(QColor(color), icons["strokeWidth"])
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(control_icon_path(name))
    painter.restore()


class ControlButton(QAbstractButton):
    def __init__(self, name, label):
        super().__init__()
        self.icon_name = name
        self.setObjectName("control")
        size = panel_icons()["controls"]["size"]
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(label)
        self.setAccessibleName(label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.loading = False
        self.keyboard_focus_visible = False
        self.rotation = 0.0
        self.spin = QVariantAnimation(self)
        self.spin.setStartValue(0.0)
        self.spin.setEndValue(360.0)
        self.spin.setDuration(1000)
        self.spin.setLoopCount(-1)
        self.spin.valueChanged.connect(self.rotate_icon)

    def rotate_icon(self, angle):
        self.rotation = angle
        self.update()

    def set_loading(self, loading):
        self.loading = loading
        if loading and self.isVisible():
            self.spin.start()
        else:
            self.spin.stop()
            self.rotate_icon(0.0)

    def showEvent(self, event):
        super().showEvent(event)
        self.set_loading(self.loading)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.spin.stop()
        self.rotate_icon(0.0)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        self.keyboard_focus_visible = event.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)
        super().focusInEvent(event)
        self.update()

    def setFocus(self, reason=Qt.FocusReason.OtherFocusReason):
        # Qt skips focusInEvent when this control is already focused.
        self.keyboard_focus_visible = reason in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)
        super().setFocus(reason)
        self.update()

    def focusOutEvent(self, event):
        self.keyboard_focus_visible = False
        super().focusOutEvent(event)
        self.update()

    def mousePressEvent(self, event):
        self.keyboard_focus_visible = False
        super().mousePressEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        controls = panel_icons()["controls"]
        foreground = QColor("#aaaaaa" if self.isEnabled() else "#444444")
        keyboard_focus = self.isEnabled() and self.hasFocus() and self.keyboard_focus_visible
        if keyboard_focus:
            foreground = QColor("#eeeeee")
        if self.isEnabled() and self.underMouse():
            hover = QColor("white")
            hover.setAlphaF(controls["hoverOpacity"])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(hover)
            painter.drawRoundedRect(QRectF(self.rect()), controls["radius"], controls["radius"])
        if keyboard_focus:
            focus = QColor("white")
            focus.setAlphaF(controls["focusOpacity"])
            painter.setPen(QPen(focus, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                                    controls["radius"], controls["radius"])
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.rotation)
        painter.translate(-self.width() / 2, -self.height() / 2)
        draw_control_icon(painter, QRectF(self.rect()), self.icon_name, foreground)


class UsageWorker(QObject):
    result = Signal(str, object)
    error = Signal(str, str)
    finished = Signal(object)

    def __init__(self, check_updates=False):
        super().__init__()
        self.check_updates = check_updates

    def work(self):
        data = []
        try:
            data = fetch.fetch_all_data(on_result=self.result.emit, on_error=self.error.emit)
            state.save_cache(data)
            if self.check_updates:
                fetch.check_for_updates()
        except Exception:
            logging.exception("Usage refresh failed")
            for name in config.enabled_connection_order():
                self.error.emit(name, "Refresh failed; see the application log.")
        finally:
            self.finished.emit(data)


class ProviderSettings(QWidget):
    saved = Signal()
    cancelled = Signal()
    about_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dashboard = parent
        self.setFont(panel_font())
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#252525"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#eeeeee"))
        self.setPalette(palette)
        self.setStyleSheet(PANEL_STYLE + """
            QListWidget { background: transparent; border: none; }
            QListWidget::item { padding: 8px 4px; }
            QListWidget::item:selected { background: #252525; color: #eeeeee; }
            QCheckBox { padding: 5px 0; }
            QPushButton { border: 1px solid #303030; border-radius: 6px; }
            QComboBox { border: 1px solid #303030; border-radius: 6px; padding: 6px 8px; }
            QComboBox QAbstractItemView { background: #111111; selection-background-color: #252525; }
            QListWidget::indicator, QCheckBox::indicator {
                width: 16px; height: 16px; border: 1px solid #888888;
                border-radius: 4px; background: #161616;
            }
            QListWidget::indicator:checked, QCheckBox::indicator:checked {
                background: #eeeeee; border-color: #eeeeee;
                image: url(CHECKMARK);
            }
        """.replace("CHECKMARK", '"' + (ASSETS / "checkmark.png").as_posix() + '"'))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(8)
        layout.addWidget(plain_label("Active provider & limit", "#eeeeee"))
        self.active = QComboBox()
        self.active.setIconSize(QSize(16, 16))
        self.active.setAccessibleName("Active provider and limit")
        layout.addWidget(self.active)
        layout.addSpacing(14)
        layout.addWidget(plain_label("Bar display", "#eeeeee"))
        selected = state.load_selected() or {}
        self.display = {}
        for key, label, default in (("show_provider", "Provider name", True),
                                    ("show_model", "Model / plan", True),
                                    ("show_metric", "Limit name", False),
                                    ("show_pct", "Usage value", True)):
            checkbox = QCheckBox(label)
            checkbox.setChecked(selected.get(key, default))
            self.display[key] = checkbox
            layout.addWidget(checkbox)
        self.icon_mode = QComboBox()
        self.icon_mode.setAccessibleName("Bar icon")
        for value, label in (("off", "None"), ("bot", "Bot"), ("logo", "Provider logo")):
            self.icon_mode.addItem("Icon: " + label, value)
        self.icon_mode.setCurrentIndex(self.icon_mode.findData(state.get_icon_mode(selected)))
        layout.addWidget(self.icon_mode)
        layout.addSpacing(14)
        layout.addWidget(plain_label("Providers", "#eeeeee"))
        hint = plain_label("Enable providers and set their order.", "#666666")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.providers = ProviderList()
        enabled = config.enabled_connection_order()
        available = config.available_connections()
        for name in dict.fromkeys(enabled + available):
            if name not in available:
                continue
            item = QListWidgetItem(provider_icon(name), provider_name(name))
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in enabled else Qt.CheckState.Unchecked)
            item.setSizeHint(QSize(0, 36))
            self.providers.addItem(item)
        self.providers.setFixedHeight(self.providers.count() * 36 + 4)
        layout.addWidget(self.providers)
        self.startup = QCheckBox("Start when I sign in to Windows")
        self.startup.setVisible(paths.IS_WINDOWS)
        self.startup.setChecked(startup_enabled())
        layout.addWidget(self.startup)
        layout.addSpacing(14)
        self.about_button = QPushButton("About AI Status")
        self.about_button.clicked.connect(self.about_requested)
        layout.addWidget(self.about_button)
        self.message = plain_label("")
        self.message.setWordWrap(True)
        self.message.hide()
        self.buttons = QWidget(self)
        self.buttons.hide()
        footer = QHBoxLayout(self.buttons)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addWidget(self.message, 1)
        footer.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancelled)
        footer.addWidget(self.cancel_button)
        self.save_button = QPushButton("Save")
        self.save_button.setStyleSheet("border: 1px solid #303030; border-radius: 6px; padding: 6px 8px;")
        self.save_button.clicked.connect(self.save)
        footer.addWidget(self.save_button)
        self.providers.itemChanged.connect(self.update_choices)
        self.providers.model().rowsMoved.connect(self.update_choices)
        self.providers.model().rowsInserted.connect(self.update_choices)
        self.providers.model().rowsRemoved.connect(self.update_choices)
        self.update_choices()
        for checkbox in self.display.values():
            checkbox.toggled.connect(self.clear_message)
        self.icon_mode.currentIndexChanged.connect(self.clear_message)
        self.active.currentIndexChanged.connect(self.clear_message)
        self.startup.toggled.connect(self.clear_message)

    def clear_message(self):
        self.message.hide()

    def update_choices(self):
        choice = self.active.currentData()
        if choice is None:
            selected = state.load_selected() or {}
            choice = [selected.get("provider"), selected.get("idx", 0), selected.get("metric")]
        self.active.blockSignals(True)
        self.active.clear()
        data = getattr(self.dashboard, "data", {})
        for i in range(self.providers.count()):
            item = self.providers.item(i)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            name = item.data(Qt.ItemDataRole.UserRole)
            entries = data.get(name) or [{"provider": provider_name(name), "metrics": []}]
            for entry in entries:
                metrics = entry.get("metrics") or [{"type": "rolling"}]
                for metric in metrics:
                    key = render.metric_key(metric)
                    title = render.metric_title(metric)
                    detail = " (" + key.split(":", 1)[1] + ")" if ":" in key and not metric.get("id") and not metric.get("name") else ""
                    self.active.addItem(provider_icon(name), f"{Dashboard.entry_name(name, entry)} · {title}{detail}",
                                        [name, entry.get("_idx", 0), key])
        index = self.active.findData(choice)
        self.active.setCurrentIndex(index if index >= 0 else 0)
        self.active.setEnabled(self.active.count() > 0)
        self.active.blockSignals(False)
        self.clear_message()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    def save(self):
        order = [self.providers.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.providers.count())
                 if self.providers.item(i).checkState() == Qt.CheckState.Checked]
        display = {key: checkbox.isChecked() for key, checkbox in self.display.items()}
        if not any(display.values()):
            self.message.setText("Show at least one text field in the bar.")
            self.message.show()
            return
        selected = dict(state.load_selected() or {})
        choice = self.active.currentData()
        if choice:
            selected.update(zip(("provider", "idx", "metric"), choice))
        selected.update(display, icon_mode=self.icon_mode.currentData())
        try:
            if paths.IS_WINDOWS:
                set_startup(self.startup.isChecked())
            config.save_connection_order(order)
            state._save_json(state.SELECTED_FILE, selected)
        except OSError:
            self.message.setText("Unable to save settings. Check access to your user configuration directory.")
            self.message.show()
            return
        self.message.setText("Saved")
        self.message.show()
        self.saved.emit()


class AboutView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        info = about.project_info()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(status_icon().pixmap(40, 40))
        layout.addWidget(logo)
        title = plain_label(info["name"], "#eeeeee")
        title.setStyleSheet("color: #eeeeee; font-size: 16px; font-weight: 500;")
        layout.addWidget(title)
        for text in (info["description"],
                     f"Version: v{info['version']}\nCommit: {info['commit']}\nLicense: {info['license']}\nAuthor: {info['author']}"):
            label = plain_label(text)
            label.setWordWrap(True)
            layout.addWidget(label)
        for text, key in (("GitHub", "github"), ("Documentation", "documentation"), ("Report a bug", "issues")):
            button = QPushButton(text)
            row = QHBoxLayout(button)
            row.setContentsMargins(8, 0, 8, 0)
            row.addStretch()
            row.addWidget(ArrowIcon())
            button.setObjectName("about-" + key)
            button.setStyleSheet("border: 1px solid #303030; border-radius: 6px; padding: 6px 8px;")
            button.clicked.connect(lambda checked=False, url=info[key]: QDesktopServices.openUrl(QUrl(url)))
            layout.addWidget(button)
        layout.addSpacing(6)
        layout.addWidget(plain_label("Quick guide", "#eeeeee"))
        for text in (
            "Tray: click to show usage; right-click for settings and other actions.",
            "Usage: click a limit to show it in the tray. Refresh checks now; Reset credits shows the available resets.",
            "Settings: pick a limit, text and icon. Enable providers and reorder them with arrows or drag and drop. Save applies changes and keeps settings open.",
            "Keyboard: R refreshes, C opens settings, Esc goes back. Tab moves between controls; Alt+Up/Down reorders providers.",
        ):
            label = plain_label(text)
            label.setWordWrap(True)
            layout.addWidget(label)


class UpdateWorker(QObject):
    progress = Signal(str)
    finished = Signal(str, bool)

    def work(self):
        try:
            message = updates.run_update(progress=self.progress.emit)
        except (ValueError, OSError) as error:
            self.finished.emit(str(error), False)
        except Exception:
            logging.exception("Application update failed")
            self.finished.emit("Unable to update. Retry or use the manual update guide.", False)
        else:
            self.finished.emit(message, True)


class UpdateView(QWidget):
    update_requested = Signal()

    def __init__(self):
        super().__init__()
        self.guide = {}
        self.version = {}
        self.running = False
        self.completed = False
        self.failed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(14)
        self.heading = plain_label("Update AI Status", "#eeeeee")
        self.heading.setStyleSheet("color: #eeeeee; font-weight: 500;")
        layout.addWidget(self.heading)
        self.versions = plain_label("")
        self.versions.setWordWrap(True)
        layout.addWidget(self.versions)
        optional = plain_label("You can keep using this version and update when you're ready.")
        optional.setWordWrap(True)
        layout.addWidget(optional)
        self.description = plain_label("")
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.steps = plain_label("")
        self.steps.setWordWrap(True)
        layout.addWidget(self.steps)
        self.command_box = QWidget()
        self.command_box.setObjectName("updateCommandBox")
        self.command_box.setStyleSheet("QWidget#updateCommandBox { background: #181818; border: 1px solid #303030; border-radius: 6px; }")
        command_layout = QHBoxLayout(self.command_box)
        command_layout.setContentsMargins(10, 10, 8, 10)
        command_layout.setSpacing(8)
        self.command = QLabel()
        self.command.setTextFormat(Qt.TextFormat.PlainText)
        self.command.setWordWrap(True)
        self.command.setMinimumWidth(1)
        self.command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.command.setStyleSheet("color: #dddddd;")
        command_layout.addWidget(self.command, 1)
        self.copy_button = ControlButton("copy", "Copy command")
        self.copy_button.clicked.connect(self.copy_command)
        command_layout.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.command_box)
        self.copy_feedback = QTimer(self)
        self.copy_feedback.setSingleShot(True)
        self.copy_feedback.timeout.connect(self.reset_copy_feedback)
        self.action = QPushButton()
        self.action.setObjectName("update-action")
        self.action.setStyleSheet("color: #89b4fa; border: 1px solid #294666; border-radius: 6px; padding: 8px;")
        self.action.clicked.connect(self.update_requested)
        layout.addWidget(self.action)
        self.status = plain_label("")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)
        for title, key in (("Downloads and release notes", "releaseUrl"), ("Manual update guide", "guideUrl")):
            button = QPushButton(title)
            button.setObjectName("update-" + key)
            row = QHBoxLayout(button)
            row.setContentsMargins(8, 0, 8, 0)
            row.addStretch()
            row.addWidget(ArrowIcon())
            button.clicked.connect(lambda checked=False, key=key: self.open_link(key))
            layout.addWidget(button)
        layout.addStretch()

    def set_guide(self, guide, version):
        self.guide = guide
        self.version = version
        self.heading.setText(guide.get("title") or "Update AI Status")
        current = version.get("current") or __version__
        latest = version.get("latest")
        self.versions.setText(f"Installed: v{current}\nLatest: v{latest}" if latest else
                              f"Installed: v{current}\nCheck for updates with Refresh.")
        self.description.setText(guide.get("description", ""))
        self.steps.setText("\n\n".join(f"{index}. {step}" for index, step in enumerate(guide.get("steps", []), 1)))
        command = guide.get("command", "")
        if self.command.text() != command:
            self.reset_copy_feedback()
        self.command.setText(command)
        self.command_box.setVisible(bool(command))
        self.update_action()

    def update_action(self):
        available = bool(self.guide.get("canUpdate") and self.version.get("has_update"))
        self.action.setVisible(available or self.running or self.completed or self.failed)
        self.action.setEnabled(available and not self.running)
        self.action.setText("Updating…" if self.running else
                            "Retry update" if self.failed else self.guide.get("actionLabel", "Update now"))

    def show_progress(self, message):
        self.status.setText(message)
        self.status.setStyleSheet("color: #89b4fa;")
        self.status.setVisible(bool(message))

    def copy_command(self):
        QApplication.clipboard().setText(self.guide.get("command", ""))
        self.copy_button.setText("Copied")
        self.copy_button.icon_name = "check"
        self.copy_button.setToolTip("Copied")
        self.copy_button.setAccessibleName("Copied")
        self.copy_button.update()
        self.copy_feedback.start(1800)

    def reset_copy_feedback(self):
        self.copy_feedback.stop()
        self.copy_button.setText("")
        self.copy_button.icon_name = "copy"
        self.copy_button.setToolTip("Copy command")
        self.copy_button.setAccessibleName("Copy command")
        self.copy_button.update()

    def open_link(self, key):
        url = self.guide.get(key)
        if url:
            QDesktopServices.openUrl(QUrl(url))


class Dashboard(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.app = app
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(f"AI Status {__version__}")
        self.setWindowIcon(status_icon())
        self.setFont(panel_font())
        self.setStyleSheet(PANEL_STYLE)
        self.setFixedWidth(380)
        self.resize(380, 620)
        self.data = {}
        for item in state.load_cache():
            self.data.setdefault(render.connection_key(item), []).append(item)
        self.errors = {}
        self.selected = state.load_selected() or {}
        self.busy = False
        self.pending = set()
        self.metric_values = []
        self.metric_buttons = []
        self.provider_buttons = {}
        self.reset_provider = None
        self.settings_view = None
        self.settings_scroll_position = 0
        self.usage_scroll_position = 0
        self.updating = False
        self.update_thread = None
        self.structure = None
        self.queued = False
        self.quitting = False
        self.last_update_check = 0
        self.last_config = config.load_config()
        self.last_refresh = paths.read_json(state.REFRESH_FILE)
        self.last_activation = paths.read_json(paths.RUNTIME_DIR / "desktop-request.json")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        panel = QWidget()
        panel.setObjectName("panel")
        layout.addWidget(panel)
        self.panel_layout = QVBoxLayout(panel)
        self.panel_layout.setContentsMargins(1, 1, 1, 1)
        self.panel_layout.setSpacing(0)
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(49)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 12, 0)
        header_layout.setSpacing(4)
        self.back_button = ControlButton("arrow-left", "Back to usage (Esc)")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.hide()
        header_layout.addWidget(self.back_button)
        self.back_title_gap = QSpacerItem(0, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        header_layout.addSpacerItem(self.back_title_gap)
        self.brand = plain_label("AI Status")
        self.brand.setObjectName("brand")
        header_layout.addWidget(self.brand)
        header_layout.addStretch()
        self.version = plain_label(f"v{__version__}")
        header_layout.addWidget(self.version)
        header_layout.addSpacing(8)
        self.refresh_button = ControlButton("refresh-cw", "Refresh usage (R)")
        self.refresh_button.clicked.connect(self.refresh)
        header_layout.addWidget(self.refresh_button)
        self.settings_button = ControlButton("settings", "Configure (C)")
        self.settings_button.clicked.connect(self.configure)
        header_layout.addWidget(self.settings_button)
        self.panel_layout.addWidget(header)
        self.status = QLabel("Updates every 5 minutes")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.credits_view = ResetCreditsView()
        self.credits_scroll = QScrollArea()
        self.credits_scroll.setWidgetResizable(True)
        self.credits_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.credits_scroll.setWidget(self.credits_view)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.scroll)
        self.pages.addWidget(self.credits_scroll)
        self.panel_layout.addWidget(self.pages)
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pages.addWidget(self.settings_scroll)
        self.about_scroll = QScrollArea()
        self.about_scroll.setWidgetResizable(True)
        self.about_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.about_view = AboutView(self)
        self.about_scroll.setWidget(self.about_view)
        self.pages.addWidget(self.about_scroll)
        self.update_scroll = QScrollArea()
        self.update_scroll.setWidgetResizable(True)
        self.update_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.update_view = UpdateView()
        self.update_view.update_requested.connect(self.start_update)
        self.update_scroll.setWidget(self.update_view)
        self.pages.addWidget(self.update_scroll)
        self.settings_footer = QWidget()
        self.settings_footer_layout = QHBoxLayout(self.settings_footer)
        self.settings_footer_layout.setContentsMargins(16, 8, 16, 12)
        self.settings_footer.hide()
        self.panel_layout.addWidget(self.settings_footer)
        self.tray = QSystemTrayIcon(status_icon(), self)
        menu = QMenu(self)
        menu.setFont(panel_font())
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        menu.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint)
        for label, callback in (("Open dashboard", self.show_dashboard), ("Refresh", self.refresh),
                                ("Settings", self.configure), ("Connection details", self.show_diagnostics),
                                ("Update AI Status", self.show_updates),
                                ("Open logs folder", self.open_logs), ("Exit", self.request_exit)):
            if label in ("Connection details", "Exit"):
                menu.addSeparator()
            action = QAction(label, menu)
            action.triggered.connect(callback)
            menu.addAction(action)
            if label == "Refresh":
                self.refresh_action = action
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.activate)
        self.tray.show()
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.poll_state)
        self.poll.start(1000)
        self.auto_refresh = QTimer(self)
        self.auto_refresh.timeout.connect(self.refresh)
        self.auto_refresh.start(300_000)
        self.animation_frame = 0
        self.animation = QTimer(self)
        self.animation.timeout.connect(self.animate)
        self.animation.start(80)
        self.draw()
        QTimer.singleShot(0, self.refresh)

    def activate(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.hide() if self.isVisible() else self.show_dashboard()

    def show_dashboard(self):
        screen = self.app.screenAt(self.tray.geometry().center()) or self.app.primaryScreen()
        area = screen.availableGeometry()
        anchor = self.tray.geometry()
        x = anchor.right() - self.width() if anchor.isValid() else area.right() - self.width() - 12
        y = anchor.top() - self.height() - 8 if anchor.isValid() else area.bottom() - self.height() - 12
        if y < area.top():
            y = anchor.bottom() + 8
        self.move(max(area.left(), min(x, area.right() - self.width() + 1)),
                  max(area.top(), min(y, area.bottom() - self.height() + 1)))
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.ActivationChange and not self.isActiveWindow():
            if not QApplication.activePopupWidget() and not self.menu.isVisible() and not self.findChildren(QDialog):
                self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.go_back() if self.reset_provider is not None or self.configuring() or self.viewing_about() or self.viewing_updates() else self.hide()
        elif self.configuring() or self.viewing_about() or self.viewing_updates():
            super().keyPressEvent(event)
        elif event.key() == Qt.Key.Key_R:
            self.refresh()
        elif event.key() == Qt.Key.Key_C:
            self.configure()
        elif self.reset_provider is None and event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self.cycle_metric(1 if event.key() == Qt.Key.Key_Down else -1)
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        if self.reset_provider is not None or self.configuring() or self.viewing_about() or self.viewing_updates():
            super().wheelEvent(event)
            return
        self.cycle_metric(1 if event.angleDelta().y() < 0 else -1)
        event.accept()

    def reset_entry(self, key):
        return next((entry for _, entry, _, value in self.visible_metrics if value[:2] == key), None)

    def show_reset_credits(self, key):
        entry = self.reset_entry(key)
        if entry is None or not reset_credits.available_credits(entry.get("reset_credits"))["available"]:
            return
        self.reset_provider = key
        self.credits_view.update_provider(key[0], entry, self.entry_name(key[0], entry))
        self.pages.setCurrentWidget(self.credits_scroll)
        self.credits_scroll.verticalScrollBar().setValue(0)
        self.update_header()
        self.fit_content()
        self.back_button.setFocus()

    def show_usage(self):
        was_configuring = self.configuring()
        was_updating = self.viewing_updates()
        key = self.reset_provider
        self.reset_provider = None
        self.pages.setCurrentWidget(self.scroll)
        self.update_header()
        self.fit_content()
        if was_updating:
            self.scroll.verticalScrollBar().setValue(self.usage_scroll_position)
        heading = self.provider_buttons.get(key)
        if heading:
            (heading.credits if not heading.credits.isHidden() else heading).setFocus()
        elif was_configuring:
            self.settings_button.setFocus()
        elif was_updating:
            (self.update_link if not self.update_link.isHidden() else self.settings_button).setFocus()

    def configuring(self):
        return self.pages.currentWidget() is self.settings_scroll

    def viewing_about(self):
        return self.pages.currentWidget() is self.about_scroll

    def viewing_updates(self):
        return self.pages.currentWidget() is self.update_scroll

    def show_updates(self):
        if not self.viewing_updates():
            self.usage_scroll_position = self.scroll.verticalScrollBar().value()
        self.reset_provider = None
        self.update_view.set_guide(updates.update_guide(), fetch.get_version_info())
        self.pages.setCurrentWidget(self.update_scroll)
        self.update_scroll.verticalScrollBar().setValue(0)
        self.update_header()
        self.fit_content()
        if not self.isVisible():
            self.show_dashboard()
        self.back_button.setFocus()

    def start_update(self):
        if self.quitting or self.updating:
            return
        # Detect the installation again immediately before acting, in case it changed.
        guide, version = updates.update_guide(), fetch.get_version_info()
        self.update_view.set_guide(guide, version)
        if not guide.get("canUpdate") or not version.get("has_update"):
            return
        self.updating = True
        self.update_view.running = True
        self.update_view.failed = False
        self.update_view.update_action()
        self.update_view.show_progress("Preparing update…")
        self.update_thread = QThread(self)
        self.update_worker = UpdateWorker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.work)
        self.update_worker.progress.connect(self.update_view.show_progress)
        self.update_worker.finished.connect(self.on_update_finished)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(self.update_thread_finished)
        self.update_thread.start()

    def on_update_finished(self, message, successful):
        self.update_view.completed = successful
        self.update_view.failed = not successful
        self.update_view.show_progress(message)
        if not successful:
            self.update_view.status.setStyleSheet("color: #f5a3a3;")
        self.fit_content()

    def update_thread_finished(self):
        self.updating = False
        self.update_thread = None
        self.update_worker = None
        self.update_view.running = False
        self.update_view.update_action()
        if self.quitting and not self.busy:
            self.app.quit()

    def show_about(self):
        self.settings_scroll_position = self.settings_scroll.verticalScrollBar().value()
        self.pages.setCurrentWidget(self.about_scroll)
        self.about_scroll.verticalScrollBar().setValue(0)
        self.update_header()
        self.fit_content()
        self.back_button.setFocus()

    def go_back(self):
        if self.viewing_about():
            self.pages.setCurrentWidget(self.settings_scroll)
            self.update_header()
            self.fit_content()
            self.settings_scroll.verticalScrollBar().setValue(self.settings_scroll_position)
            self.settings_view.about_button.setFocus()
        else:
            self.show_usage()

    def update_header(self):
        configuring = self.configuring()
        about_page = self.viewing_about()
        update_page = self.viewing_updates()
        self.brand.setText("Updates" if update_page else "About" if about_page else "Settings" if configuring else "AI Status")
        show_back = configuring or about_page or update_page or self.reset_provider is not None
        self.back_button.setVisible(show_back)
        self.back_title_gap.changeSize(8 if show_back else 0, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.back_button.parentWidget().layout().invalidate()
        back_label = "Back to settings (Esc)" if about_page else "Back to usage (Esc)"
        self.back_button.setToolTip(back_label)
        self.back_button.setAccessibleName(back_label)
        self.refresh_button.setVisible(not configuring and not about_page and not update_page)
        self.settings_button.setVisible(not configuring and not about_page and not update_page and self.reset_provider is None)
        self.settings_footer.setVisible(configuring)

    def animate(self):
        self.animation_frame += 1
        for button in self.metric_buttons:
            if button.value[0] in self.pending:
                button.percentage.setText(render.SPINNERS[self.animation_frame % len(render.SPINNERS)])
        if self.selected.get("provider") in self.pending:
            self.update_tooltip()

    def request_exit(self):
        self.quitting = True
        self.auto_refresh.stop()
        self.poll.stop()
        self.animation.stop()
        if self.busy or self.updating:
            self.status.setText("Exiting after the current operation finishes…")
        else:
            self.app.quit()

    def configure(self):
        if self.viewing_about():
            self.go_back()
        if not self.configuring():
            previous = self.settings_scroll.takeWidget()
            if previous:
                previous.deleteLater()
            while self.settings_footer_layout.count():
                self.settings_footer_layout.takeAt(0).widget().deleteLater()
            self.settings_view = ProviderSettings(self)
            self.settings_view.saved.connect(self.settings_saved)
            self.settings_view.cancelled.connect(self.show_usage)
            self.settings_view.about_requested.connect(self.show_about)
            self.settings_scroll.setWidget(self.settings_view)
            self.settings_footer_layout.addWidget(self.settings_view.buttons)
            self.settings_view.buttons.show()
            self.reset_provider = None
            self.pages.setCurrentWidget(self.settings_scroll)
            self.settings_scroll.verticalScrollBar().setValue(0)
            self.update_header()
            self.fit_content()
        if not self.isVisible():
            self.show_dashboard()
        self.settings_view.active.setFocus()

    def settings_saved(self):
        self.last_config = config.load_config()
        self.selected = state.load_selected() or {}
        self.draw()
        self.refresh()

    def show_diagnostics(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Provider connections")
        dialog.setWindowIcon(status_icon())
        dialog.setFont(panel_font())
        dialog.setStyleSheet(PANEL_STYLE)
        dialog.resize(440, 360)
        layout = QVBoxLayout(dialog)
        for name in config.enabled_connection_order():
            cached = next((entry for entry in self.data.get(name, []) if entry.get("_cached")), None)
            message = self.errors.get(name) or (cached or {}).get("_error")
            if message:
                label = plain_label(f"{provider_name(name)}\n{message}")
                label.setWordWrap(True)
                layout.addWidget(label)
        if layout.count() == 0:
            layout.addWidget(plain_label("No connection errors."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        dialog.deleteLater()

    def open_release(self):
        QDesktopServices.openUrl(QUrl(RELEASE_URL))

    def open_logs(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.LOG_FILE.parent)))

    def poll_state(self):
        activation = paths.read_json(paths.RUNTIME_DIR / "desktop-request.json")
        if activation != self.last_activation:
            self.last_activation = activation
            if activation.get("action") == "config":
                self.configure()
            else:
                self.show_dashboard()
        refresh = paths.read_json(state.REFRESH_FILE)
        cfg = config.load_config()
        selected = state.load_selected() or {}
        if selected != self.selected:
            self.selected = selected
            self.draw()
        if cfg != self.last_config or refresh != self.last_refresh:
            self.last_config, self.last_refresh = cfg, refresh
            self.draw()
            self.refresh()

    def refresh(self):
        if self.quitting:
            return
        if self.busy:
            self.queued = True
            return
        if not state.acquire_lock():
            self.status.setText("Another usage query is running; retrying shortly…")
            QTimer.singleShot(5000, self.refresh)
            return
        self.busy = True
        self.pending = set(config.enabled_connection_order())
        self.errors = {}
        self.refresh_action.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.refresh_button.set_loading(True)
        self.status.setText("Updating…")
        self.draw()
        check_updates = time.monotonic() - self.last_update_check >= 3600
        if check_updates:
            self.last_update_check = time.monotonic()
        self.worker = UsageWorker(check_updates)
        self.worker.result.connect(self.on_result)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.thread = threading.Thread(target=self.worker.work, daemon=True)
        self.thread.start()

    def on_result(self, name, providers):
        self.pending.discard(name)
        if providers:
            self.data[name] = providers
        else:
            self.data.pop(name, None)
        self.draw()

    def on_error(self, name, message):
        self.errors[name] = message
        self.draw()

    def on_finished(self, data):
        state.release_lock()
        self.busy = False
        self.pending.clear()
        self.refresh_action.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.refresh_button.set_loading(False)
        self.worker.deleteLater()
        self.status.setText("Last checked " + time.strftime("%H:%M:%S") + " · updates every 5 minutes")
        if fetch.get_version_info()["has_update"]:
            self.status.setText(self.status.text() + " · update available")
        self.draw()
        if self.quitting and not self.updating:
            self.app.quit()
        elif self.queued:
            self.queued = False
            self.refresh()

    def choose_metric(self, value):
        self.selected.update(provider=value[0], idx=value[1], metric=value[2])
        state.save_selected(self.selected)
        self.draw()

    def selected_value(self):
        return (self.selected.get("provider"), self.selected.get("idx", 0), self.selected.get("metric"))

    def cycle_metric(self, step):
        if self.metric_values:
            index = self.metric_values.index(self.selected_value()) if self.selected_value() in self.metric_values else 0
            self.choose_metric(self.metric_values[(index + step) % len(self.metric_values)])

    def update_tooltip(self):
        for name, entry, metric, value in self.visible_metrics:
            if value == self.selected_value():
                loading = name in self.pending
                percentage = render.SPINNERS[self.animation_frame % len(render.SPINNERS)] if loading else render.metric_value(metric)
                text = f"{self.entry_name(name, entry)} {percentage}"
                if entry.get("_cached"):
                    text += " · cached"
                if getattr(self, "tray_provider", None) != name:
                    self.tray.setIcon(provider_icon(name))
                    self.tray_provider = name
                self.tray.setToolTip(text[:120])
                return
        self.tray.setIcon(status_icon())
        self.tray_provider = None
        self.tray.setToolTip("AI Status · No usage available")

    @staticmethod
    def entry_name(name, entry):
        label = render.entry_name(entry) if entry.get("provider") else provider_name(name)
        return provider_name(name) if label == name else label

    def draw(self):
        scroll_position = self.scroll.verticalScrollBar().value()
        self.visible_metrics = []
        for name in config.enabled_connection_order():
            for entry in self.data.get(name) or []:
                for metric in sorted(entry.get("metrics", []), key=render.metric_sort_key):
                    value = (name, entry.get("_idx", 0), render.metric_key(metric))
                    self.visible_metrics.append((name, entry, metric, value))
        self.metric_values = [value for _, _, _, value in self.visible_metrics]
        if self.metric_values and self.selected_value() not in self.metric_values:
            value = self.metric_values[0]
            self.selected.update(provider=value[0], idx=value[1], metric=value[2])
            state.save_selected(self.selected)
        structure = tuple((value, render.metric_is_amount(metric))
                          for _, _, metric, value in self.visible_metrics)
        focused_value = next((button.value for button in self.metric_buttons if button.hasFocus()), None)
        focused_update = getattr(self, "update_link", None) is not None and self.update_link.hasFocus()
        if structure == self.structure:
            self.update_rows()
            self.fit_content()
            return
        self.structure = structure
        self.metric_buttons = []
        self.provider_buttons = {}
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(20)
        self.update_link = UsageButton()
        self.update_link.setObjectName("updateLink")
        self.update_link.setToolTip("See how to update AI Status. Updates are optional.")
        update_row = QHBoxLayout(self.update_link)
        update_row.setContentsMargins(4, 6, 8, 6)
        update_row.setSpacing(8)
        self.update_title = plain_label("", "#89b4fa")
        update_row.addWidget(self.update_title, 1)
        update_row.addWidget(ArrowIcon(color="#89b4fa"))
        self.update_link.clicked.connect(self.show_updates)
        layout.addWidget(self.update_link)
        for name in config.enabled_connection_order():
            for entry in self.data.get(name) or []:
                metrics = sorted(entry.get("metrics", []), key=render.metric_sort_key)
                if not metrics:
                    continue
                group = QWidget()
                group_layout = QVBoxLayout(group)
                group_layout.setContentsMargins(0, 0, 0, 0)
                group_layout.setSpacing(12)
                active_provider = (name, entry.get("_idx", 0)) == self.selected_value()[:2]
                heading = UsageButton()
                self.provider_buttons[(name, entry.get("_idx", 0))] = heading
                row = QHBoxLayout(heading)
                row.setContentsMargins(4, 6, 4, 6)
                row.setSpacing(8)
                arrow = plain_label("→" if active_provider else "", "#eeeeee")
                arrow.setFixedWidth(14)
                heading.arrow = arrow
                row.addWidget(arrow)
                logo = plain_label("")
                logo.setPixmap(provider_icon(name).pixmap(16, 16))
                logo.setFixedSize(16, 16)
                row.addWidget(logo)
                label = plain_label(self.entry_name(name, entry), "#eeeeee" if active_provider else "#888888")
                label.setStyleSheet(label.styleSheet() + "font-weight: 500;")
                heading.name_label = label
                row.addWidget(label, 1)
                heading.setAccessibleName(self.entry_name(name, entry))
                first = (name, entry.get("_idx", 0), render.metric_key(metrics[0]))
                heading.clicked.connect(lambda checked=False, value=first: self.choose_metric(value))
                group_layout.addWidget(heading)
                heading.cached_label = plain_label("Cached data", "#666666")
                heading.cached_label.setContentsMargins(50, 0, 0, 0)
                group_layout.addWidget(heading.cached_label)
                for metric in metrics:
                    title = render.metric_title(metric)
                    value = (name, entry.get("_idx", 0), render.metric_key(metric))
                    active = value == self.selected_value()
                    color = "#eeeeee" if active else "#888888"
                    pct = render.metric_percentage(metric)
                    button = UsageButton()
                    button.value = value
                    button.is_amount = render.metric_is_amount(metric)
                    button.setAccessibleName(f"{self.entry_name(name, entry)} {title} {render.metric_value(metric)}")
                    button.clicked.connect(lambda checked=False, value=value: self.choose_metric(value))
                    self.metric_buttons.append(button)
                    metric_layout = QVBoxLayout(button)
                    metric_layout.setContentsMargins(4, 4, 4, 4)
                    metric_layout.setSpacing(4)
                    title_row = QHBoxLayout()
                    title_row.setSpacing(8)
                    bullet = plain_label("•" if active else "", color)
                    bullet.setFixedWidth(38)
                    button.bullet = bullet
                    title_row.addWidget(bullet)
                    button.title = plain_label(title, color)
                    button.title.setWordWrap(True)
                    title_row.addWidget(button.title, 0 if button.is_amount else 1)
                    button.percentage = plain_label(render.metric_value(metric), color)
                    button.percentage.setAlignment((Qt.AlignmentFlag.AlignLeft if button.is_amount else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter)
                    title_row.addWidget(button.percentage)
                    if button.is_amount:
                        title_row.addStretch()
                    metric_layout.addLayout(title_row)
                    button.bar_container = QWidget()
                    bar_row = QHBoxLayout(button.bar_container)
                    bar_row.setContentsMargins(46, 0, 0, 0)
                    bar_row.setSpacing(4)
                    button.open_bracket = plain_label("[", color)
                    bar_row.addWidget(button.open_bracket)
                    button.bar = UsageBar()
                    bar_row.addWidget(button.bar, 1)
                    button.close_bracket = plain_label("]", color)
                    bar_row.addWidget(button.close_bracket)
                    metric_layout.addWidget(button.bar_container)
                    button.description = plain_label(render.metric_detail(metric), "#666666")
                    button.description.setContentsMargins(46, 0, 0, 0)
                    button.description.setWordWrap(True)
                    metric_layout.addWidget(button.description)
                    group_layout.addWidget(button)
                heading.credits = UsageButton()
                credits_layout = QHBoxLayout(heading.credits)
                credits_layout.setContentsMargins(50, 6, 8, 6)
                credits_layout.setSpacing(8)
                heading.credits_title = plain_label("")
                credits_layout.addWidget(heading.credits_title, 1)
                credits_layout.addWidget(ArrowIcon())
                heading.credits.clicked.connect(lambda checked=False, key=(name, entry.get("_idx", 0)):
                                                self.show_reset_credits(key))
                group_layout.addWidget(heading.credits)
                layout.addWidget(group)
        if not self.metric_values:
            self.empty_message = plain_label("")
            self.empty_message.setWordWrap(True)
            layout.addWidget(self.empty_message)
            settings = QPushButton("Settings")
            settings.clicked.connect(self.configure)
            layout.addWidget(settings)
        self.update_rows()
        self.scroll.setWidget(content)
        if focused_value is not None:
            for button in self.metric_buttons:
                if button.value == focused_value:
                    button.setFocus()
                    break
        elif focused_update:
            self.update_link.setFocus()
        self.fit_content()
        self.scroll.verticalScrollBar().setValue(scroll_position)

    def update_rows(self):
        version = fetch.get_version_info()
        self.update_link.setVisible(bool(version.get("has_update")))
        self.update_title.setText(f"Update available: v{version.get('latest', '')}")
        self.update_link.setAccessibleName(self.update_title.text() + ". Open update guide")
        if self.viewing_updates():
            self.update_view.set_guide(self.update_view.guide, version)
        groups = {}
        for name, entry, metric, value in self.visible_metrics:
            groups.setdefault(value[:2], (name, entry))
        for key, (name, entry) in groups.items():
            heading = self.provider_buttons[key]
            active = key == self.selected_value()[:2]
            heading.arrow.setText("→" if active else "")
            heading.name_label.setText(self.entry_name(name, entry))
            heading.name_label.setStyleSheet(f"color: {'#eeeeee' if active else '#888888'}; font-weight: 500;")
            heading.setAccessibleName(self.entry_name(name, entry))
            heading.cached_label.setVisible(bool(entry.get("_cached")))
            heading.cached_label.setToolTip(entry.get("_error", "Unable to refresh"))
            available = reset_credits.available_credits(entry.get("reset_credits"))["available"]
            heading.credits.setVisible(bool(available))
            heading.credits_title.setText(f"Reset credits: {available} available")
            heading.credits.setAccessibleName(f"{self.entry_name(name, entry)}: {available} reset credits. Open reset details")
        group_indices = {key: index for index, key in enumerate(groups)}
        for button, (name, entry, metric, value) in zip(self.metric_buttons, self.visible_metrics):
            active = value == self.selected_value()
            loading = name in self.pending
            color = "#eeeeee" if active else "#888888"
            pct = render.metric_percentage(metric)
            title = render.metric_title(metric)
            button.bullet.setText("•" if active else "")
            button.title.setText(title + ":" if button.is_amount else title)
            button.bar.set_usage(pct or 0, active, loading, group_indices[value[:2]])
            button.bar_container.setVisible(pct is not None)
            for item in (button.bar, button.open_bracket, button.close_bracket):
                item.setVisible(pct is not None)
            value_width = max(38, self.fontMetrics().horizontalAdvance(render.metric_value(metric)) + 4)
            button.percentage.setFixedWidth(value_width)
            if button.is_amount:
                available = self.width() - 2 - 32 - 8 - 46 - 8 - value_width
                title_width = self.fontMetrics().horizontalAdvance(title + ":") + 1
                button.title.setFixedWidth(max(24, min(title_width, available)))
            button.percentage.setText(render.SPINNERS[self.animation_frame % len(render.SPINNERS)] if loading else render.metric_value(metric))
            for label in (button.bullet, button.title, button.open_bracket, button.close_bracket, button.percentage):
                label.setStyleSheet(f"color: {color};")
            detail = render.metric_detail(metric)
            button.description.setText(detail)
            button.description.setVisible(bool(detail))
            button.setAccessibleName(f"{self.entry_name(name, entry)} {title} {render.metric_value(metric)}")
        if not self.metric_values:
            self.empty_message.setText("Checking your connected providers…" if self.busy else
                "No usage available. Connect a provider and refresh." if config.enabled_connection_order() else
                "No providers enabled. Choose them in Settings.")
        self.update_tooltip()
        if self.reset_provider is not None:
            entry = self.reset_entry(self.reset_provider)
            if entry is None:
                self.reset_provider = None
                self.pages.setCurrentWidget(self.scroll)
                self.update_header()
            else:
                name = self.reset_provider[0]
                self.credits_view.update_provider(name, entry, self.entry_name(name, entry))

    def fit_content(self):
        content = self.pages.currentWidget().widget()
        content.ensurePolished()
        content.layout().activate()
        height = content.heightForWidth(self.width() - 2) if content.hasHeightForWidth() else content.sizeHint().height()
        height = max(height, content.minimumSizeHint().height())
        natural_height = height + 57 + (self.settings_footer.sizeHint().height() if self.configuring() else 0)
        screen = self.screen().availableGeometry()
        bottom = self.geometry().bottom()
        self.resize(self.width(), min(max(180, natural_height), 720, max(180, screen.height() - 32)))
        if self.isVisible():
            self.move(self.x(), max(screen.top(), min(bottom - self.height() + 1,
                                                    screen.bottom() - self.height() + 1)))


def smoke_test():
    """Exercise the packaged raster UI and the real system ConPTY without accounts."""
    widget = QWidget()
    widget.setStyleSheet(PANEL_STYLE)
    widget.setFont(panel_font())
    layout = QVBoxLayout(widget)
    button = UsageButton()
    row = QVBoxLayout(button)
    row.addWidget(plain_label("Rolling Usage:"))
    bar = UsageBar()
    bar.set_usage(23, True, False)
    row.addWidget(bar)
    layout.addWidget(button)
    widget.resize(380, 180)
    widget.ensurePolished()
    image = widget.grab().toImage()
    result = {"widget_render": not image.isNull(),
              "provider_icons": len(PROVIDERS) == len(config.available_providers()) and all(icon_has_pixels(provider_icon(name)) for name in PROVIDERS),
              "font_family": panel_font().family(), "native_console": False}
    widget.deleteLater()
    if paths.IS_WINDOWS:
        import os
        from .windows_console import PtyProcess
        proc = PtyProcess.spawn([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/q", "/c", "echo ai-status-conpty-ok"])
        output = ""
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and "ai-status-conpty-ok" not in output:
                try:
                    output += proc.read(timeout=0.2)
                except TimeoutError:
                    continue
                except EOFError:
                    break
            result["native_console"] = "ai-status-conpty-ok" in output
        finally:
            proc.close(force=True)
    return result


def run(configure=False):
    paths.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    paths.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=paths.LOG_FILE, encoding="utf-8", level=logging.WARNING)
    if paths.IS_WINDOWS:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("gelzinn.ai-status")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("AI Status")
    app.setWindowIcon(status_icon())
    app.setFont(panel_font())
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(paths.RUNTIME_DIR / "ai-status-desktop.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        paths.atomic_json(paths.RUNTIME_DIR / "desktop-request.json", {
            "action": "config" if configure else "show", "id": uuid.uuid4().hex,
        })
        return
    if not QSystemTrayIcon.isSystemTrayAvailable():
        lock.unlock()
        raise SystemExit("The desktop notification area is unavailable.")
    dashboard = Dashboard(app)
    if configure:
        QTimer.singleShot(0, dashboard.configure)
    app.exec()
    dashboard.tray.hide()
    lock.unlock()
