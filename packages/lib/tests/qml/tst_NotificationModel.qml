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
    }
}
