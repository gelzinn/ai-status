"""Desktop adapter. The Waybar daemon and CLI do not import Qt."""
import hashlib
import logging
from pathlib import Path
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QObject, QLockFile, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import __version__, config, fetch, paths, render, state

RELEASE_URL = "https://github.com/gelzinn/ai-status/releases/latest"


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
    # Bundled drawing: no network, ImageMagick, Nerd Font or SVG loader required.
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#7c3aed"))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", 23, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "AI")
    painter.end()
    return QIcon(pixmap)


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
        self.resize(380, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enable providers and drag to reorder:"))
        self.providers = QListWidget()
        self.providers.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        enabled = config.enabled_order()
        available = config.available_providers()
        for name in dict.fromkeys(enabled + available):
            if name not in available:
                continue
            item = QListWidgetItem(name)
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
        order = [self.providers.item(i).text() for i in range(self.providers.count())
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
        super().__init__()
        self.app = app
        self.setWindowTitle(f"AI Status {__version__}")
        self.setWindowIcon(status_icon())
        self.resize(460, 620)
        self.data = {}
        for item in state.load_cache():
            self.data.setdefault(item.get("_dir"), []).append(item)
        self.errors = {}
        self.selected = state.load_selected() or {}
        self.busy = False
        self.queued = False
        self.quitting = False
        self.last_update_check = 0
        self.last_config = config.load_config()
        self.last_refresh = paths.read_json(state.REFRESH_FILE)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.active = QComboBox()
        self.active.currentIndexChanged.connect(self.select_metric)
        controls.addWidget(self.active, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_button)
        settings = QPushButton("Settings")
        settings.clicked.connect(self.configure)
        controls.addWidget(settings)
        layout.addLayout(controls)
        self.status = QLabel("Updates every 5 minutes")
        layout.addWidget(self.status)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)
        self.tray = QSystemTrayIcon(status_icon(), self)
        menu = QMenu(self)
        for label, callback in (("Open dashboard", self.show_dashboard), ("Refresh", self.refresh),
                                ("Settings", self.configure), ("Download latest version", self.open_release),
                                ("Open logs folder", self.open_logs), ("Exit", self.request_exit)):
            action = QAction(label, menu)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.activate)
        self.tray.show()
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.poll_state)
        self.poll.start(1000)
        self.auto_refresh = QTimer(self)
        self.auto_refresh.timeout.connect(self.refresh)
        self.auto_refresh.start(300_000)
        self.draw()
        QTimer.singleShot(0, self.refresh)

    def activate(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_dashboard()

    def show_dashboard(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def request_exit(self):
        self.quitting = True
        self.auto_refresh.stop()
        self.poll.stop()
        if self.busy:
            self.status.setText("Exiting after the current refresh finishes…")
        else:
            self.app.quit()

    def configure(self):
        if ProviderSettings(self).exec() == QDialog.DialogCode.Accepted:
            self.last_config = config.load_config()
            self.draw()
            self.refresh()

    def open_release(self):
        QDesktopServices.openUrl(QUrl(RELEASE_URL))

    def open_logs(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.LOG_FILE.parent)))

    def poll_state(self):
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
        self.errors = {}
        self.refresh_button.setEnabled(False)
        self.status.setText("Updating…")
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
        self.refresh_button.setEnabled(True)
        self.worker.deleteLater()
        self.status.setText("Last checked " + time.strftime("%H:%M:%S") + " · updates every 5 minutes")
        if fetch.get_version_info()["has_update"]:
            self.status.setText(self.status.text() + " · update available")
        self.draw()
        if self.active.count():
            self.select_metric(self.active.currentIndex())
        if self.quitting:
            self.app.quit()
        elif self.queued:
            self.queued = False
            self.refresh()

    def select_metric(self, index):
        value = self.active.itemData(index)
        if value:
            self.selected.update(provider=value[0], idx=value[1], metric=value[2])
            state.save_selected(self.selected)
            self.update_tooltip()

    def update_tooltip(self):
        # A standard tray tooltip is a short summary; details live in the panel.
        text = self.active.currentText() or "No usage available — open dashboard"
        self.tray.setToolTip(("AI Status · " + text)[:120])

    def draw(self):
        self.active.blockSignals(True)
        self.active.clear()
        content = QWidget()
        layout = QVBoxLayout(content)
        selected_index = -1
        for name in config.enabled_order():
            entries = self.data.get(name) or []
            if not entries:
                label = QLabel(f"{name}\n{self.errors.get(name, 'Waiting for usage…')}")
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setWordWrap(True)
                layout.addWidget(label)
                continue
            for entry in entries:
                label = QLabel(entry.get("provider", name))
                label.setTextFormat(Qt.TextFormat.PlainText)
                layout.addWidget(label)
                if entry.get("_cached"):
                    stale = QLabel("Cached data · " + entry.get("_error", "Unable to refresh"))
                    stale.setTextFormat(Qt.TextFormat.PlainText)
                    stale.setWordWrap(True)
                    layout.addWidget(stale)
                for metric in entry.get("metrics", []):
                    title = metric.get("name") or render.TYPE_NAMES.get(metric.get("type"), "Usage")
                    detail = metric.get("detail") or ""
                    value = (name, entry.get("_idx", 0), render.metric_key(metric))
                    pct = float(metric.get("percentage", 0))
                    self.active.addItem(f"{entry.get('provider', name)} · {title} · {pct:.0f}%" + (f" · {detail}" if detail else ""), value)
                    if value == (self.selected.get("provider"), self.selected.get("idx", 0), self.selected.get("metric")):
                        selected_index = self.active.count() - 1
                    bar = QProgressBar()
                    bar.setRange(0, 100)
                    bar.setValue(round(max(0, min(100, pct))))
                    bar.setFormat(title.replace("%", "%%") + f" · {pct:.0f}%")
                    layout.addWidget(bar)
                    seconds = metric.get("reset_in_seconds")
                    reset = render.format_reset_time(seconds, metric.get("type")) if seconds is not None else ""
                    if detail or reset:
                        description = QLabel(" · ".join(p for p in (detail, reset) if p))
                        description.setTextFormat(Qt.TextFormat.PlainText)
                        description.setWordWrap(True)
                        layout.addWidget(description)
        if not config.enabled_order():
            layout.addWidget(QLabel("No providers enabled. Open Settings to choose providers."))
        layout.addStretch()
        self.scroll.setWidget(content)
        self.active.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.active.blockSignals(False)
        self.update_tooltip()


