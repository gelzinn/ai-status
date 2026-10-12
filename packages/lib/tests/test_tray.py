import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from test_portability import IsolatedState
from core import config, paths, state

try:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QColor, QPixmap, QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel
    from core import tray
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "Install windows/requirements.txt to test the desktop adapter")
class DesktopTests(IsolatedState):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        settings_directory = patch.object(paths, "CONFIG_DIR", self.root / "config")
        settings_directory.start()
        self.addCleanup(settings_directory.stop)
        config.save_config(["codex", "copilot"])
        with patch.object(tray.QTimer, "singleShot"), patch.object(tray.QSystemTrayIcon, "show"):
            self.dashboard = tray.Dashboard(self.app)
        self.dashboard.poll.stop()
        self.dashboard.auto_refresh.stop()
        self.dashboard.animation.stop()
        self.addCleanup(self.dashboard.tray.hide)
        self.addCleanup(self.dashboard.deleteLater)

    def test_startup_cache_does_not_trigger_notifications(self):
        cached = [{"provider": "Codex", "_dir": "codex", "_idx": 0,
                   "_observed_at": time.time(), "metrics": [{"type": "weekly", "percentage": 100}]}]
        with patch.object(state, "load_cache", return_value=cached), \
             patch.object(tray.notifications, "process") as evaluate, \
             patch.object(tray.QTimer, "singleShot"), patch.object(tray.QSystemTrayIcon, "show"):
            dashboard = tray.Dashboard(self.app)
        for timer in (dashboard.poll, dashboard.auto_refresh, dashboard.animation):
            timer.stop()
        self.addCleanup(dashboard.tray.hide)
        self.addCleanup(dashboard.deleteLater)
        evaluate.assert_not_called()

    def test_fresh_result_is_evaluated_and_notification_click_opens_its_limit(self):
        providers = [{"provider": "Codex", "_dir": "codex", "_idx": 0, "metrics": [
            {"type": "rolling", "percentage": 23}, {"type": "weekly", "percentage": 95}]}]
        event = {"id": "weekly-95", "provider": "codex", "idx": 0, "metric": "weekly",
                 "kind": "threshold", "title": "AI Status", "body": "Codex: 95% of weekly quota used."}
        with patch.object(tray.notifications, "process") as evaluate:
            self.dashboard.on_result("codex", providers)
        self.assertIs(evaluate.call_args.args[0], providers)
        self.assertEqual(evaluate.call_args.kwargs["deliver"], self.dashboard.deliver_notification)
        with patch.object(tray.QSystemTrayIcon, "supportsMessages", return_value=True), \
             patch.object(self.dashboard.tray, "showMessage") as show:
            self.assertTrue(self.dashboard.deliver_notification(event))
        show.assert_called_once_with(event["title"], event["body"], tray.QSystemTrayIcon.MessageIcon.Warning, 10_000)
        with patch.object(self.dashboard, "show_dashboard") as open_dashboard:
            self.dashboard.tray.messageClicked.emit()
        open_dashboard.assert_called_once()
        self.assertEqual(state.load_selected()["metric"], "weekly")
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)

    def test_unsupported_or_failed_notification_is_not_accepted(self):
        event = {"kind": "recovery", "title": "AI Status", "body": "Quota available."}
        with patch.object(tray.QSystemTrayIcon, "supportsMessages", return_value=False), \
             patch.object(self.dashboard.tray, "showMessage") as show:
            self.assertFalse(self.dashboard.deliver_notification(event))
        show.assert_not_called()
        with patch.object(tray.QSystemTrayIcon, "supportsMessages", return_value=True), \
             patch.object(self.dashboard.tray, "showMessage", side_effect=RuntimeError("Unavailable")), \
             self.assertLogs(level="ERROR"):
            self.assertFalse(self.dashboard.deliver_notification(event))
        self.assertIsNone(self.dashboard.last_notification)

    def test_recovery_notification_uses_information_icon(self):
        for kind in ("recovery", "partial_recovery"):
            event = {"kind": kind, "title": "AI Status", "body": "Quota available."}
            with patch.object(tray.QSystemTrayIcon, "supportsMessages", return_value=True), \
                 patch.object(self.dashboard.tray, "showMessage") as show:
                self.assertTrue(self.dashboard.deliver_notification(event))
            self.assertEqual(show.call_args.args[2], tray.QSystemTrayIcon.MessageIcon.Information)

    def test_completed_collection_adjusts_timer_for_reset(self):
        providers = [{"provider": "Codex", "_dir": "codex", "metrics": [{"type": "weekly", "percentage": 100}]}]
        self.dashboard.data = {"codex": providers}
        self.dashboard.worker = MagicMock()
        with patch.object(tray.notifications, "next_check_delay", return_value=42) as delay, \
             patch.object(tray.fetch, "get_version_info", return_value={"has_update": False}):
            self.dashboard.on_finished(providers)
        delay.assert_called_once_with(providers)
        self.assertEqual(self.dashboard.auto_refresh.interval(), 42_000)

    def test_incremental_dashboard_selection_and_cache_warning(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "_dir": "codex", "_idx": 0,
            "_cached": True, "_error": "Session expired", "metrics": [
                {"type": "rolling", "percentage": 120}, {"type": "weekly", "percentage": 10},
            ]}])
        self.assertEqual(len(self.dashboard.metric_values), 2)
        self.dashboard.metric_buttons[1].click()
        self.assertEqual(state.load_selected()["metric"], "weekly")
        self.assertIn("10%", self.dashboard.tray.toolTip())
        self.assertIn("cached", self.dashboard.tray.toolTip())
        labels = [item.text() for item in self.dashboard.scroll.widget().findChildren(QLabel)]
        self.assertTrue(any("Cached data" in text for text in labels))

    def test_failed_provider_is_hidden_from_usage_panel(self):
        self.dashboard.on_error("copilot", "<b>Sign in</b>")
        labels = self.dashboard.scroll.widget().findChildren(QLabel)
        self.assertFalse(any("Sign in" in label.text() or "copilot" in label.text().lower() for label in labels))
        self.assertEqual(self.dashboard.errors["copilot"], "<b>Sign in</b>")
        self.assertFalse(self.dashboard.metric_values)

    def test_no_providers_does_not_show_old_cache(self):
        config.save_config([])
        self.dashboard.draw()
        self.assertEqual(len(self.dashboard.metric_values), 0)
        self.assertIn("No usage", self.dashboard.tray.toolTip())

    def test_compact_panel_has_refresh_settings_and_project_identity(self):
        for button in (self.dashboard.refresh_button, self.dashboard.settings_button):
            self.assertEqual(button.width(), button.height())
        self.assertFalse(self.dashboard.windowIcon().isNull())
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)",
            "metrics": [{"type": "weekly", "percentage": 23}]}])
        self.assertLess(self.dashboard.height(), 300)
        self.assertTrue(self.dashboard.windowFlags() & tray.Qt.WindowType.FramelessWindowHint)
        labels = [label.text() for label in self.dashboard.scroll.widget().findChildren(QLabel)]
        self.assertIn("[", labels)
        self.assertIn("]", labels)
        self.assertIn("•", labels)
        self.assertIn("→", labels)

    def test_header_refresh_action_and_loading_state(self):
        with patch.object(state, "acquire_lock", return_value=True), patch.object(tray.threading, "Thread"):
            self.dashboard.refresh_button.click()
        self.assertTrue(self.dashboard.busy)
        self.assertFalse(self.dashboard.refresh_button.isEnabled())
        self.assertFalse(self.dashboard.refresh_action.isEnabled())
        self.assertTrue(self.dashboard.refresh_button.loading)
        with patch.object(tray.fetch, "get_version_info", return_value={"has_update": False}):
            self.dashboard.on_finished([])
        self.assertTrue(self.dashboard.refresh_button.isEnabled())
        self.assertFalse(self.dashboard.refresh_button.loading)
        self.assertEqual(self.dashboard.refresh_button.rotation, 0)

    def test_refresh_rotates_only_icon_and_pauses_when_hidden(self):
        button = tray.ControlButton("refresh-cw", "Refresh")
        self.addCleanup(button.deleteLater)
        button.show()
        button.setEnabled(False)
        button.set_loading(True)
        self.app.processEvents()
        button.spin.pause()
        button.spin.setCurrentTime(0)
        original = button.grab().toImage()
        button.spin.setCurrentTime(250)
        rotated = button.grab().toImage()
        self.assertNotEqual(original, rotated)
        self.assertEqual(button.rotation, 90)
        self.assertEqual(button.size(), tray.QSize(28, 28))
        self.assertEqual(original.pixel(2, 2), rotated.pixel(2, 2))
        button.hide()
        self.assertEqual(button.rotation, 0)
        self.assertEqual(button.spin.state(), tray.QVariantAnimation.State.Stopped)
        button.show()
        self.assertEqual(button.spin.state(), tray.QVariantAnimation.State.Running)
        button.set_loading(False)
        self.assertEqual(button.rotation, 0)
        self.assertEqual(button.spin.state(), tray.QVariantAnimation.State.Stopped)

    def test_header_control_outline_requires_tab_navigation_and_background_requires_hover(self):
        panel = tray.QWidget()
        self.addCleanup(panel.deleteLater)
        panel.setObjectName("panel")
        panel.setStyleSheet(tray.PANEL_STYLE)
        panel.resize(100, 100)
        button = tray.ControlButton("settings", "Configure")
        button.setParent(panel)
        button.move(16, 16)
        other = tray.QPushButton("Other", panel)
        other.move(50, 60)
        tray.QWidget.setTabOrder(button, other)
        clicked = MagicMock()
        button.clicked.connect(clicked)
        panel.show()
        self.app.processEvents()
        QTest.mouseMove(panel, tray.QPoint(90, 90))
        button.clearFocus()
        self.app.processEvents()
        idle = button.grab().toImage()
        background = idle.pixelColor(14, 4)
        self.assertEqual(background.alpha(), 0)
        self.assertEqual(idle.pixelColor(14, 0).alpha(), 0)

        button.setFocus()  # Programmatic focus never adds a visible outline.
        self.app.processEvents()
        self.assertTrue(button.hasFocus())
        self.assertEqual(button.grab().toImage(), idle)
        QTest.mouseMove(button, tray.QPoint(14, 14))
        self.app.processEvents()
        hovered = button.grab().toImage()
        self.assertGreater(hovered.pixelColor(14, 4).alpha(), background.alpha())
        QTest.mouseMove(panel, tray.QPoint(90, 90))

        other.setFocus()
        QTest.keyClick(other, tray.Qt.Key.Key_Tab)
        self.app.processEvents()
        self.assertTrue(button.hasFocus())
        focused = button.grab().toImage()
        self.assertEqual(focused.pixelColor(14, 4), background)
        self.assertGreater(focused.pixelColor(14, 0).alpha(), idle.pixelColor(14, 0).alpha())
        QTest.keyClick(button, tray.Qt.Key.Key_Return)
        QTest.keyClick(button, tray.Qt.Key.Key_Space)
        self.assertEqual(clicked.call_count, 2)
        button.setFocus()  # Also clear the outline if focus is already here.
        self.app.processEvents()
        self.assertEqual(button.grab().toImage(), idle)

        other.setFocus()
        QTest.keyClick(other, tray.Qt.Key.Key_Backtab)
        self.app.processEvents()
        self.assertTrue(button.hasFocus())
        self.assertEqual(button.grab().toImage(), focused)
        QTest.mouseMove(button, tray.QPoint(14, 14))
        QTest.mouseClick(button, tray.Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(clicked.call_count, 3)
        self.assertTrue(button.hasFocus())
        self.assertEqual(button.grab().toImage(), hovered)  # Clicking clears an existing Tab outline.
        QTest.mouseMove(panel, tray.QPoint(90, 90))
        self.app.processEvents()
        self.assertEqual(button.grab().toImage(), idle)

        QTest.mouseMove(button, tray.QPoint(14, 14))
        button.setEnabled(False)
        self.app.processEvents()
        disabled = button.grab().toImage()
        self.assertEqual(disabled.pixelColor(14, 4), background)
        self.assertEqual(disabled.pixelColor(14, 0).alpha(), 0)
        QTest.mouseClick(button, tray.Qt.MouseButton.LeftButton)
        self.assertEqual(clicked.call_count, 3)

    def test_about_is_last_settings_tab_preserves_drafts_and_opens_project_links(self):
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            self.app.processEvents()
            settings = self.dashboard.settings_view
            settings.icon_mode.setCurrentIndex(settings.icon_mode.findData("off"))
            settings.providers.move_provider(0, 1)
            order = [settings.providers.item(i).text() for i in range(settings.providers.count())]
            settings.select_section("providers")
            self.app.processEvents()
            scroll = self.dashboard.settings_scroll.verticalScrollBar()
            scroll.setValue(scroll.maximum())
            position = scroll.value()
            self.assertEqual(list(settings.section_buttons), ["general", "appearance", "alerts", "providers", "guide", "about"])
            settings.section_buttons["about"].click()
            self.assertTrue(self.dashboard.configuring())
            self.assertEqual(self.dashboard.brand.text(), "Settings")
            self.assertTrue(self.dashboard.settings_footer.isVisible())
            self.assertTrue(self.dashboard.settings_navigation.isVisible())
            about_view = settings.sections["about"]
            labels = [label.text() for label in about_view.findChildren(QLabel)]
            self.assertTrue(any("License: MIT" in text and "Author: gelzin.com" in text for text in labels))
            with patch.object(tray.QDesktopServices, "openUrl") as browser:
                about_view.findChild(tray.QPushButton, "about-issues").click()
                self.assertEqual(browser.call_args.args[0].toString(), tray.about.GITHUB + "/issues/new")
            settings.section_buttons["providers"].click()
            self.assertIs(self.dashboard.settings_view, settings)
            self.assertEqual(settings.current_section, "providers")
            self.assertEqual(settings.icon_mode.currentData(), "off")
            self.assertEqual([settings.providers.item(i).text() for i in range(settings.providers.count())], order)
            self.assertEqual(scroll.value(), position)
            self.dashboard.show_about()
            self.assertIs(self.dashboard.settings_view, settings)
            self.assertEqual(settings.current_section, "about")
            with patch.object(self.dashboard, "refresh"):
                settings.save_button.click()
            self.assertEqual(settings.current_section, "about")
            self.assertEqual(state.load_selected()["icon_mode"], "off")
            self.assertEqual(config.enabled_order(), ["copilot", "codex"])
            QTest.keyClick(self.dashboard, tray.Qt.Key.Key_Escape)
            self.assertFalse(self.dashboard.configuring())
            self.assertIs(self.dashboard.focusWidget(), self.dashboard.settings_button)

    def test_about_guide_link_opens_internal_table_preserves_draft_and_keyboard_reaches_footer(self):
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            self.app.processEvents()
            settings = self.dashboard.settings_view
            settings.select_section("appearance")
            settings.usage_display.setCurrentIndex(settings.usage_display.findData("remaining"))
            settings.select_section("alerts")
            settings.notification_levels.set_values([75, 90])
            settings.select_section("about")
            about_view = settings.sections["about"]
            links = [button for button in about_view.findChildren(tray.QPushButton)
                     if button.objectName().startswith("about-")]
            self.assertEqual([button.text() for button in links], ["Guide", "Report a bug", "Documentation", "GitHub"])
            self.assertNotIn("Quick guide", [label.text() for label in about_view.findChildren(QLabel)])
            links[0].setFocus()
            with patch.object(tray.QDesktopServices, "openUrl") as browser:
                QTest.keyClick(links[0], tray.Qt.Key.Key_Space)
            browser.assert_not_called()
            self.app.processEvents()
            self.assertIs(self.dashboard.settings_view, settings)
            self.assertEqual(settings.current_section, "guide")
            self.assertEqual(self.dashboard.brand.text(), "Settings")
            self.assertIs(self.dashboard.focusWidget(), settings.section_buttons["guide"])
            guide = settings.sections["guide"]
            self.assertEqual([label.text() for label in guide.cells[0]], ["Feature", "Action / shortcut"])
            self.assertEqual(guide.table.objectName(), "creditTable")
            self.assertTrue(all(label.wordWrap() for cells in guide.cells for label in cells))
            keycaps = {cap.text() for _, action in guide.cells[1:] for cap in action.keycaps}
            self.assertTrue({"R", "C", "Tab", "Shift+Tab", "Left", "Right", "Space", "Enter",
                             "Alt+Up", "Alt+Down", "Esc"}.issubset(keycaps))
            self.assertTrue({"Save", "Cancel", "Back"}.isdisjoint(keycaps))
            self.assertLessEqual(guide.table.width(), self.dashboard.settings_scroll.viewport().width())
            self.assertEqual(self.dashboard.settings_scroll.horizontalScrollBar().maximum(), 0)
            scroll = self.dashboard.settings_scroll.verticalScrollBar()
            self.assertGreater(scroll.maximum(), 0)
            scroll.setValue(scroll.maximum())
            self.assertTrue(self.dashboard.settings_navigation.isVisible())
            self.assertTrue(self.dashboard.settings_footer.isVisible())
            QTest.keyClick(settings.section_buttons["guide"], tray.Qt.Key.Key_Tab)
            self.assertIs(self.dashboard.focusWidget(), settings.cancel_button)
            QTest.keyClick(settings.cancel_button, tray.Qt.Key.Key_Backtab)
            self.assertIs(self.dashboard.focusWidget(), settings.section_buttons["guide"])
            settings.section_buttons["appearance"].click()
            self.assertEqual(settings.usage_display.currentData(), "remaining")
            settings.section_buttons["alerts"].click()
            self.assertEqual(settings.notification_levels.values(), [75, 90])
            self.assertEqual(state.get_usage_display(state.load_selected()), "used")
            self.assertEqual(tray.notifications.load_settings()["thresholds"], [80, 95, 100])

    def test_startup_switch_supports_native_checkbox_api_mouse_keyboard_and_save(self):
        with patch.object(paths, "IS_WINDOWS", True), \
             patch.object(tray, "startup_enabled", return_value=False), \
             patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            self.app.processEvents()
            settings = self.dashboard.settings_view
            switch = settings.startup
            self.assertIsInstance(switch, tray.QCheckBox)
            self.assertEqual(switch.accessibleName(), "Start when I sign in to Windows")
            self.assertFalse(switch.isChecked())
            toggled = MagicMock()
            switch.toggled.connect(toggled)
            # The entire track accepts clicks, including outside the native indicator.
            QTest.mouseClick(switch, tray.Qt.MouseButton.LeftButton, pos=tray.QPoint(switch.width() - 3, switch.height() // 2))
            self.assertTrue(switch.isChecked())
            toggled.assert_called_once_with(True)
            switch.setFocus(tray.Qt.FocusReason.TabFocusReason)
            QTest.keyClick(switch, tray.Qt.Key.Key_Space)
            self.assertFalse(switch.isChecked())
            switch.setChecked(True)
            settings.select_section("about")
            with patch.object(tray, "set_startup") as apply_startup, patch.object(self.dashboard, "refresh"):
                settings.save_button.click()
            apply_startup.assert_called_once_with(True)
            self.assertEqual(settings.current_section, "about")
            settings.cancel_button.click()
            with patch.object(tray, "startup_enabled", return_value=True):
                self.dashboard.configure()
            reopened = self.dashboard.settings_view
            self.assertTrue(reopened.startup.isChecked())
            self.assertEqual(reopened.current_section, "general")

    def test_settings_save_stays_in_panel_and_back_is_before_title(self):
        # Offscreen backends do not consistently activate Tool windows on Windows.
        active_window = patch.object(self.dashboard, "isActiveWindow", return_value=True)
        active_window.start()
        self.addCleanup(active_window.stop)
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "rolling", "percentage": 2}, {"type": "weekly", "percentage": 23}]}])
        self.dashboard.on_result("copilot", [{"provider": "Copilot", "metrics": [
            {"type": "monthly", "percentage": 7}]}])
        self.dashboard.show()
        self.app.processEvents()
        QTest.mouseClick(self.dashboard.settings_button, tray.Qt.MouseButton.LeftButton)
        self.app.processEvents()
        settings = self.dashboard.settings_view
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.settings_scroll)
        self.assertEqual(self.dashboard.brand.text(), "Settings")
        self.assertLess(self.dashboard.back_button.geometry().right(), self.dashboard.brand.geometry().left())
        self.assertTrue(self.dashboard.refresh_button.isHidden())
        self.assertTrue(self.dashboard.settings_button.isHidden())
        settings.active.setCurrentIndex(settings.active.findData(["codex", 0, "weekly"]))
        for i in range(settings.active.count()):
            self.assertTrue(tray.icon_has_pixels(settings.active.itemIcon(i)))
        self.assertEqual(settings.active.currentData()[0], "codex")
        self.assertEqual(settings.active.itemIcon(settings.active.currentIndex()).cacheKey(), tray.provider_icon("codex").cacheKey())
        settings.display["show_provider"].setChecked(False)
        settings.icon_mode.setCurrentIndex(settings.icon_mode.findData("logo"))
        settings.usage_display.setCurrentIndex(settings.usage_display.findData("remaining"))
        with patch.object(self.dashboard, "refresh") as refresh:
            QTest.mouseClick(settings.save_button, tray.Qt.MouseButton.LeftButton)
        refresh.assert_called_once()
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.settings_scroll)
        self.assertEqual(settings.message.text(), "Saved")
        selected = state.load_selected()
        self.assertEqual(selected["metric"], "weekly")
        self.assertEqual(selected["icon_mode"], "logo")
        self.assertEqual(selected["usage_display"], "remaining")
        self.assertFalse(selected["show_provider"])
        self.assertTrue(self.dashboard.isVisible())
        self.dashboard.back_button.click()
        self.app.processEvents()
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
        self.assertEqual(self.dashboard.brand.text(), "AI Status")
        self.assertIs(self.dashboard.focusWidget(), self.dashboard.settings_button)

    def test_provider_selector_popup_does_not_dismiss_settings(self):
        self.dashboard.configure()
        self.app.processEvents()
        popup = self.dashboard.settings_view.active.view()
        with patch.object(self.dashboard, "isActiveWindow", return_value=False), patch.object(QApplication, "activePopupWidget", return_value=popup):
            QApplication.sendEvent(self.dashboard, tray.QEvent(tray.QEvent.Type.ActivationChange))
        self.assertTrue(self.dashboard.isVisible())
        self.assertTrue(self.dashboard.configuring())

    def test_settings_sections_share_draft_and_save_all_sections_from_alerts(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "metrics": [
            {"type": "rolling", "percentage": 2}, {"type": "weekly", "percentage": 23}]}])
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        self.assertEqual(settings.current_section, "general")
        settings.active.setCurrentIndex(settings.active.findData(["codex", 0, "weekly"]))
        settings.section_buttons["appearance"].click()
        settings.usage_display.setCurrentIndex(settings.usage_display.findData("remaining"))
        settings.icon_mode.setCurrentIndex(settings.icon_mode.findData("logo"))
        settings.display["show_metric"].setChecked(True)
        settings.section_buttons["providers"].click()
        settings.providers.move_provider(0, 1)
        settings.section_buttons["alerts"].click()
        settings.notification_advanced_button.setChecked(True)
        self.assertIn("Weekly", settings.notification_rule_label.text())
        settings.notification_rule_custom.setChecked(True)
        settings.notification_rule_thresholds.setText("85, 99")
        settings.section_buttons["general"].click()
        self.assertEqual(settings.current_section, "general")
        settings.section_buttons["alerts"].click()
        self.assertEqual(settings.notification_rule_thresholds.text(), "85, 99")
        self.assertEqual(config.enabled_order(), ["codex", "copilot"])
        self.assertEqual(state.get_usage_display(state.load_selected()), "used")
        with patch.object(self.dashboard, "refresh") as refresh:
            settings.save_button.click()
        refresh.assert_called_once()
        self.assertEqual(settings.current_section, "alerts")
        self.assertEqual(settings.message.text(), "Saved")
        self.assertEqual(config.enabled_order(), ["copilot", "codex"])
        selected = state.load_selected()
        self.assertEqual((selected["provider"], selected["metric"], selected["usage_display"], selected["icon_mode"]),
                         ("codex", "weekly", "remaining", "logo"))
        self.assertTrue(selected["show_metric"])
        self.assertEqual(tray.notifications.load_settings()["rules"][0]["thresholds"], [85, 99])

    def test_settings_cancel_discards_cross_section_draft_and_reopens_general(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        settings.select_section("appearance")
        settings.usage_display.setCurrentIndex(settings.usage_display.findData("remaining"))
        settings.select_section("providers")
        settings.providers.item(0).setCheckState(tray.Qt.CheckState.Unchecked)
        settings.select_section("alerts")
        settings.notification_levels.set_values([75, 90])
        settings.cancel_button.click()
        self.assertFalse(self.dashboard.configuring())
        self.assertTrue(self.dashboard.settings_navigation.isHidden())
        self.dashboard.configure()
        reopened = self.dashboard.settings_view
        self.assertIsNot(reopened, settings)
        self.assertEqual(reopened.current_section, "general")
        self.assertEqual(reopened.usage_display.currentData(), "used")
        self.assertEqual(reopened.providers.item(0).checkState(), tray.Qt.CheckState.Checked)
        self.assertEqual(reopened.notification_levels.values(), [80, 95, 100])

    def test_settings_keyboard_navigation_reveals_controls_and_keeps_navigation_and_footer_fixed(self):
        # Qt Tool windows need an explicit active-window fixture offscreen.
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            self.app.processEvents()
            settings = self.dashboard.settings_view
            self.assertIs(self.dashboard.focusWidget(), settings.section_buttons["general"])
            QTest.keyClick(settings.section_buttons["general"], tray.Qt.Key.Key_Right)
            self.assertEqual(settings.current_section, "appearance")
            self.assertIs(self.dashboard.focusWidget(), settings.section_buttons["appearance"])
            QTest.keyClick(settings.section_buttons["appearance"], tray.Qt.Key.Key_Tab)
            self.assertIs(self.dashboard.focusWidget(), settings.usage_display)
            settings.section_buttons["alerts"].setFocus()
            QTest.keyClick(settings.section_buttons["alerts"], tray.Qt.Key.Key_Space)
            self.app.processEvents()
            self.assertEqual(settings.current_section, "alerts")
            settings.notification_advanced_button.setChecked(True)
            self.app.processEvents()
            navigation_position = self.dashboard.settings_navigation.pos()
            footer_position = self.dashboard.settings_footer.pos()
            settings.notification_rule_custom.setChecked(True)
            settings.notification_rule_enabled.setFocus(tray.Qt.FocusReason.TabFocusReason)
            QTest.keyClick(settings.notification_rule_enabled, tray.Qt.Key.Key_Tab)
            self.app.processEvents()
            self.assertIs(self.dashboard.focusWidget(), settings.notification_rule_thresholds)
            viewport = self.dashboard.settings_scroll.viewport()
            field = settings.notification_rule_thresholds
            self.assertTrue(viewport.rect().contains(tray.QRectF(field.mapTo(viewport, tray.QPoint()), field.size()).toRect()))
            self.assertEqual(self.dashboard.settings_navigation.pos(), navigation_position)
            self.assertEqual(self.dashboard.settings_footer.pos(), footer_position)
            self.assertEqual(self.dashboard.settings_scroll.horizontalScrollBar().maximum(), 0)
            self.assertLessEqual(settings.width(), viewport.width())
            QTest.keyClick(field, tray.Qt.Key.Key_Tab)
            self.assertIs(self.dashboard.focusWidget(), settings.cancel_button)

    def test_settings_restores_section_scroll_and_validation_opens_relevant_section(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        settings.select_section("providers")
        self.app.processEvents()
        scroll = self.dashboard.settings_scroll.verticalScrollBar()
        scroll.setValue(scroll.maximum())
        position = scroll.value()
        self.assertGreater(position, 0)
        settings.select_section("general")
        self.assertEqual(scroll.value(), 0)
        settings.select_section("providers")
        self.app.processEvents()
        self.assertEqual(scroll.value(), position)
        settings.notification_levels.set_values([80, 80])
        with patch.object(config, "save_connection_order") as save_order:
            settings.save_button.click()
        self.assertEqual(settings.current_section, "alerts")
        self.assertIn("threshold", settings.message.text())
        save_order.assert_not_called()
        settings.notification_levels.set_values([80, 95, 100])
        for checkbox in settings.display.values():
            checkbox.setChecked(False)
        with patch.object(config, "save_connection_order") as save_order:
            settings.save_button.click()
        self.assertEqual(settings.current_section, "appearance")
        self.assertIn("text field", settings.message.text())
        save_order.assert_not_called()

    def test_settings_single_row_tabs_scroll_in_narrow_viewport_and_reveal_selected_or_focused_tab(self):
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            self.app.processEvents()
            settings = self.dashboard.settings_view
            navigation = settings.navigation
            self.assertGreater(navigation.horizontalScrollBar().maximum(), 0)
            navigation.setFixedWidth(220)
            self.app.processEvents()
            bar = navigation.horizontalScrollBar()
            self.assertGreater(bar.maximum(), 0)
            self.assertFalse(bar.isVisible())
            buttons = list(settings.section_buttons.values())
            self.assertEqual(len({button.y() for button in buttons}), 1)
            self.assertGreater(buttons[1].width(), buttons[2].width())
            self.assertLess(buttons[0].width(), navigation.viewport().width())
            settings.section_buttons["general"].setFocus()
            for _ in range(3):
                QTest.keyClick(self.dashboard.focusWidget(), tray.Qt.Key.Key_Right)
                self.app.processEvents()
            self.assertEqual(settings.current_section, "providers")
            providers_tab = settings.section_buttons["providers"]
            self.assertIs(self.dashboard.focusWidget(), providers_tab)
            self.assertTrue(navigation.viewport().rect().contains(
                tray.QRectF(providers_tab.mapTo(navigation.viewport(), tray.QPoint()), providers_tab.size()).toRect()))
            self.assertGreater(bar.value(), 0)
            QTest.keyClick(providers_tab, tray.Qt.Key.Key_Right)
            self.app.processEvents()
            self.assertEqual(settings.current_section, "guide")
            guide_tab = settings.section_buttons["guide"]
            self.assertIs(self.dashboard.focusWidget(), guide_tab)
            QTest.keyClick(guide_tab, tray.Qt.Key.Key_Right)
            self.app.processEvents()
            self.assertEqual(settings.current_section, "about")
            about_tab = settings.section_buttons["about"]
            self.assertIs(self.dashboard.focusWidget(), about_tab)
            self.assertTrue(navigation.viewport().rect().contains(
                tray.QRectF(about_tab.mapTo(navigation.viewport(), tray.QPoint()), about_tab.size()).toRect()))
            QTest.keyClick(about_tab, tray.Qt.Key.Key_Left)
            self.assertEqual(settings.current_section, "guide")
            QTest.keyClick(guide_tab, tray.Qt.Key.Key_Left)
            self.assertEqual(settings.current_section, "providers")
            general_tab = settings.section_buttons["general"]
            general_tab.setFocus()
            self.app.processEvents()
            self.assertEqual(bar.value(), 0)
            self.assertEqual(settings.current_section, "providers")
            content = self.dashboard.settings_scroll
            content.verticalScrollBar().setValue(0)
            point = tray.QPoint(10, 10)
            event = QWheelEvent(tray.QPointF(point), tray.QPointF(navigation.viewport().mapToGlobal(point)),
                                tray.QPoint(), tray.QPoint(0, -120), tray.Qt.MouseButton.NoButton,
                                tray.Qt.KeyboardModifier.NoModifier, tray.Qt.ScrollPhase.NoScrollPhase, False)
            QApplication.sendEvent(navigation.viewport(), event)
            self.assertTrue(event.isAccepted())
            self.assertGreater(bar.value(), 0)
            self.assertEqual(content.verticalScrollBar().value(), 0)
            self.assertEqual(settings.current_section, "providers")
            event = QWheelEvent(tray.QPointF(point), tray.QPointF(content.viewport().mapToGlobal(point)),
                                tray.QPoint(), tray.QPoint(0, -120), tray.Qt.MouseButton.NoButton,
                                tray.Qt.KeyboardModifier.NoModifier, tray.Qt.ScrollPhase.NoScrollPhase, False)
            tab_position = bar.value()
            QApplication.sendEvent(content.viewport(), event)
            self.app.processEvents()
            self.assertGreater(content.verticalScrollBar().value(), 0)
            self.assertEqual(bar.value(), tab_position)

    def test_settings_viewports_reach_panel_edges_and_padding_scrolls_with_content(self):
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            self.app.processEvents()
            settings = self.dashboard.settings_view
            navigation = settings.navigation
            viewport = navigation.viewport()
            self.assertEqual(viewport.width(), self.dashboard.width() - 2)
            self.assertEqual(viewport.mapTo(self.dashboard, tray.QPoint()).x(), 1)
            tabs_scroll = navigation.horizontalScrollBar()
            tabs_scroll.setValue(0)
            first_tab = settings.section_buttons["general"]
            self.assertEqual(first_tab.mapTo(viewport, tray.QPoint()).x(), 16)
            tabs_scroll.setValue(tabs_scroll.maximum())
            last_tab = settings.section_buttons["about"]
            last_edge = last_tab.mapTo(viewport, tray.QPoint()).x() + last_tab.width()
            self.assertEqual(viewport.width() - last_edge, 16)
            self.assertLess(first_tab.mapTo(viewport, tray.QPoint()).x(), 0)
            settings.select_section("providers")
            self.app.processEvents()
            content = self.dashboard.settings_scroll
            content_viewport = content.viewport()
            viewport_top = content_viewport.mapTo(self.dashboard, tray.QPoint()).y()
            self.assertEqual(viewport_top, self.dashboard.settings_navigation.mapTo(self.dashboard, tray.QPoint()).y())
            self.assertEqual(viewport_top + content_viewport.height(), self.dashboard.settings_footer.y())
            section = settings.sections["providers"]
            scroll = content.verticalScrollBar()
            scroll.setValue(0)
            self.assertEqual(section.mapTo(content_viewport, tray.QPoint()).y(), self.dashboard.settings_scroll.covered_height + 18)
            scroll.setValue(scroll.maximum())
            section_bottom = section.mapTo(content_viewport, tray.QPoint(0, section.height())).y()
            self.assertEqual(content_viewport.height() - section_bottom, 18)
            scroll.setValue(scroll.maximum() // 2)
            self.assertLess(settings.mapTo(content_viewport, tray.QPoint()).y(), 0)
            self.assertGreater(settings.mapTo(content_viewport, tray.QPoint(0, settings.height())).y(), content_viewport.height())
            self.assertEqual(content_viewport.mapTo(self.dashboard, tray.QPoint()).y(), viewport_top)
            self.assertEqual(viewport_top + content_viewport.height(), self.dashboard.settings_footer.y())

    def test_settings_escape_and_cancel_discard_only_unsaved_changes(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        self.assertEqual(settings.usage_display.currentData(), "used")
        settings.usage_display.setCurrentIndex(settings.usage_display.findData("remaining"))
        settings.display["show_metric"].setChecked(True)
        with patch.object(self.dashboard, "refresh"):
            settings.save()
        saved = state.load_selected()
        settings.display["show_metric"].setChecked(False)
        settings.usage_display.setCurrentIndex(settings.usage_display.findData("used"))
        QTest.keyClick(settings.active, tray.Qt.Key.Key_Escape)
        self.assertFalse(self.dashboard.configuring())
        self.assertEqual(state.load_selected(), saved)
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        self.assertTrue(settings.display["show_metric"].isChecked())
        self.assertEqual(settings.usage_display.currentData(), "remaining")
        settings.providers.item(0).setCheckState(tray.Qt.CheckState.Unchecked)
        settings.cancel_button.click()
        self.assertFalse(self.dashboard.configuring())
        self.assertEqual(config.enabled_order(), ["codex", "copilot"])

    def test_remaining_usage_updates_values_bars_accessibility_and_tooltip(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "_dir": "codex", "_idx": 0,
            "metrics": [{"type": "weekly", "percentage": 23},
                        {"type": "monthly", "percentage": 25, "amount": 25, "limit": 100,
                         "unit": "USD", "value_format": "amount_ratio"},
                        {"type": "balance", "amount": 42.5, "unit": "USD"}]}])
        rows = self.dashboard.metric_buttons[:]
        self.assertEqual(rows[0].percentage.text(), "23%")
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        settings.usage_display.setCurrentIndex(settings.usage_display.findData("remaining"))
        with patch.object(self.dashboard, "refresh"):
            settings.save()
        # Updating the preference reuses the rows and changes every usage surface.
        self.assertEqual(self.dashboard.metric_buttons, rows)
        self.assertEqual(rows[0].title.text(), "Weekly Remaining")
        self.assertEqual(rows[0].percentage.text(), "77%")
        self.assertEqual(rows[0].bar.target, 77)
        self.assertIn("Weekly Remaining 77%", rows[0].accessibleName())
        self.assertIn("77%", self.dashboard.tray.toolTip())
        self.assertEqual(rows[1].percentage.text(), "$75.00 / $100.00")
        self.assertEqual(rows[1].bar.target, 75)
        self.assertEqual(rows[2].percentage.text(), "$42.50")
        self.assertTrue(rows[2].bar_container.isHidden())
        self.dashboard.show_usage()
        self.dashboard.configure()
        self.assertEqual(self.dashboard.settings_view.usage_display.currentData(), "remaining")

    def test_settings_failure_keeps_draft_open_and_does_not_refresh(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        settings.display["show_metric"].setChecked(True)
        with patch.object(config, "save_config", side_effect=OSError("read only")), patch.object(self.dashboard, "refresh") as refresh:
            settings.save()
        refresh.assert_not_called()
        self.assertTrue(self.dashboard.configuring())
        self.assertTrue(settings.display["show_metric"].isChecked())
        self.assertIn("Unable to save", settings.message.text())
        self.assertFalse((state.load_selected() or {}).get("show_metric", False))

    def test_notification_settings_keep_account_limit_drafts_and_roundtrip_controls(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "metrics": [
            {"type": "rolling", "percentage": 2}, {"type": "weekly", "percentage": 23}]}])
        self.dashboard.configure()
        self.app.processEvents()
        settings = self.dashboard.settings_view
        self.assertLessEqual(settings.width(), self.dashboard.settings_scroll.viewport().width())
        settings.notification_advanced_button.setChecked(True)
        settings.notification_levels.set_values([75, 90, 100])
        settings.notifications_recovery.setChecked(False)
        settings.notifications_recent_only.setChecked(True)
        settings.notification_quiet_start.setText("22:00")
        settings.notification_quiet_end.setText("07:00")
        settings.notification_work_start.setText("09:00")
        settings.notification_work_end.setText("18:00")
        settings.notification_mute.setChecked(True)
        settings.active.setCurrentIndex(settings.active.findData(["codex", 0, "weekly"]))
        self.assertIn("Weekly", settings.notification_rule_label.text())
        settings.notification_rule_custom.setChecked(True)
        settings.notification_rule_thresholds.setText("85, 99")
        settings.active.setCurrentIndex(settings.active.findData(["codex", 0, "rolling"]))
        settings.notification_rule_custom.setChecked(True)
        settings.notification_rule_enabled.setChecked(False)
        settings.notification_rule_thresholds.setText("80")
        settings.active.setCurrentIndex(settings.active.findData(["codex", 0, "weekly"]))
        self.assertEqual(settings.notification_rule_thresholds.text(), "85, 99")
        settings.usage_display.setCurrentIndex(settings.usage_display.findData("remaining"))
        self.assertEqual(settings.notification_rule_thresholds.text(), "85, 99")
        with patch.object(self.dashboard, "refresh"), patch.object(tray.time, "time", return_value=1000):
            settings.save()
        self.assertEqual(settings.message.text(), "Saved")
        saved = tray.notifications.load_settings()
        self.assertEqual(saved["thresholds"], [75, 90, 100])
        self.assertFalse(saved["recovery"])
        self.assertTrue(saved["recent_only"])
        self.assertEqual(saved["muted_until"], 4600)
        self.assertEqual(saved["quiet_hours"], {"start": "22:00", "end": "07:00"})
        self.assertEqual(saved["work_hours"], {"start": "09:00", "end": "18:00"})
        rules = {(rule["connection_id"], rule["metric"]): rule for rule in saved["rules"]}
        self.assertEqual(rules[("codex", "weekly")]["thresholds"], [85, 99])
        self.assertFalse(rules[("codex", "rolling")]["enabled"])
        settings.notification_mute.setChecked(False)
        with patch.object(self.dashboard, "refresh"):
            settings.save()
        self.assertEqual(tray.notifications.load_settings()["muted_until"], 0)

    def test_alerts_switches_and_native_level_sliders_support_keyboard_add_remove_and_save(self):
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            settings = self.dashboard.settings_view
            settings.select_section("alerts")
            self.app.processEvents()
            self.assertIsInstance(settings.notifications_enabled, tray.ToggleSwitch)
            self.assertIsInstance(settings.notification_mute, tray.ToggleSwitch)
            self.assertTrue(settings.notification_advanced.isHidden())
            self.assertFalse(hasattr(settings, "notification_change_limit"))
            visible_labels = [label.text() for label in settings.sections["alerts"].findChildren(QLabel)
                              if label.isVisible()]
            self.assertIn("Quota notifications", visible_labels)
            self.assertNotIn("Active account & limit", visible_labels)
            levels = settings.notification_levels
            self.assertEqual(levels.values(), [80, 95, 100])
            first = levels.sliders[0]
            first.setFocus()
            QTest.keyClick(first, tray.Qt.Key.Key_Home)
            self.assertEqual(first.value(), 1)
            QTest.keyClick(first, tray.Qt.Key.Key_End)
            self.assertEqual(first.value(), 100)
            QTest.keyClick(first, tray.Qt.Key.Key_Left)
            self.assertEqual(first.value(), 99)
            self.assertIs(self.dashboard.focusWidget(), first)
            self.assertIn("99%", [label.text() for label in levels.level_rows[0].findChildren(QLabel)])
            QTest.keyClick(first, tray.Qt.Key.Key_Tab)
            remove = levels.level_rows[0].findChild(tray.QPushButton)
            self.assertIs(self.dashboard.focusWidget(), remove)
            QTest.keyClick(remove, tray.Qt.Key.Key_Space)
            self.assertEqual(levels.values(), [95, 100])
            self.assertIs(self.dashboard.focusWidget(), levels.sliders[0])
            self.assertEqual(levels.sliders[0].accessibleName(), "Notification level 1")
            levels.add_button.setFocus()
            QTest.keyClick(levels.add_button, tray.Qt.Key.Key_Space)
            self.assertEqual(len(levels.sliders), 3)
            self.assertEqual(len(set(levels.values())), 3)
            self.assertIs(self.dashboard.focusWidget(), levels.sliders[-1])
            levels.set_values([75, 90, 100])
            settings.notifications_enabled.setFocus()
            QTest.keyClick(settings.notifications_enabled, tray.Qt.Key.Key_Space)
            settings.notification_mute.setFocus()
            QTest.keyClick(settings.notification_mute, tray.Qt.Key.Key_Space)
            with patch.object(self.dashboard, "refresh"):
                settings.save_button.click()
            saved = tray.notifications.load_settings()
            self.assertEqual(saved["thresholds"], [75, 90, 100])
            self.assertFalse(saved["enabled"])
            self.assertGreater(saved["muted_until"], time.time())

    def test_advanced_notification_disclosure_preserves_drafts_and_opens_on_invalid_save(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        settings.select_section("alerts")
        settings.notification_advanced_button.setFocus()
        QTest.keyClick(settings.notification_advanced_button, tray.Qt.Key.Key_Space)
        self.assertFalse(settings.notification_advanced.isHidden())
        settings.notification_quiet_start.setText("22:00")
        settings.notification_quiet_end.setText("07:00")
        settings.notification_rule_custom.setChecked(True)
        settings.notification_rule_thresholds.setText("85, 99")
        QTest.keyClick(settings.notification_advanced_button, tray.Qt.Key.Key_Space)
        self.assertTrue(settings.notification_advanced.isHidden())
        settings.select_section("appearance")
        settings.select_section("alerts")
        settings.notification_advanced_button.click()
        self.assertEqual(settings.notification_quiet_start.text(), "22:00")
        self.assertEqual(settings.notification_rule_thresholds.text(), "85, 99")
        settings.notification_quiet_start.setText("25:00")
        settings.notification_advanced_button.click()
        self.assertTrue(settings.notification_advanced.isHidden())
        with patch.object(tray.notifications, "save_settings") as save:
            settings.save_button.click()
        save.assert_not_called()
        self.assertFalse(settings.notification_advanced.isHidden())
        self.assertIn("quiet_hours", settings.message.text())

    def test_settings_content_alpha_fade_preserves_color_and_overlay_routes_clicks_and_focus(self):
        sample = QPixmap(40, 100)
        original = QColor(240, 80, 30)
        sample.fill(original)
        masked = tray.SettingsFadeEffect.masked_source(sample, 10, 20).toImage()
        self.assertEqual(masked.pixelColor(20, 15).alpha(), 0)
        fading = masked.pixelColor(20, 39)
        self.assertGreater(fading.alpha(), 0)
        self.assertLess(fading.alpha(), 255)
        self.assertLessEqual(abs(fading.red() - original.red()), 1)
        self.assertLessEqual(abs(fading.green() - original.green()), 1)
        self.assertLessEqual(abs(fading.blue() - original.blue()), 1)
        self.assertEqual(masked.pixelColor(20, 70), original)
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            settings = self.dashboard.settings_view
            settings.select_section("providers")
            self.app.processEvents()
            scroll = self.dashboard.settings_scroll
            self.assertIs(settings.graphicsEffect(), scroll.fade)
            self.assertEqual(settings.layout().contentsMargins().top(), scroll.covered_height + 18)
            self.assertEqual(scroll.viewport().mapTo(self.dashboard, tray.QPoint()).y(),
                             self.dashboard.settings_navigation.mapTo(self.dashboard, tray.QPoint()).y())
            scroll.verticalScrollBar().setValue(100)
            self.app.processEvents()
            tab = settings.section_buttons["providers"]
            point = tab.mapTo(scroll, tab.rect().center())
            self.assertIs(scroll.childAt(point), tab)
            QTest.mouseClick(tab, tray.Qt.MouseButton.LeftButton)
            self.assertEqual(settings.current_section, "providers")
            settings.providers.setCurrentRow(0)
            settings.providers.setFocus(tray.Qt.FocusReason.TabFocusReason)
            self.app.processEvents()
            rect = settings.providers.visualItemRect(settings.providers.item(0))
            top = settings.providers.viewport().mapTo(scroll.viewport(), rect.topLeft()).y()
            self.assertGreaterEqual(top, scroll.covered_height + 18)
            self.assertGreaterEqual(self.dashboard.settings_footer.height(), 49)

    def test_invalid_notification_settings_are_rejected_before_any_save(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        for thresholds in ([80, 80], [75, 90, 90]):
            settings.notification_levels.set_values(thresholds)
            with patch.object(config, "save_connection_order") as save_order, \
                 patch.object(state, "_save_json") as save_selection, \
                 patch.object(tray.notifications, "save_settings") as save_notifications:
                settings.save()
            save_order.assert_not_called()
            save_selection.assert_not_called()
            save_notifications.assert_not_called()
            self.assertTrue(settings.message.text())
            self.assertNotEqual(settings.message.text(), "Saved")
        settings.notification_levels.set_values([80, 95, 100])
        settings.notification_quiet_start.setText("25:00")
        settings.notification_quiet_end.setText("07:00")
        with patch.object(tray.notifications, "save_settings") as save_notifications:
            settings.save()
        save_notifications.assert_not_called()

    def test_invalid_notification_override_draft_survives_selection_changes(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "metrics": [
            {"type": "rolling", "percentage": 2}, {"type": "weekly", "percentage": 23}]}])
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        settings.notification_advanced_button.setChecked(True)
        settings.active.setCurrentIndex(settings.active.findData(["codex", 0, "weekly"]))
        settings.notification_rule_custom.setChecked(True)
        settings.notification_rule_thresholds.setText("unfinished")
        settings.active.setCurrentIndex(settings.active.findData(["codex", 0, "rolling"]))
        settings.active.setCurrentIndex(settings.active.findData(["codex", 0, "weekly"]))
        self.assertTrue(settings.notification_rule_custom.isChecked())
        self.assertEqual(settings.notification_rule_thresholds.text(), "unfinished")
        with patch.object(tray.notifications, "save_settings") as save_notifications:
            settings.save()
        save_notifications.assert_not_called()
        self.assertIn("levels", settings.message.text())

    def test_invalid_other_account_rules_are_reviewed_without_changing_the_bar_selection(self):
        config.save_config(["codex", "claude"])
        for provider in ("codex", "claude"):
            self.dashboard.on_result(provider, [{"provider": provider.title(), "metrics": [
                {"type": "weekly", "percentage": 2}]}])
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            settings = self.dashboard.settings_view
            settings.select_section("alerts")
            settings.notification_advanced_button.setChecked(True)
            settings.notification_rule_custom.setChecked(True)
            settings.notification_rule_thresholds.setText("unfinished")
            settings.select_section("general")
            settings.active.setCurrentIndex(settings.active.findData(["claude", 0, "weekly"]))
            selected = settings.active.currentData()
            settings.select_section("alerts")
            self.assertEqual(settings.notification_rule_choice, ("codex", "weekly"))
            self.assertEqual(settings.notification_rule_thresholds.text(), "unfinished")
            self.assertFalse(settings.notification_advanced.isHidden())
            with patch.object(config, "save_connection_order") as save_order:
                settings.save_button.click()
            save_order.assert_not_called()
            self.assertIn("Codex", settings.message.text())
            self.assertIn("Weekly", settings.message.text())
            self.assertIs(self.dashboard.focusWidget(), settings.notification_rule_thresholds)
            self.assertEqual(settings.active.currentData(), selected)
            settings.notification_rule_selector.setCurrentIndex(
                settings.notification_rule_selector.findData(["claude", "weekly"]))
            settings.notification_rule_custom.setChecked(True)
            settings.notification_rule_thresholds.setText("another unfinished rule")
            self.app.processEvents()
            review = next(button for button in settings.notification_rule_reviews.findChildren(tray.SettingsLinkButton)
                          if button.isVisible() and "Codex" in button.accessibleName())
            QTest.keyClick(review, tray.Qt.Key.Key_Space)
            self.assertEqual(settings.notification_rule_choice, ("codex", "weekly"))
            self.assertIs(self.dashboard.focusWidget(), settings.notification_rule_thresholds)
            self.assertEqual(settings.active.currentData(), selected)
            settings.notification_rule_thresholds.setText("85, 99")
            self.app.processEvents()
            review = next(button for button in settings.notification_rule_reviews.findChildren(tray.SettingsLinkButton)
                          if button.isVisible() and "Claude" in button.accessibleName())
            review.click()
            self.assertEqual(settings.notification_rule_thresholds.text(), "another unfinished rule")
            settings.notification_rule_thresholds.setText("90")
            with patch.object(self.dashboard, "refresh"):
                settings.save_button.click()
            self.assertEqual(state.load_selected()["provider"], "claude")
            rules = {(rule["connection_id"], rule["metric"]): rule["thresholds"]
                     for rule in tray.notifications.load_settings()["rules"]}
            self.assertEqual(rules[("codex", "weekly")], [85, 99])
            self.assertEqual(rules[("claude", "weekly")], [90])

    def test_provider_arrows_keyboard_and_native_move_preserve_checks_and_save_order(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        settings.select_section("providers")
        providers = settings.providers
        self.app.processEvents()
        first, second = providers.item(0), providers.item(1)
        # Exercise the delegate's actual per-row down arrow.
        rect = providers.visualItemRect(first)
        QTest.mouseClick(providers.viewport(), tray.Qt.MouseButton.LeftButton,
                         pos=tray.QPoint(rect.right() - 14, rect.center().y()))
        self.assertIs(providers.item(0), second)
        self.assertIs(providers.item(1), first)
        self.assertEqual(first.checkState(), tray.Qt.CheckState.Checked)
        QTest.keyClick(providers, tray.Qt.Key.Key_Up, tray.Qt.KeyboardModifier.AltModifier)
        self.assertIs(providers.item(0), first)
        # Qt's internal drop path moves rows in this same native model.
        self.assertTrue(providers.model().moveRow(QModelIndex(), 1, QModelIndex(), 0))
        self.assertIs(providers.item(0), second)
        self.assertEqual(providers.dragDropMode(), tray.QListWidget.DragDropMode.InternalMove)
        self.assertEqual(second.checkState(), tray.Qt.CheckState.Checked)
        with patch.object(self.dashboard, "refresh"):
            settings.save()
        self.assertEqual(config.enabled_order(), ["copilot", "codex"])
        self.assertTrue(self.dashboard.configuring())

    def test_settings_disabling_active_provider_selects_enabled_limit(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        self.assertEqual(settings.active.currentData()[0], "codex")
        settings.providers.item(0).setCheckState(tray.Qt.CheckState.Unchecked)
        self.assertEqual(settings.active.currentData()[0], "copilot")
        with patch.object(self.dashboard, "refresh"):
            settings.save()
        self.assertEqual(state.load_selected()["provider"], "copilot")

    def test_all_bundled_provider_logos_have_visible_pixels(self):
        for name in config.available_providers():
            self.assertTrue(tray.icon_has_pixels(tray.provider_icon(name)), name)

    def test_account_amounts_are_selectable_without_fake_percentage_bar(self):
        from core import accounts
        accounts.save_document({"version": 1, "accounts": [
            {"id": "work", "provider": "openrouter", "label": "Work"},
        ]}, config.accounts_file())
        config.save_config([])
        entry = {"provider": "OpenRouter", "_dir": "openrouter", "_connection_id": "account:work",
                 "_account_label": "Work", "metrics": [{"type": "balance", "name": "Credits",
                 "percentage": None, "amount": 42.5, "unit": "USD", "detail": "Available credits"}]}
        self.dashboard.on_result("account:work", [entry])
        button = self.dashboard.metric_buttons[0]
        self.assertEqual(button.percentage.text(), "$42.50")
        self.assertTrue(button.bar.isHidden())
        self.assertIn("Work $42.50", self.dashboard.tray.toolTip())
        button.click()
        self.assertEqual(state.load_selected()["provider"], "account:work")

    def test_cloud_credit_states_coexist_with_quota_and_reset_inventory_without_progress(self):
        config.save_config(["claude"])
        for balance, available, expires, overrides, value in (
                (75.25, True, "2099-11-05T07:59:00Z", {}, "$75.25"),
                (0, True, "2099-11-05T07:59:00Z", {}, "$0.00"),
                (75.25, True, "2000-11-05T07:59:00Z", {}, "Expired"),
                (75.25, False, "2099-11-05T07:59:00Z", {}, "Unavailable"),
                (75.25, True, "2099-11-05T07:59:00Z", {"_cached": True, "_error": "Offline"}, "Unavailable"),
                (75.25, True, "2099-11-05T07:59:00Z", {"_observed_at": time.time() - 601}, "Unavailable")):
            with self.subTest(balance=balance, value=value, overrides=overrides):
                entry = {"provider": "Claude (Max)", "_dir": "claude", "_idx": 0,
                         "_observed_at": time.time(), "metrics": [{"type": "rolling", "percentage": 9}],
                         "reset_credits": {"available": 1},
                         "monetary_credits": [{"id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
                             "balance": balance, "limit": 100, "used": 100 - balance,
                             "expires_at": expires, "available": available}], **overrides}
                self.dashboard.on_result("claude", [entry])
                self.assertEqual(len(self.dashboard.metric_buttons), 2)
                row = next(button for button in self.dashboard.metric_buttons if button.value[2] == "credits:claude-cloud")
                self.assertEqual(row.percentage.text(), value)
                self.assertTrue(row.bar.isHidden())
                self.assertTrue(row.bar_container.isHidden())
                self.assertTrue(row.description.isHidden())
                self.assertEqual(len(row.findChildren(tray.ArrowIcon)), 1)
                heading = self.dashboard.provider_buttons[("claude", 0)]
                self.assertFalse(heading.credits.isHidden())
                selected = state.load_selected()
                row.click()
                self.assertEqual(state.load_selected(), selected)
                self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.monetary_scroll)
                self.assertEqual(self.dashboard.monetary_view.balance.text(), value)
                self.assertNotIn("T07:59:00Z", self.dashboard.monetary_view.fields["expires"].text())
                historical = value in ("Expired", "Unavailable")
                self.assertEqual(self.dashboard.monetary_view.field_rows["observed_value"].isHidden(), not historical)
                self.assertEqual(self.dashboard.monetary_view.notice.isHidden(), not historical)
                if value == "Expired":
                    self.assertEqual(self.dashboard.monetary_view.fields["remaining"].text(), "Expired")
                heading.credits.click()
                self.assertEqual(self.dashboard.reset_provider, ("claude", 0))
                self.assertEqual(state.load_selected(), selected)
                self.dashboard.show_usage()

    def test_cloud_credit_only_accounts_are_visible_and_selectable_in_native_settings(self):
        from core import accounts
        accounts.save_document({"version": 1, "accounts": [
            {"id": "cloud-personal", "provider": "claude", "label": "Personal"},
            {"id": "cloud-work", "provider": "claude", "label": "Work"},
        ]}, config.accounts_file())
        config.save_config([])
        for identity, label, balance in (("personal", "Personal", 8.5), ("work", "Work", 75.25)):
            self.dashboard.on_result("account:cloud-" + identity, [{"provider": "Claude (Max)",
                "_dir": "claude", "_connection_id": "account:cloud-" + identity, "_account_label": label,
                "_idx": 0, "_observed_at": time.time(), "metrics": [],
                "monetary_credits": [{"id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
                    "balance": balance, "expires_at": "2099-11-05T07:59:00Z", "available": True}]}])
        self.assertEqual(len(self.dashboard.metric_buttons), 2)
        self.assertEqual([row.percentage.text() for row in self.dashboard.metric_buttons], ["$8.50", "$75.25"])
        selected = state.load_selected()
        self.dashboard.metric_buttons[-1].click()
        self.assertEqual(state.load_selected(), selected)
        self.assertIn("Work", self.dashboard.monetary_view.provider_label.text())
        self.assertEqual(self.dashboard.monetary_view.balance.text(), "$75.25")
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        self.assertEqual(settings.active.count(), 2)
        choices = [settings.active.itemData(index) for index in range(settings.active.count())]
        self.assertIn(["account:cloud-work", 0, "credits:claude-cloud"], choices)
        settings.active.setCurrentIndex(settings.active.findData(["account:cloud-work", 0, "credits:claude-cloud"]))
        with patch.object(self.dashboard, "refresh"):
            settings.save()
        self.assertEqual(state.load_selected()["provider"], "account:cloud-work")
        self.assertEqual(state.load_selected()["metric"], "credits:claude-cloud")

    def test_cloud_details_countdown_expiry_and_staleness_update_without_collecting_again(self):
        from core import usage_credits

        class Clock(datetime):
            current = datetime.now(timezone.utc)

            @classmethod
            def now(cls, tz=None):
                return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)

        config.save_config(["claude"])
        self.dashboard.last_config = config.load_config()
        self.dashboard.last_refresh = paths.read_json(state.REFRESH_FILE)
        for seconds, expiry_delay, value in ((2, 1, "Expired"), (601, 3600, "Unavailable"), (120, 3600, "$75.25")):
            with self.subTest(value=value), patch.object(usage_credits, "datetime", Clock), \
                    patch.object(self.dashboard, "refresh") as refresh:
                Clock.current = datetime.now(timezone.utc)
                entry = {"provider": "Claude (Max)", "_dir": "claude", "_idx": 0, "metrics": [],
                         "_observed_at": Clock.current.timestamp(), "monetary_credits": [
                             {"id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
                              "balance": 75.25, "available": True,
                              "expires_at": (Clock.current + timedelta(seconds=expiry_delay)).isoformat()}]}
                self.dashboard.on_result("claude", [entry])
                self.dashboard.metric_buttons[0].click()
                self.dashboard.poll_state()
                self.assertEqual(self.dashboard.metric_buttons[0].percentage.text(), "$75.25")
                remaining = self.dashboard.monetary_view.fields["remaining"].text()
                Clock.current += timedelta(seconds=seconds)
                self.dashboard.poll_state()
                row = self.dashboard.metric_buttons[0]
                self.assertEqual(row.percentage.text(), value)
                self.assertTrue(row.bar_container.isHidden())
                self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.monetary_scroll)
                self.assertEqual(self.dashboard.monetary_view.balance.text(), value)
                self.assertEqual(self.dashboard.monetary_view.fields["observed_value"].text(), "$75.25")
                self.assertNotEqual(self.dashboard.monetary_view.fields["remaining"].text(), remaining)
                self.assertEqual(state.load_selected()["metric"], "credits:claude-cloud")
                self.assertIn(value, self.dashboard.tray.toolTip())
                refresh.assert_not_called()

    @staticmethod
    def cloud_entry(idx=0, balance=75.25, **overrides):
        return {"provider": "Claude (Max)", "_dir": "claude", "_idx": idx,
                "_observed_at": time.time(), "metrics": [{"type": "rolling", "percentage": 9}],
                "monetary_credits": [{"id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
                    "balance": balance, "limit": 250, "used": 250 - balance,
                    "expires_at": "2099-11-05T07:59:00Z", "available": True}], **overrides}

    def test_cloud_details_display_balance_validity_and_account_without_selecting_the_amount(self):
        config.save_config(["claude"])
        entry = self.cloud_entry(_account_label="Personal")
        self.dashboard.on_result("claude", [entry])
        selected = state.load_selected()
        row = next(button for button in self.dashboard.metric_buttons if button.credit_id)
        row.click()
        view = self.dashboard.monetary_view
        self.assertEqual(self.dashboard.monetary_credit, ("claude", 0, "claude-cloud"))
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.monetary_scroll)
        self.assertEqual(view.provider_label.text(), "Claude (Max) · Cloud credits · Personal")
        self.assertNotIn("Cloud credits", [label.text() for label in view.findChildren(QLabel)])
        self.assertEqual(view.balance.text(), "$75.25")
        self.dashboard.show()
        self.app.processEvents()
        self.assertEqual(view.balance.geometry().top() - view.balance_label.geometry().bottom() - 1, 4)
        self.assertEqual(view.fields["status"].text(), "Available")
        self.assertEqual(view.fields["limit_value"].text(), "$250.00")
        self.assertEqual(view.fields["used_value"].text(), "$174.75")
        self.assertIn("2099", view.fields["expires"].text())
        self.assertNotIn("T07:59:00Z", view.fields["expires"].text())
        self.assertTrue(view.fields["remaining"].text())
        self.assertIn("Local time · UTC", view.timezone_note.text())
        self.assertTrue(view.field_rows["observed_value"].isHidden())
        self.assertTrue(view.field_rows["observed"].isHidden())
        self.assertTrue(view.notice.isHidden())
        self.assertFalse(self.dashboard.back_button.isHidden())
        self.assertFalse(self.dashboard.refresh_button.isHidden())
        self.assertTrue(self.dashboard.settings_button.isHidden())
        self.assertEqual(state.load_selected(), selected)
        self.assertEqual(self.dashboard.tray.toolTip(), "Claude (Max) · Personal 9%")

    def test_cloud_details_isolate_accounts_subaccounts_and_credit_ids(self):
        from core import accounts
        accounts.save_document({"version": 1, "accounts": [
            {"id": "cloud-home", "provider": "claude", "label": "Home"},
            {"id": "cloud-work", "provider": "claude", "label": "Work"},
        ]}, config.accounts_file())
        config.save_config(["codex"])
        self.dashboard.on_result("codex", [{"provider": "Codex", "_dir": "codex",
                                            "metrics": [{"type": "weekly", "percentage": 23}]}])
        self.dashboard.on_result("account:cloud-home", [self.cloud_entry(balance=8.5,
            _connection_id="account:cloud-home", _account_label="Home")])
        primary = self.cloud_entry(balance=20, _connection_id="account:cloud-work", _account_label="Work")
        secondary = self.cloud_entry(idx=1, balance=60.5, _connection_id="account:cloud-work", _account_label="Work")
        secondary["monetary_credits"].append({**secondary["monetary_credits"][0],
            "id": "another-promotion", "title": "Another credit", "balance": 9.75})
        self.dashboard.on_result("account:cloud-work", [primary, secondary])
        selected = state.load_selected()
        row = next(button for button in self.dashboard.metric_buttons
                   if button.value == ("account:cloud-work", 1, "credits:another-promotion"))
        row.click()
        self.assertEqual(self.dashboard.monetary_credit, ("account:cloud-work", 1, "another-promotion"))
        self.assertIn("Work", self.dashboard.monetary_view.provider_label.text())
        self.assertNotIn("Home", self.dashboard.monetary_view.provider_label.text())
        self.assertIn("Another credit", self.dashboard.monetary_view.provider_label.text())
        self.assertEqual(self.dashboard.monetary_view.balance.text(), "$9.75")
        self.assertEqual(state.load_selected(), selected)
        self.assertEqual(self.dashboard.tray.toolTip(), "Codex 23%")

    def test_cloud_details_table_matches_reset_header_and_has_only_one_top_border(self):
        config.save_config(["claude"])
        entry = self.cloud_entry(reset_credits={"available": 1})
        self.dashboard.on_result("claude", [entry])
        self.dashboard.show()
        self.dashboard.show_monetary_credit(("claude", 0, "claude-cloud"))
        self.app.processEvents()
        view = self.dashboard.monetary_view
        table_image = view.table.grab().toImage()
        first_row = view.field_rows["status"]
        value_top = first_row.mapTo(view.table, tray.QPoint(first_row.width() * 3 // 4, 0))
        self.assertEqual(table_image.pixelColor(value_top.x(), 0), tray.QColor("#262626"))
        self.assertEqual(table_image.pixelColor(value_top).alpha(), 0)
        cell = view.label_cells["status"]
        cell_image = cell.grab().toImage()
        cell_point = cell.mapTo(self.dashboard, tray.QPoint(cell.width() // 2, 3))
        dashboard_image = self.dashboard.grab().toImage()
        cell_background = dashboard_image.pixelColor(cell_point)
        self.assertEqual(cell_background, tray.QColor("#1a1a1a"))
        self.assertEqual(cell_image.pixelColor(cell.width() - 1, cell.height() // 2), tray.QColor("#262626"))
        first_corner = cell.mapTo(self.dashboard, tray.QPoint(0, 0))
        self.assertEqual(dashboard_image.pixelColor(first_corner), tray.QColor("#111111"))
        last_cell = view.label_cells["remaining"]
        self.assertTrue(last_cell.property("lastRow"))
        last_corner = last_cell.mapTo(self.dashboard, tray.QPoint(0, last_cell.height() - 1))
        self.assertEqual(dashboard_image.pixelColor(last_corner), tray.QColor("#111111"))
        self.dashboard.show_reset_credits(("claude", 0))
        self.app.processEvents()
        header = self.dashboard.credits_view.table.findChild(tray.QWidget, "creditTableHeader")
        header_point = header.mapTo(self.dashboard, tray.QPoint(header.width() // 2, 3))
        header_color = self.dashboard.grab().toImage().pixelColor(header_point)
        self.assertEqual(cell_background, header_color)
        entry["monetary_credits"][0]["expires_at"] = "2000-11-05T07:59:00Z"
        self.dashboard.on_result("claude", [entry])
        self.dashboard.show_monetary_credit(("claude", 0, "claude-cloud"))
        self.app.processEvents()
        self.assertFalse(view.label_cells["remaining"].property("lastRow"))
        self.assertTrue(view.label_cells["observed"].property("lastRow"))

    def test_cloud_details_refresh_in_place_and_back_restores_focus_and_scroll(self):
        config.save_config(["claude"])
        entries = [self.cloud_entry(idx=index, balance=index + 0.25) for index in range(9)]
        self.dashboard.on_result("claude", entries)
        self.dashboard.show()
        self.app.processEvents()
        self.dashboard.move(80, self.dashboard.screen().availableGeometry().bottom() - self.dashboard.height() - 20)
        scroll = self.dashboard.scroll.verticalScrollBar()
        scroll.setValue(scroll.maximum())
        position = scroll.value()
        self.assertGreater(position, 0)
        row = next(button for button in self.dashboard.metric_buttons
                   if button.value == ("claude", 8, "credits:claude-cloud"))
        bottom = self.dashboard.geometry().bottom()
        row.click()
        self.app.processEvents()
        view = self.dashboard.monetary_view
        self.assertIs(self.dashboard.focusWidget(), self.dashboard.back_button)
        self.assertEqual(self.dashboard.geometry().bottom(), bottom)
        selected = state.load_selected()
        entries[8] = self.cloud_entry(idx=8, balance=7.5)
        self.dashboard.on_result("claude", entries)
        self.app.processEvents()
        self.assertIs(self.dashboard.monetary_view, view)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.monetary_scroll)
        self.assertIs(self.dashboard.focusWidget(), self.dashboard.back_button)
        self.assertEqual(view.balance.text(), "$7.50")
        self.assertEqual(view.fields["used_value"].text(), "$242.50")
        self.assertEqual(self.dashboard.geometry().bottom(), bottom)
        self.assertEqual(state.load_selected(), selected)
        self.dashboard.back_button.click()
        self.app.processEvents()
        self.assertIsNone(self.dashboard.monetary_credit)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
        self.assertTrue(row.hasFocus())
        self.assertEqual(scroll.value(), position)
        self.assertEqual(self.dashboard.geometry().bottom(), bottom)

    def test_cloud_details_keyboard_navigation_preserves_selection_and_returns_to_the_row(self):
        config.save_config(["claude"])
        self.dashboard.on_result("claude", [self.cloud_entry()])
        self.dashboard.show()
        self.app.processEvents()
        row = next(button for button in self.dashboard.metric_buttons if button.credit_id)
        selected = state.load_selected()
        row.setFocus()
        QTest.keyClick(row, tray.Qt.Key.Key_Return)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.monetary_scroll)
        QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Down)
        QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Up)
        self.assertEqual(state.load_selected(), selected)
        with patch.object(self.dashboard, "refresh") as refresh:
            QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_R)
        refresh.assert_called_once_with()
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.monetary_scroll)
        QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Escape)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
        self.assertTrue(row.hasFocus())
        QTest.keyClick(row, tray.Qt.Key.Key_Space)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.monetary_scroll)
        QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Escape)
        self.assertEqual(state.load_selected(), selected)
        QTest.keyClick(row, tray.Qt.Key.Key_Escape)
        self.assertFalse(self.dashboard.isVisible())

    def test_cloud_details_handle_absent_fields_and_removed_credit_or_provider(self):
        config.save_config(["claude"])
        entry = self.cloud_entry(balance=0)
        for key in ("expires_at", "limit", "used"):
            entry["monetary_credits"][0].pop(key)
        self.dashboard.on_result("claude", [entry])
        self.dashboard.show()
        self.app.processEvents()
        row = next(button for button in self.dashboard.metric_buttons if button.credit_id)
        row.click()
        view = self.dashboard.monetary_view
        self.assertEqual(view.balance.text(), "$0.00")
        self.assertEqual(view.fields["status"].text(), "Exhausted")
        self.assertEqual(view.fields["limit_value"].text(), "Not reported")
        self.assertEqual(view.fields["used_value"].text(), "Not reported")
        self.assertEqual(view.fields["expires"].text(), "Not reported")
        self.assertTrue(view.field_rows["remaining"].isHidden())
        self.assertTrue(view.timezone_note.isHidden())
        selected = state.load_selected()
        entry.pop("monetary_credits")
        self.dashboard.on_result("claude", [entry])
        self.app.processEvents()
        self.assertIsNone(self.dashboard.monetary_credit)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
        self.assertTrue(self.dashboard.provider_buttons[("claude", 0)].hasFocus())
        self.assertEqual(state.load_selected(), selected)
        self.dashboard.show_monetary_credit(("claude", 0, "claude-cloud"))
        self.assertIsNone(self.dashboard.monetary_credit)
        self.dashboard.on_result("claude", [self.cloud_entry()])
        self.dashboard.show_monetary_credit(("claude", 0, "claude-cloud"))
        self.dashboard.on_result("claude", None)
        self.app.processEvents()
        self.assertIsNone(self.dashboard.monetary_credit)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
        self.assertTrue(self.dashboard.refresh_button.hasFocus())

    def test_long_metric_names_keep_percentages_and_amounts_in_the_viewport(self):
        config.save_config(["openai-api"])
        self.dashboard.on_result("openai-api", [{"provider": "OpenAI API", "metrics": [
            {"type": "monthly", "name": "Reported month costs / configured budget (USD)",
             "percentage": 38.75},
            {"type": "balance", "name": "Available organization prepaid credit balance (USD)",
             "percentage": None, "amount": 12345.67, "unit": "USD"},
            {"type": "credits", "name": "Account spend / total credits (USD)",
             "percentage": 25, "amount": 25, "limit": 100, "unit": "USD", "value_format": "amount_ratio"},
        ]}])
        self.dashboard.show()
        self.app.processEvents()
        viewport = self.dashboard.scroll.viewport()
        self.assertLessEqual(self.dashboard.scroll.widget().width(), viewport.width())
        self.assertEqual([button.percentage.text() for button in self.dashboard.metric_buttons],
                         ["39%", "$12345.67", "$25.00 / $100.00"])
        for button in self.dashboard.metric_buttons:
            value = button.percentage
            right = value.mapTo(viewport, tray.QPoint(value.width(), 0)).x()
            self.assertLessEqual(right, viewport.width())
            self.assertGreaterEqual(value.width(), value.fontMetrics().horizontalAdvance(value.text()))

    def test_metric_values_align_above_full_width_bars_and_amounts_have_no_bar_row(self):
        config.save_config(["openrouter"])
        self.dashboard.on_result("openrouter", [{"provider": "OpenRouter", "metrics": [
            {"type": "credits", "name": "Account credits", "percentage": 25,
             "amount": 25, "limit": 100, "unit": "USD", "value_format": "amount_ratio"},
            {"type": "monthly", "name": "Key limit", "percentage": 12,
             "amount": 12, "limit": 100, "unit": "USD", "value_format": "amount_ratio"},
            {"type": "balance", "name": "Available balance", "percentage": None,
             "amount": 75, "unit": "USD"},
        ]}])
        self.dashboard.show()
        self.app.processEvents()
        rows = self.dashboard.metric_buttons
        right_edges = [row.percentage.mapTo(self.dashboard.scroll.widget(),
                       tray.QPoint(row.percentage.width(), 0)).x() for row in rows if not row.is_amount]
        self.assertEqual(len(set(right_edges)), 1)
        for row in rows:
            self.assertEqual(row.title.parentWidget(), row.percentage.parentWidget())
            if row.bar_container.isHidden():
                self.assertTrue(row.bar.isHidden())
            else:
                self.assertGreater(row.bar_container.y(), row.percentage.y())
                self.assertGreater(row.bar.width(), row.title.width())
        rows[-1].click()
        self.assertEqual(state.load_selected()["metric"], rows[-1].value[2])
        self.assertEqual(rows[-1].bullet.text(), "•")

    def test_native_metric_content_aligns_with_provider_name_and_amount_value_is_adjacent(self):
        config.save_config(["deepseek"])
        self.dashboard.on_result("deepseek", [{"provider": "DeepSeek", "metrics": [
            {"type": "balance", "name": "Available balance", "id": "balance", "amount": 20.5,
             "unit": "USD", "percentage": None, "detail": "Organization credits"},
            {"type": "monthly", "name": "Monthly usage", "percentage": 25, "reset_in_seconds": 3600},
        ]}])
        self.dashboard.show()
        self.app.processEvents()
        content = self.dashboard.scroll.widget()
        heading = self.dashboard.provider_buttons[("deepseek", 0)]
        anchor = heading.name_label.mapTo(content, tray.QPoint(0, 0)).x()
        marker = heading.arrow.mapTo(content, tray.QPoint(0, 0)).x()
        for row in self.dashboard.metric_buttons:
            self.assertEqual(row.title.mapTo(content, tray.QPoint(0, 0)).x(), anchor)
            self.assertEqual(row.bullet.mapTo(content, tray.QPoint(0, 0)).x(), marker)
            self.assertEqual(row.description.mapTo(content,
                tray.QPoint(row.description.contentsMargins().left(), 0)).x(), anchor)
            if not row.bar_container.isHidden():
                self.assertEqual(row.open_bracket.mapTo(content, tray.QPoint(0, 0)).x(), anchor)
            if row.is_amount:
                self.assertTrue(row.percentage.alignment() & tray.Qt.AlignmentFlag.AlignLeft)
                self.assertFalse(row.percentage.alignment() & tray.Qt.AlignmentFlag.AlignRight)
                self.assertEqual(row.percentage.x() - row.title.geometry().right() - 1, 8)
                self.assertTrue(row.bar_container.isHidden())
                self.assertEqual(row.percentage.font().pixelSize(), 13)
        amount = next(row for row in self.dashboard.metric_buttons if row.is_amount)
        amount.setFocus()
        QTest.keyClick(amount, tray.Qt.Key.Key_Return)
        selected = amount.value
        before = [(row.geometry(), row.percentage.geometry()) for row in self.dashboard.metric_buttons]
        self.dashboard.pending.add("deepseek")
        self.dashboard.animate()
        self.app.processEvents()
        self.assertEqual(before, [(row.geometry(), row.percentage.geometry()) for row in self.dashboard.metric_buttons])
        self.assertEqual(self.dashboard.selected_value(), selected)
        self.assertTrue(amount.hasFocus())

    def test_cached_status_and_reset_credits_link_align_with_provider_name(self):
        config.save_config(["codex"])
        self.dashboard.on_result("codex", [{"provider": "Codex", "_cached": True,
            "_error": "Session expired", "metrics": [{"type": "weekly", "percentage": 23}],
            "reset_credits": {"available": 2}}])
        self.dashboard.show()
        self.app.processEvents()
        heading = self.dashboard.provider_buttons[("codex", 0)]
        content = self.dashboard.scroll.widget()
        anchor = heading.name_label.mapTo(content, tray.QPoint(0, 0)).x()
        self.assertFalse(heading.cached_label.isHidden())
        self.assertEqual(heading.cached_label.mapTo(content,
            tray.QPoint(heading.cached_label.contentsMargins().left(), 0)).x(), anchor)
        self.assertFalse(heading.credits.isHidden())
        self.assertEqual(heading.credits_title.mapTo(content, tray.QPoint(0, 0)).x(), anchor)
        heading.credits.click()
        self.assertEqual(self.dashboard.reset_provider, ("codex", 0))

    def test_two_openrouter_accounts_fit_without_scrolling(self):
        from core import accounts
        import json
        from test_metered_apis import load
        parser = load("openrouter", "parse").parse
        accounts.save_document({"version": 1, "accounts": [
            {"id": "personal", "provider": "openrouter", "label": "Personal"},
            {"id": "work", "provider": "openrouter", "label": "Work"},
        ]}, config.accounts_file())
        config.save_config([])
        for identity, label, spent, key_used in (("personal", "Personal", 25, 12), ("work", "Work", 42, 29)):
            parsed = parser(json.dumps({
                "key": {"data": {"usage_monthly": key_used, "limit": 100, "limit_remaining": 100 - key_used,
                                   "limit_reset": "monthly"}},
                "credits": {"data": {"total_credits": 100, "total_usage": spent}},
            }))
            self.dashboard.on_result("account:" + identity, [{"provider": "OpenRouter",
                "_dir": "openrouter", "_connection_id": "account:" + identity,
                "_account_label": label, "metrics": parsed["metrics"]}])
        self.dashboard.show()
        self.app.processEvents()
        self.assertEqual(len(self.dashboard.metric_buttons), 4)
        self.assertEqual([row.description.text() for row in self.dashboard.metric_buttons if row.description.text()],
                         ["$25.00 of $100.00 used (25%)", "$42.00 of $100.00 used (42%)"])
        credit_rows = [row for row in self.dashboard.metric_buttons if row.title.text() == "Credit balance"]
        self.assertEqual([row.percentage.text() for row in credit_rows], ["$75.00", "$58.00"])
        self.assertEqual([row.bar.target for row in credit_rows], [25, 42])
        self.assertFalse(any(row.title.text().startswith("Available balance") for row in self.dashboard.metric_buttons))
        self.assertLessEqual(self.dashboard.height(), 720)
        self.assertEqual(self.dashboard.scroll.verticalScrollBar().maximum(), 0)
        self.dashboard.metric_buttons[-1].click()
        self.assertEqual(state.load_selected()["provider"], "account:work")

    def test_openrouter_wallet_shows_balance_in_both_display_modes_with_spend_bar(self):
        import json
        from test_metered_apis import load
        parser = load("openrouter", "parse").parse
        config.save_config(["openrouter"])
        parsed = parser(json.dumps({"credits": {"data": {"total_credits": 40, "total_usage": 36.1}}}))
        entry = dict(parsed, _dir="openrouter", _idx=0)
        self.dashboard.on_result("openrouter", [entry])
        self.dashboard.show()
        for mode, progress in (("used", 90.25), ("remaining", 9.75)):
            with self.subTest(mode=mode):
                self.dashboard.selected["usage_display"] = mode
                self.dashboard.draw()
                row = self.dashboard.metric_buttons[0]
                row.click()
                self.app.processEvents()
                self.assertEqual(row.title.text(), "Credit balance")
                self.assertEqual(row.percentage.text(), "$3.90")
                self.assertEqual(row.description.text(), "$36.10 of $40.00 used (90%)")
                self.assertAlmostEqual(row.bar.target, progress)
                self.assertFalse(row.bar_container.isHidden())
                self.assertEqual(self.dashboard.tray.toolTip(), "OpenRouter $3.90")
                self.assertEqual(state.load_selected()["metric"], "credits:Account spend / total credits (USD)")

    def test_openrouter_legacy_balance_selection_stays_on_account_after_rows_merge(self):
        import json
        from test_metered_apis import load
        parser = load("openrouter", "parse").parse
        config.save_config(["claude", "openrouter"])
        self.dashboard.on_result("claude", [{"provider": "Claude (Max)", "_idx": 0,
            "metrics": [{"type": "weekly", "percentage": 50}]}])
        self.dashboard.selected.update(provider="openrouter", idx=0,
            metric="credits:Account credit balance (USD)")
        state.save_selected(self.dashboard.selected)
        parsed = parser(json.dumps({"credits": {"data": {"total_credits": 0, "total_usage": 0}}}))
        self.dashboard.on_result("openrouter", [dict(parsed, _dir="openrouter", _idx=0)])
        self.assertEqual(self.dashboard.selected_value(),
                         ("openrouter", 0, "credits:Account spend / total credits (USD)"))
        self.assertEqual(state.load_selected()["provider"], "openrouter")
        self.assertEqual(state.load_selected()["metric"], "credits:Account spend / total credits (USD)")
        self.assertEqual(self.dashboard.tray.toolTip(), "OpenRouter $0.00")
        self.assertEqual(len([row for row in self.dashboard.metric_buttons
                             if row.value[0] == "openrouter"]), 1)

    def test_refresh_keeps_rows_and_geometry_while_providers_finish_independently(self):
        from core import fetch
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "weekly", "percentage": 23, "reset_in_seconds": 3600}]}])
        self.dashboard.on_result("copilot", [{"provider": "Copilot", "metrics": [
            {"type": "monthly", "percentage": 7}]}])
        self.dashboard.show()
        self.app.processEvents()
        rows = self.dashboard.metric_buttons[:]
        rows[0].setFocus()
        def geometry():
            return [self.dashboard.size()] + [(row.geometry(), row.bar.geometry(),
                row.open_bracket.geometry(), row.close_bracket.geometry(),
                row.percentage.geometry(), row.description.geometry()) for row in rows]
        before = geometry()
        with patch.object(state, "acquire_lock", return_value=True), patch.object(tray.threading, "Thread"):
            self.dashboard.refresh()
        self.app.processEvents()
        self.dashboard.animate()
        self.assertEqual(rows, self.dashboard.metric_buttons)
        self.assertEqual(before, geometry())
        self.assertTrue(all(row.bar.loading for row in rows))
        self.assertIn(rows[0].percentage.text(), tray.render.SPINNERS)
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "weekly", "percentage": 100, "reset_in_seconds": 3600}]}])
        self.app.processEvents()
        self.assertFalse(rows[0].bar.loading)
        self.assertTrue(rows[1].bar.loading)
        self.assertEqual(rows[0].percentage.text(), "100%")
        self.assertEqual(rows, self.dashboard.metric_buttons)
        self.assertEqual(before, geometry())
        self.assertTrue(rows[0].hasFocus())
        with patch.object(fetch, "get_version_info", return_value={"has_update": False}):
            self.dashboard.on_finished([])
        self.app.processEvents()
        self.assertEqual(rows[1].percentage.text(), "7%")
        self.assertEqual(before, geometry())

    def test_first_mount_animates_fill_and_selection_does_not_restart_it(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "metrics": [
            {"type": "rolling", "percentage": 80}, {"type": "weekly", "percentage": 20}]}])
        self.dashboard.on_result("copilot", [{"provider": "Copilot", "metrics": [
            {"type": "monthly", "percentage": 7}]}])
        self.dashboard.show()
        self.app.processEvents()
        bar = self.dashboard.metric_buttons[0].bar
        self.assertEqual(bar.displayed, 0)
        self.assertLess(bar.start_delay.remainingTime(), self.dashboard.metric_buttons[2].bar.start_delay.remainingTime())
        initial = bar.grab().toImage()
        bar.start_delay.stop()
        bar.start_fill()
        bar.fill.setCurrentTime(500)
        self.assertGreater(bar.displayed, 0)
        self.assertLess(bar.displayed, 80)
        self.dashboard.metric_buttons[1].click()
        self.assertIs(bar, self.dashboard.metric_buttons[0].bar)
        self.assertEqual(bar.fill.currentTime(), 500)
        bar.fill.setCurrentTime(1500)
        self.assertEqual(bar.displayed, 80)
        self.assertNotEqual(initial, bar.grab().toImage())

    def test_loading_shimmers_without_a_fill_and_pauses_when_hidden(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "metrics": [
            {"type": "weekly", "percentage": 80}]}])
        self.dashboard.pending = {"codex"}
        self.dashboard.draw()
        self.dashboard.show()
        self.app.processEvents()
        bar = self.dashboard.metric_buttons[0].bar
        bar.shimmer.setCurrentTime(0)
        first = bar.grab().toImage()
        bar.shimmer.setCurrentTime(750)
        self.assertNotEqual(first, bar.grab().toImage())
        self.assertEqual(bar.displayed, 0)
        self.dashboard.hide()
        self.assertEqual(bar.shimmer.state(), tray.QVariantAnimation.State.Stopped)
        self.assertFalse(bar.start_delay.isActive())
        self.dashboard.show()
        self.app.processEvents()
        self.assertEqual(bar.shimmer.state(), tray.QVariantAnimation.State.Running)

    def test_reset_credits_are_provider_details_and_never_selectable_metrics(self):
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "weekly", "percentage": 23}], "reset_credits": {"available": 2, "credits": [
                {"count": 1, "title": "Full reset", "expires_at": "2099-10-22T16:00:00Z"}]}}])
        heading = self.dashboard.provider_buttons[("codex", 0)]
        self.assertEqual(heading.credits_title.text(), "Reset credits: 2 available")
        main_text = "\n".join(label.text() for label in self.dashboard.scroll.widget().findChildren(QLabel))
        self.assertNotIn("Full reset", main_text)
        self.assertNotIn("Expires", main_text)
        self.assertEqual(len(self.dashboard.metric_values), 1)
        self.assertEqual(state.load_selected()["metric"], "weekly")
        selected = state.load_selected()
        heading.credits.click()
        self.assertEqual(self.dashboard.reset_provider, ("codex", 0))
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.credits_scroll)
        view = self.dashboard.credits_view
        self.assertEqual(view.available.text(), "2")
        self.assertEqual(view.available_label.text(), "Available resets")
        self.assertIs(view.available.parentWidget(), view.total_footer)
        self.assertTrue(view.table.isAncestorOf(view.available))
        header = view.table.findChild(tray.QWidget, "creditTableHeader")
        self.assertEqual([label.text() for label in header.findChildren(QLabel)], ["Reset type", "Expires"])
        text = "\n".join(label.text() for label in self.dashboard.credits_view.findChildren(QLabel))
        self.assertIn("Full reset", text)
        self.assertIn("Oct 22, 2099", text)
        self.assertIn("Local time · UTC", view.timezone_note.text())
        self.assertIs(view.timezone_note.parentWidget(), view)
        self.assertFalse(view.table.isAncestorOf(view.timezone_note))
        self.assertTrue(all("UTC" not in remaining.text() for _, remaining in view.rows))
        self.assertIn("Not provided", text)  # The second credit's details are unavailable.
        self.assertEqual(state.load_selected(), selected)
        self.dashboard.data["codex"][0]["reset_credits"]["available"] = 0
        self.dashboard.draw()
        self.assertEqual(self.dashboard.credits_view.available.text(), "0")
        self.assertTrue(self.dashboard.credits_view.table.isHidden())
        self.assertTrue(self.dashboard.credits_view.timezone_note.isHidden())
        self.assertFalse(self.dashboard.credits_view.empty.isHidden())
        self.assertFalse(self.dashboard.back_button.isHidden())
        self.assertEqual(self.dashboard.credits_view.heading.findChildren(tray.QAbstractButton), [])
        self.dashboard.back_button.click()
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
        self.assertTrue(heading.credits.isHidden())
        self.assertEqual(self.dashboard.tray.toolTip(), "Codex (Pro) 23%")

    def test_reset_submenu_uses_the_clicked_provider_and_account(self):
        config.save_config(["claude", "codex"])
        self.dashboard.on_result("claude", [
            {"provider": "Claude (Max)", "_idx": 0, "metrics": [{"type": "rolling", "percentage": 2}],
             "reset_credits": {"available": 1, "credits": [{"title": "Max reset", "count": 1}]}},
            {"provider": "Claude (Pro)", "_idx": 1, "metrics": [{"type": "rolling", "percentage": 4}],
             "reset_credits": {"available": 2, "credits": [{"title": "Pro reset", "count": 2}]}},
        ])
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "weekly", "percentage": 23}], "reset_credits": {"available": 3}}])
        self.dashboard.provider_buttons[("codex", 0)].click()
        selected = state.load_selected()
        self.dashboard.provider_buttons[("claude", 1)].credits.click()
        self.assertEqual(self.dashboard.reset_provider, ("claude", 1))
        self.assertEqual(self.dashboard.credits_view.provider_label.text(), "Claude (Pro)")
        text = "\n".join(label.text() for label in self.dashboard.credits_view.findChildren(QLabel))
        self.assertIn("Pro reset", text)
        self.assertIn("2 credits", text)
        self.assertNotIn("Max reset", text)
        self.assertEqual(state.load_selected(), selected)
        self.assertEqual(self.dashboard.tray.toolTip(), "Codex (Pro) 23%")

    def test_reset_details_refresh_in_place_and_back_restores_focus_and_position(self):
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "weekly", "percentage": 23}], "reset_credits": {"available": 3}}])
        self.dashboard.show()
        self.app.processEvents()
        self.dashboard.move(80, 500)
        heading = self.dashboard.provider_buttons[("codex", 0)]
        bottom = self.dashboard.geometry().bottom()
        heading.credits.click()
        self.app.processEvents()
        view = self.dashboard.credits_view
        self.assertTrue(view.timezone_note.isHidden())
        self.assertEqual(self.dashboard.geometry().bottom(), bottom)
        self.assertIs(self.dashboard.focusWidget(), self.dashboard.back_button)
        self.assertFalse(view.notice.isHidden())
        self.assertEqual(view.rows[0][0].text(), "Not provided")
        self.dashboard.pending = {"codex"}
        self.dashboard.draw()
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "weekly", "percentage": 24}], "reset_credits": {"available": 3, "credits": [
                {"count": 1, "title": "Full reset", "expires_at": "2099-10-22T16:00:00Z"},
                {"count": 2, "title": "Weekly reset", "expires_at": "2099-10-29T16:00:00Z"}]}}])
        self.app.processEvents()
        self.assertIs(self.dashboard.provider_buttons[("codex", 0)], heading)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.credits_scroll)
        self.assertIs(self.dashboard.focusWidget(), self.dashboard.back_button)
        self.assertTrue(view.notice.isHidden())
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(self.dashboard.geometry().bottom(), bottom)
        self.dashboard.back_button.click()
        self.app.processEvents()
        self.assertTrue(heading.credits.hasFocus())
        self.assertEqual(self.dashboard.geometry().bottom(), bottom)
        self.assertEqual(self.dashboard.tray.toolTip(), "Codex (Pro) 24%")

    def test_reset_submenu_keyboard_back_and_missing_provider(self):
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "rolling", "percentage": 3}, {"type": "weekly", "percentage": 23}],
            "reset_credits": {"available": 3}}])
        self.dashboard.show()
        self.app.processEvents()
        link = self.dashboard.provider_buttons[("codex", 0)].credits
        link.setFocus()
        QTest.keyClick(link, tray.Qt.Key.Key_Return)
        self.assertEqual(self.dashboard.reset_provider, ("codex", 0))
        selected = state.load_selected()
        QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Down)
        self.assertEqual(state.load_selected(), selected)
        QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Escape)
        self.assertIsNone(self.dashboard.reset_provider)
        self.assertTrue(self.dashboard.isVisible())
        self.assertTrue(link.hasFocus())
        QTest.keyClick(link, tray.Qt.Key.Key_Escape)
        self.assertFalse(self.dashboard.isVisible())
        self.dashboard.show()
        QTest.keyClick(link, tray.Qt.Key.Key_Space)
        self.assertEqual(self.dashboard.reset_provider, ("codex", 0))
        self.dashboard.on_result("codex", None)
        self.assertIsNone(self.dashboard.reset_provider)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
        self.dashboard.show_reset_credits(("codex", 0))
        self.assertIsNone(self.dashboard.reset_provider)

    def prepare_reset_action(self):
        cache_directory = patch.object(paths, "CACHE_DIR", self.root / "reset-cache")
        cache_directory.start()
        self.addCleanup(cache_directory.stop)
        mutation = patch.object(tray.reset_actions, "apply", return_value="Reset applied. Refreshing account usage…")
        apply_reset = mutation.start()
        self.addCleanup(mutation.stop)
        entry = {
            "provider": "Codex (Pro)", "_dir": "codex", "_idx": 0,
            "_fingerprint": "a" * 64, "_observed_at": time.time(),
            "metrics": [{"type": "weekly", "percentage": 23}],
            "reset_credits": {"available": 2, "credits": [
                {"title": "Full reset", "count": 2, "expires_at": "2099-10-22T16:00:00Z", "action_id": "b" * 64}
            ]},
        }
        self.dashboard.on_result("codex", [entry])
        self.dashboard.show_reset_credits(("codex", 0))
        view = self.dashboard.credits_view
        # Capture the UI contract without starting a thread, CLI or real mutation.
        view.reset_requested.disconnect(self.dashboard.apply_reset)
        requested = MagicMock()
        view.reset_requested.connect(requested)
        return entry, view, requested, apply_reset

    def test_update_and_reset_never_start_workers_while_the_other_is_running(self):
        _, view, requested, apply_reset = self.prepare_reset_action()
        payload = dict(view.action, credit="b" * 64, confirmed=True)
        self.dashboard.updating = True
        with patch.object(tray, "ResetWorker") as worker:
            self.dashboard.apply_reset(payload)
        worker.assert_not_called()
        self.assertFalse(self.dashboard.reset_applying)
        self.dashboard.draw()
        self.assertTrue(all(button.isHidden() for button in view.action_buttons))
        self.dashboard.updating = False
        self.dashboard.reset_applying = True
        with patch.object(tray, "UpdateWorker") as worker:
            self.dashboard.start_update()
        worker.assert_not_called()
        self.assertFalse(self.dashboard.updating)
        self.dashboard.reset_applying = False
        requested.assert_not_called()
        apply_reset.assert_not_called()

    def test_apply_reset_only_opens_confirmation_and_cancel_never_emits(self):
        _, view, requested, apply_reset = self.prepare_reset_action()
        button = view.action_buttons[0]
        self.assertFalse(button.isHidden())
        self.assertTrue(button.isEnabled())
        self.assertTrue(view.confirmation.isHidden())
        button.click()
        self.assertFalse(view.confirmation.isHidden())
        self.assertIn("Full reset", view.confirmation_text.text())
        self.assertIn("Codex (Pro)", view.confirmation_text.text())
        self.assertIn("1 reset credit", view.confirmation_text.text())
        requested.assert_not_called()
        apply_reset.assert_not_called()
        view.cancel_button.click()
        self.assertIsNone(view.target)
        self.assertTrue(view.confirmation.isHidden())
        view.confirm_button.click()
        requested.assert_not_called()
        apply_reset.assert_not_called()

    def test_confirm_reset_emits_once_and_worker_calls_mocked_mutation_once(self):
        _, view, requested, apply_reset = self.prepare_reset_action()
        token = view.action["fingerprint"]
        view.action_buttons[0].click()
        view.confirm_button.click()
        requested.assert_called_once_with({
            "provider": "codex", "idx": 0, "fingerprint": token,
            "credit": "b" * 64, "confirmed": True,
        })
        self.assertTrue(view.confirmation.isHidden())
        self.assertIsNone(view.target)
        view.confirm_button.click()
        view.confirm_reset()
        self.assertEqual(requested.call_count, 1)
        apply_reset.assert_not_called()
        worker = tray.ResetWorker(requested.call_args.args[0])
        self.addCleanup(worker.deleteLater)
        finished = MagicMock()
        worker.finished.connect(finished)
        worker.work()
        apply_reset.assert_called_once_with(requested.call_args.args[0])
        finished.assert_called_once_with("Reset applied. Refreshing account usage…", True)

    def test_reset_actions_are_hidden_for_cached_pending_or_unidentified_credits(self):
        entry, view, requested, apply_reset = self.prepare_reset_action()
        entry["_cached"] = True
        self.dashboard.draw()
        self.assertTrue(all(button.isHidden() for button in view.action_buttons))
        view.action_buttons[0].click()
        self.assertIsNone(view.target)
        entry.pop("_cached")
        self.dashboard.pending = {"copilot"}
        self.dashboard.busy = True
        self.dashboard.draw()
        self.assertTrue(all(button.isHidden() for button in view.action_buttons))
        self.assertIsNone(view.action)
        self.dashboard.pending.clear()
        self.dashboard.busy = False
        entry["reset_credits"]["credits"][0].pop("action_id")
        self.dashboard.draw()
        self.assertEqual(view.action_buttons, [])
        self.assertIsNone(view.action)
        self.assertFalse(view.table.isHidden())
        self.assertEqual(view.available.text(), "2")
        requested.assert_not_called()
        apply_reset.assert_not_called()

    def test_reset_request_keeps_custom_connection_identity(self):
        entry, view, requested, apply_reset = self.prepare_reset_action()
        entry = dict(entry, _connection_id="account:work", _account_label="Work")
        view.update_provider("account:work", entry, "Codex (Pro) · Work")
        token = view.action["fingerprint"]
        view.action_buttons[0].click()
        self.assertIn("Codex (Pro) · Work", view.confirmation_text.text())
        view.confirm_button.click()
        requested.assert_called_once_with({
            "provider": "account:work", "idx": 0, "fingerprint": token,
            "credit": "b" * 64, "confirmed": True,
        })
        apply_reset.assert_not_called()

    def test_reset_actions_require_recent_identified_observation(self):
        entry, view, requested, apply_reset = self.prepare_reset_action()
        entry.pop("_fingerprint")
        self.dashboard.draw()
        self.assertTrue(all(button.isHidden() for button in view.action_buttons))
        entry["_fingerprint"] = "a" * 64
        entry["_observed_at"] = time.time() - tray.reset_actions.MAX_SNAPSHOT_AGE - 1
        self.dashboard.draw()
        self.assertTrue(all(button.isHidden() for button in view.action_buttons))
        requested.assert_not_called()
        apply_reset.assert_not_called()

    def test_reset_token_already_requested_stays_blocked_until_fresh_observation(self):
        entry, view, requested, apply_reset = self.prepare_reset_action()
        token = view.action["fingerprint"]
        view.attempts.add(token)
        self.dashboard.draw()
        self.assertFalse(view.action_buttons[0].isEnabled())
        view.action_buttons[0].click()
        view.begin_reset(tray.reset_credits.available_credits(entry["reset_credits"])["credits"][0])
        self.assertIsNone(view.target)
        entry["_fingerprint"] = "c" * 64
        entry["_observed_at"] = time.time()
        self.dashboard.draw()
        self.assertNotEqual(view.action["fingerprint"], token)
        self.assertTrue(view.action_buttons[0].isEnabled())
        requested.assert_not_called()
        apply_reset.assert_not_called()

    def test_escape_cancels_reset_confirmation_before_leaving_submenu(self):
        _, view, requested, apply_reset = self.prepare_reset_action()
        self.dashboard.show()
        self.app.processEvents()
        view.action_buttons[0].click()
        self.app.processEvents()
        self.assertTrue(view.cancel_button.hasFocus())
        QTest.keyClick(view.cancel_button, tray.Qt.Key.Key_Escape)
        self.assertTrue(view.confirmation.isHidden())
        self.assertIsNone(view.target)
        self.assertEqual(self.dashboard.reset_provider, ("codex", 0))
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.credits_scroll)
        requested.assert_not_called()
        apply_reset.assert_not_called()
        QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Escape)
        self.assertIsNone(self.dashboard.reset_provider)
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
        requested.assert_not_called()
        apply_reset.assert_not_called()

    def test_hiding_dashboard_discards_unconfirmed_reset(self):
        _, view, requested, apply_reset = self.prepare_reset_action()
        self.dashboard.show()
        self.app.processEvents()
        view.action_buttons[0].click()
        self.assertFalse(view.confirmation.isHidden())
        self.dashboard.hide()
        self.assertTrue(view.confirmation.isHidden())
        self.assertIsNone(view.target)
        view.confirm_reset()
        requested.assert_not_called()
        apply_reset.assert_not_called()

    def test_reset_result_status_is_visible_only_for_its_account(self):
        entry, view, requested, apply_reset = self.prepare_reset_action()
        message = "Reset applied. Refreshing account usage…"
        view.show_action_status(message, provider=("codex", 0))
        self.assertFalse(view.action_status.isHidden())
        work = dict(entry, _connection_id="account:work", _account_label="Work")
        view.update_provider("account:work", work, "Codex (Pro) · Work")
        self.assertTrue(view.action_status.isHidden())
        view.update_provider("codex", entry, "Codex (Pro)")
        self.assertFalse(view.action_status.isHidden())
        self.assertEqual(view.action_status.text(), message)
        requested.assert_not_called()
        apply_reset.assert_not_called()

    def test_many_reset_rows_scroll_without_changing_tray_selection(self):
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
            {"type": "rolling", "percentage": 3}, {"type": "weekly", "percentage": 23}],
            "reset_credits": {"available": 10, "credits": [
                {"title": "Full reset (Weekly + 5 hr)", "count": 1,
                 "expires_at": "2099-10-22T16:00:00Z"} for _ in range(10)]}}])
        self.dashboard.show()
        self.dashboard.provider_buttons[("codex", 0)].credits.click()
        self.app.processEvents()
        selected = state.load_selected()
        scroll = self.dashboard.credits_scroll
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        self.assertLessEqual(self.dashboard.height(), 720)
        self.assertLessEqual(self.dashboard.credits_view.width(), scroll.viewport().width())
        point = tray.QPoint(10, 10)
        event = QWheelEvent(tray.QPointF(point), tray.QPointF(scroll.viewport().mapToGlobal(point)),
                            tray.QPoint(), tray.QPoint(0, -120), tray.Qt.MouseButton.NoButton,
                            tray.Qt.KeyboardModifier.NoModifier, tray.Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(scroll.viewport(), event)
        self.app.processEvents()
        self.assertGreater(scroll.verticalScrollBar().value(), 0)
        self.assertEqual(state.load_selected(), selected)

    @staticmethod
    def update_guide(can_update=True):
        return {"method": "windows-installer" if can_update else "windows-portable",
                "title": "Update AI Status", "description": "Update this installation.",
                "steps": ["Download the latest installer.", "Run setup to keep your settings."],
                "command": "", "actionLabel": "Update now", "canUpdate": can_update,
                "releaseUrl": "https://github.com/gelzinn/ai-status/releases/latest",
                "guideUrl": "https://github.com/gelzinn/ai-status/blob/main/packages/lib/WINDOWS.md"}

    def wait_for_update(self):
        deadline = time.monotonic() + 5
        while self.dashboard.updating and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertFalse(self.dashboard.updating)

    def test_optional_update_link_opens_guide_and_back_restores_usage(self):
        version = {"current": "0.11.0", "latest": "0.12.1", "has_update": True}
        with patch.object(tray.fetch, "get_version_info", return_value=version), \
                patch.object(tray.updates, "update_guide", return_value=self.update_guide()):
            self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
                {"type": "weekly", "id": str(index), "percentage": 23} for index in range(15)]}])
            self.dashboard.show()
            self.app.processEvents()
            selected = state.load_selected()
            link = self.dashboard.update_link
            self.assertFalse(link.isHidden())
            self.assertEqual(self.dashboard.update_title.text(), "Update available: v0.12.1")
            self.assertIsInstance(link.findChild(tray.ArrowIcon), tray.ArrowIcon)
            link.setFocus()
            self.dashboard.scroll.verticalScrollBar().setValue(200)
            position = self.dashboard.scroll.verticalScrollBar().value()
            self.assertGreater(position, 0)
            QTest.keyClick(link, tray.Qt.Key.Key_Return)
            self.app.processEvents()
            self.assertTrue(self.dashboard.viewing_updates())
            self.assertEqual(self.dashboard.brand.text(), "Updates")
            self.assertIs(self.dashboard.focusWidget(), self.dashboard.back_button)
            self.assertEqual(self.dashboard.update_view.versions.text(), "v0.11.0 → v0.12.1")
            self.assertTrue(self.dashboard.update_view.action.isEnabled())
            QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Down)
            self.assertEqual(state.load_selected(), selected)
            QTest.keyClick(self.dashboard.back_button, tray.Qt.Key.Key_Escape)
            self.app.processEvents()
            self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.scroll)
            self.assertEqual(self.dashboard.scroll.verticalScrollBar().value(), position)
            self.assertTrue(link.hasFocus())
            self.assertEqual(state.load_selected(), selected)
            version["has_update"] = False
            self.dashboard.draw()
            self.assertTrue(link.isHidden())

    def test_portable_update_guide_offers_download_and_manual_links(self):
        with patch.object(tray.fetch, "get_version_info", return_value={"has_update": True}), \
                patch.object(tray.updates, "update_guide", return_value=self.update_guide(False)), \
                patch.object(tray.QDesktopServices, "openUrl") as browser, \
                patch.object(tray.updates, "run_update") as updater:
            self.dashboard.show_updates()
            self.assertTrue(self.dashboard.update_view.action.isHidden())
            self.dashboard.start_update()
            updater.assert_not_called()
            self.dashboard.update_view.findChild(tray.QPushButton, "update-releaseUrl").click()
            self.assertEqual(browser.call_args.args[0].toString(), self.update_guide(False)["releaseUrl"])
            self.dashboard.update_view.findChild(tray.QPushButton, "update-guideUrl").click()
            self.assertEqual(browser.call_args.args[0].toString(), self.update_guide(False)["guideUrl"])

    def test_update_action_runs_in_worker_and_error_allows_retry(self):
        version = {"current": "0.11.0", "latest": "0.12.1", "has_update": True}
        def failed_update(progress=None):
            progress("Verifying download…")
            raise OSError("Unable to download the update. Check your connection and retry.")
        with patch.object(tray.fetch, "get_version_info", return_value=version), \
                patch.object(tray.updates, "update_guide", return_value=self.update_guide()), \
                patch.object(tray.updates, "run_update", side_effect=failed_update) as updater:
            self.dashboard.show_updates()
            self.dashboard.update_view.action.click()
            self.assertTrue(self.dashboard.updating)
            self.assertFalse(self.dashboard.update_view.action.isEnabled())
            self.dashboard.start_update()
            self.wait_for_update()
            updater.assert_called_once()
            self.assertEqual(self.dashboard.update_view.status.text(), "Download failed. Check your connection.")
            self.assertIn("Check your connection", self.dashboard.update_view.status.toolTip())
            self.assertEqual(self.dashboard.update_view.action.text(), "Retry")
            self.assertTrue(self.dashboard.update_view.action.isEnabled())
            updater.side_effect = None
            updater.return_value = "The verified installer is open. Follow setup to update."
            self.dashboard.update_view.action.click()
            self.wait_for_update()
            self.assertEqual(updater.call_count, 2)
            self.assertTrue(self.dashboard.update_view.completed)
            self.assertTrue(self.dashboard.update_view.action.isEnabled())
            self.assertEqual(self.dashboard.update_view.action.text(), "Done")
            self.assertEqual(self.dashboard.update_view.status.text(), "Updater opened")
            self.assertIn("verified installer is open", self.dashboard.update_view.status.toolTip())
            self.dashboard.update_view.action.click()
            self.assertFalse(self.dashboard.viewing_updates())
            self.assertEqual(updater.call_count, 2)  # Done never opens a second setup wizard.
            self.dashboard.show_updates()  # Setup can be cancelled; a later action can retry.
            self.assertEqual(self.dashboard.update_view.action.text(), self.update_guide()["actionLabel"])
            version["has_update"] = False
            self.dashboard.update_view.set_guide(self.update_guide(), version)
            self.dashboard.on_update_finished("AI Status is already up to date.", True)
            self.assertEqual(self.dashboard.update_view.status.text(), "Up to date")
            self.assertTrue(self.dashboard.update_view.action.isEnabled())
            self.dashboard.update_view.action.click()
            self.assertFalse(self.dashboard.viewing_updates())
            self.assertEqual(updater.call_count, 2)

    def test_update_guide_command_can_be_copied(self):
        guide = self.update_guide(False)
        guide["command"] = "ai-status update"
        with patch.object(tray.fetch, "get_version_info", return_value={"has_update": True}), \
                patch.object(tray.updates, "update_guide", return_value=guide):
            self.dashboard.show_updates()
            self.dashboard.update_view.copy_button.click()
            self.assertEqual(self.app.clipboard().text(), "ai-status update")
            self.assertEqual(self.dashboard.update_view.copy_button.text(), "Copied")

    def test_release_notes_match_the_update_and_keep_the_footer_visible(self):
        version = {"current": "0.11.0", "latest": "0.12.1", "has_update": True}
        guide = self.update_guide()
        guide["releaseNotes"] = {
            "version": "0.12.1", "title": "v0.12.1", "url": guide["releaseUrl"],
            "body": "### Features\n" + "\n".join(f"- Improve **desktop feedback** {i}." for i in range(60)) +
                    "\n![Preview](file:///tmp/private.png)\n[Details](https://github.com/gelzinn/ai-status/releases)",
        }
        with patch.object(tray.fetch, "get_version_info", return_value=version), \
                patch.object(tray.updates, "update_guide", return_value=guide), \
                patch.object(tray.QDesktopServices, "openUrl") as browser:
            self.dashboard.show_updates()
            self.app.processEvents()
            view = self.dashboard.update_view
            self.assertTrue(view.notes_body.isVisible())
            self.assertIn("desktop feedback", view.notes_body.text())
            self.assertNotIn("<img", view.notes_body.text())
            self.assertGreater(self.dashboard.update_scroll.verticalScrollBar().maximum(), 0)
            self.assertTrue(view.action.isVisible())
            view.notes_body.linkActivated.emit("file:///tmp/private.png")
            browser.assert_not_called()
            view.notes_body.linkActivated.emit("https://github.com/gelzinn/ai-status/releases")
            self.assertEqual(browser.call_args.args[0].scheme(), "https")
            self.dashboard.on_update_finished("Installer opened.", True)
            self.app.processEvents()
            self.assertTrue(view.action.isVisible())
            self.assertLess(view.action.width(), view.footer.width() / 2)
            self.assertLess(view.status.geometry().right(), view.action.geometry().left())
            self.dashboard.on_update_finished("AI Status is already up to date.", True)
            view.set_guide(guide, version)
            self.assertTrue(view.notes_body.isHidden())
            view.completed = False
            guide["releaseNotes"]["version"] = "0.12.0"
            view.set_guide(guide, version)
            self.assertTrue(view.notes_body.isHidden())
            guide["releaseNotes"]["version"] = "0.12.1"
            version["has_update"] = False
            view.set_guide(guide, version)
            self.assertTrue(view.notes_heading.isHidden())

    def test_live_update_progress_stays_in_footer_and_survives_navigation(self):
        release = threading.Event()
        version = {"current": "0.11.0", "latest": "0.12.1", "has_update": True}

        def updating(progress=None):
            progress({"stage": "downloading", "message": "Downloading update…",
                      "downloadedBytes": 4_200_000, "totalBytes": 10_000_000, "percent": 42})
            if not release.wait(5):
                raise OSError("Fixture timed out")
            return "Installer opened. Complete setup to restart AI Status."

        with patch.object(tray.fetch, "get_version_info", return_value=version), \
                patch.object(tray.updates, "update_guide", return_value=self.update_guide()), \
                patch.object(tray.updates, "run_update", side_effect=updating):
            self.dashboard.show_updates()
            view = self.dashboard.update_view
            view.action.click()
            try:
                deadline = time.monotonic() + 3
                while view.percent.text() != "42%" and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertEqual(view.percent.text(), "42%")
                self.assertEqual(view.progress_bar.value(), 42)
                self.assertEqual(view.transferred.text(), "4.2 / 10.0 MB")
                self.assertEqual(view.remaining.text(), "5.8 MB left")
                self.assertTrue(view.spinner.running)
                self.assertTrue(view.action.isHidden())
                self.assertIs(view.footer.parentWidget(), self.dashboard.pages.parentWidget())
                self.assertGreaterEqual(view.footer.y(), self.dashboard.pages.geometry().bottom())
                self.dashboard.go_back()
                self.app.processEvents()
                self.assertTrue(view.footer.isHidden())
                self.dashboard.show_updates()
                self.app.processEvents()
                self.assertEqual(view.progress_bar.value(), 42)
                self.assertEqual(view.percent.text(), "42%")
                self.assertTrue(view.spinner.isVisible())
                self.assertTrue(view.progress_bar.isVisible())
                self.assertEqual(view.remaining.text(), "5.8 MB left")
                self.assertFalse(view.action.isEnabled())
            finally:
                release.set()
                self.wait_for_update()
            self.assertTrue(view.progress_bar.isHidden())
            self.assertTrue(view.spinner.isHidden())
            self.assertTrue(view.remaining.isHidden())
            self.assertEqual(view.status.text(), "Updater opened")
            self.assertTrue(view.result_icon.isVisible())
            self.assertIn("Complete setup", view.status.toolTip())

    def test_unknown_download_size_and_verification_do_not_show_fake_percentage(self):
        with patch.object(tray.fetch, "get_version_info", return_value={"has_update": True}), \
                patch.object(tray.updates, "update_guide", return_value=self.update_guide()):
            self.dashboard.show_updates()
            view = self.dashboard.update_view
            view.running = True
            view.show_progress({"stage": "downloading", "message": "Downloading update…",
                                "downloadedBytes": 2_500_000})
            self.assertEqual(view.progress_bar.maximum(), 0)
            self.assertTrue(view.percent.isHidden())
            self.assertEqual(view.transferred.text(), "2.5 MB downloaded")
            self.assertTrue(view.remaining.isHidden())
            view.show_progress({"stage": "verifying", "message": "Verifying update…"})
            self.assertEqual(view.progress_bar.maximum(), 0)
            self.assertTrue(view.transferred.isHidden())
            self.assertTrue(view.spinner.running)
            self.dashboard.on_update_finished("Download failed. Retry.", False)
            self.assertTrue(view.progress_bar.isHidden())
            self.assertFalse(view.spinner.running)
            self.assertEqual(view.action.text(), "Retry")
            self.assertTrue(view.action.isEnabled())

    def test_provider_settings_save_disabled_providers(self):
        settings = tray.ProviderSettings(self.dashboard)
        self.addCleanup(settings.deleteLater)
        for i in range(settings.providers.count()):
            settings.providers.item(i).setCheckState(tray.Qt.CheckState.Unchecked)
        with patch.object(paths, "IS_WINDOWS", False):
            settings.save()
        self.assertEqual(config.enabled_order(), [])

    def test_settings_display_names_preserve_ids_and_reordering(self):
        config.save_config(["zai", "commandcode", "claude"])
        settings = tray.ProviderSettings(self.dashboard)
        self.addCleanup(settings.deleteLater)
        self.assertEqual([settings.providers.item(i).text() for i in range(3)],
                         ["Z.AI", "Command Code", "Claude"])
        item = settings.providers.takeItem(2)
        settings.providers.insertItem(0, item)
        with patch.object(paths, "IS_WINDOWS", False):
            settings.save()
        self.assertEqual(config.enabled_order(), ["claude", "zai", "commandcode"])

    def test_clicking_provider_and_cycling_metrics_updates_tray_logo(self):
        self.dashboard.on_result("codex", [{"provider": "Codex (Pro)", "_idx": 0,
            "metrics": [{"type": "weekly", "percentage": 23}]}])
        self.dashboard.on_result("copilot", [{"provider": "Copilot", "_idx": 0,
            "metrics": [{"type": "monthly", "percentage": 7}]}])
        codex_icon = self.dashboard.tray.icon().pixmap(32, 32).toImage()
        self.dashboard.provider_buttons[("copilot", 0)].click()
        self.assertEqual(self.dashboard.tray.toolTip(), "Copilot 7%")
        self.assertNotEqual(codex_icon, self.dashboard.tray.icon().pixmap(32, 32).toImage())
        self.dashboard.cycle_metric(1)
        self.assertEqual(self.dashboard.tray.toolTip(), "Codex (Pro) 23%")
        self.assertEqual(state.load_selected()["provider"], "codex")

    def test_failed_selected_provider_falls_back_to_available_data(self):
        self.dashboard.on_result("codex", [{"provider": "Codex", "metrics": [{"type": "rolling", "percentage": 20}]}])
        self.dashboard.on_result("copilot", [{"provider": "Copilot", "metrics": [{"type": "monthly", "percentage": 7}]}])
        self.dashboard.on_error("codex", "Session expired")
        self.dashboard.on_result("codex", None)
        self.assertEqual(self.dashboard.selected["provider"], "copilot")
        self.assertEqual(len(self.dashboard.metric_values), 1)
        self.assertEqual(self.dashboard.tray.toolTip(), "Copilot 7%")

    def test_activation_file_opens_existing_app_without_qt_network(self):
        paths.atomic_json(paths.RUNTIME_DIR / "desktop-request.json", {"action": "config", "id": "new"})
        with patch.object(self.dashboard, "configure") as configure:
            self.dashboard.poll_state()
            self.dashboard.poll_state()
        configure.assert_called_once()

    def test_overlapping_refresh_is_queued(self):
        self.dashboard.busy = True
        with patch.object(state, "acquire_lock") as lock:
            self.dashboard.refresh()
        self.assertTrue(self.dashboard.queued)
        lock.assert_not_called()

    def test_refresh_worker_delivers_results_and_releases_lock(self):
        from core import fetch
        def collect(on_result=None, on_error=None, check_updates=False):
            self.assertTrue(check_updates)
            data = [{"provider": "Codex", "_dir": "codex", "_idx": 0,
                     "metrics": [{"type": "rolling", "percentage": 42}]}]
            on_result("codex", data)
            return data
        with patch.object(fetch, "fetch_all_data", side_effect=collect), patch.object(fetch, "check_for_updates"):
            self.dashboard.refresh()
            deadline = time.monotonic() + 5
            while self.dashboard.busy and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
        self.assertFalse(self.dashboard.busy)
        self.assertFalse(Path(state.LOCK_FILE).exists())
        self.assertIn("42%", self.dashboard.tray.toolTip())
        self.assertEqual(state.load_selected()["provider"], "codex")

    def test_exit_waits_for_worker(self):
        app = MagicMock()
        self.dashboard.app = app
        self.dashboard.busy = True
        self.dashboard.request_exit()
        app.quit.assert_not_called()
        self.dashboard.worker = MagicMock()
        self.dashboard.on_finished([])
        app.quit.assert_called_once()

    def test_windows_startup_quotes_packaged_executable(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = 1
        registry.REG_SZ = 1
        with patch.dict(sys.modules, {"winreg": registry}), patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(self.root / "ai-status-cli.exe")):
            tray.set_startup(True)
        command = registry.SetValueEx.call_args.args[-1]
        self.assertTrue(command.startswith('"'))
        self.assertIn("ai-status.exe", command)
        self.assertTrue(command.endswith(" tray"))


