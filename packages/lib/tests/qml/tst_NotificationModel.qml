import QtQuick
import QtTest
import "modeltest" as Backend

Item {
    Item { id: firstWidget }
    Item { id: secondWidget }
    SignalSpy { id: activation; target: Backend.Model; signalName: "notificationActivated" }
    TestCase {
        name: "NotificationModel"
        when: windowShown
        function init() {
            Backend.Model.receivedSnapshot = false
            Backend.Model.notificationActivationId = ""
            Backend.Model.consumerWidgets = []
            Backend.Model.consumers = 0
            Backend.Model.updateStage = "idle"
            Backend.Model.updateRunning = false
            Backend.Model.updateError = ""
            Backend.Model.updateMessage = ""
            Backend.Model.resetApplying = false
            Backend.Model.resetTarget = null
            Backend.Model.resetAttempts = []
            Backend.Model.settingsSaving = false
            Backend.Model.settingsError = ""
            activation.clear()
        }
        function snapshot(identity) {
            return JSON.stringify({schemaVersion: 1, text: "Claude 95%", providers: [],
                notificationActivation: identity ? {id: identity, provider: "claude", idx: 0, metric: "weekly"} : null})
        }
        function test_notification_click_opens_once_and_restart_does_not_replay() {
            Backend.Model.accept(snapshot("old"))
            compare(activation.count, 0)
            Backend.Model.accept(snapshot("old"))
            compare(activation.count, 0)
            Backend.Model.accept(snapshot("new"))
            compare(activation.count, 1)
            Backend.Model.accept(snapshot("new"))
            compare(activation.count, 1)
            Backend.Model.accept(snapshot(null))
            Backend.Model.accept(snapshot("new"))
            compare(activation.count, 1)
        }
        function test_multiple_monitors_share_one_notification_owner() {
            Backend.Model.acquire(firstWidget)
            Backend.Model.acquire(secondWidget)
            compare(Backend.Model.notificationOwner, firstWidget)
            compare(Backend.Model.consumers, 2)
            Backend.Model.release(firstWidget)
            compare(Backend.Model.notificationOwner, secondWidget)
            Backend.Model.release(secondWidget)
            compare(Backend.Model.notificationOwner, null)
            compare(Backend.Model.consumers, 0)
        }
        function test_settings_writer_serializes_refresh_interval_with_existing_draft() {
            Backend.Model.consumers = 1
            Backend.Model.snapshot = {settings: {refreshIntervalMinutes: 5}}
            const process = findChild(Backend.Model, "settings-process")
            const draft = {enabled: ["claude"], usageDisplay: "remaining", refreshIntervalMinutes: 30,
                selected: {provider: "claude", idx: 0, metric: "weekly"}}
            Backend.Model.saveSettings(draft)
            verify(Backend.Model.settingsSaving)
            compare(process.command[2], "save-settings")
            compare(process.command[4], "quickshell")
            compare(JSON.parse(process.command[6]).refreshIntervalMinutes, 30)
            compare(JSON.parse(process.command[6]).usageDisplay, "remaining")
            compare(Backend.Model.snapshot.settings.refreshIntervalMinutes, 5)
            const command = JSON.stringify(process.command)
            Backend.Model.saveSettings({refreshIntervalMinutes: 60})
            compare(JSON.stringify(process.command), command)
            process.exited(0, 0)
            process.running = false
            verify(!Backend.Model.settingsSaving)
        }
        function test_update_and_reset_do_not_dispatch_while_the_other_is_running() {
            Backend.Model.consumers = 1
            Backend.Model.snapshot = {update: {canUpdate: true}, providers: [
                {id: "codex", idx: 0, loading: false, cached: false,
                 resetAction: {fingerprint: "current-observation"},
                 resetCredits: {rows: [{actionId: "selected-credit"}]}}
            ]}
            const process = findChild(Backend.Model, "update-process")
            const command = JSON.stringify(process.command)
            Backend.Model.resetApplying = true
            Backend.Model.startUpdate()
            verify(!Backend.Model.updateRunning)
            compare(JSON.stringify(process.command), command)
            Backend.Model.resetApplying = false
            Backend.Model.updateRunning = true
            verify(!Backend.Model.applyReset({provider: "codex", idx: 0,
                fingerprint: "current-observation", credit: "selected-credit", confirmed: true}))
            verify(!Backend.Model.resetApplying)
            compare(Backend.Model.resetAttempts.length, 0)
            compare(Backend.Model.resetTarget, null)
        }
        function test_update_progress_accepts_confirmed_terminal_handoff_and_ignores_invalid_events() {
            Backend.Model.acceptUpdateProgress("  " + JSON.stringify({stage: "checking", message: "Checking release"}) + "\n")
            compare(Backend.Model.updateStage, "checking")
            Backend.Model.acceptUpdateProgress("broken JSON")
            Backend.Model.acceptUpdateProgress(JSON.stringify({stage: "opening", message: 42}))
            Backend.Model.acceptUpdateProgress(JSON.stringify({stage: "downloading", message: "Unsupported here"}))
            compare(Backend.Model.updateStage, "checking")
            compare(Backend.Model.updateMessage, "Checking release")
            Backend.Model.acceptUpdateProgress(JSON.stringify({stage: "error", message: "Terminal unavailable"}))
            compare(Backend.Model.updateError, "Terminal unavailable")
            compare(Backend.Model.updateMessage, "")
            Backend.Model.acceptUpdateProgress(JSON.stringify({stage: "opening", message: "Opening terminal"}))
            compare(Backend.Model.updateStage, "opening")
            compare(Backend.Model.updateError, "")
            Backend.Model.acceptUpdateProgress(JSON.stringify({stage: "complete", message: "The terminal is open"}))
            compare(Backend.Model.updateStage, "complete")
            compare(Backend.Model.updateMessage, "The terminal is open")
        }
        function test_update_process_requires_success_and_confirmed_completion() {
            Backend.Model.consumers = 1
            Backend.Model.snapshot = {update: {canUpdate: true}}
            const process = findChild(Backend.Model, "update-process")
            Backend.Model.startUpdate()
            verify(Backend.Model.updateRunning)
            compare(process.command[process.command.length - 1], "--json-progress")
            process.exited(0, 0)
            verify(!Backend.Model.updateRunning)
            compare(Backend.Model.updateStage, "error")
            verify(Backend.Model.updateError.indexOf("before confirming") !== -1)
            compare(Backend.Model.updateMessage, "")
            Backend.Model.startUpdate()
            Backend.Model.acceptUpdateProgress(JSON.stringify({stage: "complete", message: "The terminal is open"}))
            process.exited(0, 0)
            compare(Backend.Model.updateStage, "complete")
            compare(Backend.Model.updateError, "")
            compare(Backend.Model.updateMessage, "The terminal is open")
            Backend.Model.startUpdate()
            Backend.Model.acceptUpdateProgress(JSON.stringify({stage: "error", message: "Terminal unavailable"}))
            process.exited(1, 0)
            compare(Backend.Model.updateStage, "error")
            compare(Backend.Model.updateError, "Terminal unavailable")
            compare(Backend.Model.updateMessage, "")
            process.running = false
        }
    }
}
