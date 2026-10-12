pragma Singleton

import QtQuick
import Quickshell.Io

Item {
    id: root
    visible: false
    property int consumers: 0
    property int retryDelay: 1000
    property string errorMessage: ""
    property var snapshot: ({text: "AI Status …", providers: [], selected: {}, loading: true})
    property var actions: []
    property bool settingsSaving: false
    property string settingsError: ""
    property bool updateRunning: false
    property string updateError: ""
    property string updateMessage: ""
    property string updateStage: "idle"
    signal settingsSaved()
    signal notificationActivated()
    property var consumerWidgets: []
    readonly property var notificationOwner: consumerWidgets.length ? consumerWidgets[0] : null
    property string notificationActivationId: ""
    property bool receivedSnapshot: false
    property int frame: 0
    readonly property string spinner: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"][frame % 10]
    readonly property string cliPath: decodeURIComponent(Qt.resolvedUrl("../src/bin/ai-status").toString().replace(/^file:\/\//, ""))

    function acquire(widget) {
        if (widget) consumerWidgets = consumerWidgets.concat([widget])
        consumers += 1
        if (consumers === 1 && !backend.running) backend.running = true
    }

    function release(widget) {
        consumerWidgets = consumerWidgets.filter(item => item !== widget)
        consumers = Math.max(0, consumers - 1)
        if (consumers === 0) {
            retry.stop()
            backend.running = false
            actions = []
            actionProcess.running = false
            settingsProcess.running = false
        }
    }

    function accept(line) {
        try {
            const next = JSON.parse(line)
            if (next.schemaVersion !== 1 || typeof next.text !== "string" || !Array.isArray(next.providers)) return
            const activation = next.notificationActivation
            const identity = activation && typeof activation.id === "string" ? activation.id : ""
            const activate = receivedSnapshot && identity && identity !== notificationActivationId
            notificationActivationId = identity || notificationActivationId
            receivedSnapshot = true
            snapshot = next
            errorMessage = ""
            retryDelay = 1000
            if (activate) notificationActivated()
        } catch (error) {
            // A partial/invalid line must never replace the last usable data.
            console.warn("AI Status: ignored invalid daemon output")
        }
    }

    function action(command) {
        if (["refresh", "scroll-up", "scroll-down", "cycle-metric"].indexOf(command) !== -1) {
            if (command === "refresh" && snapshot.loading) return
            actions = actions.concat([[command, "--frontend", "quickshell"]])
            drain()
        }
    }

    function selectMetric(provider, idx, metric) {
        actions = actions.concat([["select-metric", "--frontend", "quickshell", "--selection-json",
                                  JSON.stringify({provider: provider, idx: idx, metric: metric})]])
        drain()
    }

    function saveSettings(settings) {
        if (settingsSaving || consumers === 0) return
        settingsError = ""
        settingsSaving = true
        settingsProcess.exec(["python3", cliPath, "save-settings", "--frontend", "quickshell", "--settings-json", JSON.stringify(settings)])
    }

    function startUpdate() {
        if (updateRunning || consumers === 0 || !snapshot.update || !snapshot.update.canUpdate) return
        updateError = ""
        updateMessage = ""
        updateStage = "checking"
        updateRunning = true
        updateProcess.exec(["python3", cliPath, "update", "--json-progress"])
    }

    function acceptUpdateProgress(line) {
        try {
            const event = JSON.parse(line)
            if (!event || ["checking", "opening", "complete", "error"].indexOf(event.stage) === -1 || typeof event.message !== "string") return
            updateStage = event.stage
            if (event.stage === "error") {
                updateError = event.message
                updateMessage = ""
            } else {
                updateMessage = event.message
                updateError = ""
            }
        } catch (error) {
            // A malformed line cannot claim that the terminal opened.
        }
    }

    function drain() {
        if (consumers === 0 || actionProcess.running || actions.length === 0) return
        const command = actions[0]
        actions = actions.slice(1)
        actionProcess.exec(["python3", cliPath].concat(command))
    }

    Process {
        id: backend
        command: ["python3", root.cliPath, "daemon", "--format", "quickshell"]
        stdout: SplitParser { onRead: data => root.accept(data) }
        stderr: SplitParser { onRead: data => console.warn("AI Status daemon:", data) }
        onRunningChanged: {
            if (!running && root.consumers > 0) {
                root.errorMessage = "AI Status is reconnecting. Check the shell logs if this persists."
                retry.restart()
            }
        }
    }

    Process {
        id: actionProcess
        onRunningChanged: if (!running) Qt.callLater(root.drain)
    }

    Process {
        id: settingsProcess
        stderr: SplitParser { onRead: data => root.settingsError = data }
        onExited: (exitCode, exitStatus) => {
            root.settingsSaving = false
            if (exitCode === 0 && exitStatus === 0) {
                root.settingsError = ""
                root.settingsSaved()
            } else if (!root.settingsError) {
                root.settingsError = "Could not save settings. Try again."
            }
        }
        onRunningChanged: {
            if (!running) Qt.callLater(() => {
                if (root.settingsSaving) {
                    root.settingsSaving = false
                    root.settingsError = root.settingsError || "Could not start the settings writer."
                }
            })
        }
    }

    Process {
        id: updateProcess
        objectName: "update-process"
        stdout: SplitParser { onRead: data => root.acceptUpdateProgress(data) }
        stderr: SplitParser { onRead: data => root.updateError = data }
        onExited: (exitCode, exitStatus) => {
            root.updateRunning = false
            if (exitCode !== 0 || exitStatus !== 0) {
                root.updateMessage = ""
                root.updateStage = "error"
                root.updateError = root.updateError || "Could not start the update. Try again or use the terminal command."
            } else if (root.updateStage !== "complete") {
                root.updateMessage = ""
                root.updateStage = "error"
                root.updateError = root.updateError || "The updater stopped before confirming the terminal opened. Try again."
            }
        }
        onRunningChanged: if (!running) Qt.callLater(() => {
            if (root.updateRunning) {
                root.updateRunning = false
                root.updateStage = "error"
                root.updateError = root.updateError || "Could not start the updater. Use the terminal command."
            }
        })
    }

    Timer {
        interval: 150
        repeat: true
        running: root.consumers > 0 && root.snapshot.loading === true
        onTriggered: root.frame = (root.frame + 1) % 10
    }

    Timer {
        id: retry
        interval: root.retryDelay
        onTriggered: {
            if (root.consumers > 0 && !backend.running) {
                root.retryDelay = Math.min(30000, root.retryDelay * 2)
                backend.running = true
            }
        }
    }
}
