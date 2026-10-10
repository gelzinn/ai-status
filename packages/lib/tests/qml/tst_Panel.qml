import QtQuick
import QtTest
import "plugin" as Plugin

Item {
    width: 380
    height: 800
    Plugin.Panel { id: panel; width: 380; height: 700 }
    TestCase {
        name: "NativePanel"
        when: windowShown
        function init() {
            Plugin.Model.reset()
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[1].resetCredits = {available: 2, rows: [
                {title: "Full reset", count: 2, expires: "Oct 22, 18:05", remaining: "12d 2h left", timezone: "UTC+00:00"}
            ], undetailed: 0}
            Plugin.Model.snapshot = snapshot
            panel.open()
            wait(20)
        }
        function cleanup() { panel.close() }
        function test_reset_navigation_uses_clicked_provider_and_back_restores_focus() {
            const selected = JSON.stringify(Plugin.Model.snapshot.selected)
            const button = findChild(panel, "reset-credits-codex-0")
            mouseClick(button)
            compare(panel.resetProvider.id, "codex")
            compare(panel.resetEntry.name, "Codex (Plus)")
            compare(JSON.stringify(Plugin.Model.snapshot.selected), selected)
            wait(20)
            const back = findChild(panel, "reset-back")
            verify(back.activeFocus)
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
    }
}