def run(configure=False):
    paths.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    paths.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=paths.LOG_FILE, encoding="utf-8", level=logging.WARNING)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("AI Status")
    app.setQuitOnLastWindowClosed(False)
    server_name = "ai-status-" + hashlib.sha256(str(paths.CONFIG_DIR).encode()).hexdigest()[:16]
    client = QLocalSocket()
    client.connectToServer(server_name)
    if client.waitForConnected(1000):
        client.write(b"config" if configure else b"show")
        client.waitForBytesWritten(1000)
        return
    lock = QLockFile(str(paths.RUNTIME_DIR / "ai-status-desktop.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None, "AI Status", "AI Status is already running in the notification area.")
        return
    if not QSystemTrayIcon.isSystemTrayAvailable():
        lock.unlock()
        raise SystemExit("The desktop notification area is unavailable.")
    dashboard = Dashboard(app)
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    QLocalServer.removeServer(server_name)
    if not server.listen(server_name):
        logging.warning("Unable to start desktop activation socket")

    def receive():
        connection = server.nextPendingConnection()

        def read():
            message = bytes(connection.readAll())
            if message == b"config":
                dashboard.configure()
            else:
                dashboard.show_dashboard()
            connection.disconnectFromServer()
        connection.readyRead.connect(read)
        connection.disconnected.connect(connection.deleteLater)
        if connection.bytesAvailable():
            read()

    server.newConnection.connect(receive)
    if configure:
        QTimer.singleShot(0, dashboard.configure)
    app.exec()
    dashboard.tray.hide()
    server.close()
    lock.unlock()
