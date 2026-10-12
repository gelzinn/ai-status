import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from test_portability import IsolatedState
from core import config, paths, state

try:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QWheelEvent
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

    def test_about_returns_to_settings_without_discarding_draft_and_opens_project_links(self):
        with patch.object(self.dashboard, "isActiveWindow", return_value=True):
            self.dashboard.configure()
            self.app.processEvents()
            settings = self.dashboard.settings_view
            settings.icon_mode.setCurrentIndex(settings.icon_mode.findData("off"))
            settings.providers.move_provider(0, 1)
            order = [settings.providers.item(i).text() for i in range(settings.providers.count())]
            scroll = self.dashboard.settings_scroll.verticalScrollBar()
            scroll.setValue(scroll.maximum())
            position = scroll.value()
            settings.about_button.click()
            self.assertTrue(self.dashboard.viewing_about())
            self.assertEqual(self.dashboard.brand.text(), "About")
            self.assertTrue(self.dashboard.settings_footer.isHidden())
            labels = [label.text() for label in self.dashboard.about_view.findChildren(QLabel)]
            self.assertTrue(any("License: MIT" in text and "Author: gelzin.com" in text for text in labels))
            with patch.object(tray.QDesktopServices, "openUrl") as browser:
                self.dashboard.about_view.findChild(tray.QPushButton, "about-issues").click()
                self.assertEqual(browser.call_args.args[0].toString(), tray.about.GITHUB + "/issues/new")
            QTest.keyClick(self.dashboard, tray.Qt.Key.Key_Escape)
            self.assertTrue(self.dashboard.configuring())
            self.assertIs(self.dashboard.settings_view, settings)
            self.assertEqual(settings.icon_mode.currentData(), "off")
            self.assertEqual([settings.providers.item(i).text() for i in range(settings.providers.count())], order)
            self.assertEqual(scroll.value(), position)
            self.assertIs(self.dashboard.focusWidget(), settings.about_button)

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
        settings.notification_thresholds.setText("75, 90, 100")
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

    def test_invalid_notification_settings_are_rejected_before_any_save(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        for thresholds in ("eighty", "80, 101", "0", "80, 80"):
            settings.notification_thresholds.setText(thresholds)
            with patch.object(config, "save_connection_order") as save_order, \
                 patch.object(state, "_save_json") as save_selection, \
                 patch.object(tray.notifications, "save_settings") as save_notifications:
                settings.save()
            save_order.assert_not_called()
            save_selection.assert_not_called()
            save_notifications.assert_not_called()
            self.assertTrue(settings.message.text())
            self.assertNotEqual(settings.message.text(), "Saved")
        settings.notification_thresholds.setText("80, 95, 100")
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
        self.assertIn("threshold", settings.message.text())

    def test_provider_arrows_keyboard_and_native_move_preserve_checks_and_save_order(self):
        self.dashboard.configure()
        settings = self.dashboard.settings_view
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
                         ["Available balance: $75.00", "Available balance: $58.00"])
        self.assertFalse(any(row.title.text().startswith("Available balance") for row in self.dashboard.metric_buttons))
        self.assertLessEqual(self.dashboard.height(), 720)
        self.assertEqual(self.dashboard.scroll.verticalScrollBar().maximum(), 0)
        self.dashboard.metric_buttons[-1].click()
        self.assertEqual(state.load_selected()["provider"], "account:work")

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
                "command": "", "actionLabel": "Download and open installer", "canUpdate": can_update,
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
            self.assertIn("Installed: v0.11.0", self.dashboard.update_view.versions.text())
            self.assertIn("Latest: v0.12.1", self.dashboard.update_view.versions.text())
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
            self.assertIn("Check your connection", self.dashboard.update_view.status.text())
            self.assertEqual(self.dashboard.update_view.action.text(), "Retry update")
            self.assertTrue(self.dashboard.update_view.action.isEnabled())
            updater.side_effect = None
            updater.return_value = "The verified installer is open. Follow setup to update."
            self.dashboard.update_view.action.click()
            self.wait_for_update()
            self.assertEqual(updater.call_count, 2)
            self.assertTrue(self.dashboard.update_view.completed)
            self.assertTrue(self.dashboard.update_view.action.isEnabled())  # Setup can be cancelled.
            self.assertIn("verified installer is open", self.dashboard.update_view.status.text())

    def test_update_guide_command_can_be_copied(self):
        guide = self.update_guide(False)
        guide["command"] = "ai-status update"
        with patch.object(tray.fetch, "get_version_info", return_value={"has_update": True}), \
                patch.object(tray.updates, "update_guide", return_value=guide):
            self.dashboard.show_updates()
            self.dashboard.update_view.copy_button.click()
            self.assertEqual(self.app.clipboard().text(), "ai-status update")
            self.assertEqual(self.dashboard.update_view.copy_button.text(), "Copied")

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
