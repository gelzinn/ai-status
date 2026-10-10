"""Desktop adapter. The Waybar daemon and CLI do not import Qt."""
import logging
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from PySide6.QtCore import QObject, QLockFile, QTimer, Qt, QUrl, Signal, QSize
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QStyledItemDelegate, QStyle,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import __version__, config, fetch, paths, render, state

RELEASE_URL = "https://github.com/gelzinn/ai-status/releases/latest"
ASSETS = paths.LIB_DIR / "assets"
_font_family = None
PROVIDERS = paths.read_json(ASSETS / "providers.json") or paths.read_json(
    paths.LIB_DIR.parent / "shared/providers/providers.json")


def provider_name(key):
    return PROVIDERS.get(key, {}).get("name", key)

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
QProgressBar { background: #141414; border: 1px solid #222222; border-radius: 1px; }
QProgressBar::chunk { background: #555555; }
QProgressBar[active="true"]::chunk { background: #eeeeee; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 6px 0; }
QScrollBar::handle:vertical { background: #303030; border-radius: 2px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QPushButton { padding: 6px 8px; }
QPushButton#actions { background: #1c1c1c; padding: 0; border-radius: 6px; text-align: center; }
QPushButton#actions:hover { background: #252525; }
QMenu { background: #111111; border: 1px solid #303030; padding: 5px; }
QMenu::item { padding: 8px 16px; }
QMenu::item:selected { background: #252525; color: #eeeeee; }
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


def plain_label(text, color=None):
    label = QLabel(str(text))
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    if color:
        label.setStyleSheet(f"color: {color};")
    return label


class ProviderDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # The selected row provides the neutral focus indicator; avoid the
        # platform's blue rectangle drawn separately around the text.
        option.state &= ~QStyle.StateFlag.State_HasFocus


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
            for name in config.enabled_order():
                self.error.emit(name, "Refresh failed; see the application log.")
        finally:
            self.finished.emit(data)


class ProviderSettings(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Status settings")
        self.setWindowIcon(status_icon())
        self.setFont(panel_font())
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#252525"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#eeeeee"))
        self.setPalette(palette)
        self.setStyleSheet(PANEL_STYLE + """
            QListWidget { background: #161616; border: 1px solid #262626; border-radius: 8px; padding: 8px; }
            QListWidget::item { padding: 7px; }
            QListWidget::item:selected { background: #252525; color: #eeeeee; }
            QCheckBox { padding: 8px 0; }
            QPushButton { border: 1px solid #303030; border-radius: 6px; }
            QListWidget::indicator, QCheckBox::indicator {
                width: 16px; height: 16px; border: 1px solid #888888;
                border-radius: 4px; background: #161616;
            }
            QListWidget::indicator:checked, QCheckBox::indicator:checked {
                background: #eeeeee; border-color: #eeeeee;
                image: url(CHECKMARK);
            }
        """.replace("CHECKMARK", '"' + (ASSETS / "checkmark.png").as_posix() + '"'))
        self.resize(380, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enable providers and drag to reorder:"))
        self.providers = QListWidget()
        self.providers.setItemDelegate(ProviderDelegate(self.providers))
        self.providers.setIconSize(QSize(20, 20))
        self.providers.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        enabled = config.enabled_order()
        available = config.available_providers()
        for name in dict.fromkeys(enabled + available):
            if name not in available:
                continue
            item = QListWidgetItem(provider_icon(name), provider_name(name))
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in enabled else Qt.CheckState.Unchecked)
            self.providers.addItem(item)
        layout.addWidget(self.providers)
        self.startup = QCheckBox("Start when I sign in to Windows")
        self.startup.setVisible(paths.IS_WINDOWS)
        self.startup.setChecked(startup_enabled())
        layout.addWidget(self.startup)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        order = [self.providers.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.providers.count())
                 if self.providers.item(i).checkState() == Qt.CheckState.Checked]
        try:
            if paths.IS_WINDOWS:
                set_startup(self.startup.isChecked())
            config.save_config(order)
        except OSError:
            QMessageBox.warning(self, "Settings", "Unable to save settings. Check access to your user configuration directory.")
            return
        self.accept()


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
            self.data.setdefault(item.get("_dir"), []).append(item)
        self.errors = {}
        self.selected = state.load_selected() or {}
        self.busy = False
        self.pending = set()
        self.metric_values = []
        self.metric_buttons = []
        self.provider_buttons = {}
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
        brand = plain_label("AI Status")
        brand.setObjectName("brand")
        header_layout.addWidget(brand)
        header_layout.addStretch()
        self.version = plain_label(f"v{__version__}")
        header_layout.addWidget(self.version)
        self.menu_button = QPushButton("⋯")
        self.menu_button.setObjectName("actions")
        self.menu_button.setAccessibleName("AI Status actions")
        self.menu_button.setFixedSize(28, 28)
        header_layout.addWidget(self.menu_button)
        self.panel_layout.addWidget(header)
        # Refresh is a context-menu action, not a permanent toolbar in the usage panel.
        self.status = QLabel("Updates every 5 minutes")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.panel_layout.addWidget(self.scroll)
        self.tray = QSystemTrayIcon(status_icon(), self)
        menu = QMenu(self)
        for label, callback in (("Open dashboard", self.show_dashboard), ("Refresh", self.refresh),
                                ("Settings", self.configure), ("Connection details", self.show_diagnostics),
                                ("Download latest version", self.open_release),
                                ("Open logs folder", self.open_logs), ("Exit", self.request_exit)):
            action = QAction(label, menu)
            action.triggered.connect(callback)
            menu.addAction(action)
            if label == "Refresh":
                self.refresh_action = action
        self.menu = menu
        self.menu_button.clicked.connect(lambda: menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft())))
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
            if not self.menu.isVisible() and not self.findChildren(QDialog):
                self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self.cycle_metric(1 if event.key() == Qt.Key.Key_Down else -1)
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        self.cycle_metric(1 if event.angleDelta().y() < 0 else -1)
        event.accept()

    def animate(self):
        self.animation_frame += 1
        for button in self.metric_buttons:
            if button.value[0] in self.pending:
                button.percentage.setText(render.SPINNERS[self.animation_frame % len(render.SPINNERS)])

    def request_exit(self):
        self.quitting = True
        self.auto_refresh.stop()
        self.poll.stop()
        self.animation.stop()
        if self.busy:
            self.status.setText("Exiting after the current refresh finishes…")
        else:
            self.app.quit()

    def configure(self):
        settings = ProviderSettings(self)
        if settings.exec() == QDialog.DialogCode.Accepted:
            self.last_config = config.load_config()
            self.draw()
            self.refresh()
        settings.deleteLater()

    def show_diagnostics(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Provider connections")
        dialog.setWindowIcon(status_icon())
        dialog.setFont(panel_font())
        dialog.setStyleSheet(PANEL_STYLE)
        dialog.resize(440, 360)
        layout = QVBoxLayout(dialog)
        for name in config.enabled_order():
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
        self.pending = set(config.enabled_order())
        self.errors = {}
        self.refresh_action.setEnabled(False)
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
        self.worker.deleteLater()
        self.status.setText("Last checked " + time.strftime("%H:%M:%S") + " · updates every 5 minutes")
        if fetch.get_version_info()["has_update"]:
            self.status.setText(self.status.text() + " · update available")
        self.draw()
        if self.quitting:
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
                text = f"{self.entry_name(name, entry)} {float(metric.get('percentage', 0)):.0f}%"
                if entry.get("_cached"):
                    text += " · cached"
                if name in self.pending:
                    text += " · updating"
                self.tray.setIcon(provider_icon(name))
                self.tray.setToolTip(text[:120])
                return
        self.tray.setIcon(status_icon())
        self.tray.setToolTip("AI Status · No usage available")

    @staticmethod
    def entry_name(name, entry):
        label = entry.get("provider") or provider_name(name)
        return provider_name(name) if label == name else label

    def draw(self):
        scroll_position = self.scroll.verticalScrollBar().value()
        self.visible_metrics = []
        for name in config.enabled_order():
            for entry in self.data.get(name) or []:
                for metric in sorted(entry.get("metrics", []), key=lambda m: render.TYPE_ORDER.get(m.get("type"), 4)):
                    value = (name, entry.get("_idx", 0), render.metric_key(metric))
                    self.visible_metrics.append((name, entry, metric, value))
        self.metric_values = [value for _, _, _, value in self.visible_metrics]
        if self.metric_values and self.selected_value() not in self.metric_values:
            value = self.metric_values[0]
            self.selected.update(provider=value[0], idx=value[1], metric=value[2])
            state.save_selected(self.selected)
        self.metric_buttons = []
        self.provider_buttons = {}
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(26)
        for name in config.enabled_order():
            for entry in self.data.get(name) or []:
                metrics = sorted(entry.get("metrics", []), key=lambda m: render.TYPE_ORDER.get(m.get("type"), 4))
                if not metrics:
                    continue
                group = QWidget()
                group_layout = QVBoxLayout(group)
                group_layout.setContentsMargins(0, 0, 0, 0)
                group_layout.setSpacing(16)
                active_provider = (name, entry.get("_idx", 0)) == self.selected_value()[:2]
                heading = UsageButton()
                self.provider_buttons[(name, entry.get("_idx", 0))] = heading
                row = QHBoxLayout(heading)
                row.setContentsMargins(4, 6, 4, 6)
                row.setSpacing(8)
                arrow = plain_label("→" if active_provider else "", "#eeeeee")
                arrow.setFixedWidth(14)
                row.addWidget(arrow)
                logo = plain_label("")
                logo.setPixmap(provider_icon(name).pixmap(16, 16))
                logo.setFixedSize(16, 16)
                row.addWidget(logo)
                label = plain_label(self.entry_name(name, entry), "#eeeeee" if active_provider else "#888888")
                label.setStyleSheet(label.styleSheet() + "font-weight: 500;")
                row.addWidget(label, 1)
                heading.setAccessibleName(self.entry_name(name, entry))
                first = (name, entry.get("_idx", 0), render.metric_key(metrics[0]))
                heading.clicked.connect(lambda checked=False, value=first: self.choose_metric(value))
                group_layout.addWidget(heading)
                if entry.get("_cached"):
                    stale = plain_label("    Cached data", "#666666")
                    stale.setToolTip(entry.get("_error", "Unable to refresh"))
                    group_layout.addWidget(stale)
                for metric in metrics:
                    title = metric.get("name") or render.TYPE_NAMES.get(metric.get("type"), "Usage")
                    value = (name, entry.get("_idx", 0), render.metric_key(metric))
                    active = value == self.selected_value()
                    color = "#eeeeee" if active else "#888888"
                    pct = float(metric.get("percentage", 0))
                    button = UsageButton()
                    button.value = value
                    button.setAccessibleName(f"{self.entry_name(name, entry)} {title} {pct:.0f}%")
                    button.clicked.connect(lambda checked=False, value=value: self.choose_metric(value))
                    self.metric_buttons.append(button)
                    metric_layout = QVBoxLayout(button)
                    metric_layout.setContentsMargins(4, 4, 4, 4)
                    metric_layout.setSpacing(4)
                    title_row = QHBoxLayout()
                    title_row.setSpacing(0)
                    bullet = plain_label("•" if active else "", color)
                    bullet.setFixedWidth(20)
                    title_row.addWidget(bullet)
                    title_row.addWidget(plain_label(title + ":", color), 1)
                    metric_layout.addLayout(title_row)
                    bar_row = QHBoxLayout()
                    bar_row.setContentsMargins(20, 0, 0, 0)
                    bar_row.setSpacing(4)
                    bar_row.addWidget(plain_label("[", color))
                    bar = QProgressBar()
                    bar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                    bar.setTextVisible(False)
                    bar.setFixedHeight(15)
                    bar.setProperty("active", active)
                    bar.setRange(0, 0 if name in self.pending else 100)
                    bar.setValue(round(max(0, min(100, pct))))
                    bar_row.addWidget(bar, 1)
                    bar_row.addWidget(plain_label("]", color))
                    button.percentage = plain_label(f"{pct:.0f}%", color)
                    button.percentage.setFixedWidth(38)
                    button.percentage.setAlignment(Qt.AlignmentFlag.AlignRight)
                    bar_row.addWidget(button.percentage)
                    metric_layout.addLayout(bar_row)
                    seconds = metric.get("reset_in_seconds")
                    reset = render.format_reset_time(seconds, metric.get("type")) if seconds is not None else "no reset available"
                    description = plain_label("    " + (metric.get("detail") or reset), "#666666")
                    description.setWordWrap(True)
                    metric_layout.addWidget(description)
                    group_layout.addWidget(button)
                layout.addWidget(group)
        if not self.metric_values:
            message = ("Checking your connected providers…" if self.busy else
                       "No usage available. Connect a provider and refresh." if config.enabled_order() else
                       "No providers enabled. Choose them in Settings.")
            empty = plain_label(message)
            empty.setWordWrap(True)
            layout.addWidget(empty)
            settings = QPushButton("Settings")
            settings.clicked.connect(self.configure)
            layout.addWidget(settings)
        self.scroll.setWidget(content)
        content.ensurePolished()
        layout.activate()
        natural_height = content.sizeHint().height() + 57
        screen = self.screen().availableGeometry()
        self.resize(self.width(), min(max(180, natural_height), 720, max(180, screen.height() - 32)))
        self.scroll.verticalScrollBar().setValue(scroll_position)
        self.menu_button.setToolTip(self.status.text())
        self.update_tooltip()


def smoke_test():
    """Exercise the packaged raster UI and the real system ConPTY without accounts."""
    widget = QWidget()
    widget.setStyleSheet(PANEL_STYLE)
    widget.setFont(panel_font())
    layout = QVBoxLayout(widget)
    button = UsageButton()
    row = QVBoxLayout(button)
    row.addWidget(plain_label("Rolling Usage:"))
    bar = QProgressBar()
    bar.setValue(23)
    row.addWidget(bar)
    layout.addWidget(button)
    widget.resize(380, 180)
    widget.ensurePolished()
    image = widget.grab().toImage()
    result = {"widget_render": not image.isNull(),
              "provider_icons": len(PROVIDERS) == 8 and all(icon_has_pixels(provider_icon(name)) for name in PROVIDERS),
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