class ConPTYTests(unittest.TestCase):
    def test_windows_console_reads_usage_and_closes_process(self):
        from core import console, windows_console
        process = MagicMock()
        process.read.side_effect = ["Welcome to the Antigravity CLI\n>",
            "GEMINI MODELS\nWeekly Limit\n[=====]\n80%\nQuota available\n"]
        with patch.object(windows_console.PtyProcess, "spawn", return_value=process), patch.object(console, "cli_path", return_value="agy.exe"), patch.object(console.time, "monotonic", side_effect=[0, 1, 2, 3, 4]):
            raw = console.query_antigravity()
        self.assertIn("Weekly Limit", raw)
        process.write.assert_called_once_with("/usage\r")
        process.close.assert_called_once_with(force=True)

    def test_timeout_cleans_up_native_console(self):
        from core import console, windows_console
        from core.provider_http import QueryError
        process = MagicMock()
        with patch.object(windows_console.PtyProcess, "spawn", return_value=process), patch.object(console, "cli_path", return_value="agy.exe"), patch.object(console.time, "monotonic", side_effect=[0, 16]):
            with self.assertRaises(QueryError):
                console.query_antigravity()
        process.close.assert_called_once_with(force=True)


@unittest.skipUnless(sys.platform == "win32", "Requires the real Windows ConPTY APIs")
class NativeConsoleTests(IsolatedState):
    def collect(self, proc, marker):
        result = ""
        deadline = time.monotonic() + 8
        while marker not in result and time.monotonic() < deadline:
            try:
                result += proc.read(timeout=0.2)
            except TimeoutError:
                continue
            except EOFError:
                break
        self.assertIn(marker, result)
        return result

    def test_real_console_unicode_input_output_and_cleanup(self):
        from core.windows_console import PtyProcess
        proc = PtyProcess.spawn([sys.executable, "-u", "-c",
            "print('READY', flush=True); text=input(); print('READ:'+text, flush=True)"])
        try:
            self.collect(proc, "READY")
            proc.write("é café\r")
            self.collect(proc, "READ:é café")
        finally:
            proc.close(force=True)
        self.assertFalse(proc.reader.is_alive())
        self.assertFalse(proc.isalive())
        proc.close(force=True)

    def test_cmd_launcher_with_unicode_and_spaces(self):
        from core.windows_console import PtyProcess
        script = self.root / "provider helper.cmd"
        script.write_text("@echo off\r\necho ai-status-wrapper-ok\r\n", encoding="utf-8")
        proc = PtyProcess.spawn([str(script)])
        try:
            self.collect(proc, "ai-status-wrapper-ok")
        finally:
            proc.close(force=True)
        self.assertFalse(proc.reader.is_alive())

    def test_failed_spawn_closes_console_and_reader(self):
        from core.windows_console import PtyProcess
        before = {thread.ident for thread in __import__("threading").enumerate()}
        with self.assertRaises(OSError):
            PtyProcess.spawn([str(self.root / "missing.exe")])
        self.assertEqual({thread.ident for thread in __import__("threading").enumerate()}, before)


if __name__ == "__main__":
    unittest.main()
