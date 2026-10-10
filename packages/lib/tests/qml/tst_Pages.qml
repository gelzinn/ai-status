import QtQuick
import QtTest
import "plugin" as Plugin

Item {
    width: 380
    height: 800
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
            compare(Plugin.Model.snapshot.providers[0].metrics.length, 3)
            const cleared = JSON.parse(JSON.stringify(snapshot))
            cleared.providers[0].resetCredits = null
            Plugin.Model.snapshot = cleared
            verify(!findChild(usage, "reset-credits-claude-0").visible)
        }
    }
}
