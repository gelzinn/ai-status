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
