import sys
import time
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
        config.save_config(["codex", "copilot"])
        with patch.object(tray.QTimer, "singleShot"), patch.object(tray.QSystemTrayIcon, "show"):
            self.dashboard = tray.Dashboard(self.app)
        self.dashboard.poll.stop()
        self.dashboard.auto_refresh.stop()
        self.dashboard.animation.stop()
        self.addCleanup(self.dashboard.tray.hide)
        self.addCleanup(self.dashboard.deleteLater)

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
        with patch.object(self.dashboard, "refresh") as refresh:
            QTest.mouseClick(settings.save_button, tray.Qt.MouseButton.LeftButton)
        refresh.assert_called_once()
        self.assertIs(self.dashboard.pages.currentWidget(), self.dashboard.settings_scroll)
        self.assertEqual(settings.message.text(), "Saved")
        selected = state.load_selected()
        self.assertEqual(selected["metric"], "weekly")
        self.assertEqual(selected["icon_mode"], "logo")
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
        settings.display["show_metric"].setChecked(True)
        with patch.object(self.dashboard, "refresh"):
            settings.save()
        saved = state.load_selected()
        settings.display["show_metric"].setChecked(False)
        QTest.keyClick(settings.active, tray.Qt.Key.Key_Escape)
        self.assertFalse(self.dashboard.configuring())
        self.assertEqual(state.load_selected(), saved)
        self.dashboard.configure()
        settings = self.dashboard.settings_view
        self.assertTrue(settings.display["show_metric"].isChecked())
        settings.providers.item(0).setCheckState(tray.Qt.CheckState.Unchecked)
        settings.cancel_button.click()
        self.assertFalse(self.dashboard.configuring())
        self.assertEqual(config.enabled_order(), ["codex", "copilot"])

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
        text = "\n".join(label.text() for label in self.dashboard.credits_view.findChildren(QLabel))
        self.assertIn("Full reset", text)
        self.assertIn("Oct 22, 2099", text)
        self.assertIn("Not provided", text)  # The second credit's details are unavailable.
        self.assertEqual(state.load_selected(), selected)
        self.dashboard.data["codex"][0]["reset_credits"]["available"] = 0
        self.dashboard.draw()
        self.assertEqual(self.dashboard.credits_view.available.text(), "Available 0")
        self.assertTrue(self.dashboard.credits_view.table.isHidden())
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
        def collect(on_result=None, on_error=None):
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
