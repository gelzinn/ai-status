pragma Singleton

import QtQuick
import Quickshell.Io

QtObject {
    // Load the shared geometry once per QML engine, independent of the number
    // of controls in the panel. FileView needs no QML XHR environment flags.
    readonly property FileView sourceFile: FileView {
        id: resource
        path: Qt.resolvedUrl("../assets/panel-icons.json")
        blockLoading: true
    }
    readonly property var data: JSON.parse(resource.text())
    readonly property var svgPaths: {
        const result = {}
        for (const name in data.paths)
            result[name] = data.paths[name].map(command => command.join(" ")).join(" ")
        return result
    }

    function path(name) { return svgPaths[name] || "" }
}
