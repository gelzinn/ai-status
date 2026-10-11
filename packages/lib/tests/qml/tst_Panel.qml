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
        function prepareUpdate(canUpdate) {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.version = {current: "0.11.0", latest: "0.12.1", has_update: true}
            snapshot.update = {
                title: "Update the Omarchy plugin", description: "Omarchy updates AI Status in place.",
                steps: ["Start the update.", "Wait for the plugin to reload."],
                command: "omarchy plugin update io.github.gelzinn.ai-status",
                canUpdate: canUpdate, actionLabel: "Update in terminal",
                releaseUrl: "https://github.com/gelzinn/ai-status/releases/tag/v0.12.1"
            }
            Plugin.Model.snapshot = snapshot
            wait(20)
        }
        function test_update_link_opens_guide_only_and_back_restores_focus() {
            prepareUpdate(true)
            const selected = JSON.stringify(Plugin.Model.snapshot.selected)
            const link = findChild(panel, "update-available")
            const scroller = findChild(panel, "panel-scroller")
            verify(link.visible)
            compare(link.text, "Update available: v0.12.1")
            compare(link.trailingIconName, "arrow-right")
            compare(link.foreground, "#89b4fa")
            mouseMove(link, 10, 10)
            verify(link.color.a > 0)
            compare(link.color.b, link.foreground.b)
            const scrollPosition = scroller.contentY
            mouseClick(link)
            wait(20)
            verify(panel.updatePage)
            compare(findChild(panel, "panel-title").text, "Update AI Status")
            verify(findChild(panel, "panel-back").activeFocus)
            verify(!findChild(panel, "panel-settings").visible)
            verify(!link.visible)
            compare(Plugin.Model.updateStarts, 0)
            compare(JSON.stringify(Plugin.Model.snapshot.selected), selected)
            verify(findChild(panel, "update-versions").text.indexOf("0.11.0") !== -1)
            compare(findChild(panel, "update-command").text, Plugin.Model.snapshot.update.command)
            keyClick(Qt.Key_Escape)
            wait(20)
            verify(!panel.updatePage)
            verify(panel.opened)
            verify(link.activeFocus)
            compare(scroller.contentY, scrollPosition)
            keyClick(Qt.Key_Return)
            verify(panel.updatePage)
            mouseClick(findChild(panel, "panel-back"))
            verify(!panel.updatePage)
        }
        function test_update_action_reports_failure_and_can_retry_without_forcing_update() {
            prepareUpdate(true)
            panel.showUpdate()
            wait(20)
            const action = findChild(panel, "update-action")
            mouseClick(action)
            compare(Plugin.Model.updateStarts, 1)
            verify(!action.enabled)
            mouseClick(action)
            compare(Plugin.Model.updateStarts, 1)
            Plugin.Model.updateError = "Terminal not found. Run the command above."
            Plugin.Model.updateRunning = false
            verify(action.enabled)
            compare(findChild(panel, "update-status").text, Plugin.Model.updateError)
            mouseClick(action)
            compare(Plugin.Model.updateStarts, 2)
            compare(Plugin.Model.updateError, "")
            panel.close()
            verify(!panel.updatePage)
            verify(Plugin.Model.updateRunning)
        }
        function test_manual_update_guide_keeps_command_and_release_notes_available() {
            prepareUpdate(false)
            mouseClick(findChild(panel, "update-available"))
            wait(20)
            verify(panel.updatePage)
            verify(!findChild(panel, "update-action").visible)
            verify(findChild(panel, "update-release-notes").visible)
            verify(findChild(panel, "update-copy-command").visible)
            compare(Plugin.Model.updateStarts, 0)
            Plugin.Model.updateError = ""
            panel.configure()
            verify(!panel.updatePage)
            verify(!findChild(panel, "update-available").visible)
        }
        function test_update_notice_does_not_replace_backend_error() {
            prepareUpdate(true)
            Plugin.Model.errorMessage = "Backend is reconnecting."
            verify(findChild(panel, "update-available").visible)
            compare(Plugin.Model.errorMessage, "Backend is reconnecting.")
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.version.has_update = false
            Plugin.Model.snapshot = snapshot
            verify(!findChild(panel, "update-available").visible)
            compare(Plugin.Model.updateStarts, 0)
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
            verify(findChild(panel, "reset-table").radius > 0)
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
