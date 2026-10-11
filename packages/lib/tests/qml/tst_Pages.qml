import QtQuick
import QtTest
import "plugin" as Plugin

Item {
    width: 380
    height: 800
    property var openedReset: null
    Connections {
        target: usage
        function onResetRequested(provider, idx) { openedReset = {provider: provider, idx: idx} }
    }
    Plugin.ResetCreditsPage {
        id: credits
        width: 344
        visible: false
        provider: Plugin.Model.snapshot.providers ? Plugin.Model.snapshot.providers[1] || null : null
    }
    Plugin.UsageBar { id: initialBar; width: 200; visible: false; percentage: 80 }
    Plugin.UsageBar { id: staggeredBar; width: 200; visible: false; percentage: 80; groupIndex: 1 }
    Plugin.SettingsPage {
        id: settings
        width: 344
        x: 18
        y: 60
        foreground: "#eeeeee"
    }
    Plugin.UsagePage {
        id: usage
        width: 344
        visible: false
        foreground: "#eeeeee"
    }
    TestCase {
        name: "NativePages"
        when: windowShown
        function init() {
            Plugin.Model.reset()
            settings.begin()
            usage.visible = false
            settings.visible = true
            credits.visible = false
            openedReset = null
            initialBar.visible = false
            staggeredBar.visible = false
        }
        function verifyMetricAlignment(provider) {
            const name = findChild(usage, "usage-provider-name-" + provider.id + "-" + provider.idx)
            verify(name !== null)
            const nameX = name.mapToItem(usage, 0, 0).x
            for (const metric of provider.metrics) {
                const suffix = provider.id + "-" + provider.idx + "-" + metric.key
                const title = findChild(usage, "usage-title-" + suffix)
                const bracket = findChild(usage, "usage-bracket-" + suffix)
                const detail = findChild(usage, "usage-detail-" + suffix)
                compare(title.mapToItem(usage, 0, 0).x, nameX)
                compare(bracket.mapToItem(usage, 0, 0).x, nameX)
                compare(detail.mapToItem(usage, 0, 0).x, nameX)
            }
        }
        function test_draft_is_isolated_and_cancel_reloads_saved_settings() {
            settings.toggleProvider("kiro")
            settings.moveProvider(0, 1)
            compare(Plugin.Model.snapshot.settings.enabled.length, 2)
            compare(Plugin.Model.snapshot.settings.order[0], "claude")
            compare(Plugin.Model.saved, null)
            settings.begin()
            compare(settings.enabledProviders.length, 2)
            compare(settings.order[0], "claude")
        }
        function test_amount_only_account_keeps_identity_and_hides_progress() {
            settings.visible = false
            const snapshot = Plugin.Model.snapshot
            snapshot.selected = {provider: "account:work", idx: 0, metric: "balance:credits"}
            snapshot.providers = [{id: "account:work", providerId: "openrouter", idx: 0, name: "OpenRouter · Work", logoPath: "", loading: false, cached: false, error: "", metrics: [
                {key: "balance:credits", name: "Available credits", percentage: null, hasPercentage: false, isAmount: true, value: "$42.50", detail: ""}
            ]}]
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            usage.visible = true
            wait(20)
            const bar = findChild(usage, "usage-bar-account:work-0-balance:credits")
            verify(bar !== null)
            verify(!bar.visible)
            const value = findChild(usage, "usage-value-account:work-0-balance:credits")
            compare(value.text, "$42.50")
            verify(value.visible)
            const title = findChild(usage, "usage-title-account:work-0-balance:credits")
            compare(title.mapToItem(usage, 0, 0).y, value.mapToItem(usage, 0, 0).y)
            verify(title.mapToItem(usage, title.width, 0).x < value.mapToItem(usage, 0, 0).x)
            compare(value.mapToItem(usage, 0, 0).x - title.mapToItem(usage, title.width, 0).x, 6)
            compare(value.font.pixelSize, title.font.pixelSize)
            verify(value.font.pixelSize < 20)
            compare(bar.parent.visible, false)
            verifyMetricAlignment(snapshot.providers[0])
            mouseClick(value)
            compare(Plugin.Model.chosen.provider, "account:work")
            compare(Plugin.Model.chosen.metric, "balance:credits")
            keyClick(Qt.Key_Return)
            compare(Plugin.Model.chosen.metric, "balance:credits")
            const valueX = value.x
            const valueWidth = value.width
            const titleWidth = title.width
            snapshot.providers[0].loading = true
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            wait(20)
            compare(value.x, valueX)
            compare(value.width, valueWidth)
            compare(title.width, titleWidth)
            compare(value.text, Plugin.Model.spinner)
            compare(title.parent.parent.implicitHeight, title.parent.height)
        }
        function test_reorder_and_save() {
            settings.moveProvider(1, -1)
            settings.selected = {provider: "claude", idx: 0, metric: "weekly:Fable"}
            settings.save()
            compare(Plugin.Model.saved.enabled[0], "codex")
            compare(Plugin.Model.saved.selected.metric, "weekly:Fable")
            compare(Plugin.Model.saved.iconMode, "logo")
        }
        function test_account_credit_ratio_aligns_with_title_above_full_width_progress() {
            settings.visible = false
            const snapshot = Plugin.Model.snapshot
            snapshot.selected = {provider: "account:work", idx: 0, metric: "credits:account"}
            snapshot.providers = [{id: "account:work", providerId: "openrouter", idx: 0, name: "OpenRouter · Work", logoPath: "", loading: false, cached: false, error: "", metrics: [
                {key: "credits:account", name: "Account spend / total credits", percentage: 25, hasPercentage: true, value: "$25.00 / $100.00", detail: "Account totals"}
            ]}]
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            usage.visible = true
            wait(20)
            const value = findChild(usage, "usage-value-account:work-0-credits:account")
            const bar = findChild(usage, "usage-bar-account:work-0-credits:account")
            compare(value.text, "$25.00 / $100.00")
            verify(value.width >= value.implicitWidth)
            verify(bar.visible && bar.width > 0)
            verify(Math.abs(value.mapToItem(usage, value.width, 0).x - usage.width) < 0.1)
            const title = findChild(usage, "usage-title-account:work-0-credits:account")
            verify(title.mapToItem(usage, title.width, 0).x < value.mapToItem(usage, 0, 0).x)
            compare(title.mapToItem(usage, 0, 0).y, value.mapToItem(usage, 0, 0).y)
            verify(bar.mapToItem(usage, 0, 0).y >= value.mapToItem(usage, 0, value.height).y)
            verify(bar.width > bar.parent.width * 0.9)
            verifyMetricAlignment(snapshot.providers[0])
            verify(title.implicitHeight > value.implicitHeight)
            verify(bar.mapToItem(usage, 0, 0).y >= title.mapToItem(usage, 0, title.height).y)
            const valueWidth = value.width
            const titleWidth = title.width
            snapshot.providers[0].loading = true
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            wait(20)
            compare(value.width, valueWidth)
            compare(title.width, titleWidth)
            compare(value.text, Plugin.Model.spinner)
        }
        function test_disabling_active_provider_selects_an_enabled_one() {
            settings.toggleProvider("claude")
            compare(settings.selected.provider, "codex")
            verify(settings.valid)
            settings.save()
            compare(Plugin.Model.saved.enabled.length, 1)
            compare(Plugin.Model.saved.selected.provider, "codex")
        }
        function test_all_disabled_or_hidden_cannot_save() {
            settings.toggleProvider("claude")
            settings.toggleProvider("codex")
            verify(!settings.valid)
            settings.save()
            compare(Plugin.Model.saved, null)
            settings.begin()
            settings.display = {show_provider: false, show_model: false, show_metric: false, show_pct: false}
            verify(!settings.valid)
            settings.save()
            compare(Plugin.Model.saved, null)
        }
        function test_enable_provider_before_first_fetch() {
            settings.toggleProvider("kiro")
            settings.selected = {provider: "kiro", idx: 0, metric: "rolling"}
            verify(settings.valid)
            settings.save()
            compare(Plugin.Model.saved.selected.provider, "kiro")
        }
        function test_weekly_limits_are_individually_selectable() {
            verify(settings.choices.some(item => item.metric === "weekly"))
            verify(settings.choices.some(item => item.metric === "weekly:Fable"))
            settings.selected = {provider: "claude", idx: 0, metric: "weekly:Fable"}
            verify(settings.selectedLabel.indexOf("Fable") !== -1)
        }
        function test_controls_respond_to_click_and_keyboard() {
            const checkbox = findChild(settings, "display-show_pct")
            verify(checkbox !== null)
            mouseClick(checkbox)
            verify(!settings.display.show_pct)
            keyClick(Qt.Key_Space)
            verify(settings.display.show_pct)
            mouseClick(findChild(settings, "provider-claude"))
            compare(settings.selected.provider, "codex")
            mouseClick(findChild(settings, "active-provider"))
            verify(settings.selectionOpen)
        }
        function test_provider_selector_logos_render_in_trigger_and_every_option() {
            settings.iconMode = "off"
            const trigger = findChild(settings, "active-provider")
            const triggerLogo = findChild(trigger, "provider-logo")
            tryCompare(triggerLogo, "status", Image.Ready)
            verify(trigger.logoSource.toString().endsWith("/claude.png"))
            mouseClick(trigger)
            verify(settings.selectionOpen)
            wait(20)
            for (const choice of settings.choices) {
                const option = findChild(trigger.popupItem, "active-provider-option-" + choice.provider + "-" + choice.idx + "-" + choice.metric)
                verify(option.visible)
                tryCompare(findChild(option, "provider-logo"), "status", Image.Ready)
                verify(option.logoSource.toString().endsWith("/" + choice.provider + ".png"))
            }
            mouseClick(findChild(trigger.popupItem, "active-provider-option-codex-0-weekly"))
            compare(settings.selected.provider, "codex")
            compare(settings.selected.metric, "weekly")
            verify(trigger.logoSource.toString().endsWith("/codex.png"))
            tryCompare(triggerLogo, "status", Image.Ready)
            // Enabling a provider before its first query still uses its bundled logo.
            settings.toggleProvider("kiro")
            settings.selected = {provider: "kiro", idx: 0, metric: "rolling"}
            verify(trigger.logoSource.toString().endsWith("/kiro.png"))
            tryCompare(triggerLogo, "status", Image.Ready)
        }
        function test_both_selectors_overlay_without_resizing_and_support_keyboard() {
            const provider = findChild(settings, "active-provider")
            const icon = findChild(settings, "icon-mode")
            wait(20)
            const height = settings.implicitHeight
            for (const trigger of [provider, icon]) {
                compare(trigger.trailingIconName, "chevron-down")
                const chevron = findChild(trigger, "trailing-icon")
                compare(chevron.x + chevron.width, trigger.width - 8)
                mouseClick(trigger)
                wait(20)
                verify(trigger.popupOpen)
                compare(settings.implicitHeight, height)
                const menu = findChild(trigger.popupItem, trigger.objectName + "-menu")
                const triggerBottom = trigger.mapToItem(trigger.popupItem, 0, trigger.height).y
                verify(Math.abs(menu.y - triggerBottom - 4) < 1 || Math.abs(menu.y + menu.height + 4 - triggerBottom + trigger.height) < 1)
                keyClick(Qt.Key_End)
                keyClick(Qt.Key_Return)
                verify(!trigger.popupOpen)
                verify(trigger.activeFocus)
            }
            compare(settings.selected.provider, "codex")
            compare(settings.selected.metric, "weekly")
            compare(settings.iconMode, "logo")
            mouseClick(icon)
            wait(20)
            keyClick(Qt.Key_Home)
            keyClick(Qt.Key_Return)
            compare(settings.iconMode, "off")
            mouseClick(provider)
            wait(20)
            keyClick(Qt.Key_Escape)
            verify(!provider.popupOpen)
            verify(settings.visible)
            mouseClick(icon)
            wait(20)
            mouseClick(icon.popupItem, 370, 780)
            verify(!icon.popupOpen)
            compare(settings.implicitHeight, height)
        }
        function test_provider_rows_show_official_names_and_logos_independent_of_bar_icon() {
            settings.iconMode = "off"
            for (const name of settings.order) {
                const row = findChild(settings, "provider-" + name)
                compare(row.text, Plugin.Model.snapshot.settings.names[name])
                verify(row.logoSource.toString().endsWith("/" + name + ".png"))
                tryCompare(findChild(row, "provider-logo"), "status", Image.Ready)
            }
        }
        function test_usage_layout_has_content_and_stable_metric_alignment() {
            verify(usage.implicitHeight > 200)
            for (const provider of Plugin.Model.snapshot.providers) verifyMetricAlignment(provider)
            const rightEdges = []
            function walk(item) {
                // QQmlListProperty gained JS iteration in later Qt versions.
                for (let index = 0; index < item.children.length; index++) {
                    const child = item.children[index]
                    verify(child.width >= 0)
                    verify(isFinite(child.x) && isFinite(child.y))
                    if (typeof child.text === "string" && /^\d+%$/.test(child.text))
                        rightEdges.push(child.mapToItem(usage, child.width, 0).x)
                    walk(child)
                }
            }
            walk(usage)
            compare(rightEdges.length, 5)
            for (const edge of rightEdges)
                verify(Math.abs(edge - usage.width) < 0.1)
        }
        function test_reset_credits_show_only_with_available_inventory() {
            settings.visible = false
            usage.visible = true
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[0].resetCredits = {
                available: 1,
                summary: "1 reset available",
                details: ["Launch reset · Expires Oct 22 13:00 UTC"]
            }
            Plugin.Model.snapshot = snapshot
            const block = findChild(usage, "reset-credits-claude-0")
            verify(block !== null)
            verify(block.visible)
            verify(block.implicitHeight > 0)
            compare(block.text, "Reset credits: 1 available")
            wait(20)
            let resetText = null
            for (let index = 0; index < block.children.length; index++) {
                const child = block.children[index]
                if (child.text === block.text) resetText = child
            }
            verify(resetText !== null)
            const providerName = findChild(usage, "usage-provider-name-claude-0")
            compare(resetText.mapToItem(usage, 0, 0).x, providerName.mapToItem(usage, 0, 0).x)
            mouseClick(block)
            compare(openedReset.provider, "claude")
            compare(openedReset.idx, 0)
            compare(Plugin.Model.chosen, null)
            compare(Plugin.Model.snapshot.providers[0].metrics.length, 3)
            const cleared = JSON.parse(JSON.stringify(snapshot))
            cleared.providers[0].resetCredits = null
            Plugin.Model.snapshot = cleared
            verify(!findChild(usage, "reset-credits-claude-0").visible)
        }
        function test_empty_usage_shows_windows_loading_and_no_data_messages() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers = []
            snapshot.loading = true
            Plugin.Model.snapshot = snapshot
            compare(findChild(usage, "empty-usage").text, "Checking your connected providers…")
            snapshot.loading = false
            Plugin.Model.snapshot = JSON.parse(JSON.stringify(snapshot))
            compare(findChild(usage, "empty-usage").text, "No usage available. Connect a provider and refresh.")
        }
        function test_streaming_refresh_preserves_rows_and_finishes_each_provider() {
            settings.visible = false
            usage.visible = true
            const claude = findChild(usage, "usage-bar-claude-0-rolling")
            const codex = findChild(usage, "usage-bar-codex-0-weekly")
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.loading = true
            snapshot.providers.forEach(provider => provider.loading = true)
            Plugin.Model.snapshot = snapshot
            compare(findChild(usage, "usage-bar-claude-0-rolling"), claude)
            verify(claude.shimmering)
            verify(codex.shimmering)
            compare(claude.fillOpacity, 0)
            const phase = claude.phase
            wait(200)
            verify(claude.phase !== phase)
            snapshot.providers[0].loading = false
            snapshot.providers[0].metrics[0].percentage = 40
            Plugin.Model.snapshot = JSON.parse(JSON.stringify(snapshot))
            compare(findChild(usage, "usage-bar-claude-0-rolling"), claude)
            verify(!claude.shimmering)
            verify(codex.shimmering)
            tryCompare(claude, "mounted", true)
            wait(1600)
            compare(claude.displayed, 40)
            // A reset-countdown update must not recreate or refill the usage row.
            snapshot.providers[0].resetCredits = {available: 1, rows: [], undetailed: 1}
            Plugin.Model.snapshot = JSON.parse(JSON.stringify(snapshot))
            compare(findChild(usage, "usage-bar-claude-0-rolling"), claude)
            verify(!claude.filling)
            usage.visible = false
            verify(!codex.shimmering)
        }
        function test_initial_fill_uses_windows_stagger_and_refresh_shimmer() {
            initialBar.mounted = false
            initialBar.displayed = 0
            staggeredBar.mounted = false
            staggeredBar.displayed = 0
            initialBar.visible = true
            staggeredBar.visible = true
            wait(150)
            verify(initialBar.mounted)
            verify(!staggeredBar.mounted)
            wait(1700)
            compare(initialBar.displayed, 80)
            compare(staggeredBar.displayed, 80)
            initialBar.loading = true
            compare(initialBar.fillOpacity, 0)
            verify(initialBar.shimmering)
            initialBar.visible = false
            verify(!initialBar.shimmering)
            initialBar.loading = false
        }
        function test_reset_page_matches_windows_and_updates_without_selection_changes() {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[1].resetCredits = {available: 5, undetailed: 3, rows: [
                {title: "Full reset", count: 1, expires: "Oct 22, 18:05", remaining: "12d 2h left", timezone: "UTC-03:00"},
                {title: "Reset credit", count: 1, expires: "Not provided", remaining: "", timezone: ""}
            ]}
            Plugin.Model.snapshot = snapshot
            settings.visible = false
            credits.visible = true
            wait(20)
            const available = findChild(credits, "reset-available")
            const table = findChild(credits, "reset-table")
            const header = findChild(credits, "reset-column-header")
            const footer = findChild(table, "reset-table-footer")
            compare(available.text, "5")
            verify(table.visible)
            compare(table.radius, 8)
            compare(findChild(footer, "reset-available"), available)
            compare(findChild(footer, "reset-available-label").text, "Available resets")
            compare(available.font.weight, Font.Medium)
            verify(footer.y > header.y + header.height)
            verify(findChild(header, "reset-available") === null)
            compare(findChild(header, "reset-type-header").text, "Reset type")
            compare(findChild(header, "reset-expires-header").text, "Expires")
            compare(header.color, Qt.rgba(credits.foreground.r, credits.foreground.g, credits.foreground.b, 0.04))
            compare(header.radius, 7)
            const explanation = findChild(credits, "reset-explanation")
            compare(explanation.color, findChild(credits, "reset-section-title").color)
            compare(explanation.opacity, 0.55)
            compare(explanation.font.pixelSize, 13)
            compare(Plugin.Model.chosen, null)
            const undetailed = JSON.parse(JSON.stringify(snapshot))
            undetailed.providers[1].resetCredits = {available: 3, undetailed: 3, rows: []}
            Plugin.Model.snapshot = undetailed
            verify(table.visible)
            verify(footer.visible)
            compare(available.text, "3")
            const empty = JSON.parse(JSON.stringify(snapshot))
            empty.providers[1].resetCredits = null
            Plugin.Model.snapshot = empty
            verify(!findChild(credits, "reset-table").visible)
            verify(!available.visible)
            compare(Plugin.Model.snapshot.selected.provider, "claude")
        }
    }
}
