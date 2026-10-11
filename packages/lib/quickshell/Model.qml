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
    signal settingsSaved()
    property int frame: 0
    readonly property string spinner: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"][frame % 10]
    readonly property string cliPath: decodeURIComponent(Qt.resolvedUrl("../src/bin/ai-status").toString().replace(/^file:\/\//, ""))

    function acquire() {
        consumers += 1
        if (consumers === 1 && !backend.running) backend.running = true
    }

    function release() {
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
            snapshot = next
            errorMessage = ""
            retryDelay = 1000
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
        updateRunning = true
        updateProcess.exec(["python3", cliPath, "update"])
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
        stdout: SplitParser { onRead: data => root.updateMessage = data }
        stderr: SplitParser { onRead: data => root.updateError = data }
        onExited: (exitCode, exitStatus) => {
            root.updateRunning = false
            if (exitCode !== 0 || exitStatus !== 0) {
                root.updateMessage = ""
                root.updateError = root.updateError || "Could not start the update. Try again or use the command above."
            }
        }
        onRunningChanged: if (!running) Qt.callLater(() => {
            if (root.updateRunning) {
                root.updateRunning = false
                root.updateError = root.updateError || "Could not start the updater. Use the command above."
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
