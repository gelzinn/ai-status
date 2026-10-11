import QtQuick
import QtTest
import qs.Commons
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
            snapshot.providers[1].resetCredits = {available: 2, timezone: "Local time · UTC+00:00", rows: [
                {title: "Full reset", count: 2, expires: "Oct 22, 18:05", remaining: "12d 2h left", timezone: "UTC+00:00"}
            ], undetailed: 0}
            Plugin.Model.snapshot = snapshot
            panel.open()
            wait(20)
        }
        function cleanup() { Plugin.Model.settingsSaving = false; panel.close(); panel.bar = null }
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
        function test_update_back_preserves_manually_scrolled_usage() {
            prepareUpdate(true)
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            const original = snapshot.providers[0].metrics[0]
            for (let index = 0; index < 20; index++) {
                const metric = Object.assign({}, original, {key: "rolling:long-" + index, name: "Usage " + index})
                snapshot.providers[0].metrics.push(metric)
            }
            Plugin.Model.snapshot = snapshot
            wait(20)
            const link = findChild(panel, "update-available")
            const scroller = findChild(panel, "panel-scroller")
            verify(scroller.contentHeight > scroller.height * 2)
            link.forceActiveFocus(Qt.TabFocusReason)
            wait(20)
            verify(link.activeFocus)
            scroller.contentY = 200
            wait(20)
            compare(scroller.contentY, 200)
            verify(link.activeFocus)
            verify(link.mapToItem(scroller, 0, 0).y + link.height < 0)
            keyClick(Qt.Key_Return)
            wait(20)
            verify(panel.updatePage)
            compare(panel.usageScrollPosition, 200)
            keyClick(Qt.Key_Escape)
            wait(20)
            verify(!panel.updatePage)
            verify(link.activeFocus)
            compare(scroller.contentY, 200)
            const next = link.nextItemInFocusChain(true)
            keyClick(Qt.Key_Tab)
            tryVerify(() => next.activeFocus)
            verifyControlInViewport(next, scroller)
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
            compare(refresh.radius, Style.cornerRadius)
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
            compare(Plugin.PanelIcons.path("arrow-left"), "M 12 21 L 3 12 L 12 3 M 21 12 L 3 12")
            compare(Plugin.PanelIcons.path("missing"), "")
        }
        function configureManyProviders() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.settings.providerIds = {claude: "claude", codex: "codex", kiro: "kiro"}
            for (let index = 0; index < 20; index++) {
                const id = "account:scroll-" + index
                const entry = JSON.parse(JSON.stringify(snapshot.providers[0]))
                entry.id = id
                entry.providerId = "claude"
                entry.name = "Claude · Account " + (index + 1)
                snapshot.providers.push(entry)
                snapshot.settings.names[id] = entry.name
                snapshot.settings.providerIds[id] = "claude"
                snapshot.settings.order.push(id)
                snapshot.settings.enabled.push(id)
            }
            Plugin.Model.snapshot = snapshot
            panel.configure()
            wait(20)
            const scroller = findChild(panel, "panel-scroller")
            verify(scroller.contentHeight > scroller.height * 2)
            return findChild(panel, "panel-settings-page")
        }
        function verifyControlInViewport(control, scroller) {
            tryVerify(() => {
                const top = control.mapToItem(scroller, 0, 0).y
                return top >= -0.5 && top + control.height <= scroller.height + 0.5
            }, 1000, "Focused control must be fully visible: " + control.objectName)
        }
        function tabToNextControl(control, scroller, backwards) {
            const next = control.nextItemInFocusChain(!backwards)
            keyClick(backwards ? Qt.Key_Backtab : Qt.Key_Tab,
                     backwards ? Qt.ShiftModifier : Qt.NoModifier)
            tryVerify(() => next.activeFocus)
            verifyControlInViewport(next, scroller)
            return next
        }
        function test_tab_and_backtab_reveal_controls_through_long_settings() {
            const settings = configureManyProviders()
            const scroller = findChild(panel, "panel-scroller")
            const first = findChild(settings, "active-provider")
            const last = findChild(settings, "settings-about")
            first.forceActiveFocus(Qt.TabFocusReason)
            verifyControlInViewport(first, scroller)
            compare(scroller.contentY, 0)
            let focused = first
            let count = 0
            while (focused !== last && count++ < 100)
                focused = tabToNextControl(focused, scroller, false)
            compare(focused, last)
            verify(count > 40)
            verify(scroller.contentY > scroller.height)
            const bottomPosition = scroller.contentY
            count = 0
            while (focused !== first && count++ < 100)
                focused = tabToNextControl(focused, scroller, true)
            compare(focused, first)
            verify(scroller.contentY < bottomPosition)
            verifyControlInViewport(first, scroller)
        }
        function test_fixed_footer_and_header_focus_preserve_settings_scroll() {
            const settings = configureManyProviders()
            const scroller = findChild(panel, "panel-scroller")
            const about = findChild(settings, "settings-about")
            scroller.contentY = Math.max(0, scroller.contentHeight - scroller.height)
            about.forceActiveFocus(Qt.TabFocusReason)
            verifyControlInViewport(about, scroller)
            const position = scroller.contentY
            const cancel = findChild(panel, "settings-cancel")
            keyClick(Qt.Key_Tab)
            tryVerify(() => cancel.activeFocus)
            compare(scroller.contentY, position)
            const save = findChild(panel, "settings-save")
            keyClick(Qt.Key_Tab)
            tryVerify(() => save.activeFocus)
            compare(scroller.contentY, position)
            const back = findChild(panel, "panel-back")
            back.forceActiveFocus(Qt.TabFocusReason)
            wait(20)
            verify(back.activeFocus)
            compare(scroller.contentY, position)
        }
        function test_tab_dismisses_selector_without_scrolling_to_popup_overlay() {
            const settings = configureManyProviders()
            const scroller = findChild(panel, "panel-scroller")
            const selector = findChild(settings, "active-provider")
            selector.forceActiveFocus(Qt.TabFocusReason)
            verifyControlInViewport(selector, scroller)
            const position = scroller.contentY
            keyClick(Qt.Key_Space)
            tryVerify(() => selector.popupItem.activeFocus)
            verify(selector.popupOpen)
            compare(scroller.contentY, position)
            keyClick(Qt.Key_Tab)
            tryCompare(selector, "popupOpen", false)
            const next = findChild(settings, "display-show_provider")
            tryVerify(() => next.activeFocus)
            verifyControlInViewport(next, scroller)
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
            compare(findChild(panel, "reset-table").radius, Style.cornerRadius)
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
