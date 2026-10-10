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
        function test_reorder_and_save() {
            settings.moveProvider(1, -1)
            settings.selected = {provider: "claude", idx: 0, metric: "weekly:Fable"}
            settings.save()
            compare(Plugin.Model.saved.enabled[0], "codex")
            compare(Plugin.Model.saved.selected.metric, "weekly:Fable")
            compare(Plugin.Model.saved.iconMode, "logo")
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
        function test_usage_layout_has_content_and_stable_metric_alignment() {
            verify(usage.implicitHeight > 300)
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
            snapshot.providers[1].resetCredits = {available: 2, undetailed: 1, rows: [
                {title: "Full reset", count: 1, expires: "Oct 22, 18:05", remaining: "12d 2h left", timezone: "UTC-03:00"},
                {title: "Reset credit", count: 1, expires: "Not provided", remaining: "", timezone: ""}
            ]}
            Plugin.Model.snapshot = snapshot
            settings.visible = false
            credits.visible = true
            compare(findChild(credits, "reset-available").text, "Available 2")
            verify(findChild(credits, "reset-table").visible)
            compare(Plugin.Model.chosen, null)
            const empty = JSON.parse(JSON.stringify(snapshot))
            empty.providers[1].resetCredits = null
            Plugin.Model.snapshot = empty
            verify(!findChild(credits, "reset-table").visible)
            compare(Plugin.Model.snapshot.selected.provider, "claude")
        }
    }
}
