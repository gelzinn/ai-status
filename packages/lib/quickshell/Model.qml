pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    visible: false
    property int consumers: 0
    property int retryDelay: 1000
    property string errorMessage: ""
    property var snapshot: ({text: "AI Status …", providers: [], selected: {}, loading: true})
    property var actions: []
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
        if (command === "config") {
            Quickshell.execDetached(["python3", cliPath, "config"])
        } else if (["refresh", "scroll-up", "scroll-down", "cycle-metric"].indexOf(command) !== -1) {
            actions = actions.concat([command])
            drain()
        }
    }

    function drain() {
        if (consumers === 0 || actionProcess.running || actions.length === 0) return
        const command = actions[0]
        actions = actions.slice(1)
        actionProcess.exec(["python3", cliPath, command, "--frontend", "quickshell"])
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
