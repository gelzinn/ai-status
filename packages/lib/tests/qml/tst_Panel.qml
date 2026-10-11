import QtQuick
import QtTest
import "plugin" as Plugin

Item {
    width: 380
    height: 800
    Plugin.Panel { id: panel; width: 380; height: 700 }
    QtObject {
        id: hostBar
        property string fontFamily: "monospace"
        property var targets: []
        property var tooltipTarget: null
        property string tooltip: ""
        property int switchDirection: 0
        function registerClickTarget(target) { targets = targets.concat([target]) }
        function unregisterClickTarget(target) { targets = targets.filter(item => item !== target) }
        function showTooltip(target, text) { tooltipTarget = target; tooltip = text }
        function hideTooltip(target) { if (tooltipTarget === target) { tooltipTarget = null; tooltip = "" } }
        function switchPanelFrom(owner, direction) { switchDirection = direction; return true }
    }
    TestCase {
        name: "NativePanel"
        when: windowShown
        function init() {
            Plugin.Model.reset()
            Plugin.Model.settingsSaving = false
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[1].resetCredits = {available: 2, rows: [
                {title: "Full reset", count: 2, expires: "Oct 22, 18:05", remaining: "12d 2h left", timezone: "UTC+00:00"}
            ], undetailed: 0}
            Plugin.Model.snapshot = snapshot
            panel.open()
            wait(20)
        }
        function cleanup() { Plugin.Model.settingsSaving = false; panel.close(); panel.bar = null }
        function test_header_buttons_preserve_host_click_targets_and_tooltips() {
            panel.bar = hostBar
            const refresh = findChild(panel, "panel-refresh")
            const configure = findChild(panel, "panel-settings")
            const back = findChild(panel, "panel-back")
            compare(hostBar.targets.length, 3)
            verify(hostBar.targets.indexOf(refresh) !== -1)
            verify(hostBar.targets.indexOf(configure) !== -1)
            verify(hostBar.targets.indexOf(back) !== -1)
            mouseMove(panel, 1, 350)
            mouseMove(refresh, refresh.width / 2, refresh.height / 2)
            tryCompare(hostBar, "tooltipTarget", refresh)
            compare(hostBar.tooltip, "Refresh usage (R)")
            mouseClick(refresh)
            compare(hostBar.tooltipTarget, null)
            compare(Plugin.Model.actions[0], "refresh")
            verify(panel.switchPanel(-1))
            compare(hostBar.switchDirection, -1)
            panel.bar = null
            compare(hostBar.targets.length, 0)
        }
        function test_header_buttons_have_hover_only_fill_and_keyboard_focus_outline() {
            mouseMove(panel, 1, 350)
            const refresh = findChild(panel, "panel-refresh")
            const configure = findChild(panel, "panel-settings")
            compare(refresh.width, 28)
            compare(refresh.height, 28)
            compare(refresh.radius, 6)
            compare(findChild(refresh, "panel-refresh-icon").width, 16)
            compare(refresh.color, Qt.rgba(0, 0, 0, 0))
            compare(refresh.border.width, 0)
            compare(configure.color, Qt.rgba(0, 0, 0, 0))
            mouseMove(refresh, refresh.width / 2, refresh.height / 2)
            tryCompare(refresh, "tooltipHovered", true)
            compare(refresh.color, Qt.rgba(panel.barForeground.r, panel.barForeground.g, panel.barForeground.b, 0.09))
            mouseMove(panel, 1, 350)
            tryCompare(refresh, "tooltipHovered", false)
            refresh.forceActiveFocus(Qt.TabFocusReason)
            verify(refresh.activeFocus)
            compare(refresh.color, Qt.rgba(0, 0, 0, 0))
            compare(refresh.border.width, 1)
            compare(findChild(refresh, "panel-refresh-icon").foreground, Qt.lighter(panel.barForeground, 1.35))
            keyClick(Qt.Key_Tab)
            verify(configure.activeFocus)
            compare(configure.color, Qt.rgba(0, 0, 0, 0))
            compare(configure.border.width, 1)
            compare(findChild(configure, "panel-settings-icon").foreground, Qt.lighter(panel.barForeground, 1.35))
            compare(findChild(refresh, "panel-refresh-icon").foreground, panel.barForeground)
            keyClick(Qt.Key_Backtab)
            verify(refresh.activeFocus)
            panel.configure()
            wait(20)
            const back = findChild(panel, "panel-back")
            compare(back.radius, refresh.radius)
            compare(back.color, Qt.rgba(0, 0, 0, 0))
            back.forceActiveFocus(Qt.OtherFocusReason)
            compare(back.border.width, 0)
            compare(findChild(back, "panel-back-icon").foreground, panel.barForeground)
            findChild(panel, "settings-cancel").forceActiveFocus(Qt.OtherFocusReason)
            back.forceActiveFocus(Qt.TabFocusReason)
            compare(back.border.width, 1)
            compare(findChild(back, "panel-back-icon").foreground, Qt.lighter(panel.barForeground, 1.35))
            back.focusProgrammatically()
            compare(back.border.width, 0)
            findChild(panel, "settings-cancel").forceActiveFocus(Qt.OtherFocusReason)
            back.forceActiveFocus(Qt.TabFocusReason)
            mouseMove(back, back.width / 2, back.height / 2)
            tryCompare(back, "tooltipHovered", true)
            compare(back.color, Qt.rgba(panel.barForeground.r, panel.barForeground.g, panel.barForeground.b, 0.09))
            mouseClick(back)
            compare(back.border.width, 0)
            refresh.forceActiveFocus(Qt.OtherFocusReason)
            compare(refresh.border.width, 0)
            compare(refresh.color, Qt.rgba(0, 0, 0, 0))
            mouseMove(refresh, refresh.width / 2, refresh.height / 2)
            compare(refresh.border.width, 0)
            mouseClick(refresh)
            compare(refresh.border.width, 0)
        }
        function test_header_buttons_activate_with_keyboard_and_ignore_disabled_presses() {
            const refresh = findChild(panel, "panel-refresh")
            refresh.forceActiveFocus()
            keyClick(Qt.Key_Space)
            compare(Plugin.Model.actions[0], "refresh")
            const configure = findChild(panel, "panel-settings")
            configure.forceActiveFocus()
            keyClick(Qt.Key_Return)
            verify(panel.configurationPage)
            const back = findChild(panel, "panel-back")
            back.forceActiveFocus()
            keyClick(Qt.Key_Space)
            verify(!panel.configurationPage)
            configure.forceActiveFocus()
            keyClick(Qt.Key_Enter)
            verify(panel.configurationPage)
            Plugin.Model.settingsSaving = true
            verify(!back.enabled)
            mouseMove(back, back.width / 2, back.height / 2)
            verify(!back.tooltipHovered)
            compare(back.color, Qt.rgba(0, 0, 0, 0))
            compare(back.border.width, 0)
            compare(findChild(back, "panel-back-icon").foreground, panel.barForeground)
            back.triggerPress(Qt.LeftButton)
            verify(panel.configurationPage)
            mouseClick(back)
            verify(panel.configurationPage)
        }
        function test_keyboard_panel_tab_marks_back_focus_and_pointer_clears_it() {
            panel.showResetCredits("codex", 0)
            wait(20)
            const back = findChild(panel, "panel-back")
            const keyCatcher = findChild(panel, "panel-key-catcher")
            compare(back.border.width, 0)
            keyCatcher.forceActiveFocus()
            keyClick(Qt.Key_Tab)
            verify(back.activeFocus)
            compare(back.border.width, 1)
            compare(back.color, Qt.rgba(0, 0, 0, 0))
            mouseClick(back)
            compare(back.border.width, 0)
            wait(20)
            panel.configure()
            panel.showAbout()
            wait(20)
            compare(back.border.width, 0)
            keyCatcher.forceActiveFocus()
            keyClick(Qt.Key_Backtab)
            verify(back.activeFocus)
            compare(back.border.width, 1)
            mouseClick(back)
            compare(back.border.width, 0)
        }
        function test_panel_icons_use_shared_resource() {
            const refresh = findChild(findChild(panel, "panel-refresh"), "panel-refresh-icon")
            compare(refresh.pathData, Plugin.PanelIcons.data.paths["refresh-cw"].map(command => command.join(" ")).join(" "))
            verify(refresh.pathData.indexOf("C ") !== -1)
            verify(Plugin.PanelIcons.path("settings").indexOf("C ") !== -1)
            compare(Plugin.PanelIcons.path("arrow-left"), "M 12 19 L 5 12 L 12 5 M 19 12 L 5 12")
            compare(Plugin.PanelIcons.path("missing"), "")
        }
        function test_reset_navigation_uses_clicked_provider_and_back_restores_focus() {
            const selected = JSON.stringify(Plugin.Model.snapshot.selected)
            const button = findChild(panel, "reset-credits-codex-0")
            mouseClick(button)
            compare(panel.resetProvider.id, "codex")
            compare(panel.resetEntry.name, "Codex (Plus)")
            compare(JSON.stringify(Plugin.Model.snapshot.selected), selected)
            wait(20)
            const back = findChild(panel, "panel-back")
            verify(back.activeFocus)
            verify(back.visible)
            const title = findChild(panel, "panel-title")
            verify(back.x + back.width < title.x)
            const heading = findChild(panel, "reset-provider-heading")
            verify(!heading.activeFocusOnTab)
            verify(findChild(panel, "reset-back") === null)
            compare(findChild(panel, "reset-table").radius, 8)
            mouseClick(heading)
            compare(panel.resetProvider.id, "codex")
            compare(JSON.stringify(Plugin.Model.snapshot.selected), selected)
            back.forceActiveFocus()
            keyClick(Qt.Key_Escape)
            compare(panel.resetProvider, null)
            verify(panel.opened)
            wait(20)
            verify(button.activeFocus)
            keyClick(Qt.Key_Space)
            compare(panel.resetProvider.id, "codex")
            wait(20)
            mouseClick(back)
            compare(panel.resetProvider, null)
        }
        function test_reset_page_updates_and_returns_when_provider_disappears() {
            panel.showResetCredits("codex", 0)
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[1].resetCredits = null
            Plugin.Model.snapshot = snapshot
            compare(panel.resetProvider.id, "codex")
            verify(!findChild(panel, "reset-table").visible)
            snapshot.providers.pop()
            Plugin.Model.snapshot = JSON.parse(JSON.stringify(snapshot))
            tryCompare(panel, "resetProvider", null)
            verify(panel.opened)
        }
        function test_settings_and_escape_return_to_usage() {
            panel.configure()
            verify(panel.configurationPage)
            wait(20)
            keyClick(Qt.Key_Escape)
            verify(!panel.configurationPage)
            verify(panel.opened)
            keyClick(Qt.Key_Escape)
            verify(!panel.opened)
        }
        function test_header_back_is_before_settings_title() {
            const configure = findChild(panel, "panel-settings")
            verify(configure.visible)
            mouseClick(configure)
            verify(panel.configurationPage)
            wait(20)
            const back = findChild(panel, "panel-back")
            const title = findChild(panel, "panel-title")
            verify(back.visible)
            verify(back.x + back.width < title.x)
            compare(title.text, "Settings")
            verify(!configure.visible)
            verify(!findChild(panel, "panel-refresh").visible)
            mouseClick(back)
            verify(!panel.configurationPage)
            verify(panel.opened)
            verify(configure.visible)
        }
        function test_save_keeps_settings_open_after_backend_completion() {
            panel.configure()
            wait(20)
            const settings = findChild(panel, "panel-settings-page")
            settings.toggleProvider("kiro")
            settings.moveProvider(1, -1)
            const order = JSON.stringify(settings.order)
            mouseClick(findChild(panel, "settings-save"))
            compare(Plugin.Model.saved.enabled[0], "codex")
            verify(panel.configurationPage)
            Plugin.Model.settingsSaved()
            verify(panel.configurationPage)
            verify(panel.opened)
            verify(settings.saved)
            compare(JSON.stringify(settings.order), order)
            // A second edit/save remains possible without leaving the page.
            settings.toggleProvider("kiro")
            verify(!settings.saved)
            mouseClick(findChild(panel, "settings-save"))
            compare(Plugin.Model.saved.enabled.length, 2)
            Plugin.Model.settingsSaved()
            verify(panel.configurationPage)
            mouseClick(findChild(panel, "panel-back"))
            verify(!panel.configurationPage)
        }
        function test_about_back_preserves_settings_draft_and_scroll() {
            panel.configure()
            wait(20)
            const settings = findChild(panel, "panel-settings-page")
            settings.toggleProvider("kiro")
            settings.moveProvider(1, -1)
            const order = JSON.stringify(settings.order)
            const scroller = findChild(panel, "panel-scroller")
            scroller.contentY = Math.max(0, scroller.contentHeight - scroller.height)
            const scrollPosition = scroller.contentY
            mouseClick(findChild(settings, "settings-about"))
            wait(20)
            verify(panel.aboutPage)
            compare(findChild(panel, "panel-title").text, "About")
            verify(!findChild(panel, "settings-save").visible)
            const metadata = findChild(panel, "about-metadata")
            verify(metadata.text.indexOf("12345678") !== -1)
            verify(metadata.text.indexOf("gelzin.com") !== -1)
            keyClick(Qt.Key_Escape)
            wait(20)
            verify(!panel.aboutPage)
            verify(panel.configurationPage)
            compare(JSON.stringify(settings.order), order)
            verify(settings.enabledProviders.indexOf("kiro") !== -1)
            compare(scroller.contentY, scrollPosition)
            verify(findChild(settings, "settings-about").activeFocus)
            mouseClick(findChild(panel, "settings-save"))
            compare(Plugin.Model.saved.enabled[0], "codex")
        }
        function test_separator_reaches_sides_and_only_refresh_icon_spins() {
            const surface = findChild(panel, "panel-surface")
            const divider = findChild(panel, "panel-divider")
            compare(divider.mapToItem(surface, 0, 0).x, 0)
            compare(divider.width, surface.width)
            const button = findChild(panel, "panel-refresh")
            const icon = findChild(button, "panel-refresh-icon")
            const originalWidth = button.width
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.loading = true
            Plugin.Model.snapshot = snapshot
            verify(!button.enabled)
            tryVerify(() => icon.rotation > 0)
            const rotation = icon.rotation
            wait(40)
            verify(icon.rotation !== rotation)
            compare(button.rotation, 0)
            compare(button.width, originalWidth)
            snapshot.loading = false
            Plugin.Model.snapshot = JSON.parse(JSON.stringify(snapshot))
            verify(button.enabled)
            compare(icon.rotation, 0)
        }
    }
}
