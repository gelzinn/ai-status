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
            findChild(panel, "panel-update-page").commandExpanded = false
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[1].resetCredits = {available: 2, timezone: "Local time · UTC+00:00", rows: [
                {title: "Full reset", count: 2, expires: "Oct 22, 18:05", remaining: "12d 2h left", timezone: "UTC+00:00"}
            ], undetailed: 0}
            Plugin.Model.snapshot = snapshot
            panel.open()
            wait(20)
        }
        function cleanup() { Plugin.Model.settingsSaving = false; panel.close(); panel.bar = null }
        function cloudCredit(overrides) {
            return Object.assign({id: "claude-cloud", title: "Cloud credits", currency: "USD",
                status: "available", value: "$75.25", balance: 75.25, limit: 250, used: 174.75,
                limit_value: "$250.00", used_value: "$174.75", expires: "Nov 5, 2099 at 07:59",
                remaining: "12d 2h left", timezone: "UTC+00:00", stale: false,
                observed: "Oct 24, 2099 at 05:59", observed_value: "$75.25", status_note: ""}, overrides || {})
        }
        function withCloud(provider, credit) {
            const result = JSON.parse(JSON.stringify(provider))
            result.monetaryCredits = [credit || cloudCredit()]
            result.metrics.push({key: "credits:claude-cloud", name: "Cloud credits", type: "credits",
                value: result.monetaryCredits[0].value, percentage: null, hasPercentage: false,
                isAmount: result.monetaryCredits[0].status === "available", detail: "Expires 2099-11-05T07:59:00Z"})
            return result
        }
        function test_multiple_bar_items_keep_credit_actions_and_link_to_provider_settings() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.settings.items = [{provider: "claude", idx: 0, metric: "rolling"},
                                       {provider: "codex", idx: 0, metric: "weekly"}]
            snapshot.providers[0] = withCloud(snapshot.providers[0])
            Plugin.Model.snapshot = snapshot
            wait(20)
            const original = JSON.stringify(snapshot.settings.items)
            mouseClick(findChild(panel, "usage-metric-claude-0-credits:claude-cloud"))
            wait(20)
            compare(panel.creditSelection.creditId, "claude-cloud")
            panel.showUsage()
            wait(20)
            mouseClick(findChild(panel, "reset-credits-codex-0"))
            wait(20)
            compare(panel.resetProvider.id, "codex")
            panel.showUsage()
            wait(20)
            compare(Plugin.Model.chosen, null)
            compare(JSON.stringify(Plugin.Model.snapshot.settings.items), original)
            mouseClick(findChild(panel, "usage-bar-settings"))
            wait(20)
            verify(panel.configurationPage)
            compare(findChild(panel, "panel-settings-page").section, "providers")
            compare(Plugin.Model.chosen, null)
        }
        function prepareCloud() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[0] = withCloud(snapshot.providers[0])
            Plugin.Model.snapshot = snapshot
            wait(20)
            return findChild(panel, "usage-metric-claude-0-credits:claude-cloud")
        }
        function test_cloud_link_opens_details_and_back_restores_focus_without_selecting_credit() {
            const link = prepareCloud()
            const selected = JSON.stringify(Plugin.Model.snapshot.selected)
            const scroller = findChild(panel, "panel-scroller")
            const scrollPosition = scroller.contentY
            verify(!findChild(panel, "usage-detail-claude-0-credits:claude-cloud").visible)
            verify(findChild(panel, "usage-credit-arrow-claude-0-credits:claude-cloud").visible)
            mouseClick(findChild(panel, "usage-value-claude-0-credits:claude-cloud"))
            wait(20)
            compare(panel.creditSelection.id, "claude")
            compare(panel.creditSelection.idx, 0)
            compare(panel.creditSelection.creditId, "claude-cloud")
            compare(findChild(panel, "panel-title").text, "AI Status")
            compare(findChild(panel, "usage-credits-provider").text, "Claude (Max) · Cloud credits")
            compare(findChild(panel, "usage-credits-balance").text, "$75.25")
            compare(findChild(panel, "usage-credits-limit").text, "$250.00")
            compare(findChild(panel, "usage-credits-used").text, "$174.75")
            compare(findChild(panel, "usage-credits-expires").text, "Nov 5, 2099 at 07:59")
            compare(findChild(panel, "usage-credits-remaining").text, "12d 2h left")
            compare(findChild(panel, "usage-credits-timezone").text, "Local time · UTC+00:00")
            verify(findChild(panel, "panel-back").activeFocus)
            compare(JSON.stringify(Plugin.Model.snapshot.selected), selected)
            compare(Plugin.Model.chosen, null)
            keyClick(Qt.Key_Escape)
            wait(20)
            compare(panel.creditSelection, null)
            verify(link.activeFocus)
            compare(scroller.contentY, scrollPosition)
            keyClick(Qt.Key_Return)
            wait(20)
            verify(panel.creditSelection !== null)
            mouseClick(findChild(panel, "panel-back"))
            wait(20)
            verify(link.activeFocus)
            keyClick(Qt.Key_Space)
            wait(20)
            verify(panel.creditSelection !== null)
            compare(JSON.stringify(Plugin.Model.snapshot.selected), selected)
            compare(Plugin.Model.chosen, null)
        }
        function test_cloud_back_preserves_manually_scrolled_usage() {
            const link = prepareCloud()
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            const original = snapshot.providers[1].metrics[0]
            for (let index = 0; index < 25; index++) snapshot.providers[1].metrics.push(Object.assign({}, original, {key: "rolling:long-" + index}))
            Plugin.Model.snapshot = snapshot
            wait(20)
            const scroller = findChild(panel, "panel-scroller")
            link.forceActiveFocus(Qt.TabFocusReason)
            wait(20)
            scroller.contentY = 200
            wait(20)
            keyClick(Qt.Key_Return)
            wait(20)
            compare(panel.usageScrollPosition, 200)
            keyClick(Qt.Key_Escape)
            wait(20)
            verify(link.activeFocus)
            compare(scroller.contentY, 200)
            const next = link.nextItemInFocusChain(true)
            keyClick(Qt.Key_Tab)
            tryVerify(() => next.activeFocus)
            verifyControlInViewport(next, scroller)
        }
        function test_cloud_open_details_refresh_exhausted_expired_and_unavailable_states() {
            const link = prepareCloud()
            mouseClick(link)
            wait(20)
            const selected = JSON.stringify(Plugin.Model.snapshot.selected)
            const states = [
                {status: "exhausted", value: "$0.00", balance: 0, used: 250, used_value: "$250.00", observed_value: "$0.00"},
                {status: "expired", value: "Expired", balance: null, remaining: "Expired"},
                {status: "unavailable", value: "Unavailable", balance: null, stale: true, status_note: "Cached data is too old to confirm the balance."}
            ]
            for (const state of states) {
                const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
                snapshot.providers[0].monetaryCredits = [cloudCredit(state)]
                Plugin.Model.snapshot = snapshot
                wait(20)
                verify(panel.creditSelection !== null)
                compare(findChild(panel, "usage-credits-balance").text, state.value)
                compare(findChild(panel, "usage-credits-status").text.toLowerCase(), state.status)
                compare(JSON.stringify(Plugin.Model.snapshot.selected), selected)
                verify(findChild(panel, "panel-back").activeFocus)
                if (state.status === "expired" || state.status === "unavailable") {
                    compare(findChild(panel, "usage-credits-observed-balance").text, "$75.25")
                    compare(findChild(panel, "usage-credits-observed").text, "Oct 24, 2099 at 05:59")
                }
            }
            compare(findChild(panel, "usage-credits-unavailable").text, states[2].status_note)
            verify(findChild(panel, "usage-credits-unavailable").visible)
            const refresh = findChild(panel, "panel-refresh")
            mouseClick(refresh)
            compare(Plugin.Model.actions[0], "refresh")
            verify(panel.creditSelection !== null)
        }
        function test_cloud_details_keep_connection_account_index_and_credit_identity() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            const original = snapshot.providers[0]
            snapshot.providers = [
                withCloud(Object.assign({}, original, {id: "account:work", idx: 0, name: "Claude · Work"}), cloudCredit({value: "$10.00"})),
                withCloud(Object.assign({}, original, {id: "account:work", idx: 1, name: "Claude · Work second"}), cloudCredit({value: "$20.00"})),
                withCloud(Object.assign({}, original, {id: "account:personal", idx: 0, name: "Claude · Personal"}), cloudCredit({value: "$30.00"}))
            ]
            snapshot.providers[1].monetaryCredits.push(Object.assign({}, cloudCredit(), {id: "other-credit", title: "Other credit", value: "$40.00"}))
            Plugin.Model.snapshot = snapshot
            wait(20)
            const link = findChild(panel, "usage-metric-account:work-1-credits:claude-cloud")
            mouseClick(link)
            wait(20)
            compare(panel.creditSelection.id, "account:work")
            compare(panel.creditSelection.idx, 1)
            compare(findChild(panel, "usage-credits-provider").text, "Claude · Work second · Cloud credits")
            compare(findChild(panel, "usage-credits-balance").text, "$20.00")
            const updated = JSON.parse(JSON.stringify(snapshot))
            updated.providers[0].monetaryCredits[0].value = "$5.00"
            updated.providers[1].monetaryCredits.reverse()
            Plugin.Model.snapshot = updated
            wait(20)
            compare(findChild(panel, "usage-credits-balance").text, "$20.00")
            keyClick(Qt.Key_Escape)
            wait(20)
            verify(link.activeFocus)
            const personal = findChild(panel, "usage-metric-account:personal-0-credits:claude-cloud")
            personal.forceActiveFocus(Qt.TabFocusReason)
            wait(20)
            mouseClick(personal)
            wait(20)
            compare(findChild(panel, "usage-credits-balance").text, "$30.00")
            compare(findChild(panel, "usage-credits-provider").text, "Claude · Personal · Cloud credits")
        }
        function test_removed_cloud_credit_or_account_returns_to_usage_without_changing_selection() {
            for (const removeProvider of [false, true]) {
                const link = prepareCloud()
                const selected = JSON.stringify(Plugin.Model.snapshot.selected)
                mouseClick(link)
                wait(20)
                const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
                if (removeProvider) snapshot.providers.shift()
                else {
                    snapshot.providers[0].monetaryCredits = []
                    snapshot.providers[0].metrics.pop()
                }
                Plugin.Model.snapshot = snapshot
                tryCompare(panel, "creditSelection", null)
                verify(panel.opened)
                verify(!findChild(panel, "panel-usage-credits-page").visible)
                compare(JSON.stringify(Plugin.Model.snapshot.selected), selected)
                compare(Plugin.Model.chosen, null)
                Plugin.Model.reset()
                wait(20)
            }
        }
        function test_cloud_unknown_expiry_and_grant_values_are_not_invented() {
            prepareCloud()
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[0].monetaryCredits = [cloudCredit({expires: "", remaining: "", timezone: "", limit_value: "", used_value: ""})]
            Plugin.Model.snapshot = snapshot
            panel.showUsageCredits("claude", 0, "claude-cloud")
            wait(20)
            for (const id of ["limit", "used", "expires", "remaining"]) compare(findChild(panel, "usage-credits-" + id).text, "Not reported")
            verify(!findChild(panel, "usage-credits-timezone").visible)
        }
        function test_cloud_label_column_matches_reset_header_fill_and_has_right_border() {
            prepareCloud()
            const radius = Style.cornerRadius
            Style.cornerRadius = 8
            try {
                panel.showUsageCredits("claude", 0, "claude-cloud")
                wait(20)
                const table = findChild(panel, "usage-credits-table")
                const background = findChild(panel, "usage-credits-label-background")
                const divider = findChild(panel, "usage-credits-column-divider")
                const resetHeader = findChild(panel, "reset-column-header")
                compare(background.color, resetHeader.color)
                compare(background.color.a, 0.04)
                compare(background.x, 1)
                compare(background.y, 1)
                compare(background.radius, table.radius - 1)
                compare(background.height, table.height - 2)
                compare(divider.x, background.x + background.width)
                compare(divider.y, background.y)
                compare(divider.width, 1)
                compare(divider.height, background.height)
                compare(divider.color.a, 0.09)
                verify(findChild(panel, "usage-credits-status").x > background.width)
                compare(findChild(panel, "usage-credits-status").x, findChild(panel, "usage-credits-expires").x)
            } finally {
                Style.cornerRadius = radius
            }
        }
        function test_cloud_heading_places_credit_after_plan_and_balance_summary_has_small_gap() {
            prepareCloud()
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[0].name = "Claude (Max) · Personal"
            snapshot.providers[0].monetaryCredits[0].heading = "Claude (Max) · Cloud credits · Personal"
            Plugin.Model.snapshot = snapshot
            panel.showUsageCredits("claude", 0, "claude-cloud")
            wait(20)
            compare(findChild(panel, "usage-credits-provider").text, "Claude (Max) · Cloud credits · Personal")
            compare(findChild(panel, "usage-credits-title"), null)
            const summary = findChild(panel, "usage-credits-balance-summary")
            const label = findChild(panel, "usage-credits-balance-label")
            const balance = findChild(panel, "usage-credits-balance")
            compare(label.text, "Available balance")
            compare(balance.text, "$75.25")
            compare(balance.parent, summary)
            compare(balance.y - label.y - label.height, Style.space(4))
            compare(balance.font.pixelSize, 24)
            compare(summary.parent, findChild(panel, "usage-credits-table").parent)
            const expired = JSON.parse(JSON.stringify(snapshot))
            expired.providers[0].monetaryCredits[0].status = "expired"
            expired.providers[0].monetaryCredits[0].value = "Expired"
            Plugin.Model.snapshot = expired
            wait(20)
            compare(label.text, "Current balance")
            compare(balance.text, "Expired")
            compare(balance.y - label.y - label.height, Style.space(4))
        }
        function test_codex_usage_credits_are_selectable_and_separate_from_resets() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            const codex = snapshot.providers[1]
            const key = "credits:Usage credits (credits)"
            codex.metrics.push({key: key, type: "credits", name: "Usage credits",
                value: "62,500.00 credits", amount: 62500, unit: "credits",
                percentage: null, hasPercentage: false, isAmount: true,
                detail: "", resetInSeconds: null})
            Plugin.Model.snapshot = snapshot
            wait(20)
            const prefix = "codex-0-" + key
            const title = findChild(panel, "usage-title-" + prefix)
            const value = findChild(panel, "usage-value-" + prefix)
            compare(title.text, "Usage credits:")
            compare(value.text, "62,500.00 credits")
            verify(value.visible)
            verify(!findChild(panel, "usage-bar-" + prefix).visible)
            compare(findChild(panel, "reset-credits-codex-0").text, "Reset credits: 2 available")
            const metric = findChild(panel, "usage-metric-" + prefix)
            mouseClick(metric)
            compare(Plugin.Model.chosen.provider, "codex")
            compare(Plugin.Model.chosen.metric, key)
            mouseClick(findChild(panel, "reset-credits-codex-0"))
            compare(panel.resetProvider.id, "codex")
            verify(findChild(panel, "reset-table").visible)
        }
        function prepareUpdate(canUpdate) {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.version = {current: "0.11.0", latest: "0.12.1", has_update: true}
            snapshot.update = {
                method: "omarchy",
                title: "Update the Omarchy plugin", description: "Updates in Terminal, then restarts the shell. Your settings are kept.",
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
            for (let index = 0; index < 30; index++) {
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
            verify(!action.visible)
            Plugin.Model.startUpdate()
            compare(Plugin.Model.updateStarts, 1)
            Plugin.Model.updateError = "Terminal not found. Run the command above."
            Plugin.Model.updateRunning = false
            verify(action.enabled)
            verify(action.visible)
            compare(action.text, "Retry")
            const label = findChild(panel, "update-status-label")
            const status = findChild(panel, "update-status")
            const footer = findChild(panel, "update-footer")
            wait(20)
            verify(action.width < footer.width)
            compare(action.x + action.width, footer.width)
            verify(status.x + status.width < action.x)
            verify(action.height >= Style.space(34))
            compare(label.text, "Update failed: Terminal unavailable")
            const icon = findChild(panel, "update-status-icon")
            verify(!findChild(panel, "update-status-detail"))
            compare(label.wrapMode, Text.WordWrap)
            compare(label.Accessible.description, Plugin.Model.updateError)
            verify(icon.visible)
            compare(icon.name, "info")
            compare(icon.width, Style.space(16))
            compare(icon.foreground, label.color)
            compare(icon.foreground, "#f5a3a3")
            const failures = [
                ["The checksum did not match. Nothing was installed.", "Verification failed: checksum mismatch"],
                ["Could not download the release checksum.", "Update failed: checksum unavailable"],
                ["This release has no valid update checksum.", "Update failed: invalid release checksum"],
                ["Windows PowerShell is unavailable.", "Update failed: PowerShell unavailable"],
                ["The AI Status runtime is unavailable.", "Update failed: updater unavailable"],
                ["Terminal did not respond.", "Update failed: Terminal not responding"],
                ["Could not open Terminal.", "Update failed: could not open Terminal"],
                ["The updater timed out.", "Update failed: updater timed out"],
                ["The download was interrupted. Check your connection and retry.", "Download failed: transfer interrupted"],
                ["Installer download failed. Check your connection.", "Download failed. Check your connection."],
                ["The updater returned invalid progress.", "Update failed: invalid updater response"],
                ["The updater stopped before confirming the update.", "Update failed: completion not confirmed"],
                ["Unknown updater failure. Keep the complete original text.", "Unknown updater failure. Keep the complete original text."],
                ["\n Unknown updater failure.\nAdditional diagnostic detail", "Unknown updater failure."]
            ]
            for (const failure of failures) {
                Plugin.Model.updateError = failure[0]
                compare(label.text, failure[1])
                compare(label.Accessible.description, failure[0])
                verify(!findChild(panel, "update-status-detail"))
            }
            Plugin.Model.updateError = "No supported terminal found. Run the command shown in the guide in your terminal."
            compare(label.text, "Update failed: Terminal unavailable")
            compare(label.Accessible.description, Plugin.Model.updateError)
            verify(findChild(panel, "update-command-box").visible)
            compare(findChild(panel, "update-manual-command").text, "Hide manual update")
            action.forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Return)
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
            verify(!findChild(panel, "update-footer").visible)
            verify(!findChild(panel, "update-status-detail"))
            verify(findChild(panel, "update-release-notes").visible)
            compare(findChild(panel, "update-guide-link").text, "Installation guide")
            verify(findChild(panel, "update-guide-link").outlined)
            verify(findChild(panel, "update-copy-command").visible)
            compare(Plugin.Model.updateStarts, 0)
            const copy = findChild(panel, "update-copy-command")
            copy.forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Return)
            compare(copy.iconName, "check")
            Plugin.Model.updateError = ""
            panel.configure()
            verify(!panel.updatePage)
            verify(!findChild(panel, "update-available").visible)
        }
        function test_update_footer_shows_real_handoff_and_preserves_manual_fallback() {
            prepareUpdate(true)
            panel.showUpdate()
            wait(20)
            const footer = findChild(panel, "update-footer")
            const scroller = findChild(panel, "panel-scroller")
            const separator = findChild(panel, "update-footer-divider")
            const icon = findChild(panel, "update-status-icon")
            const progress = findChild(panel, "update-progress")
            const label = findChild(panel, "update-status-label")
            const action = findChild(panel, "update-action")
            const command = findChild(panel, "update-command-box")
            verify(footer.visible)
            verify(!findChild(panel, "settings-footer").visible)
            compare(scroller.mapToItem(footer, 0, scroller.height).y, separator.y)
            verify(!command.visible)
            verify(!progress.visible)
            compare(action.text, "Update now")
            verify(!action.primary)
            verify(action.outlined)
            verify(action.alignLeft)
            compare(action.iconName, "")
            compare(action.leadingIconName, "")
            compare(action.trailingIconName, "")
            compare(action.width, footer.width)
            compare(action.x, 0)
            compare(icon.width, Style.space(16))
            compare(label.font.pixelSize, Style.font.body)
            verify(!findChild(panel, "update-status-detail"))
            compare(findChild(panel, "update-manual-command").text, "Update manually…")
            verify(findChild(panel, "update-manual-command").outlined)
            verify(findChild(panel, "update-release-notes").outlined)
            verify(findChild(panel, "update-guide-link").outlined)
            mouseClick(findChild(panel, "update-manual-command"))
            wait(20)
            verify(command.visible)
            compare(findChild(panel, "update-manual-command").text, "Hide manual update")
            compare(findChild(panel, "update-command").text, Plugin.Model.snapshot.update.command)
            const copy = findChild(panel, "update-copy-command")
            mouseClick(copy)
            compare(copy.iconName, "check")
            mouseClick(action)
            wait(20)
            const footerBottom = footer.y + footer.height
            compare(Plugin.Model.updateStarts, 1)
            compare(icon.name, "loader-circle")
            tryVerify(() => icon.rotation > 0)
            compare(label.text, "Checking for updates…")
            compare(findChild(panel, "update-status").width, footer.width)
            verify(!action.visible)
            verify(!findChild(panel, "update-status-detail"))
            verify(progress.visible)
            verify(progress.animating)
            const phase = progress.phase
            tryVerify(() => progress.phase !== phase)
            verify(!action.enabled)
            Plugin.Model.updateStage = "opening"
            Plugin.Model.updateMessage = "Opening the updater in a terminal…"
            compare(label.text, "Opening updater…")
            verify(!findChild(panel, "update-status-detail"))
            verify(!action.visible)
            compare(footer.y + footer.height, footerBottom)
            panel.showUsage()
            tryCompare(icon, "rotation", 0)
            verify(!progress.animating)
            panel.showUpdate()
            tryVerify(() => icon.rotation > 0)
            Plugin.Model.updateMessage = "The updater is open in a terminal. Follow its progress there."
            Plugin.Model.updateRunning = false
            wait(20)
            compare(label.text, "Updater opened")
            compare(icon.name, "check")
            compare(icon.foreground, label.color)
            tryCompare(icon, "rotation", 0)
            verify(!progress.visible)
            verify(!progress.animating)
            verify(!findChild(panel, "update-status-detail"))
            verify(action.visible)
            verify(!findChild(panel, "update-description"))
            verify(!findChild(panel, "update-next-step"))
            compare(action.text, "Done")
            verify(action.width < footer.width)
            compare(action.x + action.width, footer.width)
            verify(findChild(panel, "update-status").width < action.x)
            mouseClick(action)
            verify(!panel.updatePage)
            compare(Plugin.Model.updateStarts, 1)
        }
        function test_update_already_current_does_not_claim_terminal_opened() {
            prepareUpdate(true)
            panel.showUpdate()
            wait(20)
            mouseClick(findChild(panel, "update-action"))
            Plugin.Model.updateMessage = "AI Status is already up to date."
            Plugin.Model.updateRunning = false
            compare(findChild(panel, "update-status-label").text, "Up to date")
            verify(!findChild(panel, "update-description"))
            verify(!findChild(panel, "update-next-step"))
            compare(findChild(panel, "update-versions").text, "v0.11.0")
            verify(!findChild(panel, "update-status-detail"))
            compare(findChild(panel, "update-status-icon").name, "check")
            compare(findChild(panel, "update-status-icon").foreground, findChild(panel, "update-status-label").color)
            compare(findChild(panel, "update-action").text, "Done")
            verify(findChild(panel, "update-action").outlined)
            wait(20)
            const action = findChild(panel, "update-action")
            const footer = findChild(panel, "update-footer")
            verify(action.width < footer.width)
            compare(action.x + action.width, footer.width)
            verify(findChild(panel, "update-status").width < action.x)
            verify(!findChild(panel, "update-progress").visible)
        }
        function test_release_notes_are_inline_optional_and_keep_update_footer_fixed() {
            prepareUpdate(true)
            panel.showUpdate()
            wait(20)
            const page = findChild(panel, "panel-update-page")
            const notes = findChild(panel, "update-release-notes-content")
            const body = findChild(panel, "update-release-notes-body")
            const footer = findChild(panel, "update-footer")
            const scroller = findChild(panel, "panel-scroller")
            verify(!notes.visible)
            compare(body.text, "")
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.update.releaseNotes = {version: snapshot.version.latest, title: "New panel", body: "### Features\n- **Progress** in the panel.\n\n```sh\nai-status --update\n```\n", url: "https://github.com/gelzinn/ai-status/releases/tag/v" + snapshot.version.latest}
            Plugin.Model.snapshot = snapshot
            wait(20)
            verify(notes.visible)
            verify(body.readOnly)
            verify(body.selectByMouse)
            compare(body.textFormat, TextEdit.MarkdownText)
            compare(body.wrapMode, TextEdit.Wrap)
            verify(body.getText(0, body.length).indexOf("Progress in the panel.") !== -1)
            verify(body.getText(0, body.length).indexOf("ai-status --update") !== -1)
            verify(body.implicitHeight > 0)
            verify(page.isSafeReleaseNotesLink("https://github.com/gelzinn/ai-status/releases/tag/v0.12.1"))
            verify(page.isSafeReleaseNotesLink("http://example.com/notes"))
            verify(!page.isSafeReleaseNotesLink("javascript:alert(1)"))
            verify(!page.isSafeReleaseNotesLink("file:///tmp/update.sh"))
            compare(page.safeReleaseNotesMarkdown("<img src='file:///tmp/private.png'>\n![Preview](https://example.com/p.png)\n`<safe-code>`"), "&lt;img src='file:///tmp/private.png'&gt;\n[Preview](https://example.com/p.png)\n`<safe-code>`")
            compare(page.safeReleaseNotesMarkdown("```html\n<img src='example'>\n```"), "```html\n<img src='example'>\n```")
            const longSnapshot = JSON.parse(JSON.stringify(snapshot))
            longSnapshot.update.releaseNotes.body = "### Features\n" + Array(50).fill("- Keep the update status visible while reviewing release notes.").join("\n")
            Plugin.Model.snapshot = longSnapshot
            wait(20)
            verify(scroller.contentHeight > scroller.height)
            compare(scroller.mapToItem(footer, 0, scroller.height).y, 0)
            const footerBottom = footer.y + footer.height
            scroller.contentY = Math.min(150, scroller.contentHeight - scroller.height)
            wait(20)
            compare(footer.y + footer.height, footerBottom)
            verify(findChild(panel, "update-action").visible)
            const mismatched = JSON.parse(JSON.stringify(snapshot))
            mismatched.update.releaseNotes.version = "0.1.0"
            Plugin.Model.snapshot = mismatched
            wait(20)
            verify(!notes.visible)
            compare(body.text, "")
            const empty = JSON.parse(JSON.stringify(snapshot))
            empty.update.releaseNotes.body = " \n "
            Plugin.Model.snapshot = empty
            verify(!notes.visible)
            verify(findChild(panel, "update-release-notes").visible)
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
            verify(findChild(panel, "settings-nav-about").activeFocus)
            compare(findChild(panel, "panel-settings-page").section, "about")
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
        function configureManyProviders() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.settings.providerIds = {claude: "claude", codex: "codex", kiro: "kiro"}
            for (let index = 0; index < 30; index++) {
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
            const settings = findChild(panel, "panel-settings-page")
            settings.selectSection("providers")
            wait(20)
            const scroller = findChild(panel, "panel-scroller")
            verify(scroller.contentHeight > scroller.height * 2)
            return settings
        }
        function verifyControlInViewport(control, scroller) {
            tryVerify(() => {
                const top = control.mapToItem(scroller, 0, 0).y
                return top >= scroller.navigationInset - 0.5 && top + control.height <= scroller.height + 0.5
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
            const first = findChild(settings, "provider-claude")
            const last = findChild(settings, "provider-move-up-" + settings.order[settings.order.length - 1])
            first.forceActiveFocus(Qt.TabFocusReason)
            verifyControlInViewport(first, scroller)
            let focused = first
            let count = 0
            while (focused !== last && count++ < settings.order.length * 10)
                focused = tabToNextControl(focused, scroller, false)
            compare(focused, last)
            verify(count > 40)
            verify(scroller.contentY > scroller.height)
            const bottomPosition = scroller.contentY
            count = 0
            while (focused !== first && count++ < settings.order.length * 10)
                focused = tabToNextControl(focused, scroller, true)
            compare(focused, first)
            verify(scroller.contentY < bottomPosition)
            verifyControlInViewport(first, scroller)
        }
        function test_fixed_footer_and_header_focus_preserve_settings_scroll() {
            const settings = configureManyProviders()
            const scroller = findChild(panel, "panel-scroller")
            const about = findChild(settings, "provider-move-up-" + settings.order[settings.order.length - 1])
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
        function test_submenu_navigation_is_fixed_and_preserves_draft_and_keyboard_access() {
            const settings = configureManyProviders()
            settings.toggleProvider("kiro")
            settings.usageDisplay = "remaining"
            const scroller = findChild(panel, "panel-scroller")
            const navigation = findChild(panel, "settings-navigation")
            const providers = findChild(panel, "settings-nav-providers")
            const general = findChild(panel, "settings-nav-general")
            compare(findChild(panel, "settings-nav-appearance"), null)
            const navY = navigation.y
            scroller.contentY = scroller.contentHeight - scroller.height
            providers.forceActiveFocus(Qt.TabFocusReason)
            wait(20)
            compare(navigation.y, navY)
            verify(scroller.contentY > scroller.height)
            verify(navigation.contentWidth > navigation.width)
            verify(navigation.contentX > 0)
            verify(providers.mapToItem(navigation, 0, 0).x >= 0)
            verify(providers.mapToItem(navigation, providers.width, 0).x <= navigation.width + 0.5)
            keyClick(Qt.Key_Left)
            compare(settings.section, "alerts")
            keyClick(Qt.Key_Left)
            verify(general.activeFocus)
            keyClick(Qt.Key_Return)
            compare(settings.section, "general")
            tryCompare(scroller, "contentY", 0)
            compare(settings.usageDisplay, "remaining")
            verify(settings.enabledProviders.indexOf("kiro") !== -1)
            wait(20)
            compare(navigation.contentX, 0)
            general.forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Tab)
            verify(findChild(panel, "settings-nav-alerts").activeFocus)
            keyClick(Qt.Key_Tab)
            verify(providers.activeFocus)
            keyClick(Qt.Key_Tab)
            verify(findChild(panel, "settings-nav-guide").activeFocus)
            keyClick(Qt.Key_Tab)
            verify(findChild(panel, "settings-nav-about").activeFocus)
            keyClick(Qt.Key_Tab)
            // General starts with refresh; provider and bar choices share Providers.
            verify(findChild(settings, "refresh-interval-slider").activeFocus)
            keyClick(Qt.Key_Tab)
            verify(findChild(settings, "usage-display").activeFocus)
            keyClick(Qt.Key_Tab)
            verify(findChild(settings, "show-total").activeFocus)
            for (const key of ["show_provider", "show_model", "show_metric", "show_pct"]) {
                keyClick(Qt.Key_Tab)
                verify(findChild(settings, "display-" + key).activeFocus)
            }
            keyClick(Qt.Key_Tab)
            verify(findChild(settings, "icon-mode").activeFocus)
            keyClick(Qt.Key_Tab)
            verify(findChild(panel, "settings-cancel").activeFocus)
            Plugin.Model.settingsSaving = true
            verify(!navigation.enabled)
            settings.selectSection("providers")
            compare(settings.section, "general")
            Plugin.Model.settingsSaving = false
            mouseClick(findChild(panel, "settings-save"))
            compare(Plugin.Model.saved.usageDisplay, "remaining")
            panel.showUsage()
            panel.configure()
            compare(settings.section, "general")
            compare(settings.usageDisplay, "used")
        }
        function test_hidden_validation_stays_in_fixed_footer_and_routes_to_affected_section() {
            const settings = configureManyProviders()
            const scroller = findChild(panel, "panel-scroller")
            settings.alertThresholds = "101"
            wait(20)
            compare(scroller.contentY, 0)
            verify(!findChild(panel, "settings-save").enabled)
            const review = findChild(panel, "settings-review-section")
            const footer = findChild(panel, "settings-footer")
            verify(review.visible)
            verify(review.mapToItem(footer, 0, 0).y >= 0)
            verify(review.mapToItem(footer, 0, review.height).y <= footer.height)
            verify(findChild(panel, "settings-validation-message").visible)
            mouseClick(review)
            compare(settings.section, "alerts")
            verify(!review.visible)
            settings.alertThresholds = "80,95,100"
            wait(20)
            verify(findChild(panel, "settings-save").enabled)
            verify(!findChild(panel, "settings-validation-message").visible)
        }
        function test_horizontal_tab_strip_scrolls_without_changing_section_or_content_scroll() {
            panel.configure()
            wait(20)
            const settings = findChild(panel, "panel-settings-page")
            const navigation = findChild(panel, "settings-navigation")
            const scroller = findChild(panel, "panel-scroller")
            verify(navigation.contentWidth > navigation.width)
            compare(navigation.contentX, 0)
            mouseWheel(navigation, navigation.width / 2, navigation.height / 2, 0, -120)
            tryVerify(() => navigation.contentX > 0)
            compare(settings.section, "general")
            compare(scroller.contentY, 0)
            mouseWheel(navigation, navigation.width / 2, navigation.height / 2, 120, 0)
            tryCompare(navigation, "contentX", 0)
            settings.selectSection("providers")
            wait(20)
            const providers = findChild(panel, "settings-nav-providers")
            verify(providers.mapToItem(navigation, 0, 0).x >= 0)
            verify(providers.mapToItem(navigation, providers.width, 0).x <= navigation.width + 0.5)
        }
        function test_scroll_viewports_reach_edges_with_padding_inside_scrollable_content() {
            const settings = configureManyProviders()
            const surface = findChild(panel, "panel-surface")
            const navigation = findChild(panel, "settings-navigation")
            const scroller = findChild(panel, "panel-scroller")
            const footer = findChild(panel, "settings-footer")
            compare(navigation.mapToItem(surface, 0, 0).x, 0)
            compare(navigation.width, surface.width)
            compare(scroller.mapToItem(surface, 0, 0).x, 0)
            compare(scroller.width, surface.width)
            compare(scroller.y + scroller.navigationInset, navigation.y + navigation.height)
            compare(scroller.y + scroller.height, footer.y)
            settings.selectSection("general")
            wait(20)
            const general = findChild(panel, "settings-nav-general")
            compare(navigation.contentX, 0)
            compare(general.mapToItem(navigation, 0, 0).x, 16)
            settings.selectSection("about")
            wait(20)
            const lastTab = findChild(panel, "settings-nav-about")
            compare(navigation.contentX, navigation.contentWidth - navigation.width)
            compare(lastTab.mapToItem(navigation, lastTab.width, 0).x, navigation.width - 16)
            settings.selectSection("providers")
            wait(20)
            compare(settings.mapToItem(scroller, 0, 0).y, scroller.navigationInset + 12)
            scroller.contentY = scroller.contentHeight - scroller.height
            compare(settings.mapToItem(scroller, 0, settings.height).y, scroller.height - 12)
            verify(settings.mapToItem(scroller, 0, 0).y < 0)
        }
        function test_tab_dismisses_selector_without_scrolling_to_popup_overlay() {
            const settings = configureManyProviders()
            settings.selectSection("general")
            wait(20)
            const scroller = findChild(panel, "panel-scroller")
            const selector = findChild(settings, "icon-mode")
            selector.forceActiveFocus(Qt.TabFocusReason)
            verifyControlInViewport(selector, scroller)
            const position = scroller.contentY
            keyClick(Qt.Key_Space)
            tryVerify(() => selector.popupItem.activeFocus)
            verify(selector.popupOpen)
            compare(scroller.contentY, position)
            keyClick(Qt.Key_Tab)
            tryCompare(selector, "popupOpen", false)
            const cancel = findChild(panel, "settings-cancel")
            tryVerify(() => cancel.activeFocus)
            settings.selectSection("general")
            wait(20)
            const next = findChild(settings, "usage-display")
            next.forceActiveFocus(Qt.TabFocusReason)
            tryVerify(() => next.activeFocus)
            verifyControlInViewport(next, scroller)
            keyClick(Qt.Key_Space)
            tryVerify(() => next.popupItem.activeFocus)
            verify(next.popupOpen)
            keyClick(Qt.Key_Tab)
            tryCompare(next, "popupOpen", false)
            const checkbox = findChild(settings, "show-total")
            tryVerify(() => checkbox.activeFocus)
            verifyControlInViewport(checkbox, scroller)
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
        function prepareResetAction() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[1].resetAction = {fingerprint: "panel-action-token"}
            snapshot.providers[1].resetCredits.rows[0].actionId = "panel-credit-handle"
            Plugin.Model.snapshot = snapshot
            panel.showResetCredits("codex", 0)
            wait(20)
        }
        function test_escape_cancels_reset_confirmation_before_leaving_page() {
            prepareResetAction()
            const apply = findChild(panel, "reset-apply")
            mouseClick(apply)
            const confirmation = findChild(panel, "reset-confirmation")
            verify(confirmation.visible)
            compare(Plugin.Model.resetRequests.length, 0)
            tryVerify(() => findChild(panel, "reset-cancel").activeFocus)
            keyClick(Qt.Key_Escape)
            verify(!confirmation.visible)
            compare(panel.resetProvider.id, "codex")
            compare(Plugin.Model.resetRequests.length, 0)
            tryVerify(() => apply.activeFocus)
            keyClick(Qt.Key_Escape)
            compare(panel.resetProvider, null)
            verify(panel.opened)
            compare(Plugin.Model.resetRequests.length, 0)
        }
        function test_closing_panel_discards_confirmation_and_keeps_confirmed_action_running() {
            prepareResetAction()
            mouseClick(findChild(panel, "reset-apply"))
            verify(findChild(panel, "reset-confirmation").visible)
            const firstHold = findChild(panel, "reset-confirm")
            tryVerify(() => findChild(panel, "reset-cancel").activeFocus)
            firstHold.forceActiveFocus(Qt.TabFocusReason)
            keyPress(Qt.Key_Space)
            wait(100)
            verify(firstHold.holding)
            panel.close()
            compare(findChild(panel, "reset-confirmation"), null)
            verify(!firstHold.holding)
            compare(firstHold.progress, 0)
            keyRelease(Qt.Key_Space)
            compare(Plugin.Model.resetRequests.length, 0)
            panel.open()
            panel.showResetCredits("codex", 0)
            wait(20)
            compare(findChild(panel, "reset-confirmation"), null)
            mouseClick(findChild(panel, "reset-apply"))
            const secondHold = findChild(panel, "reset-confirm")
            tryVerify(() => findChild(panel, "reset-cancel").activeFocus)
            secondHold.forceActiveFocus(Qt.TabFocusReason)
            keyPress(Qt.Key_Space)
            tryVerify(() => Plugin.Model.resetRequests.length === 1, 3500)
            keyRelease(Qt.Key_Space)
            compare(Plugin.Model.resetRequests.length, 1)
            verify(Plugin.Model.resetApplying)
            panel.close()
            verify(Plugin.Model.resetApplying)
            compare(Plugin.Model.resetRequests.length, 1)
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
        function test_settings_footer_aligns_status_actions_and_separator() {
            panel.configure()
            wait(20)
            const footer = findChild(panel, "settings-footer")
            const separator = findChild(panel, "settings-footer-divider")
            const headerSeparator = findChild(panel, "panel-divider")
            const surface = findChild(panel, "panel-surface")
            const status = findChild(panel, "settings-status")
            const cancel = findChild(panel, "settings-cancel")
            const save = findChild(panel, "settings-save")
            const scroller = findChild(panel, "panel-scroller")
            verify(footer.visible)
            compare(separator.width, headerSeparator.width)
            compare(separator.height, headerSeparator.height)
            compare(separator.color, headerSeparator.color)
            compare(separator.mapToItem(surface, 0, 0).x, headerSeparator.mapToItem(surface, 0, 0).x)
            compare(separator.width, surface.width)
            compare(scroller.mapToItem(surface, 0, scroller.height).y, separator.mapToItem(surface, 0, 0).y)
            verify(separator.mapToItem(footer, 0, separator.height).y < cancel.mapToItem(footer, 0, 0).y)
            compare(cancel.mapToItem(footer, 0, 0).y - separator.height, 16)
            compare(surface.height - cancel.mapToItem(surface, 0, cancel.height).y, 16)
            compare(cancel.outlined, true)
            compare(save.primary, true)
            compare(save.text, "Save")
            Plugin.Model.settingsSaved()
            wait(20)
            compare(status.x, 0)
            verify(status.mapToItem(footer, status.width, 0).x < cancel.mapToItem(footer, 0, 0).x)
            compare(save.mapToItem(footer, save.width, 0).x, footer.width)
            const cancelPosition = cancel.mapToItem(footer, 0, 0).x
            Plugin.Model.settingsSaving = true
            compare(cancel.mapToItem(footer, 0, 0).x, cancelPosition)
            compare(save.mapToItem(footer, save.width, 0).x, footer.width)
        }
        function test_settings_footer_tracks_saving_error_retry_and_edits() {
            panel.configure()
            wait(20)
            const settings = findChild(panel, "panel-settings-page")
            const label = findChild(panel, "settings-status-label")
            const icon = findChild(panel, "settings-status-icon")
            const cancel = findChild(panel, "settings-cancel")
            const save = findChild(panel, "settings-save")
            compare(label.text, "")
            compare(Plugin.Model.snapshot.loading, false)
            mouseClick(save)
            verify(Plugin.Model.saved !== null)
            // Simulate the asynchronous writer while provider refresh is idle.
            Plugin.Model.settingsSaving = true
            Plugin.Model.settingsError = "A previous write failed."
            compare(label.text, "Saving…")
            compare(save.text, "Save")
            verify(!cancel.enabled)
            verify(!save.enabled)
            verify(!settings.enabled)
            compare(icon.name, "loader-circle")
            tryVerify(() => icon.rotation > 0)
            const rotation = icon.rotation
            tryVerify(() => icon.rotation !== rotation)
            panel.configurationPage = false
            tryCompare(icon, "rotation", 0)
            panel.configurationPage = true
            tryVerify(() => icon.rotation > 0)
            Plugin.Model.settingsSaving = false
            compare(label.text, "Error")
            tryCompare(icon, "rotation", 0)
            verify(cancel.enabled)
            verify(save.enabled)
            verify(settings.enabled)
            Plugin.Model.saved = null
            mouseClick(save)
            verify(Plugin.Model.saved !== null)
            // The fake Model records payloads; model the retry's writer states.
            Plugin.Model.settingsError = ""
            Plugin.Model.settingsSaving = true
            compare(label.text, "Saving…")
            Plugin.Model.settingsSaving = false
            Plugin.Model.settingsSaved()
            compare(label.text, "Saved")
            compare(icon.name, "check")
            tryCompare(icon, "rotation", 0)
            verify(panel.configurationPage)
            verify(panel.opened)
            settings.toggleProvider("kiro")
            compare(label.text, "")
        }
        function test_about_is_last_settings_tab_and_preserves_shared_draft_and_save() {
            panel.configure()
            wait(20)
            const settings = findChild(panel, "panel-settings-page")
            settings.toggleProvider("kiro")
            settings.moveProvider(1, -1)
            const order = JSON.stringify(settings.order)
            settings.usageDisplay = "remaining"
            compare(settings.sections[settings.sections.length - 1].key, "about")
            verify(findChild(settings, "settings-about") === null)
            panel.showAbout()
            wait(20)
            compare(settings.section, "about")
            verify(findChild(settings, "settings-section-about").visible)
            compare(findChild(panel, "panel-title").text, "Settings")
            verify(findChild(panel, "settings-save").visible)
            verify(findChild(panel, "settings-navigation").visible)
            const metadata = findChild(panel, "about-metadata")
            verify(metadata.text.indexOf("12345678") !== -1)
            verify(metadata.text.indexOf("gelzin.com") !== -1)
            const projectLink = findChild(settings, "about-link-guide")
            compare(projectLink.trailingIconName, "arrow-right")
            findChild(panel, "settings-nav-about").forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Tab)
            tryVerify(() => projectLink.activeFocus)
            settings.selectSection("general")
            wait(20)
            verify(panel.configurationPage)
            compare(JSON.stringify(settings.order), order)
            verify(settings.enabledProviders.indexOf("kiro") !== -1)
            compare(settings.usageDisplay, "remaining")
            settings.selectSection("about")
            wait(20)
            mouseClick(findChild(panel, "settings-save"))
            compare(Plugin.Model.saved.enabled[0], "codex")
            compare(Plugin.Model.saved.usageDisplay, "remaining")
            Plugin.Model.settingsSaved()
            compare(settings.section, "about")
            verify(settings.saved)
            keyClick(Qt.Key_Escape)
            wait(20)
            verify(!panel.configurationPage)
            verify(panel.opened)
            panel.showAbout()
            wait(20)
            verify(panel.configurationPage)
            compare(settings.section, "about")
            compare(settings.usageDisplay, "used")
        }
        function test_guide_link_order_keycaps_and_tab_icons() {
            panel.configure()
            const settings = findChild(panel, "panel-settings-page")
            compare(settings.sections.map(item => item.key).join(","), "general,alerts,providers,guide,about")
            settings.selectSection("about")
            wait(20)
            const links = ["guide", "issues", "documentation", "github"].map(key => findChild(settings, "about-link-" + key))
            for (let index = 1; index < links.length; index++) verify(links[index].y > links[index - 1].y)
            mouseClick(links[0])
            compare(settings.section, "guide")
            wait(20)
            verify(findChild(settings, "guide-table").visible)
            for (const key of ["R", "C", "Tab", "Shift+Tab", "Space", "Enter", "Left", "Right", "Esc"]) {
                const cap = findChild(settings, "guide-keycap-" + key)
                verify(cap !== null, key)
                compare(cap.border.width, 1)
                verify(cap.width > 0)
            }
            for (const section of settings.sections) {
                const tab = findChild(panel, "settings-nav-" + section.key)
                compare(tab.leadingIconName, section.icon)
                const icon = findChild(tab, "leading-icon")
                verify(icon.visible)
                compare(icon.width, 16)
            }
            findChild(panel, "settings-nav-about").forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Tab)
            verify(findChild(panel, "settings-cancel").activeFocus)
        }
        function test_review_invalid_rule_reveals_field_below_fixed_tabs_and_preserves_bar_selection() {
            panel.configure()
            const settings = findChild(panel, "panel-settings-page")
            settings.selected = {provider: "codex", idx: 0, metric: "weekly"}
            settings.setRule("thresholds", [90,100])
            settings.setRuleText("bad")
            settings.selected = {provider: "claude", idx: 0, metric: "rolling"}
            settings.selectSection("about")
            wait(20)
            mouseClick(findChild(panel, "settings-review-section"))
            compare(settings.section, "alerts")
            const field = findChild(settings, "alert-rule-thresholds")
            tryVerify(() => field.inputItem.activeFocus)
            verifyControlInViewport(field, findChild(panel, "panel-scroller"))
            compare(settings.selected.provider, "claude")
            settings.alertsAdvanced = false
            wait(20)
            verify(findChild(panel, "settings-review-section").visible)
            mouseClick(findChild(panel, "settings-review-section"))
            tryVerify(() => field.inputItem.activeFocus)
            verifyControlInViewport(field, findChild(panel, "panel-scroller"))
        }
        function test_tab_faces_stay_above_content_without_changing_colors_during_scroll() {
            panel.configure()
            const settings = findChild(panel, "panel-settings-page")
            settings.selectSection("guide")
            wait(20)
            const surface = findChild(panel, "panel-surface")
            const tab = findChild(panel, "settings-nav-guide")
            const scroller = findChild(panel, "panel-scroller")
            compare(tab.color.a, 1)
            waitForRendering(surface)
            const before = grabImage(surface)
            const position = tab.mapToItem(surface, 0, 0)
            scroller.contentY = scroller.contentHeight - scroller.height
            waitForRendering(surface)
            const after = grabImage(surface)
            for (let y = 2; y < tab.height - 2; y++) {
                for (let x = 2; x < tab.width - 2; x++)
                    compare(after.pixel(Math.round(position.x + x), Math.round(position.y + y)), before.pixel(Math.round(position.x + x), Math.round(position.y + y)))
            }
        }
        function test_unified_settings_keep_provider_bar_and_general_controls_reachable() {
            panel.configure()
            wait(20)
            const settings = findChild(panel, "panel-settings-page")
            const scroller = findChild(panel, "panel-scroller")
            const before = JSON.stringify(settings.selectedItems)
            for (const name of ["refresh-interval-slider", "usage-display", "icon-mode"]) {
                const control = findChild(settings, name)
                control.forceActiveFocus(Qt.TabFocusReason)
                verifyControlInViewport(control, scroller)
            }
            settings.selectSection("providers")
            settings.toggleProvider("kiro")
            wait(20)
            for (const name of ["provider-claude", "provider-limits-claude", "provider-bar-claude", "provider-codex", "provider-bar-codex", "provider-kiro", "provider-bar-kiro"]) {
                const control = findChild(settings, name)
                control.forceActiveFocus(Qt.TabFocusReason)
                verifyControlInViewport(control, scroller)
            }
            compare(findChild(settings, "bar-order-claude-0-rolling"), null)
            compare(JSON.stringify(settings.selectedItems), before)
        }
        function test_separator_reaches_sides_and_only_refresh_icon_spins() {
            const surface = findChild(panel, "panel-surface")
            const divider = findChild(panel, "panel-divider")
            compare(divider.color, surface.border.color)
            compare(findChild(panel, "settings-footer-divider").color, surface.border.color)
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
