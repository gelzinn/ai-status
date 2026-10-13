import QtQuick
import QtTest
import qs.Commons
import "plugin" as Plugin

Item {
    width: 380
    height: 800
    property var openedReset: null
    property var openedCredit: null
    Connections {
        target: usage
        function onResetRequested(provider, idx) { openedReset = {provider: provider, idx: idx} }
        function onCreditRequested(provider, idx, creditId) { openedCredit = {provider: provider, idx: idx, creditId: creditId} }
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
            openedCredit = null
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
        function test_refresh_interval_draft_save_cancel_and_legacy_default() {
            compare(settings.refreshIntervalMinutes, 5)
            settings.refreshIntervalMinutes = 25
            compare(Plugin.Model.snapshot.settings.refreshIntervalMinutes, 5)
            compare(Plugin.Model.saved, null)
            compare(Plugin.Model.actions.length, 0)
            settings.save()
            compare(Plugin.Model.saved.refreshIntervalMinutes, 25)
            settings.begin()
            compare(settings.refreshIntervalMinutes, 5)
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.settings.refreshIntervalMinutes = 40
            Plugin.Model.snapshot = snapshot
            settings.begin()
            compare(settings.refreshIntervalMinutes, 40)
            settings.saved = true
            settings.refreshIntervalMinutes = 45
            verify(!settings.saved)
            delete snapshot.settings.refreshIntervalMinutes
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            settings.begin()
            compare(settings.refreshIntervalMinutes, 5)
        }
        function test_refresh_interval_rejects_unsafe_or_off_step_drafts_data() {
            return [0, 1, 4, 6, 12, 61, 65].map(value => ({tag: String(value), value: value}))
        }
        function test_refresh_interval_rejects_unsafe_or_off_step_drafts(data) {
            settings.refreshIntervalMinutes = data.value
            verify(!settings.valid)
            compare(settings.validationSection, "general")
            settings.save()
            compare(Plugin.Model.saved, null)
            settings.selectSection("providers")
            mouseClick(findChild(settings, "settings-review-validation"))
            compare(settings.section, "general")
            settings.focusFirstControl()
            verify(findChild(settings, "refresh-interval-slider").activeFocus)
        }
        function test_refresh_interval_slider_keyboard_steps_and_bounds_do_not_refresh() {
            const slider = findChild(settings, "refresh-interval-slider")
            compare(slider.from, 5)
            compare(slider.to, 60)
            compare(slider.stepSize, 5)
            slider.forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Right)
            compare(settings.refreshIntervalMinutes, 10)
            verify(slider.activeFocus)
            keyClick(Qt.Key_Left)
            keyClick(Qt.Key_Left)
            compare(settings.refreshIntervalMinutes, 5)
            for (let index = 0; index < 13; index++) keyClick(Qt.Key_Right)
            compare(settings.refreshIntervalMinutes, 60)
            compare(slider.value, 60)
            keyClick(Qt.Key_Left)
            compare(settings.refreshIntervalMinutes, 55)
            verify(settings.valid)
            compare(Plugin.Model.saved, null)
            compare(Plugin.Model.actions.length, 0)
            compare(Plugin.Model.snapshot.settings.refreshIntervalMinutes, 5)
            settings.save()
            compare(Plugin.Model.saved.refreshIntervalMinutes, 55)
            Plugin.Model.settingsSaving = true
            verify(!slider.enabled)
            Plugin.Model.settingsSaving = false
        }
        function test_refresh_interval_slider_drag_snaps_without_saving_or_refreshing() {
            const slider = findChild(settings, "refresh-interval-slider")
            mousePress(slider, 1, slider.height / 2)
            mouseMove(slider, slider.width / 2, slider.height / 2)
            mouseRelease(slider, slider.width / 2, slider.height / 2)
            verify(settings.refreshIntervalMinutes >= 5 && settings.refreshIntervalMinutes <= 60)
            compare(settings.refreshIntervalMinutes % 5, 0)
            verify(settings.refreshIntervalMinutes > 5)
            compare(Plugin.Model.saved, null)
            compare(Plugin.Model.actions.length, 0)
            mouseClick(slider, slider.width - 1, slider.height / 2)
            compare(settings.refreshIntervalMinutes, 60)
            mouseClick(slider, 1, slider.height / 2)
            compare(settings.refreshIntervalMinutes, 5)
        }
        function test_general_unifies_usage_display_and_refresh_in_one_draft() {
            compare(settings.sections.map(item => item.key).join(","), "general,alerts,providers,guide,about")
            verify(findChild(settings, "settings-section-general").visible)
            verify(findChild(settings, "settings-usage-display").visible)
            verify(findChild(settings, "settings-refresh-interval").visible)
            compare(findChild(settings, "settings-section-appearance"), null)
            settings.usageDisplay = "remaining"
            settings.refreshIntervalMinutes = 20
            settings.selectSection("alerts")
            settings.selectSection("general")
            compare(settings.usageDisplay, "remaining")
            compare(settings.refreshIntervalMinutes, 20)
            settings.save()
            compare(Plugin.Model.saved.usageDisplay, "remaining")
            compare(Plugin.Model.saved.refreshIntervalMinutes, 20)
            settings.begin()
            compare(settings.usageDisplay, "used")
            compare(settings.refreshIntervalMinutes, 5)
        }
        function test_quota_alert_draft_save_and_cancel_preserve_account_rules() {
            settings.alertThresholds = "95,100"
            settings.setAlert("muted_until", 1234567890)
            settings.setAlert("quiet_hours", {start: "22:00", end: "08:00"})
            settings.setRule("thresholds", [80,100])
            settings.setRuleText("90,100")
            settings.selected = {provider: "codex", idx: 0, metric: "weekly"}
            settings.setRule("thresholds", [95,100])
            settings.save()
            compare(Plugin.Model.saved.notifications.thresholds.join(","), "95,100")
            compare(Plugin.Model.saved.notifications.rules.length, 2)
            compare(Plugin.Model.saved.notifications.rules[0].connection_id, "claude")
            compare(Plugin.Model.saved.notifications.rules[0].thresholds.join(","), "90,100")
            compare(Plugin.Model.saved.notifications.rules[1].connection_id, "codex")
            compare(Plugin.Model.saved.notifications.muted_until, 1234567890)
            compare(Plugin.Model.saved.notifications.quiet_hours.start, "22:00")
            verify(Plugin.Model.snapshot.settings.notifications === undefined)
            settings.begin()
            compare(settings.alertThresholds, "80,95,100")
            compare(settings.alertSettings.rules.length, 0)
        }
        function test_invalid_quota_threshold_drafts_block_save() {
            settings.alertThresholds = "101"
            verify(!settings.valid)
            settings.save()
            compare(Plugin.Model.saved, null)
            settings.alertThresholds = "80,95,100"
            settings.setRule("thresholds", [95,100])
            settings.setRuleText("99.6")
            verify(!settings.valid)
            settings.save()
            compare(Plugin.Model.saved, null)
            settings.setRuleText("95,100")
            verify(settings.valid)
            settings.save()
            compare(Plugin.Model.saved.notifications.rules[0].thresholds.join(","), "95,100")
        }
        function test_alert_switches_and_sliders_support_keyboard_without_losing_focus() {
            settings.selectSection("alerts")
            wait(20)
            compare(findChild(settings, "alerts-change-selection"), null)
            const enabled = findChild(settings, "alerts-enabled")
            enabled.forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Space)
            compare(settings.alertSettings.enabled, false)
            keyClick(Qt.Key_Space)
            compare(settings.alertSettings.enabled, true)
            const pause = findChild(settings, "alerts-mute")
            pause.forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Space)
            verify(settings.alertSettings.muted_until > Date.now() / 1000 + 3590)
            keyClick(Qt.Key_Space)
            compare(settings.alertSettings.muted_until, 0)
            const slider = findChild(settings, "alert-threshold-slider-0")
            slider.forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Right)
            compare(settings.alertThresholds, "81,95,100")
            verify(slider.activeFocus)
            keyClick(Qt.Key_Left)
            compare(settings.alertThresholds, "80,95,100")
            settings.updateThreshold(0, 99)
            compare(settings.alertThresholds, "94,95,100")
            verify(slider.activeFocus)
            settings.save()
            compare(Plugin.Model.saved.notifications.thresholds.join(","), "94,95,100")
        }
        function test_alert_levels_add_remove_and_advanced_keep_draft() {
            settings.selectSection("alerts")
            wait(20)
            const advanced = findChild(settings, "alerts-advanced")
            verify(!advanced.visible)
            mouseClick(findChild(settings, "alert-threshold-add"))
            compare(settings.thresholdValues.length, 4)
            verify(settings.valid)
            settings.removeThreshold(1)
            compare(settings.thresholdValues.length, 3)
            wait(20)
            verify(findChild(settings, "alert-threshold-add").activeFocus)
            mouseClick(findChild(settings, "alerts-advanced-toggle"))
            verify(advanced.visible)
            settings.setHours("quiet_hours", "22:00-08:00")
            settings.setRule("thresholds", [75,95])
            settings.setRuleText("80,95")
            settings.selectSection("guide")
            settings.selectSection("alerts")
            verify(advanced.visible)
            compare(settings.alertQuietHours, "22:00-08:00")
            compare(settings.selectedAlertThresholds, "80,95")
            settings.alertsAdvanced = false
            settings.setHours("work_hours", "99:00-18:00")
            verify(!settings.valid)
            settings.selectSection("general")
            settings.selectSection("alerts")
            verify(settings.alertsAdvanced)
            settings.setHours("work_hours", "09:00-18:00")
            settings.alertThresholds = "80,80"
            verify(!settings.valid)
            settings.alertThresholds = "80"
            settings.removeThreshold(0)
            compare(settings.thresholdValues.length, 0)
            verify(settings.valid)
            settings.save()
            compare(Plugin.Model.saved.notifications.thresholds.length, 0)
            settings.addThreshold()
            compare(settings.alertThresholds, "80")
        }
        function test_invalid_rule_for_another_account_is_editable_without_changing_bar_selection() {
            settings.selected = {provider: "codex", idx: 0, metric: "weekly"}
            settings.setRule("thresholds", [90,100])
            settings.setRuleText("bad")
            settings.selected = {provider: "claude", idx: 0, metric: "rolling"}
            const selected = JSON.stringify(settings.selected)
            settings.selectSection("alerts")
            wait(20)
            verify(settings.alertsAdvanced)
            compare(settings.ruleSelection.provider, "codex")
            compare(settings.ruleSelection.metric, "weekly")
            compare(settings.selectedAlertThresholds, "bad")
            verify(settings.ruleSelectionLabel.indexOf("Codex") !== -1)
            settings.setRuleText("90,100")
            verify(settings.valid)
            compare(JSON.stringify(settings.selected), selected)
            settings.save()
            compare(Plugin.Model.saved.selected.provider, "claude")
            compare(Plugin.Model.saved.notifications.rules[0].thresholds.join(","), "90,100")
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
        function test_cloud_credit_states_keep_account_selection_without_quota_progress() {
            settings.visible = false
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            const identity = "account:cloud-work"
            const states = [
                {status: "available", value: "$75.25", detail: "Available · Expires Nov 5, 2099", isAmount: true},
                {status: "exhausted", value: "$0.00", detail: "Exhausted · Expires Nov 5, 2099", isAmount: true},
                {status: "expired", value: "Expired", detail: "Expired Nov 5, 2000", isAmount: false},
                {status: "unavailable", value: "Unavailable", detail: "Balance could not be confirmed", isAmount: false}
            ]
            snapshot.selected = {provider: identity, idx: 0, metric: "credits:claude-cloud"}
            snapshot.providers = [{id: identity, providerId: "claude", idx: 0,
                name: "Claude (Max) · Work", logoPath: "", loading: false, cached: false, error: "",
                resetCredits: {available: 1, rows: []}, metrics: []}]
            usage.visible = true
            for (const state of states) {
                snapshot.providers[0].monetaryCredits = [Object.assign({id: "claude-cloud", title: "Cloud credits"}, state)]
                snapshot.providers[0].metrics = [
                    {key: "rolling", name: "Rolling Usage", percentage: 9, hasPercentage: true, value: "9%", detail: "Resets in 34m"},
                    {key: "credits:claude-cloud", name: "Cloud credits", percentage: null, hasPercentage: false,
                        isAmount: state.isAmount, value: state.value, detail: state.detail}
                ]
                Plugin.Model.snapshot = JSON.parse(JSON.stringify(snapshot))
                wait(20)
                const suffix = identity + "-0-credits:claude-cloud"
                const value = findChild(usage, "usage-value-" + suffix)
                compare(value.text, state.value)
                verify(value.visible)
                const progress = findChild(usage, "usage-bar-" + suffix)
                verify(!progress.visible)
                verify(!progress.parent.visible)
                verify(!findChild(usage, "usage-detail-" + suffix).visible)
                verify(findChild(usage, "usage-credit-arrow-" + suffix).visible)
                verify(findChild(usage, "usage-bar-" + identity + "-0-rolling").visible)
                const reset = findChild(usage, "reset-credits-" + identity + "-0")
                verify(reset.visible)
                mouseClick(value)
                compare(openedCredit.provider, identity)
                compare(openedCredit.idx, 0)
                compare(openedCredit.creditId, "claude-cloud")
                compare(Plugin.Model.chosen, null)
                compare(Plugin.Model.snapshot.selected.metric, "credits:claude-cloud")
                mouseClick(reset)
                compare(openedReset.provider, identity)
                compare(Plugin.Model.chosen, null)
                verifyMetricAlignment(snapshot.providers[0])
            }
        }
        function test_reorder_and_save() {
            settings.moveProvider(1, -1)
            settings.selected = {provider: "claude", idx: 0, metric: "weekly:Fable"}
            settings.save()
            compare(Plugin.Model.saved.enabled[0], "codex")
            compare(Plugin.Model.saved.selected.metric, "weekly:Fable")
            compare(Plugin.Model.saved.iconMode, "logo")
            compare(Plugin.Model.saved.usageDisplay, "used")
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
            compare(settings.validationSection, "general")
            verify(settings.validationMessage.indexOf("General") !== -1)
            settings.focusFirstControl()
            verify(findChild(settings, "usage-display").activeFocus)
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
            settings.selectSection("general")
            wait(20)
            const checkbox = findChild(settings, "display-show_pct")
            verify(checkbox !== null)
            mouseClick(checkbox)
            verify(!settings.display.show_pct)
            keyClick(Qt.Key_Space)
            verify(settings.display.show_pct)
            settings.selectSection("providers")
            wait(20)
            mouseClick(findChild(settings, "provider-claude"))
            compare(settings.selected.provider, "codex")
            settings.selectSection("general")
            wait(20)
            mouseClick(findChild(settings, "active-provider"))
            verify(settings.selectionOpen)
        }
        function test_provider_selector_logos_render_once_per_account_and_in_trigger() {
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
                compare(option.logoSource.toString(), "")
                compare(option.height, 30)
                const header = findChild(trigger.popupItem, "active-provider-group-" + choice.groupKey)
                verify(header !== null && header.visible)
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
        function test_account_groups_keep_identity_and_omit_internal_key_labels() {
            const snapshot = Plugin.Model.snapshot
            snapshot.providers.push(
                {id: "cursor", providerId: "cursor", idx: 0, name: "Cursor", loading: false, cached: false, metrics: [
                    {key: "monthly:Cursor Models included quota", name: "Cursor Models included quota", detail: ""},
                    {key: "monthly:Other Models included quota", name: "Other Models included quota", detail: ""},
                    {key: "monthly:On-demand spend this billing cycle (USD)", name: "On-demand spend this billing cycle", detail: ""}
                ]},
                {id: "account:work", providerId: "claude", idx: 0, name: "Claude (Max) · Work", loading: false, cached: false, metrics: [
                    {key: "weekly", name: "Weekly Usage", detail: ""}
                ]})
            snapshot.settings.order = ["claude", "cursor", "codex", "account:work"]
            snapshot.settings.enabled = snapshot.settings.order.slice()
            snapshot.settings.providerIds = {claude: "claude", cursor: "cursor", codex: "codex", "account:work": "claude"}
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            settings.begin()
            compare(settings.choices.map(item => item.provider).join(","), "claude,claude,claude,account:work,cursor,cursor,cursor,codex,codex")
            compare(settings.choices.filter(item => item.provider === "cursor").map(item => item.label).join(","), "Cursor Models,Other Models,On-demand spend")
            settings.selected = {provider: "cursor", idx: 0, metric: "monthly:On-demand spend this billing cycle (USD)"}
            compare(settings.selectedLabel, "Cursor · On-demand spend")
            const trigger = findChild(settings, "active-provider")
            mouseClick(trigger)
            wait(20)
            keyClick(Qt.Key_Home)
            for (let i = 0; i < 3; i++) keyClick(Qt.Key_Down)
            keyClick(Qt.Key_Return)
            compare(settings.selected.provider, "account:work")
            compare(settings.selectedLabel, "Claude (Max) · Work · Weekly")
            settings.save()
            compare(Plugin.Model.saved.selected.provider, "account:work")
            compare(Plugin.Model.saved.selected.metric, "weekly")
        }
        function test_identically_named_accounts_have_distinct_group_labels() {
            const snapshot = Plugin.Model.snapshot
            snapshot.providers.push({id: "claude", idx: 1, name: "Claude (Max)", loading: false, cached: false, metrics: [{key: "weekly", name: "Weekly Usage", detail: ""}]})
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            settings.begin()
            compare(settings.choices[0].groupLabel, "Claude (Max) · Account 1")
            compare(settings.choices[3].groupLabel, "Claude (Max) · Account 2")
            settings.selected = {provider: "claude", idx: 1, metric: "weekly"}
            settings.save()
            compare(Plugin.Model.saved.selected.idx, 1)
        }
        function test_all_selectors_overlay_without_resizing_and_support_keyboard() {
            const provider = findChild(settings, "active-provider")
            const icon = findChild(settings, "icon-mode")
            const usageDisplay = findChild(settings, "usage-display")
            wait(20)
            for (const trigger of [provider, icon, usageDisplay]) {
                settings.selectSection("general")
                wait(20)
                const height = settings.implicitHeight
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
            compare(settings.usageDisplay, "remaining")
            settings.selectSection("general")
            wait(20)
            mouseClick(icon)
            wait(20)
            keyClick(Qt.Key_Home)
            keyClick(Qt.Key_Return)
            compare(settings.iconMode, "off")
            settings.selectSection("general")
            wait(20)
            mouseClick(provider)
            wait(20)
            keyClick(Qt.Key_Escape)
            verify(!provider.popupOpen)
            verify(settings.visible)
            settings.selectSection("general")
            wait(20)
            const height = settings.implicitHeight
            mouseClick(icon)
            wait(20)
            mouseClick(icon.popupItem, 370, 780)
            verify(!icon.popupOpen)
            compare(settings.implicitHeight, height)
        }
        function test_submenus_keep_one_draft_and_cancel_reloads_every_section() {
            const provider = findChild(settings, "active-provider")
            mouseClick(provider)
            verify(settings.selectionOpen)
            settings.selectSection("general")
            verify(!settings.selectionOpen)
            settings.usageDisplay = "remaining"
            settings.iconMode = "logo"
            settings.selectSection("alerts")
            settings.alertThresholds = "90,100"
            settings.selectSection("providers")
            settings.toggleProvider("kiro")
            settings.selectSection("general")
            settings.selected = {provider: "codex", idx: 0, metric: "weekly"}
            settings.selectSection("about")
            verify(findChild(settings, "settings-section-about").visible)
            settings.save()
            compare(Plugin.Model.saved.usageDisplay, "remaining")
            compare(Plugin.Model.saved.iconMode, "logo")
            compare(Plugin.Model.saved.notifications.thresholds.join(","), "90,100")
            verify(Plugin.Model.saved.enabled.indexOf("kiro") !== -1)
            compare(Plugin.Model.saved.selected.provider, "codex")
            settings.selectSection("providers")
            settings.begin()
            compare(settings.section, "general")
            compare(settings.usageDisplay, "used")
            compare(settings.alertThresholds, "80,95,100")
            verify(settings.enabledProviders.indexOf("kiro") === -1)
        }
        function test_invalid_hidden_section_has_a_visible_review_action() {
            settings.alertThresholds = "101"
            settings.selectSection("general")
            wait(20)
            verify(!settings.valid)
            compare(settings.validationSection, "alerts")
            const review = findChild(settings, "settings-review-validation")
            verify(review.visible)
            mouseClick(review)
            compare(settings.section, "alerts")
            verify(!review.visible)
            settings.selectSection("unknown")
            compare(settings.section, "alerts")
            Plugin.Model.settingsSaving = true
            settings.selectSection("general")
            compare(settings.section, "alerts")
            Plugin.Model.settingsSaving = false
        }
        function test_usage_display_draft_save_reopen_and_validation() {
            compare(settings.usageDisplay, "used")
            settings.usageDisplay = "remaining"
            compare(Plugin.Model.snapshot.settings.usageDisplay, "used")
            settings.begin()
            compare(settings.usageDisplay, "used")
            settings.usageDisplay = "remaining"
            settings.save()
            compare(Plugin.Model.saved.usageDisplay, "remaining")
            const snapshot = Plugin.Model.snapshot
            snapshot.settings.usageDisplay = Plugin.Model.saved.usageDisplay
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            settings.begin()
            compare(settings.usageDisplay, "remaining")
            settings.usageDisplay = "invalid"
            verify(!settings.valid)
            Plugin.Model.saved = null
            settings.save()
            compare(Plugin.Model.saved, null)
            delete snapshot.settings.usageDisplay
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            settings.begin()
            compare(settings.usageDisplay, "used")
        }
        function test_usage_display_selector_dismisses_other_selectors_and_on_page_exit() {
            const provider = findChild(settings, "active-provider")
            const icon = findChild(settings, "icon-mode")
            const usageDisplay = findChild(settings, "usage-display")
            provider.popupOpen = true
            verify(provider.popupOpen)
            usageDisplay.popupOpen = true
            verify(usageDisplay.popupOpen)
            verify(settings.selectionOpen)
            verify(!provider.popupOpen)
            icon.popupOpen = true
            verify(icon.popupOpen)
            verify(!usageDisplay.popupOpen)
            usageDisplay.popupOpen = true
            verify(!icon.popupOpen)
            settings.visible = false
            verify(!settings.selectionOpen)
            verify(!usageDisplay.popupOpen)
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
            snapshot.providers[1].resetCredits = {available: 5, undetailed: 3, timezone: "Local time · UTC-03:00", rows: [
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
            const timezone = findChild(credits, "reset-timezone")
            compare(timezone.text, "Local time · UTC-03:00")
            verify(timezone.visible)
            compare(timezone.parent, credits)
            verify(findChild(table, "reset-timezone") === null)
            verify(timezone.y >= table.y + table.height)
            compare(findChild(table, "reset-remaining").text, "12d 2h left")
            compare(available.text, "5")
            verify(table.visible)
            compare(table.radius, Style.cornerRadius)
            compare(findChild(footer, "reset-available"), available)
            compare(findChild(footer, "reset-available-label").text, "Available resets")
            compare(available.font.weight, Font.Medium)
            verify(footer.y > header.y + header.height)
            verify(findChild(header, "reset-available") === null)
            compare(findChild(header, "reset-type-header").text, "Reset type")
            compare(findChild(header, "reset-expires-header").text, "Expires")
            const actionHeader = findChild(header, "reset-action-header")
            verify(actionHeader.width < findChild(header, "reset-expires-header").width)
            verify(actionHeader.x > findChild(header, "reset-expires-header").x)
            compare(header.color, Qt.rgba(credits.foreground.r, credits.foreground.g, credits.foreground.b, 0.04))
            compare(header.radius, Math.max(0, table.radius - 1))
            compare(footer.color, header.color)
            compare(footer.radius, header.radius)
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
            compare(timezone.text, "")
            verify(!timezone.visible)
            const empty = JSON.parse(JSON.stringify(snapshot))
            empty.providers[1].resetCredits = null
            Plugin.Model.snapshot = empty
            verify(!findChild(credits, "reset-table").visible)
            verify(!available.visible)
            verify(!timezone.visible)
            compare(Plugin.Model.snapshot.selected.provider, "claude")
        }
        function prepareActionableReset(overrides) {
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.providers[1] = Object.assign({}, snapshot.providers[1], {
                id: "account:work", providerId: "codex", idx: 2, name: "Codex (Plus) · Work",
                logoPath: decodeURIComponent(Qt.resolvedUrl("assets/providers/codex.png").toString().replace(/^file:\/\//, "")),
                resetAction: {fingerprint: "observed-account-token"},
                resetCredits: {available: 2, undetailed: 0, rows: [
                    {title: "Full reset", count: 2, expires: "Oct 22, 18:05", remaining: "12d left", actionId: "opaque-credit-handle"}
                ]}
            }, overrides || {})
            Plugin.Model.snapshot = snapshot
            settings.visible = false
            credits.visible = true
            wait(20)
            return snapshot
        }
        function test_reset_apply_opens_confirmation_and_cancel_never_submits() {
            prepareActionableReset()
            const apply = findChild(credits, "reset-apply")
            verify(apply.visible && apply.enabled)
            compare(findChild(credits, "reset-confirmation"), null)
            mouseClick(apply)
            const confirmation = findChild(credits, "reset-confirmation")
            const cancel = findChild(credits, "reset-cancel")
            verify(confirmation.visible)
            compare(confirmation.parent.objectName, "reset-row")
            compare(confirmation.width, confirmation.parent.width)
            verify(!apply.visible)
            compare(Plugin.Model.resetRequests.length, 0)
            const details = findChild(credits, "reset-confirmation-details")
            verify(details.text.indexOf("Codex (Plus) · Work") !== -1)
            verify(details.text.indexOf("Full reset") !== -1)
            verify(details.text.indexOf("1 reset credit") !== -1)
            tryVerify(() => cancel.activeFocus)
            keyClick(Qt.Key_Return)
            verify(!confirmation.visible)
            compare(Plugin.Model.resetRequests.length, 0)
            tryVerify(() => apply.activeFocus)
            mouseClick(apply)
            mouseClick(cancel)
            verify(!confirmation.visible)
            compare(Plugin.Model.resetRequests.length, 0)
        }
        function holdMouseUntilApplied(confirm) {
            mousePress(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            tryVerify(() => Plugin.Model.resetRequests.length === 1, 3500)
            mouseRelease(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
        }
        function openResetConfirmation() {
            mouseClick(findChild(credits, "reset-apply"))
            const cancel = findChild(credits, "reset-cancel")
            tryVerify(() => cancel.activeFocus)
            return findChild(credits, "reset-confirm")
        }
        function test_reset_confirm_submits_once_with_connection_identity() {
            const snapshot = prepareActionableReset()
            const apply = findChild(credits, "reset-apply")
            mouseClick(apply)
            compare(Plugin.Model.resetRequests.length, 0)
            tryVerify(() => findChild(credits, "reset-cancel").activeFocus)
            const confirm = findChild(credits, "reset-confirm")
            confirm.forceActiveFocus(Qt.TabFocusReason)
            keyClick(Qt.Key_Return)
            compare(Plugin.Model.resetRequests.length, 0)
            keyPress(Qt.Key_Return)
            tryVerify(() => Plugin.Model.resetRequests.length === 1, 3500)
            keyRelease(Qt.Key_Return)
            compare(Plugin.Model.resetRequests.length, 1)
            const request = Plugin.Model.resetRequests[0]
            compare(request.provider, "account:work")
            compare(request.idx, 2)
            compare(request.fingerprint, "observed-account-token")
            compare(request.credit, "opaque-credit-handle")
            compare(request.confirmed, true)
            verify(Plugin.Model.resetApplying)
            compare(findChild(credits, "reset-confirmation"), null)
            verify(!apply.visible)
            credits.confirmReset()
            credits.requestReset(snapshot.providers[1].resetCredits.rows[0])
            compare(Plugin.Model.resetRequests.length, 1)
            compare(findChild(credits, "reset-status").text, "Applying reset…")
            Plugin.Model.resetApplying = false
            Plugin.Model.resetMessage = "Reset applied. Usage is refreshing."
            compare(findChild(credits, "reset-status").text, Plugin.Model.resetMessage)
            verify(!apply.visible)
            snapshot.providers[1].resetAction.fingerprint = "fresh-observation-token"
            Plugin.Model.snapshot = JSON.parse(JSON.stringify(snapshot))
            verify(findChild(credits, "reset-apply").visible)
            compare(Plugin.Model.resetRequests.length, 1)
        }
        function test_reset_hold_released_early_and_pointer_leave_do_not_submit() {
            prepareActionableReset()
            const confirm = openResetConfirmation()
            compare(confirm.holdDuration, 3000)
            mousePress(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            wait(200)
            verify(confirm.progress > 0 && confirm.progress < 1)
            mouseRelease(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            compare(confirm.progress, 0)
            compare(Plugin.Model.resetRequests.length, 0)
            mousePress(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            wait(100)
            mouseMove(confirm, -10, confirm.height / 2)
            tryCompare(confirm, "holding", false)
            compare(confirm.progress, 0)
            mouseMove(confirm, confirm.width / 2, confirm.height / 2)
            wait(3100)
            compare(Plugin.Model.resetRequests.length, 0)
            mouseRelease(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            mouseClick(findChild(credits, "reset-cancel"))
            compare(credits.confirmation, null)
        }
        function test_reset_mouse_hold_fills_and_applies_once_after_three_seconds() {
            prepareActionableReset()
            const confirm = openResetConfirmation()
            compare(confirm.holdDuration, 3000)
            compare(confirm.progress, 0)
            verify(confirm.color.a > 0 && confirm.color.a < 0.2)
            mousePress(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            wait(2500)
            verify(confirm.progress > 0.7 && confirm.progress < 1)
            compare(Plugin.Model.resetRequests.length, 0)
            tryVerify(() => Plugin.Model.resetRequests.length === 1, 1000)
            wait(200)
            compare(Plugin.Model.resetRequests.length, 1)
            mouseRelease(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            compare(Plugin.Model.resetRequests.length, 1)
        }
        function test_reset_initial_apply_press_never_starts_confirmation_hold() {
            prepareActionableReset()
            const apply = findChild(credits, "reset-apply")
            mousePress(apply, apply.width / 2, apply.height / 2, Qt.LeftButton)
            wait(3100)
            compare(credits.confirmation, null)
            compare(Plugin.Model.resetRequests.length, 0)
            mouseRelease(apply, apply.width / 2, apply.height / 2, Qt.LeftButton)
            const confirm = findChild(credits, "reset-confirm")
            verify(confirm !== null)
            verify(!confirm.holding)
            compare(confirm.progress, 0)
            compare(Plugin.Model.resetRequests.length, 0)
        }
        function test_reset_keyboard_hold_release_focus_loss_and_escape_cancel() {
            prepareActionableReset()
            const confirm = openResetConfirmation()
            const cancel = findChild(credits, "reset-cancel")
            confirm.forceActiveFocus(Qt.TabFocusReason)
            keyPress(Qt.Key_Space)
            wait(100)
            verify(confirm.progress > 0)
            keyRelease(Qt.Key_Space)
            compare(confirm.progress, 0)
            compare(Plugin.Model.resetRequests.length, 0)
            keyPress(Qt.Key_Space)
            wait(100)
            cancel.forceActiveFocus(Qt.TabFocusReason)
            compare(confirm.progress, 0)
            verify(!confirm.holding)
            keyRelease(Qt.Key_Space)
            confirm.forceActiveFocus(Qt.TabFocusReason)
            keyPress(Qt.Key_Space)
            wait(100)
            keyClick(Qt.Key_Escape)
            compare(credits.confirmation, null)
            compare(confirm.progress, 0)
            keyRelease(Qt.Key_Space)
            compare(Plugin.Model.resetRequests.length, 0)
        }
        function test_reset_apply_is_hidden_for_ineligible_inventory_data() {
            return [
                {tag: "cached", overrides: {cached: true}},
                {tag: "loading", overrides: {loading: true}},
                {tag: "no action context", overrides: {resetAction: null}},
                {tag: "no credit handle", overrides: {resetCredits: {available: 1, undetailed: 0, rows: [
                    {title: "Full reset", count: 1, expires: "Not provided", remaining: ""}
                ]}}}
            ]
        }
        function test_reset_apply_is_hidden_for_ineligible_inventory(data) {
            const snapshot = prepareActionableReset(data.overrides)
            verify(!findChild(credits, "reset-apply").visible)
            credits.requestReset(snapshot.providers[1].resetCredits.rows[0])
            compare(credits.confirmation, null)
            credits.confirmReset()
            compare(Plugin.Model.resetRequests.length, 0)
        }
        function test_reset_buttons_are_disabled_while_another_account_is_applying() {
            const snapshot = prepareActionableReset()
            Plugin.Model.resetTarget = {provider: "account:personal", idx: 0}
            Plugin.Model.resetApplying = true
            const apply = findChild(credits, "reset-apply")
            verify(apply.visible)
            verify(!apply.enabled)
            credits.requestReset(snapshot.providers[1].resetCredits.rows[0])
            compare(credits.confirmation, null)
            compare(Plugin.Model.resetRequests.length, 0)
        }
        function test_reset_confirm_is_invalidated_when_account_details_change_data() {
            return [
                {tag: "account switched", field: "id", value: "account:personal"},
                {tag: "new observation", field: "resetAction", value: {fingerprint: "new-token"}},
                {tag: "cached", field: "cached", value: true},
                {tag: "loading", field: "loading", value: true},
                {tag: "credit disappeared", field: "resetCredits", value: {available: 1, undetailed: 1, rows: []}}
            ]
        }
        function test_reset_confirm_is_invalidated_when_account_details_change(data) {
            const snapshot = prepareActionableReset()
            const confirm = openResetConfirmation()
            verify(credits.confirmation !== null)
            confirm.forceActiveFocus(Qt.TabFocusReason)
            keyPress(Qt.Key_Space)
            wait(100)
            verify(confirm.progress > 0)
            snapshot.providers[1][data.field] = data.value
            Plugin.Model.snapshot = JSON.parse(JSON.stringify(snapshot))
            compare(credits.confirmation, null)
            if (data.field !== "resetCredits") {
                verify(!confirm.holding)
                compare(confirm.progress, 0)
            }
            keyRelease(Qt.Key_Space)
            credits.confirmReset()
            compare(Plugin.Model.resetRequests.length, 0)
        }
        function test_reset_update_start_discards_active_hold() {
            prepareActionableReset()
            const confirm = openResetConfirmation()
            mousePress(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            wait(100)
            verify(confirm.holding)
            Plugin.Model.updateRunning = true
            compare(credits.confirmation, null)
            verify(!confirm.holding)
            compare(confirm.progress, 0)
            mouseRelease(confirm, confirm.width / 2, confirm.height / 2, Qt.LeftButton)
            compare(Plugin.Model.resetRequests.length, 0)
        }
        function test_reset_hidden_page_discards_confirmation_and_error_does_not_retry() {
            prepareActionableReset()
            const hold = openResetConfirmation()
            hold.forceActiveFocus(Qt.TabFocusReason)
            keyPress(Qt.Key_Space)
            wait(100)
            credits.visible = false
            compare(credits.confirmation, null)
            verify(!hold.holding)
            compare(hold.progress, 0)
            keyRelease(Qt.Key_Space)
            credits.confirmReset()
            compare(Plugin.Model.resetRequests.length, 0)
            credits.visible = true
            holdMouseUntilApplied(openResetConfirmation())
            compare(Plugin.Model.resetRequests.length, 1)
            Plugin.Model.resetApplying = false
            Plugin.Model.resetError = "Result unknown. Refresh and check the account before applying another reset."
            compare(findChild(credits, "reset-status").text, Plugin.Model.resetError)
            verify(!findChild(credits, "reset-apply").visible)
            credits.confirmReset()
            compare(Plugin.Model.resetRequests.length, 1)
        }
    }
}
