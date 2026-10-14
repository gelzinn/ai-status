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
    readonly property bool canSelectMetric: !snapshot.settings || !snapshot.settings.items || snapshot.settings.items.length <= 1
    property var actions: []
    property bool settingsSaving: false
    property string settingsError: ""
    property bool updateRunning: false
    property string updateError: ""
    property string updateMessage: ""
    property string updateStage: "idle"
    property bool resetApplying: false
    property string resetError: ""
    property string resetMessage: ""
    property var resetTarget: null
    property var resetAttempts: []
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
            // An explicitly confirmed reset must finish even if its widget closes.
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
            if (command !== "refresh" && !canSelectMetric) return
            if (command === "refresh" && snapshot.loading) return
            actions = actions.concat([[command, "--frontend", "quickshell"]])
            drain()
        }
    }

    function selectMetric(provider, idx, metric) {
        if (!canSelectMetric) return
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
        if (updateRunning || resetApplying || consumers === 0 || !snapshot.update || !snapshot.update.canUpdate) return
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

    function resetAttempted(provider, idx, fingerprint) {
        return resetAttempts.some(attempt => attempt.provider === provider && attempt.idx === idx && attempt.fingerprint === fingerprint)
    }

    function applyReset(request) {
        if (resetApplying || updateRunning || consumers === 0 || !request || request.confirmed !== true) return false
        const provider = snapshot.providers.find(entry => entry.id === request.provider && entry.idx === request.idx)
        const eligible = provider && !provider.cached && !provider.loading && provider.resetAction
            && provider.resetAction.fingerprint === request.fingerprint
            && !resetAttempted(request.provider, request.idx, request.fingerprint)
            && provider.resetCredits && (provider.resetCredits.rows || []).some(row => row.actionId === request.credit)
        resetTarget = {provider: request.provider, idx: request.idx}
        resetMessage = ""
        resetError = ""
        if (!eligible) {
            resetError = "Reset details changed. Refresh and review them before applying a reset."
            return false
        }
        // An uncertain result must be reviewed with fresh data, never resent automatically.
        resetAttempts = resetAttempts.concat([{provider: request.provider, idx: request.idx, fingerprint: request.fingerprint}])
        resetApplying = true
        resetProcess.exec(["python3", cliPath, "apply-reset", "--request-json", JSON.stringify(request), "--frontend", "quickshell"])
        return true
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
        objectName: "settings-process"
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

    Process {
        id: resetProcess
        stdout: SplitParser { onRead: data => root.resetMessage = data }
        stderr: SplitParser { onRead: data => root.resetError = data }
        onExited: (exitCode, exitStatus) => {
            root.resetApplying = false
            if (exitCode === 0 && exitStatus === 0) {
                root.resetError = ""
                root.resetMessage = root.resetMessage || "Reset applied. Usage is refreshing."
            } else {
                root.resetMessage = ""
                root.resetError = root.resetError || "Could not confirm the reset result. Refresh and check your account before applying another reset."
            }
        }
        onRunningChanged: if (!running) Qt.callLater(() => {
            if (root.resetApplying) {
                root.resetApplying = false
                root.resetMessage = ""
                root.resetError = root.resetError || "Could not start the reset action. Refresh and review your account before applying a reset."
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
